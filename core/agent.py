# core/agent.py
"""Agent 核心模块 - 两层模型架构"""

import os
from typing import Dict, Optional, List
from datetime import datetime

from .llm_manager import LLMManager
from .skill_engine import SkillEngine
from tools import InboxTool, InboxListTool, ScheduleTool, ScheduleListTool
from tools import TodoAddTool, TodoListTool, TodoCompleteTool, TodoUpdateTool, TodoCancelTool
from tools.modules import ToolModule, ModuleRegistry
from services.database import DatabaseManager
from utils import get_logger

logger = get_logger("agent")

MAX_AGENT_ROUNDS = 5  # Agent Loop 最大轮次，防止死循环


# === 第一层 Router Prompt ===
ROUTER_PROMPT = """你是一个意图识别助手。根据用户消息，判断应该使用哪个模块处理。

可用模块：
{modules}

重要区分：

- **schedule（日程）**：时间锚定的事件，“即使我不去，事件也会发生/过去”
  关键特征：开会、约会、航班、就诊、几点开始、比赛
  ​
- **todo（待办）**：需要我完成的任务，“不做就一直悬着，等着我去完成”
  关键特征：交报告、买菜、背单词、写代码、截止、完成、待办、要做
  ​
- **timeline（时间线）**：记录/查看**已完成**的活动（过去时态）
  关键特征：刚才、今天上午、昨天、做了、完成了、干了什么

判断要点：
- 当前时间是 {current_time}，当前日期是 {today}
- 过去时态的描述 → timeline
- “到时候即使我不做，事件也会发生” → schedule
- “不做就一直悬着” → todo  
- 查看待办/任务列表 → todo
- 查看日程/安排 → schedule
- 标记完成/取消任务 → todo

规则：
1. 只输出模块名称（英文），不要其他内容
2. 如果无法确定，输出 inbox

用户消息: {message}

请输出模块名称:"""


# === 第二层 Executor Prompt ===
# 基础模板，{skill_instructions} 由 SkillEngine 从 SKILL.md 动态注入
EXECUTOR_BASE = """你是 Dailylaid，一个个人日常事务管理助手。
当前日期: {today}
当前时间: {current_time}

{skill_instructions}
"""

# 当 SKILL.md 缺失时的兜底指令
FALLBACK_INSTRUCTIONS = """请根据用户消息调用合适的工具。如果不确定如何处理，使用 inbox 工具保存。
回复时请简洁友好，使用中文。"""


class DailylaidAgent:
    """Dailylaid Agent 核心 - 两层模型架构
    
    第一层 (Router): 快速判断使用哪个模块（使用轻量模型）
    第二层 (Executor): 在模块内调用具体工具（使用完整模型）
    """
    
    def __init__(self, llm_manager: LLMManager, db: DatabaseManager):
        """初始化 Agent
        
        Args:
            llm_manager: LLM 多模型管理器
            db: 数据库管理器
        """
        self.llm = llm_manager
        self.db = db
        self.modules = ModuleRegistry()
        
        # 注册模块
        self._register_modules()
        
        # 初始化所有工具
        self.modules.init_all_tools(db)
        
        # 获取 inbox 工具（兜底用）
        self.inbox_tool = self.modules.get_tool_by_name("inbox")
        
        # 初始化 SkillEngine
        skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        self.skill_engine = SkillEngine(skills_dir)
        discovered = self.skill_engine.discover()
        logger.info(f"SkillEngine 初始化完成，发现 {len(discovered)} 个 Skill")
    
    def _register_modules(self):
        """注册所有模块"""
        
        # 日程模块
        self.modules.register(ToolModule(
            name="schedule",
            description="日程管理：添加、查看日程安排",
            tools=[ScheduleTool, ScheduleListTool],
            keywords=["日程", "安排", "开会", "约会", "提醒", "几点", "明天", "下周"]
        ))
        
        # 时间线模块（活动记录）
        from tools import TimelineRecordTool, TimelineUpdateTool, TimelineListTool, TimelineViewTool
        self.modules.register(ToolModule(
            name="timeline",
            description="时间线活动记录：记录**已完成**的活动（过去时态），查看时间线。例如：我刚才做了什么，今天干了什么",
            tools=[TimelineRecordTool, TimelineUpdateTool, TimelineListTool, TimelineViewTool],
            keywords=["记录", "时间线", "刚才", "完成了", "干了", "做了", "起床", "吃完", "结束", "写代码了", "上午", "下午"]
        ))
        
        # 待办任务模块
        self.modules.register(ToolModule(
            name="todo",
            description="待办任务：需要完成的事情，不做就一直悬着。添加/查看/完成/修改/取消待办任务",
            tools=[TodoAddTool, TodoListTool, TodoCompleteTool, TodoUpdateTool, TodoCancelTool],
            keywords=["待办", "要做", "交报告", "买菜", "背单词", "截止", "之前完成", "deadline", "任务", "完成了吗"]
        ))
        
        # 收集箱模块（兜底）
        self.modules.register(ToolModule(
            name="inbox",
            description="收集箱：保存暂时无法分类的内容，或查看收集箱",
            tools=[InboxTool, InboxListTool],
            keywords=["记一下", "收集箱", "待处理"]
        ))
    
    async def process(self, user_id: str, message: str,
                      message_type: str = "private", group_id: str = None) -> str:
        """处理用户消息（两层架构）"""
        try:
            # 第一层：路由
            module_name = await self._route(message)
            logger.info(f"路由结果: {module_name}")
            
            # 获取模块
            module = self.modules.get(module_name)
            if not module:
                module = self.modules.get_fallback()
                logger.warning(f"未知模块 {module_name}，回退到 inbox")
            
            # 第二层：执行
            return await self._execute(user_id, message, module,
                                       message_type=message_type, group_id=group_id)
            
        except RuntimeError as e:
            error_msg = str(e)
            
            # 检测API配额错误 (429)
            if "429" in error_msg:
                logger.error(f"API配额不足: {e}")
                return ("⚠️ API配额不足\n\n"
                        "当前API调用已达到限额，请：\n"
                        "1. 检查API配额状态\n"
                        "2. 等待配额重置\n"
                        "3. 或更换API Key\n\n"
                        f"错误详情：{error_msg}")
            
            # 检测无效请求错误 (500, invalid_request)
            elif "500" in error_msg or "invalid_request" in error_msg:
                logger.error(f"API请求格式错误: {e}")
                return ("⚠️ API请求格式错误\n\n"
                        "可能原因：\n"
                        "1. API Key权限不足\n"
                        "2. 模型名称不匹配\n"
                        "3. 请求参数格式问题\n\n"
                        "建议检查配置文件中的模型设置。\n\n"
                        f"错误详情：{error_msg}")
            
            # 检测网络/连接错误
            elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                logger.error(f"网络连接错误: {e}")
                return ("⚠️ 网络连接失败\n\n"
                        "无法连接到AI服务，请检查：\n"
                        "1. 网络连接是否正常\n"
                        "2. API地址是否可访问\n\n"
                        f"错误详情：{error_msg}")
            
            # 其他运行时错误
            else:
                logger.error(f"处理消息出错: {e}")
                return (f"⚠️ 处理失败\n\n"
                        f"发生错误：{error_msg}\n\n"
                        "消息已保存到收集箱，待稍后处理。")
            
        except Exception as e:
            logger.error(f"处理消息出错: {e}")
            # 出错时保存到收集箱
            if self.inbox_tool:
                self.inbox_tool.execute(user_id, message=message)
                return (f"⚠️ 系统异常\n\n"
                        f"错误：{str(e)}\n\n"
                        "消息已保存到收集箱。")
            return f"处理出错: {str(e)}"
    
    async def _route(self, message: str) -> str:
        """路由：判断使用哪个模块"""
        from datetime import datetime
        
        modules_desc = self.modules.build_router_prompt() # Changed to build_router_prompt as per original logic
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = ROUTER_PROMPT.format(
            modules=modules_desc,
            today=today,
            current_time=current_time,
            message=message
        )
        
        # 使用路由模型（轻量快速）
        response = self.llm.call_with_fallback( # Changed back to self.llm as per original
            usage="router",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 提取模块名
        content = response.get("content", "inbox").strip().lower() # Kept original variable name for consistency
        
        # 验证模块名有效
        if content in self.modules.all_names():
            return content
        
        # 尝试从回复中提取有效模块名
        for name in self.modules.all_names():
            if name in content:
                return name
        
        return "inbox"
    
    async def _execute(self, user_id: str, message: str, module: ToolModule,
                       message_type: str = "private", group_id: str = None) -> str:
        """第二层：工具执行（支持多轮 Agent Loop）"""
        self._current_message_type = message_type
        self._current_group_id = group_id
        now = datetime.now()
        today = now.strftime("%Y-%m-%d %A")
        current_time = now.strftime("%Y-%m-%d %H:%M")
        
        # 从 SkillEngine 获取模块指令（动态 SOP）
        skill_instructions = self.skill_engine.get_instructions(module.name)
        if not skill_instructions:
            logger.warning(f"Skill [{module.name}] 的 SKILL.md 未找到，使用兜底指令")
            skill_instructions = FALLBACK_INSTRUCTIONS
        
        # 构建 System Prompt
        system_prompt = EXECUTOR_BASE.format(
            today=today,
            current_time=current_time,
            skill_instructions=skill_instructions
        )
        
        # 注入模块级运行时上下文
        context = self._get_context(module.name, user_id)
        if context:
            system_prompt += f"\n\n{context}"
        
        # 获取模块工具 + inbox 兜底
        tools = module.to_openai_tools()
        if module.name != "inbox" and self.inbox_tool:
            tools.append(self.inbox_tool.to_openai_tool())
        
        # ── Agent Loop（多轮工具调用）──
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        for round_num in range(MAX_AGENT_ROUNDS):
            response = self.llm.call_with_fallback(
                usage=module.name,
                messages=messages,
                tools=tools
            )
            
            # 若是纯文本回复（无工具调用），直接返回
            if not response.get("tool_calls"):
                content = response.get("content")
                if content:
                    return content
                # LLM 没有内容也没有工具调用，兜底保存
                if self.inbox_tool:
                    return self.inbox_tool.execute(user_id, message=message)
                return "收到你的消息了！"
            
            logger.info(f"Agent Loop 第 {round_num + 1} 轮，工具调用数: {len(response['tool_calls'])}")
            
            # 回填 assistant 消息（含 tool_calls）
            messages.append({
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": __import__('json').dumps(tc["arguments"], ensure_ascii=False)
                        }
                    }
                    for tc in response["tool_calls"]
                ]
            })
            
            # 执行每个工具调用并回填结果
            for tc in response["tool_calls"]:
                tool_name = tc["name"]
                arguments = dict(tc["arguments"])  # 复制一份，避免污染原始数据
                tool = self.modules.get_tool_by_name(tool_name)
                
                if tool:
                    try:
                        # 注入隐式参数（不暴露给 LLM schema）
                        if tool_name == "timeline_record":
                            arguments["_source_message"] = message
                        if tool_name in ("schedule", "todo_add"):
                            arguments["source_type"] = getattr(self, "_current_message_type", "private")
                            arguments["source_group_id"] = getattr(self, "_current_group_id", None)
                        
                        result = tool.execute(user_id, **arguments)
                        logger.info(f"工具 {tool_name} 执行成功")
                    except Exception as e:
                        logger.error(f"工具 {tool_name} 执行出错: {e}")
                        result = f"工具 {tool_name} 执行出错: {e}"
                else:
                    logger.warning(f"未找到工具: {tool_name}")
                    result = f"未找到工具: {tool_name}"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)
                })
        
        logger.warning(f"Agent Loop 达到最大轮次 ({MAX_AGENT_ROUNDS})，强制终止")
        return "⚠️ 操作步骤过多，请拆分任务重试"
    
    def _get_context(self, skill_name: str, user_id: str) -> str:
        """获取模块级运行时上下文（注入到 System Prompt 中）"""
        if skill_name == "timeline":
            recent_activities = self.db.get_activities_recent(user_id, hours=24)
            if recent_activities:
                lines = ["**最近24小时的活动记录**（用于智能补充结束时间）："]
                for act in recent_activities:
                    if act['end_time']:
                        lines.append(f"- ID{act['id']}: {act['name']} ({act['start_time']} → {act['end_time']})")
                    else:
                        lines.append(f"- ID{act['id']}: {act['name']} ({act['start_time']} → 未结束) ← 可补充")
                return "\n".join(lines)
        
        if skill_name == "todo":
            pending_tasks = self.db.get_tasks(user_id)
            if pending_tasks:
                lines = ["**当前待办任务列表**（用于完成/更新/取消操作时匹配任务）："]
                for t in pending_tasks[:10]:  # 最多注入10条
                    dl_str = ""
                    if t.get('deadline'):
                        try:
                            dl = datetime.fromisoformat(t['deadline'])
                            dl_str = f" 截止:{dl.strftime('%m/%d %H:%M')}"
                        except (ValueError, TypeError):
                            pass
                    lines.append(f"- #{t['id']}: {t['title']}{dl_str} [{t.get('priority','medium')}]")
                return "\n".join(lines)
        
        return ""
    
    
    # _handle_tool_calls 已被内联到 _execute() 的 Agent Loop 中

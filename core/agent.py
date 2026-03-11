# core/agent.py
"""Agent 核心模块 - 两层模型架构"""

from typing import Dict, Optional, List
from datetime import datetime

from .llm_manager import LLMManager
from tools import InboxTool, InboxListTool, ScheduleTool, ScheduleListTool
from tools.modules import ToolModule, ModuleRegistry
from services.database import DatabaseManager
from utils import get_logger

logger = get_logger("agent")


# === 第一层 Router Prompt ===
ROUTER_PROMPT = """你是一个意图识别助手。根据用户消息，判断应该使用哪个模块处理。

可用模块：
{modules}

重要区分：
- **schedule（日程）**：用户想要添加/查看**未来**的计划安排
  关键特征：明天、下周、几点、提醒我、安排
  
- **timeline（时间线）**：用户想要记录/查看**已完成**的活动
  关键特征：刚才、今天上午、昨天、做了、完成了、干了什么
  过去时态的描述都属于timeline
  
时间判断：
- 当前时间是 {current_time}
- 如果提到具体时间点（如18点、9点），判断该时间是过去还是未来
  * 过去的时间 → timeline
  * 未来的时间 → schedule
- "开始"、"了"等词通常表示已完成 → timeline

规则：
1. 只输出模块名称（英文），不要其他内容
2. 如果无法确定，输出 inbox
3. 当前日期是 {today}

用户消息: {message}

请输出模块名称:"""


# === 第二层 Executor Prompt ===
EXECUTOR_PROMPT = """你是 Dailylaid，一个个人日常事务管理助手。

当前模块: {module_name}
当前日期: {today}

请根据用户消息调用合适的工具。如果不确定如何处理，使用 inbox 工具保存。

回复时请简洁友好，使用中文。
"""


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
        
        # 收集箱模块（兜底）
        self.modules.register(ToolModule(
            name="inbox",
            description="收集箱：保存暂时无法分类的内容，或查看收集箱",
            tools=[InboxTool, InboxListTool],
            keywords=["记一下", "收集箱", "待处理"]
        ))
    
    async def process(self, user_id: str, message: str) -> str:
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
            return await self._execute(user_id, message, module)
            
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
    
    async def _execute(self, user_id: str, message: str, module: ToolModule) -> str:
        """第二层：工具执行（使用模块对应的模型）"""
        today = datetime.now().strftime("%Y-%m-%d %A")
        
        # 构建 executor prompt
        system_prompt = EXECUTOR_PROMPT.format(
            module_name=module.name,
            today=today
        )
        
        # 如果是timeline模块，添加最近24小时活动上下文
        if module.name == "timeline":
            recent_activities = self.db.get_activities_recent(user_id, hours=24)
            if recent_activities:
                context = "\n\n**最近24小时的活动记录**（用于智能补充结束时间）：\n"
                for act in recent_activities:
                    if act['end_time']:
                        context += f"- ID{act['id']}: {act['name']} ({act['start_time']} → {act['end_time']})\n"
                    else:
                        context += f"- ID{act['id']}: {act['name']} ({act['start_time']} → 未结束) ← 可补充\n"
                
                context += "\n提示：如果用户提到某活动结束，检查是否有对应的未结束记录，使用timeline_update工具补充end_time。\n"
                system_prompt += context
        
        # 获取模块工具 + inbox 兜底
        tools = module.to_openai_tools()
        
        # 如果不是 inbox 模块，添加 inbox 工具作为兜底
        if module.name != "inbox" and self.inbox_tool:
            tools.append(self.inbox_tool.to_openai_tool())
        
        # 使用模块对应的模型
        response = self.llm.call_with_fallback(
            usage=module.name,  # 使用模块名作为 usage
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            tools=tools
        )
        
        # 处理工具调用
        if response.get("tool_calls"):
            return await self._handle_tool_calls(user_id, message, response["tool_calls"])
        
        # 返回文本回复
        if response.get("content"):
            return response["content"]
        
        # 默认保存到收集箱
        if self.inbox_tool:
            return self.inbox_tool.execute(user_id, message=message)
        
        return "收到你的消息了！"
    
    
    async def _handle_tool_calls(self, user_id: str, message: str, tool_calls: list) -> str:
        """处理工具调用"""
        results = []
        
        for tc in tool_calls:
            tool_name = tc["name"]
            arguments = tc["arguments"]
            
            # 跨模块查找工具
            tool = self.modules.get_tool_by_name(tool_name)
            
            if tool:
                try:
                    # 如果是timeline_record，传递原始消息
                    if tool_name == "timeline_record":
                        arguments["_source_message"] = message
                    
                    result = tool.execute(user_id, **arguments)
                    results.append(result)
                    logger.info(f"工具 {tool_name} 执行成功")
                except Exception as e:
                    logger.error(f"工具 {tool_name} 执行出错: {e}")
                    results.append(f"工具 {tool_name} 执行出错: {e}")
            else:
                logger.warning(f"未找到工具: {tool_name}")
                results.append(f"未找到工具: {tool_name}")
        
        return "\n".join(results)

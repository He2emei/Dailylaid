# core/agent.py
"""Agent 核心模块 - 两层模型架构"""

from typing import Dict, Optional, List
from datetime import datetime

from .llm_client import LLMClient
from tools import InboxTool, InboxListTool, ScheduleTool, ScheduleListTool
from tools.modules import ToolModule, ModuleRegistry
from services.database import DatabaseManager
from utils import get_logger

logger = get_logger("agent")


# === 第一层 Router Prompt ===
ROUTER_PROMPT = """你是一个意图识别助手。根据用户消息，判断应该使用哪个模块处理。

可用模块：
{modules}

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
    
    第一层 (Router): 快速判断使用哪个模块
    第二层 (Executor): 在模块内调用具体工具
    """
    
    def __init__(self, llm_client: LLMClient, db: DatabaseManager):
        self.llm = llm_client
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
            
        except Exception as e:
            logger.error(f"处理消息出错: {e}")
            # 出错时保存到收集箱
            if self.inbox_tool:
                return self.inbox_tool.execute(user_id, message=message)
            return f"处理出错: {str(e)}"
    
    async def _route(self, message: str) -> str:
        """第一层：路由判断"""
        today = datetime.now().strftime("%Y-%m-%d %A")
        
        prompt = ROUTER_PROMPT.format(
            modules=self.modules.build_router_prompt(),
            today=today,
            message=message
        )
        
        # 简单的 text completion
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ])
        
        # 提取模块名
        content = response.get("content", "inbox").strip().lower()
        
        # 验证模块名有效
        if content in self.modules.all_names():
            return content
        
        # 尝试从回复中提取有效模块名
        for name in self.modules.all_names():
            if name in content:
                return name
        
        return "inbox"
    
    async def _execute(self, user_id: str, message: str, module: ToolModule) -> str:
        """第二层：工具执行"""
        today = datetime.now().strftime("%Y-%m-%d %A")
        
        # 构建 executor prompt
        system_prompt = EXECUTOR_PROMPT.format(
            module_name=module.name,
            today=today
        )
        
        # 获取模块工具 + inbox 兜底
        tools = module.to_openai_tools()
        
        # 如果不是 inbox 模块，添加 inbox 工具作为兜底
        if module.name != "inbox" and self.inbox_tool:
            tools.append(self.inbox_tool.to_openai_tool())
        
        # 调用 LLM
        response = self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            tools=tools
        )
        
        # 处理工具调用
        if response.get("tool_calls"):
            return await self._handle_tool_calls(user_id, response["tool_calls"])
        
        # 返回文本回复
        if response.get("content"):
            return response["content"]
        
        # 默认保存到收集箱
        if self.inbox_tool:
            return self.inbox_tool.execute(user_id, message=message)
        
        return "收到你的消息了！"
    
    async def _handle_tool_calls(self, user_id: str, tool_calls: list) -> str:
        """处理工具调用"""
        results = []
        
        for tc in tool_calls:
            tool_name = tc["name"]
            arguments = tc["arguments"]
            
            # 跨模块查找工具
            tool = self.modules.get_tool_by_name(tool_name)
            
            if tool:
                try:
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

# core/agent.py
"""Agent 核心模块"""

from typing import Dict, Optional
from .llm_client import LLMClient
from tools import ToolRegistry, InboxTool
from services.database import DatabaseManager
from utils import get_logger

logger = get_logger("agent")


SYSTEM_PROMPT = """你是 Dailylaid，一个个人日常事务管理助手。

你的任务是理解用户的消息，并决定如何处理：
1. 如果消息与已注册的工具相关，调用对应工具处理
2. 如果无法确定如何处理，将消息保存到收集箱 (inbox)

当前可用的功能：
- inbox: 收集箱，用于保存暂时无法处理的消息

回复时请简洁友好，使用中文。
"""


class DailylaidAgent:
    """Dailylaid Agent 核心
    
    负责协调 LLM、工具和数据库，处理用户消息。
    """
    
    def __init__(self, llm_client: LLMClient, db: DatabaseManager):
        """初始化 Agent
        
        Args:
            llm_client: LLM 客户端
            db: 数据库管理器
        """
        self.llm = llm_client
        self.db = db
        self.tools = ToolRegistry()
        
        # 注册工具
        self._register_tools()
    
    def _register_tools(self):
        """注册所有可用工具"""
        self.tools.register(InboxTool(self.db))
    
    async def process(self, user_id: str, message: str) -> str:
        """处理用户消息
        
        Args:
            user_id: 用户 QQ 号
            message: 用户消息内容
            
        Returns:
            回复内容
        """
        try:
            # 构造消息
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ]
            
            # 获取工具列表
            tools = self.tools.to_openai_tools()
            
            # 调用 LLM
            response = self.llm.chat(messages, tools=tools)
            
            # 处理工具调用
            if response.get("tool_calls"):
                return await self._handle_tool_calls(user_id, response["tool_calls"])
            
            # 返回文本回复
            if response.get("content"):
                return response["content"]
            
            # 默认保存到收集箱
            inbox_tool = self.tools.get("inbox")
            if inbox_tool:
                return inbox_tool.execute(user_id, message=message)
            
            return "收到你的消息了！"
            
        except Exception as e:
            logger.error(f"处理消息出错: {e}")
            return f"处理消息时出错: {str(e)}"
    
    async def _handle_tool_calls(self, user_id: str, tool_calls: list) -> str:
        """处理工具调用
        
        Args:
            user_id: 用户 ID
            tool_calls: 工具调用列表
            
        Returns:
            执行结果
        """
        results = []
        
        for tc in tool_calls:
            tool_name = tc["name"]
            arguments = tc["arguments"]
            
            tool = self.tools.get(tool_name)
            if tool:
                try:
                    result = tool.execute(user_id, **arguments)
                    results.append(result)
                except Exception as e:
                    results.append(f"工具 {tool_name} 执行出错: {e}")
            else:
                results.append(f"未找到工具: {tool_name}")
        
        return "\n".join(results)

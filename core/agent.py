# core/agent.py
"""Agent 核心模块"""

from typing import Dict, Optional
from .llm_client import LLMClient
from tools import ToolRegistry, InboxTool, InboxListTool, ScheduleTool, ScheduleListTool
from services.database import DatabaseManager
from utils import get_logger

logger = get_logger("agent")


SYSTEM_PROMPT = """你是 Dailylaid，一个个人日常事务管理助手。

你的任务是理解用户的消息，识别用户意图，并调用对应的工具处理：

当前可用的功能：
- schedule: 添加日程（用户提到某个时间要做某事）
- schedule_list: 查看日程（用户问有什么安排）
- inbox: 保存到收集箱（无法确定如何处理的内容）
- inbox_list: 查看收集箱（用户问收集箱有什么）

重要提示：
1. 当用户说"明天下午3点开会"这类话时，需要把时间转换为具体日期格式 YYYY-MM-DD HH:MM
2. 当前日期是 {today}
3. 回复时请简洁友好，使用中文
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
        self.tools.register(InboxListTool(self.db))
        self.tools.register(ScheduleTool(self.db))
        self.tools.register(ScheduleListTool(self.db))
    
    async def process(self, user_id: str, message: str) -> str:
        """处理用户消息
        
        Args:
            user_id: 用户 QQ 号
            message: 用户消息内容
            
        Returns:
            回复内容
        """
        from datetime import datetime
        
        try:
            # 动态生成 system prompt (插入当前日期)
            today = datetime.now().strftime("%Y-%m-%d %A")  # 如 "2026-02-07 Friday"
            system_prompt = SYSTEM_PROMPT.format(today=today)
            
            # 构造消息
            messages = [
                {"role": "system", "content": system_prompt},
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

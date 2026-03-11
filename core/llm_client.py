# core/llm_client.py
"""LLM 客户端模块"""

import json
from typing import List, Dict, Optional, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from utils import get_logger

logger = get_logger("llm")


class LLMClient:
    """LLM API 客户端
    
    支持 OpenAI 兼容的 API 接口。
    """
    
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", 
                 api_name: str = None, name: str = None):
        """初始化客户端
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
            api_name: API友好名称（如 aicanapi-key-1）
            name: 配置中的名称（如 gemini-lite）
        """
        if OpenAI is None:
            raise ImportError("请安装 openai 库: pip install openai")
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.api_name = api_name or "未命名API"
        self.name = name or model
        logger.info(f"LLM 客户端初始化: {base_url} (模型: {model})")
    
    def chat(self, messages: List[Dict], 
             tools: List[Dict] = None,
             temperature: float = 0.7) -> Dict:
        """对话接口
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            tools: 可用工具列表（OpenAI Function Calling 格式）
            temperature: 温度参数
            
        Returns:
            响应字典，包含 content 和可能的 tool_calls
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        logger.debug(f"LLM 调用: {len(messages)} 条消息, 工具数: {len(tools) if tools else 0}")
        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        
        result = {
            "content": message.content,
            "tool_calls": None
        }
        
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
                }
                for tc in message.tool_calls
            ]
        
        return result
    
    def simple_chat(self, user_message: str, system_prompt: str = None) -> str:
        """简单对话接口
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            
        Returns:
            助手回复的文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        
        result = self.chat(messages)
        return result["content"] or ""

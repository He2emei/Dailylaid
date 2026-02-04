# services/adapters/base_adapter.py
"""网络适配器基类"""

from abc import ABC, abstractmethod
from typing import Callable, Any

from utils import get_logger

logger = get_logger("adapter")


class BaseAdapter(ABC):
    """网络适配器基类
    
    所有网络连接适配器（HTTP、WebSocket等）都需要继承此类。
    提供统一的接口来发送和接收消息。
    """
    
    def __init__(self):
        self._message_callbacks = []
        self._running = False
    
    @abstractmethod
    async def start(self):
        """启动连接/服务"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止连接/服务"""
        pass
    
    @abstractmethod
    async def send_message(self, target_type: str, target_id: int, message: str) -> dict:
        """发送消息
        
        Args:
            target_type: 消息目标类型 ('group' | 'private')
            target_id: 目标ID (群号或QQ号)
            message: 消息内容
            
        Returns:
            API 响应结果
        """
        pass
    
    def on_message(self, callback: Callable[[dict], Any]):
        """注册消息回调函数
        
        当收到消息时，会调用所有注册的回调函数。
        
        Args:
            callback: 回调函数，接收消息数据字典
        """
        self._message_callbacks.append(callback)
    
    async def _dispatch_message(self, data: dict):
        """分发消息到所有回调函数"""
        for callback in self._message_callbacks:
            try:
                result = callback(data)
                # 支持异步回调
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"消息回调出错: {e}")
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

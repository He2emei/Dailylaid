# services/adapters/ws_adapter.py
"""WebSocket 正向连接适配器"""

import asyncio
import json
from typing import Optional

try:
    import websockets
except ImportError:
    websockets = None

from .base_adapter import BaseAdapter
from utils import get_logger

logger = get_logger("ws_adapter")


class WebSocketAdapter(BaseAdapter):
    """WebSocket 正向连接适配器
    
    本项目作为 WebSocket 客户端，主动连接到 NapCat 的 WebSocket 服务器。
    适用于开发环境，不需要本机有公网 IP。
    """
    
    def __init__(self, ws_url: str, token: str = None):
        """初始化适配器
        
        Args:
            ws_url: NapCat WebSocket 服务器地址 (如 ws://127.0.0.1:3001)
            token: 认证 Token (可选)
        """
        super().__init__()
        self.ws_url = ws_url
        self.token = token
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_interval = 5  # 重连间隔(秒)
        self._echo_counter = 0
        self._pending_requests = {}
    
    async def start(self):
        """启动 WebSocket 连接"""
        if websockets is None:
            raise ImportError("请安装 websockets 库: pip install websockets")
        
        self._running = True
        await self._connect()
    
    async def _connect(self):
        """建立连接"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        try:
            self.ws = await websockets.connect(
                self.ws_url, 
                additional_headers=headers if headers else None
            )
            logger.info(f"已连接到 {self.ws_url}")
            
            # 启动监听任务
            self._listen_task = asyncio.create_task(self._listen())
            
        except Exception as e:
            logger.error(f"连接失败: {e}")
            if self._running:
                logger.info(f"{self._reconnect_interval}秒后重试...")
                await asyncio.sleep(self._reconnect_interval)
                await self._connect()
    
    async def _listen(self):
        """监听消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"收到非JSON消息: {message[:100]}")
        except websockets.ConnectionClosed:
            logger.warning("连接已关闭")
            if self._running:
                logger.info(f"{self._reconnect_interval}秒后重连...")
                await asyncio.sleep(self._reconnect_interval)
                await self._connect()
        except Exception as e:
            logger.error(f"监听出错: {e}")
    
    async def _handle_message(self, data: dict):
        """处理收到的消息"""
        # 检查是否是 API 调用的响应
        echo = data.get("echo")
        if echo and echo in self._pending_requests:
            future = self._pending_requests.pop(echo)
            future.set_result(data)
            return
        
        # 检查是否是事件上报
        post_type = data.get("post_type")
        if post_type:
            # 分发给回调处理
            await self._dispatch_message(data)
    
    async def stop(self):
        """停止连接"""
        self._running = False
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
            logger.info("连接已关闭")
    
    async def send_message(self, target_type: str, target_id: int, message: str) -> dict:
        """发送消息
        
        Args:
            target_type: 'group' 或 'private'
            target_id: 群号或QQ号
            message: 消息内容
            
        Returns:
            API 响应
        """
        action = "send_group_msg" if target_type == "group" else "send_private_msg"
        id_key = "group_id" if target_type == "group" else "user_id"
        
        return await self._call_api(action, {
            id_key: target_id,
            "message": message
        })
    
    async def _call_api(self, action: str, params: dict, timeout: float = 30) -> dict:
        """调用 OneBot API
        
        Args:
            action: API 动作名称
            params: API 参数
            timeout: 超时时间(秒)
            
        Returns:
            API 响应
        """
        # websockets 16.0 使用 state 属性判断连接状态
        if not self.ws:
            raise ConnectionError("WebSocket 未连接")
        
        try:
            # 检查连接是否打开
            if self.ws.state.name != "OPEN":
                raise ConnectionError("WebSocket 连接未打开")
        except AttributeError:
            # 兼容旧版本
            if hasattr(self.ws, 'closed') and self.ws.closed:
                raise ConnectionError("WebSocket 连接已关闭")
        
        # 生成唯一 echo
        self._echo_counter += 1
        echo = f"dailylaid_{self._echo_counter}"
        
        # 构造请求
        payload = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        # 创建 Future 等待响应
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_requests[echo] = future
        
        try:
            await self.ws.send(json.dumps(payload))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_requests.pop(echo, None)
            raise TimeoutError(f"API 调用超时: {action}")

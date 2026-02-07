# config.py
"""全局配置管理"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """配置类"""
    
    # === LLM 配置 (执行层) ===
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # === 路由模型配置 (第一层) ===
    ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
    ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL", "")
    ROUTER_MODEL = os.getenv("ROUTER_MODEL", "")
    
    # === NapCat 网络配置 ===
    # 连接模式: http_client | ws_server | ws_client
    NAPCAT_MODE = os.getenv("NAPCAT_MODE", "ws_server")
    
    # HTTP 模式配置
    NAPCAT_HTTP_URL = os.getenv("NAPCAT_HTTP_URL", "http://127.0.0.1:23333")
    NAPCAT_HTTP_TOKEN = os.getenv("NAPCAT_HTTP_TOKEN", "")
    
    # WebSocket 正向模式配置 (本项目作为客户端连接 NapCat)
    NAPCAT_WS_URL = os.getenv("NAPCAT_WS_URL", "ws://127.0.0.1:3001")
    NAPCAT_WS_TOKEN = os.getenv("NAPCAT_WS_TOKEN", "")
    
    # WebSocket 反向模式配置 (本项目作为服务端等待 NapCat 连接)
    NAPCAT_WS_SERVER_HOST = os.getenv("NAPCAT_WS_SERVER_HOST", "0.0.0.0")
    NAPCAT_WS_SERVER_PORT = int(os.getenv("NAPCAT_WS_SERVER_PORT", "7779"))
    
    # === 本地服务配置 ===
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "7778"))
    
    # === 数据库配置 ===
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/dailylaid.db")
    
    # === 测试过滤配置 ===
    # 允许的用户 QQ 号（私聊）
    ALLOWED_USERS = set(
        filter(None, os.getenv("ALLOWED_USERS", "").split(","))
    )
    # 允许的群号
    ALLOWED_GROUPS = set(
        filter(None, os.getenv("ALLOWED_GROUPS", "").split(","))
    )
    
    @classmethod
    def is_allowed(cls, user_id: str, group_id: str = None) -> bool:
        """检查是否允许处理该消息"""
        # 如果没配置任何过滤，允许所有
        if not cls.ALLOWED_USERS and not cls.ALLOWED_GROUPS:
            return True
        
        # 群消息：检查群号
        if group_id:
            return str(group_id) in cls.ALLOWED_GROUPS
        
        # 私聊：检查用户
        return str(user_id) in cls.ALLOWED_USERS
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        
        if cls.NAPCAT_MODE not in ["http_client", "ws_server", "ws_client"]:
            errors.append(f"NAPCAT_MODE 无效: {cls.NAPCAT_MODE}")
        
        if errors:
            raise ValueError("配置错误:\n" + "\n".join(errors))
        
        return True

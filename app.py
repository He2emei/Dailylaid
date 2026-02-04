# app.py
"""Dailylaid 主入口"""

import asyncio
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, ".")

from config import Config
from core import LLMClient, DailylaidAgent
from services import DatabaseManager
from services.adapters import WebSocketAdapter
from utils import init_logger, get_logger


async def main():
    """主函数"""
    # 初始化日志
    init_logger(level="INFO", log_file="logs/dailylaid.log")
    logger = get_logger("app")
    
    logger.info("=" * 50)
    logger.info("  Dailylaid - 个人日常事务 AI Agent")
    logger.info("=" * 50)
    
    # 验证配置
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        logger.error("请检查 .env 文件配置")
        return
    
    # 初始化组件
    logger.info("初始化数据库...")
    db = DatabaseManager(Config.DATABASE_PATH)
    
    logger.info("初始化 LLM 客户端...")
    llm = LLMClient(
        api_key=Config.LLM_API_KEY,
        base_url=Config.LLM_BASE_URL,
        model=Config.LLM_MODEL
    )
    
    logger.info("初始化 Agent...")
    agent = DailylaidAgent(llm, db)
    
    # 根据配置选择网络适配器
    logger.info(f"初始化网络适配器 (模式: {Config.NAPCAT_MODE})...")
    
    if Config.NAPCAT_MODE == "ws_server":
        # WebSocket 正向连接模式
        adapter = WebSocketAdapter(
            ws_url=Config.NAPCAT_WS_URL,
            token=Config.NAPCAT_WS_TOKEN or None
        )
    else:
        logger.error(f"暂不支持的连接模式: {Config.NAPCAT_MODE}")
        logger.error("当前仅支持: ws_server (正向 WebSocket)")
        return
    
    # 注册消息处理回调
    async def on_message(data: dict):
        """处理收到的消息"""
        post_type = data.get("post_type")
        
        # 只处理消息事件
        if post_type != "message":
            return
        
        message_type = data.get("message_type")
        user_id = str(data.get("user_id", ""))
        raw_message = data.get("raw_message", "")
        
        if not raw_message:
            return
        
        logger.info(f"📩 收到消息 [{message_type}] 来自 {user_id}: {raw_message}")
        
        # 调用 Agent 处理
        reply = await agent.process(user_id, raw_message)
        
        if reply:
            logger.info(f"📤 回复: {reply}")
            
            # 发送回复
            if message_type == "group":
                group_id = data.get("group_id")
                await adapter.send_message("group", group_id, reply)
            else:
                await adapter.send_message("private", int(user_id), reply)
    
    adapter.on_message(on_message)
    
    # 启动适配器
    logger.info("🚀 启动连接...")
    try:
        await adapter.start()
        
        logger.info("✅ Dailylaid 已启动!")
        logger.info(f"   连接地址: {Config.NAPCAT_WS_URL}")
        logger.info("按 Ctrl+C 停止...")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️  正在停止...")
    except Exception as e:
        logger.error(f"运行出错: {e}")
    finally:
        await adapter.stop()
        logger.info("👋 已停止")


if __name__ == "__main__":
    asyncio.run(main())

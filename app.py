# app.py
"""Dailylaid 主入口"""

import asyncio
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, ".")

from config import Config
from core import LLMClient, DailylaidAgent
from services import DatabaseManager, ReminderService
from services.adapters import WebSocketAdapter
from utils import init_logger, get_logger


# 全局变量，用于提醒服务发送消息
_adapter = None


async def send_reminder_message(user_id: str, message: str):
    """提醒服务的消息发送回调"""
    if _adapter:
        await _adapter.send_message("private", int(user_id), message)


async def handle_command(user_id: str, message: str, db) -> str:
    """处理快捷命令（以 / 开头的消息）
    
    Args:
        user_id: 用户 ID
        message: 消息内容
        db: 数据库实例
        
    Returns:
        命令处理结果，如果不是有效命令返回 None
    """
    from tools import InboxTool, ScheduleListTool
    
    cmd = message.lower().strip()
    
    # /inbox - 查看收集箱
    if cmd in ["/inbox", "/收集箱"]:
        inbox_tool = InboxTool(db)
        return inbox_tool.list_items(user_id)
    
    # /today - 今日日程
    if cmd in ["/today", "/今天", "/今日"]:
        schedule_tool = ScheduleListTool(db)
        return schedule_tool.execute(user_id, range_days=1)
    
    # /week - 本周日程
    if cmd in ["/week", "/本周"]:
        schedule_tool = ScheduleListTool(db)
        return schedule_tool.execute(user_id, range_days=7)
    
    # /help - 帮助
    if cmd in ["/help", "/帮助", "/?"]:
        return """📋 可用命令：

/inbox  - 查看收集箱
/today  - 今日日程
/week   - 本周日程
/help   - 显示此帮助

也可以直接用自然语言对话，例如：
• "明天下午3点开会"
• "今天有什么安排"
"""
    
    # 未知命令，返回 None 让 Agent 处理
    return None


async def main():
    """主函数"""
    global _adapter
    
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
    
    logger.info("初始化 LLM 管理器...")
    from core import LLMManager
    llm_manager = LLMManager("llm_config.yaml")
    
    logger.info("初始化 Agent...")
    agent = DailylaidAgent(llm_manager, db)
    
    # 初始化提醒服务
    logger.info("初始化提醒服务...")
    reminder_service = ReminderService(db, send_callback=send_reminder_message)
    
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
    
    # 设置全局 adapter 引用（供提醒服务使用）
    _adapter = adapter
    
    # 注册消息处理回调
    async def on_message(data: dict):
        """处理收到的消息"""
        post_type = data.get("post_type")
        
        # 只处理消息事件
        if post_type != "message":
            return
        
        message_type = data.get("message_type")
        user_id = str(data.get("user_id", ""))
        group_id = str(data.get("group_id", "")) if data.get("group_id") else None
        raw_message = data.get("raw_message", "")
        
        if not raw_message:
            return
        
        # 检查是否允许处理
        if not Config.is_allowed(user_id, group_id):
            logger.debug(f"跳过消息 (不在允许列表): [{message_type}] {user_id}")
            return
        
        logger.info(f"📩 收到消息 [{message_type}] 来自 {user_id}: {raw_message}")
        
        # 检查是否是快捷命令（以 / 开头，绕过 LLM）
        reply = None
        if raw_message.startswith("/"):
            reply = await handle_command(user_id, raw_message, db)
        
        # 如果不是命令或命令未处理，走 Agent 流程
        if reply is None:
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
        
        # 启动提醒服务
        reminder_service.start()
        
        logger.info("✅ Dailylaid 已启动!")
        logger.info(f"   连接地址: {Config.NAPCAT_WS_URL}")
        logger.info("   提醒服务: 已启动 (每分钟检查)")
        logger.info("按 Ctrl+C 停止...")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️  正在停止...")
    except Exception as e:
        logger.error(f"运行出错: {e}")
    finally:
        reminder_service.stop()
        await adapter.stop()
        logger.info("👋 已停止")


if __name__ == "__main__":
    asyncio.run(main())

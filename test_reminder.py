# test_reminder.py
"""测试日程提醒功能"""

import asyncio
import sys
sys.path.insert(0, ".")

from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

from services.database import DatabaseManager
from services.reminder_service import ReminderService
from services.adapters import WebSocketAdapter
from config import Config


async def main():
    print("=== 日程提醒测试 ===\n")
    
    # 计算 10 分钟后的时间
    now = datetime.now()
    remind_time = now + timedelta(minutes=10)
    
    # 提前 5 分钟提醒（即 5 分钟后发送提醒）
    remind_at = now + timedelta(minutes=5)
    
    print(f"当前时间: {now.strftime('%H:%M:%S')}")
    print(f"日程时间: {remind_time.strftime('%H:%M:%S')}")
    print(f"提醒时间: {remind_at.strftime('%H:%M:%S')} (提前5分钟)")
    
    # 1. 初始化数据库
    db = DatabaseManager("data/dailylaid.db")
    
    # 2. 创建测试日程
    user_id = Config.ALLOWED_USERS.pop() if Config.ALLOWED_USERS else "1659388154"
    
    schedule_data = {
        "user_id": user_id,
        "title": "测试提醒日程",
        "start_time": remind_time.isoformat(),
        "reminders": "[5, 1]",  # 提前 5 分钟和 1 分钟提醒
        "repeat_rule": '{"type": "none"}',
        "source_message": "这是一个测试提醒"
    }
    
    schedule_id = db.insert_schedule(schedule_data)
    print(f"\n✅ 创建日程成功: ID={schedule_id}")
    print(f"   预计 {5} 分钟后收到第一次提醒")
    print(f"   预计 {9} 分钟后收到第二次提醒")
    
    # 3. 初始化 WebSocket 适配器
    print("\n正在连接 NapCat...")
    adapter = WebSocketAdapter(
        ws_url=Config.NAPCAT_WS_URL,
        token=Config.NAPCAT_WS_TOKEN
    )
    
    # 4. 定义发送消息的回调
    async def send_reminder(user_id: str, message: str):
        print(f"\n📤 发送提醒到 {user_id}:")
        print(f"   {message}")
        await adapter.send_message("private", user_id, message)
    
    # 5. 启动提醒服务
    reminder_service = ReminderService(db, send_callback=send_reminder)
    reminder_service.start()
    
    # 6. 启动适配器
    try:
        await adapter.start()
        print("\n✅ 已连接 NapCat!")
        print("等待提醒触发 (按 Ctrl+C 停止)...\n")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n停止测试...")
    finally:
        reminder_service.stop()
        await adapter.stop()
        
        # 清理测试数据
        db.delete_schedule(schedule_id)
        print("✅ 测试日程已删除")


if __name__ == "__main__":
    asyncio.run(main())

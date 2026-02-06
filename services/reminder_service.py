# services/reminder_service.py
"""提醒服务 - 基于 APScheduler"""

import json
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import sys
sys.path.insert(0, ".")

from services.database import DatabaseManager
from utils import get_logger

logger = get_logger("reminder")


class ReminderService:
    """提醒服务
    
    使用 APScheduler 定时检查并发送日程提醒。
    """
    
    def __init__(self, db: DatabaseManager, send_callback=None):
        """初始化提醒服务
        
        Args:
            db: 数据库管理器
            send_callback: 发送消息的回调函数 async def(user_id, message)
        """
        self.db = db
        self.send_callback = send_callback
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """启动提醒服务"""
        # 每分钟检查一次
        self.scheduler.add_job(
            self._check_reminders,
            'interval',
            minutes=1,
            id='check_reminders',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("提醒服务已启动 (每分钟检查)")
    
    def stop(self):
        """停止提醒服务"""
        self.scheduler.shutdown()
        logger.info("提醒服务已停止")
    
    async def _check_reminders(self):
        """检查并发送提醒"""
        now = datetime.now()
        logger.debug(f"检查提醒... {now}")
        
        # 获取未来 24 小时内的日程
        schedules = self.db.get_upcoming_schedules(hours=24)
        
        for schedule in schedules:
            await self._process_schedule_reminders(schedule, now)
    
    async def _process_schedule_reminders(self, schedule: dict, now: datetime):
        """处理单个日程的提醒"""
        schedule_id = schedule["id"]
        user_id = schedule["user_id"]
        title = schedule["title"]
        start_time = datetime.fromisoformat(schedule["start_time"])
        
        # 解析提醒列表
        try:
            reminders = json.loads(schedule.get("reminders", "[]"))
        except json.JSONDecodeError:
            reminders = []
        
        if not reminders:
            return
        
        for remind_minutes in reminders:
            remind_time = start_time - timedelta(minutes=remind_minutes)
            remind_time_str = remind_time.isoformat()
            
            # 检查是否在当前这一分钟内需要提醒
            if now <= remind_time < now + timedelta(minutes=1):
                # 检查是否已发送
                if self.db.is_reminder_sent(schedule_id, remind_time_str):
                    logger.debug(f"提醒已发送过: {schedule_id} @ {remind_time_str}")
                    continue
                
                # 发送提醒
                await self._send_reminder(
                    user_id=user_id,
                    schedule_id=schedule_id,
                    title=title,
                    start_time=start_time,
                    remind_minutes=remind_minutes
                )
                
                # 记录已发送
                self.db.log_reminder(schedule_id, remind_time_str)
    
    async def _send_reminder(self, user_id: str, schedule_id: int, 
                              title: str, start_time: datetime, remind_minutes: int):
        """发送提醒消息"""
        # 格式化时间
        time_str = start_time.strftime("%H:%M")
        date_str = start_time.strftime("%m月%d日")
        
        # 构建消息
        if remind_minutes >= 60:
            time_desc = f"{remind_minutes // 60}小时后"
        else:
            time_desc = f"{remind_minutes}分钟后"
        
        message = f"⏰ 日程提醒\n\n{title}\n时间: {date_str} {time_str}\n({time_desc}开始)"
        
        logger.info(f"发送提醒: [{user_id}] {title}")
        
        # 调用回调发送
        if self.send_callback:
            try:
                await self.send_callback(user_id, message)
            except Exception as e:
                logger.error(f"发送提醒失败: {e}")
        else:
            logger.warning("未设置消息发送回调")

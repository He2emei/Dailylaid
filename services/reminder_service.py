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
    
    使用 APScheduler 定时检查并发送日程提醒和待办催促。
    """
    
    # === Task 提醒常量（Phase 7 迁移到 YAML 配置） ===
    TASK_PRE_REMIND_MINUTES = 30        # scheduled_time 前 30 分钟预提醒
    TASK_DEADLINE_WARN_MINUTES = 60     # deadline 前 1 小时预警
    OVERDUE_INTERVALS_HOURS = [2, 4, 8, 24]  # 逾期退避间隔（小时）
    MAX_DAILY_REMINDERS = 3             # 每天最多催促次数
    MAX_OVERDUE_DAYS = 7                # 最大逾期催促天数
    
    def __init__(self, db: DatabaseManager, send_callback=None):
        """初始化提醒服务
        
        Args:
            db: 数据库管理器
            send_callback: 发送消息的回调函数
                           async def(user_id, message, message_type, group_id) -> str|None
                           返回 message_id 或 None
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
        logger.info("提醒服务已启动 (每分钟检查 schedules + tasks)")
    
    def stop(self):
        """停止提醒服务"""
        self.scheduler.shutdown()
        logger.info("提醒服务已停止")
    
    async def _check_reminders(self):
        """检查并发送提醒（schedules + tasks）"""
        now = datetime.now()
        logger.debug(f"检查提醒... {now}")
        
        # 1. 检查日程提醒（原有逻辑）
        schedules = self.db.get_upcoming_schedules(hours=24)
        for schedule in schedules:
            await self._process_schedule_reminders(schedule, now)
        
        # 2. 检查待办任务提醒（Phase 3 新增）
        upcoming_tasks = self.db.get_upcoming_tasks(hours=24)
        for task in upcoming_tasks:
            await self._process_task_reminders(task, now)
        
        # 3. 检查逾期任务催促（Phase 3 新增）
        overdue_tasks = self.db.get_overdue_tasks()
        for task in overdue_tasks:
            await self._process_overdue_task(task, now)
    
    # =========================================================
    #  Schedule 提醒（原有逻辑，保持不变）
    # =========================================================
    
    async def _process_schedule_reminders(self, schedule: dict, now: datetime):
        """处理单个日程的提醒"""
        schedule_id = schedule["id"]
        user_id = schedule["user_id"]
        title = schedule["title"]
        start_time = datetime.fromisoformat(schedule["start_time"])
        source_type = schedule.get("source_type", "private")
        source_group_id = schedule.get("source_group_id")
        
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
                await self._send_schedule_reminder(
                    user_id=user_id,
                    schedule_id=schedule_id,
                    title=title,
                    start_time=start_time,
                    remind_minutes=remind_minutes,
                    source_type=source_type,
                    source_group_id=source_group_id
                )
                
                # 记录已发送
                self.db.log_reminder(schedule_id, remind_time_str)
    
    async def _send_schedule_reminder(self, user_id: str, schedule_id: int, 
                              title: str, start_time: datetime, remind_minutes: int,
                              source_type: str = "private", source_group_id: str = None):
        """发送日程提醒消息（原逻辑，仅重命名）"""
        # 格式化时间
        time_str = start_time.strftime("%H:%M")
        date_str = start_time.strftime("%m月%d日")
        
        # 构建消息文案
        if remind_minutes == 0:
            message = f"⏰ 该{title}了！（{date_str} {time_str}）"
        elif remind_minutes >= 60:
            time_desc = f"{remind_minutes // 60}小时后"
            message = f"⏰ 日程提醒\n\n{title}\n时间: {date_str} {time_str}\n({time_desc}开始)"
        else:
            time_desc = f"{remind_minutes}分钟后"
            message = f"⏰ 日程提醒\n\n{title}\n时间: {date_str} {time_str}\n({time_desc}开始)"
        
        # 群聊时在消息前加 AT
        if source_type == "group" and source_group_id:
            message = f"[CQ:at,qq={user_id}] {message}"
        
        logger.info(f"发送日程提醒 [{source_type}]: [{user_id}] {title}")
        
        if self.send_callback:
            try:
                await self.send_callback(
                    user_id=user_id,
                    message=message,
                    message_type=source_type,
                    group_id=source_group_id
                )
            except Exception as e:
                logger.error(f"发送日程提醒失败: {e}")
        else:
            logger.warning("未设置消息发送回调")
    
    # =========================================================
    #  Task 提醒（Phase 3 新增）
    # =========================================================
    
    async def _process_task_reminders(self, task: dict, now: datetime):
        """处理单个待办任务的提醒（预提醒 / 到时 / deadline 预警）"""
        task_id = task["id"]
        title = task["title"]
        
        # 1. scheduled_time 相关提醒
        if task.get("scheduled_time"):
            try:
                scheduled_time = datetime.fromisoformat(task["scheduled_time"])
            except (ValueError, TypeError):
                scheduled_time = None
            
            if scheduled_time:
                # 预提醒: scheduled_time - 30min
                pre_remind_time = scheduled_time - timedelta(minutes=self.TASK_PRE_REMIND_MINUTES)
                if now <= pre_remind_time < now + timedelta(minutes=1):
                    remind_time_str = pre_remind_time.isoformat()
                    if not self.db.log_task_reminder(task_id, "pre_scheduled", remind_time_str):
                        logger.debug(f"预提醒已发送过: 任务 #{task_id}")
                    else:
                        await self._send_task_reminder(task, "pre_scheduled",
                            f"📋 待办提醒\n\n#{task_id} {title}\n⏰ {self.TASK_PRE_REMIND_MINUTES}分钟后开始")
                
                # 到时提醒: scheduled_time 到达
                if now <= scheduled_time < now + timedelta(minutes=1):
                    remind_time_str = scheduled_time.isoformat()
                    if not self.db.log_task_reminder(task_id, "scheduled", remind_time_str):
                        logger.debug(f"到时提醒已发送过: 任务 #{task_id}")
                    else:
                        await self._send_task_reminder(task, "scheduled",
                            f"⏰ 现在该做了！\n\n#{task_id} {title}")
        
        # 2. deadline 预警
        if task.get("deadline"):
            try:
                deadline = datetime.fromisoformat(task["deadline"])
            except (ValueError, TypeError):
                deadline = None
            
            if deadline:
                warn_time = deadline - timedelta(minutes=self.TASK_DEADLINE_WARN_MINUTES)
                if now <= warn_time < now + timedelta(minutes=1):
                    remind_time_str = warn_time.isoformat()
                    if not self.db.log_task_reminder(task_id, "deadline_warn", remind_time_str):
                        logger.debug(f"Deadline 预警已发送过: 任务 #{task_id}")
                    else:
                        deadline_str = deadline.strftime("%m月%d日 %H:%M")
                        await self._send_task_reminder(task, "deadline_warn",
                            f"⚠️ 截止时间快到了！\n\n#{task_id} {title}\n⏰ 截止: {deadline_str}（还剩1小时）")
    
    async def _process_overdue_task(self, task: dict, now: datetime):
        """处理逾期任务的催促（指数退避）"""
        task_id = task["id"]
        title = task["title"]
        
        try:
            deadline = datetime.fromisoformat(task["deadline"])
        except (ValueError, TypeError):
            return
        
        # 计算逾期时长
        overdue_duration = now - deadline
        overdue_hours = overdue_duration.total_seconds() / 3600
        overdue_days = overdue_duration.days
        
        # 超过 MAX_OVERDUE_DAYS 天不再催促
        if overdue_days >= self.MAX_OVERDUE_DAYS:
            return
        
        # 检查今日催促次数
        today_count = self.db.get_task_reminder_count_today(task_id)
        if today_count >= self.MAX_DAILY_REMINDERS:
            return
        
        # 确定当前退避间隔：2h → 4h → 8h → 24h
        # 根据已经过去了多少小时来确定应该用哪个间隔
        current_interval_hours = self.OVERDUE_INTERVALS_HOURS[-1]  # 默认最大间隔
        for interval in self.OVERDUE_INTERVALS_HOURS:
            if overdue_hours < interval * 3:  # 阶段跃迁：逾期时间 < 3倍间隔时使用该间隔
                current_interval_hours = interval
                break
        
        # 检查距上次催促的间隔
        last_reminder = self.db.get_last_task_reminder(task_id, "overdue")
        if last_reminder:
            # 使用 remind_time 判断上次催促时间（比 sent_at 更可靠）
            last_time_str = last_reminder.get("remind_time", "")
            last_sent = None
            try:
                last_sent = datetime.fromisoformat(last_time_str)
            except (ValueError, TypeError):
                try:
                    last_sent = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass
            
            if last_sent:
                elapsed = (now - last_sent).total_seconds() / 3600
                if elapsed < current_interval_hours:
                    # 还没到下一个催促时间
                    return
        
        # 发送逾期催促
        remind_time_str = now.isoformat()
        if not self.db.log_task_reminder(task_id, "overdue", remind_time_str):
            return  # 已记录（极端情况下同一秒重复）
        
        # 构建催促文案
        if overdue_hours < 1:
            overdue_desc = "刚刚逾期"
        elif overdue_hours < 24:
            overdue_desc = f"已逾期 {int(overdue_hours)} 小时"
        else:
            overdue_desc = f"已逾期 {overdue_days} 天"
        
        deadline_str = deadline.strftime("%m月%d日 %H:%M")
        message = (
            f"🔴 待办逾期提醒！\n\n"
            f"#{task_id} {title}\n"
            f"📅 截止: {deadline_str}\n"
            f"⏳ {overdue_desc}"
        )
        
        await self._send_task_reminder(task, "overdue", message)
        logger.info(f"逾期催促: 任务 #{task_id}「{title}」{overdue_desc}（今日第{today_count + 1}次）")
    
    async def _send_task_reminder(self, task: dict, remind_type: str, message: str):
        """发送待办提醒消息并绑定 message_id
        
        Args:
            task: 任务 dict
            remind_type: 提醒类型 (pre_scheduled / scheduled / deadline_warn / overdue)
            message: 消息内容
        """
        task_id = task["id"]
        user_id = task["user_id"]
        source_type = task.get("source_type", "private")
        source_group_id = task.get("source_group_id")
        
        # 添加操作提示
        message += "\n\n💡 回复本消息：完成✅ / 推迟⏳ / 取消❌"
        
        # 群聊时加 AT
        if source_type == "group" and source_group_id:
            message = f"[CQ:at,qq={user_id}] {message}"
        
        logger.info(f"发送任务{remind_type}提醒 [{source_type}]: [{user_id}] #{task_id}")
        
        if self.send_callback:
            try:
                msg_id = await self.send_callback(
                    user_id=user_id,
                    message=message,
                    message_type=source_type,
                    group_id=source_group_id
                )
                # 将催促消息的 message_id 绑定到任务，以便用户回复
                if msg_id:
                    self.db.append_bound_message(task_id, str(msg_id))
                    logger.debug(f"🔗 催促消息 message_id={msg_id} → 任务 #{task_id}")
            except Exception as e:
                logger.error(f"发送任务提醒失败: {e}")
        else:
            logger.warning("未设置消息发送回调")

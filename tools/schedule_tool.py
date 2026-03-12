# tools/schedule_tool.py
"""日程工具"""

import json
from datetime import datetime
from typing import Dict

from .base_tool import BaseTool
from utils import get_logger

logger = get_logger("schedule_tool")


class ScheduleTool(BaseTool):
    """日程工具 - 添加和管理日程"""
    
    name = "schedule"
    description = """添加日程。当用户提到要在某个时间做某事时使用此工具。
    例如：
    - "明天下午3点开会"
    - "周五10点去医院"
    - "提醒我8点吃药"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "日程标题/内容"
            },
            "start_time": {
                "type": "string", 
                "description": "开始时间，格式: YYYY-MM-DD HH:MM"
            },
            "location": {
                "type": "string",
                "description": "地点（可选）"
            },
            "reminders": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "提前提醒时间列表，单位分钟。规则：[0] 表示到时间点立刻提醒（适用于'3分钟后喝水'、'半小时后吃药'等短时间提醒）；[30] 表示提前30分钟提醒（适用于会议、约会等正式安排）；[60, 30] 表示提前60分钟和30分钟各提醒一次。请根据提醒距现在的时长智能选择。"
            }
        },
        "required": ["title", "start_time"]
    }
    
    def execute(self, user_id: str, **params) -> str:
        """添加日程"""
        title = params.get("title")
        start_time = params.get("start_time")
        location = params.get("location")
        reminders = params.get("reminders")
        source_type = params.get("source_type", "private")
        source_group_id = params.get("source_group_id")
        
        if not title or not start_time:
            return "需要提供日程标题和时间"
        
        # 解析时间
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        except ValueError:
            return f"时间格式错误: {start_time}，请使用 YYYY-MM-DD HH:MM 格式"
        
        # 智能推断默认提醒时间：距现在超过60分钟 → 提前30分钟；否则 → 到时立刻提醒
        if reminders is None:
            minutes_until = (start_dt - datetime.now()).total_seconds() / 60
            reminders = [30] if minutes_until > 60 else [0]
        
        # 保存到数据库
        schedule_data = {
            "user_id": user_id,
            "title": title,
            "start_time": start_dt.isoformat(),
            "location": location,
            "reminders": json.dumps(reminders),
            "repeat_rule": '{"type": "none"}',
            "source_type": source_type,
            "source_group_id": source_group_id,
        }
        
        schedule_id = self.db.insert_schedule(schedule_data)
        
        # 格式化时间显示
        time_str = start_dt.strftime("%m月%d日 %H:%M")
        
        # 构造回复
        reply = f"✅ 已添加日程\n\n📅 {title}\n⏰ {time_str}"
        if location:
            reply += f"\n📍 {location}"
        if reminders == [0]:
            reply += "\n🔔 到时立刻提醒"
        elif reminders:
            reply += f"\n🔔 提前 {reminders[0]} 分钟提醒"
        
        logger.info(f"添加日程: [{user_id}] {title} @ {time_str}")
        return reply



class ScheduleListTool(BaseTool):
    """日程查询工具 - 查看日程"""
    
    name = "schedule_list"
    description = """查看日程。当用户问今天/明天/本周有什么安排时使用。
    例如：
    - "今天有什么安排"
    - "我的日程"
    - "这周有什么事"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "range_days": {
                "type": "integer",
                "description": "查询天数范围，默认7天"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, **params) -> str:
        """查询日程"""
        range_days = params.get("range_days", 7)
        
        from datetime import timedelta
        today = datetime.now().date()
        end_date = today + timedelta(days=range_days)
        
        schedules = self.db.get_schedules(user_id, today, end_date)
        
        if not schedules:
            return f"📅 未来 {range_days} 天没有日程安排"
        
        result = f"📅 未来 {range_days} 天的日程：\n"
        for s in schedules:
            start_time = datetime.fromisoformat(s["start_time"])
            time_str = start_time.strftime("%m/%d %H:%M")
            result += f"\n• {time_str} {s['title']}"
            if s.get("location"):
                result += f" @ {s['location']}"
        
        return result

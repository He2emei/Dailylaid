# mcp_server/tools/schedule_tool.py
"""日程工具 - MCP 实现"""

import json
from datetime import datetime, timedelta
from typing import Optional
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY

import sys
sys.path.insert(0, ".")

from services.database import DatabaseManager


# 数据库实例（延迟初始化）
_db: DatabaseManager = None


def get_db() -> DatabaseManager:
    """获取数据库实例"""
    global _db
    if _db is None:
        _db = DatabaseManager("data/dailylaid.db")
    return _db


def register_schedule_tools(mcp):
    """注册日程相关的 MCP 工具"""
    
    @mcp.tool()
    def schedule_add(
        user_id: str,
        title: str,
        start_time: str,
        end_time: str = None,
        location: str = None,
        description: str = None,
        reminders: list[int] = None,
        repeat_rule: dict = None,
        source_message: str = None
    ) -> dict:
        """添加日程
        
        Args:
            user_id: 用户 ID
            title: 日程标题
            start_time: 开始时间 (格式: YYYY-MM-DD HH:MM)
            end_time: 结束时间 (可选)
            location: 地点 (可选)
            description: 详细描述 (可选)
            reminders: 提醒时间列表，单位分钟 (如 [60, 30, 10])
            repeat_rule: 重复规则 (如 {"type": "weekly", "weekdays": [0, 2, 4]})
            source_message: 创建日程的原始消息
        
        Returns:
            创建结果，包含日程 ID
        """
        db = get_db()
        
        # 解析时间
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        except ValueError:
            return {"success": False, "error": "时间格式错误，请使用 YYYY-MM-DD HH:MM"}
        
        end_dt = None
        if end_time:
            try:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        # 准备数据
        schedule_data = {
            "user_id": user_id,
            "title": title,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat() if end_dt else None,
            "location": location,
            "description": description,
            "reminders": json.dumps(reminders or []),
            "repeat_rule": json.dumps(repeat_rule or {"type": "none"}),
            "source_message": source_message
        }
        
        schedule_id = db.insert_schedule(schedule_data)
        
        return {
            "success": True,
            "id": schedule_id,
            "message": f"已添加日程: {title} ({start_time})"
        }
    
    @mcp.tool()
    def schedule_list(
        user_id: str,
        date: str = None,
        range_days: int = 7,
        include_recurring: bool = True
    ) -> list:
        """列出日程
        
        Args:
            user_id: 用户 ID
            date: 指定日期 (YYYY-MM-DD)，默认今天
            range_days: 查询天数范围
            include_recurring: 是否包含重复日程的实例
        
        Returns:
            日程列表
        """
        db = get_db()
        
        if date:
            try:
                start_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                start_date = datetime.now().date()
        else:
            start_date = datetime.now().date()
        
        end_date = start_date + timedelta(days=range_days)
        
        schedules = db.get_schedules(user_id, start_date, end_date)
        
        result = []
        for s in schedules:
            # 解析重复规则，计算实际日期
            repeat_rule = json.loads(s.get("repeat_rule", '{"type": "none"}'))
            
            if include_recurring and repeat_rule.get("type") != "none":
                occurrences = get_occurrences(s, start_date, end_date)
                for occ in occurrences:
                    result.append({
                        "id": s["id"],
                        "title": s["title"],
                        "start_time": occ.isoformat(),
                        "location": s.get("location"),
                        "is_recurring": True
                    })
            else:
                result.append({
                    "id": s["id"],
                    "title": s["title"],
                    "start_time": s["start_time"],
                    "end_time": s.get("end_time"),
                    "location": s.get("location"),
                    "is_recurring": repeat_rule.get("type") != "none"
                })
        
        return result
    
    @mcp.tool()
    def schedule_today(user_id: str) -> list:
        """获取今日日程
        
        Args:
            user_id: 用户 ID
        
        Returns:
            今日日程列表
        """
        return schedule_list(user_id, range_days=1)
    
    @mcp.tool()
    def schedule_update(
        schedule_id: int,
        title: str = None,
        start_time: str = None,
        end_time: str = None,
        location: str = None,
        description: str = None,
        reminders: list[int] = None,
        repeat_rule: dict = None
    ) -> dict:
        """更新日程
        
        Args:
            schedule_id: 日程 ID
            其他参数: 要更新的字段
        
        Returns:
            更新结果
        """
        db = get_db()
        
        updates = {}
        if title is not None:
            updates["title"] = title
        if start_time is not None:
            try:
                dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
                updates["start_time"] = dt.isoformat()
            except ValueError:
                return {"success": False, "error": "时间格式错误"}
        if end_time is not None:
            try:
                dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
                updates["end_time"] = dt.isoformat()
            except ValueError:
                pass
        if location is not None:
            updates["location"] = location
        if description is not None:
            updates["description"] = description
        if reminders is not None:
            updates["reminders"] = json.dumps(reminders)
        if repeat_rule is not None:
            updates["repeat_rule"] = json.dumps(repeat_rule)
        
        if not updates:
            return {"success": False, "error": "没有要更新的内容"}
        
        db.update_schedule(schedule_id, updates)
        return {"success": True, "message": f"已更新日程 #{schedule_id}"}
    
    @mcp.tool()
    def schedule_delete(schedule_id: int) -> dict:
        """删除日程
        
        Args:
            schedule_id: 日程 ID
        
        Returns:
            删除结果
        """
        db = get_db()
        db.delete_schedule(schedule_id)
        return {"success": True, "message": f"已删除日程 #{schedule_id}"}


def get_occurrences(schedule: dict, start_date, end_date) -> list:
    """根据重复规则计算时间范围内的所有日程实例"""
    rule = json.loads(schedule.get("repeat_rule", '{"type": "none"}'))
    
    if rule.get("type") == "none":
        base_time = datetime.fromisoformat(schedule["start_time"])
        if start_date <= base_time.date() <= end_date:
            return [base_time]
        return []
    
    freq_map = {
        "daily": DAILY,
        "weekly": WEEKLY,
        "monthly": MONTHLY,
        "yearly": YEARLY
    }
    
    base_time = datetime.fromisoformat(schedule["start_time"])
    
    try:
        rr = rrule(
            freq=freq_map.get(rule["type"], DAILY),
            dtstart=base_time,
            interval=rule.get("interval", 1),
            byweekday=rule.get("weekdays"),
            bymonthday=rule.get("monthday"),
            until=datetime.strptime(rule["until"], "%Y-%m-%d") if rule.get("until") else None,
            count=rule.get("count")
        )
        
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        return list(rr.between(start_dt, end_dt, inc=True))
    except Exception:
        return [base_time]

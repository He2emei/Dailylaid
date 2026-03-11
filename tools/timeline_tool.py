# tools/timeline_tool.py
"""时间线活动记录工具"""

import json
from datetime import datetime, timedelta
from typing import Dict, List

from .base_tool import BaseTool
from utils import get_logger

logger = get_logger("timeline_tool")


class TimelineRecordTool(BaseTool):
    """时间线记录工具 - 记录已完成的活动"""
    
    name = "timeline_record"
    description = """记录已完成的活动。当用户提到自己刚才做了什么、完成了什么时使用。
    例如：
    - "我刚才9点到11点写代码了"
    - "我7点起床了"
    - "记录一下，10点到10点半吃早饭"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "活动名称，如'写代码'、'开会'、'吃饭'、'起床'"
            },
            "start_time": {
                "type": "string", 
                "description": "开始时间，格式: YYYY-MM-DD HH:MM"
            },
            "end_time": {
                "type": "string",
                "description": "结束时间，格式: YYYY-MM-DD HH:MM（可选，如果是时刻事件如'起床'可不提供）"
            },
            "description": {
                "type": "string",
                "description": "活动详细描述（可选）"
            },
            "category": {
                "type": "string",
                "description": "分类：工作/学习/娱乐/生活/其他（可选）"
            },
            "location": {
                "type": "string",
                "description": "地点（可选）"
            }
        },
        "required": ["name", "start_time"]
    }
    
    def execute(self, user_id: str, **params) -> str:
        """记录活动
        
        Args:
            user_id: 用户 ID
            name: 活动名称
            start_time: 开始时间
            end_time: 结束时间（可选）
            description: 描述
            category: 分类
            location: 地点
        """
        name = params.get("name")
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        description = params.get("description")
        category = params.get("category")
        location = params.get("location")
        
        if not name or not start_time:
            return "需要提供活动名称和开始时间"
        
        # 解析时间
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            end_dt = None
            if end_time:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
                
                # 检查时间合理性
                if end_dt <= start_dt:
                    return "结束时间必须晚于开始时间"
        except ValueError as e:
            return f"时间格式错误: {e}，请使用 YYYY-MM-DD HH:MM 格式"
        
        # 检测时间重叠
        overlaps = self.db.check_activity_overlap(user_id, start_time, end_time)
        overlap_warning = ""
        if overlaps:
            overlap_warning = "\n\n⚠️ 时间重叠提醒：\n"
            for o in overlaps:
                end_str = o['end_time'] if o['end_time'] else "未结束"
                overlap_warning += f"  • {o['name']} ({o['start_time']} - {end_str})\n"
        
        # 保存到数据库
        activity_data = {
            "user_id": user_id,
            "name": name,
            "description": description,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat() if end_dt else None,
            "category": category,
            "location": location,
            "related_messages": json.dumps([params.get("_source_message", "")])
        }
        
        activity_id = self.db.insert_activity(activity_data)
        
        # 格式化时间显示
        start_str = start_dt.strftime("%m月%d日 %H:%M")
        
        # 构造回复
        if end_time:
            end_str = end_dt.strftime("%H:%M")
            duration = end_dt - start_dt
            hours = duration.seconds // 3600
            mins = (duration.seconds % 3600) // 60
            duration_str = f"{hours}h{mins}m" if hours > 0 else f"{mins}m"
            
            reply = f"✅ 已记录活动\n\n📝 {name}\n⏰ {start_str} → {end_str} ({duration_str})"
        else:
            reply = f"✅ 已记录活动\n\n📝 {name}\n⏰ {start_str}"
        
        if location:
            reply += f"\n📍 {location}"
        if category:
            reply += f"\n🏷️ {category}"
        
        reply += overlap_warning
        
        logger.info(f"记录活动: [{user_id}] {name} @ {start_str}")
        return reply


class TimelineUpdateTool(BaseTool):
    """时间线更新工具 - 更新已有活动（主要用于补充结束时间）"""
    
    name = "timeline_update"
    description = """更新已有活动记录。主要用于补充结束时间。
    当用户提到某个活动结束时，如果最近有该活动的未结束记录，应使用此工具补充end_time。
    例如：
    - 历史有"18:00 开始吃饭（未结束）"，用户说"吃完饭了" → 补充end_time
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "activity_id": {
                "type": "integer",
                "description": "要更新的活动ID"
            },
            "end_time": {
                "type": "string",
                "description": "补充的结束时间，格式: YYYY-MM-DD HH:MM"
            },
            "description": {
                "type": "string",
                "description": "更新描述（可选）"
            },
            "add_message": {
                "type": "string",
                "description": "追加相关消息（可选）"
            }
        },
        "required": ["activity_id"]
    }
    
    def execute(self, user_id: str, **params) -> str:
        """更新活动"""
        activity_id = params.get("activity_id")
        end_time = params.get("end_time")
        description = params.get("description")
        add_message = params.get("add_message")
        
        # 获取原活动
        activity = self.db.get_activity_by_id(activity_id)
        if not activity:
            return f"未找到ID为 {activity_id} 的活动"
        
        # 验证权限
        if activity['user_id'] != user_id:
            return "无权修改此活动"
        
        updates = {}
        
        # 补充结束时间
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace(" ", "T"))
                start_dt = datetime.fromisoformat(activity['start_time'])
                
                if end_dt <= start_dt:
                    return "结束时间必须晚于开始时间"
                
                updates['end_time'] = end_dt.isoformat()
            except ValueError as e:
                return f"时间格式错误: {e}"
        
        # 更新描述
        if description:
            updates['description'] = description
        
        # 追加消息
        if add_message:
            messages = json.loads(activity.get('related_messages', '[]'))
            messages.append(add_message)
            updates['related_messages'] = json.dumps(messages)
        
        if not updates:
            return "没有需要更新的内容"
        
        # 执行更新
        self.db.update_activity(activity_id, updates)
        
        reply = f"✅ 已更新活动: {activity['name']}"
        if end_time:
            end_str = end_dt.strftime("%H:%M")
            start_str = start_dt.strftime("%H:%M")
            duration = end_dt - start_dt
            hours = duration.seconds // 3600
            mins = (duration.seconds % 3600) // 60
            duration_str = f"{hours}h{mins}m" if hours > 0 else f"{mins}m"
            reply += f"\n⏰ {start_str} → {end_str} ({duration_str})"
        
        logger.info(f"更新活动: [{user_id}] ID={activity_id}")
        return reply


class TimelineListTool(BaseTool):
    """时间线列表工具 - 查看活动记录（文本列表）"""
    
    name = "timeline_list"
    description = """查看活动记录列表。
    例如：
    - "我今天都干了啥"
    - "看看我最近的活动"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "hours": {
                "type": "integer",
                "description": "查询最近N小时，默认24"
            },
            "date": {
                "type": "string",
                "description": "查询特定日期，格式: YYYY-MM-DD"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, **params) -> str:
        """查询活动列表"""
        hours = params.get("hours", 24)
        date_str = params.get("date")
        
        if date_str:
            # 查询特定日期
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                activities = self.db.get_activities(user_id, target_date, target_date)
                title = f"📅 {target_date.strftime('%Y年%m月%d日')} 的活动"
            except ValueError:
                return "日期格式错误，请使用 YYYY-MM-DD"
        else:
            # 查询最近N小时
            activities = self.db.get_activities_recent(user_id, hours)
            title = f"📅 最近 {hours} 小时的活动"
        
        if not activities:
            return f"{title}：\n\n暂无记录"
        
        result = f"{title}：\n"
        for act in activities:
            start_dt = datetime.fromisoformat(act['start_time'])
            start_str = start_dt.strftime("%H:%M")
            
            if act['end_time']:
                end_dt = datetime.fromisoformat(act['end_time'])
                end_str = end_dt.strftime("%H:%M")
                duration = end_dt - start_dt
                hours_d = duration.seconds // 3600
                mins_d = (duration.seconds % 3600) // 60
                duration_str = f"{hours_d}h{mins_d}m" if hours_d > 0 else f"{mins_d}m"
                result += f"\n• {start_str}-{end_str} {act['name']} ({duration_str})"
            else:
                result += f"\n• {start_str} {act['name']}"
            
            if act.get('location'):
                result += f" @ {act['location']}"
        
        return result


class TimelineViewTool(BaseTool):
    """时间线可视化工具 - 生成时间线图片"""
    
    name = "timeline_view"
    description = """生成可视化时间线图片。
    例如：
    - "生成今天的时间线"
    - "看看我今天的时间线图"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "日期，格式: YYYY-MM-DD，默认今天"
            },
            "style": {
                "type": "string",
                "description": "风格：glass(毛玻璃)/neon(霓虹)/skeletal(极简)，默认glass"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, **params) -> str:
        """生成时间线图片"""
        date_str = params.get("date")
        style = params.get("style", "glass")
        
        # 解析日期
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return "日期格式错误，请使用 YYYY-MM-DD"
        else:
            target_date = datetime.now().date()
        
        # 查询活动
        activities = self.db.get_activities(user_id, target_date, target_date)
        
        if not activities:
            return f"📅 {target_date.strftime('%Y年%m月%d日')} 暂无活动记录"
        
        # TODO: 生成SVG并转PNG
        # 当前返回文本提示
        result = f"📊 时间线可视化（{style}风格）\n\n"
        result += f"日期: {target_date.strftime('%Y-%m-%d')}\n"
        result += f"活动数: {len(activities)}\n\n"
        result += "⚠️ 图片生成功能开发中...\n"
        result += "当前返回文本列表：\n"
        
        for act in activities:
            start_dt = datetime.fromisoformat(act['start_time'])
            start_str = start_dt.strftime("%H:%M")
            
            if act['end_time']:
                end_dt = datetime.fromisoformat(act['end_time'])
                end_str = end_dt.strftime("%H:%M")
                result += f"\n• {start_str}-{end_str} {act['name']}"
            else:
                result += f"\n• {start_str} {act['name']}"
        
        logger.info(f"生成时间线视图: [{user_id}] {target_date}")
        return result

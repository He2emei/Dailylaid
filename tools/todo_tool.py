# tools/todo_tool.py
"""待办任务工具"""

import json
from datetime import datetime, timedelta
from typing import Dict

from .base_tool import BaseTool
from utils import get_logger

logger = get_logger("todo_tool")


class TodoAddTool(BaseTool):
    """添加待办任务"""
    
    name = "todo_add"
    description = """添加待办任务。当用户提到需要完成的事情时使用。
    例如：
    - "下周五之前交报告"
    - "帮我记住要去超市买菜"
    - "今天要背50个单词"
    待办任务会追踪完成状态，未完成前会持续提醒。
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "任务标题/内容"
            },
            "deadline": {
                "type": "string",
                "description": "截止时间，格式: YYYY-MM-DD HH:MM。这是任务必须完成的最后期限。"
            },
            "scheduled_time": {
                "type": "string",
                "description": "预设提醒时间，格式: YYYY-MM-DD HH:MM。这是用户打算开始做这个任务的时间。不同于 deadline，这是'想在什么时候做'。"
            },
            "priority": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "优先级：high(紧急/重要)、medium(默认)、low(有空再做)"
            },
            "category": {
                "type": "string",
                "description": "分类：工作/学习/生活/健康 等（可选）"
            },
            "description": {
                "type": "string",
                "description": "详细描述（可选）"
            }
        },
        "required": ["title"]
    }
    
    def execute(self, user_id: str, **params) -> str:
        """添加待办任务"""
        title = params.get("title")
        deadline = params.get("deadline")
        scheduled_time = params.get("scheduled_time")
        priority = params.get("priority", "medium")
        category = params.get("category")
        description = params.get("description")
        source_type = params.get("source_type", "private")
        source_group_id = params.get("source_group_id")
        source_message_id = params.get("source_message_id")
        
        if not title:
            return "需要提供任务标题"
        
        # 解析时间
        deadline_dt = None
        if deadline:
            try:
                deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
            except ValueError:
                return f"截止时间格式错误: {deadline}，请使用 YYYY-MM-DD HH:MM 格式"
        
        scheduled_dt = None
        if scheduled_time:
            try:
                scheduled_dt = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")
            except ValueError:
                return f"预设时间格式错误: {scheduled_time}，请使用 YYYY-MM-DD HH:MM 格式"
        
        # 保存到数据库
        task_data = {
            "user_id": user_id,
            "title": title,
            "description": description,
            "deadline": deadline_dt.isoformat() if deadline_dt else None,
            "scheduled_time": scheduled_dt.isoformat() if scheduled_dt else None,
            "priority": priority,
            "category": category,
            "source_type": source_type,
            "source_group_id": source_group_id,
            "source_message_id": source_message_id,
        }
        
        task_id = self.db.insert_task(task_data)
        
        # 构造回复
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
        reply = f"✅ 已添加待办 #{task_id}\n\n{priority_emoji} {title}"
        
        if deadline_dt:
            reply += f"\n⏰ 截止: {deadline_dt.strftime('%m月%d日 %H:%M')}"
        if scheduled_dt:
            reply += f"\n📅 预定: {scheduled_dt.strftime('%m月%d日 %H:%M')}"
        if category:
            reply += f"\n🏷️ {category}"
        
        reply += "\n\n💡 回复本消息可：完成 ✅ / 推迟 ⏳ / 取消 ❌"
        
        logger.info(f"添加待办: [{user_id}] #{task_id} {title}")
        return reply


class TodoListTool(BaseTool):
    """查看待办任务列表"""
    
    name = "todo_list"
    description = """查看待办任务。当用户问有什么要做、待办列表时使用。
    例如：
    - "我有什么待办"
    - "看看我的任务"
    - "还有什么没做的"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["pending", "done", "cancelled"],
                "description": "过滤状态，默认显示 pending（未完成）"
            },
            "show_overdue": {
                "type": "boolean",
                "description": "是否单独标注逾期任务，默认 true"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, **params) -> str:
        """查询待办列表"""
        status = params.get("status", "pending")
        show_overdue = params.get("show_overdue", True)
        
        tasks = self.db.get_tasks(user_id, status=status if status != "pending" else None)
        
        if not tasks:
            if status == "pending":
                return "✨ 没有待办任务，真棒！"
            return f"没有状态为 {status} 的任务"
        
        now = datetime.now()
        
        # 分组：逾期 / 今日 / 其他
        overdue = []
        today_tasks = []
        other = []
        
        for t in tasks:
            if status != "pending":
                other.append(t)
                continue
            
            if t.get("deadline"):
                try:
                    dl = datetime.fromisoformat(t["deadline"])
                    if dl < now:
                        overdue.append(t)
                        continue
                    elif dl.date() == now.date():
                        today_tasks.append(t)
                        continue
                except (ValueError, TypeError):
                    pass
            
            if t.get("scheduled_time"):
                try:
                    st = datetime.fromisoformat(t["scheduled_time"])
                    if st.date() == now.date():
                        today_tasks.append(t)
                        continue
                except (ValueError, TypeError):
                    pass
            
            other.append(t)
        
        # 构建输出
        result = f"📋 待办任务 ({len(tasks)} 项)：\n"
        
        if overdue and show_overdue:
            result += "\n🔴 逾期：\n"
            for t in overdue:
                result += self._format_task(t, show_deadline=True)
        
        if today_tasks:
            result += "\n📅 今日：\n"
            for t in today_tasks:
                result += self._format_task(t, show_deadline=True)
        
        if other:
            label = "\n📋 其他：\n" if (overdue or today_tasks) else "\n"
            result += label
            for t in other:
                result += self._format_task(t, show_deadline=True)
        
        return result
    
    def _format_task(self, task: dict, show_deadline: bool = False) -> str:
        """格式化单个任务"""
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
            task.get("priority", "medium"), "🟡"
        )
        line = f"  {priority_emoji} #{task['id']} {task['title']}"
        
        if show_deadline and task.get("deadline"):
            try:
                dl = datetime.fromisoformat(task["deadline"])
                line += f" (截止: {dl.strftime('%m/%d %H:%M')})"
            except (ValueError, TypeError):
                pass
        
        if task.get("category"):
            line += f" [{task['category']}]"
        
        return line + "\n"


class TodoCompleteTool(BaseTool):
    """标记任务完成"""
    
    name = "todo_complete"
    description = """标记待办任务完成。当用户说某件事做完了时使用。
    例如：
    - "报告交了"
    - "买菜完成"
    - "#3 完成"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "任务 ID（如 #3 中的 3）"
            },
            "title_keyword": {
                "type": "string",
                "description": "任务标题关键词（如果用户没有指定 ID，用关键词模糊匹配）"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, **params) -> str:
        """标记任务完成"""
        task_id = params.get("task_id")
        keyword = params.get("title_keyword")
        
        if task_id:
            task = self.db.get_task_by_id(task_id)
            if not task:
                return f"未找到任务 #{task_id}"
            if task["user_id"] != user_id:
                return "无权操作此任务"
            if task["status"] != "pending":
                return f"任务 #{task_id} 已经是 {task['status']} 状态"
        elif keyword:
            # 模糊匹配
            tasks = self.db.get_tasks(user_id)
            matched = [t for t in tasks if keyword in t["title"]]
            if not matched:
                return f"未找到包含 '{keyword}' 的待办任务"
            if len(matched) > 1:
                lines = [f"找到多个匹配任务，请指定 ID："]
                for t in matched:
                    lines.append(f"  #{t['id']} {t['title']}")
                return "\n".join(lines)
            task = matched[0]
            task_id = task["id"]
        else:
            return "请指定任务 ID 或标题关键词"
        
        success = self.db.complete_task(task_id)
        if success:
            logger.info(f"完成待办: [{user_id}] #{task_id} {task['title']}")
            return f"✅ 已完成：{task['title']} 🎉"
        return "操作失败"


class TodoUpdateTool(BaseTool):
    """更新待办任务（修改时间、描述等）"""
    
    name = "todo_update"
    description = """更新待办任务信息。当用户要推迟、修改截止时间或更新任务内容时使用。
    例如：
    - "#3 推迟到下周一"
    - "报告的截止时间改成周日"
    - "给买菜加个备注：要买鸡蛋"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "任务 ID"
            },
            "new_deadline": {
                "type": "string",
                "description": "新截止时间，格式: YYYY-MM-DD HH:MM"
            },
            "new_scheduled_time": {
                "type": "string",
                "description": "新预设时间，格式: YYYY-MM-DD HH:MM"
            },
            "new_title": {
                "type": "string",
                "description": "新标题"
            },
            "add_description": {
                "type": "string",
                "description": "追加描述/备注"
            },
            "new_priority": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "新优先级"
            }
        },
        "required": ["task_id"]
    }
    
    def execute(self, user_id: str, **params) -> str:
        """更新任务"""
        task_id = params.get("task_id")
        
        task = self.db.get_task_by_id(task_id)
        if not task:
            return f"未找到任务 #{task_id}"
        if task["user_id"] != user_id:
            return "无权操作此任务"
        if task["status"] != "pending":
            return f"任务 #{task_id} 已经是 {task['status']} 状态，无法修改"
        
        updates = {}
        changes = []
        
        # 更新截止时间
        if params.get("new_deadline"):
            try:
                dl = datetime.strptime(params["new_deadline"], "%Y-%m-%d %H:%M")
                updates["deadline"] = dl.isoformat()
                changes.append(f"⏰ 截止 → {dl.strftime('%m月%d日 %H:%M')}")
            except ValueError:
                return f"截止时间格式错误: {params['new_deadline']}"
        
        # 更新预设时间
        if params.get("new_scheduled_time"):
            try:
                st = datetime.strptime(params["new_scheduled_time"], "%Y-%m-%d %H:%M")
                updates["scheduled_time"] = st.isoformat()
                changes.append(f"📅 预定 → {st.strftime('%m月%d日 %H:%M')}")
            except ValueError:
                return f"预设时间格式错误: {params['new_scheduled_time']}"
        
        # 更新标题
        if params.get("new_title"):
            updates["title"] = params["new_title"]
            changes.append(f"📝 标题 → {params['new_title']}")
        
        # 追加描述
        if params.get("add_description"):
            old_desc = task.get("description") or ""
            new_desc = f"{old_desc}\n{params['add_description']}" if old_desc else params["add_description"]
            updates["description"] = new_desc
            changes.append(f"📎 备注已更新")
        
        # 更新优先级
        if params.get("new_priority"):
            updates["priority"] = params["new_priority"]
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[params["new_priority"]]
            changes.append(f"{emoji} 优先级 → {params['new_priority']}")
        
        if not updates:
            return "没有需要更新的内容"
        
        success = self.db.update_task(task_id, updates)
        if success:
            result = f"✅ 已更新任务 #{task_id}：{task['title']}\n"
            result += "\n".join(changes)
            logger.info(f"更新待办: [{user_id}] #{task_id}")
            return result
        return "更新失败"


class TodoCancelTool(BaseTool):
    """取消待办任务"""
    
    name = "todo_cancel"
    description = """取消待办任务。当用户说不做了、取消时使用。
    例如：
    - "#3 取消"
    - "买菜不用了"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "任务 ID"
            },
            "title_keyword": {
                "type": "string",
                "description": "任务标题关键词（如果用户没有指定 ID）"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, **params) -> str:
        """取消任务"""
        task_id = params.get("task_id")
        keyword = params.get("title_keyword")
        
        if task_id:
            task = self.db.get_task_by_id(task_id)
            if not task:
                return f"未找到任务 #{task_id}"
            if task["user_id"] != user_id:
                return "无权操作此任务"
            if task["status"] != "pending":
                return f"任务 #{task_id} 已经是 {task['status']} 状态"
        elif keyword:
            tasks = self.db.get_tasks(user_id)
            matched = [t for t in tasks if keyword in t["title"]]
            if not matched:
                return f"未找到包含 '{keyword}' 的待办任务"
            if len(matched) > 1:
                lines = [f"找到多个匹配任务，请指定 ID："]
                for t in matched:
                    lines.append(f"  #{t['id']} {t['title']}")
                return "\n".join(lines)
            task = matched[0]
            task_id = task["id"]
        else:
            return "请指定任务 ID 或标题关键词"
        
        success = self.db.cancel_task(task_id)
        if success:
            logger.info(f"取消待办: [{user_id}] #{task_id} {task['title']}")
            return f"❌ 已取消：{task['title']}"
        return "操作失败"

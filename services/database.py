# services/database.py
"""数据库管理模块"""

import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from utils import get_logger

logger = get_logger("database")


class DatabaseManager:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str):
        """初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_dir()
        self._init_tables()
        logger.info(f"数据库初始化完成: {db_path}")
    
    def _ensure_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 人情记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    person TEXT NOT NULL,
                    event TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 待办表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT,
                    due_date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 兴趣记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    tags TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 收集箱
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    raw_message TEXT NOT NULL,
                    processed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 日程表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    location TEXT,
                    reminders TEXT DEFAULT '[]',
                    repeat_rule TEXT DEFAULT '{"type": "none"}',
                    source_message TEXT,
                    related_messages TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 提醒日志表（防止重复提醒）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminder_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    remind_time TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(schedule_id, remind_time)
                )
            ''')
            
            # 活动记录表（时间线）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    category TEXT,
                    tags TEXT,
                    location TEXT,
                    related_messages TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 待办任务表（新版 Todo 系统）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    deadline TEXT,
                    scheduled_time TEXT,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    template_id INTEGER,
                    category TEXT,
                    tags TEXT DEFAULT '[]',
                    source_message_id TEXT,
                    bound_message_ids TEXT DEFAULT '[]',
                    source_type TEXT DEFAULT 'private',
                    source_group_id TEXT,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 重复任务模板
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    tags TEXT DEFAULT '[]',
                    priority TEXT DEFAULT 'medium',
                    recurrence_type TEXT NOT NULL,
                    recurrence_rule TEXT NOT NULL,
                    default_deadline_offset TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_generated TEXT,
                    next_generate TEXT,
                    source_type TEXT DEFAULT 'private',
                    source_group_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 任务提醒日志
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_reminder_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    remind_type TEXT NOT NULL,
                    remind_time TEXT NOT NULL,
                    message_id TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(task_id, remind_type, remind_time)
                )
            ''')
            
            # 用户偏好
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    daily_brief_time TEXT DEFAULT '08:00',
                    daily_brief_enabled BOOLEAN DEFAULT 1,
                    timezone TEXT DEFAULT 'Asia/Shanghai',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 兼容迁移：为旧数据库补充来源字段
            try:
                cursor.execute("ALTER TABLE schedules ADD COLUMN source_type TEXT DEFAULT 'private'")
            except sqlite3.OperationalError:
                pass  # 列已存在
            try:
                cursor.execute("ALTER TABLE schedules ADD COLUMN source_group_id TEXT")
            except sqlite3.OperationalError:
                pass  # 列已存在
            
            conn.commit()
    
    # === 收集箱操作 ===
    
    def add_to_inbox(self, user_id: str, message: str) -> int:
        """添加消息到收集箱"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO inbox (user_id, raw_message) VALUES (?, ?)",
                (user_id, message)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_inbox(self, user_id: str, limit: int = 10) -> List[Dict]:
        """获取收集箱消息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM inbox WHERE user_id = ? AND processed = 0 ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # === 人情操作 ===
    
    def add_favor(self, user_id: str, person: str, event: str, 
                  direction: str, date: str = None) -> int:
        """添加人情记录
        
        Args:
            user_id: 用户QQ号
            person: 对方名称
            event: 事件描述
            direction: 'given'(我给) / 'received'(我收)
            date: 日期
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO favors (user_id, person, event, direction, date) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, person, event, direction, date or datetime.now().strftime("%Y-%m-%d"))
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_favors(self, user_id: str, person: str = None) -> List[Dict]:
        """获取人情记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if person:
                cursor.execute(
                    "SELECT * FROM favors WHERE user_id = ? AND person LIKE ? ORDER BY date DESC",
                    (user_id, f"%{person}%")
                )
            else:
                cursor.execute(
                    "SELECT * FROM favors WHERE user_id = ? ORDER BY date DESC",
                    (user_id,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    # === 待办操作 ===
    
    def add_todo(self, user_id: str, content: str, 
                 category: str = None, due_date: str = None) -> int:
        """添加待办"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO todos (user_id, content, category, due_date) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, content, category, due_date)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_todos(self, user_id: str, status: str = "pending") -> List[Dict]:
        """获取待办列表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM todos WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def complete_todo(self, todo_id: int) -> bool:
        """完成待办"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE todos SET status = 'done' WHERE id = ?",
                (todo_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    # === 兴趣操作 ===
    
    def add_interest(self, user_id: str, type_: str, name: str,
                     description: str = None, tags: str = None, source: str = None) -> int:
        """添加兴趣记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO interests (user_id, type, name, description, tags, source) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, type_, name, description, tags, source)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_interests(self, user_id: str, type_: str = None) -> List[Dict]:
        """获取兴趣记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if type_:
                cursor.execute(
                    "SELECT * FROM interests WHERE user_id = ? AND type = ? ORDER BY created_at DESC",
                    (user_id, type_)
                )
            else:
                cursor.execute(
                    "SELECT * FROM interests WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    # === 日程操作 ===
    
    def insert_schedule(self, data: Dict[str, Any]) -> int:
        """插入日程"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO schedules 
                   (user_id, title, description, start_time, end_time, location, 
                    reminders, repeat_rule, source_message, source_type, source_group_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["user_id"], data["title"], data.get("description"),
                 data["start_time"], data.get("end_time"), data.get("location"),
                 data.get("reminders", "[]"), data.get("repeat_rule", '{"type": "none"}'),
                 data.get("source_message"),
                 data.get("source_type", "private"),
                 data.get("source_group_id"))
            )
            conn.commit()
            return cursor.lastrowid

    
    def get_schedules(self, user_id: str, start_date, end_date) -> List[Dict]:
        """获取日期范围内的日程"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM schedules 
                   WHERE user_id = ? 
                   AND (date(start_time) BETWEEN ? AND ? 
                        OR repeat_rule != '{"type": "none"}')
                   ORDER BY start_time""",
                (user_id, str(start_date), str(end_date))
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_schedule_by_id(self, schedule_id: int) -> Optional[Dict]:
        """获取单个日程"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_schedule(self, schedule_id: int, updates: Dict[str, Any]) -> bool:
        """更新日程"""
        if not updates:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [schedule_id]
            cursor.execute(
                f"UPDATE schedules SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_schedule(self, schedule_id: int) -> bool:
        """删除日程"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_upcoming_schedules(self, hours: int = 24) -> List[Dict]:
        """获取未来 N 小时内的日程（用于提醒）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM schedules 
                   WHERE datetime(start_time) BETWEEN datetime('now') AND datetime('now', ? || ' hours')
                   ORDER BY start_time""",
                (str(hours),)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # === 提醒日志 ===
    
    def log_reminder(self, schedule_id: int, remind_time: str) -> bool:
        """记录已发送的提醒"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO reminder_logs (schedule_id, remind_time) VALUES (?, ?)",
                    (schedule_id, remind_time)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # 已存在，避免重复
                return False
    
    def is_reminder_sent(self, schedule_id: int, remind_time: str) -> bool:
        """检查提醒是否已发送"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM reminder_logs WHERE schedule_id = ? AND remind_time = ?",
                (schedule_id, remind_time)
            )
            return cursor.fetchone() is not None
    
    # === 活动记录操作 ===
    
    def insert_activity(self, data: Dict[str, Any]) -> int:
        """插入活动记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO activities 
                   (user_id, name, description, start_time, end_time, category, 
                    tags, location, related_messages)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["user_id"], data["name"], data.get("description"),
                 data["start_time"], data.get("end_time"), data.get("category"),
                 data.get("tags", "[]"), data.get("location"),
                 data.get("related_messages", "[]"))
            )
            conn.commit()
            return cursor.lastrowid
    
    def update_activity(self, activity_id: int, updates: Dict[str, Any]) -> bool:
        """更新活动记录"""
        if not updates:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [activity_id]
            cursor.execute(
                f"UPDATE activities SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_activities(self, user_id: str, start_date, end_date) -> List[Dict]:
        """获取日期范围内的活动"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM activities 
                   WHERE user_id = ? 
                   AND date(start_time) BETWEEN ? AND ?
                   ORDER BY start_time""",
                (user_id, str(start_date), str(end_date))
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_activities_recent(self, user_id: str, hours: int = 24) -> List[Dict]:
        """获取最近N小时的活动"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM activities 
                   WHERE user_id = ?
                   AND start_time >= datetime('now', '-' || ? || ' hours')
                   ORDER BY start_time DESC""",
                (user_id, str(hours))
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_activity_by_id(self, activity_id: int) -> Optional[Dict]:
        """获取单个活动"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def check_activity_overlap(self, user_id: str, start_time: str, 
                                end_time: str = None) -> List[Dict]:
        """检测活动时间重叠
        
        Args:
            user_id: 用户ID
            start_time: 开始时间
            end_time: 结束时间（可选）
            
        Returns:
            重叠的活动列表
        """
        if not end_time:
            # 如果没有结束时间，只检查是否有活动包含这个时刻
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM activities 
                       WHERE user_id = ? 
                       AND start_time <= ? 
                       AND (end_time IS NULL OR end_time >= ?)""",
                    (user_id, start_time, start_time)
                )
                return [dict(row) for row in cursor.fetchall()]
        else:
            # 检测时间段重叠
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM activities 
                       WHERE user_id = ? 
                       AND start_time < ? 
                       AND (end_time IS NULL OR end_time > ?)""",
                    (user_id, end_time, start_time)
                )
                return [dict(row) for row in cursor.fetchall()]
    
    def find_unclosed_activities(self, user_id: str, name_pattern: str = None, 
                                   hours: int = 24) -> List[Dict]:
        """查找最近未结束的活动（end_time为NULL）
        
        用于智能补充场景：例如找到"吃饭"相关的未结束活动
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if name_pattern:
                cursor.execute(
                    """SELECT * FROM activities 
                       WHERE user_id = ? 
                       AND end_time IS NULL
                       AND name LIKE ?
                       AND start_time >= datetime('now', '-' || ? || ' hours')
                       ORDER BY start_time DESC""",
                    (user_id, f"%{name_pattern}%", str(hours))
                )
            else:
                cursor.execute(
                    """SELECT * FROM activities 
                       WHERE user_id = ? 
                       AND end_time IS NULL
                       AND start_time >= datetime('now', '-' || ? || ' hours')
                       ORDER BY start_time DESC""",
                    (user_id, str(hours))
                )
            return [dict(row) for row in cursor.fetchall()]
    
    # === 待办任务操作 (Todo System) ===
    
    def insert_task(self, data: Dict[str, Any]) -> int:
        """插入待办任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO tasks 
                   (user_id, title, description, deadline, scheduled_time,
                    priority, template_id, category, tags,
                    source_message_id, bound_message_ids, source_type, source_group_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["user_id"], data["title"], data.get("description"),
                 data.get("deadline"), data.get("scheduled_time"),
                 data.get("priority", "medium"), data.get("template_id"),
                 data.get("category"), data.get("tags", "[]"),
                 data.get("source_message_id"),
                 data.get("bound_message_ids", "[]"),
                 data.get("source_type", "private"),
                 data.get("source_group_id"))
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """获取单个任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_tasks(self, user_id: str, status: str = None,
                  include_overdue: bool = False) -> List[Dict]:
        """获取待办任务列表
        
        Args:
            user_id: 用户 ID
            status: 过滤状态（None=all pending, 'done', 'cancelled'）
            include_overdue: 是否包含逾期任务
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    """SELECT * FROM tasks 
                       WHERE user_id = ? AND status = ?
                       ORDER BY COALESCE(deadline, '9999-12-31') ASC, created_at DESC""",
                    (user_id, status)
                )
            else:
                # 默认获取所有 pending 任务
                cursor.execute(
                    """SELECT * FROM tasks 
                       WHERE user_id = ? AND status = 'pending'
                       ORDER BY COALESCE(deadline, '9999-12-31') ASC, created_at DESC""",
                    (user_id,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_tasks_by_date(self, user_id: str, target_date: str) -> List[Dict]:
        """获取某天到期或预定的待办任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM tasks 
                   WHERE user_id = ? AND status = 'pending'
                   AND (date(deadline) = ? OR date(scheduled_time) = ?)
                   ORDER BY COALESCE(scheduled_time, deadline, '9999') ASC""",
                (user_id, target_date, target_date)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_overdue_tasks(self, user_id: str = None) -> List[Dict]:
        """获取所有逾期的 pending 任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """SELECT * FROM tasks 
                       WHERE user_id = ? AND status = 'pending'
                       AND deadline IS NOT NULL
                       AND datetime(deadline) < datetime('now')
                       ORDER BY deadline ASC""",
                    (user_id,)
                )
            else:
                cursor.execute(
                    """SELECT * FROM tasks 
                       WHERE status = 'pending'
                       AND deadline IS NOT NULL
                       AND datetime(deadline) < datetime('now')
                       ORDER BY deadline ASC"""
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_upcoming_tasks(self, hours: int = 24) -> List[Dict]:
        """获取未来 N 小时内有 scheduled_time 或 deadline 的 pending 任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM tasks 
                   WHERE status = 'pending'
                   AND (
                       (scheduled_time IS NOT NULL 
                        AND datetime(scheduled_time) BETWEEN datetime('now') AND datetime('now', ? || ' hours'))
                       OR
                       (deadline IS NOT NULL 
                        AND datetime(deadline) BETWEEN datetime('now') AND datetime('now', ? || ' hours'))
                   )
                   ORDER BY COALESCE(scheduled_time, deadline) ASC""",
                (str(hours), str(hours))
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def update_task(self, task_id: int, updates: Dict[str, Any]) -> bool:
        """更新任务"""
        if not updates:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [task_id]
            cursor.execute(
                f"UPDATE tasks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def complete_task(self, task_id: int) -> bool:
        """标记任务完成"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE tasks SET status = 'done', completed_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'""",
                (task_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE tasks SET status = 'cancelled',
                   updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'""",
                (task_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def find_task_by_bound_message(self, message_id: str) -> Optional[Dict]:
        """通过消息 ID 反查关联的任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # bound_message_ids 是 JSON 数组，使用 LIKE 做模糊匹配
            cursor.execute(
                """SELECT * FROM tasks 
                   WHERE bound_message_ids LIKE ? AND status = 'pending'
                   ORDER BY updated_at DESC LIMIT 1""",
                (f'%{message_id}%',)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def find_task_by_source_message(self, message_id: str, user_id: str = None) -> Optional[Dict]:
        """通过 source_message_id 反查任务（备选方案）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """SELECT * FROM tasks 
                       WHERE source_message_id = ? AND user_id = ? AND status = 'pending'
                       ORDER BY updated_at DESC LIMIT 1""",
                    (message_id, user_id)
                )
            else:
                cursor.execute(
                    """SELECT * FROM tasks 
                       WHERE source_message_id = ? AND status = 'pending'
                       ORDER BY updated_at DESC LIMIT 1""",
                    (message_id,)
                )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def append_bound_message(self, task_id: int, message_id: str) -> bool:
        """追加消息 ID 到任务的 bound_message_ids"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False
        
        import json
        ids = json.loads(task.get("bound_message_ids", "[]"))
        ids.append(str(message_id))
        
        return self.update_task(task_id, {
            "bound_message_ids": json.dumps(ids)
        })
    
    # === 任务提醒日志 ===
    
    def log_task_reminder(self, task_id: int, remind_type: str, 
                          remind_time: str, message_id: str = None) -> bool:
        """记录任务提醒"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """INSERT INTO task_reminder_logs 
                       (task_id, remind_type, remind_time, message_id) 
                       VALUES (?, ?, ?, ?)""",
                    (task_id, remind_type, remind_time, message_id)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_task_reminder_count_today(self, task_id: int) -> int:
        """获取今天对某任务的催促次数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COUNT(*) FROM task_reminder_logs 
                   WHERE task_id = ? AND date(sent_at) = date('now')""",
                (task_id,)
            )
            return cursor.fetchone()[0]
    
    def get_last_task_reminder(self, task_id: int, remind_type: str = None) -> Optional[Dict]:
        """获取某任务最后一次提醒记录
        
        Args:
            task_id: 任务 ID
            remind_type: 提醒类型（None=不限类型）
        
        Returns:
            最后一次提醒记录 dict，或 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if remind_type:
                cursor.execute(
                    """SELECT * FROM task_reminder_logs 
                       WHERE task_id = ? AND remind_type = ?
                       ORDER BY id DESC LIMIT 1""",
                    (task_id, remind_type)
                )
            else:
                cursor.execute(
                    """SELECT * FROM task_reminder_logs 
                       WHERE task_id = ?
                       ORDER BY id DESC LIMIT 1""",
                    (task_id,)
                )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # === 用户偏好 ===
    
    def get_user_preferences(self, user_id: str) -> Dict:
        """获取用户偏好（不存在则返回默认值）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            # 返回默认值
            return {
                "user_id": user_id,
                "daily_brief_time": "08:00",
                "daily_brief_enabled": 1,
                "timezone": "Asia/Shanghai"
            }
    
    def upsert_user_preferences(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """更新用户偏好（不存在则创建）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 先尝试获取
            cursor.execute(
                "SELECT 1 FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            if cursor.fetchone():
                # 更新
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                values = list(updates.values()) + [user_id]
                cursor.execute(
                    f"UPDATE user_preferences SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    values
                )
            else:
                # 插入
                updates["user_id"] = user_id
                cols = ", ".join(updates.keys())
                placeholders = ", ".join(["?"] * len(updates))
                cursor.execute(
                    f"INSERT INTO user_preferences ({cols}) VALUES ({placeholders})",
                    list(updates.values())
                )
            conn.commit()
            return True

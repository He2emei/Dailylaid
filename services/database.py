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
                    reminders, repeat_rule, source_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["user_id"], data["title"], data.get("description"),
                 data["start_time"], data.get("end_time"), data.get("location"),
                 data.get("reminders", "[]"), data.get("repeat_rule", '{"type": "none"}'),
                 data.get("source_message"))
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


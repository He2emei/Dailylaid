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

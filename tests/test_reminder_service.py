# tests/test_reminder_service.py
"""Phase 3: ReminderService Task 提醒逻辑单元测试"""

import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.database import DatabaseManager
from services.reminder_service import ReminderService


@pytest.fixture
def db(tmp_path):
    """创建临时数据库"""
    db_path = str(tmp_path / "test.db")
    return DatabaseManager(db_path)


@pytest.fixture
def mock_callback():
    """模拟消息发送回调，返回 message_id"""
    callback = AsyncMock(return_value="99999")
    return callback


@pytest.fixture
def service(db, mock_callback):
    """创建 ReminderService 实例"""
    return ReminderService(db, send_callback=mock_callback)


def _create_task(db, user_id="test_user", title="测试任务",
                 deadline=None, scheduled_time=None, **kwargs):
    """辅助函数：创建任务并返回 task_id"""
    data = {
        "user_id": user_id,
        "title": title,
        "deadline": deadline,
        "scheduled_time": scheduled_time,
        **kwargs
    }
    return db.insert_task(data)


# ==============================================================
#  1. 预提醒 (Pre-Remind)
# ==============================================================

class TestPreRemind:
    """scheduled_time 前 30 分钟预提醒"""
    
    def test_pre_remind_triggers(self, db, service, mock_callback):
        """当 scheduled_time - 30min 在当前分钟窗口内时，应触发预提醒"""
        now = datetime.now()
        # scheduled_time 设为 now + 30min，这样 pre_remind_time = now
        scheduled = (now + timedelta(minutes=30)).isoformat()
        task_id = _create_task(db, scheduled_time=scheduled)
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args
        assert "📋 待办提醒" in call_args.kwargs.get("message", call_args[1].get("message", ""))
    
    def test_pre_remind_not_duplicate(self, db, service, mock_callback):
        """同一预提醒不应重复发送"""
        now = datetime.now()
        scheduled = (now + timedelta(minutes=30)).isoformat()
        task_id = _create_task(db, scheduled_time=scheduled)
        
        task = db.get_task_by_id(task_id)
        
        # 第一次
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        assert mock_callback.call_count == 1
        
        # 第二次 - 应该被去重
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        assert mock_callback.call_count == 1  # 没有新调用


# ==============================================================
#  2. 到时提醒 (On-Time)
# ==============================================================

class TestOnTimeRemind:
    """scheduled_time 到达时提醒"""
    
    def test_on_time_triggers(self, db, service, mock_callback):
        """当 scheduled_time 在当前分钟窗口内时，应触发到时提醒"""
        now = datetime.now()
        scheduled = now.isoformat()
        task_id = _create_task(db, scheduled_time=scheduled)
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args
        assert "现在该做了" in call_args.kwargs.get("message", call_args[1].get("message", ""))


# ==============================================================
#  3. Deadline 预警
# ==============================================================

class TestDeadlineWarn:
    """deadline 前 1 小时预警"""
    
    def test_deadline_warn_triggers(self, db, service, mock_callback):
        """当 deadline - 60min 在当前分钟窗口内时，应触发预警"""
        now = datetime.now()
        deadline = (now + timedelta(minutes=60)).isoformat()
        task_id = _create_task(db, deadline=deadline)
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args
        assert "截止时间快到了" in call_args.kwargs.get("message", call_args[1].get("message", ""))


# ==============================================================
#  4. 逾期催促 (Overdue Backoff)
# ==============================================================

class TestOverdueRemind:
    """逾期指数退避催促"""
    
    def test_overdue_triggers(self, db, service, mock_callback):
        """逾期任务应触发催促"""
        now = datetime.now()
        deadline = (now - timedelta(hours=3)).isoformat()
        task_id = _create_task(db, deadline=deadline)
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_overdue_task(task, now)
        )
        
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args
        assert "逾期" in call_args.kwargs.get("message", call_args[1].get("message", ""))
    
    def test_overdue_daily_limit(self, db, service, mock_callback):
        """每天最多催 MAX_DAILY_REMINDERS 次"""
        now = datetime.now()
        deadline = (now - timedelta(hours=3)).isoformat()
        task_id = _create_task(db, deadline=deadline)
        
        # 预先填入 MAX_DAILY_REMINDERS 条今日记录
        for i in range(service.MAX_DAILY_REMINDERS):
            db.log_task_reminder(task_id, "overdue",
                                (now - timedelta(hours=i+1)).isoformat())
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_overdue_task(task, now)
        )
        
        mock_callback.assert_not_called()
    
    def test_overdue_stops_after_max_days(self, db, service, mock_callback):
        """逾期超过 MAX_OVERDUE_DAYS 天后停止催促"""
        now = datetime.now()
        deadline = (now - timedelta(days=service.MAX_OVERDUE_DAYS + 1)).isoformat()
        task_id = _create_task(db, deadline=deadline)
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_overdue_task(task, now)
        )
        
        mock_callback.assert_not_called()
    
    def test_overdue_respects_backoff(self, db, service, mock_callback):
        """退避期间不应重复催促"""
        now = datetime.now()
        deadline = (now - timedelta(hours=3)).isoformat()
        task_id = _create_task(db, deadline=deadline)
        
        # 模拟 1 小时前刚催过（当前间隔应为 2h，所以还没到）
        db.log_task_reminder(task_id, "overdue",
                            (now - timedelta(hours=1)).isoformat())
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_overdue_task(task, now)
        )
        
        mock_callback.assert_not_called()


# ==============================================================
#  5. 去重验证
# ==============================================================

class TestDeduplication:
    """提醒去重"""
    
    def test_same_reminder_not_sent_twice(self, db, service, mock_callback):
        """同类型同时间的提醒只发一次"""
        now = datetime.now()
        scheduled = now.isoformat()
        task_id = _create_task(db, scheduled_time=scheduled)
        
        task = db.get_task_by_id(task_id)
        
        # 调用两次
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        asyncio.get_event_loop().run_until_complete(
            service._process_task_reminders(task, now)
        )
        
        assert mock_callback.call_count == 1


# ==============================================================
#  6. Message ID 绑定
# ==============================================================

class TestMessageBinding:
    """催促消息发送后 message_id 绑定到任务"""
    
    def test_reminder_binds_message_id(self, db, service, mock_callback):
        """催促消息发送后，message_id 应被追加到 bound_message_ids"""
        import json
        
        now = datetime.now()
        deadline = (now - timedelta(hours=3)).isoformat()
        task_id = _create_task(db, deadline=deadline)
        
        task = db.get_task_by_id(task_id)
        asyncio.get_event_loop().run_until_complete(
            service._process_overdue_task(task, now)
        )
        
        # 检查 bound_message_ids 是否包含返回的 message_id
        updated_task = db.get_task_by_id(task_id)
        bound_ids = json.loads(updated_task["bound_message_ids"])
        assert "99999" in bound_ids


# ==============================================================
#  7. 数据库方法: get_last_task_reminder
# ==============================================================

class TestGetLastTaskReminder:
    """database.py 新增的 get_last_task_reminder 方法"""
    
    def test_returns_none_when_no_reminders(self, db):
        """无提醒记录时返回 None"""
        result = db.get_last_task_reminder(999)
        assert result is None
    
    def test_returns_latest_reminder(self, db):
        """返回最新的一条记录"""
        task_id = _create_task(db)
        
        db.log_task_reminder(task_id, "overdue", "2026-03-16T10:00:00")
        db.log_task_reminder(task_id, "overdue", "2026-03-16T12:00:00")
        db.log_task_reminder(task_id, "overdue", "2026-03-16T14:00:00")
        
        result = db.get_last_task_reminder(task_id, "overdue")
        assert result is not None
        assert result["remind_time"] == "2026-03-16T14:00:00"
    
    def test_filters_by_remind_type(self, db):
        """按 remind_type 过滤"""
        task_id = _create_task(db)
        
        db.log_task_reminder(task_id, "scheduled", "2026-03-16T10:00:00")
        db.log_task_reminder(task_id, "overdue", "2026-03-16T12:00:00")
        
        result = db.get_last_task_reminder(task_id, "scheduled")
        assert result["remind_type"] == "scheduled"

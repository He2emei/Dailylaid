"""快速验证 Todo 系统 Phase 1"""
import sys, os
sys.path.insert(0, ".")

from services.database import DatabaseManager

DB_PATH = "data/_test_todo_verify.db"


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    db = DatabaseManager(DB_PATH)
    print("1. DB init OK")
    
    tid = db.insert_task({
        "user_id": "u1", "title": "交报告",
        "deadline": "2026-03-15T14:00:00", "priority": "high"
    })
    tid2 = db.insert_task({
        "user_id": "u1", "title": "买菜",
        "scheduled_time": "2026-03-13T18:00:00", "priority": "low"
    })
    print(f"2. Insert OK: #{tid}, #{tid2}")
    
    tasks = db.get_tasks("u1")
    assert len(tasks) == 2
    print(f"3. Query OK: {len(tasks)} tasks")
    
    db.complete_task(tid)
    t = db.get_task_by_id(tid)
    assert t["status"] == "done"
    print(f"4. Complete OK")
    
    db.cancel_task(tid2)
    t2 = db.get_task_by_id(tid2)
    assert t2["status"] == "cancelled"
    print(f"5. Cancel OK")
    
    tid3 = db.insert_task({"user_id": "u1", "title": "Bind test"})
    db.append_bound_message(tid3, "msg_001")
    found = db.find_task_by_bound_message("msg_001")
    assert found and found["id"] == tid3
    print(f"6. Message binding OK")
    
    prefs = db.get_user_preferences("u1")
    assert prefs["daily_brief_time"] == "08:00"
    db.upsert_user_preferences("u1", {"daily_brief_time": "07:30"})
    prefs2 = db.get_user_preferences("u1")
    assert prefs2["daily_brief_time"] == "07:30"
    print(f"7. User prefs OK")
    
    from tools.todo_tool import TodoAddTool, TodoListTool
    add_tool = TodoAddTool(db)
    result = add_tool.execute("u2", title="Tool test", priority="medium")
    assert "已添加待办" in result
    print(f"8. TodoAddTool OK")
    
    list_tool = TodoListTool(db)
    result = list_tool.execute("u2")
    assert "Tool test" in result
    print(f"9. TodoListTool OK")
    
    os.remove(DB_PATH)
    print("\nALL PASS")


if __name__ == "__main__":
    main()

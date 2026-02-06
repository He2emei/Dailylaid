# test_schedule.py
"""测试日程工具 MCP 实现"""

import sys
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from services.database import DatabaseManager


def main():
    print("=== 日程工具测试 ===\n")
    
    # 初始化数据库
    db = DatabaseManager("data/dailylaid.db")
    
    user_id = "test_user"
    
    # 1. 添加日程
    print("1. 添加日程...")
    schedule_data = {
        "user_id": user_id,
        "title": "测试会议",
        "start_time": "2026-02-07T14:00:00",
        "location": "会议室A",
        "reminders": "[60, 30, 10]",
        "repeat_rule": '{"type": "none"}',
        "source_message": "明天下午2点开会"
    }
    schedule_id = db.insert_schedule(schedule_data)
    print(f"   创建成功: ID={schedule_id}")
    
    # 2. 添加重复日程
    print("\n2. 添加重复日程...")
    schedule_data2 = {
        "user_id": user_id,
        "title": "每周例会",
        "start_time": "2026-02-10T10:00:00",
        "reminders": "[30]",
        "repeat_rule": '{"type": "weekly", "weekdays": [0]}',
    }
    schedule_id2 = db.insert_schedule(schedule_data2)
    print(f"   创建成功: ID={schedule_id2}")
    
    # 3. 查询日程
    print("\n3. 查询日程...")
    from datetime import date, timedelta
    today = date.today()
    schedules = db.get_schedules(user_id, today, today + timedelta(days=30))
    for s in schedules:
        print(f"   [{s['id']}] {s['title']} @ {s['start_time']}")
    
    # 4. 更新日程
    print("\n4. 更新日程...")
    db.update_schedule(schedule_id, {"title": "测试会议（已更新）", "location": "会议室B"})
    updated = db.get_schedule_by_id(schedule_id)
    print(f"   更新后: {updated['title']} @ {updated['location']}")
    
    # 5. 删除日程
    print("\n5. 删除日程...")
    db.delete_schedule(schedule_id)
    db.delete_schedule(schedule_id2)
    print("   删除成功")
    
    print("\n✅ 测试完成!")


if __name__ == "__main__":
    main()

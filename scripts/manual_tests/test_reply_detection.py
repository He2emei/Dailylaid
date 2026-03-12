# scripts/manual_tests/test_reply_detection.py
"""测试 OneBot 11 回复消息的解析

运行方法：
1. 启动 Dailylaid 主程序
2. 在 QQ 中发送一条普通消息，观察日志
3. 回复那条消息，观察日志中的 reply 信息
4. 本脚本模拟解析逻辑，可以用测试数据验证
"""

import re
import json


def extract_reply_id(raw_message: str) -> int | None:
    """从 raw_message 中提取被回复消息的 ID
    
    OneBot 11 中，回复消息的 raw_message 格式：
    [CQ:reply,id=12345] 实际回复内容
    """
    match = re.search(r'\[CQ:reply,id=(\d+)\]', raw_message)
    if match:
        return int(match.group(1))
    return None


def extract_reply_id_from_message_array(message: list) -> int | None:
    """从 message 数组中提取被回复消息的 ID
    
    OneBot 11 message 数组格式：
    [
        {"type": "reply", "data": {"id": "12345"}},
        {"type": "text", "data": {"text": "实际回复内容"}}
    ]
    """
    for seg in message:
        if isinstance(seg, dict) and seg.get("type") == "reply":
            reply_id = seg.get("data", {}).get("id")
            if reply_id:
                return int(reply_id)
    return None


def strip_cq_codes(raw_message: str) -> str:
    """移除所有 CQ 码，返回纯文本"""
    return re.sub(r'\[CQ:[^\]]+\]', '', raw_message).strip()


def extract_text_from_message_array(message: list) -> str:
    """从 message 数组中提取纯文本"""
    texts = []
    for seg in message:
        if isinstance(seg, dict) and seg.get("type") == "text":
            texts.append(seg.get("data", {}).get("text", ""))
    return "".join(texts).strip()


# ===== 测试用例 =====

def test_parse_reply():
    """模拟 NapCat 发来的回复消息"""
    
    # 场景 1: 用户回复一条消息说"完成了"
    test_data_1 = {
        "post_type": "message",
        "message_type": "private",
        "user_id": 123456,
        "raw_message": "[CQ:reply,id=98765] 完成了",
        "message": [
            {"type": "reply", "data": {"id": "98765"}},
            {"type": "text", "data": {"text": "完成了"}}
        ]
    }
    
    # 从 raw_message 解析
    reply_id = extract_reply_id(test_data_1["raw_message"])
    actual_text = strip_cq_codes(test_data_1["raw_message"])
    print(f"测试1 (raw_message):")
    print(f"  回复的消息ID: {reply_id}")
    print(f"  实际文本: {actual_text}")
    assert reply_id == 98765
    assert actual_text == "完成了"
    
    # 从 message 数组解析
    reply_id_2 = extract_reply_id_from_message_array(test_data_1["message"])
    actual_text_2 = extract_text_from_message_array(test_data_1["message"])
    print(f"测试1 (message array):")
    print(f"  回复的消息ID: {reply_id_2}")
    print(f"  实际文本: {actual_text_2}")
    assert reply_id_2 == 98765
    assert actual_text_2 == "完成了"
    
    # 场景 2: 普通消息（无回复）
    test_data_2 = {
        "raw_message": "下周交报告",
        "message": [
            {"type": "text", "data": {"text": "下周交报告"}}
        ]
    }
    
    reply_id_3 = extract_reply_id(test_data_2["raw_message"])
    reply_id_4 = extract_reply_id_from_message_array(test_data_2["message"])
    print(f"\n测试2 (普通消息):")
    print(f"  raw_message reply_id: {reply_id_3}")
    print(f"  message array reply_id: {reply_id_4}")
    assert reply_id_3 is None
    assert reply_id_4 is None
    
    # 场景 3: 回复消息+推迟指令
    test_data_3 = {
        "raw_message": "[CQ:reply,id=12388][CQ:at,qq=BOT_QQ] 推迟到周日",
        "message": [
            {"type": "reply", "data": {"id": "12388"}},
            {"type": "at", "data": {"qq": "BOT_QQ"}},
            {"type": "text", "data": {"text": " 推迟到周日"}}
        ]
    }
    
    reply_id_5 = extract_reply_id(test_data_3["raw_message"])
    actual_text_5 = strip_cq_codes(test_data_3["raw_message"])
    actual_text_6 = extract_text_from_message_array(test_data_3["message"])
    print(f"\n测试3 (回复+AT+推迟):")
    print(f"  回复的消息ID: {reply_id_5}")
    print(f"  raw_message 文本: '{actual_text_5}'")
    print(f"  message array 文本: '{actual_text_6}'")
    assert reply_id_5 == 12388
    
    print("\n✅ 所有解析测试通过!")


def test_send_message_response():
    """模拟 send_msg API 返回值"""
    
    # OneBot 11 send_msg 返回格式
    mock_response = {
        "status": "ok",
        "retcode": 0,
        "data": {
            "message_id": 54321
        },
        "echo": "dailylaid_1"
    }
    
    message_id = mock_response.get("data", {}).get("message_id")
    print(f"\n发送消息返回的 message_id: {message_id}")
    assert message_id == 54321
    
    print("✅ 发送消息 ID 获取测试通过!")


if __name__ == "__main__":
    print("=" * 50)
    print("  OneBot 11 回复消息解析测试")
    print("=" * 50)
    print()
    
    test_parse_reply()
    test_send_message_response()
    
    print("\n" + "=" * 50)
    print("  全部测试通过 ✅")
    print("=" * 50)
    print()
    print("下一步：启动真实程序，发送回复消息，检查日志中的实际数据格式")

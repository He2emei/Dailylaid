# test_llm.py
"""测试 LLM API 连接"""

import requests


BASE_URL = "https://aicanapi.com/v1"
API_KEY = "sk-QiLkXTrfzLJ6x0ZQewCSbPPXY8Byy7fEQbmr12MpYxylsGai"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def test_chat(model: str):
    """测试对话接口"""
    print(f"\n=== 测试模型: {model} ===")
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "请用中文简短回答：什么是人工智能？（50字以内）"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        content = data["choices"][0]["message"]["content"]
        print(f"✅ 回复: {content}")
        
        # 显示使用信息
        usage = data.get("usage", {})
        if usage:
            print(f"   Token 使用: 输入={usage.get('prompt_tokens', 0)}, 输出={usage.get('completion_tokens', 0)}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应: {e.response.text}")
        return False


if __name__ == "__main__":
    # 只测试 gemini-2.5-flash
    test_chat("gemini-2.5-flash")

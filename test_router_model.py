# test_router_model.py
"""测试路由模型"""

from openai import OpenAI

client = OpenAI(
    api_key="sk-mv2WegerYIQ7A6P2ZXZ5G5sDIeXLTQu5cmouvGkOJXMqbA3W",
    base_url="https://aicanapi.com/v1"
)

model = "gemini-2.5-flash-lite-nothinking"

print(f"测试模型: {model}")
print("-" * 40)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "说OK"}]
    )
    print(f"✅ 成功! 响应: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ 失败: {e}")

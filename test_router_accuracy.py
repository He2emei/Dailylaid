# test_router_accuracy.py
"""测试路由模型准确率"""

from openai import OpenAI

client = OpenAI(
    api_key="sk-mv2WegerYIQ7A6P2ZXZ5G5sDIeXLTQu5cmouvGkOJXMqbA3W",
    base_url="https://aicanapi.com/v1"
)

MODEL = "gemini-2.5-flash-lite-nothinking"

# 模块描述（给路由模型看的）
MODULES = """- schedule: 日程管理：添加、查看日程安排
  (关键词: 日程, 安排, 开会, 约会, 提醒, 几点, 明天, 下周)
- inbox: 收集箱：保存暂时无法分类的内容，或查看收集箱
  (关键词: 记一下, 收集箱, 待处理)"""

# 测试用例: (用户消息, 期望路由)
TEST_CASES = [
    ("明天下午3点开会", "schedule"),
    ("今天有什么安排", "schedule"),
    ("帮我记一下：老王欠我100块", "inbox"),
    ("收集箱里有什么", "inbox"),
    ("周五10点去医院", "schedule"),
    ("下周一要交报告", "schedule"),
    ("查看我的日程", "schedule"),
    ("这个想法很有意思，先记着", "inbox"),
    ("待处理的东西有哪些", "inbox"),
    ("8点提醒我吃药", "schedule"),
]

ROUTER_PROMPT = """你是一个意图识别助手。根据用户消息，判断应该使用哪个模块处理。

可用模块：
{modules}

规则：
1. 只输出模块名称（英文），不要其他内容
2. 如果无法确定，输出 inbox

用户消息: {message}

请输出模块名称:"""


def test_routing():
    print(f"路由模型: {MODEL}")
    print(f"测试用例: {len(TEST_CASES)} 个")
    print("=" * 60)
    
    correct = 0
    total = len(TEST_CASES)
    
    for i, (message, expected) in enumerate(TEST_CASES, 1):
        prompt = ROUTER_PROMPT.format(modules=MODULES, message=message)
        
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10
            )
            result = response.choices[0].message.content.strip().lower()
            
            # 提取模块名
            if "schedule" in result:
                result = "schedule"
            elif "inbox" in result:
                result = "inbox"
            
            is_correct = result == expected
            if is_correct:
                correct += 1
                status = "✅"
            else:
                status = "❌"
            
            print(f"{i}. {status} \"{message[:25]}...\"")
            print(f"   期望: {expected}, 实际: {result}")
            
        except Exception as e:
            print(f"{i}. ❌ 错误: {e}")
    
    print("=" * 60)
    accuracy = correct / total * 100
    print(f"准确率: {correct}/{total} ({accuracy:.1f}%)")


if __name__ == "__main__":
    test_routing()

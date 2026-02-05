# test_llm_config.py
"""测试 LLM 多模型配置"""

import sys
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from core import LLMConfig


def main():
    print("=== 测试 LLM 配置系统 ===\n")
    
    # 加载配置
    config = LLMConfig("llm_config.yaml")
    
    # 显示配置信息
    print(f"提供商列表: {config.list_providers()}")
    print(f"当前提供商: {config.active_provider.name}")
    print(f"模型列表: {config.list_models()}")
    
    # 测试获取不同级别的客户端
    print("\n--- 测试各级别模型 ---")
    
    for level in ["light", "standard", "advanced"]:
        try:
            base_url, api_key, model = config.get_model(level)
            print(f"\n[{level}]")
            print(f"  模型: {model}")
            print(f"  URL: {base_url}")
            print(f"  Key: {api_key[:20]}..." if api_key else "  Key: (未配置)")
            
            # 简单测试调用
            client = config.get_client(level)
            response = client.simple_chat("1+1=? 只回答数字")
            print(f"  测试回复: {response}")
            
        except Exception as e:
            print(f"[{level}] 错误: {e}")
    
    print("\n✅ 测试完成!")


if __name__ == "__main__":
    main()

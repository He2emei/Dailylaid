# test_send.py
"""测试发送消息"""

import asyncio
import sys
sys.path.insert(0, ".")

from config import Config
from services.adapters import WebSocketAdapter


async def main():
    # 创建适配器
    adapter = WebSocketAdapter(
        ws_url=Config.NAPCAT_WS_URL,
        token=Config.NAPCAT_WS_TOKEN or None
    )
    
    print("连接中...")
    await adapter.start()
    print("已连接!")
    
    # 等待连接稳定
    await asyncio.sleep(1)
    
    # 发送群消息
    print("\n发送群消息到 638227713...")
    try:
        result = await adapter.send_message("group", 638227713, "你好！这是来自 Dailylaid 的测试消息 🎉")
        print(f"群消息发送结果: {result}")
    except Exception as e:
        print(f"群消息发送失败: {e}")
    
    # 发送私聊消息
    print("\n发送私聊消息到 1659388154...")
    try:
        result = await adapter.send_message("private", 1659388154, "你好！这是来自 Dailylaid 的私聊测试消息 👋")
        print(f"私聊消息发送结果: {result}")
    except Exception as e:
        print(f"私聊消息发送失败: {e}")
    
    # 关闭连接
    await adapter.stop()
    print("\n测试完成!")


if __name__ == "__main__":
    asyncio.run(main())

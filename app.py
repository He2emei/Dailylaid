# app.py
"""Dailylaid 主入口"""

import asyncio
import re
import sys
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, ".")

from config import Config
from core import LLMClient, DailylaidAgent
from services import DatabaseManager, ReminderService
from services.adapters import WebSocketAdapter
from utils import init_logger, get_logger


# 全局变量，用于提醒服务发送消息
_adapter = None
logger = get_logger("app")


async def send_reminder_message(user_id: str, message: str,
                                message_type: str = "private", group_id: str = None) -> str | None:
    """提醒服务的消息发送回调
    
    Returns:
        发出消息的 message_id（str），或 None（发送失败/超时）
    """
    if _adapter:
        try:
            if message_type == "group" and group_id:
                resp = await _adapter.send_message("group", int(group_id), message)
            else:
                resp = await _adapter.send_message("private", int(user_id), message)
            # 提取 message_id
            msg_id = resp.get("data", {}).get("message_id") if isinstance(resp, dict) else None
            return str(msg_id) if msg_id else None
        except TimeoutError:
            logger.warning(f"提醒消息发送超时（消息可能已发出）")
            return None
        except Exception as e:
            logger.error(f"提醒消息发送失败: {e}")
            return None
    return None


# === Phase 2: 回复消息解析工具 ===

def extract_reply_id(message_array: list) -> str | None:
    """从 message 数组中提取被回复消息的 ID"""
    if not isinstance(message_array, list):
        return None
    for seg in message_array:
        if isinstance(seg, dict) and seg.get("type") == "reply":
            reply_id = seg.get("data", {}).get("id")
            if reply_id:
                return str(reply_id)
    return None


def extract_text_from_message(message_array: list) -> str:
    """从 message 数组中提取纯文本（去除 reply/at 等 CQ 段）"""
    if not isinstance(message_array, list):
        return ""
    texts = []
    for seg in message_array:
        if isinstance(seg, dict) and seg.get("type") == "text":
            texts.append(seg.get("data", {}).get("text", ""))
    return "".join(texts).strip()


def recognize_reply_intent(text: str) -> tuple[str, dict]:
    """识别回复消息的意图
    
    Returns:
        (intent, params): intent 为 'complete'/'cancel'/'defer'/'unknown'
                          params 包含额外参数（如推迟时间）
    """
    text = text.strip()
    
    # 完成
    if text in ("完成", "完成了", "做完了", "做好了", "搞定", "done", "✅", "ok", "OK"):
        return "complete", {}
    if any(kw in text for kw in ("完成", "做完", "搞定", "done")):
        return "complete", {}
    
    # 取消
    if text in ("取消", "不做了", "算了", "cancel", "❌"):
        return "cancel", {}
    if any(kw in text for kw in ("取消", "不做了", "不用了", "算了")):
        return "cancel", {}
    
    # 推迟 — 包含时间信息，需要 LLM 解析
    if any(kw in text for kw in ("推迟", "延后", "改到", "改成", "推到", "延期")):
        return "defer", {"raw_text": text}
    
    return "unknown", {"raw_text": text}


async def handle_task_reply(db, adapter, agent, user_id: str, task: dict,
                            text: str, message_type: str, target_id: int,
                            logger) -> None:
    """处理回复消息对任务的操作
    
    Args:
        db: 数据库实例
        adapter: 网络适配器
        agent: Agent 实例
        user_id: 用户 ID
        task: 匹配到的任务
        text: 用户回复的纯文本
        message_type: 'group' 或 'private'
        target_id: 群号或用户 QQ 号
        logger: 日志
    """
    task_id = task["id"]
    title = task["title"]
    intent, params = recognize_reply_intent(text)
    
    if intent == "complete":
        success = db.complete_task(task_id)
        if success:
            reply = f"✅ 已完成：{title} 🎉"
            logger.info(f"[回复操作] 完成待办 #{task_id} {title}")
        else:
            reply = f"操作失败，任务 #{task_id} 可能已经完成或取消了"
    
    elif intent == "cancel":
        success = db.cancel_task(task_id)
        if success:
            reply = f"❌ 已取消：{title}"
            logger.info(f"[回复操作] 取消待办 #{task_id} {title}")
        else:
            reply = f"操作失败，任务 #{task_id} 可能已经完成或取消了"
    
    elif intent == "defer":
        # 推迟需要 LLM 解析时间，走 Agent 处理
        enriched_message = f"把待办任务 #{task_id}「{title}」{params['raw_text']}"
        reply = await agent.process(user_id, enriched_message,
                                    message_type=message_type,
                                    group_id=str(target_id) if message_type == "group" else None)
        logger.info(f"[回复操作] 推迟待办 #{task_id} {title}: {params['raw_text']}")
    
    else:
        # 无法识别意图，转给 Agent 处理，附带任务上下文
        enriched_message = f"用户回复了待办任务 #{task_id}「{title}」，回复内容是：{params.get('raw_text', text)}"
        reply = await agent.process(user_id, enriched_message,
                                    message_type=message_type,
                                    group_id=str(target_id) if message_type == "group" else None)
        logger.info(f"[回复操作] 未知意图，转 Agent 处理: #{task_id}")
    
    if reply:
        resp = {}
        try:
            resp = await adapter.send_message(message_type, target_id, reply)
        except TimeoutError:
            logger.warning(f"[回复操作] 发送回复超时（消息可能已发出）")
        except Exception as e:
            logger.error(f"[回复操作] 发送失败: {e}")
        # 绑定回复消息 ID
        bot_msg_id = resp.get("data", {}).get("message_id") if isinstance(resp, dict) else None
        if bot_msg_id and task["status"] == "pending":
            db.append_bound_message(task_id, str(bot_msg_id))


async def handle_command(user_id: str, message: str, db) -> str:
    """处理快捷命令（以 / 开头的消息）
    
    Args:
        user_id: 用户 ID
        message: 消息内容
        db: 数据库实例
        
    Returns:
        命令处理结果，如果不是有效命令返回 None
    """
    from tools import InboxTool, ScheduleListTool, TodoListTool
    
    cmd = message.lower().strip()
    
    # /inbox - 查看收集箱
    if cmd in ["/inbox", "/收集箱"]:
        inbox_tool = InboxTool(db)
        return inbox_tool.list_items(user_id)
    
    # /today - 今日日程
    if cmd in ["/today", "/今天", "/今日"]:
        schedule_tool = ScheduleListTool(db)
        return schedule_tool.execute(user_id, range_days=1)
    
    # /week - 本周日程
    if cmd in ["/week", "/本周"]:
        schedule_tool = ScheduleListTool(db)
        return schedule_tool.execute(user_id, range_days=7)
    
    # /todo - 查看待办
    if cmd in ["/todo", "/待办", "/任务"]:
        todo_tool = TodoListTool(db)
        return todo_tool.execute(user_id)
    
    # /help - 帮助
    if cmd in ["/help", "/帮助", "/?"]:
        return """📋 可用命令：

/inbox  - 查看收集箱
/today  - 今日日程
/week   - 本周日程
/todo   - 查看待办
/help   - 显示此帮助

也可以直接用自然语言对话，例如：
• "明天下午3点开会"
• "帮我记住下周交报告"
• "我有什么待办"
"""
    
    # 未知命令，返回 None 让 Agent 处理
    return None


async def main():
    """主函数"""
    global _adapter
    
    # 初始化日志
    init_logger(level="DEBUG", log_file="logs/dailylaid.log")
    logger = get_logger("app")
    
    logger.info("=" * 50)
    logger.info("  Dailylaid - 个人日常事务 AI Agent")
    logger.info("=" * 50)
    
    # 验证配置
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        logger.error("请检查 .env 文件配置")
        return
    
    # 初始化组件
    logger.info("初始化数据库...")
    db = DatabaseManager(Config.DATABASE_PATH)
    
    logger.info("初始化 LLM 管理器...")
    from core import LLMManager
    llm_manager = LLMManager("llm_config.yaml")
    
    logger.info("初始化 Agent...")
    agent = DailylaidAgent(llm_manager, db)
    
    # 初始化提醒服务
    logger.info("初始化提醒服务...")
    reminder_service = ReminderService(db, send_callback=send_reminder_message)
    
    # 根据配置选择网络适配器
    logger.info(f"初始化网络适配器 (模式: {Config.NAPCAT_MODE})...")
    
    if Config.NAPCAT_MODE == "ws_server":
        # WebSocket 正向连接模式
        adapter = WebSocketAdapter(
            ws_url=Config.NAPCAT_WS_URL,
            token=Config.NAPCAT_WS_TOKEN or None
        )
    else:
        logger.error(f"暂不支持的连接模式: {Config.NAPCAT_MODE}")
        logger.error("当前仅支持: ws_server (正向 WebSocket)")
        return
    
    # 设置全局 adapter 引用（供提醒服务使用）
    _adapter = adapter
    
    # 消息去重缓存 (防止 WebSocket 重复投递)
    _seen_msg_ids = set()
    _SEEN_MSG_MAX = 200
    
    # Phase 2: 待绑定队列 — 记录 BOT 刚发出的 todo 回复，等待自身消息上报来获取 message_id
    # 格式: {task_id: {"pattern": str, "timestamp": float}}
    _pending_bind = {}
    _PENDING_BIND_TTL = 30  # 30秒过期
    
    # Phase 4: 路由确认等待队列
    # 格式: {user_id: {"original_message": str, "candidates": list, "message_type": str, "group_id": str|None, "message_id": str}}
    _pending_confirmations = {}
    
    def try_bind_self_message(bot_msg_id: str, raw_text: str):
        """尝试将 BOT 自身消息的 message_id 绑定到待绑定队列中的任务"""
        now = time.time()
        expired_keys = [k for k, v in _pending_bind.items() if now - v["timestamp"] > _PENDING_BIND_TTL]
        for k in expired_keys:
            _pending_bind.pop(k, None)
        
        # 从自身消息文本中提取任务 ID
        match = re.search(r'已添加待办 #(\d+)', raw_text)
        if match:
            task_id = int(match.group(1))
            if task_id in _pending_bind:
                db.append_bound_message(task_id, bot_msg_id)
                _pending_bind.pop(task_id, None)
                logger.info(f"🔗 自身消息绑定 message_id={bot_msg_id} → 任务 #{task_id}")
                return True
            else:
                # 即使不在队列中也尝试绑定（兜底）
                task = db.get_task_by_id(task_id)
                if task and task["status"] == "pending":
                    db.append_bound_message(task_id, bot_msg_id)
                    logger.info(f"🔗 自身消息绑定（直接匹配）message_id={bot_msg_id} → 任务 #{task_id}")
                    return True
        
        return False
    
    # 注册消息处理回调
    async def on_message(data: dict):
        """处理收到的消息"""
        nonlocal _seen_msg_ids
        
        post_type = data.get("post_type")
        
        # 处理消息事件和自身消息事件 (message_sent)
        if post_type not in ("message", "message_sent"):
            return
        
        # message_sent 是 BOT 自身发出的消息（NapCat "上报自身消息" 功能）
        if post_type == "message_sent":
            bot_msg_id = str(data.get("message_id", ""))
            raw_text = data.get("raw_message", "")
            logger.info(f"🤖 收到自身消息 message_id={bot_msg_id}, 内容: {raw_text[:80]}")
            if bot_msg_id:
                try_bind_self_message(bot_msg_id, raw_text)
            return  # 不做后续处理，避免死循环
        
        # 消息去重
        msg_id = data.get("message_id")
        if msg_id in _seen_msg_ids:
            return
        _seen_msg_ids.add(msg_id)
        if len(_seen_msg_ids) > _SEEN_MSG_MAX:
            # 清理旧缓存，保留最近一半
            _seen_msg_ids = set(list(_seen_msg_ids)[-_SEEN_MSG_MAX // 2:])
        
        logger.debug(f"RAW MSG PAYLOAD: {data}")
        
        message_type = data.get("message_type")
        user_id = str(data.get("user_id", ""))
        group_id = str(data.get("group_id", "")) if data.get("group_id") else None
        message_array = data.get("message", [])
        
        raw_message = data.get("raw_message", "")
        # 如果 raw_message 为空，尝试从 message 数组提取纯文本
        if not raw_message and isinstance(message_array, list):
            texts = []
            for seg in message_array:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    texts.append(seg.get("data", {}).get("text", ""))
            raw_message = "".join(texts).strip()
            
        if not raw_message:
            return
        
        # 检查是否允许处理
        if not Config.is_allowed(user_id, group_id):
            logger.debug(f"跳过消息 (不在允许列表): [{message_type}] {user_id}")
            return
        
        logger.info(f"📩 收到消息 [{message_type}] 来自 {user_id}: {raw_message}")
        
        # === Phase 2: 回复消息拦截 ===
        reply_msg_id = extract_reply_id(message_array)
        if reply_msg_id:
            # 查找关联的任务（先查 bound_message_ids，再查 source_message_id）
            task = db.find_task_by_bound_message(reply_msg_id)
            if not task:
                task = db.find_task_by_source_message(reply_msg_id, user_id)
            
            actual_text = extract_text_from_message(message_array)
            
            # 兜底策略：如果 message_id 匹配不到，但回复文本是明确的任务操作意图，
            # 则尝试匹配用户最近的 pending 任务
            if not task:
                intent, _ = recognize_reply_intent(actual_text)
                if intent != "unknown":
                    # 用户明确表达了操作意图，尝试匹配最近的任务
                    pending_tasks = db.get_tasks(user_id)
                    if len(pending_tasks) == 1:
                        # 只有一个待办，直接匹配
                        task = pending_tasks[0]
                        logger.info(f"🔗 回复兜底匹配（唯一待办）→ #{task['id']}「{task['title']}」")
                    elif len(pending_tasks) > 1:
                        # 多个待办，选最近创建的那个
                        task = pending_tasks[0]  # 已按 deadline/created_at 排序
                        logger.info(f"🔗 回复兜底匹配（最近待办）→ #{task['id']}「{task['title']}」(共{len(pending_tasks)}个)")
                    else:
                        logger.debug(f"🔗 回复兜底：用户无 pending 任务")
            
            if task and task["user_id"] == user_id:
                logger.info(f"🔗 回复匹配到任务 #{task['id']}「{task['title']}」, 文本: {actual_text}")
                
                target_id = int(group_id) if message_type == "group" else int(user_id)
                await handle_task_reply(db, adapter, agent, user_id, task,
                                        actual_text, message_type, target_id, logger)
                return  # 已处理，不走正常路由
        
        # === Phase 4: 路由确认回复 ===
        if user_id in _pending_confirmations:
            confirm = _pending_confirmations.pop(user_id)
            choice = raw_message.strip()
            if choice in ("1", "2"):
                idx = int(choice) - 1
                chosen_module = confirm["candidates"][idx]
                logger.info(f"Phase 4: 用户选择 {choice} -> {chosen_module}")
                reply = await agent.execute_with_module(
                    user_id, confirm["original_message"], chosen_module,
                    message_type=confirm.get("message_type", "private"),
                    group_id=confirm.get("group_id"),
                    message_id=confirm.get("message_id")
                )
                # 跳到发送回复
                if reply:
                    logger.info(f"\U0001f4e4 回复: {reply}")
                    try:
                        if message_type == "group":
                            await adapter.send_message("group", data.get("group_id"), reply)
                        else:
                            await adapter.send_message("private", int(user_id), reply)
                    except TimeoutError:
                        logger.warning(f"发送消息超时（消息可能已发出）")
                    except Exception as e:
                        logger.error(f"消息发送失败: {e}")
                return
            else:
                # 用户回复的不是 1/2，丢弃确认状态，当作新消息继续处理
                logger.info(f"Phase 4: 用户回复非确认选项，丢弃确认状态，按新消息处理")
        
        # 检查是否是快捷命令（以 / 开头，绕过 LLM）
        reply = None
        if raw_message.startswith("/"):
            reply = await handle_command(user_id, raw_message, db)
        
        # 如果不是命令或命令未处理，走 Agent 流程
        if reply is None:
            result = await agent.process(user_id, raw_message,
                                        message_type=message_type,
                                        group_id=group_id,
                                        message_id=str(data.get("message_id", "")))
            
            # Phase 4: 如果返回的是确认请求（dict），存入确认队列
            if isinstance(result, dict) and result.get("type") == "confirmation":
                _pending_confirmations[user_id] = {
                    "original_message": result["original_message"],
                    "candidates": result["candidates"],
                    "message_type": message_type,
                    "group_id": group_id,
                    "message_id": str(data.get("message_id", ""))
                }
                reply = result["message"]  # 确认问题文本
                logger.info(f"Phase 4: 触发路由确认，等待用户回复")
            else:
                reply = result
        
        if reply:
            logger.info(f"📤 回复: {reply}")
            
            # Phase 2: 如果是 todo 回复，加入待绑定队列等待自身消息上报
            if "已添加待办 #" in reply:
                match = re.search(r'已添加待办 #(\d+)', reply)
                if match:
                    task_id = int(match.group(1))
                    _pending_bind[task_id] = {
                        "pattern": f"已添加待办 #{task_id}",
                        "timestamp": time.time()
                    }
                    logger.debug(f"📋 任务 #{task_id} 加入待绑定队列，等待自身消息上报")
            
            # 发送回复
            resp = {}
            try:
                if message_type == "group":
                    resp = await adapter.send_message("group", data.get("group_id"), reply)
                else:
                    resp = await adapter.send_message("private", int(user_id), reply)
            except TimeoutError:
                # send_group_msg 经常超时但消息已发出，此处不视为错误
                logger.warning(f"发送消息超时（消息可能已发出），继续处理")
            except Exception as e:
                logger.error(f"消息发送失败: {e}")
            
            # 如果 API 响应成功拿到 message_id（备用路径），也直接绑定
            bot_msg_id = resp.get("data", {}).get("message_id") if isinstance(resp, dict) else None
            if bot_msg_id and "已添加待办 #" in reply:
                match = re.search(r'已添加待办 #(\d+)', reply)
                if match:
                    task_id = int(match.group(1))
                    db.append_bound_message(task_id, str(bot_msg_id))
                    _pending_bind.pop(task_id, None)  # 已通过 API 绑定，从队列移除
                    logger.debug(f"🔗 API响应绑定 message_id={bot_msg_id} → 任务 #{task_id}")
    
    adapter.on_message(on_message)
    
    # 启动适配器
    logger.info("🚀 启动连接...")
    try:
        await adapter.start()
        
        # 启动提醒服务
        reminder_service.start()
        
        logger.info("✅ Dailylaid 已启动!")
        logger.info(f"   连接地址: {Config.NAPCAT_WS_URL}")
        logger.info("   提醒服务: 已启动 (每分钟检查)")
        logger.info("按 Ctrl+C 停止...")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️  正在停止...")
    except Exception as e:
        logger.error(f"运行出错: {e}")
    finally:
        reminder_service.stop()
        await adapter.stop()
        logger.info("👋 已停止")


if __name__ == "__main__":
    asyncio.run(main())


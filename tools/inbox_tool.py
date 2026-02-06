# tools/inbox_tool.py
"""收集箱工具"""

from datetime import datetime
from .base_tool import BaseTool
from utils import get_logger

logger = get_logger("inbox")


class InboxTool(BaseTool):
    """收集箱工具
    
    用于保存无法分类的消息，待后续处理。
    这是一个特殊的"兜底"工具，当其他工具都不适用时使用。
    """
    
    name = "inbox"
    description = """将消息保存到收集箱。
当无法确定用户消息属于哪个具体功能时使用此工具。
例如：
- 模糊的备忘
- 暂时无法分类的内容
- 需要后续处理的事项
"""
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "要保存的消息内容"
            }
        },
        "required": ["message"]
    }
    
    def execute(self, user_id: str, message: str = "", **params) -> str:
        """保存消息到收集箱"""
        if not message:
            return "消息内容为空，未保存。"
        
        if self.db:
            record_id = self.db.add_to_inbox(user_id, message)
            logger.info(f"用户 {user_id} 保存消息到收集箱 (ID: {record_id})")
            return f"📥 已记录到收集箱\n\n发送 /inbox 查看收集箱内容"
        else:
            logger.warning("数据库未初始化，无法保存到收集箱")
            return "⚠️ 数据库未初始化，无法保存。"
    
    def list_items(self, user_id: str, limit: int = 10) -> str:
        """获取收集箱内容列表"""
        if not self.db:
            return "数据库未初始化"
        
        items = self.db.get_inbox(user_id, limit)
        if not items:
            return "📭 收集箱是空的"
        
        result = f"📥 收集箱 ({len(items)} 条未处理)\n\n"
        for i, item in enumerate(items, 1):
            # 截断过长消息
            msg = item['raw_message']
            if len(msg) > 40:
                msg = msg[:40] + "..."
            
            # 格式化时间
            created = item.get('created_at', '')
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    time_str = dt.strftime("%m/%d %H:%M")
                except:
                    time_str = ""
            else:
                time_str = ""
            
            result += f"{i}. [{time_str}] {msg}\n"
        
        return result.strip()
    
    def archive_item(self, user_id: str, item_id: int) -> str:
        """归档（标记已处理）收集箱条目"""
        if not self.db:
            return "数据库未初始化"
        
        # TODO: 实现归档逻辑
        # self.db.archive_inbox_item(item_id)
        return f"✅ 已归档条目 #{item_id}"


class InboxListTool(BaseTool):
    """查看收集箱工具 - 供 LLM 调用"""
    
    name = "inbox_list"
    description = """查看收集箱内容。
当用户想查看收集箱、待处理事项时使用。
例如：
- "看看收集箱"
- "有什么待处理的"
- "收集箱里有什么"
"""
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "显示条数，默认10条"
            }
        },
        "required": []
    }
    
    def execute(self, user_id: str, limit: int = 10, **params) -> str:
        """查看收集箱"""
        if not self.db:
            return "数据库未初始化"
        
        items = self.db.get_inbox(user_id, limit)
        if not items:
            return "📭 收集箱是空的"
        
        result = f"📥 收集箱 ({len(items)} 条)\n\n"
        for i, item in enumerate(items, 1):
            msg = item['raw_message']
            if len(msg) > 40:
                msg = msg[:40] + "..."
            
            created = item.get('created_at', '')
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    time_str = dt.strftime("%m/%d %H:%M")
                except:
                    time_str = ""
            else:
                time_str = ""
            
            result += f"{i}. [{time_str}] {msg}\n"
        
        return result.strip()


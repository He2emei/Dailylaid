# tools/inbox_tool.py
"""收集箱工具"""

from .base_tool import BaseTool
from utils import get_logger

logger = get_logger("inbox")


class InboxTool(BaseTool):
    """收集箱工具
    
    用于保存无法分类的消息，待后续处理。
    """
    
    name = "inbox"
    description = "将消息保存到收集箱，用于暂存无法分类或需要后续处理的内容"
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
            return f"✅ 已保存到收集箱 (ID: {record_id})"
        else:
            logger.warning("数据库未初始化，无法保存到收集箱")
            return "⚠️ 数据库未初始化，无法保存。"
    
    def get_items(self, user_id: str, limit: int = 10) -> str:
        """获取收集箱内容"""
        if not self.db:
            return "数据库未初始化"
        
        items = self.db.get_inbox(user_id, limit)
        if not items:
            return "📭 收集箱是空的"
        
        result = "📥 收集箱内容:\n"
        for i, item in enumerate(items, 1):
            result += f"{i}. {item['raw_message'][:50]}...\n"
        
        return result

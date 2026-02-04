# tools/base_tool.py
"""工具基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseTool(ABC):
    """工具基类
    
    所有工具都需要继承此类，并实现 execute 方法。
    """
    
    # 工具名称
    name: str = "base_tool"
    
    # 工具描述（用于 LLM 理解工具用途）
    description: str = "基础工具"
    
    # 工具参数定义（OpenAI Function Calling 格式）
    parameters: Dict = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, db=None):
        """初始化工具
        
        Args:
            db: 数据库管理器实例
        """
        self.db = db
    
    @abstractmethod
    def execute(self, user_id: str, **params) -> str:
        """执行工具
        
        Args:
            user_id: 用户 ID (QQ号)
            **params: 工具参数
            
        Returns:
            执行结果文本
        """
        pass
    
    def to_openai_tool(self) -> Dict:
        """转换为 OpenAI Tool 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> BaseTool:
        """获取工具"""
        return self._tools.get(name)
    
    def all(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def to_openai_tools(self) -> List[Dict]:
        """转换为 OpenAI Tools 列表"""
        return [tool.to_openai_tool() for tool in self._tools.values()]

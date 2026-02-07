# tools/modules.py
"""工具模块注册系统

两层模型架构：
- 第一层 (Router): 根据用户消息选择模块
- 第二层 (Executor): 在选定模块内调用具体工具
"""

from typing import Dict, List, Type
from .base_tool import BaseTool

from utils import get_logger

logger = get_logger("modules")


class ToolModule:
    """工具模块
    
    将相关工具组织在一起，便于路由层选择。
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        tools: List[Type[BaseTool]],
        keywords: List[str] = None
    ):
        """
        Args:
            name: 模块名称（英文标识）
            description: 模块描述（给第一层路由看）
            tools: 该模块包含的工具类列表
            keywords: 帮助路由识别的关键词
        """
        self.name = name
        self.description = description
        self.tool_classes = tools
        self.keywords = keywords or []
        self._tools: Dict[str, BaseTool] = {}
    
    def init_tools(self, db):
        """初始化所有工具实例"""
        for tool_cls in self.tool_classes:
            tool = tool_cls(db)
            self._tools[tool.name] = tool
        logger.debug(f"模块 {self.name} 初始化完成: {list(self._tools.keys())}")
    
    def get_tools(self) -> List[BaseTool]:
        """获取所有工具实例"""
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> BaseTool:
        """获取指定工具"""
        return self._tools.get(name)
    
    def to_openai_tools(self) -> List[Dict]:
        """转换为 OpenAI Tools 列表"""
        return [tool.to_openai_tool() for tool in self._tools.values()]


class ModuleRegistry:
    """模块注册表"""
    
    def __init__(self):
        self._modules: Dict[str, ToolModule] = {}
        self._fallback_module: str = "inbox"  # 兜底模块
    
    def register(self, module: ToolModule):
        """注册模块"""
        self._modules[module.name] = module
        logger.debug(f"注册模块: {module.name}")
    
    def get(self, name: str) -> ToolModule:
        """获取模块"""
        return self._modules.get(name)
    
    def get_fallback(self) -> ToolModule:
        """获取兜底模块"""
        return self._modules.get(self._fallback_module)
    
    def all(self) -> List[ToolModule]:
        """获取所有模块"""
        return list(self._modules.values())
    
    def all_names(self) -> List[str]:
        """获取所有模块名称"""
        return list(self._modules.keys())
    
    def init_all_tools(self, db):
        """初始化所有模块的工具"""
        for module in self._modules.values():
            module.init_tools(db)
    
    def build_router_prompt(self) -> str:
        """构建第一层路由的 prompt"""
        lines = []
        for module in self._modules.values():
            keywords = ", ".join(module.keywords) if module.keywords else ""
            lines.append(f"- {module.name}: {module.description}")
            if keywords:
                lines.append(f"  (关键词: {keywords})")
        return "\n".join(lines)
    
    def get_tool_by_name(self, tool_name: str) -> BaseTool:
        """跨模块获取工具"""
        for module in self._modules.values():
            tool = module.get_tool(tool_name)
            if tool:
                return tool
        return None

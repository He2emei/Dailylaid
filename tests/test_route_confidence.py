# tests/test_route_confidence.py
"""Phase 4: 路由置信度 + 确认机制 单元测试"""

import pytest
import asyncio
import os
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
#  _parse_route_json 测试
# ============================================================

class TestParseRouteJson:
    """测试 JSON 路由解析"""
    
    @pytest.fixture
    def agent(self):
        """创建一个 mock Agent 用于测试 _parse_route_json"""
        from core.agent import DailylaidAgent
        # 不真正初始化 Agent，只需要 _parse_route_json 方法
        # 使用 object.__new__ 跳过 __init__
        a = object.__new__(DailylaidAgent)
        # 设置 modules mock（_parse_route_json 需要 all_names()）
        a.modules = MagicMock()
        a.modules.all_names.return_value = ["schedule", "todo", "timeline", "inbox"]
        return a
    
    def test_valid_json_high_confidence(self, agent):
        """解析正确的 JSON，高置信度"""
        content = '{"module": "schedule", "confidence": 0.95}'
        module, conf = agent._parse_route_json(content)
        assert module == "schedule"
        assert conf == 0.95
    
    def test_valid_json_low_confidence(self, agent):
        """解析正确的 JSON，低置信度"""
        content = '{"module": "todo", "confidence": 0.6}'
        module, conf = agent._parse_route_json(content)
        assert module == "todo"
        assert conf == 0.6
    
    def test_json_with_markdown_wrapper(self, agent):
        """处理 markdown 代码块包裹的 JSON"""
        content = '```json\n{"module": "schedule", "confidence": 0.9}\n```'
        module, conf = agent._parse_route_json(content)
        assert module == "schedule"
        assert conf == 0.9
    
    def test_invalid_json_returns_none(self, agent):
        """非 JSON 文本应返回 (None, 1.0)"""
        content = "schedule"
        module, conf = agent._parse_route_json(content)
        assert module is None
        assert conf == 1.0
    
    def test_invalid_module_returns_none(self, agent):
        """JSON 有效但模块名无效"""
        content = '{"module": "unknown_module", "confidence": 0.9}'
        module, conf = agent._parse_route_json(content)
        assert module is None
    
    def test_confidence_clamped(self, agent):
        """置信度应被限制在 [0, 1]"""
        content = '{"module": "todo", "confidence": 1.5}'
        module, conf = agent._parse_route_json(content)
        assert conf == 1.0
        
        content = '{"module": "todo", "confidence": -0.3}'
        module, conf = agent._parse_route_json(content)
        assert conf == 0.0
    
    def test_missing_confidence_defaults_to_1(self, agent):
        """缺少 confidence 字段时默认 1.0"""
        content = '{"module": "schedule"}'
        module, conf = agent._parse_route_json(content)
        assert module == "schedule"
        assert conf == 1.0


# ============================================================
#  _build_confirmation 测试
# ============================================================

class TestBuildConfirmation:
    """测试确认消息生成"""
    
    @pytest.fixture
    def agent(self):
        a = object.__new__(_import_agent_class())
        return a
    
    def test_confirmation_structure(self, agent):
        """确认返回值结构完整"""
        result = agent._build_confirmation("周五去健身房", "schedule", 0.6)
        assert result["type"] == "confirmation"
        assert "message" in result
        assert "original_message" in result
        assert "candidates" in result
        assert len(result["candidates"]) == 2
    
    def test_schedule_first_when_suggested(self, agent):
        """建议为 schedule 时，schedule 排第一"""
        result = agent._build_confirmation("test", "schedule", 0.6)
        assert result["candidates"][0] == "schedule"
        assert result["candidates"][1] == "todo"
    
    def test_todo_first_when_suggested(self, agent):
        """建议为 todo 时，todo 排第一"""
        result = agent._build_confirmation("test", "todo", 0.6)
        assert result["candidates"][0] == "todo"
        assert result["candidates"][1] == "schedule"
    
    def test_message_contains_options(self, agent):
        """确认消息包含选项"""
        result = agent._build_confirmation("周五去健身房", "schedule", 0.6)
        msg = result["message"]
        assert "1" in msg
        assert "2" in msg
        assert "日程" in msg
        assert "待办" in msg


# ============================================================
#  process() 置信度阈值测试
# ============================================================

class TestProcessConfidence:
    """测试 process() 的置信度分支"""
    
    @pytest.fixture
    def agent(self):
        """创建带 mock 依赖的 Agent"""
        a = object.__new__(_import_agent_class())
        a.modules = MagicMock()
        a.modules.all_names.return_value = ["schedule", "todo", "timeline", "inbox"]
        a.modules.get.return_value = MagicMock()
        a.modules.get_fallback.return_value = MagicMock()
        a.inbox_tool = MagicMock()
        return a
    
    def test_high_confidence_no_confirmation(self, agent):
        """高置信度不触发确认"""
        agent._route = AsyncMock(return_value=("schedule", 0.95))
        agent._execute = AsyncMock(return_value="已添加日程")
        
        result = asyncio.get_event_loop().run_until_complete(
            agent.process("user1", "明天十点开会")
        )
        assert isinstance(result, str)
        assert result == "已添加日程"
    
    def test_low_confidence_triggers_confirmation(self, agent):
        """低置信度触发确认"""
        agent._route = AsyncMock(return_value=("schedule", 0.6))
        
        result = asyncio.get_event_loop().run_until_complete(
            agent.process("user1", "周五去健身房")
        )
        assert isinstance(result, dict)
        assert result["type"] == "confirmation"
    
    def test_low_confidence_non_confirmable_no_confirmation(self, agent):
        """低置信度但非可确认模块（timeline/inbox），不触发确认"""
        agent._route = AsyncMock(return_value=("timeline", 0.5))
        agent._execute = AsyncMock(return_value="时间线记录")
        
        result = asyncio.get_event_loop().run_until_complete(
            agent.process("user1", "刚才做了什么")
        )
        assert isinstance(result, str)


# ============================================================
#  辅助函数
# ============================================================

def _import_agent_class():
    from core.agent import DailylaidAgent
    return DailylaidAgent

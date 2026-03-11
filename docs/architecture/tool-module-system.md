# 工具与模块注册系统

本文档详解 Dailylaid 的工具抽象层和模块注册系统设计，以及如何新增自定义工具和模块。

---

## 📐 设计概述

工具系统分为三层：

```
ModuleRegistry              ← 管理所有模块
  └── ToolModule (×N)       ← 将相关工具组织在一起，给 Router 选择
       └── BaseTool (×N)    ← 单个工具，对接 OpenAI Function Calling
```

**核心理念**：工具是原子操作单元，模块是工具的逻辑分组。Router 在模块级别路由，Executor 在工具级别调用。

---

## BaseTool 工具基类

位于 `tools/base_tool.py`。

### 类定义

```python
class BaseTool(ABC):
    name: str = "base_tool"          # 工具名（必须唯一）
    description: str = "基础工具"     # 工具描述（给 LLM 看）
    parameters: Dict = {              # 参数定义（OpenAI Function 格式）
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, db=None):
        self.db = db                  # 数据库实例注入
    
    @abstractmethod
    def execute(self, user_id: str, **params) -> str:
        """执行工具，返回文本结果"""
        pass
    
    def to_openai_tool(self) -> Dict:
        """转为 OpenAI Tool 定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
```

### 设计要点

| 特性 | 说明 |
|------|------|
| **类级别属性** | `name`, `description`, `parameters` 定义在类上而非实例 |
| **统一签名** | `execute(user_id, **params)` → 所有工具入口一致 |
| **返回纯文本** | 工具只返回 `str`，由 Agent 直接发给用户 |
| **DB 注入** | 通过构造函数注入而非全局访问 |

---

## 已有工具清单

### schedule 模块

#### ScheduleTool

| 属性 | 值 |
|------|-----|
| name | `schedule` |
| 功能 | 添加日程 |
| 必填参数 | `title` (str), `start_time` (str, "YYYY-MM-DD HH:MM") |
| 可选参数 | `location` (str), `reminders` (int[], 单位分钟) |
| 返回示例 | `✅ 已添加日程\n📅 开会\n⏰ 03月12日 15:00\n🔔 提前 30 分钟提醒` |

#### ScheduleListTool

| 属性 | 值 |
|------|-----|
| name | `schedule_list` |
| 功能 | 查询日程 |
| 可选参数 | `range_days` (int, 默认7) |
| 返回示例 | `📅 未来 7 天的日程：\n• 03/12 15:00 开会` |

---

### timeline 模块

#### TimelineRecordTool

| 属性 | 值 |
|------|-----|
| name | `timeline_record` |
| 功能 | 记录已完成的活动 |
| 必填参数 | `name` (str), `start_time` (str) |
| 可选参数 | `end_time` (str), `description` (str), `category` (str), `location` (str) |
| 特殊逻辑 | 自动检测时间重叠并在回复中提醒 |

#### TimelineUpdateTool

| 属性 | 值 |
|------|-----|
| name | `timeline_update` |
| 功能 | 更新已有活动（主要是补充结束时间） |
| 必填参数 | `activity_id` (int) |
| 可选参数 | `end_time` (str), `description` (str), `add_message` (str) |
| 权限验证 | 检查 `activity.user_id == user_id` |

#### TimelineListTool

| 属性 | 值 |
|------|-----|
| name | `timeline_list` |
| 功能 | 查看活动记录列表（文本） |
| 可选参数 | `hours` (int, 默认24), `date` (str, "YYYY-MM-DD") |

#### TimelineViewTool

| 属性 | 值 |
|------|-----|
| name | `timeline_view` |
| 功能 | 生成可视化时间线图片 |
| 可选参数 | `date` (str), `style` (str: glass/neon/skeletal) |
| 状态 | ⚠️ TODO：图片生成未实现，当前返回文本列表 |

---

### inbox 模块

#### InboxTool

| 属性 | 值 |
|------|-----|
| name | `inbox` |
| 功能 | 保存消息到收集箱（兜底） |
| 必填参数 | `message` (str) |
| 额外方法 | `list_items()`, `archive_item()` (TODO) |

#### InboxListTool

| 属性 | 值 |
|------|-----|
| name | `inbox_list` |
| 功能 | 查看收集箱内容 |
| 可选参数 | `limit` (int, 默认10) |

---

## ToolModule 工具模块

位于 `tools/modules.py`。

### 类定义

```python
class ToolModule:
    def __init__(self, name, description, tools, keywords=None):
        self.name = name                   # 模块英文标识
        self.description = description     # 给 Router Prompt 用的描述
        self.tool_classes = tools          # 该模块包含的工具类列表
        self.keywords = keywords or []     # 辅助路由的关键词
        self._tools = {}                   # 初始化后的工具实例
    
    def init_tools(self, db):
        """将工具类实例化并注入 db"""
        for tool_cls in self.tool_classes:
            tool = tool_cls(db)
            self._tools[tool.name] = tool
    
    def to_openai_tools(self):
        """返回该模块所有工具的 OpenAI 格式定义列表"""
```

### 当前模块注册

在 `core/agent.py` 的 `_register_modules()` 中：

```python
# 日程模块
self.modules.register(ToolModule(
    name="schedule",
    description="日程管理：添加、查看日程安排",
    tools=[ScheduleTool, ScheduleListTool],
    keywords=["日程", "安排", "开会", "约会", "提醒", "几点", "明天", "下周"]
))

# 时间线模块
self.modules.register(ToolModule(
    name="timeline",
    description="时间线活动记录：记录**已完成**的活动...",
    tools=[TimelineRecordTool, TimelineUpdateTool, TimelineListTool, TimelineViewTool],
    keywords=["记录", "时间线", "刚才", "完成了", "干了", ...]
))

# 收集箱模块（兜底）
self.modules.register(ToolModule(
    name="inbox",
    description="收集箱：保存暂时无法分类的内容",
    tools=[InboxTool, InboxListTool],
    keywords=["记一下", "收集箱", "待处理"]
))
```

---

## ModuleRegistry 模块注册表

管理所有模块的中心注册表。

### 核心方法

```python
class ModuleRegistry:
    def register(module)           # 注册模块
    def get(name) -> ToolModule    # 按名称获取模块
    def get_fallback()             # 获取兜底模块（inbox）
    def all_names() -> [str]       # 所有模块名称列表
    def init_all_tools(db)         # 批量初始化所有模块的工具
    def build_router_prompt()      # 构建 Router 的模块描述文本
    def get_tool_by_name(name)     # 跨模块按名称查找工具
```

### `build_router_prompt()` 输出示例

```
- schedule: 日程管理：添加、查看日程安排
  (关键词: 日程, 安排, 开会, 约会, 提醒, 几点, 明天, 下周)
- timeline: 时间线活动记录：记录**已完成**的活动...
  (关键词: 记录, 时间线, 刚才, 完成了, 干了, 做了, ...)
- inbox: 收集箱：保存暂时无法分类的内容
  (关键词: 记一下, 收集箱, 待处理)
```

---

## 🔧 新增工具完整教程

以新增 **人情追踪（FavorTool）** 为例：

### 第 1 步：创建工具文件

```python
# tools/favor_tool.py

from .base_tool import BaseTool
from utils import get_logger

logger = get_logger("favor_tool")


class FavorAddTool(BaseTool):
    """添加人情记录"""
    
    name = "favor_add"
    description = """记录人情。当用户提到谁帮了自己、或自己帮了谁时使用。
    例如：
    - "昨天小王帮我搬家了"
    - "我帮同事修了电脑"
    """
    
    parameters = {
        "type": "object",
        "properties": {
            "person": {
                "type": "string",
                "description": "对方名称"
            },
            "event": {
                "type": "string",
                "description": "事件描述"
            },
            "direction": {
                "type": "string",
                "enum": ["given", "received"],
                "description": "方向：given(我帮别人) / received(别人帮我)"
            },
            "date": {
                "type": "string",
                "description": "日期 YYYY-MM-DD（可选）"
            }
        },
        "required": ["person", "event", "direction"]
    }
    
    def execute(self, user_id: str, **params) -> str:
        person = params.get("person")
        event = params.get("event")
        direction = params.get("direction")
        date = params.get("date")
        
        self.db.add_favor(user_id, person, event, direction, date)
        
        direction_text = "别人帮你" if direction == "received" else "你帮别人"
        return f"✅ 已记录人情\n\n👤 {person}\n📝 {event}\n↔️ {direction_text}"
```

### 第 2 步：导出工具类

```python
# tools/__init__.py 中添加
from .favor_tool import FavorAddTool, FavorListTool
```

### 第 3 步：注册模块

```python
# core/agent.py 的 _register_modules() 中添加
from tools import FavorAddTool, FavorListTool

self.modules.register(ToolModule(
    name="favor",
    description="人情追踪：记录谁帮了你、你帮了谁",
    tools=[FavorAddTool, FavorListTool],
    keywords=["人情", "帮忙", "帮过", "还人情"]
))
```

### 第 4 步：配置模型（可选）

```yaml
# llm_config.yaml 的 usage 中添加
usage:
  favor: standard
```

### 第 5 步：更新 Router Prompt（自动）

无需手动操作。`ModuleRegistry.build_router_prompt()` 会自动包含新注册的模块。

---

## MCP 工具服务器

`mcp_server/` 提供了另一种工具暴露方式——MCP (Model Context Protocol)，允许外部 AI Agent（如 Cursor、Cline 等）通过标准协议调用 Dailylaid 的工具。

### 架构

```
外部 AI Agent (如 Cursor)
    │
    ▼ MCP Protocol
┌──────────────────┐
│  FastMCP Server  │
│  mcp_server/     │
│  ├── server.py   │  ← 注册工具
│  └── tools/      │
│      └── schedule_tool.py  ← 日程 CRUD + 重复日程
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  DatabaseManager │  ← 直接操作数据库
└──────────────────┘
```

### MCP 日程工具

| 工具名 | 功能 | 备注 |
|--------|------|------|
| `schedule_add` | 添加日程 | 支持重复规则 |
| `schedule_list` | 列出日程 | 支持展开重复日程实例 |
| `schedule_today` | 今日日程 | `schedule_list` 的快捷调用 |
| `schedule_update` | 更新日程 | 支持部分字段更新 |
| `schedule_delete` | 删除日程 | — |

> [!NOTE]
> MCP 工具与 Agent 内部工具的区别：MCP 工具直接操作数据库，不经过 LLM 处理。
> 它们面向外部 AI Agent，提供结构化输入输出。

---

*最后更新: 2026-03-11*

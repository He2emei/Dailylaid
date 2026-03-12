# Skills 在 Dailylaid 中的适配方案

> 📚 本文档面向具体实施的 Agent，规划如何将 Skills 架构引入 Dailylaid 项目。

---

## 1. 现状分析

### 1.1 当前架构

```
用户消息
  │
  ▼
_route() ← 第一层: 轻量 LLM 路由（ROUTER_PROMPT）
  │         输入: 模块清单 + 用户消息
  │         输出: 模块名（schedule / timeline / inbox）
  ▼
_execute() ← 第二层: 标准 LLM + Function Calling（EXECUTOR_PROMPT）
  │          输入: 4行通用 System Prompt + 模块工具列表
  │          输出: tool_calls 或文本回复
  ▼
_handle_tool_calls() ← 执行工具，返回结果
```

### 1.2 核心问题

**第二层 EXECUTOR_PROMPT 太弱**：

```python
# 现有 — 仅 4 行，没有任何模块特定的操作指导
EXECUTOR_PROMPT = """你是 Dailylaid，一个个人日常事务管理助手。

当前模块: {module_name}
当前日期: {today}
当前时间: {current_time}

请根据用户消息调用合适的工具。如果不确定如何处理，使用 inbox 工具保存。

回复时请简洁友好，使用中文。
"""
```

**问题表现**：
1. LLM 不知道当前模块的具体规则（如 schedule 的提醒默认值策略）
2. LLM 不知道工具之间的协作方式（如 timeline 的"先查未结束记录 → 再补充结束时间"）
3. 不同模块共用同一个 prompt，无法做模块级定制
4. timeline 的上下文注入是硬编码在 `agent.py` 中的 if-else，不可扩展

### 1.3 已有优势

| 已有 | 说明 |
|------|------|
| 两层路由架构 | 第一层 Router 工作良好，可复用 |
| BaseTool 基类 | 工具定义规范，支持 OpenAI Function Calling |
| ToolModule 模块系统 | 已有 name/description/keywords/tools 分组 |
| LLMManager 多模型管理 | 支持按用途选择模型和故障切换 |
| ModuleRegistry | 模块注册和查找机制 |

---

## 2. 适配方案：渐进式改造

> [!IMPORTANT]
> 核心策略：**不是推翻重来，而是渐进式增强**。保留已有的 Router + ToolModule 框架，用 SKILL.md 文件替代硬编码的 EXECUTOR_PROMPT。

### 2.1 改造全景图

```
改造前：                              改造后：
                                     
agent.py                             agent.py
├── ROUTER_PROMPT (硬编码)            ├── ROUTER_PROMPT (硬编码，保留)
├── EXECUTOR_PROMPT (4行通用)          ├── SkillEngine (从文件系统加载)
├── _register_modules() (硬编码)      ├── _register_modules() → 自动发现
├── _execute() (通用逻辑)             ├── _execute() (注入 Skill 指令)  
└── _handle_tool_calls() (单轮)       └── _agent_loop() (支持多轮)
                                     
tools/                               skills/
├── base_tool.py                     ├── schedule/
├── modules.py                       │   ├── SKILL.md     ← 模块级 SOP
├── schedule_tool.py                 │   └── references/
├── timeline_tool.py                 ├── timeline/
└── inbox_tool.py                    │   ├── SKILL.md
                                     │   └── references/
                                     └── inbox/
                                         └── SKILL.md
                                     
                                     tools/ (保留不变)
                                     ├── base_tool.py
                                     ├── modules.py
                                     ├── schedule_tool.py
                                     ├── timeline_tool.py
                                     └── inbox_tool.py
```

### 2.2 改造分三个阶段

---

## 阶段 1：创建 SKILL.md 文件（纯增量，零风险）

**目标**：为每个现有模块编写 SKILL.md，但暂不改代码。

### 步骤

1. 创建 `skills/` 目录

```
Dailylaid_Dev/
├── skills/
│   ├── schedule/
│   │   └── SKILL.md
│   ├── timeline/
│   │   └── SKILL.md
│   └── inbox/
│       └── SKILL.md
├── tools/  (不变)
├── core/   (不变)
└── ...
```

2. 编写每个 SKILL.md

**schedule/SKILL.md**：
```markdown
---
name: schedule
description: 管理未来的日程安排。当用户提到"明天"、"安排"、"提醒我"、"开会"、"几点"、"下周"等与未来计划相关的内容时使用。
---

# 日程管理

## 角色
你是日程管理助手，负责帮用户创建和查询未来的日程安排。

## 规则
1. 以当前时间为基准推算相对时间（如"3分钟后"、"半小时后"）
2. start_time 格式必须为 YYYY-MM-DD HH:MM
3. 如果用户只说了"明天开会"没给时间，合理推断（如默认上午9:00）
4. 不确定的内容用 inbox 工具保存

## 可用工具
- schedule — 添加日程（必须：title, start_time；可选：location, reminders）
- schedule_list — 查询未来日程（可选：range_days 默认7天）
- inbox — 兜底，无法处理时保存到收集箱

## 提醒策略
- 用户明确说了提醒时间 → 使用用户指定的值
- 距现在超过 60 分钟 → reminders: [30]（提前30分钟）
- 距现在 60 分钟以内 → reminders: [0]（到时立刻提醒）

## 输出格式
添加成功时简洁回复，包含 ✅📅⏰📍🔔 等 emoji。
查询时列出所有日程，按时间排序。
```

**timeline/SKILL.md**：
```markdown
---
name: timeline
description: 记录和查看已完成的活动。当用户使用过去时态描述活动（如"刚才"、"完成了"、"干了"、"做了"、"起床"、"吃完"）时使用。
---

# 时间线活动记录

## 角色
你是活动记录助手，帮用户追踪已完成的活动并生成时间线。

## 规则
1. 只记录**已发生/正在发生**的活动，不记录未来计划（那是 schedule 的职责）
2. 时间格式为 YYYY-MM-DDTHH:MM:SS
3. **智能补充结束时间**：如果用户说"做完了"、"结束了"，检查最近未结束的活动进行补充

## 可用工具
- timeline_record — 记录新活动（必须：name, start_time, category）
- timeline_update — 更新活动（用于补充结束时间等）
- timeline_list — 查看时间线
- timeline_view — 查看某天的时间线可视化
- inbox — 兜底

## 上下文注入
执行前会注入**最近24小时的活动记录**。利用这些信息：
- 判断新活动的开始时间（上一个活动结束 = 新活动开始）
- 识别未结束的活动并补充 end_time

## 输出格式
- 记录成功：✅ 已记录 [活动名称]
- 更新成功：✅ 已更新 [活动名称]
- 查询时按时间线格式展示
```

**inbox/SKILL.md**：
```markdown
---
name: inbox
description: 收集箱，保存暂时无法分类的内容，或查看/管理收集箱。当消息不属于日程或时间线时使用。
---

# 收集箱

## 角色
你是信息收集助手，将用户的碎片化想法、待办、随记保存到收集箱。

## 规则
1. 保存原始内容，不要过度加工
2. 自动推断优先级（high/medium/low）
3. 用户说"帮我记一下"、"待处理"等也应保存

## 可用工具
- inbox — 保存到收集箱（必须：message；需自动推断 priority）
- inbox_list — 查看收集箱内容

## 输出格式
- 保存成功：📥 已保存到收集箱
- 列出时按优先级分组展示
```

---

## 阶段 2：引入 SkillEngine，替换硬编码 Prompt

**目标**：在 `core/` 中实现 SkillEngine，替代硬编码的 `EXECUTOR_PROMPT`。

### 2.1 新增文件

#### `core/skill_engine.py`

```python
"""Skill 引擎 — 从文件系统加载模块级 SOP"""

import os
import re
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from utils import get_logger

logger = get_logger("skill_engine")

@dataclass
class SkillMeta:
    name: str
    description: str
    path: str

@dataclass  
class SkillContent:
    meta: SkillMeta
    instructions: str  # SKILL.md 正文
    references: Dict[str, str] = field(default_factory=dict)

class SkillEngine:
    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self._index: Dict[str, SkillMeta] = {}
        self._cache: Dict[str, SkillContent] = {}
    
    def discover(self) -> List[SkillMeta]:
        """扫描 skills/ 目录，建立索引"""
        if not os.path.exists(self.skills_dir):
            logger.warning(f"Skills 目录不存在: {self.skills_dir}")
            return []
        
        for entry in os.listdir(self.skills_dir):
            skill_dir = os.path.join(self.skills_dir, entry)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            
            if os.path.isdir(skill_dir) and os.path.exists(skill_md):
                try:
                    fm = self._parse_frontmatter(skill_md)
                    meta = SkillMeta(
                        name=fm.get("name", entry),
                        description=fm.get("description", ""),
                        path=skill_dir
                    )
                    self._index[meta.name] = meta
                    logger.info(f"发现 Skill: {meta.name}")
                except Exception as e:
                    logger.error(f"解析 Skill 失败 [{entry}]: {e}")
        
        return list(self._index.values())
    
    def get_instructions(self, skill_name: str) -> Optional[str]:
        """获取 Skill 的正文指令（激活阶段）"""
        if skill_name in self._cache:
            return self._cache[skill_name].instructions
        
        meta = self._index.get(skill_name)
        if not meta:
            return None
        
        skill_md = os.path.join(meta.path, "SKILL.md")
        content = self._read_file(skill_md)
        _, instructions = self._split_frontmatter(content)
        
        self._cache[skill_name] = SkillContent(
            meta=meta, instructions=instructions
        )
        return instructions
    
    def load_reference(self, skill_name: str, ref_name: str) -> Optional[str]:
        """按需加载参考文件"""
        meta = self._index.get(skill_name)
        if not meta:
            return None
        
        ref_path = os.path.join(meta.path, "references", ref_name)
        if os.path.exists(ref_path):
            return self._read_file(ref_path)
        return None
    
    def build_skills_list(self) -> str:
        """构建路由用的技能清单"""
        lines = []
        for meta in self._index.values():
            lines.append(f"- {meta.name}: {meta.description}")
        return "\n".join(lines)
    
    # --- 内部方法 ---
    
    @staticmethod
    def _parse_frontmatter(filepath: str) -> dict:
        content = SkillEngine._read_file(filepath)
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1)) or {}
        return {}
    
    @staticmethod
    def _split_frontmatter(content: str) -> tuple:
        match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', content, re.DOTALL)
        if match:
            return {}, match.group(1).strip()
        return {}, content.strip()
    
    @staticmethod
    def _read_file(filepath: str) -> str:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
```

### 2.2 修改 `core/agent.py`

核心变更：

```python
# === 改造前 ===
EXECUTOR_PROMPT = """你是 Dailylaid，一个个人日常事务管理助手。
当前模块: {module_name}
..."""

# === 改造后 ===
EXECUTOR_BASE = """你是 Dailylaid，一个个人日常事务管理助手。
当前日期: {today}
当前时间: {current_time}

{skill_instructions}
"""
```

在 `_execute()` 方法中：

```python
async def _execute(self, user_id, message, module, ...):
    # 从 SkillEngine 获取模块指令（而非硬编码 prompt）
    skill_instructions = self.skill_engine.get_instructions(module.name)
    
    if not skill_instructions:
        # 兜底：如果没找到 SKILL.md，用默认通用指令
        skill_instructions = "请根据用户消息调用合适的工具。如果不确定，使用 inbox 工具保存。"
    
    system_prompt = EXECUTOR_BASE.format(
        today=today,
        current_time=current_time,
        skill_instructions=skill_instructions
    )
    
    # 上下文注入（通用化）
    context = self._get_context(module.name, user_id)
    if context:
        system_prompt += f"\n\n{context}"
    
    # ... 后续逻辑不变 ...
```

### 2.3 上下文注入通用化

将 timeline 的硬编码上下文注入改为可扩展的机制：

```python
def _get_context(self, skill_name: str, user_id: str) -> str:
    """获取模块级运行时上下文"""
    if skill_name == "timeline":
        activities = self.db.get_activities_recent(user_id, hours=24)
        if activities:
            lines = ["**最近24小时的活动记录**（用于智能补充结束时间）："]
            for act in activities:
                if act['end_time']:
                    lines.append(f"- ID{act['id']}: {act['name']} ({act['start_time']} → {act['end_time']})")
                else:
                    lines.append(f"- ID{act['id']}: {act['name']} ({act['start_time']} → 未结束) ← 可补充")
            return "\n".join(lines)
    
    return ""
```

> [!TIP]
> 未来可以将上下文提供逻辑也外部化（如 SKILL.md 中声明 `context_provider: recent_activities`，由引擎自动调用对应函数）。但初期阶段硬编码即可，不必过度工程化。

---

## 阶段 3：支持多轮 Agent Loop（可选增强）

**目标**：让第二层 LLM 支持多轮工具调用。

### 当前限制

```python
# 现在：一轮就结束
response = self.llm.call_with_fallback(usage=module.name, messages=..., tools=tools)
if response.get("tool_calls"):
    return await self._handle_tool_calls(...)  # 执行完工具就直接返回结果文本
```

LLM 无法做到"先查询、再决定、再操作"这样的多步推理。

### 改造方案

```python
MAX_ROUNDS = 5

async def _execute(self, user_id, message, module, ...):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    tools = module.to_openai_tools()
    
    for round_num in range(MAX_ROUNDS):
        response = self.llm.call_with_fallback(
            usage=module.name,
            messages=messages,
            tools=tools
        )
        
        # 如果是纯文本回复，结束循环
        if not response.get("tool_calls"):
            return response.get("content", "收到！")
        
        # 回填 assistant 消息
        messages.append({
            "role": "assistant",
            "content": response.get("content"),
            "tool_calls": response["tool_calls"]
        })
        
        # 执行工具并回填结果
        for tc in response["tool_calls"]:
            tool = self.modules.get_tool_by_name(tc["name"])
            if tool:
                result = tool.execute(user_id, **tc["arguments"])
            else:
                result = f"未找到工具: {tc['name']}"
            
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })
    
    return "⚠️ 操作步骤过多，请拆分任务重试"
```

> [!WARNING]
> 多轮 Agent Loop 需要改造 `LLMClient.chat()` 的返回值，让它保留 `tool_calls` 的完整结构（包括 `id` 字段）。当前 `_handle_tool_calls` 的返回格式中没有 `id`，需要一并修改。

---

## 3. 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `skills/schedule/SKILL.md` | 日程模块的 SOP 指令 |
| `skills/timeline/SKILL.md` | 时间线模块的 SOP 指令 |
| `skills/inbox/SKILL.md` | 收集箱模块的 SOP 指令 |
| `core/skill_engine.py` | Skill 引擎核心实现 |

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `core/agent.py` | 引入 SkillEngine，替换 EXECUTOR_PROMPT，支持 Agent Loop |
| `core/llm_client.py` | 返回完整 tool_call 结构（含 id） |
| `core/__init__.py` | 导出 SkillEngine |

### 不变文件

| 文件 | 原因 |
|------|------|
| `tools/base_tool.py` | 工具层完全不变 |
| `tools/modules.py` | ToolModule 保留，用于工具分组 |
| `tools/schedule_tool.py` 等 | 所有工具实现不变 |
| `config.py` | 配置层不变 |
| `services/` | 服务层不变 |

---

## 4. 迁移风险与降级策略

| 风险 | 缓解措施 |
|------|----------|
| SKILL.md 解析失败 | `get_instructions()` 返回 None 时使用默认通用 Prompt（兜底） |
| 新 prompt 导致 LLM 行为变化 | 阶段 1 先写 SKILL.md 但不改代码，通过测试验证 prompt 效果 |
| Agent Loop 死循环 | `MAX_ROUNDS = 5` 强制终止 |
| 多轮调用 token 成本增加 | 监控日志，设置单次对话 token 上限 |

---

## 5. 验证方案

### 阶段 1 验证
- 编写 SKILL.md 后，手动将正文拼入 prompt 测试 LLM 输出质量
- 对比"有 Skill 指令"vs"无 Skill 指令"的工具调用准确率

### 阶段 2 验证
- 发送测试消息，检查日志中是否正确加载了 Skill 指令
- 测试 SKILL.md 缺失时的兜底行为
- 回归测试现有功能（日程、时间线、收集箱）

### 阶段 3 验证
- 发送需要多步推理的消息（如"帮我看看今天有没有安排，然后把下午3点标记为开会"）
- 验证 `MAX_ROUNDS` 限制是否生效

---

*最后更新: 2026-03-12*

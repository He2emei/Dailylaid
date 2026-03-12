# Skills 实现细节

> 📚 本文档面向具体实施的 Agent 和开发者，详细讲解 Skills 引擎的工程实现。

---

## 1. 核心数据结构

### 1.1 SkillMetadata（元数据）

从 SKILL.md 的 YAML frontmatter 解析而来，是 Skill 被发现和选中的依据。

```python
@dataclass
class SkillMetadata:
    name: str           # 技能名称（与目录名一致）
    description: str    # 触发描述（给路由层看的）
    path: str           # 技能目录的绝对路径
```

**`description` 的写法至关重要**，它决定了路由准确性：

```yaml
# ❌ 太抽象，路由无法准确匹配
description: 帮助用户管理事务

# ✅ 包含触发关键词 + 明确边界
description: 管理未来的日程安排。当用户提到"明天"、"安排"、"提醒我"、"开会"、"几点"等与未来计划相关的内容时使用。
```

### 1.2 SkillContent（完整内容）

当 Skill 被触发后加载的完整信息：

```python
@dataclass
class SkillContent:
    metadata: SkillMetadata
    instructions: str       # SKILL.md 正文（Markdown 指令）
    tools: List[BaseTool]   # 该 Skill 关联的工具实例列表
    references: Dict[str, str]  # 引用文件 {文件名: 内容}（按需加载）
```

---

## 2. SKILL.md 正文设计规范

SKILL.md 正文是"操作手册"的核心。好的正文应包含以下板块：

### 模板

```markdown
---
name: <skill_name>
description: <触发描述，包含关键词和适用边界>
---

# <Skill 标题>

## 角色定位
你在此模块中扮演的角色、处理范围。

## 规则
1. 必须遵守的硬规则
2. 边界情况处理方式
3. 错误恢复策略

## 可用工具
- tool_name_1 — 简要描述（必须参数：x, y）
- tool_name_2 — 简要描述

## 上下文注入
说明哪些运行时上下文需要注入（如最近记录、当前时间等）。

## 参考资料
- references/xxx.md — 用途说明（当需要时才读取）

## 输出格式
- 回复风格要求
- emoji 使用规范
- 结构化输出格式（如适用）

## 工作流程
step-by-step 的执行步骤指引。
```

### 实例：schedule Skill 的 SKILL.md 正文

```markdown
---
name: schedule
description: 管理未来的日程安排。当用户提到"明天"、"安排"、"提醒我"、"开会"、"几点"、"下周"等与未来计划相关的内容时使用。
---

# 日程管理

## 角色定位
你是日程管理助手，负责帮用户创建和查询未来的日程安排。

## 规则
1. **时间解析**：以"当前时间"为基准推算相对时间（如"3分钟后"、"半小时后"）
2. **格式要求**：start_time 必须为 YYYY-MM-DD HH:MM 格式
3. **提醒默认值**：距现在超过 60 分钟 → 提前 30 分钟提醒；否则 → 到时立刻提醒
4. **兜底**：如果用户意图不明确，使用 inbox 工具保存

## 可用工具
- schedule — 添加日程（必须参数：title, start_time；可选：location, reminders）
- schedule_list — 查询日程（可选参数：range_days，默认7天）
- inbox — 兜底：无法处理的内容保存到收集箱

## 上下文信息
- 当前日期：{today}
- 当前时间：{current_time}

## 输出格式
- 使用中文回复
- 添加成功时包含 ✅ 📅 ⏰ 📍 🔔 等 emoji
- 简洁友好，不要冗长

## 工作流程
1. 从用户消息中提取：事件标题、时间、地点（可选）
2. 将相对时间转换为绝对时间
3. 调用 schedule 工具
4. 如果信息不完整，直接用 inbox 保存
```

---

## 3. Skill 引擎实现

### 3.1 Discover（发现）

扫描指定目录，找到所有合法的 Skill：

```python
class SkillEngine:
    def __init__(self, skills_dirs: List[str]):
        """
        Args:
            skills_dirs: Skill 目录列表，靠后的目录优先级更高（可覆盖同名 Skill）
        """
        self.skills_dirs = skills_dirs
        self._index: List[SkillMetadata] = []
    
    def discover(self) -> List[SkillMetadata]:
        """扫描所有 skills 目录，建立索引"""
        seen = {}  # name -> SkillMetadata（后来者覆盖）
        
        for base_dir in self.skills_dirs:
            for skill_dir in list_subdirs(base_dir):
                skill_md = os.path.join(skill_dir, "SKILL.md")
                if os.path.exists(skill_md):
                    frontmatter = parse_yaml_frontmatter(skill_md)
                    meta = SkillMetadata(
                        name=frontmatter["name"],
                        description=frontmatter["description"],
                        path=skill_dir
                    )
                    seen[meta.name] = meta  # 后来者覆盖
        
        self._index = list(seen.values())
        return self._index
```

**关键设计**：

- 支持**多目录**搜索，高优先级目录中的同名 Skill 覆盖低优先级的
- 只解析 YAML frontmatter，不读取正文（低成本）

### 3.2 Build Router Prompt（构建路由提示）

将索引转化为紧凑的技能清单，注入到路由 LLM 的提示中：

```python
def build_skills_list(self) -> str:
    """构建给路由 LLM 看的技能清单"""
    lines = []
    for meta in self._index:
        lines.append(f"- {meta.name}: {meta.description}")
    return "\n".join(lines)
```

**上下文成本估算**：每个 Skill 约 30-50 tokens 的 description，10 个 Skill ≈ 300-500 tokens。远低于将所有工具定义全量注入的成本。

### 3.3 Match（匹配）

将用户意图与 Skill 索引进行匹配。有三种实现策略：

| 策略 | 实现方式 | 适用场景 | 我们的选择 |
|------|----------|----------|------------|
| **LLM 路由** | 把 skills list 给轻量 LLM，让它输出 skill name | Skill 数量中等（3-15个） | ✅ **推荐** |
| **语义搜索** | Embedding 向量匹配 + 阈值 | Skill 数量很多（50+个） | 暂不需要 |
| **关键词匹配** | 正则/关键词匹配 | 确定性需求强、Skill 少 | 可作为补充 |

Dailylaid 当前只有 3-5 个模块，**LLM 路由**（现有的第一层 Router）是最合适的策略。

### 3.4 Activate（激活）

匹配到 Skill 后，加载完整的 SKILL.md 正文：

```python
def activate(self, skill_name: str) -> SkillContent:
    """加载 Skill 完整内容"""
    meta = self._get_meta(skill_name)
    skill_md_path = os.path.join(meta.path, "SKILL.md")
    
    # 读取完整文件
    full_content = read_file(skill_md_path)
    
    # 分离 frontmatter 和正文
    _, instructions = split_frontmatter(full_content)
    
    # 获取关联的工具实例
    tools = self._get_tools_for_skill(skill_name)
    
    return SkillContent(
        metadata=meta,
        instructions=instructions,
        tools=tools,
        references={}  # 延迟加载
    )
```

### 3.5 Execute（执行）

将 Skill 指令注入 System Prompt，进入 Agent Loop：

```python
def execute(self, user_msg: str, skill: SkillContent, context: dict) -> str:
    """在 Skill 上下文中执行"""
    
    # 1. 构建 System Prompt = Skill 指令 + 运行时上下文
    system_prompt = self._build_prompt(skill, context)
    
    # 2. 获取工具定义
    tools = [tool.to_openai_tool() for tool in skill.tools]
    
    # 3. Agent Loop（支持多轮工具调用）
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ]
    
    while True:
        response = llm.chat(messages, tools=tools)
        
        if response.get("tool_calls"):
            # 执行工具调用
            for tc in response["tool_calls"]:
                result = execute_tool(tc["name"], tc["arguments"])
                messages.append({"role": "assistant", "content": None, 
                                "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                "content": result})
        else:
            return response["content"]
```

### 3.6 按需加载 References

当 Skill 指令中提到需要参考某个文件时：

```python
def load_reference(self, skill: SkillContent, ref_name: str) -> str:
    """按需加载参考文件"""
    if ref_name in skill.references:
        return skill.references[ref_name]  # 已缓存
    
    ref_path = os.path.join(skill.metadata.path, "references", ref_name)
    if os.path.exists(ref_path):
        content = read_file(ref_path)
        skill.references[ref_name] = content
        return content
    
    return None
```

---

## 4. 上下文注入机制

不同 Skill 需要不同的运行时上下文。目前 Dailylaid 已经有一个具体案例：timeline 模块会注入最近 24 小时活动。

### 4.1 上下文注入的设计模式

在 SKILL.md 中通过占位符声明需要的上下文：

```markdown
## 上下文信息
- 当前日期：{today}
- 当前时间：{current_time}
- {context_injection}
```

在代码层面，每个 Skill 可以注册一个上下文提供函数：

```python
# 上下文提供函数的注册
context_providers = {
    "timeline": lambda user_id, db: {
        "recent_activities": db.get_activities_recent(user_id, hours=24)
    },
    "schedule": lambda user_id, db: {
        "upcoming_schedules": db.get_schedules(user_id, today, today + 7days)
    },
}
```

### 4.2 渐进式上下文注入

并非所有上下文都需要在一开始就注入。可以让 LLM 通过工具调用来"拉取"上下文：

1. **立即注入**：时间、日期等轻量上下文 → 直接放在 System Prompt 中
2. **工具拉取**：历史记录等重量上下文 → 通过 `schedule_list` / `timeline_list` 等查询工具获取

---

## 5. 多轮工具调用（Agent Loop）

现有 Dailylaid 的第二层只做**一轮**工具调用：LLM 返回 `tool_calls` → 执行 → 直接返回结果给用户。

成熟的 Skills 引擎需要支持**多轮** Agent Loop：

```
LLM → tool_call(schedule, ...) → 执行 → 结果回填 → LLM → "✅ 已添加日程..."
  │                                                ↑
  └── tool_call(schedule_list) → 执行 → 结果回填 ──┘ （如果 LLM 决定先查询再添加）
```

### 实现要点

```python
MAX_TOOL_ROUNDS = 5  # 防止无限循环

async def agent_loop(messages, tools, llm):
    for _ in range(MAX_TOOL_ROUNDS):
        response = llm.chat(messages, tools=tools)
        
        if not response.get("tool_calls"):
            return response["content"]  # 最终文本回复
        
        # 回填 assistant 的 tool_calls 消息
        messages.append({
            "role": "assistant",
            "content": response.get("content"),
            "tool_calls": response["tool_calls"]
        })
        
        # 执行每个工具调用并回填结果
        for tc in response["tool_calls"]:
            result = execute_tool(tc["name"], tc["arguments"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })
    
    return "操作超时，请重试"
```

---

## 6. YAML Frontmatter 解析

### 解析逻辑

```python
import yaml
import re

def parse_yaml_frontmatter(filepath: str) -> dict:
    """解析 SKILL.md 的 YAML frontmatter"""
    content = read_file(filepath)
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        raise ValueError(f"无效的 SKILL.md: {filepath}，缺少 YAML frontmatter")
    
    return yaml.safe_load(match.group(1))

def split_frontmatter(content: str) -> tuple[dict, str]:
    """将 SKILL.md 分离为 frontmatter 和正文"""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    
    metadata = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return metadata, body
```

---

## 7. 安全与治理

### 7.1 元数据安全

- `description` 不应过于宽泛（避免误匹配）
- 定期 Review SKILL.md 的变更

### 7.2 工具执行安全

- 所有工具调用仍然通过现有的 `BaseTool.execute()` 接口，保持已有的参数校验
- 设置 `MAX_TOOL_ROUNDS` 防止死循环
- 保持 inbox 兜底机制

### 7.3 Scripts 安全（如采用）

- Scripts 只在受控环境中执行
- 对输入做校验
- 锁定脚本版本

---

## 附录 A：OpenClaw 源码分析要点

> 以下内容基于对 OpenClaw 仓库（`myAIApp/Temp/openclaw`）源码的实际阅读。

### A.1 Skill 加载的 6 级优先级

OpenClaw 从 6 个位置加载 Skills，优先级从低到高：

```
extra (配置的额外目录)
  ↓ 覆盖
bundled (内置 Skills，随安装包分发)
  ↓ 覆盖
managed (~/.openclaw/skills)
  ↓ 覆盖
agents-skills-personal (~/.agents/skills)
  ↓ 覆盖
agents-skills-project (<workspace>/.agents/skills)
  ↓ 覆盖
workspace (<workspace>/skills)  ← 最高优先级
```

**源码位置**：`src/agents/skills/workspace.ts` L490-L509

同名 Skill 被更高优先级目录中的版本覆盖（简单 Map.set 覆盖策略）。

> **对 Dailylaid 的启示**：我们只需要一个 `skills/` 目录即可，多级加载是 Dailylaid 不需要的复杂度。

### A.2 Prompt 注入格式：紧凑 XML

OpenClaw 使用 `formatSkillsForPrompt()`（来自 `@mariozechner/pi-coding-agent` 库）将可用 Skills 以紧凑 XML 格式注入系统提示：

**成本公式**（字符数）：

```
total = 195 (base) + Σ (97 + len(name) + len(description) + len(location))
```

- 基础开销：195 字符（仅当 ≥1 个 skill 时）
- 每个 Skill：97 字符 + name + description + location 的 XML 转义长度
- 粗略换算：~4 字符 ≈ 1 token，所以每个 Skill ≈ 24+ tokens

**源码位置**：`docs/tools/skills.md` L269-L285

> **对 Dailylaid 的启示**：我们当前只有 3 个模块，总成本约 300-500 tokens，完全可承受。不需要 XML 格式，普通文本列表即可。

### A.3 Size limits（防护措施）

OpenClaw 定义了严格的上限防止资源滥用：

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| maxSkillFileBytes | 256,000 | 单个 SKILL.md 文件大小上限 |
| maxCandidatesPerRoot | 300 | 单个目录下最多扫描的子目录数 |
| maxSkillsLoadedPerSource | 200 | 单个来源最多加载的 Skill 数 |
| maxSkillsInPrompt | 150 | 注入提示词的最大 Skill 数 |
| maxSkillsPromptChars | 30,000 | Skills 清单的最大字符数 |

**源码位置**：`src/agents/skills/workspace.ts` L96-L100

> **对 Dailylaid 的启示**：我们不需要这些限制，但可以设一个合理的 `MAX_SKILL_FILE_SIZE` 防止意外。

### A.4 Invocation Policy（调用策略）

OpenClaw 的每个 Skill 有两个控制开关：

```typescript
type SkillInvocationPolicy = {
  userInvocable: boolean;          // 是否暴露为斜杠命令（默认 true）
  disableModelInvocation: boolean; // 是否从模型提示中排除（默认 false）
};
```

组合效果：

| userInvocable | disableModelInvocation | 效果 |
|:---:|:---:|------|
| true | false | 模型可触发 + 用户可用命令调用 |
| true | true | **仅**用户命令调用，模型看不到 |
| false | false | 模型可触发，但不暴露命令 |
| false | true | 不可用（被过滤掉） |

**源码位置**：`src/agents/skills/frontmatter.ts` L208-L218

> **对 Dailylaid 的启示**：当前我们已有 `/help`、`/inbox` 等斜杠命令。未来可以考虑让 Skill 声明 `user-invocable: true` 自动注册为斜杠命令。

### A.5 真实 SKILL.md 写法模式

分析了 `skills/weather/SKILL.md` 和 `skills/github/SKILL.md`，发现共同模式：

```markdown
---
name: <skill_name>
description: "<功能说明>. Use when: <触发场景>. NOT for: <不适用场景>."
metadata: { "openclaw": { "requires": { "bins": ["<依赖>"] } } }
---

# <Skill 标题>

## When to Use
✅ **USE this skill when:**
- 触发场景 1
- 触发场景 2

## When NOT to Use
❌ **DON'T use this skill when:**
- 不适用场景 1（→ 应该用 XXX）
- 不适用场景 2

## Commands / 工具使用方法
具体的命令或工具调用示例

## Notes
注意事项
```

> **对 Dailylaid 的启示**：采用 "When to Use / When NOT to Use" 的明确边界描述模式，可以显著提升路由准确率。

### A.6 路径安全检查

OpenClaw 对 Skill 路径做严格的"包含检查"（`isPathInside`），确保：
- Skill 目录的真实路径不逃逸出配置的根目录
- 符号链接被解析后仍在根目录内
- 否则跳过该 Skill 并记录警告

**源码位置**：`src/agents/skills/workspace.ts` L187-L247

> **对 Dailylaid 的启示**：我们的 Skills 都是自有的，暂不需要路径安全检查。但如果未来开放第三方 Skills，应加入此机制。

---

*最后更新: 2026-03-12*

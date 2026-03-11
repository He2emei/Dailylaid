# 两层 LLM 路由+执行架构深度解析

本文档深度剖析 Dailylaid 的核心设计——两层 LLM 架构，涵盖 Prompt 工程、模型管理、故障切换等实现细节。

---

## 📐 架构设计动机

### 为什么不用单层 LLM？

**单层方案**：将所有工具定义一次性传给 LLM → 让它自行判断调用哪个。

**问题**：
1. **Token 浪费**：8 个工具的 Function 定义约 800 tokens，每次请求都要携带
2. **路由精度下降**：工具越多，LLM 选错的概率越高
3. **模型选择受限**：简单的路由任务被迫使用昂贵模型
4. **延迟和成本**：重模型处理简单分类，性价比低

### 两层架构的优势

```
第一层 Router: 轻量模型 → 低延迟、低成本   → "这条消息属于哪个模块？"
第二层 Executor: 标准模型 → 高准确度      → "在这个模块内调用什么工具？"
```

| 维度 | 单层 | 两层 |
|------|------|------|
| 路由延迟 | 高（重模型） | 低（轻量模型） |
| Token 成本 | 每次传全部工具 | Router 无工具定义 |
| 路由准确率 | 工具多时下降 | 模块少（3个），准确率高 |
| 可扩展性 | 工具增多后急剧恶化 | 只增加模块内工具，Router 不变 |

---

## 第一层：Router（意图路由）

### 核心逻辑

位于 `core/agent.py` 的 `_route()` 方法。

```python
async def _route(self, message: str) -> str:
    # 1. 构建 Prompt（含模块列表 + 当前时间）
    # 2. 调用轻量 LLM（usage="router" → light 级别）
    # 3. 提取模块名并验证
    # 4. 无效模块名 → 回退到 inbox
```

### Router Prompt 设计

```
你是一个意图识别助手。根据用户消息，判断应该使用哪个模块处理。

可用模块：
- schedule: 日程管理：添加、查看日程安排 (关键词: 日程, 安排, 开会, ...)
- timeline: 时间线活动记录：记录**已完成**的活动... (关键词: 刚才, 完成了, ...)
- inbox: 收集箱：保存暂时无法分类的内容

重要区分：
- **schedule（日程）**：用户想要添加/查看**未来**的计划安排
- **timeline（时间线）**：用户想要记录/查看**已完成**的活动

时间判断：
- 当前时间是 {current_time}
- 如果提到具体时间点（如18点、9点），判断该时间是过去还是未来
  * 过去的时间 → timeline
  * 未来的时间 → schedule

规则：
1. 只输出模块名称（英文），不要其他内容
2. 如果无法确定，输出 inbox

用户消息: {message}
请输出模块名称:
```

**Prompt 设计要点**：

1. **强约束输出**："只输出模块名称（英文），不要其他内容" → 减少后处理复杂度
2. **核心区分规则**：schedule vs timeline 是最容易混淆的一对，Prompt 专门用一大段解释区分逻辑
3. **注入当前时间**：让模型能判断"18点"是过去还是未来
4. **兜底策略**："如果无法确定，输出 inbox" → 永远有出路

### 路由结果校验

```python
content = response.get("content", "inbox").strip().lower()

# 直接匹配
if content in self.modules.all_names():
    return content

# 模糊匹配（LLM 可能回复 "应该用 schedule 模块" 而非纯 "schedule"）
for name in self.modules.all_names():
    if name in content:
        return name

return "inbox"  # 终极兜底
```

三层防御：精确匹配 → 模糊匹配 → 默认兜底。即使 LLM 输出格式不完美，也能正确路由。

---

## 第二层：Executor（工具执行）

### 核心逻辑

位于 `core/agent.py` 的 `_execute()` 方法。

```python
async def _execute(self, user_id: str, message: str, module: ToolModule) -> str:
    # 1. 构建 System Prompt（含模块名、日期上下文）
    # 2. 如果是 timeline 模块，注入最近24小时活动上下文
    # 3. 获取模块工具列表 + inbox 兜底工具
    # 4. 调用标准 LLM（Function Calling）
    # 5. 处理 tool_calls → 执行工具 → 返回结果
```

### Executor Prompt

```
你是 Dailylaid，一个个人日常事务管理助手。

当前模块: schedule
当前日期: 2026-03-11 Tuesday

请根据用户消息调用合适的工具。如果不确定如何处理，使用 inbox 工具保存。

回复时请简洁友好，使用中文。
```

### Timeline 模块的上下文注入

当路由到 `timeline` 模块时，Executor 会额外注入最近 24 小时的活动记录：

```
**最近24小时的活动记录**（用于智能补充结束时间）：
- ID3: 写代码 (2026-03-11T09:00:00 → 未结束) ← 可补充
- ID2: 吃早饭 (2026-03-11T07:30:00 → 2026-03-11T08:00:00)

提示：如果用户提到某活动结束，检查是否有对应的未结束记录，
使用 timeline_update 工具补充 end_time。
```

**设计目的**：用户说"写完代码了"时，LLM 能看到 ID3 是未结束状态，自动调用 `timeline_update(activity_id=3, end_time="...")` 而非新建一条记录。

### 工具列表构建

```python
# 模块自身的工具
tools = module.to_openai_tools()

# 非 inbox 模块时，额外添加 inbox 作为兜底
if module.name != "inbox" and self.inbox_tool:
    tools.append(self.inbox_tool.to_openai_tool())
```

这保证即使在 schedule 模块中，如果用户消息实际无法处理，LLM 也可以选择将其保存到收集箱。

### Tool Call 处理

```python
async def _handle_tool_calls(self, user_id, message, tool_calls):
    for tc in tool_calls:
        tool = self.modules.get_tool_by_name(tc["name"])  # 跨模块查找
        result = tool.execute(user_id, **tc["arguments"])
        results.append(result)
    return "\n".join(results)
```

支持一次多个 tool_calls（LLM 可能一次返回多个工具调用），通过 `get_tool_by_name` 跨模块查找。

---

## 模型管理与故障切换

### LLMManager (`core/llm_manager.py`)

管理所有模型实例，提供按用途获取客户端和自动故障切换。

```
llm_config.yaml
     │
     ▼
 ┌──────────────────────┐
 │     LLMManager       │
 │                      │
 │  clients:            │
 │    light:            │
 │      [0] gemini-lite │  ← 优先使用
 │      [1] grok-fast   │  ← 备用
 │    standard:         │
 │      [0] gemini-flash│
 │    advanced:         │
 │      (空)             │
 │                      │
 │  usage_map:          │
 │    router → light    │
 │    schedule → standard│
 │    default → standard│
 └──────────────────────┘
```

### 故障切换策略 (`call_with_fallback`)

```python
def call_with_fallback(self, usage, messages, tools=None):
    tier = self.usage_map.get(usage, "standard")
    clients = self.clients.get(tier, [])
    
    # 层级内没有客户端 → 降级到 standard
    if not clients:
        clients = self.clients.get("standard", [])
    
    # 逐个尝试
    for client in clients:
        try:
            return client.chat(messages, tools=tools)
        except Exception:
            continue  # 切换到下一个备用
    
    raise RuntimeError("所有模型调用失败")
```

**切换层级**：
1. 同级别内顺序尝试多个客户端（如 light 有 gemini-lite 和 grok-fast）
2. 如果整个级别无可用客户端，降级到 standard
3. 全部失败 → 抛出包含所有失败详情的 `RuntimeError`

### LLMClient (`core/llm_client.py`)

单一客户端封装，使用 OpenAI Python SDK：

```python
class LLMClient:
    def __init__(self, api_key, base_url, model, api_name=None, name=None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def chat(self, messages, tools=None, temperature=0.7):
        kwargs = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = self.client.chat.completions.create(**kwargs)
        # 解析 content + tool_calls 并返回
```

**关键设计**：
- `tool_choice = "auto"`：让模型自行决定是否调用工具
- `temperature = 0.7`：默认温度，平衡创造性和确定性
- 返回统一格式：`{"content": "...", "tool_calls": [...]}`

---

## 错误处理策略

`DailylaidAgent.process()` 中的错误分类处理：

| 错误类型 | 识别方式 | 用户提示 | 消息保存 |
|----------|----------|----------|----------|
| API 配额不足 | `"429" in error` | ⚠️ API配额不足 | 否 |
| 请求格式错误 | `"500"` / `"invalid_request"` | ⚠️ API请求格式错误 | 否 |
| 网络连接错误 | `"timeout"` / `"connection"` | ⚠️ 网络连接失败 | 否 |
| 其他 RuntimeError | 兜底 | ⚠️ 处理失败 | 收集箱 |
| 未知异常 | `except Exception` | ⚠️ 系统异常 | 收集箱 |

> [!TIP]
> 非 API 错误会自动将消息保存到收集箱，确保用户的输入不会丢失。

---

## 扩展指南

### 新增模块的步骤

1. 在 `tools/` 下创建新工具文件（参考 `schedule_tool.py`）
2. 在 `core/agent.py` 的 `_register_modules()` 中注册模块
3. 在 `llm_config.yaml` 的 `usage` 中为新模块指定模型级别
4. 在 `tools/__init__.py` 中导出新工具类

### 新增模型提供商

1. 在 `.env` 中添加新 API Key 环境变量
2. 在 `llm_config.yaml` 的对应层级下添加模型配置
3. `LLMManager` 会自动加载并纳入故障切换链

---

*最后更新: 2026-03-11*

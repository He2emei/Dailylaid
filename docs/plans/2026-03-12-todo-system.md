# 待办/事务管理系统设计方案

**状态**: `进行中`
**创建日期**: 2026-03-12

---

## 背景 (Context)

目前 Dailylaid 有三个核心模块：
- **schedule（日程）**：面向未来，"只提醒不追踪" — 到时间提醒一次即结束
- **timeline（时间线）**：面向过去，记录已完成的活动
- **inbox（收集箱）**：兜底，保存无法分类的碎片信息

现有的 `todos` 表结构简单（仅 content/category/due_date/status），无法支撑：
1. 完成状态追踪与持续催促
2. 重复/周期性任务
3. 消息-任务绑定（回复交互）
4. 每日规划摘要

我们希望让 Dailylaid 从"提醒工具"进化为**私人秘书**级别的事务管理系统。

---

## 1. 架构决策

### 1.1 Schedule vs Todo：分离但共享基础设施

**核心判断标准**：
- "到时候即使我不做，这件事也会发生/过去" → **schedule**（会议、航班、约会）
- "不做就一直悬着，等着我去完成" → **todo**（交报告、买菜、背单词）

```
┌────────────────────────────────────────────────────────┐
│                  Dailylaid 事务管理                      │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌────────┐ │
│  │ SCHEDULE │  │   TODO   │  │ TIMELINE │ │  PLAN  │ │
│  │  日程    │  │  待办    │  │  时间线  │ │ 每日规划│ │
│  │ 过期失效 │  │ 逾期催促 │  │ 记录过去 │ │ 聚合视图│ │
│  └─────┬────┘  └────┬─────┘  └──────────┘ └────┬───┘ │
│        │            │                           │     │
│        └─────┬──────┘                           │     │
│              ▼                                  │     │
│  ┌─────────────────────┐                        │     │
│  │  ReminderService    │◄───────────────────────┘     │
│  │  (统一提醒引擎)     │                              │
│  └─────────────────────┘                              │
│                                                        │
│  ┌─────────────────────────────────────────────┐      │
│  │  ConfigManager (YAML 配置 + 热加载)         │      │
│  └─────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────┘
```

### 1.2 路由层的模糊性对策：置信度 + 确认机制

对于模棱两可的请求（如"周五去健身房"），Router 返回置信度：

```json
{"module": "schedule", "confidence": 0.6}
```

- **≥ 0.8**：直接执行
- **< 0.8**：BOT 主动确认：
  > "📋 '周五去健身房' — 这是一个固定时间安排（到点就过），还是需要追踪完成的待办？"

Router Prompt 中需要清晰表达区分原则，并教会 LLM 输出 JSON 格式。

---

## 2. 消息回复交互 — 已验证 ✅

### 2.1 NapCat 实测数据（2026-03-12 确认）

用户在群聊中回复一条消息时，NapCat 上报的数据：

```json
{
  "message_id": 1176001989,
  "raw_message": "[CQ:reply,id=654648425][CQ:at,qq=1919447403] 这是一条回复测试信息",
  "message": [
    {"type": "reply", "data": {"id": "654648425"}},
    {"type": "at", "data": {"qq": "1919447403"}},
    {"type": "text", "data": {"text": " 这是一条回复测试信息"}}
  ]
}
```

**关键确认**：
- ✅ `reply` 类型段包含被回复消息的 `id`
- ✅ 群聊回复自动带 `at` 段
- ✅ 纯文本可通过 `text` 段提取
- ✅ `send_msg` API 返回 `data.message_id`，可用于记录 BOT 发出的消息 ID

### 2.2 交互流程

```
用户: "下周交项目报告"
  ↓
BOT（response → message_id = 12345）: 
  "✅ 已添加待办 #7
   📋 交项目报告 ⏰ 截止: 03月19日
   💡 回复本消息：完成✅ / 推迟⏳ / 取消❌"
  ↓ 系统记录: task.bound_message_ids = [12345]

--- 3天后 BOT 催促（message_id = 12388）---

用户（回复 12388）: "推迟到周日"
  ↓ 系统解析 [CQ:reply,id=12388] → 查 bound_message_ids → task #7
  ↓ LLM 识别意图 → 更新 deadline
BOT: "✅ 已推迟，新截止日期: 03月23日"
```

### 2.3 回复处理（在 app.py on_message 中拦截）

```python
# 伪代码 — 在现有 on_message 中新增
reply_msg_id = extract_reply_id(message_array)
if reply_msg_id:
    task = db.find_task_by_bound_message(reply_msg_id)
    if task:
        actual_text = extract_text(message_array)
        result = agent.process_task_reply(user_id, task, actual_text)
        # 发送回复并记录新 message_id
        resp = adapter.send_message(...)
        db.append_bound_message(task.id, resp.data.message_id)
        return
# 否则走正常路由
```

---

## 3. Todo 核心数据模型

```sql
-- 待办事项主表（新表，不修改旧 todos 表）
CREATE TABLE tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    deadline        TEXT,                    -- 截止时间 (ISO format)
    scheduled_time  TEXT,                    -- 预设提醒时间
    status          TEXT DEFAULT 'pending',  -- pending / done / cancelled
    priority        TEXT DEFAULT 'medium',   -- high / medium / low
    template_id     INTEGER,                -- 关联重复模板
    category        TEXT,
    tags            TEXT DEFAULT '[]',
    source_message_id   TEXT,               -- 创建时的原始消息 ID
    bound_message_ids   TEXT DEFAULT '[]',  -- BOT 发送的关联消息 ID 列表
    source_type         TEXT DEFAULT 'private',
    source_group_id     TEXT,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 重复任务模板
CREATE TABLE task_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    tags            TEXT DEFAULT '[]',
    priority        TEXT DEFAULT 'medium',
    recurrence_type TEXT NOT NULL,          -- daily / weekly / monthly / custom
    recurrence_rule TEXT NOT NULL,          -- JSON: 详细重复配置
    default_deadline_offset TEXT,           -- "+1d", "+3h", null
    is_active       BOOLEAN DEFAULT 1,
    last_generated  TEXT,
    next_generate   TEXT,
    source_type     TEXT DEFAULT 'private',
    source_group_id TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 任务提醒日志
CREATE TABLE task_reminder_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL,
    remind_type     TEXT NOT NULL,          -- scheduled / deadline / overdue
    remind_time     TEXT NOT NULL,
    message_id      TEXT,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, remind_type, remind_time)
);

-- 用户偏好
CREATE TABLE user_preferences (
    user_id             TEXT PRIMARY KEY,
    daily_brief_time    TEXT DEFAULT '08:00',
    daily_brief_enabled BOOLEAN DEFAULT 1,
    timezone            TEXT DEFAULT 'Asia/Shanghai',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. 提醒策略

初版直接 hardcode 常量，后续按需抽成 YAML 配置文件并实现热加载。

| 阶段 | 触发条件 | 频率 | 消息 |
|------|---------|------|------|
| 预提醒 | `scheduled_time` 前 30 分 | 一次 | 📋 该做 XX 了 |
| 到时提醒 | `scheduled_time` 到达 | 一次 | ⏰ 现在做 XX！ |
| Deadline 预警 | `deadline` 前 1 小时 | 一次 | ⚠️ XX 还有 1 小时截止！ |
| 逾期催促 | 超过 `deadline` | 2h→4h→8h→24h（退避） | 🔴 XX 已逾期！ |

每天最多催 3 次，超过 7 天不再催促。

---

## 5. 每日规划 (Plan Module)

作为**独立 Module**，拥有自己的路由关键词和 Skill。

**数据聚合**：
```
Daily Brief = schedules(今日) + tasks(今日到期/预定/逾期) + 重复任务实例
```

**触发方式**：
- 自动推送：按用户 `user_preferences.daily_brief_time` 推送
- 快捷命令：`/plan`、`/today`
- 自然语言：路由到 plan 模块（"今天有什么要做"）
- 扩展：`/week` 看本周

---

## 6. 配置热加载

### 6.1 实现方式：文件 Watcher

使用 `watchdog` 库监控 YAML 配置文件变更：

```python
class ConfigManager:
    """可热加载的配置管理器"""
    
    def __init__(self, config_path):
        self._config_path = config_path
        self._config = self._load()
        self._start_watcher()
    
    def _load(self):
        """加载配置"""
        with open(self._config_path) as f:
            config = yaml.safe_load(f)
        # 校验配置格式
        self._validate(config)
        return config
    
    def _on_file_changed(self):
        """文件变更回调"""
        try:
            new_config = self._load()
            self._config = new_config
            logger.info("配置已热加载")
        except Exception as e:
            logger.error(f"配置加载失败，保持旧配置: {e}")
    
    def get(self, key, default=None):
        return self._config.get(key, default)
```

**安全措施**：
- 加载失败时保持旧配置，不会崩溃
- 加载成功时打日志通知

---

## 7. 实施路线图（Phase 顺序）

### Phase 1: 数据层 + 基础 Todo 工具 ⭐ 最先做
> 所有后续功能的基础。没有数据表和工具，其他都无法开展。

- [ ] 在 `database.py` 中添加 `tasks` + `task_templates` + `task_reminder_logs` + `user_preferences` 建表语句
- [ ] 实现数据层 CRUD 方法
- [ ] 创建 Todo 工具类（`todo_add`, `todo_list`, `todo_complete`, `todo_update`, `todo_cancel`）
- [ ] 创建 `skills/todo/SKILL.md`
- [ ] 在 Agent 的 Router 中注册 `todo` 模块
- [ ] 更新 Router Prompt，明确 schedule vs todo 判断标准

### Phase 2: 消息回复交互
> 依赖 Phase 1 的 tasks 表和 bound_message_ids 字段。

- [ ] 在 `app.py` `on_message` 中新增回复消息拦截逻辑
- [ ] 实现 `extract_reply_id()` 和 `extract_text()` 工具函数
- [ ] 实现 `find_task_by_bound_message()` 数据库查询
- [ ] 修改 `send_message` 调用，捕获返回的 `message_id` 并记录
- [ ] 实现回复意图识别 → 任务操作的链路

### Phase 3: 提醒引擎扩展 ✅
> 依赖 Phase 1 的 tasks 表 + Phase 2 的消息 ID 记录。

- [x] 扩展 `ReminderService`，新增 Task 类型检查逻辑
- [x] 实现分级催促（预提醒 → 到时 → deadline → 逾期退避）
- [x] 催促消息发送后记录 `message_id` 到 `bound_message_ids`
- [x] 实现每天最大催促次数限制 & 超时停止催促

### Phase 4: 路由置信度 + 确认机制
> 优化体验，需要 Phase 1 的 todo 模块已就位。

- [ ] 修改 Router Prompt，输出 JSON 格式 `{"module": "xxx", "confidence": 0.9}`
- [ ] 修改 `_route()` 方法解析置信度
- [ ] 低置信度时生成确认消息并等待用户回复
- [ ] 确认后路由到正确模块

### Phase 5: 重复任务
> 依赖 Phase 1 的 task_templates 表。

- [ ] 实现 `task_templates` CRUD
- [ ] 实现定时生成器（每日扫描 + 生成 task 实例）
- [ ] 实例继承模板字段
- [ ] 模板管理交互（创建/暂停/恢复/删除）

### Phase 6: 每日规划 (Plan Module)
> 依赖 Phase 1 (tasks) + Phase 3 (提醒引擎) + Phase 5 的重复任务数据。

- [ ] 创建 `plan` Module + `skills/plan/SKILL.md`
- [ ] 实现聚合查询工具（跨 schedules + tasks 表）
- [ ] 在 Router 注册 plan 模块
- [ ] 实现 `user_preferences` CRUD
- [ ] 在 `ReminderService` 中新增定时 Daily Brief 推送
- [ ] 扩展快捷命令 `/plan`、`/today`、`/week`

### Phase 7: 配置热加载
> 独立基础设施，可在任何时候做。

- [ ] 添加 `watchdog` 依赖
- [ ] 实现 `ConfigManager` 类
- [ ] 创建 `reminder_config.yaml`
- [ ] 将 Phase 3 中 hardcode 的催促参数迁移到配置文件
- [ ] 将 `daily_brief_time` 默认值等也纳入配置

---

## 参考资料

- **GTD (Getting Things Done)**：五步法（收集→处理→组织→回顾→执行）
- **Things 3 / Todoist**：标签+优先级+重复规则的成熟参考
- **OpenClaw Skills**：apple-reminders、things-mac 的交互模式参考
- **OneBot 11 协议**：CQ 码规范，send_msg 返回 message_id
- **NapCat 实测结果**：2026-03-12 确认 reply CQ 码解析完全可行

---

*最后更新: 2026-03-16*

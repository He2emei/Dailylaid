# Dailylaid 开发待办 (Dev TODO)

> 本文档用于在 AI Agent 对话之间持续追踪任务进度、记录待完成事项和快速对齐上下文。
> 每次对话开始时请先阅读此文件。

## ⭐ 当前进度

### Todo 管理系统（7 阶段路线图）
📄 设计文档：[2026-03-12-todo-system.md](plans/2026-03-12-todo-system.md)

| Phase | 内容 | 状态 | 说明 |
|-------|------|------|------|
| 1 | 数据层 + 基础 Todo 工具 | ✅ | 4 表 + 15 CRUD + 5 工具 |
| 2 | 消息回复交互 | ✅ | 自身消息上报 (`message_sent`) + 待绑定队列 |
| 3 | 提醒引擎扩展 | ✅ | 4 级提醒 + 逾期退避 + 每日3次 + 7天上限 |
| 4 | 路由置信度 + 确认机制 | ✅ | JSON 置信度 + 确认问题 + 回复路由 |
| 5 | 重复任务 | ⬜ | 模板 → 实例生成 |
| 6 | 每日规划 Plan Module | ⬜ | 聚合视图 + `/plan` 命令 |
| 7 | 配置热加载 | ⬜ | watchdog 文件监控 |

## 📋 待办事项

### 高优先级
- [x] ~~Phase 2 调试：验证 `.env` 添加 `ALLOWED_USERS` 后回复交互是否正常~~ → ALLOWED_USERS 已改回空
- [x] ~~`send_group_msg` API 超时问题排查~~ → 根因确认，已做兜底处理
- [x] ~~重启 app 验证回复交互是否正常工作~~ → 改用自身消息上报方案
- [ ] **真机验证**：启动 app，发送待办，确认自身消息上报绑定 → 回复完成/取消
- [ ] **真机验证 Phase 3**：测试提醒引擎（预提醒 / 到时 / deadline 预警 / 逾期催促）

### 中优先级
- [ ] Phase 3 开始：提醒引擎扩展
- [ ] 路由区分优化：schedule vs todo 边界模糊时的处理策略

### 低优先级 / 想法
- [ ] 日志编码问题（日志文件出现乱码）
- [ ] AI 日志分析和 Tag 提取（用户提到的想法）

## 🐛 已知问题

| 问题 | 状态 | 相关文件 |
|------|------|----------|
| `send_group_msg` 每次都超时（消息已发但响应丢失） | ✅ 已兜底 + 自身消息上报方案 | `app.py`, `ws_adapter.py` |
| WebSocket 消息重复投递（每条消息收到两次） | ✅ 已修复 | `app.py` (dedup) |
| 回复消息 message_id 匹配不到任务 | ✅ 已修复（自身消息上报绑定） | `app.py` |
| 日志文件中文乱码 | 🔍 待排查 | `utils/logger.py` |

## 📝 对话速记
> 每次对话结束后简要记录，便于下次接续。

### 2026-03-12
- 完成 Todo 系统 Phase 1 全部实现
- 设计文档已写入 `docs/plans/2026-03-12-todo-system.md`
- 已推送到 Dev + Production + GitHub

### 2026-03-13 上午
- 开始 Phase 2 消息回复交互实现
- 发现私聊消息被 `is_allowed()` 拦截（`ALLOWED_USERS` 为空）
- 修复 `.env`，等待重新测试

### 2026-03-13 中午
- 确认 `ALLOWED_USERS` 应为空（dev 只过滤群消息），已改回
- 排查回复交互失败原因：`send_group_msg` **每次都超时**，BOT 的 message_id 永远拿不到
- 修复 3 项问题：
  1. **send_group_msg 超时兜底**：捕获 TimeoutError，视为消息已发出
  2. **回复意图兜底**：当 message_id 匹配不到任务时，如果回复文本是明确意图（完成/取消/推迟），匹配最近的 pending 任务
  3. **消息去重**：WebSocket 每条消息投递两次，加了 dedup 缓存
- **待验证**：需重启 app 测试回复交互

### 2026-03-16
- 用户在 NapCat 开启了"上报自身消息"功能
- 实现**自身消息上报方案**彻底解决 message_id 绑定问题：
  1. `config.py` 添加 `BOT_QQ` 配置（`1035013925`）
  2. `app.py` 新增自身消息检测：识别 `user_id == BOT_QQ` 的消息，提取 `message_id` 绑定到任务
  3. 新增 `try_bind_self_message()` 函数 + 待绑定队列（30s TTL）
  4. 移除旧的 incoming message_id 绑定方案（不够可靠）
  5. 保留 API 响应绑定作为备用路径
- **待验证**：启动 app 真机测试完整链路

### 2026-03-16 下午
- 完成 Phase 3 提醒引擎扩展：
  1. `reminder_service.py` 重写，支持 4 级 Task 提醒（预提醒30min / 到时 / deadline预警1h / 逾期退避2→4→8→24h）
  2. `database.py` 新增 `get_last_task_reminder()` 方法，退避间隔判断
  3. `app.py` 回调 `send_reminder_message` 改为返回 `message_id`，催促消息自动绑定到任务
  4. 限制条件：每天最多催 3 次，逾期超 7 天停止
- 13 个单元测试全部通过

### 2026-03-25
- 完成 Phase 4 路由置信度 + 确认机制：
  1. `agent.py`：ROUTER_PROMPT 输出 JSON `{module, confidence}`，`_route()` 解析置信度
  2. 低于 0.8 且属于 schedule/todo 模糊时，主动向用户发确认问题
  3. `app.py`：确认等待队列，用户回复 1/2 后路由到对应模块
  4. 用户回复非 1/2 则丢弃确认状态，当作新消息处理
- 14 个单元测试全部通过，全套 43 个测试通过

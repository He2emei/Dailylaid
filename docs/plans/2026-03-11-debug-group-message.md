# 修复群消息未响应问题

**状态**: `已完成`
**创建日期**: 2026-03-11

## 背景 (Context)
用户在群聊（1087453112）中发送了消息“提醒我3分钟后喝水”，但 Dailylaid 没有回复。由于用户在 `.env` 中配置了 `ALLOWED_GROUPS=1087453112`，需要排查为何消息被忽略。

## 计划 (Plan)
- [x] 调查 `.env` 和 `Config.is_allowed` 过滤逻辑，确认白名单处理正确。
- [x] 开启 DEBUG 日志，排查底层消息接收情况。
- [x] 调查 `app.py` 中的 `on_message` 早期丢弃逻辑。
- [x] 修改 `app.py` 解析逻辑，从 `message` 数组提取纯文本，修复 `raw_message` 为空时静默丢弃的 bug。
- [x] 重启应用并通知用户测试。

## 当前进展 (Progress)
已完成所有排查和修复工作。
1. 确认了 `ALLOWED_GROUPS` 的解析和 `Config.is_allowed()` 方法工作正常，返回了 `True`。
2. 发现 `app.py` 原有逻辑 `if not raw_message: return` 会在 NapCat 将消息以 `message` 数组（segment 格式）发送且不提供 `raw_message` 时静默丢弃消息。
3. 补充了从 `message` 中提取 `text` segment 的功能，并重启了服务。

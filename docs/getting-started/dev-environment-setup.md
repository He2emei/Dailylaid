# 开发环境搭建指南

本文档帮助开发者从零搭建 Dailylaid 开发环境并成功启动服务。

---

## 前置依赖

| 依赖 | 最低版本 | 用途 |
|------|----------|------|
| Python | 3.11+ | 运行时 |
| pip | 最新 | 包管理 |
| Git | 2.x | 版本控制 |
| NapCat | - | QQ 机器人框架（远程服务器部署） |

> [!NOTE]
> Dailylaid 本身在本地运行，但需要连接到一个部署了 NapCat 的远程服务器。
> 如果你只是本地开发和测试 LLM 相关功能，可以先跳过 NapCat 配置。

---

## 一、克隆项目与虚拟环境

```bash
# 1. 克隆仓库
git clone <repo-url> Dailylaid
cd Dailylaid

# 2. 创建 Python 虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

### 依赖说明

`requirements.txt` 中的核心依赖：

| 包 | 用途 |
|------|------|
| `openai>=1.0.0` | LLM API 客户端（兼容 OpenAI 协议） |
| `websockets>=12.0` | WebSocket 连接 NapCat |
| `flask>=2.3.0` | HTTP 服务器（HTTP 适配器模式，当前未启用） |
| `python-dotenv>=1.0.0` | 环境变量管理 |
| `pyyaml>=6.0` | LLM 配置文件解析 |
| `apscheduler>=3.10.0` | 定时提醒服务 |
| `fastmcp>=2.0.0` | MCP 工具服务器 |
| `aiohttp>=3.9.0` | 异步 HTTP 请求 |
| `cairosvg>=2.7.0` | SVG 渲染为 PNG（时间线可视化） |
| `python-dateutil>=2.8.0` | 日期时间处理增强（重复日程规则） |

> [!WARNING]
> `cairosvg` 依赖系统级的 Cairo 库。在 Windows 上你可能需要额外安装 GTK 运行时：
> - 下载 [GTK for Windows Runtime](https://github.com/nickvdp/gtk-for-windows-runtime-environment-installer/releases)
> - 或者使用 `conda install cairo` (如果你使用 Anaconda)
>
> 如果暂时不需要时间线可视化功能，可以忽略此依赖。

---

## 二、配置环境变量

```bash
# 复制示例配置
cp .env.example .env
```

编辑 `.env` 文件，填入以下必要配置：

### 必填配置

```ini
# === LLM API 配置 ===
# 主执行模型的 API Key（用于日程、时间线等功能模块）
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1     # 或兼容接口地址

# === 路由模型的 API Key ===
# 第一层路由使用的轻量模型（意图识别）
ROUTER_API_KEY=your_router_api_key_here
```

### 网络连接配置

```ini
# === NapCat 连接 ===
NAPCAT_MODE=ws_server                        # 推荐：正向 WebSocket
NAPCAT_WS_URL=ws://your-server-ip:3001       # NapCat WS 地址
NAPCAT_WS_TOKEN=your_token_here              # 认证 Token（可选）
```

### 可选配置

```ini
# === 消息过滤（开发测试用） ===
ALLOWED_USERS=123456789                      # 只处理该 QQ 号的消息
ALLOWED_GROUPS=987654321                     # 只处理该群的消息

# === 数据库路径 ===
DATABASE_PATH=data/dailylaid.db              # 默认即可
```

> [!TIP]
> 如果 `ALLOWED_USERS` 和 `ALLOWED_GROUPS` 都不配置，则处理所有消息。
> 建议开发阶段配置过滤，避免意外处理生产消息。

---

## 三、LLM 多模型配置

除了 `.env` 中的基础配置，更细粒度的模型管理在 `llm_config.yaml` 中：

```yaml
models:
  light:      # 轻量级 → 路由/分类
    - name: gemini-lite
      api_key_env: ROUTER_API_KEY     # 读取 .env 中的环境变量名
      base_url: https://aicanapi.com/v1
      model: gemini-2.5-flash-lite-nothinking
  
  standard:   # 标准级 → 日常任务
    - name: gemini-flash
      api_key_env: LLM_API_KEY
      base_url: https://aicanapi.com/v1
      model: gemini-2.5-flash

usage:
  router: light       # 意图路由用轻量模型
  schedule: standard   # 日程用标准模型
  timeline: standard   # 时间线用标准模型
  default: standard    # 默认标准模型
```

**配置要点**：
- 每个模型分组（`light`/`standard`/`advanced`）下可配置多个模型，作为备用（故障切换）
- `api_key_env` 字段指定从 `.env` 读取哪个环境变量作为 API Key
- `usage` 映射决定每个功能模块使用哪个级别的模型

---

## 四、NapCat 远程配置

Dailylaid 使用 **正向 WebSocket** 模式连接 NapCat（推荐）。

### NapCat 端配置

在 NapCat WebUI → 网络配置 → 新建**正向 WebSocket**：

```json
{
  "name": "dailylaid_ws",
  "type": "websocket_server",
  "host": "0.0.0.0",
  "port": 3001,
  "token": "your_secret_token"
}
```

### 本地 `.env` 对应配置

```ini
NAPCAT_MODE=ws_server
NAPCAT_WS_URL=ws://<napcat-server-ip>:3001
NAPCAT_WS_TOKEN=your_secret_token
```

> [!IMPORTANT]
> 本地开发时不需要公网 IP。正向 WS 模式下，是本项目主动连接远程 NapCat，所以只要你能访问到 NapCat 服务器即可。

---

## 五、启动服务

### 方式 1：命令行启动

```bash
# 确保在项目根目录，且虚拟环境已激活
python app.py
```

### 方式 2：批处理启动（Windows）

```bash
# 双击或命令行运行
start.bat
```

### 启动成功日志

```
==================================================
  Dailylaid - 个人日常事务 AI Agent
==================================================
初始化数据库...
初始化 LLM 管理器...
初始化 Agent...
初始化提醒服务...
初始化网络适配器 (模式: ws_server)...
🚀 启动连接...
已连接到 ws://xxx.xxx.xxx:3001
✅ Dailylaid 已启动!
   连接地址: ws://xxx.xxx.xxx:3001
   提醒服务: 已启动 (每分钟检查)
按 Ctrl+C 停止...
```

---

## 六、验证运行

1. **发送测试消息**：在 QQ 中向机器人账号私聊或在允许的群里发消息
2. **日程测试**：发送 "明天下午3点开会"，应收到 `✅ 已添加日程` 回复
3. **时间线测试**：发送 "我10点到11点在写代码"，应收到 `✅ 已记录活动` 回复
4. **快捷命令**：发送 `/help` 查看可用命令
5. **收集箱兜底**：发送任意无法分类的内容，应保存到收集箱

---

## 七、常见问题

### Q: `cairosvg` 安装失败
暂时不需要时间线渲染功能的话，可以从 `requirements.txt` 中注释掉 `cairosvg>=2.7.0`，不影响核心功能。

### Q: WebSocket 连接失败
- 检查 NapCat 是否正在运行且正向 WS 端口已开放
- 检查服务器防火墙是否放通对应端口
- 检查 `.env` 中 `NAPCAT_WS_URL` 地址和 Token 是否正确
- 日志中会自动重试连接，间隔 5 秒

### Q: LLM 调用返回 429 错误
API 配额用尽。检查 API 平台的用量，或在 `llm_config.yaml` 中配置备用模型。

### Q: 消息发出但没有回复
- 检查 `ALLOWED_USERS` / `ALLOWED_GROUPS` 是否包含你的 QQ 号/群号
- 查看 `logs/dailylaid.log` 中是否有 `跳过消息 (不在允许列表)` 日志

---

## 八、开发调试建议

- **日志文件**：`logs/dailylaid.log`，包含详细的 LLM 调用和工具执行记录
- **数据库查看**：使用 DB Browser for SQLite 打开 `data/dailylaid.db`
- **单独测试 LLM**：运行 `python test_llm.py` 验证 API 连通性
- **路由准确性测试**：运行 `python test_router_accuracy.py`

---

*最后更新: 2026-03-11*

# Dailylaid - 项目架构文档

## 📋 项目概述

Dailylaid 是一个基于 QQ 机器人的个人日常事务 AI Agent，通过自然语言交互来管理人情、待办、兴趣收集等日常事务。

## 🎯 核心设计理念

```
QQ消息输入 → LLM 意图识别与分类 → 工具调用执行 → 结果反馈
```

### 消息分类策略

LLM 处理用户输入时，核心分类逻辑：

| 分类 | 说明 | 处理方式 |
|------|------|----------|
| **已支持** | 有对应的处理工具 | 直接调用对应工具执行 |
| **未支持** | 暂无对应的处理工具 | 存入「收集箱」待后续处理 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Dailylaid Agent                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   QQ Input   │    │   LLM Core   │    │   Storage    │      │
│  │   (NapCat)   │───▶│  (意图识别)   │───▶│   (SQLite)   │      │
│  └──────────────┘    └──────┬───────┘    └──────────────┘      │
│                             │                                   │
│                             ▼                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                    工具层 (Tools)                      │      │
│  ├──────────┬──────────┬──────────┬──────────┬─────────┤      │
│  │ 人情管理  │ 待办管理  │ 兴趣收集  │ 收集箱   │   ...   │      │
│  └──────────┴──────────┴──────────┴──────────┴─────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
Dailylaid/
├── README.md                 # 项目说明
├── IDEAS.md                  # 功能想法记录
├── ARCHITECTURE.md           # 本文档
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量（不提交）
├── .env.example              # 环境变量示例
├── .gitignore                # Git 忽略配置
│
├── app.py                    # 主入口：Flask 服务器
├── config.py                 # 全局配置
│
├── core/                     # 核心模块
│   ├── __init__.py
│   ├── agent.py              # Agent 主循环逻辑
│   ├── llm_client.py         # LLM API 客户端
│   ├── classifier.py         # 意图分类器
│   └── memory.py             # 记忆/上下文管理
│
├── tools/                    # 工具层（每个功能一个模块）
│   ├── __init__.py
│   ├── base_tool.py          # 工具基类
│   ├── favor_tool.py         # 人情追踪工具
│   ├── todo_tool.py          # 待办管理工具
│   ├── interest_tool.py      # 兴趣收集工具
│   └── inbox_tool.py         # 收集箱工具
│
├── services/                 # 服务层
│   ├── __init__.py
│   ├── database.py           # 数据库管理
│   └── qq_client.py          # QQ消息发送客户端
│
├── handlers/                 # 消息处理器
│   ├── __init__.py
│   └── message_handler.py    # 消息接收与分发
│
├── data/                     # 数据存储
│   ├── dailylaid.db          # SQLite 数据库
│   └── inbox/                # 收集箱原始消息
│
└── tests/                    # 测试文件
    ├── __init__.py
    └── test_tools.py
```

---

## 🔧 核心组件详解

### 1. 入口层 (app.py)

Flask Web 服务器，接收来自 NapCat 的 HTTP 回调。

```python
# 工作流程
1. 接收 POST 请求 (来自 NapCat)
2. 解析消息内容
3. 调用 Agent 处理
4. 返回响应
```

### 2. Agent 核心 (core/agent.py)

主循环逻辑，协调各组件工作。

```python
class DailylaidAgent:
    def process(self, message: str, user_id: str) -> str:
        # 1. 获取用户上下文
        context = self.memory.get_context(user_id)
        
        # 2. LLM 意图识别
        intent = self.classifier.classify(message, context)
        
        # 3. 路由到对应工具
        if intent.tool_name in self.tools:
            result = self.tools[intent.tool_name].execute(intent.params)
        else:
            result = self.tools['inbox'].save(message)
        
        # 4. 更新记忆
        self.memory.update(user_id, message, result)
        
        return result
```

### 3. LLM 客户端 (core/llm_client.py)

与大语言模型交互。支持多种 API：
- OpenAI 兼容接口
- 本地模型 (Ollama 等)

```python
class LLMClient:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
    
    def chat(self, messages: list, tools: list = None) -> str:
        # 调用 LLM API
        pass
```

### 4. 意图分类器 (core/classifier.py)

通过 LLM 识别用户意图，输出结构化结果。

```python
# 输入: "昨天小王帮我搬家了"
# 输出:
{
    "tool_name": "favor",
    "action": "add",
    "params": {
        "person": "小王",
        "event": "帮我搬家",
        "date": "2026-02-03",
        "direction": "received"  # 我收到的人情
    }
}
```

### 5. 工具层 (tools/)

每个工具负责一类具体功能，统一接口：

```python
class BaseTool:
    name: str
    description: str
    
    def execute(self, params: dict) -> str:
        """执行工具并返回结果文本"""
        raise NotImplementedError
```

---

## 💾 数据库设计

### SQLite 表结构

#### favors - 人情记录表
```sql
CREATE TABLE favors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,          -- QQ号
    person TEXT NOT NULL,           -- 对方名称
    event TEXT NOT NULL,            -- 事件描述
    direction TEXT NOT NULL,        -- 'given'(我给) / 'received'(我收)
    date TEXT,                      -- 日期
    status TEXT DEFAULT 'pending',  -- 'pending' / 'returned'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### todos - 待办表
```sql
CREATE TABLE todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    due_date TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending' / 'done'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### interests - 兴趣记录表
```sql
CREATE TABLE interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,             -- 'blogger' / 'topic' / 'thing'
    name TEXT NOT NULL,
    description TEXT,
    tags TEXT,                      -- JSON数组
    source TEXT,                    -- 来源（哪个平台发现的）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### inbox - 收集箱
```sql
CREATE TABLE inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    raw_message TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔌 外部依赖

### NapCat QQ 机器人框架

- **官方文档**: https://napcat.napneko.icu/develop/api
- **网络配置文档**: https://napcat.napneko.icu/onebot/network
- **部署位置**: 远程服务器

---

## 🌐 网络连接配置 (可配置)

NapCat 支持多种网络连接方式，本项目设计为**可配置**，支持以下 4 种模式：

### 连接模式对比

| 模式 | 通信方向 | 说明 | 适用场景 |
|------|----------|------|----------|
| **HTTP Server** (被动) | NapCat ← 本项目 | 本项目作为 HTTP 服务器，NapCat 调用 API | 需要主动查询 NapCat |
| **HTTP Client** (主动) | NapCat → 本项目 | NapCat 推送事件到本项目的 HTTP 端点 | 传统的 Webhook 模式 |
| **WebSocket Server** (正向WS) | 双向 | 本项目连接到 NapCat 的 WS 服务器 | 开发环境推荐 ⭐ |
| **WebSocket Client** (反向WS) | 双向 | NapCat 连接到本项目的 WS 服务器 | 生产环境常用 |

### 模式详解

#### 模式 1: HTTP Client (主动推送 / Webhook)

传统模式，NapCat 主动将事件推送到本项目的 HTTP 端点。

```
┌─────────────┐  POST /event   ┌─────────────┐
│   NapCat    │ ─────────────▶ │  Dailylaid  │
│  (远程服务器) │                │  (Flask)    │
└─────────────┘                └─────────────┘
       ▲                              │
       │    POST /send_group_msg      │
       └──────────────────────────────┘
```

**NapCat 配置 (WebUI → 网络配置 → 新建 HTTP 客户端):**
```json
{
  "name": "dailylaid_webhook",
  "type": "http_client",
  "url": "http://<your-ip>:7778/",
  "token": "your_secret_token"
}
```

**本项目入口:** `app.py` (Flask)

---

#### 模式 2: WebSocket Server (正向 WS) ⭐ 开发推荐

本项目主动连接到 NapCat 的 WebSocket 服务器，双向通信。

```
┌─────────────┐                ┌─────────────┐
│   NapCat    │ ◀═══ WS ════▶  │  Dailylaid  │
│  (WS Server) │    双向通信    │  (WS Client) │
└─────────────┘                └─────────────┘
```

**NapCat 配置 (WebUI → 网络配置 → 新建 正向 WebSocket):**
```json
{
  "name": "dailylaid_ws",
  "type": "websocket_server",
  "host": "0.0.0.0",
  "port": 3001,
  "token": "your_secret_token"
}
```

**本项目连接地址:** `ws://<napcat-server>:3001`

**优点:**
- ✅ 不需要本机有公网 IP
- ✅ 实时双向通信
- ✅ 开发调试方便

---

#### 模式 3: WebSocket Client (反向 WS)

NapCat 主动连接到本项目的 WebSocket 服务器。

```
┌─────────────┐                ┌─────────────┐
│   NapCat    │ ════ WS ═══▶   │  Dailylaid  │
│ (WS Client)  │    主动连接    │ (WS Server)  │
└─────────────┘                └─────────────┘
```

**NapCat 配置 (WebUI → 网络配置 → 新建 反向 WebSocket):**
```json
{
  "name": "dailylaid_reverse",
  "type": "websocket_client",
  "url": "ws://<your-ip>:7779/onebot/v11/ws",
  "token": "your_secret_token",
  "reconnectInterval": 5000
}
```

**本项目入口:** 需要启动 WebSocket Server (端口 7779)

---

### 目录结构更新

```
services/
├── __init__.py
├── database.py           # 数据库管理
├── qq_client.py          # QQ消息发送客户端 (统一接口)
├── adapters/             # 网络适配器 ⭐ 新增
│   ├── __init__.py
│   ├── base_adapter.py   # 适配器基类
│   ├── http_adapter.py   # HTTP 模式适配器
│   └── ws_adapter.py     # WebSocket 模式适配器
```

### 适配器设计

```python
# services/adapters/base_adapter.py
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    """网络适配器基类"""
    
    @abstractmethod
    async def start(self):
        """启动连接"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止连接"""
        pass
    
    @abstractmethod
    async def send_message(self, target_type: str, target_id: int, message: str):
        """发送消息
        target_type: 'group' | 'private'
        """
        pass
    
    @abstractmethod
    def on_message(self, callback):
        """注册消息回调"""
        pass
```

```python
# services/adapters/ws_adapter.py
import websockets
import asyncio
import json

class WebSocketAdapter(BaseAdapter):
    """WebSocket 正向连接适配器"""
    
    def __init__(self, ws_url: str, token: str = None):
        self.ws_url = ws_url
        self.token = token
        self.ws = None
        self.callbacks = []
    
    async def start(self):
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        self.ws = await websockets.connect(self.ws_url, extra_headers=headers)
        asyncio.create_task(self._listen())
    
    async def _listen(self):
        async for message in self.ws:
            data = json.loads(message)
            for callback in self.callbacks:
                await callback(data)
    
    async def send_message(self, target_type: str, target_id: int, message: str):
        action = "send_group_msg" if target_type == "group" else "send_private_msg"
        id_key = "group_id" if target_type == "group" else "user_id"
        
        payload = {
            "action": action,
            "params": {
                id_key: target_id,
                "message": message
            }
        }
        await self.ws.send(json.dumps(payload))
```

---

## ⚙️ 配置说明

### 环境变量 (.env)

```bash
# === LLM API 配置 ===
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1

# === NapCat 网络配置 ===
# 连接模式: http_client | ws_server | ws_client
NAPCAT_MODE=ws_server

# HTTP 模式配置 (当 NAPCAT_MODE=http_client)
NAPCAT_HTTP_URL=http://your-server-ip:23333
NAPCAT_HTTP_TOKEN=

# WebSocket 正向模式配置 (当 NAPCAT_MODE=ws_server) ⭐ 开发推荐
NAPCAT_WS_URL=ws://your-server-ip:3001
NAPCAT_WS_TOKEN=

# WebSocket 反向模式配置 (当 NAPCAT_MODE=ws_client)
# 本项目作为 WS Server，监听端口
NAPCAT_WS_SERVER_HOST=0.0.0.0
NAPCAT_WS_SERVER_PORT=7779

# === 本地服务配置 ===
SERVER_HOST=0.0.0.0
SERVER_PORT=7778

# === 数据库配置 ===
DATABASE_PATH=data/dailylaid.db
```

---

## 🚀 启动流程

### 开发环境

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 3. 启动服务
python app.py
```

### 与远程 NapCat 联调

1. 确保本机服务已启动并可被远程访问（需要公网IP或内网穿透）
2. 在远程服务器的 NapCat 配置中设置回调 URL
3. 测试消息收发

---

## 📚 参考资源

- **NapCat 开发文档**: https://napcat.napneko.icu/develop/api
- **旧项目参考**: `e:\Project\qq_bot` (已有的 QQ Bot 代码)
- **OpenAI API 文档**: https://platform.openai.com/docs/api-reference

---

*文档版本: 1.0*  
*最后更新: 2026-02-04*

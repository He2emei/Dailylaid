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
- **通信方式**: HTTP 回调 / WebSocket
- **部署位置**: 远程服务器

#### HTTP 回调配置

NapCat 需要配置 HTTP 回调地址，将消息转发到本项目：

```yaml
# NapCat 配置示例
http:
  enable: true
  host: 0.0.0.0
  port: 23333
  post:
    - url: http://<your-server-ip>:7778/
      secret: ""
```

#### 发送消息 API

```python
# 发送群消息
POST http://<napcat-server>:23333/send_group_msg
{
    "group_id": 123456789,
    "message": "Hello World"
}

# 发送私聊消息
POST http://<napcat-server>:23333/send_private_msg
{
    "user_id": 123456789,
    "message": "Hello World"
}
```

---

## ⚙️ 配置说明

### 环境变量 (.env)

```bash
# LLM API 配置
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1

# NapCat 配置
NAPCAT_BASE_URL=http://your-server-ip:23333

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=7778

# 数据库路径
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

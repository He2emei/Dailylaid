# Dailylaid 开发文档导航

> 📚 本目录包含 Dailylaid 项目的所有开发文档，按功能分类组织。

---

## 📁 文档索引

### 🚀 入门指南 (`getting-started/`)

| 文档 | 说明 |
|------|------|
| [dev-environment-setup.md](getting-started/dev-environment-setup.md) | 开发环境搭建、依赖安装、首次启动 |

### 🏗️ 架构解析 (`architecture/`)

| 文档 | 说明 |
|------|------|
| [system-overview.md](architecture/system-overview.md) | 系统架构总览：组件关系、请求生命周期、数据流全景图 |
| [llm-two-layer-architecture.md](architecture/llm-two-layer-architecture.md) | 两层 LLM 路由+执行架构深度解析：Prompt 设计、模型配置、故障切换 |
| [tool-module-system.md](architecture/tool-module-system.md) | 工具与模块注册系统：BaseTool、ToolModule、如何新增工具 |
| [database-design.md](architecture/database-design.md) | 数据库设计：7 张表结构、查询模式、扩展方向 |
| [network-adapter-design.md](architecture/network-adapter-design.md) | 网络适配器设计：WebSocket/HTTP 模式、NapCat 集成、消息协议 |
| [skills-concept-overview.md](architecture/skills-concept-overview.md) | Skills 概念总览：定义、组成、生命周期、与 MCP/Prompt 的对比 |
| [skills-implementation-detail.md](architecture/skills-implementation-detail.md) | Skills 实现细节：数据结构、引擎实现、Agent Loop、YAML 解析 |
| [skills-dailylaid-adaptation.md](architecture/skills-dailylaid-adaptation.md) | Skills 在 Dailylaid 中的适配方案：3 阶段渐进式改造计划 |

### 📏 规范守则 (`standards/`)

| 文档 | 说明 |
|------|------|
| [ai-agent-guidelines.md](ai-agent-guidelines.md) | AI Agent 协作守则：文档规范、Git 提交规范、变基友好原则 |
| [testing-guidelines.md](standards/testing-guidelines.md) | 测试规范与脚本管理机制：pytest配置、自动化与手动调试脚本分离方案 |

### 📅 任务规划 (`plans/`)

| 文档 | 说明 |
|------|------|
| [2026-03-11-debug-group-message.md](plans/2026-03-11-debug-group-message.md) | 群消息处理 Bug 排查与修复 |
| [2026-03-11-organize-tests.md](plans/2026-03-11-organize-tests.md) | 测试脚本整理与 pytest 接入 |
| [2026-03-12-implement-skills.md](plans/2026-03-12-implement-skills.md) | Skills 架构实施（SkillEngine + 多轮 Agent Loop）|

---

## 📖 参考资料 (References)

- **NapCat 开发文档**: https://napcat.napneko.icu/develop/api
- **NapCat 网络配置**: https://napcat.napneko.icu/onebot/network
- **OneBot 11 协议**: https://11.onebot.dev/
- **OpenAI API 文档**: https://platform.openai.com/docs/api-reference
- **OpenAI Function Calling**: https://platform.openai.com/docs/guides/function-calling
- **FastMCP**: https://github.com/jlowin/fastmcp
- **APScheduler 文档**: https://apscheduler.readthedocs.io/

---

*最后更新: 2026-03-12*

# AI Agent 协作守则

本文档规定了 AI Agent（如 Antigravity ）在本项目中执行任务时必须遵守的工作规范。

---

## 1. 每次完成任务必须撰写文档

### 规则

任务完成后，Agent **必须**在 `docs/he2emei/` 对应子目录下撰写或更新相关文档，确保所有工作有据可查。

### 文档存放位置

根据文档类型放入对应子目录：

```
mydir/docs
├── getting-started/    # 🚀 入门 & 环境搭建
├── architecture/       # 🏗️ 架构 & 深度解析
├── standards/          # 📏 规范 & 守则
├── plans/              # 📅 进度 & 任务追踪
└── human-guides/       # 👤 人类独立参考手册
```

| 分类         | 目录               | 放什么                       | 示例                       |
| ------------ | ------------------ | ---------------------------- | -------------------------- |
| **入门指南** | `getting-started/` | 环境搭建、初始配置、快速上手 | `dev-environment-setup.md` |
| **架构解析** | `architecture/`    | 模块分析、设计决策、代码走读 | `gateway-deep-dive.md`     |
| **规范守则** | `standards/`       | 开发规范、提交标准、协作约定 | `ai-agent-guidelines.md`   |
| **任务规划** | `plans/`           | 任务追踪、进度同步、TODO     | `2024-03-20-auth-feat.md`  |
| **人类参考** | `human-guides/`    | 人类独立操作时的实用参考手册 | `daily-workflow.md`        |

> [!IMPORTANT]
> 新建文档后，必须同步更新 `he2emei/docs/README.md` 的导航索引。
> 此外，若涉及到外部关键参考资料（如官方文档、第三方库文档），也应添加到 `README.md` 的 **参考资料 (References)** 章节，方便 subsequent agents 快速查阅。

### 文档格式要求

| 要求     | 说明                                             |
| -------- | ------------------------------------------------ |
| **格式** | Markdown (.md)                                   |
| **命名** | 小写英文 + 连字符，如 `dev-environment-setup.md` |
| **语言** | 中文为主，技术术语保留英文                       |
| **内容** | 包含：背景说明、实现细节、关键决策、使用示例     |
| **时效** | 文档末尾标注 `*最后更新: YYYY-MM-DD*`            |

### 文档类型

- **配置/环境类** → `getting-started/` — 记录搭建步骤、前置依赖、常见问题
- **功能实现类** → `architecture/` — 记录设计决策、架构说明、接口定义
- **规范约定类** → `standards/` — 记录团队规范、工作流程、协作约定
- **任务进度类** → `plans/` — 记录任务计划、执行状态、下一步行动
- **问题排查类** → `getting-started/` 或 `architecture/` — 记录问题、排查过程、解决方案
- **人类参考类** → `human-guides/` — 人类在不依赖 AI Agent 的情况下独立操作项目时的参考手册

> [!CAUTION]
> 文档是知识传承的核心。没有文档的工作等于没有做。

### `human-guides/` 目录说明

此目录专门存放**人类开发者在没有 AI Agent 辅助的情况下**，独立操作、维护项目时所需的参考资料。

与其他文档目录不同，`human-guides/` 的读者是**人类本身**，因此文档应：

- **步骤化**：提供可直接跟随执行的操作步骤
- **自包含**：尽量减少对其他文档的依赖，可以独立阅读
- **实用优先**：以「用得上」为第一原则，避免过度抽象

#### 推荐包含的指南

| 指南文件                    | 内容说明                                                       |
| --------------------------- | -------------------------------------------------------------- |
| `project-overview.md`       | 项目全景图：目录结构、模块关系、技术栈一览                     |
| `daily-workflow.md`         | 日常开发工作流：拉取/推送代码、分支管理、常用命令速查          |
| `config-reference.md`       | 配置项速查：所有可调参数的含义、默认值与修改方法               |
| `troubleshooting.md`        | 常见故障排查手册：报错信息 → 可能原因 → 解决方案               |
| `deployment-checklist.md`   | 部署与发布检查清单：从构建到上线的逐步检查项                   |
| `working-with-ai-agents.md` | 如何与 AI Agent 高效协作：提示词技巧、最佳实践、注意事项       |

> [!TIP]
> Agent 在完成任务时，如果发现某些知识对人类独立操作非常关键，应主动将其整理到 `human-guides/` 中。

---

## 2. 任务启动前必须建立计划文档

### 规则

在开始任何复杂任务（超过 3 个步骤或跨越多次对话）前，Agent **必须**在 `he2emei/docs/plans/` 目录下创建计划文档。

### 目的

1. **消除信息差**：确保用户和 Agent 对任务目标、进度、阻碍有一致的理解。
2. **进度找回**：当用户开启新对话时，可以通过阅读该文档快速恢复上下文，继续未完成的任务。

### 文档规范

- **命名**：`YYYY-MM-DD-<task-name>.md` (例如 `2024-03-20-implement-auth.md`)
- **内容模板**：

```markdown
# [Task Name]

**状态**: `进行中` | `已完成` | `挂起`
**创建日期**: YYYY-MM-DD

## 背景 (Context)
简要描述任务背景和目标。

## 计划 (Plan)
- [x] 阶段 1
- [ ] 阶段 2 (Current)
- [ ] 阶段 3

## 当前进展 (Progress)
*记录最新的进展、遇到的问题或待确认事项。*
```

### 维护规则

- **实时更新**：每次 Task Boundary 变更或对话结束前，务必更新 "当前进展" 和勾选 "计划" 列表。
- **归档**：任务完成后，将状态标记为 `已完成`。

---

## 3. 每次完成任务必须提交代码

### 规则

所有代码变更必须通过 Git 提交，且提交信息必须遵循 **Conventional Commits** 规范。

### 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 各字段说明

#### type（必填）

| 类型       | 用途                    |
| ---------- | ----------------------- |
| `feat`     | 新功能                  |
| `fix`      | 修复 bug                |
| `docs`     | 仅文档变更              |
| `style`    | 代码格式（不影响逻辑）  |
| `refactor` | 重构（非 feat、非 fix） |
| `test`     | 添加或修改测试          |
| `chore`    | 构建、工具、依赖等杂项  |

#### scope（推荐填写）

范围标识受影响的模块，例如：

- `herqq` — herQQ 渠道插件
- `gateway` — Gateway 核心
- `config` — 配置系统
- `he2emei` — He2emei 文档

#### subject（必填）

- 使用英文动词原形开头（如 `add`, `fix`, `update`, `remove`）
- 不超过 72 个字符
- 不以句号结尾
- 言简意赅地描述变更内容

#### body（推荐填写）

- 详细描述变更内容和动机
- 列出关键修改的文件和组件
- 一行不超过 100 个字符

#### footer（可选）

- 关联 Issue：`Closes #123`
- 破坏性变更：`BREAKING CHANGE: <description>`

### 提交示例

#### 好的提交 ✅

```
feat(herqq): add QQ channel integration via NapCat OneBot 11

- Implement herQQ channel plugin with 13 source files
- Support private chat messaging (group chat deferred)

Key components:
  extensions/herqq/src/channel.ts   - ChannelPlugin implementation
  extensions/herqq/src/onebot-client.ts - OneBot HTTP API client
```

```
docs(he2emei): reorganize documentation into categorized structure

Move flat docs into getting-started/, architecture/, standards/
subdirectories. Add README.md with navigation index.
```

```
fix(herqq): resolve TypeScript type errors in channel plugin

- Fix runtime.ts to use PluginRuntime instead of RuntimeEnv
- Fix outbound sendText return type to match OutboundDeliveryResult
```

#### 不好的提交 ❌

```
update files          # 太模糊
fixed stuff           # 没有说明修了什么
WIP                   # 不应该提交半成品
add herqq plugin and fix some bugs and update docs  # 应该分开提交
```

### 提交流程

```bash
# 1. 查看变更
git status
git diff

# 2. 暂存文件（按逻辑分组）
git add <相关文件>

# 3. 提交（使用规范格式）
git commit -m "<type>(<scope>): <subject>" -m "<body>"

# 4. 如果需要，推送到远程
git push
```

> [!WARNING]
> **禁止**在一个提交中混合不相关的变更。功能代码、文档、修复应分开提交。

---

_最后更新: 2026-03-16_

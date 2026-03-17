# 双开环境隔离指南

*为了保障日常使用机器人免受开发调试的干扰，我们在同一台机器上设立了两套独立的环境。*

---

## 🏗 环境划分与目录结构

本项目实行 **开发** 与 **生产** 的目录级分离：

1. **生产环境 (Production)**
   - 📍 目录：`myAIApp/Dailylaid`
   - ✅ 作用：日常使用，对接真实的数据库和主 QQ 机器人。
   - ⚠️ 规则：严禁在此目录下直接写代码调试。必须在开发环境测试无误后再 `git pull` 部署。

2. **开发环境 (Development)**
   - 📍 目录：`myAIApp/Dailylaid_Dev`
   - ✅ 作用：调试新功能、修 Bug。
   - 🛠 规则：连接独立的测试数据库、测试端口、测试 QQ 机器人，随意报错无顾忌。

---

## ⚙️ .env 独立配置差异表

两个目录在代码层面通过 Git 保持同步，但根目录下的 `.env` 文件是**相互隔离的（被 `.gitignore` 忽略）**。

因此，两者的独立配置文件存在以下差异：

| 配置项 | 生产环境 (`Dailylaid`) | 开发环境 (`Dailylaid_Dev`) | 说明 |
| :--- | :--- | :--- | :--- |
| **`SERVER_PORT`** | `7778` | **`7779`** 或者其他 | 本地 Flask 后端监听端口，必须错开以免端口被占用 |
| **`DATABASE_PATH`** | `data/dailylaid.db` | **`data/test_dailylaid.db`** | **最核心差异**：数据库绝对隔离，开发环境怎么折腾都不会污染真实待办数据 |
| **`NAPCAT_WS_URL`** | `ws://ip:23334` (主 QQ) | 另起测试 NapCat 实例 (测试 QQ) | 建议开发过程使用小号机器人，若共用同一个 NapCat 可能会导致主进程回复错位 |
| **`ALLOWED_USERS`** | `你的常用大号QQ` | `你的备用/测试账号` | 防止测试过程由于命令泛滥影响大号使用体验 |

> [!IMPORTANT]
> - 由于两个环境的数据隔离完全依赖于忽略 `data/` 目录和 `.env` 的同名文件隔离，请**千万避免**将任何带有绝密信息或指向生产数据库路径的文件硬编码提交到 Git 仓库上。
> - 在 `Dailylaid_Dev` 下通过 `python app.py` 启动开发测试，测试完毕只需提交代码。
> - 切换到 `Dailylaid` 目录执行 `git pull` 后重启应用，即可让主大号获得最新功能！

---

## 🔀 Git Remote 与代码同步

两个本地仓库通过 **GitHub** 作为中转进行代码同步：

```
Dailylaid_Dev  ──push──▶  GitHub  ◀──pull──  Dailylaid
 (开发端)          (git@github.com:He2emei/Dailylaid.git)     (生产端)
```

### Remote 配置

| 仓库 | Remote 名 | 指向 | 用途 |
|------|----------|------|------|
| `Dailylaid_Dev` | `origin` | `git@github.com:He2emei/Dailylaid.git` | 开发完成后 push 到 GitHub |
| `Dailylaid_Dev` | `production` | `E:/Project/myAIApp/Dailylaid` | 本地生产仓库（仅保留，不直接 push） |
| `Dailylaid` | `origin` | `git@github.com:He2emei/Dailylaid.git` | 从 GitHub pull 最新代码 |

### 日常同步流程

```bash
# 1. 在开发端完成开发、提交
cd Dailylaid_Dev
git add .
git commit -m "feat(xxx): ..."
git push origin master

# 2. 在生产端拉取最新代码
cd Dailylaid
git pull origin master

# 3. 重启生产环境的 app
```

> [!WARNING]
> 不要直接从 Dev push 到本地 Production（`git push production master`），因为 Production 是 non-bare 仓库且 master 已签出，会被 Git 拒绝。

---

*最后更新: 2026-03-18*

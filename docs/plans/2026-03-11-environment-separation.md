# 建立开发与生产环境隔离 (Development Environment Separation)

**状态**: `进行中`
**创建日期**: 2026-03-11

## 背景 (Context)
随着 Dailylaid 项目的逐步成型，用户希望能在日常使用稳定性的同时，安全地开发新功能及进行调试测试。因此需要在原有的 `Dailylaid`（生产环境）外，分离出一个 `Dailylaid_Dev`（开发环境），并相应隔离端口、数据库等容易冲突的配置。

## 计划 (Plan)
- [ ] 阶段 1：在 `Dailylaid` 中编写环境分离说明文档（`environment-separation.md`）并更新 `docs/README.md`。
- [ ] 阶段 2：克隆 `Dailylaid` 代码库至 `Dailylaid_Dev` 目录。
- [ ] 阶段 3：在 `Dailylaid_Dev` 中修改 `.env` 文件（更改服务端端口、WebSocket 端口、数据库名称）。
- [ ] 阶段 4：在 `Dailylaid` 中提交文档。

## 当前进展 (Progress)
*2026-03-11*: 读取生产环境 `.env` 配置并记录环境隔离指南文档。

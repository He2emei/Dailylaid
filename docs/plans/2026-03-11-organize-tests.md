# 规整测试脚本与测试管理方案

**状态**: `进行中`
**创建日期**: 2026-03-11

## 背景 (Context)
当前 Dailylaid 项目的根目录下散落了大量的 `test_*.py` 脚本（如 `test_llm.py`, `test_schedule.py`）以及运行这些脚本产生的图像输出（`.svg`, `.png`）。
这些脚本实际上并非自动化测试（Unit Tests），而是用于功能调试、接口调通的手动小脚本。
因此，需要一套相对成熟的测试管理方案，将自动化测试与手动脚本分离，清理根目录，并引入标准测试框架。

## 计划 (Plan)
- [x] 阶段 1：审查现有测试文件，制定目录结构规划。
- [x] 阶段 2：用户评审测试方案（`implementation_plan.md`）。
- [x] 阶段 3 (Current)：新建 `scripts/manual_tests/` 与 `tests/` 目录结构。
- [x] 阶段 4：将现有的 11 个手工测试脚本移动到 `scripts/manual_tests/`，并修改其 imports (`sys.path.insert`)。
- [x] 阶段 5：清理根目录下的 `.svg` 与 `.png` 临时输出文件，更新 `.gitignore`。
- [x] 阶段 6：引入并配置 `pytest`，创建 `pytest.ini` 和基础 `tests/conftest.py`。
- [x] 阶段 7：验证脚本运行与 Git 提交。

## 当前进展 (Progress)
*2026-03-11 16:21*: 已完成现有文件的审查并起草了架构调整计划。正在等待用户评审成熟的测试管理方案。

# 测试规范与脚本管理机制

本文档说明了 Dailylaid 项目的自动化测试及调试脚本分类管理机制。

---

## 📐 目录划分

在项目的测试和调试体系中，我们严格区分两类代码：“临时功能测试脚本” 和 “自动化回归测试”。
目录主要切分为：

```text
Dailylaid/
├── scripts/
│   └── manual_tests/      # 手动功能验证与临时调试脚本
├── tests/                 # 自动化测试目录（供 pytest 使用）
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── conftest.py        # 全局测试夹具 (fixtures)
└── tmp/                   # 测试输出或临时文件的存放区
```

### 1. 自动化测试 (`tests/`)
这里存放每次提交前应当验证通过的稳定测试代码，统一使用 `pytest` 框架执管。

**规则**：
- 测试文件必须以 `test_` 开头。
- 测试函数必须以 `test_` 开头。
- 禁止在 `tests/` 下存放运行时会产生永久副作用的脚本。
- **运行命令**：在项目根目录执行 `pytest` 即可自动执行所有用例。

### 2. 手工调试脚本 (`scripts/manual_tests/`)
这一层放置的是：开发功能过程的中间产物、特定场景连通性调测代码（如直跑 LLM 确认 Prompt、手动往数据库里塞模拟数据）。此类脚本通常仅由当前开发者按需用 `python` 直接运行。

**规则**：
- 它们必须能作为 Python 模块独立运行（例如：在根目录下执行 `python scripts/manual_tests/test_schedule.py`）。
- 任何调试生成的附件输出（如 `.svg`, `.png` 视觉图）**必须输出到 `/tmp/` 目录**中，以防止向 Git 错误提交垃圾文件。
- 不要在根目录直接放调试用的 `*.py`。

---

## 🛠 `pytest` 测试框架应用

我们引入 `pytest` 来接管所有的自动化测试流程。相比起传统的 `unittest`，它的语法更简洁且夹具设计更具灵活性。

### 全局配置
项目根目录下的 `pytest.ini` 定义了 pytest 的行为，它默认会扫描 `tests/` 目录下的用例：
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### 测试夹具 (Fixtures) 与 `conftest.py`
`tests/conftest.py` 会在所有测试前被加载。
这十分适合用于初始化“内存型数据库（Mock DB）”或“配置单例”。你可以编写 fixture 函数并在其它用例中通过参数名直接拿取实例：

```python
# conftest.py 示例
import pytest
from services.database import DatabaseManager

@pytest.fixture
def test_db():
    # 比如在真实操作中，这可以连接到一个全内存的 sqlite 库如 :memory:
    db = DatabaseManager("data/test_dailylaid.db")
    yield db
    # setup 和 teardown 由 yield 两侧分隔
    # db.close() 等等
```

```python
# tests/unit/test_demo.py
def test_schedule_insertion(test_db):
    result = test_db.insert_schedule({...})
    assert result > 0
```

---

*最后更新: 2026-03-11*

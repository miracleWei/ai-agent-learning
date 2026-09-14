# Day 1 · Python 环境与项目结构

## 今日目标

> 不求成为 Python 专家，只求：**能读懂 AI 项目的 Python 目录，并能自己写出一个能跑起来的 Python 程序。**

## 知识点

| # | 知识点 | 对应文件 |
| --- | --- | --- |
| 1 | Python 安装 & 版本管理 | `env_check.py` |
| 2 | `pip` vs `uv` | - |
| 3 | 虚拟环境（venv）为什么必需 | - |
| 4 | Python 项目结构：模块 / 包 / 入口 | `greeter/` |
| 5 | 函数定义与 f-string | `hello.py` |

---

## 任务清单

### 任务 1（必做）：第一个 Python 函数

文件：`hello.py`

```python
def hello(name):
    return f"Hello {name}"
```

验收：`python day01_python_basics\hello.py` 能打印出问候语。

### 任务 2（必做）：环境自检脚本

文件：`env_check.py`

要求程序能报告：

- Python 版本（并判断是否 >= 3.11）
- 当前解释器路径
- 是否运行在虚拟环境中
- 操作系统

验收：`python day01_python_basics\env_check.py` 有完整输出。

### 任务 3（必做）：理解「包」

文件：`greeter/`（`__init__.py` + `core.py` + `__main__.py`）

验收（在**仓库根目录**执行）：

```powershell
python -m day01_python_basics.greeter Tom
# 输出：Hello Tom

python -m day01_python_basics.greeter
# 输出：Hello World
```

同时能回答下面这个问题：

> 为什么 `python -m day01_python_basics.greeter` 里能写 `from .core import hello`，
> 但直接 `python day01_python_basics\greeter\__main__.py` 却报错：
> `ImportError: attempted relative import with no known parent package`？
>
> 提示：**以脚本运行** 和 **以模块运行（-m）**，Python 设置的 `__package__` 不一样。

### 任务 4（进阶）：自己造一个包

新建 `day01_python_basics\mathx\`，包含：

- `__init__.py`
- `core.py`：实现 `add` / `sub` / `mul` / `div`
- `__main__.py`：读取两个命令行参数并打印四则运算结果

验收：`python -m day01_python_basics.mathx 6 3` 输出 `9 / 3 / 18 / 2.0`。

---

## 思考题

1. 为什么 AI 项目几乎不会把依赖装到全局 Python 里？
2. `pip` 和 `uv` 的区别是什么？为什么现在更推荐 `uv`？
3. `if __name__ == "__main__":` 这行到底在做什么？
4. Python 里「模块（module）」和「包（package）」的区别是什么？

## 面试题

1. Python 的虚拟环境解决了什么问题？
2. `python -m package.module` 和 `python path/to/module.py` 有什么区别？
3. 为什么 Python 项目要有 `pyproject.toml`？

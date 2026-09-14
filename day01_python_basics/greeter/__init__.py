"""Day 1 · 任务 3：一个标准的 Python「包」。

一个目录只要有 ``__init__.py``，Python 就把它当成 **package（包）**。

``__init__.py`` 的作用：
    1. 标记这个目录是包（Python 3.3+ 有「命名空间包」可以不写，但显式写更清晰）
    2. 包被 import 时会执行这里的代码
    3. 通常在这里做「对外暴露」的整理，让使用者不用关心内部文件结构

对应 Java：类似于 ``package com.example.greeter;`` 这层声明，
            但 ``__init__.py`` 还额外承担了「包的公开 API」的职责。
"""

from .core import DEFAULT_TARGET, hello

# __all__ 决定 `from greeter import *` 时导出什么
__all__ = ["hello", "DEFAULT_TARGET"]

__version__ = "0.1.0"

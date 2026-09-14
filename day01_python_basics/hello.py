"""Day 1 · 任务 1：第一个 Python 函数。

运行：
    python day01_python_basics/hello.py
"""

from __future__ import annotations


def hello(name: str) -> str:
    """返回一句问候语。

    Args:
        name: 要问候的名字。

    Returns:
        形如 ``"Hello Tom"`` 的字符串。

    Notes:
        ``f"..."`` 是 Python 3.6+ 的 **f-string**，把 ``{变量}`` 直接嵌进字符串，
        比 Java 的 ``"Hello " + name`` 或 ``String.format`` 更简洁。
    """
    return f"Hello {name}"


# 这是 Python 的「程序入口」惯例：
#   - 直接运行本文件时      → __name__ 等于 "__main__"，下面的代码会执行
#   - 被别的文件 import 时  → __name__ 等于 "hello"，下面的代码不会执行
#
# 对应 Java：相当于只有一个 main 方法会在被调用时运行，
#            而不是被 import 的时候就自动跑起来。
if __name__ == "__main__":
    print(hello("World"))
    print(hello("Agent"))

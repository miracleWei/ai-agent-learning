"""greeter 包的核心逻辑。

对应 Java：相当于 service / 业务实现类所在的文件。
"""

from __future__ import annotations

DEFAULT_TARGET = "World"


def hello(name: str = DEFAULT_TARGET) -> str:
    """返回问候语。

    Args:
        name: 要问候的名字，默认 ``"World"``。

    Returns:
        形如 ``"Hello Tom"`` 的字符串。
    """
    name = (name or "").strip()
    if not name:
        name = DEFAULT_TARGET
    return f"Hello {name}"

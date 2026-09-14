"""greeter 包的命令行入口。

``__main__.py`` 是这个包被「**当模块运行**」时执行的入口文件（在仓库根目录执行）：

    python -m day01_python_basics.greeter Tom

此时 Python 把 ``day01_python_basics.greeter`` 解析成一个**包**，
``__package__ == "day01_python_basics.greeter"``，
所以下面用 **相对导入** ``from .core import hello`` 是合法的。

⚠️ 两个反例，都会报 ``ImportError: attempted relative import with no known parent package``：

    python day01_python_basics/greeter/__main__.py Tom
    python day01_python_basics/greeter Tom

原因：这两种写法 Python 都把它当**脚本**执行，``__package__`` 为空，
没有「父包」这个概念，``.core`` 自然无从解析。

对应 Java：
    以模块运行 ≈ ``java -cp . com.example.greeter.Main``
    以脚本运行 ≈ ``java -cp . Main``（丢了包名）
"""

from __future__ import annotations

import sys

from .core import DEFAULT_TARGET, hello


def main(argv: list[str] | None = None) -> None:
    """命令行入口。

    Args:
        argv: 参数列表（不含程序名），默认取 ``sys.argv[1:]``。
    """
    args = sys.argv[1:] if argv is None else argv
    name = args[0] if args else DEFAULT_TARGET
    print(hello(name))


if __name__ == "__main__":
    main()

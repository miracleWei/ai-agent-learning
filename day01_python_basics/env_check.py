"""Day 1 · 任务 2：环境自检脚本。

运行：
    python day01_python_basics/env_check.py

它会告诉我们三件事：
    1. 当前用的是哪个 Python（版本 / 路径）
    2. 有没有在虚拟环境里
    3. 依赖装到哪里去了
"""

from __future__ import annotations

import platform
import sys

MIN_VERSION = (3, 11)


def get_env_report() -> dict[str, str]:
    """收集当前 Python 环境信息。"""
    version_info = sys.version_info
    version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    # 判断是否在虚拟环境中：
    #   系统 Python 的 sys.prefix == sys.base_prefix
    #   虚拟环境里      sys.prefix 指向 .venv 目录，与 base_prefix 不同
    in_venv = sys.prefix != sys.base_prefix

    return {
        "Python 版本": version,
        "是否满足 >= 3.11": "✅ 是" if version_info[:2] >= MIN_VERSION else "❌ 否",
        "解释器路径": sys.executable,
        "运行模式": "虚拟环境" if in_venv else "全局（system）环境",
        "虚拟环境路径": sys.prefix if in_venv else "-",
        "操作系统": f"{platform.system()} {platform.release()} ({platform.machine()})",
        # 第三方库的安装位置：虚拟环境下应该指向 .venv
        "依赖安装位置": [p for p in sys.path if p.endswith(("site-packages", "dist-packages"))][:1]
        or ["-"],
    }


def main() -> None:
    report = get_env_report()

    print("=" * 60)
    print("  Python 环境自检")
    print("=" * 60)
    for key, value in report.items():
        if isinstance(value, list):
            value = value[0]
        print(f"  {key:<18}: {value}")
    print("=" * 60)

    if report["运行模式"].startswith("全局"):
        print("\n⚠️  当前没有使用虚拟环境！")
        print("   请先执行：uv venv   然后激活 .venv\\Scripts\\Activate.ps1")


if __name__ == "__main__":
    main()

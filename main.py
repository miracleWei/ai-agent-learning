"""Day 1 · 最小可运行示例：亲手体验「Python → LLM → 回答」。

它演示三个层次，正好对应学习计划里的第三步：

    demo1  最原始写法：5 行代码直接调通          （先让它跑起来）
    demo2  封装成类：LLMClient.chat()             （可复用）
    demo3  流式输出：LLMClient.chat_stream()      （像 ChatGPT 那样逐字蹦）

运行：
    uv run python main.py          # 依次跑完三个 demo
    uv run python main.py 2        # 只跑 demo2
"""

from __future__ import annotations

import os
import sys
import time

from llm_client import LLMClient, LLMError

# 每个 demo 用的问题
QUESTION_SIMPLE = "你好，请用一句话介绍一下你自己。"
QUESTION_CLASS = "请解释一下什么是 Java Spring Boot，假设我是初学者，200 字以内。"
QUESTION_STREAM = "请用 100 字左右介绍一下 JVM 的垃圾回收机制。"


def demo1_raw_sdk() -> None:
    """最原始的方式：直接用 openai SDK，不封装。

    这就是计划里第 6 步那段代码。目的是让你看清：
    所谓「调用大模型」，本质就是一次 HTTP 请求。
    """
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
    )

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        messages=[{"role": "user", "content": QUESTION_SIMPLE}],
    )
    print(response.choices[0].message.content)


def demo2_class() -> None:
    """封装成类之后：调用方不用再关心 Key、地址、模型名。"""
    llm = LLMClient()
    print(llm.chat(QUESTION_CLASS))
    print(f"\n[{llm.usage_text()}]")


def demo3_stream() -> None:
    """流式输出：边生成边显示，这正是 ChatGPT 网页版的效果。

    关键点：`flush=True` 强制立即刷新缓冲区，否则你会看到文字卡住不动，
    最后一次性全冒出来 —— 那就失去流式的意义了。
    """
    llm = LLMClient()
    start = time.perf_counter()
    for piece in llm.chat_stream(QUESTION_STREAM):
        print(piece, end="", flush=True)
    elapsed = time.perf_counter() - start
    print(f"\n\n[{elapsed:.1f}s · {llm.usage_text()}]")


DEMOS = {
    "1": ("最原始写法（直接调 SDK）", demo1_raw_sdk),
    "2": ("封装成 LLMClient 类", demo2_class),
    "3": ("流式输出 Streaming", demo3_stream),
}


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = list(DEMOS) if which == "all" else [which]

    for key in targets:
        if key not in DEMOS:
            print(f"未知的 demo 编号：{key}（可选 1 / 2 / 3 / all）")
            return 2
        title, func = DEMOS[key]
        print("=" * 64)
        print(f"  Demo {key} · {title}")
        print("=" * 64)
        try:
            func()
        except LLMError as exc:
            print(exc)
            print("\n提示：先把 .env 里的 LLM_API_KEY 填好再运行。")
            return 1
        except KeyboardInterrupt:
            print("\n已中断")
            return 130
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

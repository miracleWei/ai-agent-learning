"""Day 1 · Challenge：一个带记忆的命令行 AI 对话程序。

它比 main.py 多了两个关键能力：

    1. Streaming        —— 回答逐字显示（体验）
    2. Conversation History —— 记住上下文（**这是 Agent Memory 的最初形态**）

为什么「记忆」这么重要？

    大模型 API 是**无状态**的。你不把历史发过去，它就完全不知道刚才聊了什么：

        第 1 轮  发送：[我叫 Jack]                      → 回答「你好 Jack」
        第 2 轮  发送：[我叫什么？]                     → 回答「我不知道你叫什么」
        第 2 轮  发送：[我叫 Jack, 你叫... , 我叫什么？] → 回答「你叫 Jack」

    所以「记忆」不是模型记住了，而是**我们每一轮都把历史重新发了一遍**。

Java 类比
    这个 messages 列表 ≈ 存在 Redis 里的会话上下文
    （对应 Spring Session / ChatMemory）

运行：
    uv run python chat.py                 # 流式输出（默认）
    uv run python chat.py --no-stream     # 一次性输出，方便看 token 用量
    uv run python chat.py --system "你是一个仅用古文回答的助手"

对话中的命令：
    /clear    清空上下文，重新开始
    /history  查看当前上下文条数
    /help     查看帮助
    exit      退出
"""

from __future__ import annotations

import argparse
import sys
import time

from llm_client import LLMClient, LLMError, Message

# 系统提示词：决定 AI 的「人设」与回答风格
DEFAULT_SYSTEM_PROMPT = (
    "你是一位耐心、务实的技术导师，面向有 Java 后端工程背景的工程师讲解 AI 知识。"
    "回答要简洁准确，善用 Java 世界的类比帮助理解，不要啰嗦。"
)

EXIT_WORDS = {"exit", "quit", "bye", "/exit", "/quit", ":q"}

HELP_TEXT = """
可用命令：
  /clear    清空上下文，重新开始对话
  /history  查看当前上下文条数与内容概览
  /help     显示本帮助
  exit      退出程序
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="命令行 AI 对话（带上下文记忆）")
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="关闭流式输出（一次性返回，便于查看 token 用量）",
    )
    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM_PROMPT,
        help="自定义系统提示词",
    )
    return parser.parse_args()


def show_history(messages: list[Message]) -> None:
    """打印当前上下文概览，肉眼确认「记忆」确实在累积。"""
    if not messages:
        print("[上下文为空]")
        return
    print(f"[当前上下文共 {len(messages)} 条]")
    for i, msg in enumerate(messages, 1):
        content = msg["content"].replace("\n", " ")
        preview = content[:36] + ("..." if len(content) > 36 else "")
        print(f"  {i}. {msg['role']:<9} {preview}")


def main() -> int:
    args = parse_args()

    # ---- 1. 初始化客户端（配置错误在这里就会友好报错，而不是堆栈）----
    try:
        llm = LLMClient()
    except LLMError as exc:
        print(exc)
        return 1

    stream_mode = not args.no_stream
    print("=" * 64)
    print("  CLI AI Chat · Day 1 Challenge")
    print("=" * 64)
    print(f"  {llm.config.describe()}")
    print(f"  输出模式：{'流式 Streaming' if stream_mode else '一次性'}")
    print("  输入 exit 退出，/help 查看命令")
    print("=" * 64)

    # ---- 2. 上下文列表：整个程序的「记忆」就是它 ----
    messages: list[Message] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})

    while True:
        # ---- 读取用户输入 ----
        try:
            raw = input("\n你：")
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        text = raw.strip()
        if not text:
            continue
        if text.lower() in EXIT_WORDS:
            print("再见！")
            break

        # ---- 斜杠命令 ----
        if text.startswith("/"):
            command = text.lower()
            if command == "/clear":
                messages = [{"role": "system", "content": args.system}] if args.system else []
                print("[已清空上下文]")
            elif command == "/history":
                show_history(messages)
            elif command == "/help":
                print(HELP_TEXT)
            else:
                print(f"[未知命令：{text}，输入 /help 查看可用命令]")
            continue

        # ---- 3. 把用户这句话追加进上下文 ----
        messages.append({"role": "user", "content": text})

        print("AI：", end="", flush=True)
        start = time.perf_counter()
        pieces: list[str] = []

        try:
            if stream_mode:
                for piece in llm.chat_stream(messages):
                    pieces.append(piece)
                    print(piece, end="", flush=True)
            else:
                answer = llm.chat(messages)
                pieces.append(answer)
                print(answer)
        except LLMError as exc:
            # 关键细节：请求失败时把刚才那句话**回滚**，
            # 否则上下文里会留下一个没有回答的 user 消息，污染后续对话。
            messages.pop()
            print(f"\n{exc}")
            continue
        except KeyboardInterrupt:
            messages.pop()
            print("\n[已取消本次回答]")
            continue

        elapsed = time.perf_counter() - start
        print()

        # ---- 4. 把 AI 的回答也追加进上下文，形成完整的一轮 ----
        messages.append({"role": "assistant", "content": "".join(pieces)})

        # ---- 5. 状态栏：耗时 / token / 上下文长度 ----
        print(f"[{elapsed:.1f}s · {llm.usage_text()} · 上下文 {len(messages)} 条]")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Day 1 · v4 —— 加记忆（Conversation History）⭐ 今天的核心

相比 v3，只加了 3 件事：

    ① 循环外面建一个 messages 列表
    ② 每轮把【用户说的】append 进去，然后把这个完整列表发给模型
    ③ 拿到回答后，把【模型说的】也 append 进去

就这 3 步，AI 从"每次都是第一次见你"变成"记得你叫 Jack"。

效果：
    你：我叫 Jack
    AI：你好 Jack！
    你：我叫什么？
    AI：你叫 Jack。        ← ✅ 记住了！

运行：
    uv run python day01_llm_basics/my_chat_v4.py

⭐ 请务必亲手试这个对话，并留意每轮打印的"上下文 N 条"在增长：
    你：我叫 Jack
    你：我现在在北京
    你：我叫什么？我在哪？
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or "https://api.deepseek.com",
)

MODEL = os.getenv("LLM_MODEL") or "deepseek-chat"

# ① ⭐ 记忆就是这个列表 —— 没有别的东西了
#
#    它放在循环【外面】，所以在整个程序运行期间一直存在，
#    不会因为进入下一轮循环而被清空。
#    （放里面就每次都重新开始，等于没有记忆 —— 可以自己改一下试试）
messages: list[dict] = [
    # system 消息是"人设"，可选。它不参与对话内容，但会影响回答风格。
    {"role": "system", "content": "你是一位简洁的助手，回答控制在两句话以内。"},
]

print("=" * 50)
print("  v4 · 有记忆的连续对话")
print("  输入 exit 退出，history 查看上下文")
print("=" * 50)

while True:
    try:
        text = input("\n你：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n再见！")
        break

    if not text:
        continue
    if text.lower() == "exit":
        print("再见！")
        break

    # 小工具：把上下文摊开给你看，亲眼确认"记忆"确实在累积
    if text.lower() == "history":
        print(f"[当前上下文共 {len(messages)} 条]")
        for i, m in enumerate(messages, 1):
            preview = m["content"].replace("\n", " ")[:30]
            print(f"  {i}. {m['role']:<9} {preview}")
        continue

    # ② ⭐ 把用户这句话追加进历史
    #
    #    一定要在【发请求之前】追加，否则模型看不到这句话。
    messages.append({"role": "user", "content": text})

    # ③ ⭐ 把【整个列表】发过去，而不是只发最后一句
    #
    #    这是 v3 和 v4 唯一的关键差异：
    #        v3:  messages=[{"role": "user", "content": text}]
    #        v4:  messages=messages          ← 全部历史！
    #
    #    模型本身是无状态的，它不会"记得"任何东西。
    #    所谓记忆，就是【我们每一轮都把历史重新发了一遍】。
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    answer = response.choices[0].message.content or ""
    print("AI：", answer, flush=True)

    # ④ ⭐ 把模型的回答也追加进历史
    #
    #    为什么必须也存？
    #    因为下一轮发过去的历史里，如果有"用户问过什么"却没有"模型答过什么"，
    #    模型会看到一串连续的 user 消息，上下文就残缺了。
    #    一轮完整的对话 = user + assistant 成对出现。
    messages.append({"role": "assistant", "content": answer})

    # ⑤ 打印状态：留意 token 用量一轮比一轮大
    #
    #    因为输入里带的历史越来越长 —— 这就是"记忆的代价"。
    #    上下文会无限增长，最终撞到模型的上下文长度上限，而且越来越贵。
    #    怎么解决？截断 / 摘要 / 只检索相关内容（→ 这就是后面 RAG 的动机）。
    usage = response.usage
    print(f"   [上下文 {len(messages)} 条 · "
          f"token: {usage.prompt_tokens}(输入) + {usage.completion_tokens}(输出) "
          f"= {usage.total_tokens}]")

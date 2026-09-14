"""Day 1 · v3 —— 加循环：能连续对话。

相比 v2，加了 while True 让程序不退出，输入 exit 才停。

⚠️ 这一版【故意留了一个缺陷】，正是这个缺陷让你理解 v4：

    你：我叫 Jack
    AI：你好 Jack！
    你：我叫什么？
    AI：抱歉，我不知道你叫什么。      ← 它忘了！
    你：我刚刚不是告诉你了吗？
    AI：真的很抱歉，我看不到之前的对话记录。

先跑一遍，亲眼看到它"忘事"。那个困惑感很重要，别跳过。

运行：
    uv run python day01_llm_basics/my_chat_v3.py
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

print("=" * 50)
print("  v3 · 连续对话（但【没有记忆】）")
print("  输入 exit 退出")
print("=" * 50)

# ① 死循环：让程序一直跑，直到用户主动退出
while True:
    # ② 读一行用户输入
    #
    #    input("你：") 会先打印"你："，然后等你在终端敲字并回车。
    #
    #    为什么用 try 包起来？
    #    如果输入流被关闭（比如你把文件重定向进来、或者按了 Ctrl+C），
    #    input() 会抛 EOFError / KeyboardInterrupt。
    #    不处理的话会打印一大堆红色堆栈 —— 对用户很不友好。
    try:
        text = input("\n你：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n再见！")
        break

    # ③ 空输入直接跳过（用户不小心连按了回车）
    if not text:
        continue

    # ④ 退出条件
    if text.lower() == "exit":
        print("再见！")
        break

    # ⑤ 发请求
    #
    #    ⚠️⚠️ 注意这里：messages 里【只有刚打进去的这一句】！
    #    上一轮说过什么，这里一个字都没带上。
    #    所以模型每次都是"第一次见到你" —— 它当然不记得你叫 Jack。
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": text},
        ],
    )

    print("AI：", response.choices[0].message.content)
    usage = response.usage
    print(f"   [token: {usage.prompt_tokens} + {usage.completion_tokens} "
          f"= {usage.total_tokens}]")

# ⭐ 观察一下：每次对话的"输入 token"几乎一样多（就你那句话的量）。
#    这正说明了 —— 我们什么都没带上，每次都是全新的一轮。
#
#    到了 v4，你会看到输入 token 一轮比一轮大，
#    因为每一轮都在重发【全部历史】。

"""Day 1 · v2 —— 加流式输出（Streaming）。

相比 v1，只改了两处：
    1. create() 里加 stream=True
    2. 把"一次性取结果"换成"for 循环逐块接收"

效果对比：
    v1  → 卡住两三秒，整段文字一次性出现
    v2  → 立刻开始逐字往外蹦（和 ChatGPT 网页版一样）

为什么体验差这么多？
    一次完整生成要算很多个 token。非流式是"全算完再给你"，
    流式是"算出一个就立刻发给你"。总时间其实一样，但体感完全不同。

运行：
    uv run python day01_llm_basics/my_chat_v2.py
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or "https://api.deepseek.com",
)

# ① 唯一的改动：stream=True
stream = client.chat.completions.create(
    model=os.getenv("LLM_MODEL") or "deepseek-chat",
    messages=[
        {"role": "user", "content": "请用 100 字左右介绍一下 JVM 的垃圾回收机制"},
    ],
    stream=True,
)

# ② 返回值从"一个完整对象"变成了"一个迭代器（可以 for 遍历的东西）"
#
#    ⚠️ 最重要的差异：字段名变了！
#        非流式：response.choices[0].message.content     ← message
#        流式：  chunk.choices[0].delta.content          ← delta
#
#    delta 是"增量"的意思：每次只给你新生成的那一小段。
for chunk in stream:
    # ③ 取这一小块文本
    #
    #    为什么可能拿到 None？
    #    流式过程中，有些 chunk 不带文本内容（比如最后一个 chunk
    #    只带结束标志和 token 用量），此时 delta.content 就是 None。
    #    所以必须判空，否则会打印出 "None"。
    piece = chunk.choices[0].delta.content

    # ④ 打印这一小块
    #
    #    ⚠️⚠️ end="" 和 flush=True 都【必须】写：
    #
    #    end=""      默认 print 会在末尾加换行，那样每个字都换一行。
    #                改成空字符串，才能把字拼在同一行。
    #
    #    flush=True  print 默认先把内容攒在"缓冲区"里，攒够了才真正输出。
    #                不加它，你会看到文字卡住不动、最后一次性全冒出来 ——
    #                那就完全失去流式的意义了。
    if piece:
        print(piece, end="", flush=True)

# 循环结束后补一个换行（因为上面全程 end=""，光标还停在同一行）
print()

# ⑤ 流式模式下 token 用量通常在【最后一个】chunk 里返回，需要单独拿
#    这就是为什么 chat.py 里要写 if chunk.usage: ... 的原因
if chunk.usage:
    print(f"\n[token: 输入 {chunk.usage.prompt_tokens} + "
          f"输出 {chunk.usage.completion_tokens} = {chunk.usage.total_tokens}]")
else:
    print("\n[本次未返回 token 用量]")

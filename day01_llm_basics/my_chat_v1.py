"""Day 1 · v1 —— 最小调用：把「Python → LLM → 回答」跑通。

这是整个 180 天路线里第一段真正调用大模型的代码。
它只有十几行。跑通它，你就知道所谓"调用 AI"到底是怎么回事：

    你的一句话
        ↓  一次 HTTP POST
    大模型的服务器
        ↓  返回 JSON
    一段文字

没有魔法。

运行：
    uv run python day01_llm_basics/my_chat_v1.py
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

# ① 把 .env 文件里的内容读进"环境变量"（os.environ）
#
#    为什么不能把密钥直接写在代码里？
#      1. 代码会提交到 Git，密钥就永久留在版本历史里，删不掉
#      2. 不同人/不同环境的密钥不同，写死了就没法共用一份代码
#    所以约定：密钥放 .env（不进 Git），代码从环境变量读。
load_dotenv()

# ② 创建一个「带鉴权的 HTTP 客户端」
#
#    Java 类比：
#        RestTemplate t = new RestTemplate();
#        t.getInterceptors().add(new AuthInterceptor(apiKey));
#
#    base_url 是接口地址。国内各家模型厂商都实现了 OpenAI 兼容协议，
#    所以换厂商只需要改这个地址 + 模型名，代码一行不用动。
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),          # 密钥（放 .env）
    base_url=os.getenv("LLM_BASE_URL") or "https://api.deepseek.com",
)

# ③ 发一次请求 —— 这一步背后就是一次 HTTP POST
#
#    model    用哪个模型
#    messages 上下文（就是"对话历史"）。这里只有一句用户的话。
#
#    注意 messages 是个【列表】，元素是带 role 的字典：
#        {"role": "user",      "content": "..."}   用户说的
#        {"role": "assistant", "content": "..."}   模型说的
#        {"role": "system",    "content": "..."}   人设/规则（可选）
response = client.chat.completions.create(
    model=os.getenv("LLM_MODEL") or "deepseek-chat",
    messages=[
        {"role": "user", "content": "你好，请用一句话介绍你自己"},
    ],
)

# ④ 从响应里取出文本
#
#    这个长长的链式取值是 Python 里"顺着数据结构往下走"的写法：
#        response                    整个响应体
#          .choices                  候选回答列表（通常只有 1 个）
#            [0]                     取第一个
#            .message                里面的"消息"对象
#            .content                消息的文本内容
#
#    Java 类比：
#        response.getBody().getChoices().get(0).getMessage().getContent()
print(response.choices[0].message.content)

# ⑤ 顺便看一眼 token 用量 —— 这是计费的依据
#
#    输入 token = 你发过去的字
#    输出 token = 模型生成的字
#    两者价格不同
usage = response.usage
print(f"\n[token: 输入 {usage.prompt_tokens} + 输出 {usage.completion_tokens} "
      f"= {usage.total_tokens}]")

# Day 1+ · 第一个 LLM Client

日期：2026-09-14（接续 `day01.md` 的环境搭建）

---

## 一、今天打通的链路

```
Python
  ↓
uv（装依赖）
  ↓
.env（放密钥）
  ↓
LLMClient（封装）
  ↓
第一次调用 LLM
  ↓
Streaming
  ↓
CLI Chat + 上下文记忆
```

最终成果：

| 文件 | 作用 |
| --- | --- |
| `llm_client.py` | 与厂商无关的 LLM 客户端封装 |
| `main.py` | 三个递进的最小示例 |
| `chat.py` | 带流式与记忆的命令行对话 |
| `.env` / `.env.example` | 密钥与配置（`.env` 不入库） |

---

## 二、核心认知：调用大模型本质就是一次 HTTP 请求

剥掉所有框架的外壳，就这一件事：

```
messages[]  ──POST──▶  /v1/chat/completions  ──▶  模型  ──▶  文本
```

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}],
)
print(response.choices[0].message.content)
```

**六个概念，逐一对应：**

| 代码 | 含义 |
| --- | --- |
| `load_dotenv()` | 把 `.env` 读进环境变量 |
| `OpenAI(...)` | 创建一个带鉴权的 HTTP 客户端 |
| `.create(...)` | 发请求 |
| `model=` | 用哪个模型 |
| `messages=` | 上下文（对话历史） |
| `response.choices[0].message.content` | 取出文本 |

---

## 三、⭐ 最重要的认知：模型是「无状态」的

这是本日最容易被忽略、却在后面整个 Agent 阶段都离不开的一点。

**错误的心智模型：**

```
我以为：模型记住了我刚才说的话
```

**事实：**

```
模型什么都没记住。是我每一轮都把历史重新发了一遍。
```

对比实验：

```python
# ❌ 没有记忆
client.chat("我叫 Jack")     # → 你好 Jack
client.chat("我叫什么？")     # → 抱歉，我不知道你叫什么

# ✅ 有记忆
messages = [
    {"role": "user",      "content": "我叫 Jack"},
    {"role": "assistant", "content": "你好 Jack！"},
    {"role": "user",      "content": "我叫什么？"},
]
client.chat(messages)        # → 你叫 Jack
```

**结论：**

> Memory 不是模型的能力，是**应用层的行为**。
> 这就是后面 Agent Memory / RAG / 上下文工程的第一块砖。

`chat.py` 里的 `messages` 列表，就是这一认知的最小实现。

---

## 四、Streaming：为什么 AI 应用的体验和普通接口不一样

| | 普通后端接口 | LLM 接口 |
| --- | --- | --- |
| 用户等待 | 等 5 秒，然后一次性出结果 | 立刻开始出字，逐字累积 |
| 协议 | 一次 HTTP 响应 | SSE（`text/event-stream`） |
| 前端 | `fetch` | `EventSource` / `ReadableStream` |
| Java | `ResponseEntity` | `SseEmitter` / `Flux<String>` |

实现要点（本日踩过的坑）：

```python
for chunk in stream:
    piece = chunk.choices[0].delta.content
    if piece:
        yield piece
```

```python
print(piece, end="", flush=True)
#                  ↑ 没有 flush=True 会卡在缓冲区里，
#                    最后一次性全冒出来 —— 那就没有流式的意义了
```

**注意变化：** 非流式读 `response.choices[0].message.content`，
流式读 `chunk.choices[0].delta.content`。**`message` → `delta`**。

---

## 五、Token

Token 是模型处理文本的**基本单位**，不是「一个字 = 一个 token」。

```
"Hello world"  →  可能拆成 ["Hello", " world"]

输入 token  +  输出 token  =  总 token
              ↓
        直接决定：成本 / 上下文长度 / 响应速度
```

用法（`response.usage`）：

```python
u = response.usage
print(u.prompt_tokens, u.completion_tokens, u.total_tokens)
```

**流式模式下**要显式请求：

```python
stream_options={"include_usage": True}
```

> 本日实现的一个工程细节：部分厂商不支持这个参数，
> 所以 `llm_client.py` 捕获异常后**自动降级重试一次**（去掉该参数），
> 而不是直接崩掉。这是「优雅降级」的一个真实例子。

---

## 六、设计决策：为什么不用 `client.responses.create()`

| | `responses.create` | `chat.completions.create` |
| --- | --- | --- |
| 提供方 | **仅 OpenAI 专有** | 事实标准，几乎全厂商兼容 |
| DeepSeek / Qwen / GLM | ❌ 不支持 | ✅ 支持 |
| 取文本 | `response.output_text` | `choices[0].message.content` |

需求是「换一家模型不改代码」，所以统一走 `chat.completions`。

> 工程原则：**在兼容性与新特性之间，优先选兼容性**，
> 除非新特性带来不可替代的价值。

---

## 七、工程习惯

### 1. 密钥永不入库

```gitignore
.env
.env.*
!.env.example
```

- `.env` → 本地真实密钥，**绝不提交**
- `.env.example` → 模板，提交，给别人看要填哪些字段

```powershell
# 提交前自查，确认列表里没有 .env
git status --short
```

### 2. 配置与代码分离

```python
# ❌ 密钥硬编码
client = OpenAI(api_key="sk-1234567890")

# ✅ 从环境变量读
api_key = os.getenv("DEEPSEEK_API_KEY")
```

变量名按优先级依次尝试：`DEEPSEEK_API_KEY` → `LLM_API_KEY` → `OPENAI_API_KEY`。
这样既能跟着主推厂商（DeepSeek）走，又兼容通用命名。

理由：密钥会轮换、不同环境不同值、泄漏后无法撤销（Git 历史里删不掉）。

### 3. 错误要翻译成「人能看懂的话」

```python
# ❌ 直接把 SDK 异常抛给用户
openai.AuthenticationError: Error code: 401 - {'error': {...}}

# ✅ 翻译成可操作提示
❌ 鉴权失败（401）：API Key 无效或已失效。请检查 .env 里的 DEEPSEEK_API_KEY。
```

⚠️ **踩坑点：异常判断顺序**。`AuthenticationError` 是 `APIStatusError` 的子类，
`APITimeoutError` 是 `APIConnectionError` 的子类。
**必须先判断子类，再判断父类**，否则永远命中父类分支。

---

## 八、Java ↔ AI 对照表

| Java 世界 | AI 世界 | 说明 |
| --- | --- | --- |
| Spring Boot | Python + uv | 运行时与依赖管理 |
| `@ConfigurationProperties` | `LLMConfig` + `dataclass` | 配置绑定 |
| `final` 字段 | `@dataclass(frozen=True)` | 不可变 |
| `RestTemplate` / `WebClient` | `OpenAI` SDK | HTTP 客户端 |
| Service 层 | `LLMClient` | 业务封装 |
| Request DTO | `messages` / Prompt | 请求体 |
| Response DTO | `choices[0].message` | 响应体 |
| SSE / `Flux<String>` | `chat_stream()` | 流式 |
| Redis Session | `messages` 历史列表 | 会话记忆 |
| `ResponseEntity` | `LLMError` | 错误处理 |

**结论：不是从零学编程，而是把已有的后端工程能力平移到 AI 应用工程。**

---

## 九、面试题

**Q1：大模型 API 是有状态的吗？多轮对话怎么实现？**

无状态。API 每次请求相互独立，模型不保留任何会话信息。
多轮对话靠**应用层**在每次请求时把完整历史 `messages` 一并发送。
因此上下文长度会线性增长，带来 token 成本与超限问题，
工程上需要截断、摘要或向量检索（这就引出了 Memory 与 RAG）。

**Q2：Streaming 和普通接口的区别？后端怎么实现？**

普通接口一次性返回完整响应体。Streaming 基于 SSE 长连接，
服务端逐 token 推送增量数据（`delta`），客户端边收边渲染。
Java 侧用 `SseEmitter` 或 WebFlux 的 `Flux<String>`；
Python 侧用生成器 `yield` + `flush=True`。

**Q3：为什么要把 LLM 调用封装成 Client 类而不是散落各处？**

统一管理鉴权、超时、重试、错误翻译与模型切换；
调用方只依赖「输入消息 → 输出文本」这一契约。
后续换厂商、加缓存、加限流、加可观测性都只改一处（开闭原则）。

**Q4：Token 是什么？为什么要关心它？**

模型处理文本的最小单位，由分词器切分，不等于字或词。
它直接决定计费成本、上下文窗口上限和生成速度。
优化方向：精简 System Prompt、裁剪历史、控制输出长度、
用便宜模型处理简单任务（模型路由）。

**Q5：API Key 泄漏了怎么办？**

立即到平台吊销并重新生成；用 `git filter-repo` / BFG 清理历史（但历史可能已被 fork 或缓存，
所以**吊销才是根本手段**）；此后改为环境变量 + 密钥管理服务（Vault / KMS）注入。

---

## 十、本日踩的坑

1. **`openai` 已是 3.x 大版本** —— 不能凭记忆写 API，先 `inspect.signature` 实测。
2. **`httpx` 改名 `httpx2`** —— `import httpx` 会失败，改用 SDK 自身做连通性测试。
3. **异常判断顺序** —— 见上文第七条。
4. **`print` 不加 `flush=True`** —— 流式效果被缓冲吞掉。
5. **`stream_options` 非全厂商支持** —— 需要降级重试。

---

## 十一、验收清单

- [x] `uv sync` 装好 `openai` / `python-dotenv`
- [x] `.env` / `.env.example` 分离，`.env` 已被 gitignore
- [x] `llm_client.py`：配置读取、同步调用、流式调用、错误翻译、用量统计
- [x] `main.py`：三个递进 demo
- [x] `chat.py`：流式 + 上下文记忆 + 命令 + 失败回滚
- [x] 连通性预检通过（返回 401 = 网络通，只差真 Key）
- [x] 笔记 + 面试题

### 待你完成

- [ ] 到 <https://platform.deepseek.com/api_keys> 申请 Key，填进 `.env`
- [ ] `uv run python main.py` 跑通三个 demo
- [ ] `uv run python chat.py` 做「我是 Jack」→「我叫什么」的记忆实验

---

## 十二、明日预告（Day 2）

**Python 异步 + API 工程化 + 把 CLI Chat 抽成真正可复用的 LLM Service**

- `async` / `await` / `asyncio`
- 为什么 LLM 应用必须异步（高 IO 等待、多 Tool 并发）
- 把 `messages` 历史从 `chat.py` 抽出成 `ChatSession` 类
- 加上重试、超时、限流

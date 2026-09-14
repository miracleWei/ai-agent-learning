# AI Agent Learning

> Java 后端 → **AI Agent / AI 应用工程师** 的 180 天学习仓库。
>
> - 学习路线：[`../学习路线.MD`](../学习路线.MD)
> - 详细日程：[`../学习安排/总安排计划.MD`](../学习安排/总安排计划.MD)
> - 👉 **今日任务：[`../学习安排/Day01-学习指南.md`](../学习安排/Day01-学习指南.md)**

学习的核心原则不是「看完视频」，而是：

```
学一个概念 → 马上写代码 → 加进项目 → 写技术总结
```

---

## 一、环境

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.11.1 | `D:\install\python\python.exe` |
| uv | 0.12.13 | 极快的 Python 包 / 虚拟环境管理器 |
| Git | 2.29.0 | 版本管理 |

---

## 二、目录结构

```
ai-agent-learning/
│
├── README.md                    # 本文件：项目说明 + 学习进度
├── pyproject.toml               # 项目元信息 + 依赖 + 镜像源
├── uv.lock                      # 依赖锁定文件（保证可复现）
├── .gitignore                   # 忽略 .venv / __pycache__ / .env
├── .env.example                 # 配置模板（入库，不含真实密钥）
├── .env                         # 本地真实密钥（⚠️ 不入库）
│
├── llm_client.py                # ⭐ 核心：LLM 客户端封装（与厂商无关）
├── main.py                      # 最小可运行示例（3 个 demo）
├── chat.py                      # ⭐ CLI 对话：流式 + 上下文记忆
│
├── notes/                       # 每日学习笔记 + 面试题
│   ├── day01.md                 # Python 环境与项目结构
│   └── day01-llm-client.md      # LLM Client 封装（含 Java↔AI 对照）
│
└── day01_python_basics/         # Day 1 热身：Python 基础
    ├── README.md
    ├── hello.py
    ├── env_check.py
    └── greeter/
        ├── __init__.py
        ├── core.py
        └── __main__.py
```

### 三层调用关系

```
chat.py          ── CLI 交互层（读输入 / 维护历史 / 打印）
     ↓
llm_client.py    ── 客户端封装层（配置 / 请求 / 错误翻译 / 流式）
     ↓
openai SDK       ── 协议层（HTTP + SSE）
     ↓
LLM API          ── DeepSeek / Qwen / GLM / OpenAI
```

---

## 三、快速开始

### 1. 创建虚拟环境

```powershell
# 在仓库根目录执行；uv 会在当前目录创建 .venv
uv venv
```

### 2. 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
```

> 如果提示「禁止运行脚本」，先执行一次：
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

激活成功后，命令行前面会出现 `(.venv)`。

### 3. 安装依赖

```powershell
uv sync          # 依 pyproject.toml 安装，几秒钟搞定
```

> `uv` 已配置清华镜像源（写在 `pyproject.toml` 的 `[[tool.uv.index]]`），
> 因为 `pypi.org` 在国内直连很慢。

### 4. 配置 API Key（‼️ 必做）

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，把这一行换成你的真实密钥：

```
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
```

> DeepSeek 密钥申请：<https://platform.deepseek.com/api_keys>
> **不要把这个 Key 发到任何聊天窗口里，包括 AI 助手。**
>
> 💡 变量名无需纠结：代码按优先级依次尝试
> `DEEPSEEK_API_KEY` → `LLM_API_KEY` → `OPENAI_API_KEY`，填哪个都能跑。
> 启动时状态栏会显示 `Key=sk-xxx (来自 DEEPSEEK_API_KEY)`，一眼看出配置来源。
> 同理，`LLM_BASE_URL` 不填时默认走 DeepSeek，**不会误打到 OpenAI 官方地址**。

### 5. 验证环境

```powershell
uv run python day01_python_basics\env_check.py   # 确认在虚拟环境里
uv run python main.py 1                          # 最小调用，能出字就通了
```

### 6. 开始对话

```powershell
# 流式输出（默认），体验和 ChatGPT 网页版一样
uv run python chat.py

# 一次性输出，方便查看 token 用量
uv run python chat.py --no-stream

# 自定义人设
uv run python chat.py --system "你是一个只用古文回答的助手"
```

会话内命令：`/clear` 清空上下文 · `/history` 查看上下文 · `/help` 帮助 · `exit` 退出

---

## 四、技术栈路线（中国大陆 AI 生态）

> 目标不是跟国外教程做 Demo，而是**对标中国大陆企业 AI 应用开发岗位**的实际技术栈。
> 所以从 Day 1 起就以国内模型为主力。

| 层次 | 选用 | 说明 |
| --- | --- | --- |
| **主模型** | DeepSeek、Qwen | 国内直连、便宜、兼容 OpenAI 协议 |
| 辅助了解 | GLM、Kimi、豆包 | 按需切换，代码无需改 |
| Embedding | BGE、Qwen-Embedding | 中文语义检索效果好 |
| 向量库 | pgvector、Milvus、Elasticsearch | 优先 pgvector（契合企业后端） |
| Java 侧 | Spring Boot、Spring AI | 你的主战场 |
| Python 侧 | FastAPI、Pydantic | 写 Demo 与 Agent |
| Agent 框架 | Spring AI、LangGraph | Java 主线 + Python 参考 |
| 协议 | MCP | 必学 |
| 基础设施 | PostgreSQL、Redis、Kafka、Docker、K8s | 你的存量优势 |

**为什么用 `openai` SDK 而不是 DeepSeek 专用 SDK？**

因为国内厂商（DeepSeek / Qwen / GLM / Kimi）几乎都实现了 **OpenAI 兼容协议**。
用 `openai` SDK 只是当 HTTP 客户端用，换厂商只改 `.env` 三行，代码零改动。

---

## 五、切换其他大模型

代码**与厂商无关**，只改 `.env` 里三个变量即可，Python 一行都不用动：

| 厂商 | LLM_BASE_URL | LLM_MODEL |
| --- | --- | --- |
| **DeepSeek**（✅ 当前主推） | `https://api.deepseek.com` | `deepseek-chat` |
| DeepSeek 推理模型 | `https://api.deepseek.com` | `deepseek-reasoner` |
| 阿里云百炼 Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Moonshot Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| OpenAI（需代理） | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

> DeepSeek 的地址带不带 `/v1` 都可以（已实测），`/v1` 只是为兼容 OpenAI 而保留，与模型版本无关。

---

## 六、故障排查

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `❌ 鉴权失败（401）` | Key 错误 / 已失效 | 重新生成 Key，更新 `.env` |
| `❌ 余额不足（402）` | 账户没钱 | 去平台充值 |
| `❌ 连接不上 LLM 服务` | 网络 / 地址写错 | 检查 `LLM_BASE_URL`；境外服务需开代理 |
| `❌ 找不到资源（404）` | 模型名或地址写错 | 对照上表核对 |
| `❌ .env 里的 DEEPSEEK_API_KEY 还是占位符` | 忘了填 Key | 编辑 `.env` |
| 中文输出乱码 | PowerShell 编码 | 先执行 `chcp 65001` |
| 文字卡住不逐字显示 | 缓冲区未刷新 | 代码里必须有 `flush=True` |
| `Missing credentials`（Key 明明填了） | 变量名不一致（如代码读 `LLM_API_KEY`，`.env` 写 `DEEPSEEK_API_KEY`） | 改名为 `API_KEY_VARS` 里任一个，或改 `.env` |
| `UnicodeEncodeError: surrogates not allowed` | 用管道把中文喂给 python（PowerShell 5.1 的 `$OutputEncoding` 默认 US-ASCII） | 直接在终端手敲输入，别用管道 |
| `VIRTUAL_ENV=... does not match...` | 激活了别的目录的 `.venv` | 删掉多余的那个（`Remove-Item "F:\笔记\AI-学习\.venv" -Recurse -Force`） |

---

## 七、学习进度

> ⚠️ **状态含义**：
> `✅` = **你亲自跑通过** ｜ `🔧` = 代码已写好但**你还没实跑/手敲** ｜ `⬜` = 未开始

| Day | 主题 | 状态 |
| --- | --- | --- |
| 01 | Python 环境 / uv / 虚拟环境 / 项目结构 | ✅ 环境已就绪 |
| 01+ | 第一个 LLM Client（DeepSeek）：调用 / Streaming / CLI 对话 / 上下文记忆 | ✅ 已实测跑通 |
| 01++ | **自己手敲 v1～v4 + 写自己的笔记** | ⬜ **仅剩这一步** |
| 02 | Python 异步 + API 工程化 + 抽出可复用的 LLM Service | ⬜ |
| 03 | class / dataclass / 继承 / typing | ⬜ |
| 04 | 异常 / 文件 / JSON / 环境变量 | ⬜ |
| 05 | lambda / map / filter / 装饰器 / 生成器 | ⬜ |
| 06 | async / await / asyncio | ⬜ |
| 07 | Token / 成本统计 / 错误重试 | ⬜ |

### Day 1 待办（详见学习指南）

```
✅ 填 .env 的 DEEPSEEK_API_KEY（已完成）
✅ uv run python main.py 1     能出回答（已验证）
✅ uv run python main.py 3     能流式输出（已验证）
✅ 记忆机制已验证：带历史答对 / 不带历史答不出

⬜ 自己敲 day01_llm_basics/my_chat_v1.py ~ v4.py（不用看 llm_client.py）⬅️ 仅剩这一步
⬜ 写 notes/day01-我的笔记.md（自己的话）
⬜ git commit + push
```

---

## 八、约定

1. **每天一个 commit**，提交信息格式：`day01: 主题`。
2. **API Key 绝不入库**：统一放在 `.env`；提交前可用 `git status` 确认 `.env` 不在列表里。
3. **每天写笔记**：`notes/dayNN*.md`，包含「今天学了什么 / 踩了什么坑 / 面试题」。
4. **注释写「为什么」**，而不是复述代码「做了什么」。

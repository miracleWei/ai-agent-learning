# AI Agent Learning

> Java 后端 → **AI Agent / AI 应用工程师** 的 180 天学习仓库。
>
> - 学习路线：[`../学习路线.MD`](../学习路线.MD)
> - 详细日程：[`../学习安排/总安排计划.MD`](../学习安排/总安排计划.MD)

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
├── README.md                    # 本文件：项目说明 + 学习进度
├── pyproject.toml               # 项目元信息（uv 识别它）
├── .gitignore                   # 忽略 .venv / __pycache__ / .env
├── notes/                       # 每日学习笔记 + 面试题
│   └── day01.md
└── day01_python_basics/         # Day 1 代码
    ├── README.md                # 今日任务清单 + 验收标准
    ├── hello.py                 # 任务 1：第一个 Python 函数
    ├── env_check.py             # 任务 2：环境自检脚本
    └── greeter/                 # 任务 3：一个标准 Python「包」
        ├── __init__.py
        ├── core.py
        └── __main__.py
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
uv pip install -r requirements.txt   # 当前还没有第三方依赖
# 或者
uv sync                              # 依据 pyproject.toml 同步
```

### 4. 运行 Day 1 代码

```powershell
python day01_python_basics\hello.py
python day01_python_basics\env_check.py

# 运行「包」形式的程序：必须用 -m（模块方式），且不要写 .py
python -m day01_python_basics.greeter Tom
# 输出：Hello Tom
```

---

## 四、学习进度

| Day | 主题 | 状态 |
| --- | --- | --- |
| 01 | Python 环境 / uv / 虚拟环境 / 项目结构 | ✅ |
| 02 | list / dict / tuple / set / 推导式 | ⬜ |
| 03 | class / dataclass / 继承 / typing | ⬜ |
| 04 | 异常 / 文件 / JSON / 环境变量 | ⬜ |
| 05 | lambda / map / filter / 装饰器 / 生成器 | ⬜ |
| 06 | async / await / asyncio | ⬜ |
| 07 | 小项目：Python LLM API Client | ⬜ |

---

## 五、约定

1. **每天一个 commit**，提交信息格式：`day01: Python 环境与项目结构`。
2. **API Key 绝不入库**：统一放在 `.env`，`.env` 已在 `.gitignore` 中。
3. **每天写笔记**：`notes/dayNN.md`，包含「今天学了什么 / 踩了什么坑 / 面试题」。

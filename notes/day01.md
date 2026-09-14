# Day 1 · Python 环境与项目结构

日期：2026-09-14

---

## 一、今天学了什么

| 概念 | 一句话理解 |
| --- | --- |
| CPython | 官方 Python 解释器；`python.exe` 就是它 |
| pip | Python 自带的包管理器，装全局包容易把环境搞脏 |
| uv | Rust 写的超快包/环境管理器，替代 `pip` + `venv` + `pip-tools` + `poetry` 的一部分职责 |
| 虚拟环境 | 每个项目一份独立的 `site-packages`，互不污染 |
| 模块 module | 一个 `.py` 文件 |
| 包 package | 一个含 `__init__.py` 的目录 |
| `__main__.py` | 包被「当模块运行」时的入口 |

---

## 二、环境结论（本机）

```
Python   : 3.11.1   （D:\install\python\python.exe）
pip      : 22.3.1
uv       : 0.12.13
Git      : 2.29.0
venv     : F:\笔记\AI-学习\ai-agent-learning\.venv
```

---

## 三、四个关键知识点

### 1. 为什么必须要虚拟环境？

因为 Python 没有 Java 那样的 `groupId:artifactId:version` 依赖坐标。
`pip install requests` 默认装到**全局** `site-packages`，于是：

- 项目 A 要 `langchain==0.1`，项目 B 要 `langchain==0.3` → 直接冲突
- 系统里一堆来路不明的包，出问题无法定位

**虚拟环境 = 每个项目一个独立的依赖目录。**
激活后 `sys.prefix` 指向 `.venv`，`pip install` 就只影响这个项目。

> 对应 Java：相当于每个项目自带一份 `~/.m2`。

### 2. pip vs uv

```powershell
# 老方式（三轮）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 新方式（uv，毫秒级）
uv venv
uv pip install -r requirements.txt
```

uv 的核心优势：**快**（Rust + 全局缓存 + 硬链接）、自带锁文件、能直接管 Python 版本。

### 3. 项目结构：模块 / 包 / 入口

```
day01_python_basics/
└── greeter/              ← 包（有 __init__.py）
    ├── __init__.py       ← 包的「公开 API」，external 只 import 这里
    ├── core.py           ← 模块，真正干活的代码
    └── __main__.py       ← 被「当模块运行」时的入口
```

- `__init__.py` ≈ Java 的 `package` 声明 + 「对外只暴露这几个类」的整理层
- `__main__.py` ≈ Java 的 `public static void main`

### 4. `if __name__ == "__main__":`

```python
if __name__ == "__main__":
    main()
```

- 直接 `python hello.py` → `__name__ == "__main__"` → 执行
- 被 `import hello` → `__name__ == "hello"` → 不执行

作用：**让文件既能当脚本跑，又能被别的模块 import 而不产生副作用。**

---

## 四、今天踩的坑 ⭐

**问题：`python day01_python_basics\greeter Tom` 报错**

```
ImportError: attempted relative import with no known parent package
```

**原因：** 把「目录」交给 python 时，Python 会去执行该目录的 `__main__.py`，
但它是**当作脚本**（顶层代码）执行的，`__package__` 为空。
既然没有「父包」，`from .core import hello` 里的 `.` 就无从解析。

**正确写法：**

```powershell
# 在仓库根目录
python -m day01_python_basics.greeter Tom

# 或在 day01_python_basics 目录内
python -m greeter Tom
```

**规律：**

| 运行方式 | `__package__` | 相对导入 |
| --- | --- | --- |
| `python x/y/main.py` | `""`（空） | ❌ 失败 |
| `python x/y`（目录） | `""`（空） | ❌ 失败 |
| `python -m x.y` | `"x.y"` | ✅ 成功 |

> 类比 Java：`java Main`（丢包名）vs `java com.example.Main`（有包名）。

---

## 五、面试题（附参考答案）

**Q1：Python 的虚拟环境解决了什么问题？**

隔离依赖。Python 不像 Java 有 Maven 坐标做依赖解析与隔离，全局 `site-packages` 会被所有项目共用，版本冲突无法解决。虚拟环境给每个项目独立的解释器前缀和 `site-packages`（`sys.prefix != sys.base_prefix`），从而做到项目级隔离与可复现。

**Q2：`python -m package.module` 和 `python path/to/module.py` 有什么区别？**

- `path/to/module.py`：模块被当作**脚本**执行，`sys.path[0]` 是该文件所在目录，`__package__` 为空 → 相对导入失败。
- `-m package.module`：Python 按**包路径**解析，设置正确的 `__package__`，相对导入可用，且 `sys.path[0]` 是当前工作目录。

**Q3：为什么 Python 项目要有 `pyproject.toml`？**

它是 PEP 518/621 定义的标准项目元数据文件，统一描述构建后端、项目名、版本、依赖、Python 版本要求、工具配置（ruff/pytest 等）。取代了零散的 `setup.py` / `setup.cfg` / `requirements.txt`，是现代 Python 打包与工具链的统一入口。

---

## 六、验收清单

- [x] Python 3.11.1 可用，`pip` / `uv` 可用
- [x] `.venv` 虚拟环境创建成功，`env_check.py` 报告「运行模式 = 虚拟环境」
- [x] `hello.py` 输出 `Hello World` / `Hello Agent`
- [x] `greeter` 包可通过 `-m` 运行，并理解相对导入失败的原因
- [x] `.gitignore` 正确忽略 `.venv/`、`__pycache__/`、`.env`
- [x] Git 仓库初始化 + 首次提交
- [x] 笔记写完

---

## 七、明日预告（Day 2）

`list` / `dict` / `tuple` / `set` / 推导式（comprehension）。

重点是把 Java 的 `List` / `Map` / `Set` 思维切换过来：

```python
users = [
    {"name": "Tom", "age": 20},
    {"name": "Jack", "age": 30},
]

names = [u["name"] for u in users]
```

对应 Java：

```java
List<String> names = users.stream().map(u -> u.getName()).toList();
```

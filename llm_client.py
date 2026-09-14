"""Day 1 · LLM Client —— 把「调用大模型」封装成一个可复用的类。

设计目标：**与厂商无关（provider-agnostic）**
    切换 DeepSeek / Qwen / GLM / OpenAI / Ollama，只需要改 .env 里三个变量，
    Python 代码一行都不用动。

为什么不用 OpenAI 官方的 ``client.responses.create``？
    ``responses`` 是 OpenAI 专有接口，而 DeepSeek / Qwen / GLM / Ollama 等
    国内外厂商统一实现的是 ``chat.completions``。
    为了「换一家厂商不改代码」，这里统一走 ``chat.completions``。

Java 类比
    ``LLMClient``         ≈ 一个封装好鉴权与序列化的 HTTP Client
    ``LLMConfig``         ≈ application.yml 里的一段配置 + @ConfigurationProperties
    ``chat()``            ≈ 一次同步调用
    ``chat_stream()``     ≈ 返回 Flux / SSE 的流式调用
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import openai
from dotenv import load_dotenv
from openai import OpenAI

# 一条消息就是 {"role": "system" | "user" | "assistant", "content": "..."}
Message = dict[str, str]

# 没配 LLM_MODEL 时的兜底模型
DEFAULT_MODEL = "deepseek-chat"

# 没配 LLM_BASE_URL 时的兜底地址
# 主推 DeepSeek（国内直连、无需代理）；换厂商就在 .env 里显式写 LLM_BASE_URL
DEFAULT_BASE_URL = "https://api.deepseek.com"

# 读取 API Key 时按优先级依次尝试的环境变量名
# 以 DeepSeek 为主推，同时兼容通用命名（LLM_）与 OpenAI 命名
API_KEY_VARS: tuple[str, ...] = ("DEEPSEEK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")

# 认定为「还是占位符、没填真 Key」的特征串
_PLACEHOLDER_HINTS = ("在这里填入", "xxxxxxxx", "your-key", "your_key", "填入你的")


class LLMError(RuntimeError):
    """把底层各种 SDK 异常翻译成一句人能看懂的中文提示。"""


@dataclass(frozen=True)
class LLMConfig:
    """LLM 连接配置（不可变，创建后不会被人偷偷改掉）。

    ``frozen=True`` 让这个类变成「只读」，相当于 Java 里的 ``final`` 字段 +
    只有构造器赋值，避免配置在运行中被意外修改。
    """

    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str | None = DEFAULT_BASE_URL
    temperature: float = 0.7
    timeout: float = 60.0
    stream_usage: bool = True
    # 记录 api_key 是从哪个环境变量读到的，便于排查配置问题
    key_source: str = ""

    def describe(self) -> str:
        """返回一段用于自检展示的描述（绝不包含 Key 本身）。"""
        masked = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
        source = f" (来自 {self.key_source})" if self.key_source else ""
        return (
            f"模型={self.model} | 地址={self.base_url or '未设置'} | "
            f"Key={masked}{source} | temperature={self.temperature}"
        )

    @classmethod
    def from_env(cls) -> LLMConfig:
        """从 ``.env`` / 环境变量读取配置。

        这是 Python 里常见的「工厂方法」写法，等价于 Java 的
        ``LLMConfig.fromEnv()`` 静态工厂。
        """
        # 把 .env 读进 os.environ；重复调用是安全的，不会重复生效
        load_dotenv()

        # 按优先级找一个非空的 Key，并记住它来自哪个变量名（报错时要提示到具体变量）
        api_key, key_var = "", API_KEY_VARS[0]
        for var in API_KEY_VARS:
            value = (os.getenv(var) or "").strip()
            if value:
                api_key, key_var = value, var
                break

        model = (os.getenv("LLM_MODEL") or DEFAULT_MODEL).strip()
        # 只填了 Key、没填地址时，默认走 DeepSeek，避免误打到 OpenAI 官方接口
        base_url = (os.getenv("LLM_BASE_URL") or "").strip() or DEFAULT_BASE_URL

        if not api_key:
            tried = " / ".join(API_KEY_VARS)
            raise LLMError(
                "❌ 没有找到 API Key。\n"
                "   请在本目录创建 .env 文件（可从 .env.example 复制），写入：\n"
                f"       {API_KEY_VARS[0]}=你的密钥\n"
                f"   （代码会按优先级依次尝试这些变量名：{tried}）"
            )
        if any(hint in api_key for hint in _PLACEHOLDER_HINTS):
            raise LLMError(
                f"❌ .env 里的 {key_var} 还是占位符，没有填真实密钥。\n"
                f"   请打开 .env，把 {key_var} 换成你自己的 Key 后重试。"
            )

        def _float(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, "") or default)
            except ValueError:
                return default

        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=_float("LLM_TEMPERATURE", 0.7),
            timeout=_float("LLM_TIMEOUT", 60.0),
            stream_usage=(os.getenv("LLM_STREAM_USAGE", "true") or "true").lower()
            not in {"false", "0", "no"},
            key_source=key_var,
        )


def _to_messages(payload: str | Sequence[Message]) -> list[Message]:
    """把「一句话」或「消息列表」统一成消息列表。"""
    if isinstance(payload, str):
        return [{"role": "user", "content": payload}]
    return [dict(m) for m in payload]


def _friendly_error(exc: Exception) -> str:
    """把 SDK 抛出的异常翻译成可操作的中文提示。

    ⚠️ 判断顺序很重要：必须先判断具体的子类，再判断父类，
       因为 AuthenticationError 也是 APIStatusError 的子类。
    """
    status = getattr(exc, "status_code", None)

    if isinstance(exc, openai.AuthenticationError):
        return (
            "❌ 鉴权失败（401）：API Key 无效或已失效。\n"
            "   请检查 .env 里的 DEEPSEEK_API_KEY（或 LLM_API_KEY / OPENAI_API_KEY）。\n"
            "   DeepSeek 控制台：https://platform.deepseek.com/api_keys"
        )
    if status == 402:
        return "❌ 余额不足（402）：请到模型平台充值后重试。"
    if isinstance(exc, openai.RateLimitError):
        return "❌ 触发限流（429）：请求太频繁或超出配额，稍后重试。"
    if isinstance(exc, openai.APITimeoutError):
        return "❌ 请求超时：网络不稳定，或可调大 .env 里的 LLM_TIMEOUT。"
    if isinstance(exc, openai.APIConnectionError):
        return (
            "❌ 连接不上 LLM 服务：\n"
            "   1) 检查网络是否正常\n"
            "   2) 核对 .env 里的 LLM_BASE_URL 是否写错\n"
            "   3) 若用境外服务（OpenAI），确认代理已开启"
        )
    if status == 404:
        return (
            f"❌ 找不到资源（404）：通常是模型名或地址写错了。\n"
            f"   当前模型={os.getenv('LLM_MODEL')} 地址={os.getenv('LLM_BASE_URL')}"
        )
    if isinstance(exc, openai.APIStatusError):
        detail = getattr(exc, "message", None) or str(exc)
        return f"❌ 服务返回异常（HTTP {status}）：{detail}"
    if isinstance(exc, openai.OpenAIError):
        return f"❌ SDK 异常：{type(exc).__name__}: {exc}"
    return f"❌ 未预期的错误：{type(exc).__name__}: {exc}"


class LLMClient:
    """一个极简但完整的 LLM 客户端。

    它只做三件事：
        1. 读取配置（Key / 地址 / 模型）
        2. 发请求
        3. 把结果吐出来（一次性返回 / 逐个 token 吐出）

    Example:
        >>> client = LLMClient()
        >>> client.chat("用一句话介绍你自己")
        '你好！我是一个...'

        >>> for piece in client.chat_stream("写一首五言绝句"):
        ...     print(piece, end="", flush=True)
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        # config 允许注入，方便写单元测试时传入假配置
        self.config: LLMConfig = config or LLMConfig.from_env()
        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )
        # 最近一次请求的 token 用量（流式模式可能为 None）
        self.last_usage: openai.types.CompletionUsage | None = None
        # 流式模式下若厂商不支持用量统计，会自动降级并置为 True
        self._stream_usage_disabled = False

    # ------------------------------------------------------------------
    # 对外属性
    # ------------------------------------------------------------------

    @property
    def model(self) -> str:
        return self.config.model

    # ------------------------------------------------------------------
    # 同步调用：一次性拿到完整回答
    # ------------------------------------------------------------------

    def chat(
        self,
        payload: str | Sequence[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """发送请求并返回**完整**回答文本。

        Args:
            payload: 一句话（str），或者完整的消息列表（含历史）。
            temperature: 覆盖默认温度。
            max_tokens: 限制回答长度，None 表示用服务端默认值。

        Returns:
            模型回答的纯文本。
        """
        messages = _to_messages(payload)
        kwargs: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - 统一翻译成友好提示再抛出
            raise LLMError(_friendly_error(exc)) from exc

        self.last_usage = response.usage
        content = response.choices[0].message.content
        return content or ""

    # ------------------------------------------------------------------
    # 流式调用：逐 token 吐出
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        payload: str | Sequence[Message],
        *,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """发送请求并**逐段**产出回答文本。

        对应 Java 的 SSE / ``Flux<String>``：调用方边收边展示，用户不用干等。

        Yields:
            每次一小段文本（可能是几个字，也可能是一个字）。
        """
        messages = _to_messages(payload)
        kwargs: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
            "stream": True,
        }
        if self.config.stream_usage and not self._stream_usage_disabled:
            kwargs["stream_options"] = {"include_usage": True}

        try:
            stream = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            # 有些厂商不支持 stream_options，这里优雅降级重试一次
            if "stream_options" in kwargs:
                self._stream_usage_disabled = True
                kwargs.pop("stream_options")
                try:
                    stream = self._client.chat.completions.create(**kwargs)
                except Exception as exc2:  # noqa: BLE001
                    raise LLMError(_friendly_error(exc2)) from exc2
            else:
                raise LLMError(_friendly_error(exc)) from exc

        self.last_usage = None
        try:
            for chunk in stream:
                # 每个 chunk 可能带 usage（通常是最后一个 chunk）
                if getattr(chunk, "usage", None):
                    self.last_usage = chunk.usage
                if not chunk.choices:
                    continue
                piece = chunk.choices[0].delta.content
                if piece:
                    yield piece
        except Exception as exc:  # noqa: BLE001
            raise LLMError(_friendly_error(exc)) from exc

    # ------------------------------------------------------------------
    # 便利方法：不想手写 messages 时用
    # ------------------------------------------------------------------

    def ask(self, prompt: str) -> str:
        """单轮提问的简写，等于 ``chat(prompt)``。"""
        return self.chat(prompt)

    def ask_stream(self, prompt: str) -> Iterator[str]:
        """单轮流式提问的简写，等于 ``chat_stream(prompt)``。"""
        return self.chat_stream(prompt)

    def usage_text(self) -> str:
        """把最近一次的 token 用量格式化成一行字。"""
        u = self.last_usage
        if u is None:
            return "token 用量：未返回（流式模式下部分厂商不返回）"
        return (
            f"token 用量：输入 {u.prompt_tokens} + 输出 {u.completion_tokens} "
            f"= 合计 {u.total_tokens}"
        )

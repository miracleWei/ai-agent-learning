"""Token Budget Context Manager —— Agent 的核心基础设施。

======================================================================
 为什么需要它（它解决什么问题）
======================================================================
模型 API 是【无状态】的：每轮都要把上下文重新发一遍。
而上下文里有多种来源，它们的重要性和大小差异极大：

    System Prompt   ← 必须留（人设/规则）
    当前问题         ← 必须留（否则答非所问）
    Memory          ← 小、价值高（用户是谁）
    RAG 检索结果     ← 中、可能很长
    Tool 结果        ← 可能【爆炸】（一次 SQL 返回几千行）
    对话历史         ← 最不值钱，最先该裁

好消息是：它们【不可能无限增长】—— 有个硬上限叫 Context Window。
坏消息是：谁先被挤出去，决定了 Agent 是否还"活着"。

所以这个模块的核心命题是：
    ⭐ 在固定的 token 预算内，装进【最重要的那些东西】。

======================================================================
 不用框架怎么做（设计三原则）
======================================================================
① 先按【优先级】排序，而不是按时间
   现在的 trim_by_tokens 是"从最旧裁"——它假设所有东西价值相同。
   实际上 System 比第 1 轮寒暄重要得多。

② Pinned 项不参与裁剪
   System 和当前问题必须留，哪怕单独就超预算。
   （宁可请求失败报警，也不能静默地"换个人"或"答非所问"）

③ 单条过大的要【截断】，不是直接丢
   Tool 返回 5000 行，你丢了它 Agent 就没法推理；
   截断到前 N 行 + 标记，Agent 至少知道"有个很大的结果"。

======================================================================
 生产环境会在哪里出问题（已知的坑）
======================================================================
1. Token 估算不准   → 实测线性估算误差 ±30%，只能偏保守
2. RAG 召回太长     → 10 个 chunk × 500 token = 5000，直接吃掉整个预算
3. Tool Result 爆炸 → 一次查询返回 100KB，必须截断
4. Memory 污染      → 提取错误的记忆会一路错下去，且占预算
5. Context Lost     → 静默丢掉了关键信息，Agent 行为变得不可解释
6. Cost 飙升        → 每轮重发全部上下文，轮数一多成本是平方级增长
7. 长任务失控        → 30 轮后的 Agent 已经"忘了"最初的目标

本模块直接对应处理 1/2/3/5 和 6 的观测；4/7 属于上层策略。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

# ======================================================================
#  一、Token 估算
#
#  为什么必须估算而不能精确算？
#      裁剪发生在【发请求之前】。为了数 token 而先发一次请求 ——
#      那本身就要花钱花时间，逻辑上也不成立。
#
#  所以工业界是「两套账」：
#      ① 本地估算 → 做预算决策（快、免费、有误差）
#      ② API 的 usage → 事后精确记账（准、但事后才知道）
#
#  实测校准的误差（16 个样本，真实 API 调用）：
#      中文      ≈ 0.5 token/字
#      代码/JSON ≈ 0.28
#      英文散文  ≈ 0.14
#      空白      ≈ 0.05
#      平均绝对误差 24%~34%，最坏 80%（英文散文会被高估）
#
#  ⚠️ 刻意偏高估：高估只是多裁历史（记性差一点），
#     低估会让请求超出模型窗口而【直接失败】。
#     这是「安全优先于精确」的工程取舍。
# ======================================================================

_TOKENS_PER_CJK_CHAR = 0.5
_TOKENS_PER_WS_CHAR = 0.05
_TOKENS_PER_OTHER_CHAR = 0.28

# 每条消息的结构开销：role 标记、消息分隔符、特殊 token
# 实测：单条消息固定开销约 4 token（与实际内容无关）
_TOKENS_PER_MESSAGE_OVERHEAD = 4

# 一次请求本身的固定开销（模板、结束符等）——实测约 4
_TOKENS_PER_REQUEST_OVERHEAD = 4


def is_cjk(ch: str) -> bool:
    """判断是不是中日韩字符。

    为何要单独区分：这类字符 token 密度和英文差 3 倍以上。
        中文「你好世界」 4 字 → 2 token（0.5/字）
        英文 "abcdefgh" 8 字符 → 2 token（0.25/字符）
    混在一起算两边都不准。
    """
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF      # CJK 统一表意文字
        or 0x3400 <= code <= 0x4DBF   # 扩展 A
        or 0x3000 <= code <= 0x303F   # CJK 标点
        or 0xFF00 <= code <= 0xFFEF   # 全角字符
        or 0x3040 <= code <= 0x30FF   # 日文假名
    )


def estimate_tokens(text: str) -> int:
    """估算一段文本的 token 数（偏保守/偏高估）。

    误差约 ±30%。用途是"要不要裁"，不是"收多少钱"。
    精确值请读 API 返回的 usage.prompt_tokens。
    """
    if not text:
        return 1

    cjk = ws = 0
    for ch in text:
        if ch.isspace():
            ws += 1
        elif is_cjk(ch):
            cjk += 1
    other = len(text) - cjk - ws

    estimated = (
        cjk * _TOKENS_PER_CJK_CHAR
        + ws * _TOKENS_PER_WS_CHAR
        + other * _TOKENS_PER_OTHER_CHAR
    )
    # 用 round 而非 int()：int(0.9) 会截成 0，导致极小内容算成 0 token
    return max(1, round(estimated))


# ======================================================================
#  二、Context 来源与优先级
# ======================================================================


class ContextSource(str, Enum):
    """上下文的来源。

    继承 str 让它可以和普通字符串混用（写日志、做 dict key 都方便）。
    """

    SYSTEM = "system"        # 人设/规则
    QUESTION = "question"    # 当前用户问题
    MEMORY = "memory"        # 长期记忆（结构化事实）
    RAG = "rag"              # 检索到的文档片段
    TOOL = "tool"            # 工具执行结果
    HISTORY = "history"      # 对话历史


# ⭐ 优先级表：预算不够时，数字大的先保留
#
# 这个顺序不是随便定的，它对应一个反问：
#     "如果只能保留一样，保留哪个？"
#
#     SYSTEM  100  ← 换人设 = 换了整个应用的行为
#     QUESTION 90  ← 没有问题 = 完全答非所问
#     MEMORY   80  ← 关系到"对谁说话"，且通常很小
#     RAG      70  ← 直接决定答案质量
#     TOOL     60  ← 推理需要，但通常可截断
#     HISTORY  50  ← 最不值钱：它是"发生过什么"，不是"现在需要什么"
#
# ⚠️ 注意 HISTORY 最低是【有意为之】——
#    很多人直觉觉得"近的对话最重要"，但系统性问题恰恰是
#    把宝贵的预算花在了"嗯嗯"、"谢谢"这类寒暄上。
DEFAULT_PRIORITY: dict[ContextSource, int] = {
    ContextSource.SYSTEM: 100,
    ContextSource.QUESTION: 90,
    ContextSource.MEMORY: 80,
    ContextSource.RAG: 70,
    ContextSource.TOOL: 60,
    ContextSource.HISTORY: 50,
}


# ======================================================================
#  三、数据结构
# ======================================================================


@dataclass
class Segment:
    """一个待组装进 Context 的片段。

    一个 Segment 可以包含多条消息（比如"1 个 RAG 文档"可能是 3 条 user 消息）。
    """

    source: ContextSource
    messages: list[dict[str, str]]
    # 优先级；None 表示用 DEFAULT_PRIORITY 里的默认值
    priority: int | None = None
    # pinned=True 表示"无论如何都要保留"（system、当前问题）
    pinned: bool = False
    # 用于日志/报告的标签
    label: str = ""
    # 单条过大的截断上限（token）。None 表示不截断。
    # ⭐ Tool result 必须设这个 —— 一次 SQL 可能返回几千行
    max_tokens: int | None = None
    # ⭐ 装不下时"保留哪一部分"的方向：
    #
    #   "tail" —— 从【最后】往前保留（历史：最新的最有价值）
    #   "head" —— 从【开头】往后保留（RAG：调用方已按相关度排好序）
    #
    # ⚠️ 为什么必须有这个字段？
    #    最初我写成"装不下就整块丢"，结果测试发现：
    #       预算 1500，RAG 需 1860 → 整块被丢
    #       但剩下 962 token 完全没用上，处于浪费状态
    #    → 贪心整块分配会浪费预算，必须支持"部分保留"。
    keep_direction: str = "head"

    def __post_init__(self) -> None:
        if self.priority is None:
            self.priority = DEFAULT_PRIORITY.get(self.source, 50)
        if not self.label:
            self.label = str(self.source)

    def cost(self) -> int:
        """这个片段的总 token 估算（含每条消息的结构开销）。"""
        return sum(
            estimate_tokens(m.get("content") or "") + _TOKENS_PER_MESSAGE_OVERHEAD
            for m in self.messages
        )


@dataclass
class SourceStats:
    """某个来源的统计（用于可观测性）。"""

    segments: int = 0
    messages: int = 0
    tokens: int = 0

    def add(self, msg_count: int, tokens: int) -> None:
        self.segments += 1
        self.messages += msg_count
        self.tokens += tokens


@dataclass
class ContextReport:
    """组装结果报告 —— 这是「可观测性」的入口。

    ⭐ 为什么需要它？
       没有报告时，Context Lost 是【静默】的：
       Agent 行为变差，但你不知道是"模型不行"还是"信息被裁掉了"。
       有了报告，每次请求都能回答：
           "这次丢了什么？丢了多少 token？"
    """

    budget: int = 0
    used: int = 0
    kept: dict[str, SourceStats] = field(default_factory=dict)
    dropped: dict[str, SourceStats] = field(default_factory=dict)
    truncated: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def dropped_tokens(self) -> int:
        return sum(s.tokens for s in self.dropped.values())

    @property
    def utilization(self) -> float:
        return self.used / self.budget if self.budget else 0.0

    def summary(self) -> str:
        """一行摘要，方便打进日志。"""
        parts = [f"{self.used}/{self.budget} token ({self.utilization:.0%})"]
        if self.kept:
            kept_str = " ".join(
                f"{k}:{v.messages}条" for k, v in sorted(self.kept.items())
            )
            parts.append(f"保留 {kept_str}")
        if self.dropped:
            drop_str = " ".join(
                f"{k}:{v.messages}条/{v.tokens}tok" for k, v in sorted(self.dropped.items())
            )
            parts.append(f"丢弃 {drop_str}")
        if self.truncated:
            parts.append(f"截断 {len(self.truncated)}处")
        return " | ".join(parts)

    def detail(self) -> str:
        """多行详细报告。"""
        lines = ["Context 组装报告", "=" * 60]
        lines.append(f"  预算      : {self.budget} token")
        lines.append(f"  实际使用  : {self.used} token ({self.utilization:.1%})")
        lines.append(f"  丢掉的    : {self.dropped_tokens} token")
        lines.append("")
        if self.kept:
            lines.append("  保留：")
            for src, st in sorted(self.kept.items()):
                lines.append(f"    {src:<10} {st.messages:>3} 条  {st.tokens:>5} token")
        if self.dropped:
            lines.append("  丢弃：")
            for src, st in sorted(self.dropped.items()):
                lines.append(f"    {src:<10} {st.messages:>3} 条  {st.tokens:>5} token")
        if self.truncated:
            lines.append("  截断：")
            for label in self.truncated:
                lines.append(f"    {label}")
        if self.warnings:
            lines.append("  警告：")
            for w in self.warnings:
                lines.append(f"    {w}")
        return "\n".join(lines)


# ======================================================================
#  四、Context Manager
# ======================================================================


class ContextManager:
    """按 token 预算组装上下文。

    典型用法（Agent Loop 里）：

        cm = ContextManager(budget=8000)
        cm.add_system(system_prompt)
        cm.add_memory(memory_dict)
        cm.add_rag(retrieved_chunks)
        cm.add_tool_result("search_orders", big_text)
        cm.add_history(conversation)
        cm.add_question(user_input)

        messages = cm.build()          # 组装出最终 messages
        print(cm.report.detail())      # ⭐ 看谁被丢了
    """

    def __init__(self, budget: int = 8000) -> None:
        self.budget = budget
        self._segments: list[Segment] = []
        self.report = ContextReport(budget=budget)

    # ------------------------------------------------------------------
    # 添加来源（每个方法都刻意做成"语义化"的 —— 调用处一眼看懂在加什么）
    # ------------------------------------------------------------------

    def add_system(self, prompt: str) -> ContextManager:
        """加 System Prompt。⭐ 自动 pinned —— 人设不能丢。"""
        self._segments.append(
            Segment(
                source=ContextSource.SYSTEM,
                messages=[{"role": "system", "content": prompt}],
                pinned=True,
                label="system_prompt",
            )
        )
        return self

    def add_question(self, question: str) -> ContextManager:
        """加当前问题。⭐ 自动 pinned —— 没有它什么都答不对。"""
        self._segments.append(
            Segment(
                source=ContextSource.QUESTION,
                messages=[{"role": "user", "content": question}],
                pinned=True,
                label="current_question",
            )
        )
        return self

    def add_memory(self, facts: dict[str, str], label: str = "user_memory") -> ContextManager:
        """加长期记忆（结构化事实）。

        为什么包成一条 system 消息而不是拆成多条？
            记忆是"背景知识"不是"对话内容"，放 system 更符合语义，
            也更不容易被模型误当成用户说过的话。
        """
        if not facts:
            return self
        import json

        body = "\n".join(f"- {k}: {v}" for k, v in facts.items() if v)
        if not body:
            return self
        self._segments.append(
            Segment(
                source=ContextSource.MEMORY,
                messages=[
                    {
                        "role": "system",
                        "content": f"关于当前用户的已知信息：\n{body}",
                    }
                ],
                label=label,
            )
        )
        return self

    def add_rag(self, chunks: Sequence[str], label: str = "rag") -> ContextManager:
        """加 RAG 检索结果。

        ⭐ 每个 chunk 单独一条消息（而不是拼成一大块）——
           这样预算不够时可以【逐块】保留，而不是"要么全要要么全不要"。
           调用方应按相关度【降序】传入，我们会从最相关的开始保留。

        ⚠️ 最常见的问题：召回 10 个 chunk × 500 token = 5000 token，
           直接吃掉整个预算。
        """
        if not chunks:
            return self
        self._segments.append(
            Segment(
                source=ContextSource.RAG,
                messages=[
                    {
                        "role": "system",
                        "content": f"参考资料 {i}/{len(chunks)}：\n{chunk}",
                    }
                    for i, chunk in enumerate(chunks, 1)
                ],
                label=label,
                max_tokens=2000,     # 给 RAG 一个总上限，防它挤死别人
                keep_direction="head",  # 从最相关的开始保留
            )
        )
        return self

    def add_tool_result(
        self, tool_name: str, result: str, max_tokens: int = 500
    ) -> ContextManager:
        """加工具执行结果。

        ⭐ Tool Result 是 Context 爆炸的头号元凶：
           一次 SQL 查询可能返回几千行，一次网页抓取可能几十 KB。
           所以【默认就给一个小的截断上限】，宁可让 Agent 知道
           "有个大结果被截断了"，也不要让它挤掉其他所有东西。
        """
        self._segments.append(
            Segment(
                source=ContextSource.TOOL,
                messages=[
                    {
                        "role": "user",
                        "content": f"[工具 {tool_name} 的结果]\n{result}",
                    }
                ],
                label=f"tool:{tool_name}",
                max_tokens=max_tokens,
            )
        )
        return self

    def add_history(self, messages: Sequence[dict[str, str]]) -> ContextManager:
        """加对话历史。

        ⚠️ 历史是【最可裁】的，所以优先级最低。
           装不下时从最旧开始丢（keep_direction="tail"），
           并保证 user/assistant 成对。
        """
        msgs = [dict(m) for m in messages if m.get("role") != "system"]
        if not msgs:
            return self
        self._segments.append(
            Segment(
                source=ContextSource.HISTORY,
                messages=msgs,
                label="conversation_history",
                keep_direction="tail",   # 从最新的开始保留
            )
        )
        return self

    # ------------------------------------------------------------------
    # 组装
    # ------------------------------------------------------------------

    def build(self) -> list[dict[str, str]]:
        """按预算组装出最终 messages。

        Returns:
            OpenAI 格式的 messages 列表，顺序为
            system → memory → rag → history → tool → question。

        Raises:
            RuntimeError: pinned 内容单独就超预算（配置错误，应该早暴露）。
        """
        report = ContextReport(budget=self.budget)
        self.report = report

        # ---- 步骤 1：按优先级降序排列（同优先级保持添加顺序，稳定排序）----
        ordered = sorted(self._segments, key=lambda s: -(s.priority or 0))

        # ---- 步骤 2：pinned 先无条件占位 ----
        #
        # ⚠️ 这一步必须独立做，不能和普通项混在一起判断。
        #    因为 pinned 的语义是"超预算也要留"，若走同一个 if 分支就被裁了。
        pinned = [s for s in ordered if s.pinned]
        rest = [s for s in ordered if not s.pinned]

        pinned_cost = sum(s.cost() for s in pinned)
        if pinned_cost > self.budget:
            # 启动期就该发现的配置错误 —— 让它炸，而不是静默降级
            raise RuntimeError(
                f"pinned 内容（{pinned_cost} token）超过总预算（{self.budget}）。\n"
                f"  这通常意味着：system prompt 太长、或预算设得太小。\n"
                f"  请调大预算或精简 system prompt，不要指望运行时能救。"
            )

        used = pinned_cost
        accepted: list[Segment] = list(pinned)
        for s in pinned:
            st = report.kept.setdefault(s.source.value, SourceStats())
            st.add(len(s.messages), s.cost())

        # ---- 步骤 3：剩余预算按优先级填充 ----
        #
        # ⚠️⚠️ 这里的核心设计教训（测试跑出来的真实 bug）：
        #
        #   最初的实现是"装不下就整块丢"。测试发现：
        #       预算 1500，RAG 需 1860 → 整块被丢
        #       但剩下 962 token 完全没用上，处于浪费状态
        #   也就是【贪心整块分配会浪费预算，让高价值内容白白损失】。
        #
        #   修正：装不下时先尝试【部分保留】——
        #       HISTORY 从最新往前拿
        #       RAG     从最相关往后拿
        #       TOOL    已在上一步截断过
        #   只有连一条都放不下才整块丢弃。
        for seg in rest:
            # 先看单条截断（tool/rag 可能单条就巨大）
            seg, trunc_note = self._maybe_truncate(seg)
            if trunc_note:
                report.truncated.append(trunc_note)

            cost = seg.cost()
            remaining = self.budget - used

            # 情况 1：整块装得下
            if cost <= remaining:
                accepted.append(seg)
                used += cost
                report.kept.setdefault(seg.source.value, SourceStats()).add(
                    len(seg.messages), cost
                )
                continue

            # 情况 2：装不下 → 尝试部分保留
            partial, kept_n, kept_cost = self._partial_take(seg, remaining)
            if partial:
                accepted.append(
                    Segment(
                        source=seg.source,
                        messages=partial,
                        priority=seg.priority,
                        label=seg.label,
                        keep_direction=seg.keep_direction,
                    )
                )
                used += kept_cost
                report.kept.setdefault(seg.source.value, SourceStats()).add(
                    kept_n, kept_cost
                )

                dropped_n = len(seg.messages) - kept_n
                if dropped_n:
                    report.dropped.setdefault(seg.source.value, SourceStats()).add(
                        dropped_n, cost - kept_cost
                    )
                    report.truncated.append(
                        f"{seg.label}: 部分保留 {kept_n}/{len(seg.messages)} 条"
                        f"（{kept_cost}/{cost} token）"
                    )
                continue

            # 情况 3：连一条都装不下 → 整块丢弃，并记账
            report.dropped.setdefault(seg.source.value, SourceStats()).add(
                len(seg.messages), cost
            )

        # ---- 步骤 4：按【语义顺序】输出，而不是按优先级顺序 ----
        #
        # ⭐ 为什么？优先级只用于"决定谁留下"，
        #    但 messages 的顺序影响模型理解：
        #    参考资料应该在对话【之前】，当前问题应该在最【后】。
        order = [
            ContextSource.SYSTEM,
            ContextSource.MEMORY,
            ContextSource.RAG,
            ContextSource.HISTORY,
            ContextSource.TOOL,
            ContextSource.QUESTION,
        ]
        accepted.sort(key=lambda s: order.index(s.source))

        out: list[dict[str, str]] = []
        for seg in accepted:
            out.extend(seg.messages)

        report.used = used
        if report.utilization > 0.95:
            report.warnings.append(
                f"预算利用率 {report.utilization:.0%}，已接近上限；"
                f"下一步的 tool result / RAG 很可能被裁"
            )
        if report.dropped_tokens > 0:
            report.warnings.append(
                f"本轮丢弃 {report.dropped_tokens} token —— "
                f"如果答案质量下降，先检查这里"
            )
        return out

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _maybe_truncate(self, seg: Segment) -> tuple[Segment, str | None]:
        """单条过大时按 max_tokens 截断。

        ⭐ 为什么"截断"比"丢弃"好？
           丢弃 = Agent 完全不知道发生过什么，推理链条断裂。
           截断 = Agent 知道"有个结果太大了，这里是开头部分"，
                  至少能决定"要不要换个方式再查一次"。

        截断策略：按【字符】近似切（无法精确按 token 切，因为
        我们用的是线性估算，不是分词器）。留 10% 余量。
        """
        if seg.max_tokens is None:
            return seg, None

        cost = seg.cost()
        if cost <= seg.max_tokens:
            return seg, None

        # token 预算 → 字符数的粗略换算（用最保守的密度 0.5 反推）
        # 0.5 token/字 → 字 ≈ token / 0.5。再留 10% 余量给截断标记。
        char_limit = int(seg.max_tokens / _TOKENS_PER_CJK_CHAR * 0.9)

        new_msgs = []
        for i, m in enumerate(seg.messages):
            content = m.get("content") or ""
            if len(content) > char_limit:
                head = content[:char_limit]
                content = (
                    f"{head}\n\n"
                    f"⚠️ [内容过长已截断：原始约 {cost} token，"
                    f"此处仅保留开头约 {seg.max_tokens} token。"
                    f"如需完整内容请缩小查询范围后重试。]"
                )
            new_msgs.append({**m, "content": content})

        return (
            Segment(
                source=seg.source,
                messages=new_msgs,
                priority=seg.priority,
                pinned=seg.pinned,
                label=seg.label,
            ),
            f"{seg.label}: {cost} → {seg.max_tokens} token（原 {len(seg.messages)} 条消息）",
        )

    @staticmethod
    def _partial_take(
        seg: Segment, budget: int
    ) -> tuple[list[dict[str, str]], int, int]:
        """在预算内从 segment 里【部分】取消息。

        方向由 ``seg.keep_direction`` 决定：
            "tail" —— 从最后往前取，再翻回正常顺序（历史：最新的最值钱）
            "head" —— 从开头往后取（RAG：调用方已按相关度降序传入）

        ⚠️ 取完后如果 source 是 HISTORY，还要修一下边界：
            ① 不切开 user/assistant 对（否则模型会看到"没有提问的回答"）
            ② 首条必须是 user
           这两条是【语义】约束，与预算策略无关。

        Returns:
            (保留的消息, 保留条数, 保留的 token 数)；一条都放不下时返回空列表。
        """
        if budget <= 0:
            return [], 0, 0

        def cost_of(msg: dict[str, str]) -> int:
            return (
                estimate_tokens(msg.get("content") or "")
                + _TOKENS_PER_MESSAGE_OVERHEAD
            )

        kept: list[dict[str, str]] = []
        used = 0

        if seg.keep_direction == "tail":
            # 从最新往旧装
            for msg in reversed(seg.messages):
                c = cost_of(msg)
                # `kept and` 的作用：kept 为空表示正在处理【最新那条】，
                # 无条件装进去（最新的一条必须保留）；非空则装不下就停。
                if kept and used + c > budget:
                    break
                kept.append(msg)
                used += c
            kept.reverse()
        else:
            # 从最相关往后装
            for msg in seg.messages:
                c = cost_of(msg)
                # 同理：第一条无条件装，避免"预算过小导致什么都没留"
                if kept and used + c > budget:
                    break
                kept.append(msg)
                used += c

        # 语义约束：历史必须从一条 user 开头，且不切开成对的消息
        if seg.source is ContextSource.HISTORY:
            start = 0
            while start < len(kept) and kept[start].get("role") != "user":
                start += 1
            kept = kept[start:]

        # 重新核算（可能切掉了开头几条）
        used = sum(cost_of(m) for m in kept)
        return kept, len(kept), used


# ======================================================================
#  五、便捷函数：单来源场景的简化入口
# ======================================================================


def count_messages_tokens(messages: Sequence[dict[str, str]]) -> int:
    """估算一组消息的总 token（发送前的预算检查）。"""
    return sum(
        estimate_tokens(m.get("content") or "") + _TOKENS_PER_MESSAGE_OVERHEAD
        for m in messages
    )


def trim_by_tokens(
    messages: Sequence[dict[str, str]],
    max_tokens: int = 2000,
) -> list[dict[str, str]]:
    """只处理【对话历史】的简化裁剪（多来源场景请用 ContextManager）。

    这个函数是给"还没有 Memory / RAG / Tool 的早期阶段"用的。
    它的三条规则与 ContextManager 内部完全一致 —— 不是两套逻辑。
    """
    system_msgs = [dict(m) for m in messages if m.get("role") == "system"]
    dialog = [dict(m) for m in messages if m.get("role") != "system"]

    system_cost = sum(
        estimate_tokens(m.get("content") or "") + _TOKENS_PER_MESSAGE_OVERHEAD
        for m in system_msgs
    )
    budget = max_tokens - system_cost
    if budget <= 0:
        return system_msgs

    seg = Segment(source=ContextSource.HISTORY, messages=dialog, keep_direction="tail")
    kept, _, _ = ContextManager._partial_take(seg, budget)
    return system_msgs + kept

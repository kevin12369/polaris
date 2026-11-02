"""知识库检索：BM25 排序 + 关键词高亮。

对 10~1000 条规模的知识库，BM25 表现稳定且无需向量库依赖。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import KbArticle
from .aliases import expand_query
from .tokenizer import tokenize

K1 = 1.5
B = 0.75

# 阈值标定参考语料规模（8 篇时正负样本可干净区分：正样本 ≥6.4，负样本 ≤1.9）
REFERENCE_DOCS = 8.0

# 精确短语通道：长度 ≥3 的拉丁词或形如 502 / ERR_CONN 的错误码
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{2,}|\b[A-Z]{2,5}[0-9]{0,4}\b")
# 明显无检索价值的通用词，精确匹配时忽略
_GENERIC_LATIN = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was",
    "were", "are", "you", "not", "but", "all", "can", "get", "his", "her",
    "error", "exception", "info", "warn", "debug", "trace", "stack",
}


def _exact_phrases(text: str) -> set[str]:
    """提取可用于精确匹配的短语：错误码、英文标识符等。"""
    out: set[str] = set()
    for m in _LATIN_TOKEN_RE.finditer(text or ""):
        tok = m.group(0).strip("._-").lower()
        if len(tok) >= 3 and tok not in _GENERIC_LATIN:
            out.add(tok)
    return out


def _doc_phrases(article: KbArticle) -> set[str]:
    """文档中出现过的精确匹配短语集合。"""
    parts = [article.title, article.content, article.summary, " ".join(article.tags or [])]
    for step in article.steps or []:
        if isinstance(step, dict):
            parts.append(str(step.get("title", "")))
            parts.append(str(step.get("detail", "")))
    phrases: set[str] = set()
    for p in parts:
        if not p:
            continue
        low = p.lower()
        for tok in _exact_phrases(p):
            # 要求在原文中以完整子串出现（避免 "api" 命中 "capital"）
            if tok in low:
                phrases.add(tok)
    return phrases


def _adaptive_min_score(min_score: float, n_docs: int) -> float:
    """
    BM25 的 IDF 值随语料规模剧烈波动：
    - 8 篇语料下，罕见词 IDF ≈ 2.7，相关条目得分 6.4
    - 1 篇语料下，同一词 IDF ≈ 0.29，得分骤降到 0.57

    若固定使用同一个绝对阈值，小知识库（小公司刚开始用时只有 1-5 条）
    会把所有相关条目都过滤掉。因此阈值随语料规模线性放宽，
    并以"覆盖率"和"精确短语命中"作为与语料规模无关的主判据。
    """
    if min_score <= 0:
        return 0.0
    return min_score * min(1.0, n_docs / REFERENCE_DOCS)


@dataclass
class ScoredArticle:
    article: KbArticle
    score: float
    matched_terms: list[str]
    # 精确命中的短语（错误码/英文标识符），用于展示"为什么判定为相关"
    exact_hits: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.exact_hits is None:
            self.exact_hits = []


def _doc_tokens(article: KbArticle) -> list[str]:
    parts = [article.title, article.summary, article.content, " ".join(article.tags or [])]
    for step in article.steps or []:
        if isinstance(step, dict):
            parts.append(str(step.get("title", "")))
            parts.append(str(step.get("detail", "")))
    return tokenize(" ".join(p for p in parts if p))


def search(
    db: Session,
    company_id: int,
    query: str,
    limit: int = 5,
    threshold: float = 0.0,
    min_coverage: float = 0.0,
    min_score: float = 0.0,
) -> list[ScoredArticle]:
    """
    在指定租户的知识库内检索，返回按 BM25 分数降序的条目。

    双重相关性判据（缺一不可）：
    - min_score：BM25 分数下限。阈值随语料规模自适应放宽（见 _adaptive_min_score），
      因为小知识库下 IDF 值天然偏低，用固定绝对阈值会误杀相关条目。
    - min_coverage：查询 token 的最低命中覆盖率。这是与语料规模无关的主判据，
      防止少量高 IDF 稀有词（如错误码 502）单独命中就把不相干文档顶上来。
    """
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    articles = (
        db.execute(select(KbArticle).where(KbArticle.company_id == company_id))
        .scalars()
        .all()
    )
    if not articles:
        return []

    docs = [(a, _doc_tokens(a)) for a in articles]
    n_docs = len(docs)
    avg_len = sum(len(t) for _, t in docs) / n_docs if n_docs else 0.0
    if avg_len == 0:
        avg_len = 1.0
    effective_min_score = _adaptive_min_score(min_score, n_docs)

    # 文档频率
    df: dict[str, int] = {}
    for _, tokens in docs:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1

    q_set = set(q_tokens)
    # 中英术语别名扩展：英文报错日志 → 中文知识库用词
    # （目标用户的日志是英文、知识库是中文，不处理会显著降低命中率）
    alias_tokens: set[str] = set()
    for canonical in expand_query(query):
        alias_tokens.update(tokenize(canonical))
    # 别名 token 单独统计，不计入覆盖率分母（否则会稀释真实覆盖率），
    # 只在文档确实包含该词时加分。
    alias_only = alias_tokens - q_set

    # 精确短语通道：查询里的错误码/英文标识符（如 502、BadGateway、NullPointerException）
    # 直接与文档原文比对。对长日志型查询尤其重要 —— 那类查询里绝大多数 token 是噪声，
    # 纯统计检索会被噪声词的 IDF 稀释而失效。
    q_phrases = _exact_phrases(query)
    results: list[ScoredArticle] = []
    for article, tokens in docs:
        if not tokens:
            continue
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        doc_len = len(tokens)
        score = 0.0
        matched: list[str] = []
        for term in q_set:
            f = tf.get(term, 0)
            if f == 0:
                continue
            idf = math.log(1 + (n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            denom = f + K1 * (1 - B + B * doc_len / avg_len)
            score += idf * (f * (K1 + 1)) / denom
            matched.append(term)

        # 覆盖率：与语料规模无关的主判据（分母只算原始查询 token）
        coverage = len(matched) / len(q_set) if q_set else 0.0

        # 别名命中：英文报错对应到中文知识库用词
        alias_hits = [t for t in alias_only if tf.get(t, 0) > 0]
        if alias_hits:
            for term in alias_hits:
                idf = math.log(1 + (n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
                score += idf * 0.8
                matched.append(term)

        # 精确短语命中（错误码/标识符在文档原文中出现）
        doc_phrases = _doc_phrases(article)
        exact_hits = q_phrases & doc_phrases

        # 强信号（精确短语 / 别名）优先于覆盖率判定：
        # 英文报错查询的 token 天然与中文文档低重叠，若先按覆盖率过滤，
        # 中英错配场景会被全部误杀 —— 而这正是目标用户的日常。
        strong_signal = bool(exact_hits) or bool(alias_hits)

        # 判定为相关，满足以下任一：
        # 1) 强信号 —— 精确短语或别名命中
        # 2) 高覆盖率（>= 0.6）—— 查询主体内容确实在文档里，
        #    此时不因 BM25 分数偏低（语料小时 IDF 天然低）而误杀
        # 3) BM25 分数达标且覆盖率达标
        high_coverage = coverage >= 0.6
        if not (strong_signal or high_coverage or (score >= effective_min_score and coverage >= min_coverage)):
            continue
        if score <= threshold and not strong_signal:
            continue

        # 强信号给一个保底分，保证它能进入结果集并参与排序
        final_score = score
        if exact_hits:
            final_score += 0.5 * len(exact_hits)
        if alias_hits:
            final_score += 0.4 * len(alias_hits)
        if high_coverage and final_score < effective_min_score:
            final_score = effective_min_score

        results.append(
            ScoredArticle(
                article=article,
                score=round(final_score, 4),
                matched_terms=sorted(matched, key=len, reverse=True)[:8],
                exact_hits=sorted(exact_hits)[:5],
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


def highlight(text: str, terms: list[str], limit: int = 160) -> str:
    """截取包含命中词的片段，用于检索结果摘要。"""
    if not text:
        return ""
    if not terms:
        return text[:limit]
    lowered = text.lower()
    positions = [lowered.find(t) for t in terms if lowered.find(t) >= 0]
    if not positions:
        return text[:limit]
    start = max(0, min(positions) - 30)
    snippet = text[start : start + limit]
    return ("…" if start > 0 else "") + snippet + ("…" if start + limit < len(text) else "")

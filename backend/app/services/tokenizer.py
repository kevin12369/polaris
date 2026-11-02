"""中文友好的分词：优先 jieba（若已安装），否则退化为字符二元组。

字符二元组（bigram）对中文短文本检索效果稳定，且零依赖，
保证在没有 jieba 的环境里检索质量不塌陷。
"""
from __future__ import annotations

import re

try:  # pragma: no cover - 环境相关
    import jieba  # type: ignore

    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False

_LATIN_RE = re.compile(r"[a-zA-Z0-9_.\-]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# 停用词：高频无信息词
STOPWORDS = {
    "的", "了", "和", "是", "在", "有", "我", "我们", "你", "他", "它",
    "这", "那", "就", "不", "也", "都", "与", "及", "或", "但", "而", "被",
    "把", "给", "让", "从", "到", "会", "能", "可以", "一下", "一个",
    "the", "a", "an", "is", "are", "to", "of", "and", "or", "in", "on",
    "for", "with", "it", "this", "that", "be", "was", "were",
}


def tokenize(text: str) -> list[str]:
    """把文本切成检索用的 token 列表。"""
    if not text:
        return []
    text = text.lower()
    tokens: list[str] = []

    # 拉丁词 / 错误码 / 英文日志片段整体保留（如 "timeout"、"500"、"connection_reset"）
    for m in _LATIN_RE.finditer(text):
        tok = m.group(0).strip("._-")
        if tok and len(tok) > 1 and tok not in STOPWORDS:
            tokens.append(tok)

    # 中文
    cjk_segments = re.findall(r"[\u4e00-\u9fff]+", text)
    for seg in cjk_segments:
        if _HAS_JIEBA:
            words = [w.strip() for w in jieba.cut(seg)]
            words = [w for w in words if w and len(w) > 1 and w not in STOPWORDS]
            tokens.extend(words)
        # 无论是否有 jieba，都补上二元组，提升召回
        if len(seg) == 1:
            tokens.append(seg)
        else:
            for i in range(len(seg) - 1):
                bg = seg[i : i + 2]
                if bg not in STOPWORDS:
                    tokens.append(bg)
    return tokens


def keywords(text: str, top_n: int = 8) -> list[str]:
    """抽取用于展示的关键词（按出现频次排序）。"""
    counts: dict[str, int] = {}
    for tok in tokenize(text):
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:top_n]]

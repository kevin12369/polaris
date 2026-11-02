"""LLM 客户端（OpenAI 兼容协议）。

关键设计：**LLM 是可选增强，不是硬依赖**。
- 未配置 LLM_BASE_URL / LLM_API_KEY 时，全部能力降级为本地规则引擎，功能不缺失。
- 所有调用带超时与异常兜底，LLM 挂了不影响工单流转。
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_MODEL, LLM_TIMEOUT


def llm_available() -> bool:
    return LLM_ENABLED


def _post(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1200) -> str | None:
    if not LLM_ENABLED:
        return None
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content if isinstance(content, str) else None
    except Exception:
        # 任何异常都降级，不阻断主流程
        return None


def _extract_json(text: str | None) -> dict | None:
    """从模型输出里稳健地提取 JSON 对象（容忍 ```json 包裹和前后废话）。"""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def classify_ticket(title: str, content: str, categories: list[str]) -> dict | None:
    """让 LLM 判定工单分类与优先级，失败返回 None。"""
    system = (
        "你是企业级技术支持工单分类器。只输出 JSON，不要任何解释文字。"
        "字段：category（必须从给定类别中选择）、priority（P1/P2/P3/P4）、confidence（0-1 的数字）、reason（一句话中文说明）。"
        "优先级定义：P1=业务中断/数据丢失/全量不可用；P2=核心功能报错/部分用户受影响；P3=单个用户受影响/一般缺陷；P4=咨询建议。"
    )
    user = f"可选类别：{', '.join(categories)}\n\n标题：{title}\n\n详细描述：\n{content[:1500]}"
    data = _extract_json(_post([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=400))
    if not data:
        return None
    return {
        "category": data.get("category"),
        "priority": data.get("priority"),
        "confidence": data.get("confidence", 0.6),
        "reason": str(data.get("reason", ""))[:200],
    }


def generate_steps(error_text: str, articles: list[dict]) -> dict | None:
    """基于检索到的知识库条目生成排查步骤，失败返回 None。"""
    if not articles:
        return None
    system = (
        "你是资深技术支持工程师。根据给定的报错信息和知识库条目，输出结构化排查步骤。"
        "只输出 JSON，不要解释文字。格式："
        '{"summary":"一句话诊断结论","steps":[{"title":"步骤标题","detail":"具体操作说明（含命令/路径/检查点）","source":"引用的知识库标题"}]}'
        "步骤要可执行、有先后顺序，3-6 条。"
    )
    kb_text = "\n\n".join(
        f"[KB#{i+1}] {a.get('title','')}\n分类：{a.get('category','')}\n{a.get('content','')[:900]}"
        + ("" if not a.get("steps") else "\n已有步骤：" + json.dumps(a["steps"], ensure_ascii=False)[:600])
        for i, a in enumerate(articles[:5])
    )
    user = f"报错信息：\n{error_text[:1200]}\n\n可用知识库条目：\n{kb_text}"
    data = _extract_json(_post([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=1600))
    if not data or not isinstance(data.get("steps"), list):
        return None
    steps = []
    for s in data["steps"][:8]:
        if not isinstance(s, dict):
            continue
        steps.append(
            {
                "title": str(s.get("title", ""))[:120],
                "detail": str(s.get("detail", ""))[:900],
                "source": str(s.get("source", ""))[:120],
            }
        )
    if not steps:
        return None
    return {"summary": str(data.get("summary", ""))[:400], "steps": steps}


def summarize_article(title: str, content: str) -> str | None:
    """给知识库条目生成摘要，失败返回 None。"""
    system = "为技术知识库条目写一句话中文摘要（不超过 60 字），只输出摘要文本本身。"
    data = _post(
        [{"role": "system", "content": system}, {"role": "user", "content": f"标题：{title}\n内容：\n{content[:1500]}"}],
        max_tokens=200,
    )
    if not data:
        return None
    text = data.strip().strip('"').split("\n")[0]
    return text[:300] if text else None


def draft_steps_from_ticket(title: str, content: str, resolution: str, category: str) -> list[dict] | None:
    """把已解决的工单整理成可复用的排查步骤，失败返回 None。"""
    system = (
        "把一次技术支持工单的处理过程，整理成可复用的通用排查步骤。"
        "只输出 JSON：{'steps':[{'title':'步骤标题','detail':'具体操作说明'}]}，3-6 条，通用化表述，不要包含客户名/具体工单号。"
    )
    user = f"问题标题：{title}\n问题描述：{content[:1000]}\n处理过程：{resolution[:1500]}\n分类：{category}"
    data = _extract_json(_post([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=1400))
    if not data or not isinstance(data.get("steps"), list):
        return None
    steps = []
    for s in data["steps"][:8]:
        if isinstance(s, dict):
            steps.append({"title": str(s.get("title", ""))[:120], "detail": str(s.get("detail", ""))[:900]})
    return steps or None

"""AI 自动分类：规则引擎（离线可用）+ LLM 增强（配置了 LLM 时启用）。

分类输出：category / priority / confidence / reason。
规则引擎不依赖外部服务，保证小公司开箱即用；LLM 只做"规则置信度不足时"的兜底判定。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import DEFAULT_PRIORITY, TICKET_CATEGORIES
from .aliases import expand_query
from .tokenizer import tokenize

# 类别关键词权重表：命中即累加分数
CATEGORY_RULES: dict[str, dict[str, float]] = {
    "账号登录": {
        "登录": 3.0, "登陆": 3.0, "密码": 3.0, "验证码": 2.5, "权限": 2.0, "账号": 2.5,
        "账号被锁": 3.5, "锁定": 2.0, "登不上": 3.0, "注册": 1.5, "找回": 2.0,
        "token": 2.0, "过期": 1.8, "单点登录": 3.0, "sso": 3.0, "授权": 2.0, "鉴权": 2.5,
        "401": 2.5, "403": 2.0, "unauthorized": 2.5,
    },
    "支付账单": {
        "支付": 3.0, "账单": 3.0, "发票": 3.0, "退款": 3.0, "扣款": 3.0, "订单": 2.2,
        "付款": 2.8, "收费": 2.2, "订阅": 2.5, "优惠券": 2.5, "价格": 1.5, "对账": 2.8,
        "payment": 2.5, "invoice": 2.5, "refund": 2.5, "支付失败": 3.5,
    },
    "接口API": {
        "接口": 3.0, "api": 3.0, "报错": 2.2, "500": 2.5, "502": 2.5, "503": 2.5,
        "504": 2.5, "请求": 1.8, "返回值": 2.0, "调用": 2.2, "回调": 2.5, "webhook": 2.8,
        "超时": 2.0, "timeout": 2.5, "http": 2.0, "参数": 1.5, "sdk": 2.5, "网关": 2.2,
    },
    "数据问题": {
        "数据": 3.0, "丢失": 3.5, "错乱": 3.2, "重复": 2.5, "同步": 2.5, "脏数据": 3.0,
        "不一致": 2.8, "缺失": 2.5, "为空": 2.2, "null": 2.0, "主键": 2.5, "字段": 2.0,
        "导出": 2.0, "导入": 2.0, "报表": 2.2, "备份": 2.5, "恢复": 2.2,
    },
    "性能卡顿": {
        "卡顿": 3.5, "慢": 2.5, "性能": 3.0, "延迟": 2.8, "超时": 2.0, "cpu": 2.8,
        "内存": 2.8, "负载": 2.8, "并发": 2.2, "响应慢": 3.5, "卡": 2.2, "loading": 2.0,
        "崩溃": 3.0, "oom": 3.0,
    },
    "部署运维": {
        "部署": 3.0, "上线": 2.5, "服务器": 2.8, "环境": 2.2, "发布": 2.5, "回滚": 3.0,
        "配置": 2.0, "docker": 2.8, "k8s": 2.8, "容器": 2.5, "证书": 2.2, "域名": 2.2,
        "ssl": 2.2, "网络": 2.2, "nginx": 2.5, "监控": 2.0, "告警": 2.2, "进程": 2.0,
    },
    "功能缺陷": {
        "bug": 3.0, "缺陷": 3.0, "功能": 2.2, "异常": 2.2, "错误": 2.0, "无法": 2.0,
        "打不开": 3.0, "显示": 1.8, "按钮": 1.8, "页面": 2.0, "不生效": 2.8,
        "报错提示": 2.5, "偶现": 2.8, "复现": 2.5,
    },
    "咨询其他": {
        "咨询": 2.5, "怎么": 1.5, "如何": 1.5, "文档": 1.5, "建议": 1.2, "反馈": 1.5,
    },
}

# 优先级规则：命中强信号直接提升
PRIORITY_SIGNALS: list[tuple[str, str, float]] = [
    # (正则, 优先级, 权重)
    (r"(全部|所有).*(无法|不能|失败|宕机|不可用)", "P1", 1.0),
    (r"(服务|系统|站点).*(宕机|挂了|不可用|中断)", "P1", 1.0),
    (r"(数据|订单|账).*(丢失|损坏|清空)", "P1", 1.0),
    (r"(大面积|批量).*(失败|报错|异常)", "P1", 0.95),
    (r"(无法|不能).*(登录|支付|下单|提交)", "P1", 0.9),
    (r"(生产|线上).*(故障|事故)", "P1", 1.0),
    (r"报\s*错|error|exception|traceback", "P2", 0.7),
    (r"(影响|阻塞).*(多个|部分|一批)|多人|部分用户", "P2", 0.85),
    (r"(影响|阻塞).*(单个|一个|我)", "P3", 0.8),
    (r"建议|咨询|能否|可以吗|如何|怎么用", "P4", 0.9),
]


@dataclass
class Classification:
    category: str = "咨询其他"
    priority: str = DEFAULT_PRIORITY
    confidence: float = 0.0
    reason: str = ""
    engine: str = "rule"
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "engine": self.engine,
            "signals": self.signals,
        }


def classify_by_rules(title: str, content: str = "") -> Classification:
    """纯本地规则分类，不依赖任何外部服务。"""
    text = f"{title}\n{content}".lower()
    tokens = tokenize(text)

    # 中英术语别名扩展：英文报错日志（timeout / 502 / login）→ 中文分类用词
    alias_text = " ".join(expand_query(text))
    if alias_text:
        text = f"{text}\n{alias_text}"

    # 1) 类别打分
    scores: dict[str, float] = {c: 0.0 for c in TICKET_CATEGORIES}
    signals: list[str] = []
    for category, rules in CATEGORY_RULES.items():
        for keyword, weight in rules.items():
            if keyword in text:
                # 词越短权重越高（避免长词误命中）
                len_factor = max(0.6, min(1.4, 3.0 / max(len(keyword), 1)))
                scores[category] += weight * len_factor
                signals.append(keyword)

    # 2) 标题命中权重加倍（标题信息量更高）
    title_lower = title.lower()
    for category, rules in CATEGORY_RULES.items():
        for keyword, weight in rules.items():
            if keyword in title_lower:
                scores[category] += weight * 0.8

    # 3) 选出最高分类
    # 注意：全部类别得分都是 0 时 max() 会返回字典首个键，必须显式判定为"咨询其他"
    top = max(scores.values()) if scores else 0.0
    if top <= 0.0:
        best_category, confidence = "咨询其他", 0.25
    else:
        best_category = max(scores, key=lambda c: scores[c])
        second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
        # 置信度：绝对分 + 领先优势
        margin = (top - second) / top
        confidence = min(0.95, 0.35 + min(top, 8) / 16 + margin * 0.35)

    # 4) 优先级打分
    priority_scores: dict[str, float] = {"P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0}
    for pattern, prio, weight in PRIORITY_SIGNALS:
        if re.search(pattern, text):
            priority_scores[prio] += weight
    # 类别可以影响优先级
    if best_category in ("数据问题",) and scores.get("数据问题", 0) > 5:
        priority_scores["P1"] += 0.4
    if best_category == "功能缺陷" and scores.get("功能缺陷", 0) > 5:
        priority_scores["P2"] += 0.3
    if best_category == "咨询其他" and scores.get("咨询其他", 0) > 2:
        priority_scores["P4"] += 0.5

    best_priority = max(priority_scores, key=lambda p: priority_scores[p])
    if priority_scores[best_priority] == 0:
        best_priority = DEFAULT_PRIORITY
        # 有效 token 少 → 更像咨询
        if len(tokens) < 4:
            best_priority = "P4"

    reason_bits = []
    if signals:
        top_signals = sorted(set(signals), key=len, reverse=True)[:3]
        reason_bits.append("命中关键词：" + "、".join(top_signals))
    reason_bits.append(f"类别得分 {scores.get(best_category, 0):.1f}")
    reason_bits.append(f"优先级 {best_priority}")

    return Classification(
        category=best_category,
        priority=best_priority,
        confidence=confidence,
        reason="；".join(reason_bits),
        engine="rule",
        signals=sorted(set(signals))[:8],
    )


def classify(title: str, content: str = "", llm_result: dict | None = None) -> Classification:
    """
    综合分类入口。
    规则引擎先出结果；若配置了 LLM 且其判定与规则不一致，则以 LLM 为准（LLM 权重更高）。
    """
    base = classify_by_rules(title, content)
    if not llm_result:
        return base

    llm_category = llm_result.get("category")
    llm_priority = llm_result.get("priority")
    llm_conf = float(llm_result.get("confidence", 0.5))
    if not llm_category:
        return base

    changed = []
    if llm_category in TICKET_CATEGORIES and llm_category != base.category:
        changed.append(f"类别 {base.category}→{llm_category}")
        base.category = llm_category
    if llm_priority in ("P1", "P2", "P3", "P4") and llm_priority != base.priority:
        changed.append(f"优先级 {base.priority}→{llm_priority}")
        base.priority = llm_priority

    base.engine = "rule+llm"
    base.confidence = max(base.confidence, min(0.99, llm_conf))
    if changed:
        base.reason = "AI 复核修正：" + "，".join(changed) + "；" + base.reason
    else:
        base.reason = "AI 复核确认；" + base.reason
    return base

"""仪表盘路由：工单量 / 平均响应时长 / 超时率 / 知识库命中率。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import SLA_POLICY, STATUS_LABELS
from ..db import get_db
from ..deps import get_current_user
from ..models import KbArticle, RetrievalLog, Ticket, utcnow
from ..sla import working_minutes_between

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _avg(values: list[int]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


@router.get("")
def dashboard(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = utcnow()
    since = now - dt.timedelta(days=days)
    cid = user.company_id
    schedule = user.company.work_schedule if user.company else None

    tickets = db.execute(
        select(Ticket).where(Ticket.company_id == cid, Ticket.created_at >= since)
    ).scalars().all()
    all_tickets = db.execute(select(Ticket).where(Ticket.company_id == cid)).scalars().all()

    total = len(tickets)
    if total == 0:
        return {
            "range_days": days,
            "metrics": {
                "total_tickets": 0,
                "new_tickets": 0,
                "resolved_tickets": 0,
                "avg_response_minutes": 0,
                "avg_resolution_minutes": 0,
                "timeout_rate": 0,
                "response_timeout_rate": 0,
                "resolve_timeout_rate": 0,
                "kb_hit_rate": 0,
                "open_tickets": 0,
                "kb_articles": 0,
                "kb_total_hits": 0,
                "assistant_queries": 0,
                "assistant_hit_rate": 0,
            },
            "trend": [],
            "by_status": [],
            "by_category": [],
            "by_priority": [],
            "top_kb": [],
            "recent": [],
        }

    # ---- 核心指标 ----
    open_statuses = ("new", "triaged", "in_progress", "pending")
    open_tickets = [t for t in all_tickets if t.status in open_statuses]
    resolved = [t for t in tickets if t.resolved_at is not None]
    closed = [t for t in tickets if t.status == "closed"]

    # 平均响应时长（工作分钟）：仅统计已响应的工单
    response_minutes = [
        working_minutes_between(t.created_at, t.first_response_at, schedule)
        for t in tickets
        if t.first_response_at is not None
    ]
    resolution_minutes = [
        working_minutes_between(t.created_at, t.resolved_at, schedule)
        for t in tickets
        if t.resolved_at is not None
    ]

    # 超时率：响应超时 或 解决超时，任一超时即算超时
    def resp_breached(t: Ticket) -> bool:
        if t.first_response_at is not None:
            return t.sla_response_due is not None and t.first_response_at > t.sla_response_due
        return t.sla_response_due is not None and now > t.sla_response_due

    def resolve_breached(t: Ticket) -> bool:
        if t.resolved_at is not None:
            return t.sla_resolve_due is not None and t.resolved_at > t.sla_resolve_due
        return t.sla_resolve_due is not None and now > t.sla_resolve_due

    resp_breached_count = sum(1 for t in tickets if resp_breached(t))
    resolve_breached_count = sum(1 for t in tickets if resolve_breached(t))
    any_breached = sum(1 for t in tickets if resp_breached(t) or resolve_breached(t))

    # 知识库命中率：已解决工单中，关联了知识库条目的比例
    kb_linked = sum(1 for t in resolved if t.linked_kb_ids)
    kb_hit_rate = round(kb_linked / len(resolved) * 100, 1) if resolved else 0.0

    articles = db.execute(select(KbArticle).where(KbArticle.company_id == cid)).scalars().all()
    assistant_logs = db.execute(
        select(RetrievalLog).where(
            RetrievalLog.company_id == cid,
            RetrievalLog.source == "assistant",
            RetrievalLog.created_at >= since,
        )
    ).scalars().all()
    assistant_hits = sum(1 for l in assistant_logs if l.hit)

    # ---- 趋势（按天）----
    trend_map: dict[str, dict] = {}
    for i in range(days):
        d = (since + dt.timedelta(days=i)).strftime("%Y-%m-%d")
        trend_map[d] = {"date": d, "created": 0, "resolved": 0}
    for t in tickets:
        key = t.created_at.strftime("%Y-%m-%d")
        if key in trend_map:
            trend_map[key]["created"] += 1
        if t.resolved_at:
            rkey = t.resolved_at.strftime("%Y-%m-%d")
            if rkey in trend_map:
                trend_map[rkey]["resolved"] += 1
    trend = [trend_map[k] for k in sorted(trend_map.keys())]

    # ---- 分布 ----
    by_status: dict[str, int] = {}
    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1
    by_category: dict[str, int] = {}
    for t in tickets:
        by_category[t.category] = by_category.get(t.category, 0) + 1
    by_priority: dict[str, int] = {}
    for t in tickets:
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1

    # ---- 高频知识条目 ----
    top_kb = sorted(articles, key=lambda a: (a.hits or 0) + (a.views or 0), reverse=True)[:8]
    # ---- 待办优先的工单 ----
    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    recent = sorted(
        [t for t in tickets if t.status in open_statuses],
        key=lambda t: (priority_order.get(t.priority, 9), t.sla_resolve_due or dt.datetime.max),
    )[:8]

    return {
        "range_days": days,
        "metrics": {
            "total_tickets": total,
            "new_tickets": total,
            "resolved_tickets": len(resolved),
            "closed_tickets": len(closed),
            "open_tickets": len(open_tickets),
            "avg_response_minutes": _avg(response_minutes),
            "avg_resolution_minutes": _avg(resolution_minutes),
            "timeout_rate": round(any_breached / total * 100, 1),
            "response_timeout_rate": round(resp_breached_count / total * 100, 1),
            "resolve_timeout_rate": round(resolve_breached_count / total * 100, 1),
            "response_timeout_count": resp_breached_count,
            "resolve_timeout_count": resolve_breached_count,
            "kb_hit_rate": kb_hit_rate,
            "kb_linked_count": kb_linked,
            "kb_articles": len(articles),
            "kb_total_hits": sum(a.hits or 0 for a in articles),
            "assistant_queries": len(assistant_logs),
            "assistant_hit_rate": round(assistant_hits / len(assistant_logs) * 100, 1) if assistant_logs else 0.0,
        },
        "trend": trend,
        "by_status": [
            {"code": k, "label": STATUS_LABELS.get(k, k), "count": v} for k, v in sorted(by_status.items())
        ],
        "by_category": [
            {"category": k, "count": v} for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
        "by_priority": [
            {"priority": k, "label": SLA_POLICY.get(k, {}).get("label", k), "count": v}
            for k, v in sorted(by_priority.items())
        ],
        "top_kb": [
            {
                "id": a.id,
                "title": a.title,
                "category": a.category,
                "hits": a.hits or 0,
                "views": a.views or 0,
                "helpful": a.helpful or 0,
                "source": a.source,
            }
            for a in top_kb
        ],
        "recent": [
            {
                "id": t.id,
                "code": t.code,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "status_label": STATUS_LABELS.get(t.status, t.status),
                "sla_resolve_remaining": int((t.sla_resolve_due - now).total_seconds() // 60)
                if t.sla_resolve_due
                else None,
                "sla_response_breached": resp_breached(t),
            }
            for t in recent
        ],
    }

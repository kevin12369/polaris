"""工单路由：提交、AI 分类、SLA 倒计时、状态流转、关单沉淀知识库。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import DEFAULT_PRIORITY, SLA_POLICY, STATUS_LABELS, STATUS_TRANSITIONS, TICKET_CATEGORIES
from ..db import get_db
from ..deps import get_current_user
from ..models import KbArticle, RetrievalLog, Ticket, TicketEvent, User, utcnow
from ..schemas import CommentIn, KbPromoteIn, StatusChangeIn, SuggestIn, TicketCreateIn, TicketUpdateIn
from ..security import hash_password
from ..services import llm as llm_svc
from ..services.classifier import classify
from ..services.retrieval import search
from ..sla import is_breached, remaining_minutes, sla_deadlines, working_minutes_between

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _next_code(db: Session, company_id: int) -> str:
    """生成 TK-0001 形式的工单编号（按租户独立计数）。"""
    count = db.execute(
        select(func.count(Ticket.id)).where(Ticket.company_id == company_id)
    ).scalar_one()
    # 考虑历史删除，用 max 序号兜底
    existing = db.execute(
        select(Ticket.code).where(Ticket.company_id == company_id).order_by(Ticket.code.desc()).limit(1)
    ).scalar_one_or_none()
    seq = count
    if existing and existing.startswith("TK-"):
        try:
            seq = max(seq, int(existing.split("-")[1]))
        except (ValueError, IndexError):
            pass
    return f"TK-{seq + 1:04d}"


def _serialize(ticket: Ticket, now: dt.datetime, schedule: dict | None = None) -> dict:
    """工单序列化，附带 SLA 倒计时实时状态。

    schedule 为该租户的工作时间表（可为 None，使用全局默认）。
    """
    resp_breached = ticket.sla_response_breached
    resolve_breached = ticket.sla_resolve_breached
    # 实时重算：未完成的工单，随时间推移可能从"未超时"变为"已超时"
    if ticket.first_response_at is None:
        resp_breached = resp_breached or is_breached(ticket.sla_response_due, None, now)
    if ticket.resolved_at is None:
        resolve_breached = resolve_breached or is_breached(ticket.sla_resolve_due, None, now)

    resp_remaining = remaining_minutes(ticket.sla_response_due, now)
    resolve_remaining = remaining_minutes(ticket.sla_resolve_due, now)

    # 响应计时：已响应则显示已耗时，否则显示已过等待时间
    if ticket.first_response_at:
        response_minutes = working_minutes_between(ticket.created_at, ticket.first_response_at, schedule)
    else:
        response_minutes = working_minutes_between(ticket.created_at, now, schedule)

    resolve_minutes = None
    if ticket.resolved_at:
        resolve_minutes = working_minutes_between(ticket.created_at, ticket.resolved_at, schedule)

    return {
        "id": ticket.id,
        "code": ticket.code,
        "title": ticket.title,
        "content": ticket.content,
        "requester_name": ticket.requester_name,
        "requester_email": ticket.requester_email,
        "channel": ticket.channel,
        "category": ticket.category,
        "category_source": ticket.category_source,
        "priority": ticket.priority,
        "priority_label": SLA_POLICY.get(ticket.priority, {}).get("label", ""),
        "status": ticket.status,
        "status_label": STATUS_LABELS.get(ticket.status, ticket.status),
        "allowed_transitions": STATUS_TRANSITIONS.get(ticket.status, []),
        "confidence": ticket.confidence,
        "assignee_id": ticket.assignee_id,
        "tags": ticket.tags or [],
        "created_at": ticket.created_at.isoformat(),
        "first_response_at": ticket.first_response_at.isoformat() if ticket.first_response_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
        "sla_response_due": ticket.sla_response_due.isoformat() if ticket.sla_response_due else None,
        "sla_resolve_due": ticket.sla_resolve_due.isoformat() if ticket.sla_resolve_due else None,
        "sla_response_breached": resp_breached,
        "sla_resolve_breached": resolve_breached,
        "sla_response_remaining": resp_remaining,
        "sla_resolve_remaining": resolve_remaining,
        "sla_response_total": SLA_POLICY.get(ticket.priority, {}).get("response"),
        "sla_resolve_total": SLA_POLICY.get(ticket.priority, {}).get("resolve"),
        "response_minutes": response_minutes,
        "resolve_minutes": resolve_minutes,
        "kb_hit": ticket.kb_hit,
        "linked_kb_ids": ticket.linked_kb_ids or [],
        "resolution_note": ticket.resolution_note,
    }


def _add_event(
    db: Session,
    ticket: Ticket,
    user: User | None,
    etype: str,
    note: str = "",
    from_status: str | None = None,
    to_status: str | None = None,
) -> TicketEvent:
    ev = TicketEvent(
        ticket_id=ticket.id,
        company_id=ticket.company_id,
        actor_id=user.id if user else None,
        actor_name=user.name if user else "系统",
        type=etype,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
    db.add(ev)
    return ev


@router.get("/meta")
def meta():
    """前端需要的字典：分类、优先级、状态、SLA 策略。"""
    return {
        "categories": TICKET_CATEGORIES,
        "priorities": [
            {"code": k, "label": v["label"], "response_minutes": v["response"], "resolve_minutes": v["resolve"]}
            for k, v in SLA_POLICY.items()
        ],
        "statuses": [{"code": k, "label": v} for k, v in STATUS_LABELS.items()],
        "transitions": STATUS_TRANSITIONS,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """提交工单 → AI 自动分类 → 固化 SLA 截止时间。"""
    now = utcnow()
    schedule = user.company.work_schedule if user.company else None

    # 1) AI 分类（规则优先，配置了 LLM 时做复核）
    llm_result = None
    if llm_svc.llm_available():
        llm_result = llm_svc.classify_ticket(payload.title, payload.content, TICKET_CATEGORIES)
    cls = classify(payload.title, payload.content, llm_result)

    category = payload.category or cls.category
    category_source = "manual" if payload.category else "ai"
    priority = payload.priority or cls.priority

    # 2) 固化 SLA
    resp_due, resolve_due = sla_deadlines(priority, now, schedule)

    ticket = Ticket(
        company_id=user.company_id,
        code=_next_code(db, user.company_id),
        title=payload.title.strip(),
        content=payload.content or "",
        requester_name=payload.requester_name or user.name,
        requester_email=payload.requester_email or user.email,
        channel=payload.channel,
        category=category,
        category_source=category_source,
        priority=priority,
        status="new",
        confidence=cls.confidence,
        assignee_id=user.id,
        created_at=now,
        sla_response_due=resp_due,
        sla_resolve_due=resolve_due,
    )
    db.add(ticket)
    db.flush()

    _add_event(
        db, ticket, user, "created",
        note=f"工单创建（来源：{payload.channel}），AI 分类为「{category}」，优先级 {priority}，置信度 {cls.confidence:.0%}。{cls.reason}",
    )

    # 3) 同步检索知识库 —— 若命中，标记 kb_hit 并提示可用条目
    suggestions = search(
        db, user.company_id, f"{payload.title} {payload.content}", limit=3, min_score=3.0, min_coverage=0.15
    )
    suggestion_payload = []
    if suggestions:
        ticket.kb_hit = True
        for s in suggestions:
            suggestion_payload.append(
                {"id": s.article.id, "title": s.article.title, "score": s.score, "category": s.article.category}
            )
        db.add(
            RetrievalLog(
                company_id=user.company_id,
                source="ticket_suggest",
                ticket_id=ticket.id,
                query=f"{payload.title} {payload.content}"[:2000],
                matched_ids=[s.article.id for s in suggestions],
                hit=True,
                score=suggestions[0].score,
            )
        )
        _add_event(
            db, ticket, user, "kb",
            note="自动匹配到知识库条目：" + "、".join(f"《{s.article.title}》" for s in suggestions),
        )

    db.flush()
    return {
        "ticket": _serialize(ticket, now, schedule),
        "suggestions": suggestion_payload,
        "classification": cls.to_dict(),
    }


@router.get("")
def list_tickets(
    status_: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    category: str | None = None,
    q: str | None = None,
    assignee: str | None = Query(default=None, description="me|all|<user_id>"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Ticket).where(Ticket.company_id == user.company_id)
    if status_ and status_ != "all":
        stmt = stmt.where(Ticket.status == status_)
    if priority and priority != "all":
        stmt = stmt.where(Ticket.priority == priority)
    if category and category != "all":
        stmt = stmt.where(Ticket.category == category)
    if assignee == "me":
        stmt = stmt.where(Ticket.assignee_id == user.id)
    elif assignee and assignee.isdigit():
        stmt = stmt.where(Ticket.assignee_id == int(assignee))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((Ticket.title.like(like)) | (Ticket.content.like(like)) | (Ticket.code.like(like)))

    stmt = stmt.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
    tickets = db.execute(stmt).scalars().all()
    now = utcnow()
    schedule = user.company.work_schedule if user.company else None
    total = db.execute(
        select(func.count(Ticket.id)).where(Ticket.company_id == user.company_id)
    ).scalar_one()
    return {"total": total, "items": [_serialize(t, now, schedule) for t in tickets]}


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    schedule = user.company.work_schedule if user.company else None
    events = (
        db.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.id))
        .scalars()
        .all()
    )
    return {
        "ticket": _serialize(ticket, utcnow(), schedule),
        "events": [
            {
                "id": e.id,
                "type": e.type,
                "actor_name": e.actor_name,
                "from_status": e.from_status,
                "to_status": e.to_status,
                "note": e.note,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """人工覆盖分类/优先级等。注意：改优先级不重算已固化的 SLA 截止时间。"""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    schedule = user.company.work_schedule if user.company else None

    changes = []
    if payload.title is not None and payload.title != ticket.title:
        ticket.title = payload.title.strip()
        changes.append("标题")
    if payload.content is not None and payload.content != ticket.content:
        ticket.content = payload.content
        changes.append("描述")
    if payload.category is not None and payload.category != ticket.category:
        ticket.category = payload.category
        ticket.category_source = "manual"
        changes.append(f"分类→{payload.category}")
    if payload.priority is not None and payload.priority != ticket.priority:
        changes.append(f"优先级 {ticket.priority}→{payload.priority}")
        ticket.priority = payload.priority
    if payload.assignee_id is not None:
        assignee = db.get(User, payload.assignee_id)
        if assignee is None or assignee.company_id != user.company_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "无效的受理人")
        ticket.assignee_id = assignee.id
        changes.append(f"受理人→{assignee.name}")
    if payload.tags is not None:
        ticket.tags = payload.tags
        changes.append("标签")

    if changes:
        _add_event(db, ticket, user, "comment", note="人工修改：" + "、".join(changes))
    db.flush()
    return {"ticket": _serialize(ticket, utcnow(), schedule)}


@router.post("/{ticket_id}/status")
def change_status(
    ticket_id: int,
    payload: StatusChangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """状态流转：严格校验状态机；首次响应与 SLA 超时在此刻结算。"""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")

    to_status = payload.to_status
    if to_status not in STATUS_TRANSITIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知状态：{to_status}")

    allowed = STATUS_TRANSITIONS.get(ticket.status, [])
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"不允许从「{STATUS_LABELS.get(ticket.status, ticket.status)}」流转到「{STATUS_LABELS.get(to_status, to_status)}」",
        )

    now = utcnow()
    schedule = user.company.work_schedule if user.company else None
    from_status = ticket.status
    ticket.status = to_status

    # 首次响应：离开 new/triaged 进入处理流程即视为响应
    if ticket.first_response_at is None and to_status in ("in_progress", "resolved", "closed", "pending"):
        ticket.first_response_at = now

    # SLA 超时结算
    if ticket.first_response_at is not None:
        ticket.sla_response_breached = is_breached(ticket.sla_response_due, ticket.first_response_at, now)
    if ticket.resolved_at is None:
        ticket.sla_resolve_breached = is_breached(ticket.sla_resolve_due, None, now)

    if to_status == "resolved":
        ticket.resolved_at = now
        ticket.resolution_note = payload.resolution_note or ticket.resolution_note
        ticket.sla_resolve_breached = is_breached(ticket.sla_resolve_due, now, now)
    if to_status == "closed":
        ticket.closed_at = now
        if ticket.resolved_at is None:
            ticket.resolved_at = now

    note = payload.note or f"状态流转：{STATUS_LABELS.get(from_status, from_status)} → {STATUS_LABELS.get(to_status, to_status)}"
    _add_event(db, ticket, user, "status", note=note, from_status=from_status, to_status=to_status)
    db.flush()
    return {"ticket": _serialize(ticket, now, schedule)}


@router.post("/{ticket_id}/comment")
def add_comment(
    ticket_id: int,
    payload: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    now = utcnow()
    schedule = user.company.work_schedule if user.company else None
    if ticket.first_response_at is None:
        ticket.first_response_at = now
        ticket.sla_response_breached = is_breached(ticket.sla_response_due, now, now)
    _add_event(db, ticket, user, "comment", note=payload.note)
    db.flush()
    return {"ok": True, "ticket": _serialize(ticket, now, schedule)}


@router.post("/{ticket_id}/suggest")
def suggest(
    ticket_id: int,
    payload: SuggestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """根据工单内容检索知识库候选条目。"""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    query = payload.content or f"{ticket.title} {ticket.content}"
    scored = search(db, user.company_id, query, limit=5, min_score=3.0, min_coverage=0.15)
    if scored:
        db.add(
            RetrievalLog(
                company_id=user.company_id,
                source="ticket_suggest",
                ticket_id=ticket.id,
                query=query[:2000],
                matched_ids=[s.article.id for s in scored],
                hit=True,
                score=scored[0].score,
            )
        )
    return {
        "items": [
            {
                "id": s.article.id,
                "title": s.article.title,
                "category": s.article.category,
                "summary": s.article.summary,
                "score": s.score,
                "matched_terms": s.matched_terms,
            }
            for s in scored
        ]
    }


@router.post("/{ticket_id}/promote-to-kb", status_code=status.HTTP_201_CREATED)
def promote_to_kb(
    ticket_id: int,
    payload: KbPromoteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """关单时一键沉淀为知识库条目。"""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    schedule = user.company.work_schedule if user.company else None

    title = (payload.title or ticket.title).strip()
    body = payload.content if payload.content is not None else ""
    if not body:
        body = (
            f"## 问题现象\n{ticket.content or ticket.title}\n\n"
            f"## 处理过程\n{ticket.resolution_note or '（未填写处理记录）'}"
        )

    steps = payload.steps
    if steps is None:
        if llm_svc.llm_available():
            steps = llm_svc.draft_steps_from_ticket(
                ticket.title, ticket.content, ticket.resolution_note or "", ticket.category
            )
        if steps is None:
            steps = [
                {"title": "确认问题现象", "detail": ticket.content or ticket.title},
                {"title": "执行处理动作", "detail": ticket.resolution_note or "见原工单处理记录"},
                {"title": "验证与回归", "detail": "确认客户侧问题已消除，并回归验证相关流程无副作用。"},
            ]

    summary = payload.summary
    if summary is None:
        summary = ""
        if llm_svc.llm_available():
            summary = llm_svc.summarize_article(title, body)
        if not summary:
            summary = (ticket.resolution_note or ticket.content or ticket.title)[:200]

    article = KbArticle(
        company_id=user.company_id,
        title=title,
        content=body,
        summary=summary or "",
        category=payload.category or ticket.category,
        tags=payload.tags if payload.tags is not None else (ticket.tags or []),
        source="ticket",
        source_ticket_id=ticket.id,
        source_ticket_code=ticket.code,
        steps=steps,
        created_by=user.id,
    )
    db.add(article)
    db.flush()

    # 关联回工单，标记知识库命中
    linked = list(ticket.linked_kb_ids or [])
    if article.id not in linked:
        linked.append(article.id)
    ticket.linked_kb_ids = linked
    ticket.kb_hit = True

    _add_event(db, ticket, user, "kb", note=f"已沉淀为知识库条目《{article.title}》")
    db.flush()

    return {
        "article": {
            "id": article.id,
            "title": article.title,
            "category": article.category,
            "summary": article.summary,
            "source": article.source,
            "source_ticket_code": article.source_ticket_code,
            "steps": article.steps or [],
        },
        "ticket": _serialize(ticket, utcnow(), schedule),
    }

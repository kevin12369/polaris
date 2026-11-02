"""知识库路由：CRUD + 检索 + 命中统计。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import KbArticle, Ticket, utcnow
from ..schemas import KbCreateIn, KbUpdateIn
from ..services import llm as llm_svc
from ..services.retrieval import highlight, search

router = APIRouter(prefix="/api/kb", tags=["kb"])


def _serialize(a: KbArticle) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "summary": a.summary,
        "category": a.category,
        "tags": a.tags or [],
        "source": a.source,
        "source_ticket_id": a.source_ticket_id,
        "source_ticket_code": a.source_ticket_code,
        "steps": a.steps or [],
        "views": a.views,
        "hits": a.hits,
        "helpful": a.helpful,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


@router.get("")
def list_articles(
    q: str | None = None,
    category: str | None = None,
    source: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表。带 q 时走 BM25 检索并返回命中摘要。"""
    if q and q.strip():
        scored = search(db, user.company_id, q, limit=limit, min_score=2.5, min_coverage=0.12)
        items = []
        for s in scored:
            if category and s.article.category != category:
                continue
            if source and s.article.source != source:
                continue
            payload = _serialize(s.article)
            payload["score"] = s.score
            payload["snippet"] = highlight(
                s.article.content or s.article.summary, s.matched_terms
            )
            items.append(payload)
        total = len(items)
        return {"total": total, "items": items, "mode": "search"}

    stmt = select(KbArticle).where(KbArticle.company_id == user.company_id)
    if category and category != "all":
        stmt = stmt.where(KbArticle.category == category)
    if source and source != "all":
        stmt = stmt.where(KbArticle.source == source)
    stmt = stmt.order_by(KbArticle.updated_at.desc()).limit(limit).offset(offset)
    articles = db.execute(stmt).scalars().all()
    total = db.execute(
        select(func.count(KbArticle.id)).where(KbArticle.company_id == user.company_id)
    ).scalar_one()
    return {"total": total, "items": [_serialize(a) for a in articles], "mode": "list"}


@router.get("/categories")
def categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(KbArticle.category, func.count(KbArticle.id))
        .where(KbArticle.company_id == user.company_id)
        .group_by(KbArticle.category)
    ).all()
    return [{"category": c, "count": n} for c, n in rows]


@router.get("/{article_id}")
def get_article(article_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    article = db.get(KbArticle, article_id)
    if article is None or article.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库条目不存在")
    article.views = (article.views or 0) + 1
    db.flush()
    return _serialize(article)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_article(
    payload: KbCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    summary = payload.summary
    if not summary and llm_svc.llm_available():
        summary = llm_svc.summarize_article(payload.title, payload.content)
    article = KbArticle(
        company_id=user.company_id,
        title=payload.title.strip(),
        content=payload.content,
        summary=summary or "",
        category=payload.category,
        tags=payload.tags,
        steps=payload.steps,
        source="manual",
        created_by=user.id,
    )
    db.add(article)
    db.flush()
    return _serialize(article)


@router.put("/{article_id}")
def update_article(
    article_id: int,
    payload: KbUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = db.get(KbArticle, article_id)
    if article is None or article.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库条目不存在")
    if payload.title is not None:
        article.title = payload.title.strip()
    if payload.content is not None:
        article.content = payload.content
    if payload.summary is not None:
        article.summary = payload.summary
    if payload.category is not None:
        article.category = payload.category
    if payload.tags is not None:
        article.tags = payload.tags
    if payload.steps is not None:
        article.steps = payload.steps
    article.updated_at = utcnow()
    db.flush()
    return _serialize(article)


@router.delete("/{article_id}")
def delete_article(
    article_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = db.get(KbArticle, article_id)
    if article is None or article.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库条目不存在")
    # 解绑关联工单
    linked_tickets = (
        db.execute(
            select(Ticket).where(
                Ticket.company_id == user.company_id,
                KbArticle.id == article_id,
            )
        )
        .scalars()
        .all()
    )
    for t in db.execute(select(Ticket).where(Ticket.company_id == user.company_id)).scalars():
        ids = list(t.linked_kb_ids or [])
        if article_id in ids:
            ids.remove(article_id)
            t.linked_kb_ids = ids
            if not ids:
                t.kb_hit = False
    db.delete(article)
    db.flush()
    return {"ok": True}


@router.post("/{article_id}/helpful")
def mark_helpful(
    article_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = db.get(KbArticle, article_id)
    if article is None or article.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库条目不存在")
    article.helpful = (article.helpful or 0) + 1
    db.flush()
    return {"helpful": article.helpful}

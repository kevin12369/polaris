"""AI 排障助手路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import RetrievalLog, User
from ..schemas import TroubleshootIn
from ..services import llm as llm_svc
from ..services.troubleshooter import troubleshoot

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/status")
def status(user: User = Depends(get_current_user)):
    """告知前端当前引擎：LLM 增强 or 纯本地规则。"""
    return {
        "llm_enabled": llm_svc.llm_available(),
        "engine": "llm+kb" if llm_svc.llm_available() else "kb+rules",
        "note": "已接入大模型，输出更贴合具体报错" if llm_svc.llm_available() else "未配置大模型，使用本地规则引擎（功能完整可用）",
    }


@router.post("/troubleshoot")
def run_troubleshoot(
    payload: TroubleshootIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """输入报错 → 检索知识库 → 输出排查步骤。"""
    return troubleshoot(db, user.company_id, payload.error_text, payload.ticket_id)


@router.get("/history")
def history(
    limit: int = Query(default=20, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.execute(
            select(RetrievalLog)
            .where(RetrievalLog.company_id == user.company_id, RetrievalLog.source == "assistant")
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": l.id,
            "query": l.query,
            "hit": l.hit,
            "score": l.score,
            "matched_ids": l.matched_ids or [],
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]

"""企业设置：工作时间表等租户级配置。

为什么需要：不同小公司的排班不同（有的周六上班、有的做 24 小时轮班）。
SLA 的截止时间必须按真实工作时间算，否则倒计时没有意义。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import WORK_DAYS, WORK_END_HOUR, WORK_START_HOUR
from ..db import get_db
from ..deps import get_current_user
from ..models import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


class WorkScheduleIn(BaseModel):
    """工作时间表。work_days 用 0-6 表示周一到周日（与 Python weekday 一致）。"""

    work_days: list[int] = Field(default_factory=lambda: sorted(WORK_DAYS))
    work_start_hour: int = Field(default=WORK_START_HOUR, ge=0, le=23)
    work_end_hour: int = Field(default=WORK_END_HOUR, ge=1, le=24)


@router.get("/work-schedule")
def get_work_schedule(user: User = Depends(get_current_user)):
    sched = user.company.work_schedule
    return {
        "work_days": (sched or {}).get("work_days", sorted(WORK_DAYS)),
        "work_start_hour": (sched or {}).get("work_start_hour", WORK_START_HOUR),
        "work_end_hour": (sched or {}).get("work_end_hour", WORK_END_HOUR),
        "is_default": sched is None,
        "day_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    }


@router.put("/work-schedule")
def update_work_schedule(
    payload: WorkScheduleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置本企业的工作时间表。仅管理员可改。"""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅管理员可修改工作时间表")
    days = sorted(set(payload.work_days))
    if not days:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少要选择一天为工作日")
    if any(d < 0 or d > 6 for d in days):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "工作日取值必须为 0-6")
    if payload.work_end_hour <= payload.work_start_hour:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "下班时间必须晚于上班时间")

    user.company.work_schedule = {
        "work_days": days,
        "work_start_hour": payload.work_start_hour,
        "work_end_hour": payload.work_end_hour,
    }
    db.flush()
    return {
        "ok": True,
        "work_days": days,
        "work_start_hour": payload.work_start_hour,
        "work_end_hour": payload.work_end_hour,
        "note": "新设置仅对之后创建的工单生效；已有工单的 SLA 截止时间保持不变。",
    }

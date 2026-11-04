"""企业设置：工作时间表等租户级配置。

为什么需要：不同小公司的排班不同（有的周六上班、有的做 24 小时轮班）。
SLA 的截止时间必须按真实工作时间算，否则倒计时没有意义。

节假日：内置中国大陆法定节假日（app/holidays.py），租户可额外添加
自己的休假日与调休上班日。
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import WORK_DAYS, WORK_END_HOUR, WORK_START_HOUR
from ..db import get_db
from ..deps import get_current_user
from ..holidays import extra_workdays_for_year, holidays_for_year, known_years
from ..models import User

router = APIRouter(prefix="/api/settings", tags=["settings"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class WorkScheduleIn(BaseModel):
    """工作时间表。work_days 用 0-6 表示周一到周日（与 Python weekday 一致）。"""

    work_days: list[int] = Field(default_factory=lambda: sorted(WORK_DAYS))
    work_start_hour: int = Field(default=WORK_START_HOUR, ge=0, le=23)
    work_end_hour: int = Field(default=WORK_END_HOUR, ge=1, le=24)
    # 租户自定义休假日 / 调休上班日（ISO 日期字符串）
    holidays: list[str] = Field(default_factory=list)
    extra_workdays: list[str] = Field(default_factory=list)


def _validate_dates(items: list[str], field: str) -> list[str]:
    """校验并去重日期列表。"""
    out: list[str] = []
    for raw in items:
        if not isinstance(raw, str) or not _DATE_RE.match(raw.strip()):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{field} 中的日期格式必须为 YYYY-MM-DD，收到：{raw!r}",
            )
        d = raw.strip()
        if d not in out:
            out.append(d)
    return sorted(out)


@router.get("/work-schedule")
def get_work_schedule(user: User = Depends(get_current_user)):
    sched = user.company.work_schedule
    year = 2026
    return {
        "work_days": (sched or {}).get("work_days", sorted(WORK_DAYS)),
        "work_start_hour": (sched or {}).get("work_start_hour", WORK_START_HOUR),
        "work_end_hour": (sched or {}).get("work_end_hour", WORK_END_HOUR),
        "is_default": sched is None,
        "day_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        # 内置法定节假日（只读，租户无法修改）
        "builtin_holidays": holidays_for_year(year),
        "builtin_extra_workdays": extra_workdays_for_year(year),
        "builtin_years": known_years(),
        # 租户自定义
        "custom_holidays": (sched or {}).get("holidays", []),
        "custom_extra_workdays": (sched or {}).get("extra_workdays", []),
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

    holidays = _validate_dates(payload.holidays, "holidays")
    extra_workdays = _validate_dates(payload.extra_workdays, "extra_workdays")

    user.company.work_schedule = {
        "work_days": days,
        "work_start_hour": payload.work_start_hour,
        "work_end_hour": payload.work_end_hour,
        "holidays": holidays,
        "extra_workdays": extra_workdays,
    }
    db.flush()
    return {
        "ok": True,
        "work_days": days,
        "work_start_hour": payload.work_start_hour,
        "work_end_hour": payload.work_end_hour,
        "holidays": holidays,
        "extra_workdays": extra_workdays,
        "note": "新设置仅对之后创建的工单生效；已有工单的 SLA 截止时间保持不变。",
    }

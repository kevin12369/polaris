"""SLA 计算：按工作时间（默认周一至周五 09:00-18:00）累加工作分钟。

设计要点：
- SLA 在工单创建时按优先级固化截止时间，避免后续改优先级导致历史口径漂移。
- 超时判定基于"是否已超过截止时间"，与是否已响应/解决解耦（未响应的工单也会被标记超时）。
- 工作时间表支持按租户覆盖（Company.work_schedule），以适配不同排班，
  例如周六也上班的客服团队。schedule 为 None 时使用全局默认值。
- 节假日支持：内置中国大陆法定节假日（app/holidays.py），法定假日不计时，
  调休上班日照常计时。租户可额外添加自己的休假日与调休日。
"""
from __future__ import annotations

import datetime as dt

from .config import SLA_POLICY, WORK_DAYS, WORK_END_HOUR, WORK_START_HOUR
from .holidays import resolve_holiday_set


def _resolve(schedule: dict | None) -> tuple[set[int], int, int]:
    """解析工作时间表，返回 (工作日集合, 开始小时, 结束小时)。"""
    if not schedule:
        return WORK_DAYS, WORK_START_HOUR, WORK_END_HOUR
    days = schedule.get("work_days")
    if days is None:
        days_set = set(WORK_DAYS)
    else:
        days_set = {int(d) for d in days}
    start = int(schedule.get("work_start_hour", WORK_START_HOUR))
    end = int(schedule.get("work_end_hour", WORK_END_HOUR))
    if end <= start:
        # 配置非法时回落到默认，避免出现负工作时长
        return WORK_DAYS, WORK_START_HOUR, WORK_END_HOUR
    return days_set, start, end


def _tenant_holiday_overrides(schedule: dict | None) -> dict | None:
    """取出租户自定义的节假日 / 调休配置。"""
    if not schedule:
        return None
    holidays = schedule.get("holidays")
    extra = schedule.get("extra_workdays")
    if not holidays and not extra:
        return None
    return {"holidays": holidays or [], "extra_workdays": extra or []}


def _is_workday(
    d: dt.date,
    work_days: set[int],
    holidays: set[dt.date],
    extra_workdays: set[dt.date],
) -> bool:
    """
    判断某天是否工作日。

    优先级：调休上班日 > 法定/自定义休假日 > 常规工作日表。
    """
    if d in extra_workdays:
        return True
    if d in holidays:
        return False
    return d.weekday() in work_days


def _holiday_window(
    start: dt.date, end: dt.date, schedule: dict | None
) -> tuple[set[dt.date], set[dt.date]]:
    """解析区间内的休假日与调休上班日。"""
    return resolve_holiday_set(start, end, _tenant_holiday_overrides(schedule))


def add_working_minutes(
    start: dt.datetime, minutes: int, schedule: dict | None = None
) -> dt.datetime:
    """从 start 起，在工作时段内累加 minutes 个工作分钟，返回截止时间。"""
    if minutes <= 0:
        return start
    work_days, start_hour, end_hour = _resolve(schedule)
    cur = start
    remaining = minutes
    # 最多向后找 400 天，防御性上限
    for _ in range(400):
        day = cur.date()
        # 每次循环重新解析节假日窗口（覆盖未来区间，逐年扩展）
        holidays, extras = _holiday_window(cur.date(), cur.date() + dt.timedelta(days=60), schedule)
        if not _is_workday(day, work_days, holidays, extras):
            cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)
            continue
        work_start = dt.datetime.combine(day, dt.time(start_hour))
        work_end = dt.datetime.combine(day, dt.time(end_hour))
        if cur < work_start:
            cur = work_start
        if cur >= work_end:
            cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)
            continue
        avail = int((work_end - cur).total_seconds() // 60)
        if remaining <= avail:
            return cur + dt.timedelta(minutes=remaining)
        remaining -= avail
        cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)
    return cur


def working_minutes_between(
    start: dt.datetime, end: dt.datetime, schedule: dict | None = None
) -> int:
    """计算 start→end 之间经过的工作分钟数（用于平均响应时长）。"""
    if end <= start:
        return 0
    work_days, start_hour, end_hour = _resolve(schedule)
    holidays, extras = _holiday_window(start.date(), end.date(), schedule)
    total = 0
    cur = start
    while cur < end:
        day = cur.date()
        if not _is_workday(day, work_days, holidays, extras):
            cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)
            continue
        work_start = dt.datetime.combine(day, dt.time(start_hour))
        work_end = dt.datetime.combine(day, dt.time(end_hour))
        if cur < work_start:
            # 区间起点在工作时间之前：整段推进到工作开始
            if end <= work_start:
                # 结束时间也在上班前，这一段不含工作时间
                break
            cur = work_start
        if cur >= work_end:
            cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)
            continue
        segment_end = min(end, work_end)
        if segment_end <= cur:
            break
        total += int((segment_end - cur).total_seconds() // 60)
        cur = segment_end
        if cur >= work_end:
            cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)
    return total


def sla_deadlines(
    priority: str, created_at: dt.datetime, schedule: dict | None = None
) -> tuple[dt.datetime, dt.datetime]:
    """返回 (首次响应截止时间, 解决截止时间)。"""
    policy = SLA_POLICY.get(priority, SLA_POLICY["P3"])
    return (
        add_working_minutes(created_at, policy["response"], schedule),
        add_working_minutes(created_at, policy["resolve"], schedule),
    )


def is_breached(due: dt.datetime | None, done_at: dt.datetime | None, now: dt.datetime) -> bool:
    """
    是否超时。
    - 已完成(done_at)：完成时间晚于截止时间即超时
    - 未完成(done_at=None)：当前时间已过截止时间即超时（尚未完成就超时）
    """
    if due is None:
        return False
    reference = done_at or now
    return reference > due


def remaining_minutes(due: dt.datetime | None, now: dt.datetime) -> int | None:
    """剩余分钟数；已过期返回负数。"""
    if due is None:
        return None
    return int((due - now).total_seconds() // 60)

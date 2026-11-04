"""中国大陆法定节假日数据。

数据来源：国务院办公厅《关于 2026 年部分节假日安排的通知》（2025-11-04 发布）。
https://www.gov.cn/yaowen/liebiao/202511/content_7047099.htm

用途：让 SLA 倒计时跳过法定节假日，并在调休上班日正常计时。
没有节假日支持时，国庆期间创建的工单会在「放假」时继续倒计时 —— 显然不合理。

维护说明：
- 每年国务院办公厅发布次年安排后，在此追加一个年度条目。
- 若数据与官方公告有出入，以官方公告为准，并请提 issue 修正。
"""

from __future__ import annotations

import datetime as dt


def _dates(start: str, end: str) -> list[str]:
    """生成 [start, end] 闭区间内的所有日期（ISO 字符串）。"""
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    out = []
    cur = s
    while cur <= e:
        out.append(cur.isoformat())
        cur += dt.timedelta(days=1)
    return out


# ------------------------------------------------------------------
# 2026 年（国务院办公厅 2025-11-04 通知）
# ------------------------------------------------------------------
_HOLIDAY_2026 = (
    # 元旦：1月1日（周四）至3日（周六）放假调休，共3天
    _dates("2026-01-01", "2026-01-03")
    # 春节：2月15日（农历腊月二十八、周日）至23日（农历正月初七、周一），共9天
    + _dates("2026-02-15", "2026-02-23")
    # 清明节：4月4日（周六）至6日（周一），共3天
    + _dates("2026-04-04", "2026-04-06")
    # 劳动节：5月1日（周五）至5日（周二）放假调休，共5天
    + _dates("2026-05-01", "2026-05-05")
    # 端午节：6月19日（周五）至21日（周日），共3天
    + _dates("2026-06-19", "2026-06-21")
    # 中秋节：9月25日（周五）至27日（周日），共3天
    + _dates("2026-09-25", "2026-09-27")
    # 国庆节：10月1日（周四）至7日（周三）放假调休，共7天
    + _dates("2026-10-01", "2026-10-07")
)

# 调休上班日（原本是周末，但因假期安排需要上班）
_EXTRA_WORKDAYS_2026 = [
    "2026-01-04",  # 元旦：1月4日（周日）上班
    "2026-02-14",  # 春节：2月14日（周六）上班
    "2026-02-28",  # 春节：2月28日（周六）上班
    "2026-05-09",  # 劳动节：5月9日（周六）上班
    "2026-09-20",  # 国庆节：9月20日（周日）上班
    "2026-10-10",  # 国庆节：10月10日（周六）上班
]


# ------------------------------------------------------------------
# 年度数据表
# ------------------------------------------------------------------
_HOLIDAYS_BY_YEAR: dict[int, list[str]] = {
    2026: _HOLIDAY_2026,
}

_EXTRA_WORKDAYS_BY_YEAR: dict[int, list[str]] = {
    2026: _EXTRA_WORKDAYS_2026,
}


def holidays_for_year(year: int) -> list[str]:
    """返回该年度的法定休假日（ISO 字符串列表）。未收录的年份返回空。"""
    return list(_HOLIDAYS_BY_YEAR.get(year, []))


def extra_workdays_for_year(year: int) -> list[str]:
    """返回该年度的调休上班日（ISO 字符串列表）。"""
    return list(_EXTRA_WORKDAYS_BY_YEAR.get(year, []))


def known_years() -> list[int]:
    """已收录数据的年份。"""
    return sorted(_HOLIDAYS_BY_YEAR.keys())


def resolve_holiday_set(
    start: dt.date, end: dt.date, tenant_holidays: list[str] | None = None
) -> tuple[set[dt.date], set[dt.date]]:
    """
    计算 [start, end] 区间内的休假日与调休上班日。

    合并规则：
    - 法定节假日（全局内置）+ 租户自定义休假日 = 休假日集合
    - 调休上班日（全局内置）+ 租户自定义调休日 = 调休上班日集合
    - 若同一天既在休日又在调休日，以调休为准（该日上班）

    参数
    ----
    tenant_holidays: 租户自定义的附加休假日 / 调休上班日，
                     格式为 ISO 字符串列表，或 {"holidays": [...], "extra_workdays": [...]}。
    """
    holidays: set[dt.date] = set()
    extras: set[dt.date] = set()

    # 全置内置数据
    for year in range(start.year, end.year + 1):
        for d in holidays_for_year(year):
            holidays.add(dt.date.fromisoformat(d))
        for d in extra_workdays_for_year(year):
            extras.add(dt.date.fromisoformat(d))

    # 叠加租户自定义
    tenant_holidays = tenant_holidays or []
    if isinstance(tenant_holidays, dict):
        custom_holidays = tenant_holidays.get("holidays") or []
        custom_extras = tenant_holidays.get("extra_workdays") or []
    else:
        custom_holidays = tenant_holidays
        custom_extras = []
    for d in custom_holidays:
        try:
            holidays.add(dt.date.fromisoformat(d))
        except (TypeError, ValueError):
            continue
    for d in custom_extras:
        try:
            extras.add(dt.date.fromisoformat(d))
        except (TypeError, ValueError):
            continue

    # 调休优先：该日要上班
    holidays -= extras

    # 只保留区间内的日期
    holidays = {d for d in holidays if start <= d <= end}
    extras = {d for d in extras if start <= d <= end}
    return holidays, extras

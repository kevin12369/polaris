"""SLA 工作时间计算单元测试。

重点覆盖历史上出过的两个缺陷：
1. working_minutes_between 在"区间完全落在工作时间之外"时返回负数
2. add_working_minutes 跨越非工作日/下班的正确性

运行：python -m pytest tests/ -v
或：  python tests/test_sla.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.sla import add_working_minutes, is_breached, remaining_minutes, working_minutes_between

# 2026-11-02 是周一
MON = dt.datetime(2026, 11, 2, 9, 0)
TUE = dt.datetime(2026, 11, 3, 9, 0)
SAT = dt.datetime(2026, 11, 7, 9, 0)  # 周六
SUN = dt.datetime(2026, 11, 8, 9, 0)  # 周日


def test_within_workday():
    assert working_minutes_between(MON, MON + dt.timedelta(hours=1)) == 60


def test_fully_outside_workhours_returns_zero_not_negative():
    """回归：凌晨 4:25 → 4:50 完全在工作时间外，曾错误返回 -270。"""
    start = dt.datetime(2026, 11, 2, 4, 25)
    end = dt.datetime(2026, 11, 2, 4, 50)
    result = working_minutes_between(start, end)
    assert result == 0, f"期望 0，实际 {result}（负数说明 SLA 统计会错）"


def test_before_work_start_only():
    """06:00 → 08:00，仍在工作开始前，应为 0。"""
    start = dt.datetime(2026, 11, 2, 6, 0)
    end = dt.datetime(2026, 11, 2, 8, 0)
    assert working_minutes_between(start, end) == 0


def test_spanning_into_work_start():
    """04:25 → 10:00，只应计入 09:00-10:00 的 60 分钟。"""
    start = dt.datetime(2026, 11, 2, 4, 25)
    end = dt.datetime(2026, 11, 2, 10, 0)
    assert working_minutes_between(start, end) == 60


def test_after_work_end_only():
    """19:00 → 23:00，已下班，应为 0。"""
    start = dt.datetime(2026, 11, 2, 19, 0)
    end = dt.datetime(2026, 11, 2, 23, 0)
    assert working_minutes_between(start, end) == 0


def test_spanning_weekend():
    """周五 17:00 → 下周一 10:00：周五 17-18 共 60 分钟 + 周一 9-10 共 60 分钟。"""
    start = dt.datetime(2026, 11, 6, 17, 0)  # 周五
    end = dt.datetime(2026, 11, 9, 10, 0)  # 周一
    assert working_minutes_between(start, end) == 120


def test_reverse_order_is_zero():
    assert working_minutes_between(MON + dt.timedelta(hours=2), MON) == 0


def test_add_working_minutes_simple():
    assert add_working_minutes(MON, 60) == MON + dt.timedelta(hours=1)


def test_add_working_minutes_rolls_to_next_day():
    """周一 17:00 + 120 分钟 = 周二 10:00（工作时段 9h/天）。"""
    result = add_working_minutes(dt.datetime(2026, 11, 2, 17, 0), 120)
    assert result == dt.datetime(2026, 11, 3, 10, 0), f"实际 {result}"


def test_add_working_minutes_exactly_to_end_of_day():
    """周五 17:00 + 60 分钟 = 18:00（17:00-18:00 恰好 60 工作分钟，不需跨天）。"""
    result = add_working_minutes(dt.datetime(2026, 11, 6, 17, 0), 60)
    assert result == dt.datetime(2026, 11, 6, 18, 0), f"实际 {result}"


def test_add_working_minutes_skips_weekend():
    """周五 17:00 + 90 分钟 = 周一 09:30（周五 60 分钟 + 下周一 30 分钟，跳过周末）。"""
    result = add_working_minutes(dt.datetime(2026, 11, 6, 17, 0), 90)
    assert result == dt.datetime(2026, 11, 9, 9, 30), f"实际 {result}"


def test_add_working_minutes_before_work_start():
    """04:25 + 30 分钟 = 09:30。"""
    result = add_working_minutes(dt.datetime(2026, 11, 2, 4, 25), 30)
    assert result == dt.datetime(2026, 11, 2, 9, 30), f"实际 {result}"


def test_is_breached_variants():
    now = dt.datetime(2026, 11, 2, 12, 0)
    due = dt.datetime(2026, 11, 2, 11, 0)
    # 已完成但晚于截止 → 超时
    assert is_breached(due, dt.datetime(2026, 11, 2, 11, 30), now) is True
    # 已完成且早于截止 → 未超时
    assert is_breached(due, dt.datetime(2026, 11, 2, 10, 30), now) is False
    # 未完成且已过截止 → 超时
    assert is_breached(due, None, now) is True
    # 未完成且未过截止 → 未超时
    assert is_breached(dt.datetime(2026, 11, 2, 13, 0), None, now) is False
    # 无截止时间 → 不超时
    assert is_breached(None, None, now) is False


def test_remaining_minutes():
    now = dt.datetime(2026, 11, 2, 12, 0)
    assert remaining_minutes(dt.datetime(2026, 11, 2, 12, 30), now) == 30
    assert remaining_minutes(dt.datetime(2026, 11, 2, 11, 30), now) == -30
    assert remaining_minutes(None, now) is None


# ---------- 自定义工作时间表（每租户可配）----------

SATURDAY_SCHEDULE = {
    "work_days": [0, 1, 2, 3, 4, 5],  # 周一到周六
    "work_start_hour": 9,
    "work_end_hour": 18,
}


def test_custom_schedule_includes_saturday():
    """周六上班的团队：周六 09:00-18:00 应算作工作时间。"""
    sat = dt.datetime(2026, 11, 7, 10, 0)  # 周六
    assert working_minutes_between(sat, sat + dt.timedelta(hours=2), SATURDAY_SCHEDULE) == 120
    # 默认排班下周六不算工作时间
    assert working_minutes_between(sat, sat + dt.timedelta(hours=2)) == 0


def test_custom_schedule_excludes_sunday():
    """周日仍然休息。"""
    sun = dt.datetime(2026, 11, 8, 10, 0)
    assert working_minutes_between(sun, sun + dt.timedelta(hours=2), SATURDAY_SCHEDULE) == 0


def test_custom_schedule_add_minutes_lands_on_saturday():
    """周五 17:00 + 120 分钟，在周六排班下应落到周六 10:00。"""
    result = add_working_minutes(dt.datetime(2026, 11, 6, 17, 0), 120, SATURDAY_SCHEDULE)
    assert result == dt.datetime(2026, 11, 7, 10, 0), f"实际 {result}"


def test_default_schedule_skips_saturday():
    """默认排班下同样的输入应落到下周一。"""
    result = add_working_minutes(dt.datetime(2026, 11, 6, 17, 0), 120)
    assert result == dt.datetime(2026, 11, 9, 10, 0), f"实际 {result}"


def test_invalid_schedule_falls_back_to_default():
    """非法配置（下班早于上班）应回落到默认，避免出现负工作时长。"""
    bad = {"work_days": [0, 1, 2, 3, 4], "work_start_hour": 18, "work_end_hour": 9}
    result = add_working_minutes(MON, 60, bad)
    assert result == MON + dt.timedelta(hours=1), f"实际 {result}"


def test_night_shift_schedule():
    """夜班：22:00-06:00。此实现按"单日连续时段"简化处理，
    跨日界的部分按当日时段计算，此处仅验证不抛异常且结果非负。"""
    night = {"work_days": [0, 1, 2, 3, 4], "work_start_hour": 22, "work_end_hour": 23}
    result = working_minutes_between(
        dt.datetime(2026, 11, 2, 22, 30), dt.datetime(2026, 11, 2, 23, 30), night
    )
    assert result >= 0



# ---------- 节假日支持（v1.1.0）----------

def test_holiday_blocks_working_time():
    """国庆假期内不计时：10月2日建单，跨过假期才算工作分钟。"""
    # 2026-10-02 是国庆假期（10/1-10/7）
    result = add_working_minutes(dt.datetime(2026, 10, 2, 10, 0), 60)
    # 假期到 10/7 结束，10/8(周四) 上班 09:00 起算 60 分钟 → 10:00
    assert result == dt.datetime(2026, 10, 8, 10, 0), f"实际 {result}"


def test_extra_workday_counts():
    """调休上班日照常计时：10月10日(周六)因国庆调休上班。"""
    result = add_working_minutes(dt.datetime(2026, 10, 10, 10, 0), 60)
    assert result == dt.datetime(2026, 10, 10, 11, 0), f"实际 {result}"


def test_new_year_holiday():
    """元旦假期（1/1-1/3）不计时，1月4日(周日)调休上班。"""
    # 1月1日建单，60分钟应在 1月4日(周日，调休上班) 10:00 结束
    result = add_working_minutes(dt.datetime(2026, 1, 1, 10, 0), 60)
    assert result == dt.datetime(2026, 1, 4, 10, 0), f"实际 {result}"


def test_spring_festival_holiday():
    """春节假期（2/15-2/23）不计时，2月14日调休上班但已过。"""
    # 2月16日建单（假期中），应推到 2月24日(周二) 上班
    result = add_working_minutes(dt.datetime(2026, 2, 16, 10, 0), 60)
    assert result == dt.datetime(2026, 2, 24, 10, 0), f"实际 {result}"


def test_holiday_weekday_not_counted():
    """落在工作周内的法定假日（如劳动节 5/1 周五）不计入工作分钟。"""
    # 5月1日是法定假日，5月4日是假期内，5月6日(周三)开始上班
    result = add_working_minutes(dt.datetime(2026, 5, 1, 10, 0), 60)
    assert result == dt.datetime(2026, 5, 6, 10, 0), f"实际 {result}"


def test_working_minutes_excludes_holiday():
    """区间跨越假期时，工作分钟不含假期部分。"""
    # 10/1(周四,假期) 09:00 → 10/9(周五) 10:00
    # 工作日只有 10/8(周四) 09:00-18:00 = 540 分钟 + 10/9 09:00-10:00 = 60 → 600
    total = working_minutes_between(
        dt.datetime(2026, 10, 1, 9, 0), dt.datetime(2026, 10, 9, 10, 0)
    )
    assert total == 600, f"实际 {total}"


def test_tenant_custom_holiday():
    """租户可添加自己的休假日（如年会）。"""
    schedule = {"holidays": ["2026-11-05"], "extra_workdays": []}
    # 11月4日(周三) 17:00 + 120 分钟：
    #   当天 17:00-18:00 用掉 60 分钟，剩 60 分钟
    #   11/5 是自定义假期 → 跳过
    #   11/6(周四) 09:00 起算 60 分钟 → 10:00
    result = add_working_minutes(dt.datetime(2026, 11, 4, 17, 0), 120, schedule)
    assert result == dt.datetime(2026, 11, 6, 10, 0), f"实际 {result}"


def test_tenant_extra_workday_overrides_holiday():
    """租户调休上班日优先于法定假日（如春节值班）。"""
    schedule = {"extra_workdays": ["2026-10-02"]}
    result = add_working_minutes(dt.datetime(2026, 10, 2, 10, 0), 60, schedule)
    assert result == dt.datetime(2026, 10, 2, 11, 0), f"实际 {result}"


def test_no_holiday_year_falls_back_to_weekdays():
    """未收录数据的年份按常规工作日表处理，不报错。"""
    # 2027 年数据尚未收录 → 1月1日(周五) 照常上班
    result = add_working_minutes(dt.datetime(2027, 1, 1, 10, 0), 60)
    assert result == dt.datetime(2027, 1, 1, 11, 0), f"实际 {result}"


def test_holiday_data_sanity():
    """内置节假日数据的基本校验。"""
    from app.holidays import known_years, holidays_for_year, extra_workdays_for_year

    assert 2026 in known_years()
    h = holidays_for_year(2026)
    e = extra_workdays_for_year(2026)
    # 国庆 7 天
    assert sum(1 for d in h if d.startswith("2026-10")) == 7
    # 春节 9 天
    assert sum(1 for d in h if d.startswith("2026-02")) == 9
    # 劳动节 5 天
    assert sum(1 for d in h if d.startswith("2026-05")) == 5
    # 调休上班日 6 天
    assert len(e) == 6
    # 两者不应重叠
    assert not (set(h) & set(e))


if __name__ == "__main__":
    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures.append(name)
                print(f"  FAIL  {name}: {e}")
            except Exception as e:  # noqa: BLE001
                failures.append(name)
                print(f"  ERROR {name}: {e}")
    print()
    if failures:
        print(f"❌ {len(failures)} 个用例失败: {', '.join(failures)}")
        sys.exit(1)
    print("✅ 全部通过")

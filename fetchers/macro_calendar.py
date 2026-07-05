"""
宏观经济日历模块。

设计取舍(明确告知用户,避免误以为是实时抓取):
- FOMC 会议日期由美联储官方提前公布,本模块使用 config.py 里手动维护的静态列表,
  需要你每年更新一次(federalreserve.gov/monetarypolicy/fomccalendars.htm)。
- 非农 (NFP) 使用规则近似:每月第一个周五,美国东部时间 8:30 发布。
  这是 BLS 长期以来的固定规律,极少数年份因假期会调整,重大偏差请自行核对
  https://www.bls.gov/schedule/news_release/empsit.htm
- CPI 没有像非农一样的严格规律,只能取 config.CPI_RELEASE_DATES_KNOWN 里
  手动维护的精确值;若当月未维护,则退化为"本月10-15号"的粗略窗口提示。

本模块只计算"距离下一个重大宏观事件还有多少小时",用于:
1. 事件前收窄仓位/降低杠杆的风险提示
2. 事件后的资金费率异动做归因参考
不作为方向性信号。
"""
from __future__ import annotations
from datetime import datetime, timedelta, date
import calendar

from config import FOMC_MEETINGS_2026, FOMC_MEETINGS_2027, CPI_RELEASE_DATES_KNOWN


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _all_fomc_meetings() -> list[tuple[date, date, bool]]:
    out = []
    for start, end, sep in FOMC_MEETINGS_2026 + FOMC_MEETINGS_2027:
        out.append((_parse(start), _parse(end), sep))
    return out


def next_fomc_meeting(today: date | None = None) -> dict | None:
    today = today or date.today()
    for start, end, sep in sorted(_all_fomc_meetings()):
        if end >= today:
            return {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "has_sep_dot_plot": sep,
                "days_until_decision": (end - today).days,
            }
    return None


def next_nfp_date(today: date | None = None) -> date:
    """每月第一个周五。若本月已过,顺延到下月。"""
    today = today or date.today()

    def first_friday(year: int, month: int) -> date:
        cal = calendar.Calendar()
        for day in cal.itermonthdates(year, month):
            if day.month == month and day.weekday() == 4:  # 4 = Friday
                return day
        raise RuntimeError("unreachable")

    candidate = first_friday(today.year, today.month)
    if candidate < today:
        y, m = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
        candidate = first_friday(y, m)
    return candidate


def next_cpi_date(today: date | None = None) -> dict:
    """优先使用手动维护的精确日期,否则给出粗略窗口。"""
    today = today or date.today()
    key = f"{today.year}-{today.month:02d}"
    if key in CPI_RELEASE_DATES_KNOWN:
        exact = _parse(CPI_RELEASE_DATES_KNOWN[key])
        if exact >= today:
            return {"date": exact.isoformat(), "precise": True}
    # 粗略窗口提示(非精确日期,仅供风险提醒)
    window_start = date(today.year, today.month, 10)
    window_end = date(today.year, today.month, 15)
    return {
        "window": f"{window_start.isoformat()} ~ {window_end.isoformat()}",
        "precise": False,
        "note": "CPI精确日期未在config.CPI_RELEASE_DATES_KNOWN中维护,建议核对BLS官网后补充",
    }


def macro_risk_window_hours(today: date | None = None) -> dict:
    """
    综合计算:距离最近的一个宏观风险事件(FOMC决议 或 NFP)还有多少小时。
    用于交易计划里的"事件风险提示"字段。
    """
    today = today or date.today()
    now = datetime.combine(today, datetime.min.time())

    fomc = next_fomc_meeting(today)
    nfp = next_nfp_date(today)

    candidates = []
    if fomc:
        fomc_dt = datetime.combine(_parse(fomc["end"]), datetime.min.time()) + timedelta(hours=14)  # ~14:00 ET附近
        candidates.append(("FOMC利率决议" + ("(含点阵图)" if fomc["has_sep_dot_plot"] else ""), fomc_dt))
    nfp_dt = datetime.combine(nfp, datetime.min.time()) + timedelta(hours=8, minutes=30)
    candidates.append(("非农就业数据(NFP)", nfp_dt))

    candidates.sort(key=lambda x: x[1])
    nearest_name, nearest_dt = candidates[0]
    hours_until = (nearest_dt - now).total_seconds() / 3600.0

    return {
        "nearest_event": nearest_name,
        "event_datetime_utc_approx": nearest_dt.isoformat(),
        "hours_until": round(hours_until, 1),
        "fomc": fomc,
        "next_nfp": nfp.isoformat(),
        "cpi": next_cpi_date(today),
    }

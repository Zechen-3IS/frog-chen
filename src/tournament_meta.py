"""Tournament level + rolling-window expiry helpers for point-breakdown charts."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from points_calculation import (
    ATP_MANDATORY,
    ATP_YEAR_END_FINALS,
    GRAND_SLAMS,
    WTA1000_COMBINED,
    WTA1000_NON_COMBINED,
    WTA_YEAR_END_FINAL,
)

# Common ATP 500 hosts (non-exhaustive; unknown non-1000 → M250)
ATP_500 = {
    "鹿特丹",
    "多哈",
    "迪拜",
    "阿卡普尔科",
    "巴塞罗那",
    "慕尼黑",
    "马德里",  # overridden by 1000 if in mandatory
    "汉堡",
    "伦敦",
    "哈雷",
    "女王",
    "斯图加特",
    "华盛顿",
    "北京",
    "东京",
    "维也纳",
    "巴塞尔",
    "阿斯塔纳",
    "安特卫普",
    "斯德哥尔摩",
    "蒙彼利埃",
    "马赛",
    "达拉斯",
    "洛杉矶",
    "休斯顿",
}

WTA_500 = {
    "多哈",
    "迪拜",
    "柏林",
    "伦敦",
    "东莞",
    "斯特拉斯堡",
    "巴特洪堡",
    "华盛顿",
    "蒙特雷",
    "首尔",
    "东京",
    "宁海",
    "宁波",
    "瓜达拉哈拉",
    "阿布扎比",
    "阿德莱德",
    "布里斯班",
    "霍巴特",
    "林茨",
    "斯图加特",
    "罗马",  # may be 1000
}

LEVEL_ORDER_ATP = ["大满贯", "M1000", "M500", "M250"]
LEVEL_ORDER_WTA = ["大满贯", "W1000", "W500", "W250"]
# City→500 sets below are fallbacks only; prefer calendar ``level``/``type``
# scraped per season (see parser.parse_survivor_level_logo).

SURFACE_ORDER = ["硬地", "红土", "草地"]

# Court surface by city / slam name (unknown → 硬地)
SURFACE_CLAY = {
    "法网",
    "蒙特卡洛",
    "巴塞罗那",
    "慕尼黑",
    "马德里",
    "罗马",
    "日内瓦",
    "里昂",
    "汉堡",
    "巴斯塔德",
    "乌马格",
    "基茨比厄尔",
    "格施塔德",
    "克拉约瓦",
    "布泽尼什",
    "查尔斯顿",
    "斯图加特",  # WTA clay; ATP Stuttgart is grass — rare dual, prefer clay label for WTA-heavy use
    "斯特拉斯堡",
    "拉巴特",
    "波尔图",
    "帕尔马",
}
SURFACE_GRASS = {
    "温网",
    "斯海尔托亨博斯",
    "伦敦",  # Queen's week often labeled 伦敦
    "女王",
    "哈雷",
    "伊斯特本",
    "巴特洪堡",
    "柏林",
    "马洛卡",
    "纽波特",
}


def level_order(tour: str) -> list[str]:
    t = str(tour or "").upper()
    if t in {"WS", "WTA"}:
        return list(LEVEL_ORDER_WTA)
    return list(LEVEL_ORDER_ATP)


def classify_surface(city: str) -> str:
    name = str(city or "").strip()
    if name in SURFACE_GRASS:
        return "草地"
    if name in SURFACE_CLAY:
        return "红土"
    return "硬地"


def classify_level(city: str, tour: str, *, level_hint: str = "") -> str:
    """Map event city/name to chart bucket (4 levels; finals fold into 1000).

    Prefer ``level_hint`` from that year's calendar scrape when present —
    static city sets are only a fallback (tiers change season to season).
    """
    hint = str(level_hint or "").strip()
    if hint:
        return hint
    name = str(city or "").strip()
    t = str(tour or "").upper()
    if name in GRAND_SLAMS:
        return "大满贯"
    if name == "奥运会":
        return "奥运会"
    if t in {"WS", "WTA"}:
        if name in WTA1000_COMBINED or name in WTA1000_NON_COMBINED or name in WTA_YEAR_END_FINAL:
            return "W1000"
        if name in WTA_500:
            return "W500"
        return "W250"
    # ATP / MS
    if name in ATP_MANDATORY or name in ATP_YEAR_END_FINALS:
        return "M1000"
    if name in ATP_500:
        return "M500"
    return "M250"


def estimate_invalid_date(week_start) -> Optional[pd.Timestamp]:
    """
    Approximate points-drop Monday: event week start + 54 weeks
    (~2 weeks event + 52-week window).
    """
    if week_start is None or (isinstance(week_start, float) and pd.isna(week_start)):
        return None
    try:
        ts = pd.Timestamp(week_start)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts + pd.Timedelta(weeks=54)


def format_expires(ts) -> str:
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return ""
    try:
        t = pd.Timestamp(ts)
    except Exception:
        return str(ts)
    if pd.isna(t):
        return ""
    return t.strftime("%Y-%m-%d")


def format_expires_month(ts) -> str:
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return ""
    try:
        t = pd.Timestamp(ts)
    except Exception:
        return ""
    if pd.isna(t):
        return ""
    return t.strftime("%Y.%m")


def round_label(day: Optional[int], max_day: Optional[int] = None) -> str:
    """Human round label from survivor day count."""
    if day is None or (isinstance(day, float) and pd.isna(day)):
        return ""
    try:
        d = int(day)
    except (TypeError, ValueError):
        return ""
    if d <= 0:
        return "未开战"
    if max_day is not None:
        try:
            md = int(max_day)
        except (TypeError, ValueError):
            md = None
        if md and d >= md:
            return "冠军"
        if md and d == md - 1:
            return "决赛"
        if md and d == md - 2:
            return "半决赛"
        if md and d == md - 3:
            return "四分之一决赛"
    return f"第{d}轮"

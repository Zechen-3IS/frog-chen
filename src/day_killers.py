"""本站每日杀手统计（F7）— 按存活天数聚合「球员输球 / 球员退赛」杀手 Top2。"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd

# Deaths that credit a killer player (last pick / settlement killer).
_KILLER_STATUSES = frozenset({"球员输球", "球员退赛"})


def _last_pick(row: pd.Series) -> str:
    players = row.get("players")
    if players is None:
        players = row.get("选人明细")
    if isinstance(players, list):
        for item in reversed(players):
            text = str(item or "").strip()
            if text and text != "轮空":
                return text
    return ""


def daily_killer_stats(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Build a chen-compatible daily killer table.

    Columns: 天数, 杀手球员1, 死亡人数1, 杀手球员2, 死亡人数2

    ``天数`` is 存活天数 + 1 (Day 1 = first pick), matching the ranking panel.
    Includes ``球员退赛`` (e.g. early-ret primary with no backup → 热亚).
    """
    if frame is None or frame.empty:
        return pd.DataFrame()

    status_col = next(
        (c for c in ("当前状态", "fill_status", "状态") if c in frame.columns), None
    )
    day_col = next(
        (c for c in ("存活天数", "select_day", "day") if c in frame.columns), None
    )
    killer_col = next(
        (c for c in ("杀手球员", "killer") if c in frame.columns), None
    )
    if not status_col or not day_col:
        return pd.DataFrame()

    by_day: dict[Any, Counter] = defaultdict(Counter)
    for _, row in frame.iterrows():
        if str(row.get(status_col) or "").strip() not in _KILLER_STATUSES:
            continue
        killer = ""
        if killer_col:
            killer = str(row.get(killer_col) or "").strip()
        if not killer:
            killer = _last_pick(row)
        if not killer:
            continue
        day_raw = row.get(day_col)
        try:
            if pd.isna(day_raw):
                continue
        except (TypeError, ValueError):
            pass
        try:
            day = int(float(day_raw))
        except (TypeError, ValueError):
            continue
        by_day[day].update([killer])

    records = []
    for day in sorted(by_day):
        top = by_day[day].most_common(2)
        # 存活天数 is 0-based (0 = died on first pick); panel Day labels are 1-based.
        record = {
            "天数": day + 1,
            "杀手球员1": "",
            "死亡人数1": "",
            "杀手球员2": "",
            "死亡人数2": "",
        }
        if top:
            record["杀手球员1"], record["死亡人数1"] = top[0]
        if len(top) > 1:
            record["杀手球员2"], record["死亡人数2"] = top[1]
        records.append(record)
    return pd.DataFrame(records)

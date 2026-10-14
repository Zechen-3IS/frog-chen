"""本站每日杀手统计（F7）— 按存活天数聚合「球员输球」杀手 Top2。"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd


def daily_killer_stats(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Build a chen-compatible daily killer table.

    Columns: 天数, 杀手球员1, 死亡人数1, 杀手球员2, 死亡人数2
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
    if not status_col or not day_col or not killer_col:
        return pd.DataFrame()

    by_day: dict[Any, Counter] = defaultdict(Counter)
    for _, row in frame.iterrows():
        if str(row.get(status_col) or "").strip() != "球员输球":
            continue
        killer = str(row.get(killer_col) or "").strip()
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
        # 存活天数在表内为 0-based；展示从 Day 1 起计
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

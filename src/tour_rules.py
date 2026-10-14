"""ATP/WTA keep-best scoring rules (used by player career stats)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

SLAMS = ["澳网", "法网", "温网", "美网"]
WTA_FORCED = [
    "印第安维尔斯",
    "迈阿密",
    "马德里",
    "罗马",
    "蒙特利尔",
    "多伦多",
    "辛辛那提",
    "北京",
]
WTA_UNCOMBINED = ["多哈", "迪拜", "武汉"]
ATP_FORCED = [
    "印第安维尔斯",
    "迈阿密",
    "马德里",
    "罗马",
    "多伦多",
    "蒙特利尔",
    "辛辛那提",
    "上海",
    "巴黎",
]
ATP_UNCOMBINED = ["蒙特卡洛"]
ATP_FINALS = ["都灵"]
WTA_FINALS = ["利雅得"]

YEAR_TAIL = re.compile(r"^(.*)((?:19|20)\d{2})$")


@dataclass
class TourRules:
    tennis_type: str
    slams: list[str] = field(default_factory=lambda: list(SLAMS))
    forced: list[str] = field(default_factory=list)
    uncombined: list[str] = field(default_factory=list)
    finals: list[str] = field(default_factory=list)
    forced_keep: int = 0
    uncombined_keep: int = 0
    other_keep: int = 0

    @classmethod
    def for_tour(cls, tennis_type: str) -> "TourRules":
        key = tennis_type.strip().lower()
        if key == "wta":
            return cls(
                tennis_type="wta",
                forced=list(WTA_FORCED),
                uncombined=list(WTA_UNCOMBINED),
                finals=list(WTA_FINALS),
                forced_keep=6,
                uncombined_keep=1,
                other_keep=7,
            )
        if key == "atp":
            return cls(
                tennis_type="atp",
                forced=list(ATP_FORCED),
                uncombined=list(ATP_UNCOMBINED),
                finals=list(ATP_FINALS),
                forced_keep=5,
                uncombined_keep=0,
                other_keep=9,
            )
        raise ValueError(f"unknown tennis type: {tennis_type}")


def base_event_name(name: str) -> str:
    match = YEAR_TAIL.fullmatch(str(name))
    return match.group(1) if match else str(name)


def _matching_columns(group: list[str], available: list[str]) -> list[str]:
    wanted = set(group)
    return [col for col in available if col in wanted or base_event_name(col) in wanted]


def _event_bucket(name: str, rules: TourRules) -> str:
    base = base_event_name(name)
    if name in rules.slams or base in rules.slams:
        return "slam"
    if name in rules.finals or base in rules.finals:
        return "finals"
    if name in rules.forced or base in rules.forced:
        return "forced"
    if name in rules.uncombined or base in rules.uncombined:
        return "uncombined"
    return "other"


def _select_keep(
    row: pd.Series, rules: TourRules, events: list[str]
) -> tuple[set[str], dict[str, set[str]]]:
    available = [col for col in events if col in row.index]
    empty: dict[str, set[str]] = {
        "slam": set(),
        "finals": set(),
        "forced": set(),
        "uncombined": set(),
        "other": set(),
    }
    if not available:
        return set(), empty
    scores = pd.to_numeric(row[available], errors="coerce").fillna(0)

    slams = set(_matching_columns(rules.slams, available))
    finals = set(_matching_columns(rules.finals, available))
    forced = _matching_columns(rules.forced, available)
    kept_forced: set[str] = set()
    if forced and rules.forced_keep:
        kept_forced = set(scores[forced].astype(int).nlargest(rules.forced_keep).index)

    uncombined = _matching_columns(rules.uncombined, available)
    kept_uncombined: set[str] = set()
    if uncombined and rules.uncombined_keep:
        kept_uncombined = set(
            scores[uncombined].astype(int).nlargest(rules.uncombined_keep).index
        )

    skip = slams | finals | kept_forced | kept_uncombined
    others = [col for col in scores.index if col not in skip]
    kept_others: set[str] = set()
    if others and rules.other_keep:
        kept_others = set(scores[others].astype(int).nlargest(rules.other_keep).index)

    groups = {
        "slam": slams,
        "finals": finals,
        "forced": kept_forced,
        "uncombined": kept_uncombined,
        "other": kept_others,
    }
    keep = slams | finals | kept_forced | kept_uncombined | kept_others
    return keep, groups


def counted_events(
    row: pd.Series,
    rules: TourRules,
    events: list[str],
    this_week: list[str] | None = None,
) -> set[str]:
    live = [name for name in (this_week or []) if name]
    past = [name for name in events if name not in live]
    keep, groups = _select_keep(row, rules, past)
    if not live:
        return keep

    scores = pd.to_numeric(row, errors="coerce").fillna(0)
    for name in live:
        if name not in row.index:
            continue
        score = int(scores.get(name, 0) or 0)
        bucket = _event_bucket(name, rules)
        if bucket in ("slam", "finals"):
            keep.add(name)
            groups[bucket].add(name)
            continue
        if bucket == "uncombined" and not rules.uncombined_keep:
            bucket = "other"
        group = groups[bucket]
        limit = {
            "forced": rules.forced_keep,
            "uncombined": rules.uncombined_keep,
            "other": rules.other_keep,
        }[bucket]
        if not limit:
            continue
        if len(group) < limit:
            keep.add(name)
            group.add(name)
            continue
        lowest = min(group, key=lambda col: (int(scores.get(col, 0) or 0), col))
        if score > int(scores.get(lowest, 0) or 0):
            keep.remove(lowest)
            group.remove(lowest)
            keep.add(name)
            group.add(name)
    return keep


def row_total(
    row: pd.Series,
    rules: TourRules,
    events: list[str],
    this_week: list[str] | None = None,
) -> int:
    keep = counted_events(row, rules, events, this_week)
    if not keep:
        return 0
    return int(pd.to_numeric(row[list(keep)], errors="coerce").fillna(0).sum())

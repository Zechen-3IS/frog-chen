"""Tournament-type CSS class + sort helpers for champion / calendar pages."""
from __future__ import annotations

from typing import Optional

from points_calculation import (
    ATP_YEAR_END_FINALS,
    GRAND_SLAMS,
    WTA_YEAR_END_FINAL,
)
from tournament_meta import classify_level

_TYPE_CSS_CLASS: dict[str, str] = {
    "大满贯": "gs",
    "年终总决赛": "finals",
    "奥运会": "other",
    "ATP1000": "m1000",
    "WTA1000": "w1000",
    "ATP500": "m500",
    "WTA500": "w500",
    "ATP250": "m250",
    "WTA250": "w250",
}

_TYPE_SORT_ORDER: dict[str, int] = {
    "大满贯": 0,
    "年终总决赛": 1,
    "奥运会": 1,
    "ATP1000": 2,
    "WTA1000": 2,
    "ATP500": 3,
    "WTA500": 3,
    "ATP250": 4,
    "WTA250": 4,
}

_LEVEL_TO_CHAMPION_TYPE = {
    "大满贯": "大满贯",
    "M1000": "ATP1000",
    "M500": "ATP500",
    "M250": "ATP250",
    "W1000": "WTA1000",
    "W500": "WTA500",
    "W250": "WTA250",
    "奥运会": "奥运会",
}

_CHAMPION_TYPE_TO_LEVEL = {
    "大满贯": "大满贯",
    "年终总决赛": None,  # tour-dependent; see level_from_champion_type
    "奥运会": "奥运会",
    "ATP1000": "M1000",
    "ATP500": "M500",
    "ATP250": "M250",
    "WTA1000": "W1000",
    "WTA500": "W500",
    "WTA250": "W250",
}

ATP_TYPE_FILTERS = ["大满贯", "年终总决赛", "奥运会", "ATP1000", "ATP500", "ATP250"]
WTA_TYPE_FILTERS = ["大满贯", "年终总决赛", "奥运会", "WTA1000", "WTA500", "WTA250"]


def _type_cls(t: str) -> str:
    return _TYPE_CSS_CLASS.get(str(t).strip(), "other")


def _type_order(t: str) -> int:
    return _TYPE_SORT_ORDER.get(str(t).strip(), 99)


def level_from_champion_type(type_label: str, tour: str = "") -> str:
    """Chart bucket for a stored champion-type label (per-year calendar)."""
    label = str(type_label or "").strip()
    if not label:
        return ""
    if label == "年终总决赛":
        t = str(tour or "").upper()
        return "W1000" if t in {"WS", "WTA"} else "M1000"
    mapped = _CHAMPION_TYPE_TO_LEVEL.get(label)
    if mapped is not None:
        return mapped
    return ""


def champion_type_label(
    city: str, tour: str, *, type_hint: str = "", level_hint: str = ""
) -> str:
    """Same labels as champions.csv ``type`` column (for calendar pills).

    Prefer ``type_hint`` / ``level_hint`` scraped for that season — city→level
    static tables are wrong when a stop changes tier (新加坡 250→500).
    """
    hint = str(type_hint or "").strip()
    if hint:
        return hint
    level_h = str(level_hint or "").strip()
    if level_h and level_h in _LEVEL_TO_CHAMPION_TYPE:
        return _LEVEL_TO_CHAMPION_TYPE[level_h]
    name = str(city or "").strip()
    t = str(tour or "").upper()
    if name == "奥运会":
        return "奥运会"
    if name in GRAND_SLAMS:
        return "大满贯"
    if name in ATP_YEAR_END_FINALS or name in WTA_YEAR_END_FINAL:
        return "年终总决赛"
    level = classify_level(name, t)
    return _LEVEL_TO_CHAMPION_TYPE.get(level, level or "其他")


# Survivor board theoretical max = type label (奥运会 scoring varies → unknown).
_TYPE_MAX_SCORE: dict[str, int] = {
    "大满贯": 2000,
    "年终总决赛": 1500,
    "ATP1000": 1000,
    "WTA1000": 1000,
    "ATP500": 500,
    "WTA500": 500,
    "ATP250": 250,
    "WTA250": 250,
}


def event_theoretical_max(
    city: str,
    tour: str,
    *,
    type_hint: str = "",
    level_hint: str = "",
) -> Optional[int]:
    """Max board score for this event type, or None if unknown."""
    label = champion_type_label(
        city, tour, type_hint=type_hint, level_hint=level_hint
    )
    return _TYPE_MAX_SCORE.get(label)


def type_filters_for_tour(tour: str) -> list[str]:
    t = str(tour or "").upper()
    if t in {"WS", "WTA"}:
        return list(WTA_TYPE_FILTERS)
    return list(ATP_TYPE_FILTERS)


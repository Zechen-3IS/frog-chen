"""
ATP + WTA combined rankings (live / race).

Independent display pages built by outer-merging the two tour tables on
``user_id`` and summing live scores — same idea as chen_web ``build_combined``,
adapted to frog's flat ranking columns.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from live_settlement import _as_key
from logger import get_logger

logger = get_logger(__name__)

DISPLAY_BASE = [
    "排名",
    "用户名",
    "总分",
    "排名变化",
    "WTA总分",
    "ATP总分",
    "WTA状态",
    "ATP状态",
]


def _to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def _pick_col(df: pd.DataFrame, *names: str) -> Optional[str]:
    for name in names:
        if name in df.columns:
            return name
    return None


def _event_label(name: Optional[str], year: Optional[Any], overlap: bool) -> str:
    base = (name or "").strip() or "本站"
    if overlap and year is not None and str(year).strip():
        return f"{base}{year}"
    return base


def _slice_tour(
    frame: pd.DataFrame,
    prefix: str,
    *,
    event_name: Optional[str],
    event_year: Optional[Any],
    removed_name: Optional[str],
    overlap_events: set[str],
    include_replace: bool,
) -> pd.DataFrame:
    uid_col = _pick_col(frame, "user_id", "主键")
    name_col = _pick_col(frame, "用户名", "username")
    score_col = _pick_col(frame, "即时积分", "live_score", "总分")
    base_col = _pick_col(frame, "当前积分", "current_score")
    status_col = _pick_col(frame, "当前状态", "fill_status", "状态")
    week_col = _pick_col(frame, "本站得分", "score")
    removed_col = _pick_col(frame, "扣除积分", "removed_point")

    if uid_col is None or score_col is None:
        raise ValueError(f"{prefix} ranking frame missing user_id / live score columns")

    out = pd.DataFrame(
        {
            "主键": frame[uid_col].map(_as_key),
            "用户名": frame[name_col].fillna("").astype(str) if name_col else "",
            f"{prefix}总分": _to_int(frame[score_col]),
            f"{prefix}上周总分": (
                _to_int(frame[base_col]) if base_col else _to_int(frame[score_col])
            ),
            f"{prefix}状态": (
                frame[status_col].fillna("").astype(str) if status_col else ""
            ),
        }
    )
    out = out[out["主键"].astype(str).str.len() > 0]

    if week_col and event_name:
        label = _event_label(
            event_name, event_year, overlap=(event_name in overlap_events)
        )
        if event_name in overlap_events and not label.startswith(prefix):
            label = f"{prefix}{label}"
        out[label] = _to_int(frame[week_col])

    # 替换列 = 去年同周赛事名（可能与本站不同名，如 武汉←宁波）
    if include_replace and removed_col and removed_name:
        label = (
            f"替换{prefix}{removed_name}"
            if removed_name in overlap_events
            else f"替换{removed_name}"
        )
        out[label] = _to_int(frame[removed_col])

    return out


def _normalize_removed(value: Optional[Any]) -> Optional[str]:
    """Config may store a string or a list of same-week cities; use the first label."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item).strip()
            if text:
                return text
        return None
    text = str(value).strip()
    return text or None


def build_combined(
    atp_frame: pd.DataFrame,
    wta_frame: pd.DataFrame,
    *,
    instant: bool = False,
    atp_event: Optional[str] = None,
    wta_event: Optional[str] = None,
    atp_year: Optional[Any] = None,
    wta_year: Optional[Any] = None,
    atp_removed: Optional[Any] = None,
    wta_removed: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Outer-merge ATP / WTA ranking tables into a combined board.

    Parameters
    ----------
    atp_frame, wta_frame
        Frog ranking tables (Chinese column names after ``COL_ZH_DICT`` rename),
        still containing ``user_id``.
    instant
        When True, include 扣除积分 as 「替换{去年同周}」 columns.
    atp_event / wta_event
        Current event city names used to label 本站得分 columns.
    atp_removed / wta_removed
        Last year's corresponding-week event name(s) for 替换 columns.
    """
    if atp_frame is None or atp_frame.empty:
        raise ValueError("atp_frame is required")
    if wta_frame is None or wta_frame.empty:
        raise ValueError("wta_frame is required")

    atp_removed_name = _normalize_removed(atp_removed)
    wta_removed_name = _normalize_removed(wta_removed)

    overlap: set[str] = set()
    if atp_event and wta_event and atp_event.strip() == wta_event.strip():
        overlap.add(atp_event.strip())
    if atp_removed_name and wta_removed_name and atp_removed_name == wta_removed_name:
        overlap.add(atp_removed_name)

    atp_part = _slice_tour(
        atp_frame,
        "ATP",
        event_name=atp_event,
        event_year=atp_year,
        removed_name=atp_removed_name,
        overlap_events=overlap,
        include_replace=instant,
    )
    wta_part = _slice_tour(
        wta_frame,
        "WTA",
        event_name=wta_event,
        event_year=wta_year,
        removed_name=wta_removed_name,
        overlap_events=overlap,
        include_replace=instant,
    )

    combined = pd.merge(wta_part, atp_part, on="主键", how="outer", suffixes=("_wta", "_atp"))
    if "用户名_wta" in combined.columns or "用户名_atp" in combined.columns:
        combined["用户名"] = combined.get("用户名_wta", pd.Series(dtype=str)).fillna(
            combined.get("用户名_atp", pd.Series(dtype=str))
        )
        combined = combined.drop(
            columns=[c for c in ("用户名_wta", "用户名_atp") if c in combined.columns]
        )
    elif "用户名" not in combined.columns:
        combined["用户名"] = ""

    for col in ("ATP总分", "WTA总分", "ATP上周总分", "WTA上周总分"):
        if col not in combined.columns:
            combined[col] = 0
        combined[col] = _to_int(combined[col])
    for col in ("ATP状态", "WTA状态"):
        if col not in combined.columns:
            combined[col] = ""
        combined[col] = combined[col].fillna("")

    combined["总分"] = combined["ATP总分"] + combined["WTA总分"]
    combined["上周总分"] = combined["ATP上周总分"] + combined["WTA上周总分"]
    combined["上周排名"] = combined["上周总分"].rank(ascending=False, method="min").astype(int)
    combined["排名"] = combined["总分"].rank(ascending=False, method="min").astype(int)
    # Positive = rose (aligned with frog 排名变化 / chen 升降)
    combined["排名变化"] = combined["上周排名"] - combined["排名"]
    combined["用户名"] = combined["用户名"].fillna("")
    combined = combined.sort_values(["排名", "用户名"]).reset_index(drop=True)

    # Preserve week / replace columns in WTA-then-ATP order
    extra_cols = [
        c
        for c in list(wta_part.columns) + list(atp_part.columns)
        if c not in {"主键", "用户名", "ATP总分", "WTA总分", "ATP上周总分", "WTA上周总分", "ATP状态", "WTA状态"}
        and c in combined.columns
    ]
    # Dedupe preserving order
    seen: set[str] = set()
    ordered_extra: list[str] = []
    for col in extra_cols:
        if col not in seen:
            seen.add(col)
            ordered_extra.append(col)
            combined[col] = _to_int(combined[col])

    # Keep 主键 for row click → breakdown charts (hidden in HTML render)
    html_columns = ["主键"] + DISPLAY_BASE + ordered_extra
    out = combined[html_columns].copy()
    out.attrs["instant"] = instant
    out.attrs["event_columns"] = ordered_extra
    return out


def update_combined_pages(
    atp_live: pd.DataFrame,
    wta_live: pd.DataFrame,
    atp_race: pd.DataFrame,
    wta_race: pd.DataFrame,
    *,
    atp_event: Optional[str] = None,
    wta_event: Optional[str] = None,
    atp_removed: Optional[Any] = None,
    wta_removed: Optional[Any] = None,
    year: Optional[Any] = None,
    updated: Optional[str] = None,
    output_dir: str | Path = "..",
    atp_rank_raw: Optional[pd.DataFrame] = None,
    wta_rank_raw: Optional[pd.DataFrame] = None,
    atp_race_raw: Optional[pd.DataFrame] = None,
    wta_race_raw: Optional[pd.DataFrame] = None,
) -> list[Path]:
    """Write ``combined_instant_ranking.html`` and ``combined_ranking.html``."""
    from survivor_html import render_ranking_page
    from user_breakdown import write_breakdown_bundle

    output_dir = Path(output_dir)
    data_dir = output_dir / "data"
    updated = updated or datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    written: list[Path] = []

    # Per-user event composition JSON (clicked from combined tables).
    # Raw frames supply details_text; live/race tables supply 本站得分 so
    # calculate_points matches 即时积分 on the board.
    try:
        write_breakdown_bundle(
            atp_live=atp_rank_raw if atp_rank_raw is not None else atp_live,
            wta_live=wta_rank_raw if wta_rank_raw is not None else wta_live,
            atp_race=atp_race_raw if atp_race_raw is not None else atp_race,
            wta_race=wta_race_raw if wta_race_raw is not None else wta_race,
            atp_live_table=atp_live,
            wta_live_table=wta_live,
            atp_race_table=atp_race,
            wta_race_table=wta_race,
            atp_event=atp_event,
            wta_event=wta_event,
            atp_removed=atp_removed,
            wta_removed=wta_removed,
            output_dir=data_dir,
            calendar_dir=data_dir,
            score_dir=data_dir / "event_scores",
            round_cache_dir=data_dir / "event_day_rounds",
            fetch_day_rounds=True,
        )
    except Exception:
        logger.exception("Failed to write user breakdown JSON")

    instant = build_combined(
        atp_live,
        wta_live,
        instant=True,
        atp_event=atp_event,
        wta_event=wta_event,
        atp_removed=atp_removed,
        wta_removed=wta_removed,
        atp_year=year,
        wta_year=year,
    )
    race = build_combined(
        atp_race,
        wta_race,
        instant=False,
        atp_event=atp_event,
        wta_event=wta_event,
        atp_year=year,
        wta_year=year,
    )

    specs = [
        (
            instant,
            "联合即时排名",
            "ALL · Combined Live Ranking",
            ["即时"],
            "combined_instant_ranking.html",
            "data/breakdown_live_atp.json",
            "data/breakdown_live_wta.json",
        ),
        (
            race,
            "联合冠军排名",
            "ALL · Combined Race Ranking",
            ["冠军积分"],
            "combined_ranking.html",
            "data/breakdown_race_atp.json",
            "data/breakdown_race_wta.json",
        ),
    ]
    for df, title, eyebrow, tags, filename, atp_url, wta_url in specs:
        out = output_dir / filename
        render_ranking_page(
            df=df,
            title=title,
            tour="ALL",
            eyebrow=eyebrow,
            updated=updated,
            summary_df=None,
            rank_change_col="排名变化",
            extra_tags=tags,
            available_players=None,
            enable_detail=False,
            enable_breakdown=True,
            breakdown_atp_url=atp_url,
            breakdown_wta_url=wta_url,
            output_path=str(out),
        )
        written.append(out)
        logger.info(f"wrote {out} ({len(df)} rows)")
    return written

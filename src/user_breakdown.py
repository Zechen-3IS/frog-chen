"""
Per-user race/live points composition for combined-ranking charts.

Reads official rank/race ``details_text``, applies the same live adjust +
``calculate_points`` rules as the ranking tables (18-event window, mandatory
slams / 1000s, year-end bonus), then enriches counted events with level,
expiry, and round from the calendar / event_scores cache.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from live_ranking import add_new_tournament, remove_current_tournament
from live_settlement import _as_key
from logger import get_logger
from points_calculation import calculate_points, parse_events
from site_html.types_meta import level_from_champion_type
from tournament_meta import (
    SURFACE_ORDER,
    classify_level,
    classify_surface,
    estimate_invalid_date,
    format_expires,
    format_expires_month,
    level_order,
)

logger = get_logger(__name__)

CALENDAR_DIR = Path("../data")
SCORE_CACHE_DIR = Path("../data/event_scores")
ROUND_CACHE_DIR = Path("../data/event_day_rounds")
OUT_DIR = Path("../data")


def _load_calendars(
    years: list[int], calendar_dir: Path = CALENDAR_DIR
) -> pd.DataFrame:
    frames = []
    for y in years:
        path = Path(calendar_dir) / f"calendar_{int(y)}.json"
        if not path.exists():
            continue
        try:
            frame = pd.read_json(path, orient="table")
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["city"] = out["city"].astype(str).str.strip()
    out["tour"] = out.get("event_tour", out.get("tour")).astype(str).str.upper()
    out["week_start_date"] = pd.to_datetime(out["week_start_date"], errors="coerce")
    if "invalid_date" in out.columns:
        out["invalid_date"] = pd.to_datetime(out["invalid_date"], errors="coerce")
    else:
        out["invalid_date"] = out["week_start_date"].map(estimate_invalid_date)
    if "level" not in out.columns:
        out["level"] = ""
    out["level"] = out["level"].astype(str).fillna("").str.strip()
    out["level"] = out["level"].replace({"nan": ""})
    # Prefer scraped level; else derive from scraped type; else static city map.
    missing = out["level"].eq("")
    if missing.any() and "type" in out.columns:
        derived = [
            level_from_champion_type(tp, tr)
            for tp, tr in zip(out.loc[missing, "type"], out.loc[missing, "tour"])
        ]
        out.loc[missing, "level"] = derived
        missing = out["level"].eq("")
    if missing.any():
        out.loc[missing, "level"] = [
            classify_level(c, t)
            for c, t in zip(out.loc[missing, "city"], out.loc[missing, "tour"])
        ]
    return out


def _calendar_lookup(calendar: pd.DataFrame, tour: str) -> dict[str, dict]:
    """city -> best (latest week) meta row for this tour."""
    if calendar is None or calendar.empty:
        return {}
    tour_u = "MS" if str(tour).upper() in {"MS", "ATP"} else "WS"
    sub = calendar.loc[calendar["tour"] == tour_u].copy()
    if sub.empty:
        return {}
    sub = sub.sort_values("week_start_date")
    out: dict[str, dict] = {}
    for _, row in sub.iterrows():
        city = str(row.get("city") or "").strip()
        if not city:
            continue
        out[city] = {
            "event_id": str(row.get("event_id") or ""),
            "year": int(row["event_year"])
            if pd.notna(row.get("event_year"))
            else int(row.get("year") or 0),
            "level": str(row.get("level") or classify_level(city, tour_u)),
            "surface": classify_surface(city),
            "expires": format_expires(row.get("invalid_date")),
            "expires_month": format_expires_month(row.get("invalid_date")),
            "monday": (
                row["week_start_date"].strftime("%Y-%m-%d")
                if pd.notna(row.get("week_start_date"))
                else ""
            ),
        }
    return out


def _build_day_index(
    score_dir: Path, calendar: pd.DataFrame, tour: str
) -> dict[tuple[str, str], dict[str, int]]:
    """
    (city, year_str) -> {user_id: day}
    """
    if calendar is None or calendar.empty:
        return {}
    tour_u = "MS" if str(tour).upper() in {"MS", "ATP"} else "WS"
    index: dict[tuple[str, str], dict[str, int]] = {}
    sub = calendar.loc[calendar["tour"] == tour_u]
    for _, row in sub.iterrows():
        event_id = str(row.get("event_id") or "")
        year = row.get("event_year") if pd.notna(row.get("event_year")) else row.get("year")
        city = str(row.get("city") or "").strip()
        if not event_id or year is None or not city:
            continue
        from event_calendar import score_cache_path

        path = score_cache_path(tour_u, event_id, int(year), Path(score_dir))
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        days: dict[str, int] = {}
        for rec in payload.get("rows") or []:
            uid = _as_key(rec.get("user_id"))
            if not uid:
                continue
            try:
                days[uid] = int(rec.get("day") or 0)
            except (TypeError, ValueError):
                continue
        if days:
            index[(city, str(int(year)))] = days
            # also bare city → latest overwrites (calendar sorted earlier)
            index[(city, "")] = days
    return index


def _details_col(frame: pd.DataFrame) -> Optional[str]:
    for c in ("details_text", "details", "明细"):
        if c in frame.columns:
            return c
    return None


def _normalize_removed(
    removed_tournament_name: Optional[Union[str, list]],
) -> list[str]:
    if removed_tournament_name is None:
        return []
    if isinstance(removed_tournament_name, str):
        return [removed_tournament_name] if removed_tournament_name else []
    return [str(x) for x in removed_tournament_name if x]


def _event_score_map(live_frame: Optional[pd.DataFrame]) -> dict[str, int]:
    """uid -> 本站得分 from a rendered live/race table.

    Skips 未参赛 / missing scores so we never inject a mandatory 0 for
    ranked users who did not enter the current event.
    """
    if live_frame is None or live_frame.empty:
        return {}
    uid_col = "user_id" if "user_id" in live_frame.columns else (
        "主键" if "主键" in live_frame.columns else None
    )
    score_col = next(
        (
            c
            for c in ("本站得分", "score", "event_score", "当前得分")
            if c in live_frame.columns
        ),
        None,
    )
    status_col = next(
        (
            c
            for c in ("当前状态", "fill_status", "status")
            if c in live_frame.columns
        ),
        None,
    )
    if uid_col is None or score_col is None:
        return {}
    out: dict[str, int] = {}
    for _, row in live_frame.iterrows():
        uid = _as_key(row.get(uid_col))
        if not uid:
            continue
        if status_col is not None:
            st = str(row.get(status_col) or "").strip()
            if st == "未参赛":
                continue
        val = pd.to_numeric(row.get(score_col), errors="coerce")
        if pd.isna(val):
            continue
        out[uid] = int(val)
    return out


def _compose_scores(
    details_text: Any,
    *,
    uid: str,
    new_tournament_name: Optional[str],
    removed_tournament_name: Optional[Union[str, list]],
    event_score_by_uid: Optional[dict[str, int]],
) -> dict[str, int]:
    """Mirror live_ranking / build_table before calculate_points."""
    scores = parse_events(details_text)
    for tn in _normalize_removed(removed_tournament_name):
        scores, _ = remove_current_tournament(scores, tn)
    if new_tournament_name and event_score_by_uid is not None and uid in event_score_by_uid:
        scores = add_new_tournament(
            scores, event_score_by_uid[uid], new_tournament_name
        )
    return scores


def _round_cache_path(
    tour: str, event_id: str, year: int, cache_dir: Path
) -> Path:
    return Path(cache_dir) / f"{tour}_{event_id}_{int(year)}.json"


def _load_event_day_rounds(
    tour: str,
    event_id: str,
    year: int,
    cache_dir: Path,
    *,
    fetch: bool = False,
) -> dict[int, str]:
    """Day number → *result* round label (``W``, ``F``, ``QF/2``, …)."""
    from parser import pick_rounds_to_result_rounds

    path = _round_cache_path(tour, event_id, year, cache_dir)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            cached = {
                int(k): str(v) for k, v in (raw or {}).items() if str(v).strip()
            }
            # Old caches stored pick-page rounds (title day = F); normalize once.
            if cached and cached.get(max(cached)) != "W":
                cached = pick_rounds_to_result_rounds(cached)
            return cached
        except Exception:
            pass
    if not fetch:
        return {}
    try:
        from parser import day_round_labels, fetch_event_detail

        detail = fetch_event_detail(event_id, year, tour)
        labels = day_round_labels(detail.get("days") or {})
        mapping = {
            i + 1: labels[i]
            for i in range(len(labels))
            if str(labels[i] or "").strip()
        }
        if mapping:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {str(k): v for k, v in mapping.items()},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
        return mapping
    except Exception:
        logger.exception(
            f"day-round fetch failed {tour} {event_id} {year}"
        )
        return {}


def _build_round_index(
    calendar: pd.DataFrame,
    tour: str,
    cache_dir: Path,
    *,
    fetch: bool = False,
) -> dict[tuple[str, str], dict[int, str]]:
    """(city, year_str) → {pick_day: round label}."""
    if calendar is None or calendar.empty:
        return {}
    tour_u = "MS" if str(tour).upper() in {"MS", "ATP"} else "WS"
    index: dict[tuple[str, str], dict[int, str]] = {}
    sub = calendar.loc[calendar["tour"] == tour_u]
    for _, row in sub.iterrows():
        event_id = str(row.get("event_id") or "")
        year = row.get("event_year") if pd.notna(row.get("event_year")) else row.get("year")
        city = str(row.get("city") or "").strip()
        if not event_id or year is None or not city:
            continue
        mapping = _load_event_day_rounds(
            tour_u, event_id, int(year), Path(cache_dir), fetch=fetch
        )
        if not mapping:
            continue
        index[(city, str(int(year)))] = mapping
        index[(city, "")] = mapping
    return index


def _round_for_event(
    day: Optional[int],
    points: int,
    day_rounds: Optional[dict[int, str]] = None,
) -> str:
    """Map survivor day to pick-page round (R2/1, QF/2…); never 第N轮."""
    if day is None:
        return ""
    try:
        d = int(day)
    except (TypeError, ValueError):
        return ""
    # day=0 with points ≈ exited on pick Day 1
    pick_day = 1 if d <= 0 else d
    if points <= 0 and d <= 0:
        return ""
    rounds = day_rounds or {}
    label = rounds.get(pick_day) or rounds.get(int(pick_day))
    if label:
        return str(label)
    return ""


def build_tour_breakdown(
    frame: pd.DataFrame,
    tour: str,
    *,
    calendar: Optional[pd.DataFrame] = None,
    score_dir: Path = SCORE_CACHE_DIR,
    round_cache_dir: Path = ROUND_CACHE_DIR,
    fetch_day_rounds: bool = False,
    new_tournament_name: Optional[str] = None,
    removed_tournament_name: Optional[Union[str, list]] = None,
    event_score_by_uid: Optional[dict[str, int]] = None,
) -> dict[str, dict[str, Any]]:
    """
    Return ``{uid: {username, total, events: [...]}}``.

    ``events`` are only the tournaments selected by ``calculate_points``
    (same total as the ranking table). Zero-point mandatory slots are omitted
    from the list because they do not contribute to the numeric total.
    """
    if frame is None or frame.empty:
        return {}
    uid_col = "user_id" if "user_id" in frame.columns else (
        "主键" if "主键" in frame.columns else None
    )
    name_col = "username" if "username" in frame.columns else (
        "用户名" if "用户名" in frame.columns else None
    )
    det_col = _details_col(frame)
    if uid_col is None or det_col is None:
        logger.warning(f"breakdown skip {tour}: missing user_id/details")
        return {}

    cal = calendar if calendar is not None else _load_calendars(
        list(range(2024, 2028))
    )
    meta = _calendar_lookup(cal, tour)
    day_index = _build_day_index(Path(score_dir), cal, tour)
    round_index = _build_round_index(
        cal, tour, Path(round_cache_dir), fetch=fetch_day_rounds
    )
    order = level_order(tour)
    tour_u = "MS" if str(tour).upper() in {"MS", "ATP"} else "WS"
    points_tour = "ATP" if tour_u == "MS" else "WTA"

    users: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        uid = _as_key(row.get(uid_col))
        if not uid:
            continue
        composed = _compose_scores(
            row.get(det_col),
            uid=uid,
            new_tournament_name=new_tournament_name,
            removed_tournament_name=removed_tournament_name,
            event_score_by_uid=event_score_by_uid,
        )
        if not composed:
            continue
        result = calculate_points(composed, tour=points_tour)
        counted = result.get("counted_tournaments") or {}
        total = int(result.get("total_points") or 0)
        # Stable: high points first (matches calculate_points sort).
        events = []
        for name, pts in counted.items():
            points = int(pts or 0)
            if points <= 0:
                continue
            info = meta.get(name) or {}
            level = info.get("level") or classify_level(name, tour_u)
            surface = info.get("surface") or classify_surface(name)
            year_s = str(info.get("year") or "")
            day_map = day_index.get((name, year_s)) or day_index.get((name, "")) or {}
            day = day_map.get(uid)
            day_rounds = (
                round_index.get((name, year_s))
                or round_index.get((name, ""))
                or {}
            )
            events.append(
                {
                    "name": name,
                    "points": points,
                    "level": level,
                    "surface": surface,
                    "round": _round_for_event(day, points, day_rounds),
                    "day": day if day is not None else None,
                    "expires": info.get("expires") or "",
                    "expires_month": info.get("expires_month") or "",
                    "event_id": info.get("event_id") or "",
                    "year": info.get("year") or None,
                }
            )
        users[uid] = {
            "uid": uid,
            "username": str(row.get(name_col) or "") if name_col else "",
            "total": total,
            "levels": order,
            "surfaces": list(SURFACE_ORDER),
            "events": events,
        }
    return users


def write_breakdown_bundle(
    *,
    atp_live: Optional[pd.DataFrame] = None,
    wta_live: Optional[pd.DataFrame] = None,
    atp_race: Optional[pd.DataFrame] = None,
    wta_race: Optional[pd.DataFrame] = None,
    atp_live_table: Optional[pd.DataFrame] = None,
    wta_live_table: Optional[pd.DataFrame] = None,
    atp_race_table: Optional[pd.DataFrame] = None,
    wta_race_table: Optional[pd.DataFrame] = None,
    atp_event: Optional[str] = None,
    wta_event: Optional[str] = None,
    atp_removed: Optional[Union[str, list]] = None,
    wta_removed: Optional[Union[str, list]] = None,
    output_dir: Union[str, Path] = OUT_DIR,
    calendar_dir: Union[str, Path] = CALENDAR_DIR,
    score_dir: Union[str, Path] = SCORE_CACHE_DIR,
    round_cache_dir: Optional[Union[str, Path]] = None,
    fetch_day_rounds: bool = False,
    years: Optional[list[int]] = None,
) -> dict[str, Path]:
    """Write live + race breakdown JSON files for ATP/WTA."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    years = years or list(range(2024, 2028))
    calendar = _load_calendars(years, Path(calendar_dir))
    rounds_dir = Path(round_cache_dir) if round_cache_dir else (
        output_dir / "event_day_rounds"
    )

    written: dict[str, Path] = {}
    specs = [
        (
            "breakdown_live_atp.json",
            atp_live,
            "MS",
            atp_event,
            atp_removed,
            _event_score_map(atp_live_table),
        ),
        (
            "breakdown_live_wta.json",
            wta_live,
            "WS",
            wta_event,
            wta_removed,
            _event_score_map(wta_live_table),
        ),
        (
            "breakdown_race_atp.json",
            atp_race,
            "MS",
            atp_event,
            None,  # race does not drop the rolling-window event
            _event_score_map(atp_race_table),
        ),
        (
            "breakdown_race_wta.json",
            wta_race,
            "WS",
            wta_event,
            None,
            _event_score_map(wta_race_table),
        ),
    ]
    for filename, frame, tour, event_name, removed, score_map in specs:
        if frame is None:
            continue
        data = build_tour_breakdown(
            frame,
            tour,
            calendar=calendar,
            score_dir=Path(score_dir),
            round_cache_dir=rounds_dir,
            fetch_day_rounds=fetch_day_rounds,
            new_tournament_name=event_name,
            removed_tournament_name=removed,
            event_score_by_uid=score_map or None,
        )
        path = output_dir / filename
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        path.write_text(payload, encoding="utf-8")
        # Companion .js works with file:// (script src), unlike fetch+JSON
        js_name = filename.replace(".json", ".js")
        var_name = {
            "breakdown_live_atp.json": "__BD_LIVE_ATP",
            "breakdown_live_wta.json": "__BD_LIVE_WTA",
            "breakdown_race_atp.json": "__BD_RACE_ATP",
            "breakdown_race_wta.json": "__BD_RACE_WTA",
        }.get(filename, "__BD_DATA")
        js_path = output_dir / js_name
        js_path.write_text(
            f"window.{var_name}={payload};\n", encoding="utf-8"
        )
        written[filename] = path
        written[js_name] = js_path
        logger.info(f"wrote {path} + {js_name} ({len(data)} users)")
    return written

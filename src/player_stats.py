"""
Player career / cycle stats for 签表幸存者.

Independent of the live ranking pipeline. Uses incremental cache
``data/player_events.json`` (seeded from chen_web) and frog's calendar /
score fetchers for weekly updates.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from draw_status import DAY_SCORE_RE, USER_AGENT, beijing_now
from live_settlement import _as_key
from logger import get_logger
from parser import _strip_html, fetch_survivor_calendar_event_df, fetch_table
from points_calculation import (
    ATP_MANDATORY,
    ATP_YEAR_END_FINALS,
    GRAND_SLAMS,
    WTA1000_COMBINED,
    WTA1000_NON_COMBINED,
    WTA_YEAR_END_FINAL,
    _calculate_points_atp,
    _calculate_points_wta,
    parse_events,
)
from tour_rules import TourRules, row_total

logger = get_logger(__name__)

# Montreal and Toronto alternate as the single Canadian 1000.
CANADA_EVENTS = {"蒙特利尔", "多伦多"}

STATS_CACHE = Path(__file__).resolve().parent.parent / "data" / "player_events.json"
ROLLING_SCORE_CACHE = Path(__file__).resolve().parent.parent / "data" / "rolling_scores.json"
# Forced zeros start with 2026 Indian Wells. Rankings update every Monday
# except the Monday inside a two-week event.
FORCED_ZERO_START = datetime(2026, 3, 2)
TWO_WEEK_EVENTS = set(GRAND_SLAMS) | {
    "印第安维尔斯",
    "迈阿密",
    "马德里",
    "罗马",
    "辛辛那提",
    "上海",
}
PLAYED_STATUS = {"存活", "球员输球", "自杀(退赛)", "自杀(重复)", "自杀(主备冲突)"}
# Long free-text details live in the row-click modal (not table columns).
DISPLAY_COLS = [
    "排名",
    "用户名",
    "周期参赛数",
    "周期冠军数",
    "历史冠军数",
    "历史亚军数",
    "历史最佳排名",
    "历史最长连胜天数",
    "历史最长连败天数",
    "世界第一周数",
    "历史最高得分",
    "赛季存活率",
    "历史存活率",
]
CAREER_DETAIL_COL = "_生涯明细"

TOUR_CODE = {"atp": "MS", "wta": "WS"}


def strip_username(raw: str | None) -> str:
    if not raw:
        return ""
    text = BeautifulSoup(str(raw), "html.parser").get_text()
    pos = text.rfind(">")
    return (text[pos + 1 :] if pos != -1 else text).strip()


def _day(row: dict[str, Any]) -> int:
    try:
        return int(row.get("day") or 0)
    except (TypeError, ValueError):
        return 0


def _score(row: dict[str, Any]) -> int:
    try:
        return int(row.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def _played(row: dict[str, Any]) -> bool:
    status = str(row.get("fill_status") or "")
    return status in PLAYED_STATUS and (_day(row) > 0 or status == "存活")


def _win_streak(person: pd.DataFrame) -> tuple[int, str]:
    rows = list(person.sort_values(["monday", "name"]).itertuples())
    best_days = -1
    best: list[tuple[str, int]] = []

    def consider(chain: list[tuple[str, int]]) -> None:
        nonlocal best_days, best
        total = sum(item[1] for item in chain)
        if chain and total > best_days:
            best_days = total
            best = chain

    index = 0
    while index < len(rows):
        row = rows[index]
        if row.champion:
            chain = [(row.label, int(row.day))]
            cursor = index + 1
            while cursor < len(rows):
                nxt = rows[cursor]
                chain.append((nxt.label, int(nxt.day)))
                if int(nxt.day) <= 0 or not nxt.champion:
                    break
                cursor += 1
            consider(chain)
        elif int(row.day) > 0:
            consider([(row.label, int(row.day))])
        index += 1
    if best_days < 0:
        return 0, ""
    return best_days, ", ".join(f"{name}({days})" for name, days in best)


def _longest_streak(
    flags: list[tuple[bool, str, int]], with_days: bool
) -> tuple[int, str]:
    best: list[tuple[str, int]] = []
    current: list[tuple[str, int]] = []
    best_days = -1
    for matched, label, days in flags:
        if matched:
            current.append((label, days))
            continue
        total = sum(item[1] for item in current)
        if current and total > best_days:
            best = current
            best_days = total
        current = []
    total = sum(item[1] for item in current)
    if current and total > best_days:
        best = current
        best_days = total
    if not best:
        return 0, ""
    if with_days:
        text = ", ".join(f"{name}({days})" for name, days in best)
    else:
        text = ", ".join(name for name, _ in best)
    return max(best_days, 0), text


def _unique_event_name(name: str, year: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    labeled = f"{name}{year}"
    used.add(labeled)
    return labeled


def _event_cache_key(info: dict[str, Any]) -> str:
    return f"{info.get('year')}:{info.get('id')}"


def _load_cache(path: Path = STATS_CACHE) -> dict[str, Any]:
    if not path.exists():
        return {"atp": {}, "wta": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"atp": {}, "wta": {}}
    if not isinstance(payload, dict):
        return {"atp": {}, "wta": {}}
    payload.setdefault("atp", {})
    payload.setdefault("wta", {})
    return payload


def _save_cache(cache: dict[str, Any], path: Path = STATS_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _hydrate_records(
    rows: list[dict[str, Any]], day_points: list[int] | None = None
) -> list[dict[str, Any]]:
    hydrated = []
    for row in rows:
        item = dict(row)
        monday = item.get("monday")
        if isinstance(monday, str):
            item["monday"] = datetime.strptime(monday[:10], "%Y-%m-%d")
        hydrated.append(item)
    _apply_outcome_flags(hydrated, day_points)
    return hydrated


def _serialize_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized = []
    for row in rows:
        item = dict(row)
        monday = item.get("monday")
        if isinstance(monday, datetime):
            item["monday"] = monday.strftime("%Y-%m-%d")
        serialized.append(item)
    return serialized


def _apply_outcome_flags(
    records: list[dict[str, Any]], day_points: list[int] | None = None
) -> None:
    if not records:
        return
    runner_score = int(day_points[-2]) if day_points and len(day_points) >= 2 else None
    champions = {row.get("主键") for row in records if row.get("champion")}
    for row in records:
        uid = row.get("主键")
        row["runner"] = (
            uid not in champions
            and runner_score is not None
            and int(row.get("score") or 0) == runner_score
        )


def _records_from_event(
    info: dict[str, Any],
    rows: list[dict[str, Any]],
    in_progress: bool,
    day_points: list[int] | None = None,
) -> list[dict[str, Any]]:
    played_rows = [row for row in rows if _played(row)]
    if not played_rows:
        return []
    max_day = max(_day(row) for row in played_rows)
    champions = {
        _as_key(row.get("user_id"))
        for row in played_rows
        if row.get("fill_status") == "存活" and not in_progress
    }
    label = f"{info.get('year')}-{info.get('name')}"
    records = []
    for row in played_rows:
        uid = _as_key(row.get("user_id"))
        if not uid:
            continue
        records.append(
            {
                "主键": uid,
                "用户名": strip_username(row.get("username")),
                "name": info.get("name") or "",
                "year": str(info.get("year") or ""),
                "monday": info["monday"],
                "season_year": int(info.get("season_year") or info["monday"].year),
                "label": label,
                "day": _day(row),
                "score": _score(row),
                "max_day": max_day,
                "champion": uid in champions,
                "runner": False,
                "completed": not in_progress,
            }
        )
    _apply_outcome_flags(records, day_points)
    return records


def _list_tour_events(tennis_type: str, years: list[int] | None = None) -> list[dict[str, Any]]:
    """Build event catalog from frog calendar pages (primary event per week)."""
    tour = TOUR_CODE[tennis_type]
    current_year = beijing_now().year
    years = years or list(range(current_year - 2, current_year + 1))
    events: list[dict[str, Any]] = []
    for year in years:
        df, _ = fetch_survivor_calendar_event_df(year)
        if df is None or df.empty:
            continue
        # Prefer score/detail/my pages; keep one row per event_id
        sub = df[df["tour"].str.upper() == tour].copy()
        if sub.empty:
            continue
        sub = sub.dropna(subset=["event_id"])
        sub = sub.sort_values(["week_start_date", "page_type"]).drop_duplicates(
            subset=["event_id", "event_year"], keep="first"
        )
        for _, row in sub.iterrows():
            monday = row.get("week_start_date")
            if pd.isna(monday):
                continue
            if not isinstance(monday, datetime):
                monday = pd.Timestamp(monday).to_pydatetime()
            events.append(
                {
                    "id": str(row["event_id"]),
                    "name": str(row.get("city") or ""),
                    "year": str(int(row["event_year"]) if pd.notna(row.get("event_year")) else year),
                    "gender": tour,
                    "monday": monday.replace(tzinfo=None)
                    if getattr(monday, "tzinfo", None)
                    else monday,
                    "season_year": year,
                }
            )
    events.sort(key=lambda item: (item["monday"], item.get("name") or ""))
    return events


def _fetch_event_score_rows(info: dict[str, Any]) -> list[dict[str, Any]]:
    tour = str(info.get("gender") or TOUR_CODE.get("atp")).upper()
    event_id = info.get("id")
    year = info.get("year")
    if not event_id or not year:
        return []
    try:
        df, _ = fetch_table(
            option="score", tour=tour, event_id=event_id, year=int(year)
        )
    except Exception as err:
        logger.warning(f"score fetch failed {event_id}/{year}: {err}")
        return []
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def _fetch_event_day_points(info: dict[str, Any]) -> list[int]:
    tour = str(info.get("gender") or "").upper()
    event_id = info.get("id")
    year = info.get("year")
    if not event_id or not year or tour not in {"MS", "WS"}:
        return []
    url = (
        f"https://www.live-tennis.cn/zh/survivor/event/"
        f"{event_id}/{year}/{tour}/my"
    )
    try:
        html = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=60
        ).text
    except requests.RequestException as err:
        logger.warning(f"day_points fetch failed {event_id}: {err}")
        return []
    return [int(value) for value in DAY_SCORE_RE.findall(html)]


def _snapshot_is_final(records: list[dict[str, Any]], day_points: list[int]) -> bool:
    """True when this score snapshot can be kept.

    The day ladder is published before the last day's results. If someone is
    still alive and the stored day has not reached that ladder, the score page
    was saved early and must be fetched again.
    """
    if len(day_points) < 2 or not records:
        return True
    max_day = max(int(row.get("day") or 0) for row in records)
    still_alive = any(row.get("champion") for row in records)
    return not (still_alive and max_day < len(day_points))


def _collect_history(
    tennis_type: str,
    current_event: Optional[dict[str, Any]] = None,
    cache_path: Path = STATS_CACHE,
    refresh: bool = True,
) -> list[dict[str, Any]]:
    live_key = None
    if current_event and current_event.get("name"):
        live_key = (current_event.get("name"), str(current_event.get("year") or ""))

    cache = _load_cache(cache_path)
    tour_cache = cache.setdefault(tennis_type, {})
    records: list[dict[str, Any]] = []
    changed = False

    if not refresh:
        # Cache-only mode: hydrate everything already stored
        for cached in tour_cache.values():
            if not isinstance(cached, dict) or not cached.get("completed"):
                continue
            points = list(cached.get("day_points") or [])
            records.extend(_hydrate_records(cached.get("records") or [], points))
        return records

    catalog = _list_tour_events(tennis_type)
    # Also keep cache-only events not in the (primary-only) calendar scan
    catalog_keys = {_event_cache_key(info) for info in catalog}
    for key, cached in list(tour_cache.items()):
        if key in catalog_keys or not isinstance(cached, dict):
            continue
        if cached.get("completed"):
            points = list(cached.get("day_points") or [])
            records.extend(_hydrate_records(cached.get("records") or [], points))

    for index, info in enumerate(catalog, start=1):
        if not info.get("id") or not info.get("year"):
            continue
        key = _event_cache_key(info)
        in_progress = live_key == (info.get("name"), str(info.get("year") or ""))
        cached = tour_cache.get(key) if isinstance(tour_cache.get(key), dict) else None
        if in_progress:
            logger.info(f"skip in-progress {info.get('year')}-{info.get('name')}")
            continue
        if cached and cached.get("completed"):
            points = list(cached.get("day_points") or [])
            if len(points) < 2:
                points = _fetch_event_day_points(info)
                cached["day_points"] = points
                cached["event_days"] = len(points)
                changed = True
            if _snapshot_is_final(cached.get("records") or [], points):
                event_records = _hydrate_records(cached.get("records") or [], points)
                records.extend(event_records)
                continue
            logger.info(
                f"refetch unfinished {info.get('year')}-{info.get('name')}"
            )
        logger.info(
            f"incremental {tennis_type.upper()} {index}/{len(catalog)} "
            f"{info.get('year')}-{info.get('name')}"
        )
        rows = _fetch_event_score_rows(info)
        points = _fetch_event_day_points(info)
        event_records = _records_from_event(
            info, rows, in_progress=False, day_points=points
        )
        if not event_records:
            continue
        tour_cache[key] = {
            "id": info.get("id"),
            "name": info.get("name"),
            "year": str(info.get("year") or ""),
            "completed": True,
            "event_days": len(points),
            "day_points": points,
            "records": _serialize_records(event_records),
        }
        changed = True
        records.extend(event_records)

    if changed:
        _save_cache(cache, cache_path)
        logger.info(f"wrote stats cache {cache_path}")
    else:
        logger.info("stats cache unchanged")
    return records


def _at_midnight(value: Any) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    else:
        stamp = pd.Timestamp(value).to_pydatetime()
    return stamp.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_two_week(name: str, start: datetime, nxt: Optional[datetime], tour: str) -> bool:
    if name in TWO_WEEK_EVENTS:
        return True
    if tour == "wta" and name == "北京":
        return True
    return nxt is not None and (nxt - start).days == 14


def _event_end(name: str, start: datetime, nxt: Optional[datetime], tour: str) -> datetime:
    days = 13 if _is_two_week(name, start, nxt, tour) else 6
    return start + timedelta(days=days)


def _load_calendar_rows(tour: str) -> list[dict[str, Any]]:
    code = "MS" if tour == "atp" else "WS"
    root = Path(__file__).resolve().parent.parent / "data"
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("calendar_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in payload.get("data") or []:
            if item.get("tour") != code or not item.get("week_start_date"):
                continue
            rows.append(item)
    rows.sort(key=lambda item: (item["week_start_date"], str(item.get("event_id"))))
    return rows


def _catalog_events(tour: str) -> list[dict[str, Any]]:
    """Calendar rows, collapsing a split week of the same event id."""
    pending: list[dict[str, Any]] = []
    for item in _load_calendar_rows(tour):
        start = datetime.strptime(item["week_start_date"][:10], "%Y-%m-%d")
        row = {
            "id": str(item.get("event_id") or ""),
            "year": str(item.get("event_year") or start.year),
            "name": str(item.get("city") or ""),
            "start": start,
        }
        if (
            pending
            and row["id"]
            and pending[-1]["id"] == row["id"]
            and 0 < (start - pending[-1]["start"]).days <= 14
        ):
            pending[-1] = row
            continue
        pending.append(row)
    events = sorted(pending, key=lambda item: (item["start"], item["name"], item["id"]))
    for index, event in enumerate(events):
        nxt = events[index + 1]["start"] if index + 1 < len(events) else None
        event["end"] = _event_end(event["name"], event["start"], nxt, tour)
        event["two_week"] = _is_two_week(event["name"], event["start"], nxt, tour)
    return events


def _official_board(tour: str) -> tuple[dict[str, set[str]], dict[str, int], Optional[datetime]]:
    """Current official zeros, scores, and the board's Monday."""
    table = "MS" if tour == "atp" else "WS"
    frame, _ = fetch_table(option="rank", tour=table, year=str(beijing_now().year))
    zeros: dict[str, set[str]] = {}
    scores: dict[str, int] = {}
    board_monday: Optional[datetime] = None
    if frame is None or frame.empty or "details" not in frame.columns:
        return zeros, scores, board_monday
    for row in frame.itertuples(index=False):
        raw = getattr(row, "details", None) or ""
        deleted_html = re.findall(r"<del\b[^>]*>(.*?)</del>", raw, flags=re.I | re.S)
        kept_html = re.sub(r"<del\b[^>]*>.*?</del>", " ", raw, flags=re.I | re.S)
        merged = parse_events(_strip_html(" ".join(deleted_html)))
        merged.update(parse_events(_strip_html(kept_html)))
        uid = _as_key(getattr(row, "user_id", ""))
        names = {name for name, points in merged.items() if points == 0}
        if names:
            zeros[uid] = names
        score = getattr(row, "score", None)
        if uid and score is not None and not (isinstance(score, float) and pd.isna(score)):
            scores[uid] = int(score)
        if board_monday is None and getattr(row, "monday", None):
            board_monday = _at_midnight(getattr(row, "monday"))
    return zeros, scores, board_monday


def _points_cache() -> dict[str, Any]:
    if not ROLLING_SCORE_CACHE.exists():
        return {"atp": {}, "wta": {}}
    try:
        payload = json.loads(ROLLING_SCORE_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"atp": {}, "wta": {}}
    payload.setdefault("atp", {})
    payload.setdefault("wta", {})
    return payload


def _score_rows(tour: str, event: dict[str, Any], cache: dict[str, Any]) -> list[tuple[str, int]]:
    key = f"{event['year']}:{event['id']}"
    stored = (cache.get(tour) or {}).get(key)
    if stored and stored.get("rows") is not None:
        return [(str(item["uid"]), int(item["score"])) for item in stored["rows"]]
    table = "MS" if tour == "atp" else "WS"
    frame, _ = fetch_table(
        option="score",
        tour=table,
        event_id=event["id"],
        year=event["year"],
    )
    rows: list[tuple[str, int]] = []
    if frame is not None and not frame.empty:
        for item in frame.itertuples(index=False):
            uid = _as_key(getattr(item, "user_id", ""))
            score = getattr(item, "score", None)
            if not uid or score is None or (isinstance(score, float) and pd.isna(score)):
                continue
            rows.append((uid, int(score)))
    if rows:
        cache.setdefault(tour, {})[key] = {
            "name": event["name"],
            "rows": [{"uid": uid, "score": score} for uid, score in rows],
        }
    return rows


def _counts_in_points(name: str, score: int, tour: str) -> bool:
    if score > 0:
        return True
    if name in GRAND_SLAMS:
        return True
    if tour == "atp":
        return name in ATP_MANDATORY
    return name in WTA1000_COMBINED or name in WTA1000_NON_COMBINED


def _player_total(scores: dict[str, int], tour: str) -> tuple[int, int]:
    raw = {
        name: score
        for name, score in scores.items()
        if _counts_in_points(name, score, tour)
    }
    finals = ATP_YEAR_END_FINALS if tour == "atp" else WTA_YEAR_END_FINAL
    for name in finals:
        if raw.get(name) == 0:
            raw.pop(name, None)
    if not raw:
        return 0, 0
    calc = _calculate_points_atp if tour == "atp" else _calculate_points_wta
    result = calc(raw)
    counted = result.get("counted_tournaments") or {}
    return int(result["total_points"]), len(counted)


def _rolling_peaks(
    history: pd.DataFrame,
    tour: str,
    this_monday: datetime,
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Best rank, best score, and weeks at No.1 from the end-date 52-week window.

    From Indian Wells 2026 onward, a 0 already on the current official board
    stays in that edition until it expires. Which equal-score event is kept
    is left to the existing points formula.
    """
    events = _catalog_events(tour)
    if not events:
        return {}, {}, {}
    zero_names, official_scores, board_monday = _official_board(tour)
    edition = {}
    for event in events:
        if event["end"] < this_monday:
            edition[event["name"]] = event
    score_cache = _points_cache()
    by_event: dict[tuple[str, datetime], list[tuple[str, int]]] = {}
    if not history.empty:
        for name, monday, uid, score in history[["name", "monday", "主键", "score"]].itertuples(index=False):
            by_event.setdefault((str(name), _at_midnight(monday)), []).append(
                (_as_key(uid), int(score))
            )
    fetch_from = FORCED_ZERO_START - timedelta(weeks=52)
    fetched = 0
    for event in events:
        if event["end"] < fetch_from or event["start"] >= this_monday or not event["id"]:
            continue
        key = f"{event['year']}:{event['id']}"
        had = key in (score_cache.get(tour) or {})
        rows = _score_rows(tour, event, score_cache)
        if rows:
            by_event[(event["name"], event["start"])] = rows
        if rows and not had:
            fetched += 1
            try:
                ROLLING_SCORE_CACHE.write_text(
                    json.dumps(score_cache, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as exc:
                logger.warning(f"Could not save rolling score cache: {exc}")
    if fetched:
        logger.info(f"{tour} fetched {fetched} score pages for the rolling window")

    # The Monday a two-week event starts still updates. The Monday inside it does not.
    inside = {event["start"] + timedelta(days=7) for event in events if event["two_week"]}
    first = min(event["end"] for event in events) + timedelta(days=1)
    first_monday = first - timedelta(days=first.weekday())
    mondays: list[datetime] = []
    cursor = first_monday
    while cursor <= this_monday:
        if cursor not in inside:
            mondays.append(cursor)
        cursor += timedelta(weeks=1)
    if this_monday not in inside and this_monday not in mondays:
        mondays.append(this_monday)

    best_rank: dict[str, int] = {}
    best_score: dict[str, int] = {}
    weeks_at_one: dict[str, int] = defaultdict(int)
    board_totals: dict[str, int] = {}
    for index, monday in enumerate(mondays):
        if monday < FORCED_ZERO_START:
            continue
        active: dict[str, dict[str, tuple[datetime, int]]] = defaultdict(dict)
        for event in events:
            if not (event["end"] < monday <= event["end"] + timedelta(weeks=52)):
                continue
            for uid, score in by_event.get((event["name"], event["start"]), []):
                held = active[uid].get(event["name"])
                if held is None or event["end"] >= held[0]:
                    active[uid][event["name"]] = (event["end"], score)
        if monday >= FORCED_ZERO_START:
            for uid, names in zero_names.items():
                bucket = active[uid]
                for name in names:
                    event = edition.get(name)
                    if event is None or not (event["end"] < monday <= event["end"] + timedelta(weeks=52)):
                        continue
                    if name in bucket:
                        continue
                    if name in CANADA_EVENTS and any(city in bucket for city in CANADA_EVENTS):
                        continue
                    bucket[name] = (event["end"], 0)
        totals: dict[str, int] = {}
        for uid, bucket in active.items():
            chosen = dict(bucket)
            canada = [city for city in CANADA_EVENTS if city in chosen]
            if len(canada) == 2:
                drop = min(canada, key=lambda city: chosen[city][0])
                chosen.pop(drop, None)
            scores = {name: score for name, (_end, score) in chosen.items()}
            total, _counted = _player_total(scores, tour)
            if total > 0 or scores:
                totals[uid] = total
        if not totals:
            continue
        ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        rank = 0
        last_score = None
        for place, (uid, total) in enumerate(ordered, start=1):
            if total != last_score:
                rank = place
                last_score = total
            best_rank[uid] = min(best_rank.get(uid, rank), rank)
            best_score[uid] = max(best_score.get(uid, total), total)
            if rank == 1:
                nxt = mondays[index + 1] if index + 1 < len(mondays) else monday + timedelta(weeks=1)
                weeks_at_one[uid] += max(1, (nxt - monday).days // 7)
        if board_monday is not None and monday == board_monday:
            board_totals = totals
    if official_scores and board_totals:
        matched = sum(
            1
            for uid, score in official_scores.items()
            if board_totals.get(uid) == score
        )
        logger.info(
            f"{tour} rolling score vs official {board_monday.date() if board_monday else ''}: "
            f"{matched}/{len(official_scores)}"
        )
    logger.info(
        f"{tour} rolling ranks from {FORCED_ZERO_START.date()}: "
        f"{len(best_rank)} players, {len([m for m in mondays if m >= FORCED_ZERO_START])} Mondays"
    )
    return best_rank, best_score, dict(weeks_at_one)


def build_player_stats(
    tennis_type: str,
    current_event: Optional[dict[str, Any]] = None,
    *,
    cache_path: Path = STATS_CACHE,
    refresh: bool = True,
) -> pd.DataFrame:
    """Build the career-stats table for ``atp`` or ``wta``."""
    tennis_type = tennis_type.strip().lower()
    rules = TourRules.for_tour(tennis_type)
    forced: list[str] = []
    for name in rules.forced:
        name = "加拿大" if name in CANADA_EVENTS else name
        if name not in forced:
            forced.append(name)
    rules = TourRules(
        tennis_type=rules.tennis_type,
        slams=rules.slams,
        forced=forced,
        uncombined=rules.uncombined,
        finals=rules.finals,
        forced_keep=rules.forced_keep,
        uncombined_keep=rules.uncombined_keep,
        other_keep=rules.other_keep,
    )
    this_monday = beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday = this_monday - timedelta(days=this_monday.weekday())
    season_year = this_monday.year
    window_start = this_monday - timedelta(weeks=52)
    records = _collect_history(
        tennis_type, current_event, cache_path=cache_path, refresh=refresh
    )

    if not records:
        return pd.DataFrame(columns=DISPLAY_COLS)

    history = pd.DataFrame(records)
    history = history.sort_values(["monday", "name"]).reset_index(drop=True)
    users = (
        history.groupby("主键", as_index=False)
        .agg(用户名=("用户名", "last"))
        .set_index("主键")
    )

    completed = history[history["completed"]]
    event_mondays = sorted(
        {
            value
            for value in completed["monday"].tolist()
            if isinstance(value, datetime)
        }
    )
    best_rank: dict[str, int] = {}
    best_score: dict[str, int] = {}
    weeks_at_one: dict[str, int] = defaultdict(int)
    rank_points: list[datetime] = []
    if event_mondays:
        rank_points = sorted(
            {
                value
                for start in event_mondays
                for value in (
                    start,
                    start + timedelta(weeks=1),
                    start + timedelta(weeks=53),
                    start + timedelta(weeks=54),
                )
                if event_mondays[0] < value <= this_monday
            }
            | {this_monday}
        )
    for index, monday in enumerate(rank_points):
        if monday >= FORCED_ZERO_START:
            continue
        # Before Indian Wells, keep the previous start-date window.
        window = completed[
            (completed["monday"] >= monday - timedelta(weeks=53))
            & (completed["monday"] < monday)
        ]
        if window.empty:
            continue
        canada = window[window["name"].isin(CANADA_EVENTS)]
        if not canada.empty:
            latest = canada.loc[canada.groupby("主键")["monday"].idxmax()].copy()
            latest["name"] = "加拿大"
            window = pd.concat(
                [window[~window["name"].isin(CANADA_EVENTS)], latest],
                ignore_index=True,
            )
        used_names: set[str] = set()
        rename: dict[tuple[str, str], str] = {}
        for _, event in window[["name", "year"]].drop_duplicates().iterrows():
            rename[(event["name"], event["year"])] = _unique_event_name(
                event["name"], event["year"], used_names
            )
        window = window.copy()
        window["col"] = window.apply(
            lambda row: rename[(row["name"], row["year"])], axis=1
        )
        scores = (
            window.pivot_table(index="主键", columns="col", values="score", aggfunc="max")
            .fillna(0)
        )
        events = list(scores.columns)
        totals = scores.apply(lambda row: row_total(row, rules, events), axis=1)
        ranks = totals.rank(ascending=False, method="min")
        nxt = (
            rank_points[index + 1]
            if index + 1 < len(rank_points)
            else monday + timedelta(weeks=1)
        )
        nweeks = max((nxt - monday).days // 7, 0)
        for uid, total in totals.items():
            total_int = int(total)
            rank_int = int(ranks.loc[uid])
            if uid not in best_score or total_int > best_score[uid]:
                best_score[uid] = total_int
            if uid not in best_rank or rank_int < best_rank[uid]:
                best_rank[uid] = rank_int
            if rank_int == 1:
                weeks_at_one[uid] += nweeks

    rolled_rank, rolled_score, rolled_weeks = _rolling_peaks(
        completed, tennis_type, this_monday
    )
    for uid, rank_int in rolled_rank.items():
        best_rank[uid] = min(best_rank.get(uid, rank_int), rank_int)
    for uid, total_int in rolled_score.items():
        best_score[uid] = max(best_score.get(uid, total_int), total_int)
    for uid, nweeks in rolled_weeks.items():
        weeks_at_one[uid] += nweeks

    rows_out: list[dict[str, Any]] = []
    for uid, meta in users.iterrows():
        person = history[history["主键"] == uid].sort_values("monday")
        cycle = person[person["monday"] > window_start]
        season = person[person["season_year"] == season_year]
        titles = person[person["champion"]]
        runners = person[person["runner"]]
        lose_flags = [
            ((not row.champion) and int(row.day) <= 1, row.label, int(row.day))
            for row in person.itertuples()
        ]
        win_days, win_detail = _win_streak(person)
        lose_days, lose_detail = _longest_streak(lose_flags, False)
        season_possible = int(season["max_day"].sum()) if not season.empty else 0
        all_possible = int(person["max_day"].sum()) if not person.empty else 0
        season_rate = (
            round(float(season["day"].sum()) / season_possible, 6)
            if season_possible
            else 0.0
        )
        all_rate = (
            round(float(person["day"].sum()) / all_possible, 6) if all_possible else 0.0
        )
        title_labels = [str(x) for x in titles["label"].tolist()]
        runner_labels = [str(x) for x in runners["label"].tolist()]
        rows_out.append(
            {
                "主键": uid,
                "用户名": meta["用户名"],
                "周期参赛数": int(len(cycle)),
                "周期冠军数": int(cycle["champion"].sum()),
                "历史冠军数": int(titles.shape[0]),
                "历史亚军数": int(runners.shape[0]),
                "历史最佳排名": int(best_rank.get(uid, 0)),
                "历史最长连胜天数": int(win_days),
                "历史最长连败天数": int(lose_days),
                "世界第一周数": int(weeks_at_one.get(uid, 0)),
                "历史最高得分": int(best_score.get(uid, 0)),
                "赛季存活率": season_rate,
                "历史存活率": all_rate,
                CAREER_DETAIL_COL: {
                    "titles": title_labels,
                    "runners": runner_labels,
                    "win_streak": str(win_detail or ""),
                    "lose_streak": str(lose_detail or ""),
                },
            }
        )

    frame = pd.DataFrame(rows_out)
    frame["_最佳排名"] = frame["历史最佳排名"].replace(0, 10**9)
    frame = frame.sort_values(
        ["历史冠军数", "历史亚军数", "_最佳排名"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    frame = frame.drop(columns=["_最佳排名"])
    frame["排名"] = range(1, len(frame) + 1)
    view = frame[DISPLAY_COLS + [CAREER_DETAIL_COL]].copy()
    # Show rates as percent strings for readability
    for col in ("赛季存活率", "历史存活率"):
        view[col] = view[col].map(lambda v: f"{float(v) * 100:.1f}%")
    return view


def update_player_stats_pages(
    output_dir: str | Path = "..",
    *,
    tours: tuple[str, ...] = ("atp", "wta"),
    refresh: bool = True,
    atp_event: Optional[dict[str, Any]] = None,
    wta_event: Optional[dict[str, Any]] = None,
    updated: Optional[str] = None,
) -> list[Path]:
    """Build ATP/WTA show pages with frog UI."""
    from survivor_html import render_ranking_page

    output_dir = Path(output_dir)
    updated = updated or beijing_now().strftime("%Y年%m月%d日 %H:%M:%S")
    written: list[Path] = []
    current = {"atp": atp_event, "wta": wta_event}
    for tour in tours:
        logger.info(f"building {tour.upper()} player stats (refresh={refresh})")
        df = build_player_stats(
            tour, current.get(tour), refresh=refresh
        )
        out = output_dir / f"{tour}_show.html"
        render_ranking_page(
            df=df,
            title=f"{tour.upper()}球员成绩统计",
            tour=tour.upper(),
            eyebrow=f"{tour.upper()} · Career & Cycle Stats",
            updated=updated,
            summary_df=None,
            rank_change_col=None,
            extra_tags=["生涯统计", "点击行查看夺冠/夺亚"],
            available_players=None,
            enable_detail=False,
            enable_career_detail=True,
            output_path=str(out),
        )
        written.append(out)
        logger.info(f"wrote {out} ({len(df)} rows)")
    return written

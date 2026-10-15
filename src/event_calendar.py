"""
Survivor calendar browser — year-filtered 赛历 + per-event score detail pages.

Mirrors live-tennis calendar / score board UX using frog's existing fetchers.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from home_weeks import load_calendar_json
from logger import get_logger
from parser import fetch_survivor_calendar_event_df, fetch_table
from site_html.types_meta import champion_type_label, event_theoretical_max

logger = get_logger(__name__)

CACHE_DIR = Path("../data/event_scores")
DRAW_CACHE_DIR = Path("../data/event_draws")
CALENDAR_DIR = Path("../data")
EVENTS_DIR_NAME = "events"


def _safe_token(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^\w.\-]+", "_", text, flags=re.UNICODE)
    return text or "unknown"


def score_cache_path(
    tour: str, event_id: str, year: int, cache_dir: Path = CACHE_DIR
) -> Path:
    return Path(cache_dir) / f"{_safe_token(tour)}_{_safe_token(event_id)}_{int(year)}.json"


def draw_cache_path(
    tour: str, event_id: str, year: int, cache_dir: Path = DRAW_CACHE_DIR
) -> Path:
    return Path(cache_dir) / f"{_safe_token(tour)}_{_safe_token(event_id)}_{int(year)}.json"


def score_html_relpath(tour: str, event_id: str, year: int) -> str:
    return (
        f"{EVENTS_DIR_NAME}/{int(year)}/"
        f"{_safe_token(tour)}_{_safe_token(event_id)}.html"
    )


def calendar_json_path(year: int, calendar_dir: Path = CALENDAR_DIR) -> Path:
    return Path(calendar_dir) / f"calendar_{int(year)}.json"


def load_or_fetch_calendar(
    year: int,
    *,
    calendar_dir: Path = CALENDAR_DIR,
    refresh: bool = False,
    allow_fetch: bool = True,
) -> pd.DataFrame:
    path = calendar_json_path(year, calendar_dir)
    if path.exists() and not refresh:
        frame = load_calendar_json(path)
        if not frame.empty:
            return frame
    if not allow_fetch:
        return load_calendar_json(path) if path.exists() else pd.DataFrame()
    try:
        frame, _meta = fetch_survivor_calendar_event_df(int(year))
    except Exception as err:
        logger.warning(f"calendar {year} fetch failed: {err}")
        if path.exists():
            return load_calendar_json(path)
        return pd.DataFrame()
    if frame is None or frame.empty:
        return pd.DataFrame()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_json(path, orient="table", force_ascii=False, indent=2)
    return frame


def _players_to_list(value: Any) -> list[str]:
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text.replace("'", '"'))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [text]


def _row_players(row: Any, picks_col: str) -> list[str]:
    picks = row.get(picks_col) if hasattr(row, "get") else None
    if picks is None and hasattr(row, picks_col):
        picks = row[picks_col]
    if not isinstance(picks, list):
        picks = _players_to_list(picks)
    return [str(p).strip() for p in picks if str(p).strip()]


def _match_pick_rows(
    df: pd.DataFrame, matches: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """
    For each finished draw match, resolve pick-day slot + pick counts.

    Killer credit goes to the winner: kills = picks on the loser that day
    (people who backed the opponent and got sent home).
    """
    from collections import Counter

    if df is None or df.empty or not matches:
        return []

    status_col = "当前状态" if "当前状态" in df.columns else "fill_status"
    picks_col = "选人明细" if "选人明细" in df.columns else "players"
    if status_col not in df.columns or picks_col not in df.columns:
        return []

    loser_idxs: dict[str, Counter] = {}
    for _, row in df.iterrows():
        if str(row.get(status_col) or "").strip() != "球员输球":
            continue
        players = _row_players(row, picks_col)
        if not players:
            continue
        loser = players[-1]
        if loser == "轮空":
            continue
        raw = row.get(picks_col)
        if not isinstance(raw, list):
            raw = _players_to_list(raw)
        raw = [str(p).strip() for p in raw]
        if not raw or raw[-1] != loser:
            idx = len(players) - 1
        else:
            idx = len(raw) - 1
        loser_idxs.setdefault(loser, Counter())[idx] += 1

    name_col = "用户名" if "用户名" in df.columns else "username"

    def picks_at(idx: int) -> Counter:
        counts: Counter = Counter()
        for _, row in df.iterrows():
            raw = row.get(picks_col)
            if not isinstance(raw, list):
                raw = _players_to_list(raw)
            raw = [str(p).strip() for p in raw]
            if idx < 0 or idx >= len(raw):
                continue
            name = raw[idx]
            if name and name != "轮空":
                counts[name] += 1
        return counts

    def users_picking(idx: int, player: str) -> list[str]:
        """Usernames who had ``player`` on pick-day ``idx``."""
        out: list[str] = []
        target = str(player or "").strip()
        if not target or name_col not in df.columns:
            return out
        for _, row in df.iterrows():
            raw = row.get(picks_col)
            if not isinstance(raw, list):
                raw = _players_to_list(raw)
            raw = [str(p).strip() for p in raw]
            if idx < 0 or idx >= len(raw):
                continue
            if raw[idx] != target:
                continue
            uname = str(row.get(name_col) or "").strip()
            if uname:
                out.append(uname)
        return out

    rows: list[dict[str, Any]] = []
    for match in matches:
        winner = str(match.get("winner") or "").strip()
        loser = str(match.get("loser") or "").strip()
        if not winner or not loser:
            continue
        idx_counts = loser_idxs.get(loser)
        if not idx_counts:
            continue
        idx = idx_counts.most_common(1)[0][0]
        counts = picks_at(idx)
        n_win = int(counts.get(winner, 0))
        n_lose = int(counts.get(loser, 0))
        rows.append(
            {
                "winner": winner,
                "loser": loser,
                "day_index": int(idx),
                "winner_picks": n_win,
                "loser_picks": n_lose,
                "kills": n_lose,  # winner送走选了loser的人
                "winner_users": users_picking(idx, winner),
            }
        )
    return rows


def _biggest_upset(
    df: pd.DataFrame, matches: list[dict[str, str]]
) -> Optional[dict[str, Any]]:
    """
    Largest pick-count gap in a finished match where the less-picked side won.

    Both sides must have ≥1 pick that day. Includes ``winner_users`` who
    picked the underdog that day.
    """
    best: Optional[dict[str, Any]] = None
    for row in _match_pick_rows(df, matches):
        n_win = int(row["winner_picks"])
        n_lose = int(row["loser_picks"])
        if n_win <= 0 or n_lose <= 0:
            continue
        if n_win >= n_lose:
            continue
        diff = n_lose - n_win
        if best is None or diff > int(best["diff"]):
            best = {
                "winner": row["winner"],
                "loser": row["loser"],
                "winner_picks": n_win,
                "loser_picks": n_lose,
                "diff": diff,
                "winner_users": list(row.get("winner_users") or []),
            }
    return best


def _killer_stats(
    df: pd.DataFrame, matches: Optional[list[dict[str, str]]] = None
) -> dict[str, Any]:
    """
    「克星」= match winner; kills = that day's picks on the opponent
    (people who backed the loser and got sent home).

    Distinct from traditional 「杀手」(picked X and X lost).

    - day_killer → UI 单日克星: most kills in any single match
    - total_killer → UI 累计克星: sum across all wins
    """
    from collections import Counter, defaultdict

    empty = {
        "day_killer": "",
        "day_kills": 0,
        "day_index": 0,
        "day_loser": "",
        "day_detail": None,
        "total_killer": "",
        "total_kills": 0,
        "total_details": [],
        "top_killer": "",
        "top_kills": 0,
    }
    rows = _match_pick_rows(df, matches or [])
    if not rows:
        return empty

    total_counts: Counter = Counter()
    by_winner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    day_killer = ""
    day_kills = 0
    day_index = 0
    day_loser = ""
    for row in rows:
        winner = str(row["winner"])
        loser = str(row["loser"])
        kills = int(row["kills"])
        idx = int(row["day_index"])
        if kills <= 0:
            continue
        detail = {
            "day_index": idx,
            "loser": loser,
            "kills": kills,
        }
        total_counts[winner] += kills
        by_winner[winner].append(detail)
        if kills > day_kills or (
            kills == day_kills and (not day_killer or idx < day_index)
        ):
            day_killer, day_kills, day_index, day_loser = (
                winner,
                kills,
                idx,
                loser,
            )

    total_killer = ""
    total_kills = 0
    total_details: list[dict[str, Any]] = []
    if total_counts:
        total_killer, total_kills = total_counts.most_common(1)[0]
        total_details = sorted(
            by_winner.get(total_killer) or [],
            key=lambda d: (int(d["day_index"]), str(d["loser"])),
        )

    day_detail = None
    if day_killer:
        day_detail = {
            "day_index": int(day_index),
            "loser": day_loser,
            "kills": int(day_kills),
        }

    return {
        "day_killer": day_killer,
        "day_kills": int(day_kills),
        "day_index": int(day_index),
        "day_loser": day_loser,
        "day_detail": day_detail,
        "total_killer": total_killer,
        "total_kills": int(total_kills),
        "total_details": total_details,
        "top_killer": total_killer,
        "top_kills": int(total_kills),
    }


def event_board_stats(
    df: pd.DataFrame,
    *,
    city: str,
    tour: str,
    completed: bool = False,
    matches: Optional[list[dict[str, str]]] = None,
    type_hint: str = "",
    level_hint: str = "",
) -> dict[str, Any]:
    """
    Summary strip for an event score page.

    - champions: users whose score equals the event's theoretical max
    - day_killer: winner who eliminated the most picks in one match
    - total_killer: winner with most eliminations summed across all their wins
    - biggest_upset: underdog win with max pick-count gap (both sides picked)
    """
    champions: list[str] = []
    max_pts = event_theoretical_max(
        city, tour, type_hint=type_hint, level_hint=level_hint
    )
    if max_pts is not None and df is not None and not df.empty:
        score_col = "本站得分" if "本站得分" in df.columns else "score"
        name_col = "用户名" if "用户名" in df.columns else "username"
        if score_col in df.columns and name_col in df.columns:
            scores = pd.to_numeric(df[score_col], errors="coerce").fillna(0)
            champions = [
                str(x).strip()
                for x in df.loc[scores == max_pts, name_col].tolist()
                if str(x).strip()
            ]

    match_list = matches or []
    killers = _killer_stats(df, match_list)
    upset = _biggest_upset(df, match_list)

    return {
        "champions": champions,
        "max_points": max_pts,
        **killers,
        "biggest_upset": upset,
        "n_players": 0 if df is None or df.empty else len(df),
        "completed": bool(completed),
    }


def normalize_score_df(df: pd.DataFrame) -> pd.DataFrame:
    """Display columns sorted by score desc (then days)."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["排名", "用户名", "当前状态", "存活天数", "本站得分", "选人明细"]
        )
    out = df.copy()
    rename = {
        "username": "用户名",
        "fill_status": "当前状态",
        "day": "存活天数",
        "score": "本站得分",
        "players": "选人明细",
    }
    for src, dst in rename.items():
        if src in out.columns and dst not in out.columns:
            out = out.rename(columns={src: dst})
    if "用户名" not in out.columns:
        out["用户名"] = ""
    if "当前状态" not in out.columns:
        out["当前状态"] = ""
    if "存活天数" not in out.columns:
        out["存活天数"] = 0
    if "本站得分" not in out.columns:
        out["本站得分"] = 0
    if "选人明细" not in out.columns:
        out["选人明细"] = [[] for _ in range(len(out))]
    else:
        out["选人明细"] = out["选人明细"].map(_players_to_list)

    out["存活天数"] = pd.to_numeric(out["存活天数"], errors="coerce").fillna(0).astype(int)
    out["本站得分"] = pd.to_numeric(out["本站得分"], errors="coerce").fillna(0).astype(int)
    out["当前状态"] = out["当前状态"].astype("string").fillna("").str.strip()
    out["用户名"] = out["用户名"].astype("string").fillna("").str.strip()

    out = out.sort_values(
        by=["本站得分", "存活天数", "用户名"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    out.insert(0, "排名", range(1, len(out) + 1))
    return out.loc[:, ["排名", "用户名", "当前状态", "存活天数", "本站得分", "选人明细"]]


def _rows_from_cache(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    return rows if isinstance(rows, list) else []


def load_score_cache(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as err:
        logger.warning(f"bad score cache {path}: {err}")
        return None


def load_draw_matches(
    tour: str,
    event_id: str,
    year: int,
    *,
    cache_dir: Path = DRAW_CACHE_DIR,
) -> list[dict[str, str]]:
    path = draw_cache_path(tour, event_id, year, cache_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as err:
        logger.warning(f"bad draw cache {path}: {err}")
        return []
    matches = payload.get("matches") if isinstance(payload, dict) else None
    if not isinstance(matches, list):
        return []
    out: list[dict[str, str]] = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        winner = str(item.get("winner") or "").strip()
        loser = str(item.get("loser") or "").strip()
        if not winner or not loser:
            continue
        out.append(
            {
                "left": str(item.get("left") or "").strip(),
                "right": str(item.get("right") or "").strip(),
                "winner": winner,
                "loser": loser,
            }
        )
    return out


def fetch_and_cache_draw_matches(
    tour: str,
    event_id: str,
    year: int,
    *,
    cache_dir: Path = DRAW_CACHE_DIR,
    refresh: bool = False,
) -> list[dict[str, str]]:
    path = draw_cache_path(tour, event_id, year, cache_dir)
    if path.exists() and not refresh:
        cached = load_draw_matches(tour, event_id, year, cache_dir=cache_dir)
        if cached:
            return cached
    try:
        from draw_status import fetch_draw_matches

        matches = fetch_draw_matches(event_id, year, tour)
    except Exception as err:
        logger.warning(f"draw match fetch failed {tour}/{event_id}/{year}: {err}")
        return load_draw_matches(tour, event_id, year, cache_dir=cache_dir)

    payload = {
        "event_id": str(event_id),
        "year": int(year),
        "tour": str(tour).upper(),
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "matches": matches,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return matches


def sync_event_draws(
    events: list[dict[str, Any]],
    *,
    cache_dir: Path = DRAW_CACHE_DIR,
    refresh_missing: bool = True,
    force_incomplete: bool = True,
    max_fetch: Optional[int] = None,
) -> dict[str, int]:
    """Cache completed draw matches for upset stats (skip when cache-only)."""
    counts = {"fetched": 0, "cached": 0, "empty": 0, "skipped": 0}
    fetched = 0
    for ev in events:
        path = draw_cache_path(ev["tour"], ev["event_id"], ev["year"], cache_dir)
        page_type = str(ev.get("page_type") or "").lower()
        completed = page_type == "score"
        has_cache = path.exists()
        force = force_incomplete and not completed
        if has_cache and not force:
            counts["cached"] += 1
            continue
        if not force and not refresh_missing:
            counts["skipped"] += 1
            continue
        if max_fetch is not None and fetched >= max_fetch:
            counts["skipped"] += 1
            continue
        matches = fetch_and_cache_draw_matches(
            ev["tour"],
            ev["event_id"],
            ev["year"],
            cache_dir=cache_dir,
            refresh=True,
        )
        fetched += 1
        counts["fetched"] += 1
        if not matches:
            counts["empty"] += 1
    return counts


def fetch_event_score(
    tour: str,
    event_id: str,
    year: int,
    *,
    city: str = "",
    page_type: str = "",
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> dict[str, Any]:
    """
    Return cache payload ``{meta..., rows:[...]}``.

    Completed events (page_type=score) are cached permanently unless refresh.
    Ongoing / my pages are refetched when refresh=True.
    """
    path = score_cache_path(tour, event_id, year, cache_dir)
    cached = load_score_cache(path)
    completed = str(page_type or "").lower() == "score"
    if cached and not refresh and (cached.get("completed") or completed):
        if cached.get("rows") is not None:
            return cached

    rows: list[dict] = []
    try:
        df, _n = fetch_table(
            option="score",
            tour=str(tour).upper(),
            event_id=event_id,
            year=int(year),
        )
        if df is not None and not df.empty:
            # Persist JSON-friendly records (players as list)
            raw = df.copy()
            if "players" in raw.columns:
                raw["players"] = raw["players"].map(_players_to_list)
            # Drop bulky raw username HTML if present
            drop_cols = [c for c in ("username_raw",) if c in raw.columns]
            if drop_cols:
                raw = raw.drop(columns=drop_cols)
            rows = json.loads(raw.to_json(orient="records", force_ascii=False))
    except Exception as err:
        logger.warning(f"score fetch failed {tour}/{event_id}/{year}: {err}")
        if cached and cached.get("rows") is not None:
            return cached

    payload = {
        "event_id": str(event_id),
        "year": int(year),
        "tour": str(tour).upper(),
        "city": str(city or (cached or {}).get("city") or ""),
        "page_type": str(page_type or (cached or {}).get("page_type") or ""),
        "completed": completed,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def _event_dict(row: pd.Series) -> dict[str, Any]:
    year = int(row["event_year"]) if pd.notna(row.get("event_year")) else int(row.get("year") or 0)
    tour = str(row.get("event_tour") or row.get("tour") or "").upper()
    event_id = str(row.get("event_id") or "")
    page_type = str(row.get("page_type") or "").lower()
    city = str(row.get("city") or "").strip()
    monday = row.get("week_start_date")
    mmdd = str(row.get("week_start_mmdd") or "")
    if hasattr(monday, "strftime"):
        monday_s = monday.strftime("%Y-%m-%d")
        if not mmdd:
            mmdd = monday.strftime("%m-%d")
    else:
        monday_s = str(monday or "")[:10]
    href = score_html_relpath(tour, event_id, year)
    type_hint = str(row.get("type") or "").strip()
    level_hint = str(row.get("level") or "").strip()
    return {
        "year": year,
        "tour": tour,
        "event_id": event_id,
        "city": city,
        "page_type": page_type,
        "week_start": monday_s,
        "week_mmdd": mmdd,
        "href": href,
        "source_url": str(row.get("url") or ""),
        "level": level_hint,
        "type": champion_type_label(
            city, tour, type_hint=type_hint, level_hint=level_hint
        ),
    }


def list_calendar_events(
    years: list[int],
    *,
    calendar_dir: Path = CALENDAR_DIR,
    refresh_calendar: bool = False,
    allow_fetch: bool = True,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for year in years:
        frame = load_or_fetch_calendar(
            year,
            calendar_dir=calendar_dir,
            refresh=refresh_calendar,
            allow_fetch=allow_fetch,
        )
        if frame is None or frame.empty:
            continue
        for _, row in frame.iterrows():
            ev = _event_dict(row)
            if ev["event_id"] and ev["tour"] in {"MS", "WS"}:
                events.append(ev)
    events.sort(key=lambda e: (e["year"], e["week_start"], e["tour"], e["city"]))
    return events


def sync_event_scores(
    events: list[dict[str, Any]],
    *,
    cache_dir: Path = CACHE_DIR,
    refresh_missing: bool = True,
    force_all: bool = False,
    refresh_current_year: Optional[int] = None,
    max_fetch: Optional[int] = None,
) -> dict[str, int]:
    """
    Fetch score tables into cache.

    - Completed events: fetch once, reuse cache
    - Open (page_type!=score) in ``refresh_current_year``: refetch when syncing
    - ``force_all``: refetch everything
    """
    counts = {"fetched": 0, "cached": 0, "empty": 0, "skipped": 0}
    fetched = 0
    for ev in events:
        path = score_cache_path(ev["tour"], ev["event_id"], ev["year"], cache_dir)
        cached = load_score_cache(path)
        page_type = str(ev.get("page_type") or "").lower()
        completed = page_type == "score"
        force = force_all
        # Ongoing events in the active season: keep refreshing.
        if (
            not force
            and refresh_current_year is not None
            and int(ev["year"]) == int(refresh_current_year)
            and not completed
        ):
            force = True
        # Event just finished (my → score): one final fetch to freeze the board.
        if (
            not force
            and completed
            and cached
            and cached.get("rows") is not None
            and not cached.get("completed")
        ):
            force = True
        # Completed + already frozen cache: never refetch.
        if (
            cached
            and cached.get("rows") is not None
            and (cached.get("completed") or completed)
            and not force
        ):
            counts["cached"] += 1
            continue
        if cached and cached.get("rows") is not None and not force:
            counts["cached"] += 1
            continue
        if not force and not refresh_missing:
            counts["skipped"] += 1
            continue
        if max_fetch is not None and fetched >= max_fetch:
            counts["skipped"] += 1
            continue
        logger.info(
            f"fetch score {ev.get('tour')}/{ev.get('city')}/"
            f"{ev.get('event_id')}/{ev.get('year')}"
        )
        payload = fetch_event_score(
            ev["tour"],
            ev["event_id"],
            ev["year"],
            city=ev.get("city") or "",
            page_type=ev.get("page_type") or "",
            cache_dir=cache_dir,
            refresh=True,
        )
        fetched += 1
        counts["fetched"] += 1
        if not payload.get("rows"):
            counts["empty"] += 1
    return counts


def score_df_from_cache(
    tour: str, event_id: str, year: int, *, cache_dir: Path = CACHE_DIR
) -> pd.DataFrame:
    payload = load_score_cache(score_cache_path(tour, event_id, year, cache_dir))
    if not payload:
        return normalize_score_df(pd.DataFrame())
    return normalize_score_df(pd.DataFrame(_rows_from_cache(payload)))


def update_survivor_calendar_pages(
    *,
    years: Optional[list[int]] = None,
    year_from: int = 2020,
    year_to: Optional[int] = None,
    output_dir: Union[str, Path] = "..",
    calendar_dir: Union[str, Path] = CALENDAR_DIR,
    cache_dir: Union[str, Path] = CACHE_DIR,
    draw_cache_dir: Union[str, Path] = DRAW_CACHE_DIR,
    refresh: bool = True,
    refresh_calendar: bool = False,
    max_fetch: Optional[int] = None,
    updated: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build ATP/WTA calendar pages + hub, and per-event score pages under ``events/``.
    """
    from site_html.calendar import (
        render_calendar_hub_page,
        render_calendar_page,
        render_event_score_page,
    )

    output_dir = Path(output_dir)
    calendar_dir = Path(calendar_dir)
    cache_dir = Path(cache_dir)
    draw_cache_dir = Path(draw_cache_dir)
    year_to = int(year_to or datetime.now().year)
    if years is None:
        years = list(range(int(year_from), int(year_to) + 1))
    else:
        years = [int(y) for y in years]

    updated = updated or datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    # Always render the full configured year span on the calendar page,
    # even when this run only syncs a subset (e.g. --calendar-year 2025).
    all_years = list(range(int(year_from), int(year_to) + 1))
    sync_years = years
    events_all = list_calendar_events(
        all_years,
        calendar_dir=calendar_dir,
        refresh_calendar=refresh_calendar,
        allow_fetch=refresh or refresh_calendar,
    )
    sync_set = {int(y) for y in sync_years}
    events_to_sync = [e for e in events_all if int(e["year"]) in sync_set]
    counts = sync_event_scores(
        events_to_sync,
        cache_dir=cache_dir,
        refresh_missing=refresh,
        force_all=False,
        refresh_current_year=year_to if refresh else None,
        max_fetch=max_fetch,
    )
    logger.info(
        f"event scores: fetched={counts['fetched']} cached={counts['cached']} "
        f"empty={counts['empty']} skipped={counts['skipped']}"
    )
    draw_counts = sync_event_draws(
        events_to_sync,
        cache_dir=draw_cache_dir,
        refresh_missing=refresh,
        force_incomplete=bool(refresh),
        max_fetch=max_fetch,
    )
    logger.info(
        f"event draws: fetched={draw_counts['fetched']} cached={draw_counts['cached']} "
        f"empty={draw_counts['empty']} skipped={draw_counts['skipped']}"
    )

    # Attach has_scores flag for calendar links
    for ev in events_all:
        payload = load_score_cache(
            score_cache_path(ev["tour"], ev["event_id"], ev["year"], cache_dir)
        )
        n = len(_rows_from_cache(payload or {}))
        ev["has_scores"] = n > 0
        ev["n_players"] = n
        if not ev.get("type"):
            ev["type"] = champion_type_label(
                ev.get("city") or "",
                ev.get("tour") or "",
                type_hint=str(ev.get("type") or ""),
                level_hint=str(ev.get("level") or ""),
            )

    hub_path = output_dir / "survivor_calendar.html"
    atp_path = output_dir / "survivor_calendar_atp.html"
    wta_path = output_dir / "survivor_calendar_wta.html"
    render_calendar_hub_page(updated=updated, output_path=hub_path)
    render_calendar_page(
        events=events_all,
        years=all_years,
        updated=updated,
        output_path=atp_path,
        tour="MS",
        default_year=year_to,
    )
    render_calendar_page(
        events=events_all,
        years=all_years,
        updated=updated,
        output_path=wta_path,
        tour="WS",
        default_year=year_to,
    )

    written = 0
    for ev in events_all:
        df = score_df_from_cache(
            ev["tour"], ev["event_id"], ev["year"], cache_dir=cache_dir
        )
        if df.empty:
            continue
        payload = load_score_cache(
            score_cache_path(ev["tour"], ev["event_id"], ev["year"], cache_dir)
        )
        completed = bool((payload or {}).get("completed")) or (
            str(ev.get("page_type") or "").lower() == "score"
        )
        matches = load_draw_matches(
            ev["tour"],
            ev["event_id"],
            ev["year"],
            cache_dir=draw_cache_dir,
        )
        stats = event_board_stats(
            df,
            city=ev["city"],
            tour=ev["tour"],
            completed=completed,
            matches=matches,
            type_hint=str(ev.get("type") or ""),
            level_hint=str(ev.get("level") or ""),
        )
        out = output_dir / ev["href"]
        render_event_score_page(
            df=df,
            city=ev["city"],
            tour=ev["tour"],
            year=ev["year"],
            event_id=ev["event_id"],
            updated=updated,
            output_path=out,
            source_url=ev.get("source_url") or "",
            stats=stats,
            type_label=str(ev.get("type") or ""),
        )
        written += 1

    logger.info(
        f"wrote calendars {atp_path.name}/{wta_path.name} (+ hub) "
        f"+ {written} event score pages"
    )
    return {
        "years": all_years,
        "sync_years": sync_years,
        "events": len(events_all),
        "score_pages": written,
        "counts": counts,
        "draw_counts": draw_counts,
        "calendar_path": str(hub_path),
        "atp_calendar_path": str(atp_path),
        "wta_calendar_path": str(wta_path),
    }

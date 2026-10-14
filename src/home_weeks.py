"""Homepage 上/本/下周赛况 — calendar weeks + YoY event correspondence."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from write_config import build_replace_map, find_corresponding_week_events

logger = logging.getLogger(__name__)

TOUR_CODE = {"ATP": "MS", "WTA": "WS"}
TOUR_LABEL = {"MS": "ATP", "WS": "WTA"}


def week_monday(when: Optional[datetime | str | pd.Timestamp] = None) -> pd.Timestamp:
    ts = pd.Timestamp(when or datetime.now()).normalize()
    return ts - pd.Timedelta(days=int(ts.weekday()))


def load_calendar_json(path: Union[str, Path]) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_json(path, orient="table")
    if "week_start_date" in raw.columns:
        raw["week_start_date"] = pd.to_datetime(raw["week_start_date"])
    return raw


def _event_rows(calendar: pd.DataFrame, tour_flag: str) -> pd.DataFrame:
    if calendar is None or calendar.empty:
        return pd.DataFrame()
    tour = calendar.loc[calendar["tour"].astype(str).str.upper() == tour_flag.upper()].copy()
    if tour.empty:
        return tour
    tour["week_start_date"] = pd.to_datetime(tour["week_start_date"])
    tour["city"] = tour["city"].astype(str).str.strip()
    tour["event_id"] = tour["event_id"].astype(str)
    tour["page_type"] = tour.get("page_type", pd.Series("", index=tour.index)).astype(str)
    return tour.dropna(subset=["week_start_date"]).sort_values("week_start_date")


def tour_schedule(calendar: pd.DataFrame, tour_flag: str) -> list[tuple[pd.Timestamp, list[dict]]]:
    """Group tour events by Monday → list of event dicts (stable city order)."""
    tour = _event_rows(calendar, tour_flag)
    if tour.empty:
        return []
    out: list[tuple[pd.Timestamp, list[dict]]] = []
    for monday, grp in tour.groupby("week_start_date", sort=True):
        events = [row.to_dict() for _, row in grp.iterrows()]
        out.append((pd.Timestamp(monday).normalize(), events))
    return out


def _events_still_open(events: list[dict]) -> bool:
    return any(str(e.get("page_type") or "").lower() == "my" for e in events)


def resolve_tour_week(
    calendar: pd.DataFrame,
    tour_flag: str,
    this_monday: Optional[pd.Timestamp] = None,
) -> dict[str, Any]:
    """
    Resolve previous / current / next event lists for one tour.

    Mirrors chen unfinished-week carryover using calendar ``page_type == 'my'``.
    """
    monday = week_monday(this_monday)
    schedule = tour_schedule(calendar, tour_flag)
    this_events = [e for start, evs in schedule if start.date() == monday.date() for e in evs]
    before = [(s, e) for s, e in schedule if s.date() < monday.date()]
    after = [(s, e) for s, e in schedule if s.date() > monday.date()]
    next_start, upcoming = after[0] if after else (None, [])
    later = after[1][1] if len(after) > 1 else []

    if this_events:
        current_start, current = monday, this_events
        previous = before[-1][1] if before else []
        nxt = upcoming
    elif before:
        last_start, last_events = before[-1]
        previous_of_last = before[-2][1] if len(before) > 1 else []
        if _events_still_open(last_events):
            current_start, current = last_start, last_events
            previous = previous_of_last
            nxt = upcoming
        elif upcoming and _events_still_open(upcoming):
            current_start, current = next_start or monday, upcoming
            previous = last_events
            nxt = later
        else:
            current_start, current = monday, []
            previous = last_events
            nxt = upcoming
    else:
        current_start, current = monday, []
        previous = []
        nxt = upcoming

    return {
        "tour": tour_flag,
        "this_monday": monday,
        "current_start": pd.Timestamp(current_start).normalize(),
        "previous_events": previous,
        "current_events": current,
        "next_events": nxt,
    }


def _champions_for(
    champions: Optional[pd.DataFrame],
    tour_label: str,
    city: str,
    week: Optional[pd.Timestamp] = None,
    season: Optional[int] = None,
) -> dict[str, Any]:
    """Lookup champions.csv rows for a city (+ optional week / season)."""
    empty = {"names": [], "score": 0, "level": "", "week": None, "found": False}
    if champions is None or champions.empty or not city:
        return empty
    df = champions.copy()
    df["tournament"] = df["tournament"].astype(str).str.strip()
    df["tour"] = df["tour"].astype(str).str.strip().str.upper()
    mask = (df["tournament"] == str(city).strip()) & (df["tour"] == tour_label.upper())
    hit = df.loc[mask]
    if hit.empty:
        return empty
    if season is not None and "season" in hit.columns:
        by_season = hit.loc[
            pd.to_numeric(hit["season"], errors="coerce") == int(season)
        ]
        if by_season.empty:
            return empty
        hit = by_season
    if week is not None and "week" in hit.columns:
        w = pd.Timestamp(week).normalize()
        by_week = hit.loc[pd.to_datetime(hit["week"]).dt.normalize() == w]
        if by_week.empty:
            # Season matched but not this Monday — still allow season rows
            pass
        else:
            hit = by_week
    # Prefer latest week if still ambiguous
    if "week" in hit.columns and hit["week"].nunique() > 1:
        latest = pd.to_datetime(hit["week"]).max()
        hit = hit.loc[pd.to_datetime(hit["week"]) == latest]
    names = [str(n).strip() for n in hit["username"].tolist() if str(n).strip()]
    score = int(pd.to_numeric(hit["score"], errors="coerce").max() or 0)
    level = ""
    if "type" in hit.columns and not hit.empty:
        level = str(hit.iloc[0]["type"] or "")
    week_val = None
    if "week" in hit.columns and not hit.empty:
        week_val = pd.Timestamp(hit.iloc[0]["week"]).normalize()
    return {
        "names": names,
        "score": score,
        "level": level,
        "week": week_val,
        "found": bool(names),
    }


def _summarize_score_event(event: dict, tour_label: str) -> dict[str, Any]:
    """Fallback: read official score table for survivors / top score."""
    empty = {"names": [], "score": 0, "level": "", "found": False}
    eid = event.get("event_id")
    year = event.get("event_year") or event.get("year")
    tour_code = event.get("event_tour") or TOUR_CODE.get(tour_label)
    if not eid or not year or not tour_code:
        return empty
    try:
        from parser import fetch_table

        score_df, _ = fetch_table(
            option="score", tour=str(tour_code), event_id=eid, year=int(year)
        )
    except Exception:
        logger.exception("score fetch failed for %s %s", tour_label, eid)
        return empty
    if score_df is None or getattr(score_df, "empty", True):
        return empty
    status_col = "fill_status" if "fill_status" in score_df.columns else None
    name_col = "username" if "username" in score_df.columns else None
    score_col = "score" if "score" in score_df.columns else None
    if status_col and name_col:
        alive = score_df.loc[
            score_df[status_col].astype(str).str.strip().eq("存活"), name_col
        ]
        names = [str(n).strip() for n in alive.tolist() if str(n).strip()]
        if names:
            top = 0
            if score_col:
                top = int(
                    pd.to_numeric(
                        score_df.loc[alive.index, score_col], errors="coerce"
                    ).max()
                    or 0
                )
            return {"names": names, "score": top, "level": "", "found": True}
    if score_col and name_col:
        scores = pd.to_numeric(score_df[score_col], errors="coerce").fillna(0)
        top = int(scores.max() or 0)
        names = [
            str(n).strip()
            for n, s in zip(score_df[name_col].tolist(), scores.tolist())
            if str(n).strip() and int(s or 0) == top
        ]
        return {"names": [], "score": top, "level": "", "found": False, "top_names": names}
    return empty


def _result_for_event(
    event: dict,
    tour_label: str,
    champions: Optional[pd.DataFrame],
    *,
    season: Optional[int] = None,
    fetch_score: bool = True,
) -> dict[str, Any]:
    city = str(event.get("city") or "").strip()
    ch = _champions_for(
        champions,
        tour_label,
        city,
        week=event.get("week_start_date"),
        season=season,
    )
    if ch["found"]:
        return ch
    if not fetch_score:
        return ch
    if str(event.get("page_type") or "").lower() == "my":
        return ch  # still live — don't treat score as final
    scored = _summarize_score_event(event, tour_label)
    if scored.get("found"):
        return {
            "names": scored["names"],
            "score": scored["score"],
            "level": ch.get("level") or "",
            "week": event.get("week_start_date"),
            "found": True,
        }
    # Wipeout: keep top scorers in score field path via names empty + score
    if scored.get("score"):
        return {
            "names": [],
            "score": scored["score"],
            "level": ch.get("level") or "",
            "week": event.get("week_start_date"),
            "found": False,
            "top_names": scored.get("top_names") or [],
        }
    return ch


def _primary_event(events: list[dict]) -> Optional[dict]:
    return events[0] if events else None


def _event_link(event: Optional[dict]) -> str:
    if not event:
        return ""
    url = str(event.get("url") or "").strip()
    if url:
        # Prefer live my-page when still open
        if str(event.get("page_type") or "").lower() == "my":
            return url
        return url.replace("/score", "/my").replace("/detail", "/my")
    eid = event.get("event_id")
    year = event.get("event_year") or event.get("year")
    tour = event.get("event_tour") or event.get("tour")
    if eid and year and tour:
        return f"https://www.live-tennis.cn/zh/survivor/event/{eid}/{year}/{tour}/my"
    return ""


def _correspond_cities(
    event: dict,
    this_calendar: pd.DataFrame,
    last_calendar: pd.DataFrame,
    tour_flag: str,
    replace_map: Optional[dict[str, list[str]]] = None,
) -> list[str]:
    """YoY corresponding cities via slam/1000 anchor map (not naive −52w)."""
    eid = str(event.get("event_id") or "")
    city = str(event.get("city") or "").strip()
    week = event.get("week_start_date")
    if replace_map is not None and eid in replace_map:
        return list(replace_map.get(eid) or [])
    return find_corresponding_week_events(
        last_calendar,
        tour_flag,
        week,
        this_event_id=eid or None,
        this_calendar=this_calendar,
        this_city=city or None,
    )


@dataclass
class TourWeekCard:
    tour: str  # ATP / WTA
    kind: str  # last | this | next
    city: str = ""
    level: str = ""
    week_start: Optional[pd.Timestamp] = None
    link: str = ""
    participants: Optional[int] = None
    survivors: Optional[int] = None
    champions: list[str] = field(default_factory=list)
    top_names: list[str] = field(default_factory=list)
    top_score: int = 0
    corresponding: list[str] = field(default_factory=list)
    defending_names: list[str] = field(default_factory=list)
    defending_top_names: list[str] = field(default_factory=list)
    defending_score: int = 0
    defending_level: str = ""
    empty_label: str = ""  # 无赛事 / 休赛期
    ongoing: bool = False


def build_tour_week_cards(
    *,
    tour_label: str,
    week: dict[str, Any],
    this_calendar: pd.DataFrame,
    last_calendar: pd.DataFrame,
    champions: Optional[pd.DataFrame] = None,
    replace_map: Optional[dict[str, list[str]]] = None,
    live_participants: Optional[int] = None,
    live_survivors: Optional[int] = None,
    live_city: Optional[str] = None,
) -> dict[str, TourWeekCard]:
    tour_flag = TOUR_CODE[tour_label]
    prev = _primary_event(week["previous_events"])
    curr = _primary_event(week["current_events"])
    nxt = _primary_event(week["next_events"])

    # ── last week ──
    if prev:
        city = str(prev.get("city") or "")
        ch = _result_for_event(prev, tour_label, champions)
        last = TourWeekCard(
            tour=tour_label,
            kind="last",
            city=city,
            level=ch.get("level") or "",
            week_start=pd.Timestamp(prev["week_start_date"]).normalize(),
            link=_event_link(prev),
            champions=ch.get("names") or [],
            top_names=ch.get("top_names") or [],
            top_score=int(ch.get("score") or 0),
            ongoing=str(prev.get("page_type") or "").lower() == "my",
        )
    else:
        last = TourWeekCard(tour=tour_label, kind="last", empty_label="无赛事")

    # ── this week (+ YoY correspondence for 卫冕) ──
    if curr:
        city = str(curr.get("city") or "")
        # Prefer live meta when this is the event main.py is tracking
        use_live = (
            live_city is not None
            and str(live_city).strip() == city
            and (live_participants is not None or live_survivors is not None)
        )
        corr = _correspond_cities(
            curr, this_calendar, last_calendar, tour_flag, replace_map
        )
        defending_names: list[str] = []
        defending_top_names: list[str] = []
        defending_score = 0
        defending_level = ""
        prev_year = int(pd.Timestamp(curr["week_start_date"]).year) - 1
        last_rows = _event_rows(last_calendar, tour_flag)
        for corr_city in corr:
            dch = _champions_for(
                champions,
                tour_label,
                corr_city,
                season=prev_year,
            )
            if not dch["found"]:
                cand = last_rows.loc[last_rows["city"] == corr_city]
                if not cand.empty:
                    dch = _result_for_event(
                        cand.iloc[0].to_dict(),
                        tour_label,
                        champions,
                        season=prev_year,
                    )
            if dch.get("found") or dch.get("score") or dch.get("top_names"):
                defending_names = dch.get("names") or []
                defending_top_names = dch.get("top_names") or []
                defending_score = int(dch.get("score") or 0)
                defending_level = dch.get("level") or ""
                break
        # Level only from this-year finished results (don't leak YoY type labels)
        ch_now = _champions_for(
            champions,
            tour_label,
            city,
            week=curr.get("week_start_date"),
            season=int(pd.Timestamp(curr["week_start_date"]).year),
        )
        this = TourWeekCard(
            tour=tour_label,
            kind="this",
            city=city,
            level=ch_now["level"] if ch_now.get("found") else "",
            week_start=pd.Timestamp(curr["week_start_date"]).normalize(),
            link=_event_link(curr),
            participants=live_participants if use_live else None,
            survivors=live_survivors if use_live else None,
            corresponding=corr,
            defending_names=defending_names,
            defending_top_names=defending_top_names,
            defending_score=defending_score,
            defending_level=defending_level,
            ongoing=str(curr.get("page_type") or "").lower() == "my",
        )
    else:
        this = TourWeekCard(tour=tour_label, kind="this", empty_label="无赛事")

    # ── next week ──
    if nxt:
        city = str(nxt.get("city") or "")
        corr = _correspond_cities(
            nxt, this_calendar, last_calendar, tour_flag, replace_map
        )
        next_card = TourWeekCard(
            tour=tour_label,
            kind="next",
            city=city,
            week_start=pd.Timestamp(nxt["week_start_date"]).normalize(),
            link=_event_link(nxt),
            corresponding=corr,
        )
    else:
        next_card = TourWeekCard(tour=tour_label, kind="next", empty_label="休赛期")

    return {"last": last, "this": this, "next": next_card}


def prepare_home_weeks(
    this_calendar: pd.DataFrame,
    last_calendar: pd.DataFrame,
    champions: Optional[pd.DataFrame] = None,
    *,
    atp_live: Optional[dict[str, Any]] = None,
    wta_live: Optional[dict[str, Any]] = None,
    this_monday: Optional[pd.Timestamp] = None,
) -> dict[str, Any]:
    """
    Build structured week-card data for the homepage.

    ``atp_live`` / ``wta_live`` optional keys: city, participants, survivors.
    """
    atp_live = atp_live or {}
    wta_live = wta_live or {}
    monday = week_monday(this_monday)

    replace_maps = {
        "MS": build_replace_map(this_calendar, last_calendar, "MS"),
        "WS": build_replace_map(this_calendar, last_calendar, "WS"),
    }

    tours: dict[str, dict[str, TourWeekCard]] = {}
    for label, code, live in (
        ("ATP", "MS", atp_live),
        ("WTA", "WS", wta_live),
    ):
        week = resolve_tour_week(this_calendar, code, monday)
        tours[label] = build_tour_week_cards(
            tour_label=label,
            week=week,
            this_calendar=this_calendar,
            last_calendar=last_calendar,
            champions=champions,
            replace_map=replace_maps[code],
            live_participants=live.get("participants"),
            live_survivors=live.get("survivors"),
            live_city=live.get("city"),
        )
        logger.info(
            "%s weeks: last=%s this=%s next=%s corr=%s",
            label,
            tours[label]["last"].city or tours[label]["last"].empty_label,
            tours[label]["this"].city or tours[label]["this"].empty_label,
            tours[label]["next"].city or tours[label]["next"].empty_label,
            tours[label]["this"].corresponding or "∅",
        )

    return {
        "this_monday": monday,
        "tours": tours,
        "replace_maps": replace_maps,
    }

from __future__ import annotations

import copy
from typing import Optional

import pandas as pd
import yaml

from bye import get_draw_info
from logger import get_logger
from pathlib import Path
from parser import get_coordinates, fetch_event_detail, fetch_survivor_calendar_event_df
from points_calculation import (
    ATP_MANDATORY,
    GRAND_SLAMS,
    WTA1000_COMBINED,
    WTA1000_NON_COMBINED,
)

logger = get_logger(__name__)

# Slam + 1000 anchors (always held; always 1:1 replace across seasons).
# Canada alternates Montreal/Toronto — treat as one anchor family.
_CANADA = frozenset({"蒙特利尔", "多伦多"})
_WTA_ANCHORS = frozenset(GRAND_SLAMS | WTA1000_COMBINED | WTA1000_NON_COMBINED)
_ATP_ANCHORS = frozenset(GRAND_SLAMS | ATP_MANDATORY)


class ConfigManager:
    def __init__(self, config_path):
        self.config_path = Path(config_path)

    def save(self, config):
        with self.config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                config,
                f,
                allow_unicode=True,
                sort_keys=False,  # not soft_key=False
                default_flow_style=False,
            )

    def load(self):
        if not self.config_path.exists():
            return {}

        with self.config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def update(self, updates):
        config = self.load()
        self._deep_update(config, updates)
        self.save(config)

    @staticmethod
    def _deep_update(original, updates):
        for k, v in updates.items():
            if isinstance(v, dict) and isinstance(original.get(k), dict):
                ConfigManager._deep_update(original[k], v)
            else:
                original[k] = copy.deepcopy(v)  # parentheses, not brackets


def validate_event(event_dict):
    if event_dict is None:
        return False
    if event_dict.get("event_id") is None:
        return False

    current_week = pd.Timestamp.today().normalize() - pd.Timedelta(
        days=pd.Timestamp.today().normalize().weekday()
    )
    day_diff = (current_week - event_dict["week_start_date"]).days

    if day_diff > 14:
        return False

    return True


def upcoming_monday(input_date):
    input_date = pd.Timestamp(input_date).normalize()
    days_until_monday = (7 - input_date.weekday()) % 7
    return input_date + pd.Timedelta(days=days_until_monday)


def find_last_day(detail_dict):
    last_day = max(detail_dict["days"].keys())
    last_date = detail_dict["days"][last_day]["date"]
    return last_date


def _unique_cities(frame: pd.DataFrame) -> list[str]:
    names = []
    seen = set()
    if frame is None or frame.empty or "city" not in frame.columns:
        return names
    for name in frame["city"].tolist():
        text = str(name).strip() if name is not None else ""
        if text and text not in seen:
            seen.add(text)
            names.append(text)
    return names


def _anchor_set(tour_flag: str) -> frozenset[str]:
    return _WTA_ANCHORS if str(tour_flag).upper() == "WS" else _ATP_ANCHORS


def _prep_tour_calendar(calendar: pd.DataFrame, tour_flag: str) -> pd.DataFrame:
    if calendar is None or calendar.empty:
        return pd.DataFrame()
    tour = calendar.loc[calendar["tour"] == tour_flag].copy()
    if tour.empty:
        return tour
    tour["week_start_date"] = pd.to_datetime(tour["week_start_date"])
    tour = tour.dropna(subset=["week_start_date", "event_id"])
    tour["city"] = tour["city"].astype(str).str.strip()
    tour["event_id"] = tour["event_id"].astype(str)
    sort_cols = ["week_start_date"]
    if "page_type" in tour.columns:
        sort_cols.append("page_type")
    tour = tour.sort_values(sort_cols).drop_duplicates(subset=["event_id"], keep="first")
    return tour.sort_values("week_start_date").reset_index(drop=True)


def _is_anchor_city(city: str, anchors: frozenset[str]) -> bool:
    return city in anchors


def _match_anchor_pairs(
    this_cal: pd.DataFrame, last_cal: pd.DataFrame, anchors: frozenset[str]
) -> list[tuple[pd.Timestamp, pd.Timestamp, str, str, str]]:
    """Return (this_monday, last_monday, this_city, last_city, this_event_id)."""
    this_a = this_cal.loc[this_cal["city"].isin(anchors)]
    last_a = last_cal.loc[last_cal["city"].isin(anchors)]
    used_last: set[int] = set()
    pairs: list[tuple[pd.Timestamp, pd.Timestamp, str, str, str]] = []

    for _, row in this_a.iterrows():
        cand = None
        # 1) same event_id (handles 蒙特利尔↔多伦多)
        same_id = last_a.loc[
            (~last_a.index.isin(used_last))
            & (last_a["event_id"] == str(row["event_id"]))
        ]
        if not same_id.empty:
            cand = same_id.iloc[0]
        else:
            same_city = last_a.loc[
                (~last_a.index.isin(used_last)) & (last_a["city"] == row["city"])
            ]
            if not same_city.empty:
                cand = same_city.iloc[0]
            elif row["city"] in _CANADA:
                canada = last_a.loc[
                    (~last_a.index.isin(used_last)) & (last_a["city"].isin(_CANADA))
                ]
                if not canada.empty:
                    cand = canada.iloc[0]
        if cand is None:
            logger.warning(
                f"anchor {row['city']} ({row['event_id']}) has no last-year pair"
            )
            continue
        used_last.add(int(cand.name))
        pairs.append(
            (
                pd.Timestamp(row["week_start_date"]),
                pd.Timestamp(cand["week_start_date"]),
                str(row["city"]),
                str(cand["city"]),
                str(row["event_id"]),
            )
        )
    pairs.sort(key=lambda item: item[0])
    return pairs


def _segment_key(
    this_monday: pd.Timestamp,
    pairs: list[tuple[pd.Timestamp, pd.Timestamp, str, str, str]],
) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    prevs = [p for p in pairs if p[0] <= this_monday]
    nexts = [p for p in pairs if p[0] >= this_monday]
    prev = prevs[-1][0] if prevs else None
    nxt = nexts[0][0] if nexts else None
    return prev, nxt


def build_replace_map(
    this_calendar: pd.DataFrame,
    last_calendar: pd.DataFrame,
    tour_flag: str,
    max_day_delta: int = 10,
) -> dict[str, list[str]]:
    """
    Build this_event_id → [last_year cities] using slam/1000 anchors + time fill.

    Empty list ⇒ last year had no event in the corresponding week slot.
    Mid-tier events inside one anchor gap are matched 1:1 by time (no double-claim).
    """
    anchors = _anchor_set(tour_flag)
    this_cal = _prep_tour_calendar(this_calendar, tour_flag)
    last_cal = _prep_tour_calendar(last_calendar, tour_flag)
    if this_cal.empty:
        return {}
    pairs = _match_anchor_pairs(this_cal, last_cal, anchors)
    out: dict[str, list[str]] = {}

    # Anchors first
    for _, row in this_cal.iterrows():
        eid = str(row["event_id"])
        city = str(row["city"])
        this_monday = pd.Timestamp(row["week_start_date"])
        if city not in anchors:
            continue
        by_id = [p for p in pairs if p[4] == eid]
        if by_id:
            out[eid] = [by_id[0][3]]
        else:
            by_week = [p for p in pairs if p[0] == this_monday]
            out[eid] = [by_week[0][3]] if by_week else []

    # Mid-tier: group by neighbouring anchors, 1:1 assign by interpolated time
    mid = this_cal.loc[~this_cal["city"].isin(anchors)].copy()
    if mid.empty:
        return out

    def pair_at(this_monday: pd.Timestamp):
        prevs = [p for p in pairs if p[0] <= this_monday]
        nexts = [p for p in pairs if p[0] >= this_monday]
        return (prevs[-1] if prevs else None), (nexts[0] if nexts else None)

    segments: dict[
        tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]], list[pd.Series]
    ] = {}
    for _, row in mid.iterrows():
        key = _segment_key(pd.Timestamp(row["week_start_date"]), pairs)
        segments.setdefault(key, []).append(row)

    for (seg_prev, seg_nxt), rows in segments.items():
        rows = sorted(rows, key=lambda r: pd.Timestamp(r["week_start_date"]))
        # Resolve last-year pool for this segment from any row's neighbours
        sample_monday = pd.Timestamp(rows[0]["week_start_date"])
        prev, nxt = pair_at(sample_monday)
        if prev and nxt and prev[0] != nxt[0]:
            pool = last_cal.loc[
                (last_cal["week_start_date"] > prev[1])
                & (last_cal["week_start_date"] < nxt[1])
            ].copy()
        elif prev:
            pool = last_cal.loc[last_cal["week_start_date"] > prev[1]].copy()
            if nxt:
                pool = pool.loc[pool["week_start_date"] < nxt[1]]
        elif nxt:
            pool = last_cal.loc[last_cal["week_start_date"] < nxt[1]].copy()
        else:
            pool = last_cal.copy()

        def _target_for(row: pd.Series) -> pd.Timestamp:
            this_monday = pd.Timestamp(row["week_start_date"])
            prev_r, nxt_r = pair_at(this_monday)
            if prev_r and nxt_r and prev_r[0] != nxt_r[0]:
                span_t = (nxt_r[0] - prev_r[0]).days
                span_l = (nxt_r[1] - prev_r[1]).days
                frac = (
                    0.0
                    if span_t <= 0
                    else (this_monday - prev_r[0]).days / span_t
                )
                return prev_r[1] + pd.Timedelta(days=round(frac * span_l))
            if prev_r:
                return prev_r[1] + (this_monday - prev_r[0])
            if nxt_r:
                return nxt_r[1] - (nxt_r[0] - this_monday)
            return this_monday - pd.Timedelta(weeks=52)

        claimed: set[pd.Timestamp] = set()
        pending: list[pd.Series] = []

        # Pass 1: same city name within the gap (布拉格→布拉格 before 雅典 can steal it)
        for row in rows:
            eid = str(row["event_id"])
            city = str(row["city"])
            if pool.empty:
                out[eid] = []
                continue
            avail = pool.loc[
                (~pool["week_start_date"].isin(claimed)) & (pool["city"] == city)
            ]
            if avail.empty:
                pending.append(row)
                continue
            target = _target_for(row)
            scored = avail.assign(
                _delta=(avail["week_start_date"] - target).abs().dt.days
            ).sort_values(["_delta", "week_start_date"])
            pick = scored.iloc[0]
            # Same-name can stretch a bit farther than cross-name fills
            if int(pick["_delta"]) > max_day_delta + 14:
                pending.append(row)
                continue
            week = pd.Timestamp(pick["week_start_date"])
            claimed.add(week)
            out[eid] = _unique_cities(pool.loc[pool["week_start_date"] == week])

        # Pass 2: remaining this-year events → leftover last-year weeks by time
        for row in pending:
            eid = str(row["event_id"])
            if pool.empty:
                out[eid] = []
                continue
            avail = pool.loc[~pool["week_start_date"].isin(claimed)]
            if avail.empty:
                out[eid] = []
                continue
            target = _target_for(row)
            scored = avail.assign(
                _delta=(avail["week_start_date"] - target).abs().dt.days
            ).sort_values(["_delta", "week_start_date"])
            pick = scored.iloc[0]
            if int(pick["_delta"]) > max_day_delta:
                out[eid] = []
                continue
            week = pd.Timestamp(pick["week_start_date"])
            claimed.add(week)
            out[eid] = _unique_cities(pool.loc[pool["week_start_date"] == week])

    return out


def find_corresponding_week_events(
    last_calendar: pd.DataFrame,
    tour_flag: str,
    this_week_start,
    this_event_id=None,
    this_calendar: Optional[pd.DataFrame] = None,
    this_city: Optional[str] = None,
    max_day_delta: int = 10,
) -> list[str]:
    """
    Map this year's event to last year's corresponding replacement event(s).

    Uses Grand Slam + 1000 tournaments as season anchors (always 1:1), then
    places mid-tier events by relative time between neighbouring anchors.
    2025 may have empty weeks while 2026 is denser — those map to [].
    """
    this_week_start = pd.Timestamp(this_week_start).normalize()
    if this_calendar is None or this_calendar.empty:
        # Minimal single-row this-year frame so mapping still runs
        this_calendar = pd.DataFrame(
            [
                {
                    "tour": tour_flag,
                    "week_start_date": this_week_start,
                    "city": this_city or "",
                    "event_id": str(this_event_id or ""),
                    "page_type": "score",
                }
            ]
        )

    replace_map = build_replace_map(
        this_calendar, last_calendar, tour_flag, max_day_delta=max_day_delta
    )
    eid = str(this_event_id).strip() if this_event_id is not None else ""
    if eid and eid in replace_map:
        names = replace_map[eid]
        logger.info(
            f"{tour_flag} replace (anchor-map) "
            f"{this_week_start.date()} {this_city or ''} → {names or '∅'}"
        )
        return names

    # Fallback: locate by week_start + city in this calendar
    this_cal = _prep_tour_calendar(this_calendar, tour_flag)
    if this_city:
        hit = this_cal.loc[
            (this_cal["week_start_date"] == this_week_start)
            & (this_cal["city"] == str(this_city).strip())
        ]
        if not hit.empty:
            names = replace_map.get(str(hit.iloc[0]["event_id"]), [])
            logger.info(
                f"{tour_flag} replace (anchor-map/city) "
                f"{this_week_start.date()} {this_city} → {names or '∅'}"
            )
            return names

    logger.warning(
        f"{tour_flag} replace map miss for {this_week_start.date()} "
        f"id={this_event_id} city={this_city}"
    )
    return []


def build_tour_config(
    event_dict,
    config_manager,
    tour_label,
    valid_flag,
    last_yr_calendar_path: str,
    ranking_monday: pd.Timestamp,
    debug_flag: bool = False,
):
    tour_flag = "WS" if tour_label.lower() == "wta" else "MS"
    if valid_flag:
        current_id = event_dict["event_id"]
    else:
        current_id = None

    config = config_manager.load()

    saved_id = config.get(tour_label, {}).get("event")

    if saved_id != current_id:
        if event_dict is None:
            config_dict = {"event": None, "name": None, "week_start_date": None}
            config_manager.update({tour_label: config_dict})
            logger.info("Clear %s event in YAML (no ongoing tournament)", tour_label)
            return config_dict
        config_dict = {
            "event": current_id,
            "name": event_dict["city"],
            "week_start_date": event_dict["week_start_date"].strftime("%Y-%m-%d"),
        }
        # Anchor-based replace: slam/1000 first, mid-tier by time between anchors.
        calendar_path = Path(last_yr_calendar_path)
        week_names: list[str] = []
        if not calendar_path.exists():
            logger.warning(
                "last-year calendar missing at %s; skip replace-map", calendar_path
            )
        elif event_dict is None:
            logger.warning("no current event; skip replace-map for %s", tour_label)
        else:
            last_calendar = pd.read_json(calendar_path, orient="table")
            for col in ["week_start_date", "valid_from", "invalid_date"]:
                if col in last_calendar.columns:
                    last_calendar[col] = pd.to_datetime(last_calendar[col])

            this_year = int(
                event_dict["event_year"]
                if event_dict.get("event_year") is not None
                else pd.Timestamp(event_dict["week_start_date"]).year
            )
            this_calendar, _ = fetch_survivor_calendar_event_df(this_year)

            week_names = find_corresponding_week_events(
                last_calendar,
                tour_flag,
                event_dict["week_start_date"],
                this_event_id=current_id,
                this_calendar=this_calendar,
                this_city=event_dict.get("city"),
            )
        if week_names:
            config_dict["removed_tournament_name"] = (
                week_names[0] if len(week_names) == 1 else week_names
            )
        else:
            # No corresponding week last year (empty slot) — nothing to remove.
            config_dict["removed_tournament_name"] = None
            logger.info(
                f"{tour_flag} {event_dict.get('city')}: no last-year counterpart; "
                f"removed_tournament_name=null"
            )

        if current_id is not None:
            # find coordination
            lat, lon = get_coordinates(event_dict["city_en"])
            config_dict["latitude"] = lat
            config_dict["longitude"] = lon

            # find bye rate
            draw_info = get_draw_info(current_id, event_dict["event_year"], tour_flag)
            if debug_flag:
                print(draw_info)
            config_dict["bye_rate"] = draw_info["bye_rate"]

        # write to yaml
        config_manager.update({tour_label: config_dict})
        logger.info("Update YAML!")
        if debug_flag:
            print(config_dict)
        return config_dict
    else:
        return config[tour_label]


def _write_point_removal_date(year: int, path: str):
    calendar, _ = fetch_survivor_calendar_event_df(year)
    calendar["valid_from"] = calendar.apply(
        lambda x: upcoming_monday(
            find_last_day(
                fetch_event_detail(x["event_id"], x["event_year"], x["event_tour"])
            )
        ),
        axis=1,
    )
    calendar["invalid_date"] = calendar["valid_from"] + pd.Timedelta(weeks=52)
    calendar_path = Path(path)
    calendar.to_json(
        calendar_path,
        orient="table",
        date_format="iso",
        index=False,
        force_ascii=False,  # preserve Chinese tournament/city names
    )

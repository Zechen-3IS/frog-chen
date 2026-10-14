from __future__ import annotations

import numpy as np
import os
import pandas as pd
from datetime import datetime, timedelta
from logger import get_logger
from parser import fetch_survivor_calendar_event_df, fetch_table
from pathlib import Path
from survivor_html import render_h2h_page

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover
    tqdm = None

H2H_COLS = [
    "user_id",
    "username",
    "player",
    "tour",
    "tournament",
    "day",
    "season",
    "week_start_date",
    "result",
]

SEASONS = [2024, 2025, 2026]
logger = get_logger(__name__)


def build_h2h_records(
    event_df: pd.DataFrame,
    city: str,
    tour: str,
    week_start_date,
    season: int,
) -> pd.DataFrame:
    if event_df is None or event_df.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "username",
                "player",
                "tour",
                "tournament",
                "day",
                "season",
                "week_start_date",
                "result",
            ]
        )

    df = event_df.copy()

    # keep only rows with non-empty players list
    # (assumes players is already list-like per row)
    df = df[
        df["players"].apply(lambda x: isinstance(x, (list, tuple)) and len(x) > 0)
    ].copy()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "username",
                "player",
                "tour",
                "tournament",
                "day",
                "season",
                "week_start_date",
                "result",
            ]
        )

    # stable source id per original row
    df = df.reset_index(drop=True)
    df["_src_id"] = df.index

    # explode players — assign day and total count BEFORE filtering byes
    out = df.explode("players", ignore_index=True).rename(columns={"players": "player"})
    out["day"] = out.groupby("_src_id").cumcount() + 1
    out["n_players"] = out.groupby("_src_id")["player"].transform("size")

    out = out[out["player"].astype(str).str.strip() != "轮空"].copy()
    if out.empty:
        return pd.DataFrame(columns=H2H_COLS)

    # is_last: this pick was the final pick in the original list
    out["is_last"] = out["day"].eq(out["n_players"])

    # result logic: status only controls the last pick
    out["result"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out.loc[~out["is_last"], "result"] = "W"
    out.loc[out["is_last"] & out["status"].eq(2), "result"] = "W"
    out.loc[out["is_last"] & out["status"].eq(-2), "result"] = "L"

    # drop invalid last entries
    out = out.dropna(subset=["result"]).copy()
    # metadata
    out["tour"] = tour
    out["tournament"] = city
    out["week_start_date"] = week_start_date
    out["season"] = season

    # final columns
    out = out[
        [
            "user_id",
            "username",
            "player",
            "tour",
            "tournament",
            "day",
            "season",
            "week_start_date",
            "result",
        ]
    ].reset_index(drop=True)

    return out


def build_season_h2h(year: int):
    calendar, _ = fetch_survivor_calendar_event_df(year)

    all_parts = []
    failed_events = []
    total_events = len(calendar)

    logger.info(f"[H2H] Start building season={year}, events={total_events}")

    iterator = calendar.iterrows()
    if tqdm is not None:
        iterator = tqdm(
            iterator,
            total=total_events,
            desc=f"H2H {year}",
            unit="event",
        )

    success_cnt = 0
    skipped_cnt = 0

    for idx, row in iterator:
        event_id = row["event_id"]
        city = row["city"]
        week = row["week_start_date"]
        tour = row["tour"]  # "MS" or "WS"
        season = row["year"]  # or use `year`

        try:
            event_df, _ = fetch_table(
                option="score",
                page_size=1000,
                event_id=event_id,
                year=season,
                tour=tour,
            )

            h2h_event = build_h2h_records(
                event_df=event_df,
                city=city,
                tour=tour,
                week_start_date=week,
                season=season,
            )

            if h2h_event.empty:
                skipped_cnt += 1
                logger.info(
                    f"[H2H] Empty event skipped: year={season} tour={tour} city={city} event_id={event_id}"
                )
                continue

            all_parts.append(h2h_event)
            success_cnt += 1

            if (idx + 1) % 10 == 0:
                logger.info(
                    f"[H2H] Progress {idx + 1}/{total_events} | success={success_cnt} skipped={skipped_cnt} failed={len(failed_events)}"
                )

        except Exception as e:
            failed_events.append(
                {
                    "event_id": event_id,
                    "tour": tour,
                    "city": city,
                    "error": str(e),
                }
            )
            logger.exception(
                f"[H2H] Failed event: year={season} tour={tour} city={city} event_id={event_id}"
            )
            continue

    h2h_all = (
        pd.concat(all_parts, ignore_index=True)
        if all_parts
        else pd.DataFrame(columns=H2H_COLS)
    )

    logger.info(
        f"[H2H] Done season={year} | events={total_events} success={success_cnt} skipped={skipped_cnt} failed={len(failed_events)} rows={len(h2h_all)}"
    )

    return h2h_all, pd.DataFrame(failed_events)


def build_h2h_for_target_day(
    event_df: pd.DataFrame,
    city: str,
    tour: str,
    week_start_date,
    season: int,
    target_day: int,
) -> pd.DataFrame:
    """
    Build records only for one explicit target_day from one event_df.
    """
    if target_day < 1 or event_df.empty:
        return pd.DataFrame(columns=H2H_COLS)

    df = event_df.copy()
    df["n_players"] = df["players"].str.len()

    # only rows that have at least target_day picks
    df = df[df["n_players"] >= target_day].copy()
    if df.empty:
        return pd.DataFrame(columns=H2H_COLS)

    # player at target_day (1-based day)
    df["player"] = df["players"].str[target_day - 1]
    df = df[df["player"].astype(str).str.strip() != "轮空"].copy()
    if df.empty:
        return pd.DataFrame(columns=H2H_COLS)

    # result rule
    before_last = target_day < df["n_players"]
    at_last = target_day == df["n_players"]

    df["result"] = pd.Series(pd.NA, index=df.index, dtype="object")
    df.loc[before_last, "result"] = "W"
    df.loc[at_last & (df["status"] == 2), "result"] = "W"
    df.loc[at_last & (df["status"] == -2), "result"] = "L"

    # invalid last status dropped
    df = df.dropna(subset=["result"]).copy()
    if df.empty:
        return pd.DataFrame(columns=H2H_COLS)

    df["tournament"] = city
    df["tour"] = tour
    df["day"] = target_day
    df["season"] = season
    df["week_start_date"] = week_start_date

    return df[H2H_COLS].reset_index(drop=True)


def build_h2h_for_single_day(
    event_df: pd.DataFrame,
    city: str,
    tour: str,
    week_start_date,
    season: int,
    current_day: int,
) -> pd.DataFrame:
    """
    Compatibility helper: build rows for target_day = current_day - 1.
    """
    target_day = current_day - 1
    return build_h2h_for_target_day(
        event_df=event_df,
        city=city,
        tour=tour,
        week_start_date=week_start_date,
        season=season,
        target_day=target_day,
    )


def update_h2h_csv_for_partition(
    csv_path: str,
    event_df: pd.DataFrame,
    city: str,
    tour: str,
    week_start_date,
    season: int,
    target_day: int,
    save: bool = True,
) -> pd.DataFrame:
    """
    Replace partition (season, week_start_date, tournament, day=target_day)
    with newly computed rows, then save.
    """
    if target_day < 1:
        raise ValueError("target_day must be >= 1")

    new_rows = build_h2h_for_target_day(
        event_df=event_df,
        city=city,
        tour=tour,
        week_start_date=week_start_date,
        season=season,
        target_day=target_day,
    )

    if os.path.exists(csv_path):
        hist = pd.read_csv(csv_path)
    else:
        hist = pd.DataFrame(columns=H2H_COLS)

    for c in H2H_COLS:
        if c not in hist.columns:
            hist[c] = pd.Series(dtype="object")

    before_rows = len(hist)

    # remove old rows for same event/day partition
    mask = (
        (hist["season"] == season)
        & (hist["week_start_date"].astype(str) == str(week_start_date))
        & (hist["tour"] == tour)
        & (hist["tournament"] == city)
        & (hist["day"] == target_day)
    )
    partition_before = int(mask.sum())
    hist = hist.loc[~mask, H2H_COLS]

    updated = pd.concat([hist, new_rows], ignore_index=True)

    # safety dedup
    updated = updated.drop_duplicates(
        subset=[
            "user_id",
            "season",
            "week_start_date",
            "tour",
            "tournament",
            "day",
        ],
        keep="last",
    ).reset_index(drop=True)

    logger.info(
        "[H2H] Upsert partition season=%s tour=%s week=%s tournament=%s day=%s | removed=%s added=%s total_before=%s total_after=%s",
        season,
        tour,
        week_start_date,
        city,
        target_day,
        partition_before,
        len(new_rows),
        before_rows,
        len(updated),
    )

    if save:
        updated.to_csv(csv_path, index=False)

    return updated


def update_h2h_csv_for_new_day(
    csv_path: str,
    event_df: pd.DataFrame,
    city: str,
    tour: str,
    week_start_date,
    season: int,
    current_day: int,
    save: bool = True,
) -> pd.DataFrame:
    """
    Backward compatible wrapper.
    Replace partition (season, week_start_date, tournament, day=current_day-1),
    then save.
    """
    target_day = current_day - 1
    if target_day < 1:
        raise ValueError("current_day must be >= 2")
    return update_h2h_csv_for_partition(
        csv_path=csv_path,
        event_df=event_df,
        city=city,
        tour=tour,
        week_start_date=week_start_date,
        season=season,
        target_day=target_day,
        save=save,
    )


def _upsert_champion_rows(
    event_df: pd.DataFrame,
    city: str,
    tour: str,
    season: int,
    week_start_date: str,
    champions_path: str,
) -> None:
    """Write winner rows from event_df into champions.csv if not already recorded."""
    from champion_stats import extract_champion_rows, save_champions

    # Skip if this week is already in the file
    if Path(champions_path).exists():
        existing = pd.read_csv(champions_path, encoding="utf-8-sig")
        tour_label = "ATP" if tour.upper() == "MS" else "WTA"
        already = set(
            existing.loc[existing["tour"] == tour_label, "week"]
            .dropna()
            .astype(str)
            .str[:10]
        )
        if week_start_date[:10] in already:
            return

    winner_df = extract_champion_rows(
        event_df=event_df,
        city=city,
        tour_code=tour,
        season=season,
        week_start_date=week_start_date,
    )
    if winner_df.empty:
        logger.info("[Champion] No winners yet for %s %s, skipping.", tour, city)
        return

    save_champions(winner_df, file_path=champions_path)
    logger.info(
        "[Champion] Saved %d winner(s) for %s %s to %s",
        len(winner_df),
        tour,
        city,
        champions_path,
    )


def backfill_recent_h2h_partitions(
    csv_path: str,
    calendar_year: int,
    tour: str,
    reference_date,
    backfill_events: int = 1,
    max_events_per_tour: int = 2,
    champions_path: str | None = None,
) -> dict:
    """
    Recompute and upsert all completed day partitions for the most recent
    backfill_events events (sorted by week_start_date descending).
    """
    summary = {"attempted": 0, "succeeded": 0, "failed": 0}
    if backfill_events < 1 or max_events_per_tour < 1:
        return summary

    calendar_df, _ = fetch_survivor_calendar_event_df(calendar_year)
    if calendar_df is None or calendar_df.empty:
        return summary

    d0 = pd.to_datetime(reference_date).normalize()

    c = calendar_df.copy()
    c = c[c["tour"].astype(str).str.upper() == str(tour).upper()].copy()
    c["week_start_date"] = pd.to_datetime(c["week_start_date"], errors="coerce")
    c = c.dropna(subset=["week_start_date", "event_id"]).copy()
    if c.empty:
        return summary

    c = c[c["week_start_date"] <= d0].copy()
    c = c.sort_values("week_start_date", ascending=False).head(backfill_events)
    if c.empty:
        return summary

    for _, row in c.iterrows():
        event_id = row["event_id"]
        city = row["city"]
        week_start_date = row["week_start_date"]
        season = int(row["year"])
        try:
            event_df, _ = fetch_table(
                option="score",
                page_size=1000,
                event_id=event_id,
                year=season,
                tour=tour,
            )
            if event_df is None or event_df.empty:
                continue

            if (champions_path is not None) & (row["page_type"] == "score"):
                logger.info(f"Update champions info for {tour}{city}...")
                _upsert_champion_rows(
                    event_df=event_df,
                    city=city,
                    tour=tour,
                    season=season,
                    week_start_date=week_start_date.date().isoformat(),
                    champions_path=champions_path,
                )

            max_day = int(event_df["players"].str.len().max())
            for target_day in range(1, max_day + 1):
                summary["attempted"] += 1
                try:
                    update_h2h_csv_for_partition(
                        csv_path=csv_path,
                        event_df=event_df,
                        city=city,
                        tour=tour,
                        week_start_date=week_start_date.date().isoformat(),
                        season=season,
                        target_day=target_day,
                        save=True,
                    )
                    summary["succeeded"] += 1
                except Exception:
                    summary["failed"] += 1
                    logger.exception(
                        "[H2H] Backfill partition failed: season=%s tour=%s week=%s city=%s day=%s",
                        season,
                        tour,
                        week_start_date,
                        city,
                        target_day,
                    )
        except Exception:
            logger.exception(
                "[H2H] Backfill event fetch failed: season=%s tour=%s event_id=%s city=%s",
                season,
                tour,
                event_id,
                city,
            )

    return summary


def prepare_h2h_for_render(
    rank_df: pd.DataFrame | None = None,
    tour: str = "MS",
    csv_path: str = "../data/h2h_records.csv",
) -> pd.DataFrame:
    """
    Filter H2H records to one tour and enrich with rank/username from that tour's rank table.

    Parameters
    ----------
    h2h_df : pd.DataFrame
        Combined H2H records (all tours). tour column values: "MS" / "WS".
    rank_df : pd.DataFrame | None
        Ranking table for the target tour (MS or WS).
    tour : str
        Tour code to filter by: "MS" (ATP) or "WS" (WTA).

    Returns
    -------
    pd.DataFrame
        Tour-filtered H2H records with refreshed username and added "rank" column.
    """
    h2h_df = pd.read_csv(csv_path)
    if h2h_df.empty:
        return pd.DataFrame(columns=[*H2H_COLS, "rank"])

    out = h2h_df[h2h_df["tour"].astype(str).eq(tour)].copy()
    if out.empty:
        return pd.DataFrame(columns=[*H2H_COLS, "rank"])

    if "rank" not in out.columns:
        out["rank"] = pd.NA

    if rank_df is None or rank_df.empty:
        out = out.reset_index(drop=True)
        ordered_cols = [*H2H_COLS, "rank"]
        for c in out.columns:
            if c not in ordered_cols:
                ordered_cols.append(c)
        return out[ordered_cols]

    if "user_id" not in rank_df.columns or "username" not in rank_df.columns:
        out = out.reset_index(drop=True)
        ordered_cols = [*H2H_COLS, "rank"]
        for c in out.columns:
            if c not in ordered_cols:
                ordered_cols.append(c)
        return out[ordered_cols]

    def _pick_rank_col(df: pd.DataFrame) -> str | None:
        for c in ("current_rank", "rank", "当前排名"):
            if c in df.columns:
                return c
        return None

    rank_col = _pick_rank_col(rank_df)
    keep_cols = ["user_id", "username"] + ([rank_col] if rank_col else [])
    r = (
        rank_df[keep_cols]
        .dropna(subset=["user_id"])
        .drop_duplicates(subset=["user_id"], keep="first")
        .rename(
            columns={
                "username": "new_username",
                **({rank_col: "new_rank"} if rank_col else {}),
            }
        )
    )

    out = out.merge(r, on="user_id", how="left")

    need_update = (out["username"] != out["new_username"]) & out["new_username"].notna()
    out.loc[need_update, "username"] = out.loc[need_update, "new_username"]

    if "new_rank" in out.columns:
        out["rank"] = out["new_rank"].combine_first(out["rank"])

    out = out.drop(
        columns=[c for c in ["new_username", "new_rank"] if c in out.columns]
    )
    out = out.reset_index(drop=True)

    ordered_cols = [*H2H_COLS, "rank"]
    for c in out.columns:
        if c not in ordered_cols:
            ordered_cols.append(c)
    return out[ordered_cols]


def compute_killer_stats(df: pd.DataFrame):
    killer_df = (
        df.groupby(["player", "tournament", "season"])
        .agg(
            选择人数=("user_id", "size"),
            杀人人数=("result", lambda x: (x == "L").sum()),
        )
        .reset_index()
    )
    agg_df = killer_df.groupby("player", as_index=False).agg(
        选择人数=("选择人数", "sum"),
        带走人数=("杀人人数", "sum"),
        最高单次带走人数=("杀人人数", "max"),
    )
    agg_df["杀人率"] = (agg_df["带走人数"] / agg_df["选择人数"]).map(
        lambda x: f"{x:.2%}"
    )
    agg_df = agg_df.sort_values(
        by=["带走人数", "杀人率", "最高单次带走人数"], ascending=False
    ).reset_index(drop=True)
    agg_df["排名"] = agg_df.index + 1
    agg_df = agg_df.rename({"player": "球员"}, axis=1)

    return agg_df.loc[
        :, ["排名", "球员", "带走人数", "杀人率", "最高单次带走人数", "选择人数"]
    ]


def prepare_killer_stats(csv_path: str = "../data/h2h_records.csv", current_season: int = 2026):
    h2h_all = pd.read_csv(csv_path)
    atp_season = compute_killer_stats(
        h2h_all.loc[
            (h2h_all["tour"] == "MS") & (h2h_all["season"] == current_season), :
        ]
    )
    atp_all = compute_killer_stats(h2h_all.loc[h2h_all["tour"] == "MS", :])
    wta_season = compute_killer_stats(
        h2h_all.loc[
            (h2h_all["tour"] == "WS") & (h2h_all["season"] == current_season), :
        ]
    )
    wta_all = compute_killer_stats(h2h_all.loc[h2h_all["tour"] == "WS", :])

    return atp_season, atp_all, wta_season, wta_all


if __name__ == "__main__":
    season_parts = []
    failed_parts = []
    for y in SEASONS:
        h2h_all, failed = build_season_h2h(y)
        season_parts.append(h2h_all)
        failed_parts.append(failed)

    h2h_all = (
        pd.concat(season_parts, ignore_index=True)
        if season_parts
        else pd.DataFrame(columns=H2H_COLS)
    )
    h2h_all.to_csv("../data/h2h_records.csv", index=False)

    failed_all = (
        pd.concat(failed_parts, ignore_index=True)
        if failed_parts
        else pd.DataFrame(columns=["event_id", "tour", "city", "error"])
    )
    failed_all.to_csv("../data/h2h_failed_events.csv", index=False)

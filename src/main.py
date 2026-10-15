from build_table import build_ranking_table
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
import argparse
import json
import os

from h2h import (
    backfill_recent_h2h_partitions,
    build_season_h2h,
    prepare_killer_stats,
    prepare_h2h_for_render,
    update_h2h_csv_for_new_day,
)
from write_config import build_tour_config, ConfigManager, validate_event
from logger import get_logger
from output_format import (
    drop_today_status_column,
    generate_summary,
    hide_today_picks_for_eliminated,
    mark_unfinished_status,
    mark_unpicked_status,
    prepare_rank_change,
)
import pandas as pd
from parser import (
    fetch_survivor_calendar_event_df,
    fetch_event_detail,
    fetch_table,
    find_ongoing_event,
)

import time
import yaml

from survivor_html import (
    apply_theme,
    render_index,
    render_killer_page,
    render_ranking_page,
    render_h2h_page,
)
from champion_stats import render_champion_pages
from weather import build_weather_cards
from draw_status import fetch_draw_status
from live_settlement import settle_tour_scores, summarize_backup_events
from player_stats import update_player_stats_pages
from combined_ranking import update_combined_pages
from event_calendar import update_survivor_calendar_pages
from home_weeks import load_calendar_json, prepare_home_weeks
from day_killers import daily_killer_stats

logger = get_logger(__name__)

GRAND_SLAMS = {"澳网", "法网", "温网", "美网"}


CONFIG_PATH = "../config.yaml"
# YEAR = cfg["year"]
# datetime_format = cfg["datetime_format"]

COL_ZH_DICT = {
    "username": "用户名",
    "current_rank": "当前排名",
    "current_score": "当前积分",
    "score": "本站得分",
    "players": "选人明细",
    "player": "今日主选",
    "player_alt": "今日备选",
    "status": "昨日选人",
    "fill_status": "当前状态",
    "removed_point": "扣除积分",
    "live_score": "即时积分",
    "live_rank": "即时排名",
    "rank_change": "排名变化",
    "today_status": "今日状态",
    "day": "存活天数",
    "killer": "杀手球员",
    "count": "人数",
    "possible_selection": "剩余可选",
}


def _venue_key(venue_cfg):
    lat, lon = venue_cfg.get("latitude"), venue_cfg.get("longitude")
    if lat is None or lon is None:
        return None
    # round to avoid tiny float differences
    return (round(float(lat), 4), round(float(lon), 4))


def fetch_all_tables(event: Union[int, str], tour: str):
    logger.info(f"Update at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    t = time.time()
    r, rank_records = fetch_table(option="rank", tour=tour)
    logger.info(f"Parsed {rank_records} rank records in {time.time() - t:.1f}s...")
    t2 = time.time()
    race, race_records = fetch_table(option="race", tour=tour)
    logger.info(f"Parsed {race_records} race records in {time.time() - t2:.1f}s...")
    try:
        ts = time.time()
        s, submission_records = fetch_table(
            option="submission", tour=tour, event_id=event, year=YEAR
        )
        s = s if not s.empty else None
        logger.info(
            f"Parsed {submission_records} submissions in {time.time() - ts:.1f}s..."
        )
    except RuntimeError:
        raise
    except KeyError:
        s = None
        logger.info("Submission table not available.")
    try:
        t1 = time.time()
        score_table, score_records = fetch_table(
            option="score", tour=tour, event_id=event, year=YEAR
        )
        score_table = score_table if not score_table.empty else None
        logger.info(
            f"Parsed {score_records} score records in {time.time() - t1:.1f}s..."
        )
    except RuntimeError:
        raise
    except KeyError:
        score_table = None
        logger.info("Score table not available.")
    return r, s, score_table, race


def infer_day(submission_df, score_df) -> int:
    if submission_df is None:
        return 0
    if score_df is None:
        return 1
    return int(score_df["day"].max()) + 1


def get_meta_stats(day, table, submissions):
    if day > 1:
        total = len(table[table["当前状态"] != "未参赛"])
        today = len(table[table["当前状态"] == "存活"])
    elif day == 1:
        # Count unique Day1 participants, not raw submission rows
        if submissions is None or getattr(submissions, "empty", True):
            total = 0
        elif "day" in submissions.columns:
            day1 = submissions[pd.to_numeric(submissions["day"], errors="coerce") == 1]
            total = int(day1["user_id"].nunique()) if not day1.empty else 0
        else:
            total = int(submissions["user_id"].nunique())
        # Day1 homepage metric should show bye users instead of alive users
        today = int((table["今日状态"] == "轮空").sum()) if "今日状态" in table.columns else 0
    else:
        total, today = None, None

    return total, today


def build_tour_tables(tour_cfg, tour_code, tour_label):
    """Fetch and build ranking + race tables for one tour.

    Returns
    -------
    table, race, raw_rank, submissions, score_df, day, live_players, raw_race,
    pending_uids, backup_events
    """
    if tour_cfg.get("event") is None:
        logger.info(f"{tour_label} — no tournament this week, skipping fetch")
        r, _ = fetch_table(option="rank", tour=tour_code)
        ra, _ = fetch_table(option="race", tour=tour_code)
        day = 0
        table = build_ranking_table(
            rank_df=r,
            submission_df=None,
            score_df=None,
            day=day,
            bye_rate=tour_cfg["bye_rate"],
            new_tournament_name=tour_cfg.get("name", ""),
            removed_tournament_name=tour_cfg.get("removed_tournament_name"),
            tour=tour_label,
        ).rename(COL_ZH_DICT, axis=1)
        race = (
            build_ranking_table(
                rank_df=ra,
                submission_df=None,
                score_df=None,
                day=day,
                bye_rate=tour_cfg["bye_rate"],
                new_tournament_name=tour_cfg.get("name", ""),
                tour=tour_label,
            )
            .drop("removed_point", axis=1)
            .rename(COL_ZH_DICT, axis=1)
        )
        return table, race, r, None, None, day, [], ra, set(), []

    r, s, re, ra = fetch_all_tables(tour_cfg["event"], tour=tour_code)
    day = infer_day(s, re)
    use_settled = False
    bye_users: set[str] = set()
    live_players: list[str] = []
    pending_uids: set[str] = set()
    backup_events: list = []

    settlement_cfg = (cfg or {}).get("settlement") or {}
    if settlement_cfg.get("enabled", True) and s is not None:
        try:
            draw = fetch_draw_status(
                tour_cfg["event"],
                YEAR,
                tour_code,
                is_slam=tour_cfg.get("name") in GRAND_SLAMS,
            )
            live_players = [
                p.name
                for p in draw.by_id.values()
                if p.live and not p.eliminated and str(p.name or "").strip()
            ]
            re, counts, bye_users, play_day, pending_uids, backup_events = (
                settle_tour_scores(re, s, draw, rank_df=r)
            )
            if play_day > 0:
                day = play_day
            # Day1 must keep the bye-rate table path for 轮空/非轮空 summary.
            # Settled score path is only used from Day2 onward.
            use_settled = (
                re is not None and not re.empty and int(day) > 1
            )
            if any(counts.values()) or bye_users:
                logger.info(
                    f"{tour_label}{tour_cfg['name']}站 实时结算 "
                    f"胜{counts['win']}/负{counts['loss']}/"
                    f"轮空{counts['bye']}/自杀{counts['suicide']}/"
                    f"待定{counts['pending']} "
                    f"bye_users={len(bye_users)} → Day{day}"
                    + ("" if use_settled else " (Day1 用轮空建表)")
                )
        except Exception:
            logger.exception(
                f"{tour_label} live settlement failed; falling back to official scores"
            )
            use_settled = False
            bye_users = set()
            pending_uids = set()
            backup_events = []
            day = infer_day(s, re)

    logger.info(
        f"{tour_label}{tour_cfg['name']}站Day{day}"
        + (" (settled)" if use_settled else " (auto-inferred)")
    )
    table = build_ranking_table(
        rank_df=r,
        submission_df=s,
        score_df=re,
        day=day,
        bye_rate=tour_cfg["bye_rate"],
        new_tournament_name=tour_cfg["name"],
        removed_tournament_name=tour_cfg.get("removed_tournament_name"),
        tour=tour_label,
        use_settled_score=use_settled,
        bye_user_ids=bye_users if day == 1 else None,
    ).rename(COL_ZH_DICT, axis=1)
    race = (
        build_ranking_table(
            rank_df=ra,
            submission_df=s,
            score_df=re,
            day=day,
            bye_rate=tour_cfg["bye_rate"],
            new_tournament_name=tour_cfg["name"],
            tour=tour_label,
            use_settled_score=use_settled,
            bye_user_ids=bye_users if day == 1 else None,
        )
        .drop("removed_point", axis=1)
        .rename(COL_ZH_DICT, axis=1)
    )
    if day == 1 and "今日状态" in table.columns:
        if "今日状态" in race.columns:
            race = race.drop("今日状态", axis=1)
        race = race.merge(
            table.loc[:, ["user_id", "今日状态"]], how="left", on="user_id"
        )
    # prepare_rank_change drops user_id; expose pending picks by player name so
    # mark_unfinished_status can still flip 存活 → 未完赛 after that trim.
    if pending_uids and "今日主选" in table.columns and "user_id" in table.columns:
        uid_keys = table["user_id"].map(
            lambda v: (
                ""
                if v is None or (isinstance(v, float) and pd.isna(v))
                else str(v).strip()[:-2]
                if str(v).strip().endswith(".0")
                else str(v).strip()
            )
        )
        pending_picks = {
            str(p).strip()
            for p in table.loc[uid_keys.isin(pending_uids), "今日主选"].tolist()
            if p is not None and str(p).strip()
        }
        live_players = list(
            dict.fromkeys(
                [*(live_players or []), *sorted(pending_picks)]
            )
        )
    return table, race, r, s, re, day, live_players, ra, pending_uids, backup_events


def _log_submissions_for_users(submissions_df, day, user_ids):
    if submissions_df is None:
        return
    for _, row in (
        submissions_df.loc[
            submissions_df["user_id"].isin(user_ids) & (submissions_df["day"] == day),
            ["username", "player", "player_alt"],
        ]
        .rename(COL_ZH_DICT, axis=1)
        .iterrows()
    ):
        logger.info(row.to_dict())


def prepare_weather(cfg, atp_cfg, wta_cfg, atp_name, wta_name, output_dir):
    """Build weather cards for all venues, with JSON cache fallback. Returns list of (label, cards_html)."""
    wx_cfg = cfg["weather"]
    weather_cache_path = (
        wx_cfg.get("cache_path") or f"{output_dir}/weather_cards_cache.json"
    )
    try:
        with open(weather_cache_path, encoding="utf-8") as f:
            weather_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        weather_cache = {}

    new_weather_cache = dict(weather_cache)
    grouped_venues = {}
    for label, venue_cfg in (
        (f"ATP · {atp_name}", atp_cfg),
        (f"WTA · {wta_name}", wta_cfg),
    ):
        venue_key = _venue_key(venue_cfg)
        if venue_key is None:
            continue
        grouped = grouped_venues.setdefault(venue_key, {"labels": [], "cfg": venue_cfg})
        grouped["labels"].append(label)

    weather = []
    for venue_key, grouped in grouped_venues.items():
        venue_cfg = grouped["cfg"]
        merged_label = " / ".join(grouped["labels"])
        cache_key = f"{venue_key[0]:.4f},{venue_key[1]:.4f}"
        cards = build_weather_cards(
            venue_cfg["latitude"],
            venue_cfg["longitude"],
            wx_cfg["hours"],
            wx_cfg["step"],
            wx_cfg["wind_speed_unit"],
        )
        if cards and "天气数据暂不可用" not in cards:
            weather.append((merged_label, cards))
            new_weather_cache[cache_key] = cards
        else:
            weather.append((merged_label, weather_cache.get(cache_key, cards)))

    if new_weather_cache != weather_cache:
        cache_dir = os.path.dirname(weather_cache_path)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        with open(weather_cache_path, "w", encoding="utf-8") as f:
            json.dump(new_weather_cache, f, ensure_ascii=False)

    return weather


def update_killer_pages():
    atp_killer, atp_killer_all, wta_killer, wta_killer_all = prepare_killer_stats(
        current_season=YEAR
    )

    render_killer_page(
        wta_killer,
        "WTA",
        "WTA · 2026 Season",
        updated=datetime.now().strftime(datetime_format),
        extra_tags=["2026"],
        output_path="../2026wtakiller.html",
    )

    logger.info("2026 WTA killers updated")

    render_killer_page(
        atp_killer,
        "ATP",
        "ATP · 2026 Season",
        updated=datetime.now().strftime(datetime_format),
        extra_tags=["2026"],
        output_path="../2026atpkiller.html",
    )

    logger.info("2026 ATP killers updated")

    render_killer_page(
        wta_killer_all,
        "WTA",
        "WTA · All Time",
        updated=datetime.now().strftime(datetime_format),
        extra_tags=["历年总榜"],
        output_path="../wtakiller.html",
    )

    logger.info("History WTA killers updated")

    render_killer_page(
        atp_killer_all,
        "ATP",
        "ATP · All Time",
        updated=datetime.now().strftime(datetime_format),
        extra_tags=["历年总榜"],
        output_path="../atpkiller.html",
    )
    logger.info("History ATP killers updated")


def update_rank_pages(
    atp_table: pd.DataFrame,
    wta_table: pd.DataFrame,
    atp_race: pd.DataFrame,
    wta_race: pd.DataFrame,
    atp_day1: bool = False,
    wta_day1: bool = False,
    atp_bye: bool = False,
    wta_bye: bool = False,
    atp_players: list = None,
    wta_players: list = None,
    atp_live_players: list = None,
    wta_live_players: list = None,
    atp_pending_uids: set = None,
    wta_pending_uids: set = None,
    atp_rank_raw: pd.DataFrame = None,
    wta_rank_raw: pd.DataFrame = None,
    atp_race_raw: pd.DataFrame = None,
    wta_race_raw: pd.DataFrame = None,
    atp_backup_events: list = None,
    wta_backup_events: list = None,
):
    # Mark 未完赛/未选 first (keep today's picks for losers so summary counts them),
    # then hide picks only on the rendered table.
    atp_base = mark_unpicked_status(
        mark_unfinished_status(
            atp_table,
            atp_live_players,
            atp_pending_uids,
        )
    )
    atp = prepare_rank_change(atp_base)
    atp_stats = generate_summary(atp, atp_day1, atp_bye)
    atp_killers = daily_killer_stats(atp)
    atp_backup = summarize_backup_events(atp_backup_events)
    atp_view = drop_today_status_column(hide_today_picks_for_eliminated(atp))
    atp_race_view = drop_today_status_column(
        hide_today_picks_for_eliminated(
            prepare_rank_change(
                mark_unpicked_status(
                    mark_unfinished_status(
                        atp_race,
                        atp_live_players,
                        atp_pending_uids,
                    )
                )
            )
        )
    )
    render_ranking_page(
        atp_view,
        "即时排名",
        "ATP",
        "ATP · Live Ranking",
        datetime.now().strftime(datetime_format),
        summary_df=atp_stats,
        killer_df=atp_killers,
        available_players=atp_players,
        live_players=atp_live_players,
        backup_events=atp_backup,
        output_path="../atp_ranking.html",
    )
    render_ranking_page(
        atp_race_view,
        "即时冠军排名",
        "ATP",
        "ATP · Race to Turin",
        datetime.now().strftime(datetime_format),
        summary_df=atp_stats,
        killer_df=atp_killers,
        extra_tags=["2026"],
        available_players=atp_players,
        live_players=atp_live_players,
        backup_events=atp_backup,
        output_path="../atp_race_ranking.html",
    )

    wta_base = mark_unpicked_status(
        mark_unfinished_status(
            wta_table,
            wta_live_players,
            wta_pending_uids,
        )
    )
    wta = prepare_rank_change(wta_base)
    wta_stats = generate_summary(wta, wta_day1, wta_bye)
    wta_killers = daily_killer_stats(wta)
    wta_backup = summarize_backup_events(wta_backup_events)
    wta_view = drop_today_status_column(hide_today_picks_for_eliminated(wta))
    wta_race_view = drop_today_status_column(
        hide_today_picks_for_eliminated(
            prepare_rank_change(
                mark_unpicked_status(
                    mark_unfinished_status(
                        wta_race,
                        wta_live_players,
                        wta_pending_uids,
                    )
                )
            )
        )
    )
    render_ranking_page(
        wta_view,
        "即时排名",
        "WTA",
        "WTA · Live Ranking",
        datetime.now().strftime(datetime_format),
        summary_df=wta_stats,
        killer_df=wta_killers,
        available_players=wta_players,
        live_players=wta_live_players,
        backup_events=wta_backup,
        output_path="../wta_ranking.html",
    )
    render_ranking_page(
        wta_race_view,
        "即时冠军排名",
        "WTA",
        "WTA · Race to Indian Wells",
        datetime.now().strftime(datetime_format),
        summary_df=wta_stats,
        killer_df=wta_killers,
        extra_tags=["2026"],
        available_players=wta_players,
        live_players=wta_live_players,
        backup_events=wta_backup,
        output_path="../wta_race_ranking.html",
    )

    # Combined ATP+WTA boards (chen-compatible filenames)
    try:
        atp_cfg_local = (cfg or {}).get("atp") or {}
        wta_cfg_local = (cfg or {}).get("wta") or {}
        update_combined_pages(
            mark_unpicked_status(
                mark_unfinished_status(
                    atp_table, atp_live_players, atp_pending_uids
                )
            ),
            mark_unpicked_status(
                mark_unfinished_status(
                    wta_table, wta_live_players, wta_pending_uids
                )
            ),
            mark_unpicked_status(
                mark_unfinished_status(
                    atp_race, atp_live_players, atp_pending_uids
                )
            ),
            mark_unpicked_status(
                mark_unfinished_status(
                    wta_race, wta_live_players, wta_pending_uids
                )
            ),
            atp_event=atp_cfg_local.get("name"),
            wta_event=wta_cfg_local.get("name"),
            atp_removed=atp_cfg_local.get("removed_tournament_name"),
            wta_removed=wta_cfg_local.get("removed_tournament_name"),
            year=(cfg or {}).get("year"),
            updated=datetime.now().strftime(datetime_format),
            output_dir="..",
            atp_rank_raw=atp_rank_raw,
            wta_rank_raw=wta_rank_raw,
            atp_race_raw=atp_race_raw,
            wta_race_raw=wta_race_raw,
        )
    except Exception:
        logger.exception("Failed to build combined rankings")


def update_h2h_pages(atp_rank, wta_rank):
    atp_h2h = prepare_h2h_for_render(atp_rank, tour="MS")
    wta_h2h = prepare_h2h_for_render(wta_rank, tour="WS")

    render_h2h_page(
        atp_h2h,
        datetime.now().strftime(datetime_format),
        "ATP",
        "ATP · All Time",
        output_path="../h2h_atp.html",
    )
    logger.info("ATP H2H updated.")

    render_h2h_page(
        wta_h2h,
        datetime.now().strftime(datetime_format),
        "WTA",
        "wta · All Time",
        output_path="../h2h_wta.html",
    )
    logger.info("WTA H2H updated.")


def update_h2h_and_killers(
    h2h_cfg, atp_cfg, wta_cfg, atp_re, wta_re, atp_day, wta_day, atp_r, wta_r
):
    backfill_enabled = h2h_cfg.get("backfill_enabled", True)
    backfill_events = int(h2h_cfg.get("backfill_events", 1))
    max_events_per_tour = int(h2h_cfg.get("max_events_per_tour", 2))

    atp_incremental_ok = False
    try:
        update_h2h_csv_for_new_day(
            csv_path=h2h_cfg["csv_path"],
            event_df=atp_re,
            city=atp_cfg["name"],
            tour="MS",
            week_start_date=atp_cfg["week_start_date"],
            season=YEAR,
            current_day=atp_day,
        )
        atp_incremental_ok = True
    except ValueError as err:
        logger.warning(err)
    except Exception:
        logger.exception("[H2H] ATP incremental update failed.")

    wta_incremental_ok = False
    try:
        update_h2h_csv_for_new_day(
            csv_path=h2h_cfg["csv_path"],
            event_df=wta_re,
            city=wta_cfg["name"],
            tour="WS",
            week_start_date=wta_cfg["week_start_date"],
            season=YEAR,
            current_day=wta_day,
        )
        wta_incremental_ok = True
    except ValueError as err:
        logger.warning(err)
    except Exception:
        logger.exception("[H2H] WTA incremental update failed.")

    champions_path = cfg.get("champions_path", "../data/champions.csv")

    if backfill_enabled:
        atp_backfill = backfill_recent_h2h_partitions(
            csv_path=h2h_cfg["csv_path"],
            calendar_year=YEAR,
            tour="MS",
            reference_date=datetime.now().date(),
            backfill_events=backfill_events,
            max_events_per_tour=max_events_per_tour,
            champions_path=champions_path,
        )
        logger.info(
            "[H2H] ATP backfill summary: attempted=%s succeeded=%s failed=%s",
            atp_backfill["attempted"],
            atp_backfill["succeeded"],
            atp_backfill["failed"],
        )
        if atp_day == 1 and (not atp_incremental_ok) and atp_backfill["attempted"] == 0:
            logger.warning(
                "[H2H] ATP day=1 and no eligible previous partition discovered for backfill."
            )

        wta_backfill = backfill_recent_h2h_partitions(
            csv_path=h2h_cfg["csv_path"],
            calendar_year=YEAR,
            tour="WS",
            reference_date=datetime.now().date(),
            backfill_events=backfill_events,
            max_events_per_tour=max_events_per_tour,
            champions_path=champions_path,
        )
        logger.info(
            "[H2H] WTA backfill summary: attempted=%s succeeded=%s failed=%s",
            wta_backfill["attempted"],
            wta_backfill["succeeded"],
            wta_backfill["failed"],
        )
        if wta_day == 1 and (not wta_incremental_ok) and wta_backfill["attempted"] == 0:
            logger.warning(
                "[H2H] WTA day=1 and no eligible previous partition discovered for backfill."
            )

    full_rebuild_hour = h2h_cfg.get("full_rebuild_hour")
    if full_rebuild_hour is not None and datetime.now().hour == int(full_rebuild_hour):
        try:
            season_parts, failed_parts = [], []
            for y in range(2024, YEAR + 1):
                season_df, season_failed = build_season_h2h(y)
                season_parts.append(season_df)
                failed_parts.append(season_failed)
            full_h2h = (
                pd.concat(season_parts, ignore_index=True)
                if season_parts
                else pd.DataFrame()
            )
            failed = (
                pd.concat(failed_parts, ignore_index=True)
                if failed_parts
                else pd.DataFrame()
            )
            tmp_path = f'{h2h_cfg["csv_path"]}.tmp'
            full_h2h.to_csv(tmp_path, index=False)
            os.replace(tmp_path, h2h_cfg["csv_path"])
            logger.info(
                "[H2H] Full rebuild completed for seasons=2024-%s, rows=%s, failed_events=%s",
                YEAR,
                len(full_h2h),
                len(failed),
            )
        except Exception:
            logger.exception("[H2H] Full rebuild failed.")

    render_champion_pages(
        champions_path=champions_path, datetime_format=cfg["datetime_format"]
    )

    logger.info("Update killer page...")
    update_killer_pages()

    update_h2h_pages(atp_r, wta_r)


def refresh_event_config():
    CURRENT_YEAR = datetime.today().year
    calendar, _ = fetch_survivor_calendar_event_df(CURRENT_YEAR)
    calendar_en, _ = fetch_survivor_calendar_event_df(CURRENT_YEAR, language="en")
    new_calendar = calendar.merge(
        calendar_en[["event_id", "event_tour", "city"]],
        how="left",
        on=["event_id", "event_tour"],
        suffixes=("", "_en"),
    )
    config_file = ConfigManager("test.yaml")
    config_file.update({"year": CURRENT_YEAR})
    for tour in [("atp", "ms"), ("wta", "ws")]:
        event = find_ongoing_event(new_calendar, tour[1])
        rank, _ = fetch_table(option="rank", tour=tour[1])
        valid_flag = validate_event(event)
        event_config = build_tour_config(
            event,
            config_file,
            tour_label=tour[0],
            valid_flag=valid_flag,
            last_yr_calendar_path="../data/calendar_2025.json",
            ranking_monday=pd.Timestamp(rank["monday"].iloc[0]),
        )
        logger.info(f"Update {tour[0]} event: {event_config['name']}")


def _load_cfg():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_player_stats(refresh: bool = True):
    """Generate atp_show.html / wta_show.html (independent of live ranking)."""
    global cfg, YEAR, datetime_format
    cfg = _load_cfg()
    YEAR = cfg["year"]
    datetime_format = cfg["datetime_format"]
    apply_theme(cfg["theme"])
    stats_cfg = cfg.get("player_stats") or {}
    if not stats_cfg.get("enabled", True):
        logger.info("player_stats disabled in config; skip")
        return []
    atp_cfg = cfg.get("atp") or {}
    wta_cfg = cfg.get("wta") or {}
    return update_player_stats_pages(
        output_dir=cfg["output_dir"],
        refresh=refresh,
        atp_event={
            "name": atp_cfg.get("name"),
            "year": str(YEAR),
            "id": atp_cfg.get("event"),
        },
        wta_event={
            "name": wta_cfg.get("name"),
            "year": str(YEAR),
            "id": wta_cfg.get("event"),
        },
        updated=datetime.now().strftime(datetime_format),
    )


def run_calendar_browser(refresh: bool = True, years: Optional[list] = None):
    """Generate survivor_calendar.html + events/*/score pages."""
    global cfg, YEAR, datetime_format
    cfg = _load_cfg()
    YEAR = cfg["year"]
    datetime_format = cfg["datetime_format"]
    apply_theme(cfg["theme"])
    cal_cfg = cfg.get("calendar_browser") or {}
    if not cal_cfg.get("enabled", True):
        logger.info("calendar_browser disabled in config; skip")
        return {}
    year_from = int(cal_cfg.get("years_from") or 2020)
    year_to = cal_cfg.get("years_to")
    year_to = int(year_to) if year_to is not None else int(YEAR)
    # --calendar-year limits what we fetch; calendar page still spans years_from..year_to
    return update_survivor_calendar_pages(
        years=years,
        year_from=year_from,
        year_to=year_to,
        output_dir=cfg["output_dir"],
        calendar_dir=Path(cfg.get("output_dir") or "..") / "data",
        cache_dir=Path(cfg.get("output_dir") or "..") / "data" / "event_scores",
        refresh=refresh,
        refresh_calendar=refresh,
        updated=datetime.now().strftime(datetime_format),
    )


def main(*, mode: str = "default"):
    """Generate site pages.

    mode:
      default — local run; H2H/killers gated by ``h2h.update_hour``
      live — pick-related pages (rankings / index / combined / current-year calendar)
      daily — live pages plus H2H, killers, career stats, full calendar
    """
    if mode not in {"default", "live", "daily"}:
        raise ValueError(f"unsupported mode: {mode}")

    try:
        refresh_event_config()
    except Exception as err:
        # CI / offline: keep going with committed config.yaml (live & daily).
        logger.exception(f"Failed to refresh event configuration: {err}")
        if mode == "default":
            raise
        logger.warning("Continuing with existing config.yaml (mode=%s)", mode)
    global cfg
    cfg = _load_cfg()
    global YEAR
    global datetime_format
    YEAR = cfg["year"]
    datetime_format = cfg["datetime_format"]
    apply_theme(cfg["theme"])

    atp_cfg = cfg["atp"]
    wta_cfg = cfg["wta"]
    h2h_cfg = cfg["h2h"]
    debug_cfg = cfg["debug"]
    output_dir = cfg["output_dir"]
    stats_cfg = cfg.get("player_stats") or {}

    # Fetch and build tables
    (
        atp_table,
        atp_race,
        atp_r,
        atp_s,
        atp_re,
        atp_day,
        atp_live,
        atp_ra,
        atp_pending,
        atp_backup_events,
    ) = build_tour_tables(atp_cfg, "MS", "ATP")
    (
        wta_table,
        wta_race,
        wta_r,
        wta_s,
        wta_re,
        wta_day,
        wta_live,
        wta_ra,
        wta_pending,
        wta_backup_events,
    ) = build_tour_tables(wta_cfg, "WS", "WTA")
    # Event detail: players, dates, rounds/scores for current day
    atp_players = []
    wta_players = []

    # Always keep remaining (selectable) players for summary coloring + route query
    if atp_cfg.get("event") is not None:
        atp_details = fetch_event_detail(atp_cfg["event"], YEAR, "MS")
        atp_players = [p["name"] for p in atp_details["players"]]

    if wta_cfg.get("event") is not None:
        wta_details = fetch_event_detail(wta_cfg["event"], YEAR, "WS")
        wta_players = [p["name"] for p in wta_details["players"]]

    players_output = {
        "updated": datetime.now().strftime(datetime_format),
        "ATP": atp_players,
        "WTA": wta_players,
        "ATP_live": atp_live,
        "WTA_live": wta_live,
    }
    players_path = f"{output_dir}/data/players.json"
    os.makedirs(f"{output_dir}/data", exist_ok=True)
    with open(players_path, "w", encoding="utf-8") as f:
        json.dump(players_output, f, ensure_ascii=False, indent=2)
    logger.info("Players JSON written to %s", players_path)

    atp_total, atp_today = get_meta_stats(atp_day, atp_table, atp_s)
    wta_total, wta_today = get_meta_stats(wta_day, wta_table, wta_s)

    weather = prepare_weather(
        cfg, atp_cfg, wta_cfg, atp_cfg["name"], wta_cfg["name"], output_dir
    )

    home_cfg = cfg.get("home") or {}
    week_data = None
    if home_cfg.get("week_cards", True):
        try:
            this_cal, _ = fetch_survivor_calendar_event_df(YEAR)
            last_cal_path = home_cfg.get(
                "last_calendar_path", f"{output_dir}/data/calendar_{YEAR - 1}.json"
            )
            last_cal = load_calendar_json(last_cal_path)
            if last_cal.empty:
                # Fallback: fetch previous season calendar live
                last_cal, _ = fetch_survivor_calendar_event_df(YEAR - 1)
            champs_path = cfg.get("champions_path", f"{output_dir}/data/champions.csv")
            champions = (
                pd.read_csv(champs_path)
                if os.path.exists(champs_path)
                else pd.DataFrame()
            )
            week_data = prepare_home_weeks(
                this_cal,
                last_cal,
                champions,
                atp_live={
                    "city": atp_cfg.get("name"),
                    "participants": atp_total,
                    "survivors": atp_today,
                },
                wta_live={
                    "city": wta_cfg.get("name"),
                    "participants": wta_total,
                    "survivors": wta_today,
                },
            )
        except Exception:
            logger.exception("Homepage week cards failed; continuing without them")
            week_data = None

    # Index: CI live/daily always refresh; local keeps the lighter gate unless week cards on.
    index_output = debug_cfg.get("index_output_path") or f"{output_dir}/index.html"
    should_render_index = mode in {"live", "daily"} or bool(week_data is not None) or (
        (datetime.now().minute <= 30)
        or (datetime.now().hour == h2h_cfg["update_hour"])
        or (wta_day == 1)
        or (atp_day == 1)
    )
    if should_render_index:
        render_index(
            stats={
                "atp_total": atp_total,
                "atp_today": atp_today,
                "wta_total": wta_total,
                "wta_today": wta_today,
                "atp_name": f"{atp_cfg['name']}",
                "wta_name": f"{wta_cfg['name']}",
                "atp_day": atp_day,
                "wta_day": wta_day,
            },
            version=cfg["version"],
            weather=weather,
            weather_label=cfg["weather"]["label"],
            week_data=week_data,
            output_path=index_output,
        )
        logger.info("Index page updated")

    # Score / day-round caches must exist before combined breakdown (赛事清单轮次).
    if mode in {"live", "daily"}:
        try:
            run_calendar_browser(
                refresh=True,
                years=[int(YEAR)] if mode == "live" else None,
            )
        except Exception:
            logger.exception(
                "%s calendar sync failed; rankings may lack round labels", mode
            )

    update_rank_pages(
        atp_table,
        wta_table,
        atp_race,
        wta_race,
        atp_day1=(atp_day == 1),
        wta_day1=(wta_day == 1),
        atp_bye=(atp_cfg["bye_rate"] != 0),
        wta_bye=(wta_cfg["bye_rate"] != 0),
        atp_players=atp_players,
        wta_players=wta_players,
        atp_live_players=atp_live,
        wta_live_players=wta_live,
        atp_pending_uids=atp_pending,
        wta_pending_uids=wta_pending,
        atp_rank_raw=atp_r,
        wta_rank_raw=wta_r,
        atp_race_raw=atp_ra,
        wta_race_raw=wta_ra,
        atp_backup_events=atp_backup_events,
        wta_backup_events=wta_backup_events,
    )

    if mode == "live":
        return

    # H2H + killer + champion pages
    if mode == "daily" or datetime.now().hour == h2h_cfg["update_hour"]:
        update_h2h_and_killers(
            h2h_cfg, atp_cfg, wta_cfg, atp_re, wta_re, atp_day, wta_day, atp_r, wta_r
        )

    if mode == "daily":
        run_player_stats(refresh=True)
        return

    # Player career stats (optional weekday hook; prefer `python main.py --stats`)
    weekday = stats_cfg.get("update_weekday")
    if (
        stats_cfg.get("enabled", True)
        and weekday is not None
        and datetime.now().weekday() == int(weekday)
        and datetime.now().hour == h2h_cfg["update_hour"]
    ):
        run_player_stats(refresh=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="签表幸存者数据中心")
    parser.add_argument(
        "--live",
        action="store_true",
        help="只更新与选人相关的页面（排名/首页/联合榜/当年赛历得分）",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="每日全量：live + H2H/杀手/生涯统计/全部赛历",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="只更新球员生涯统计页（atp_show / wta_show，增量缓存）",
    )
    parser.add_argument(
        "--stats-cache-only",
        action="store_true",
        help="用本地 player_events.json 生成生涯统计页，不抓网",
    )
    parser.add_argument(
        "--calendar",
        action="store_true",
        help="更新幸存者赛历与各站得分明细页（增量缓存）",
    )
    parser.add_argument(
        "--calendar-cache-only",
        action="store_true",
        help="只用本地 event_scores 缓存生成赛历页，不抓网",
    )
    parser.add_argument(
        "--calendar-year",
        type=int,
        action="append",
        default=None,
        help="只处理指定年份（可多次传入），默认 config years_from..year",
    )
    args = parser.parse_args()
    if args.live and args.daily:
        parser.error("--live and --daily are mutually exclusive")
    if args.stats or args.stats_cache_only:
        run_player_stats(refresh=not args.stats_cache_only)
    elif args.calendar or args.calendar_cache_only:
        run_calendar_browser(
            refresh=not args.calendar_cache_only,
            years=args.calendar_year,
        )
    elif args.live:
        main(mode="live")
    elif args.daily:
        main(mode="daily")
    else:
        main(mode="default")

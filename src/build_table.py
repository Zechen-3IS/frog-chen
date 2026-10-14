import math

import pandas as pd
from typing import Optional, Union, List, Set

from live_ranking import compute_live_ranking, remove_current_tournament
from logger import get_logger
from points_calculation import parse_events, calculate_points
from submission_stats import get_today_status

logger = get_logger(__name__)


def _uid_key(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        try:
            float(text)
            return text[:-2]
        except ValueError:
            return text
    return text

OUTPUT_COLUMNS = [
    "user_id",
    "current_rank",
    "current_score",
    "username",
    "score",
    "players",
    "status",
    "fill_status",
    "player",
    "player_alt",
    "removed_point",
    "live_score",
    "live_rank",
    "today_status",
    "day",
    "killer",
]
# Rendered as whole numbers (no trailing .0) in HTML tables.
INT_OUTPUT_COLS = [
    "current_rank",
    "current_score",
    "score",
    "removed_point",
    "live_score",
    "live_rank",
    "day",
    "rank_change",
]
GRAND_SLAMS = {"澳网", "法网", "温网", "美网"}


def _as_nullable_int(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in INT_OUTPUT_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    return out


def build_ranking_table(
    rank_df: pd.DataFrame,
    submission_df: Optional[pd.DataFrame],
    score_df: Optional[pd.DataFrame],
    day: int,
    bye_rate: float = 0.0,
    new_tournament_name: Optional[str] = None,
    removed_tournament_name: Optional[Union[str, List[str]]] = None,
    tour: str = "WTA",
    *,
    use_settled_score: bool = False,
    bye_user_ids: Optional[Set[str]] = None,
) -> pd.DataFrame:
    # Day1 always uses the bye / 非轮空 summary path. Settled scores are only
    # wired into the non-day1 builder from Day2 onward.
    if day == 1 and not use_settled_score:
        return _build_day1(
            rank_df,
            submission_df,
            bye_rate,
            new_tournament_name,
            removed_tournament_name,
            tour,
            bye_user_ids=bye_user_ids,
        ).sort_values(by="current_rank", ascending=True, na_position="last")
    elif day == 0:
        return _build_day0(rank_df, removed_tournament_name, tour).sort_values(
            by="current_rank", ascending=True, na_position="last"
        )
    else:
        if score_df is None or score_df.empty:
            if day == 1:
                return _build_day1(
                    rank_df,
                    submission_df,
                    bye_rate,
                    new_tournament_name,
                    removed_tournament_name,
                    tour,
                    bye_user_ids=bye_user_ids,
                ).sort_values(by="current_rank", ascending=True, na_position="last")
            raise ValueError("score_df is required when day > 1")
        return _build_non_day1(
            rank_df,
            submission_df,
            score_df,
            day,
            new_tournament_name,
            removed_tournament_name,
            tour,
        ).sort_values(by="current_rank", ascending=True, na_position="last")


def _build_day1(
    rank_df: pd.DataFrame,
    submission_df: Optional[pd.DataFrame],
    bye_rate: float,
    new_tournament_name: Optional[str],
    removed_tournament_name: Optional[Union[str, List[str]]],
    tour: str,
    bye_user_ids: Optional[Set[str]] = None,
) -> pd.DataFrame:
    submission_day1 = submission_df.loc[
        submission_df["day"] == 1,
        [
            "user_id",
            "username",
            "player",
            "player_alt",
            "normal_match_id",
            "normal_match_id_alt",
        ],
    ]

    # Start from all ranked users, outer-join with submissions
    # so we keep all ranked users + any unranked submitters
    rank_base = rank_df.loc[
        :, ["user_id", "rank", "score", "username", "event_num", "details_text"]
    ].rename(columns={"rank": "current_rank", "score": "current_score"})
    p_df = rank_base.merge(
        submission_day1,
        on="user_id",
        how="outer",
        suffixes=("", "_sub"),
    )
    if "username_sub" in p_df.columns:
        p_df["username"] = p_df["username"].fillna(p_df["username_sub"])
        p_df.drop(columns=["username_sub"], inplace=True)

    p_df["current_score"] = p_df["current_score"].fillna(0)
    p_df["event_num"] = p_df["event_num"].fillna(0)

    removed_tournaments = _normalize_removed_tournaments(removed_tournament_name)

    # Adjust event_num: +1 if submitted (new tournament), -N if removing N tournaments
    has_submission = p_df["user_id"].isin(submission_day1["user_id"])
    if new_tournament_name is not None:
        p_df.loc[has_submission, "event_num"] += 1
    if removed_tournaments:
        p_df.loc[has_submission, "event_num"] -= len(removed_tournaments)

    # Prefer explicit first-day bye set from draw settlement; else bye_rate band.
    if bye_user_ids:
        p_df["bye"] = p_df["user_id"].map(_uid_key).isin(bye_user_ids)
        n_submitted = submission_day1["user_id"].nunique()
        n_byes = int(p_df.loc[p_df["user_id"].isin(submission_day1["user_id"]), "bye"].sum())
        logger.info(f"{n_submitted}人参赛，{n_byes}人轮空 (draw quota)")
    elif bye_rate > 0:
        n_submitted = submission_day1["user_id"].nunique()
        n_byes = math.floor(n_submitted * bye_rate)
        submitted_ranked = p_df.loc[
            p_df["user_id"].isin(submission_day1["user_id"])
        ].sort_values("current_rank")
        bye_ids = submitted_ranked.head(n_byes)["user_id"]
        p_df["bye"] = p_df["user_id"].isin(bye_ids)
        logger.info(f"{n_submitted}人参赛，{n_byes}人轮空 (bye_rate={bye_rate})")
    else:
        p_df["bye"] = False

    p_df["score"] = 0
    p_df["players"] = pd.NA
    p_df["status"] = ""
    p_df["fill_status"] = ""

    p_df = get_today_status(p_df, bye=True)
    # Bye is shown only in today_status. Do not keep the synthetic "轮空" label
    # in the pick columns (official API fills player="轮空" / fill="BYE").
    bye_mask = p_df["today_status"].astype("string").eq("轮空")
    pick_is_bye = p_df["player"].astype("string").str.strip().eq("轮空")
    clear = bye_mask & pick_is_bye
    p_df.loc[clear, "player"] = ""
    if "player_alt" in p_df.columns:
        alt_is_bye = p_df["player_alt"].astype("string").str.strip().eq("轮空")
        p_df.loc[bye_mask & alt_is_bye, "player_alt"] = ""
    if not removed_tournaments:
        p_df["live_score"] = p_df["current_score"]
        p_df["removed_point"] = 0
    else:
        def _remove_many(details_text):
            details = parse_events(details_text)
            removed_total = 0
            for tn in removed_tournaments:
                details, removed_score = remove_current_tournament(details, tn)
                removed_total += removed_score
            return pd.Series([details, removed_total])

        p_df[["new_details", "removed_point"]] = p_df["details_text"].apply(_remove_many)

        for tn in removed_tournaments:
            if tn in GRAND_SLAMS:
                p_df["new_details"] = p_df["new_details"].apply(
                    lambda d: {**(d or {}), tn: 0}
                )
        # p_df["new_details"][new_tournament_name] = p_df["score"]
        p_df["live_score"] = p_df.apply(
            lambda r: calculate_points(r["new_details"], tour=tour)["total_points"],
            axis=1,
        )

    p_df["live_rank"] = (
        p_df[["live_score", "event_num"]]
        .apply(lambda r: (-r["live_score"], r["event_num"]), axis=1)
        .rank(method="min")
        .astype("Int64")
    )
    return _as_nullable_int(
        p_df.loc[:, [c for c in OUTPUT_COLUMNS if c in p_df.columns]]
    ).reset_index(drop=True)


def _build_day0(
    rank_df: pd.DataFrame,
    removed_tournament_name: Optional[Union[str, List[str]]],
    tour: str,
) -> pd.DataFrame:
    removed_tournaments = _normalize_removed_tournaments(removed_tournament_name)
    rank_base = rank_df.loc[
        :, ["user_id", "rank", "score", "username", "event_num", "details_text"]
    ].rename(columns={"rank": "current_rank", "score": "current_score"})

    def _remove_many(details_text):
        details = parse_events(details_text)
        removed_total = 0
        for tn in removed_tournaments:
            details, removed_score = remove_current_tournament(details, tn)
            removed_total += removed_score
        return pd.Series([details, removed_total])

    rank_base[["new_details", "removed_point"]] = rank_base["details_text"].apply(_remove_many)
    for tn in removed_tournaments:
        if tn in GRAND_SLAMS:
            rank_base["new_details"] = rank_base["new_details"].apply(
                lambda d: {**(d or {}), tn: 0}
            )
    if removed_tournaments:
        rank_base["event_num"] -= len(removed_tournaments)
    rank_base["live_score"] = rank_base.apply(
        lambda r: calculate_points(r["new_details"], tour=tour)["total_points"],
        axis=1,
    )
    rank_base["live_rank"] = (
        rank_base[["live_score", "event_num"]]
        .apply(lambda r: (-r["live_score"], r["event_num"]), axis=1)
        .rank(method="min")
        .astype("Int64")
    )
    return _as_nullable_int(
        rank_base.loc[:, [c for c in OUTPUT_COLUMNS if c in rank_base.columns]]
    ).reset_index(drop=True)


def _build_non_day1(
    rank_df: pd.DataFrame,
    submission_df: pd.DataFrame,
    score_df: pd.DataFrame,
    day: int,
    new_tournament_name: Optional[str],
    removed_tournament_name: Optional[Union[str, List[str]]],
    tour: str,
) -> pd.DataFrame:
    live_rank_df = compute_live_ranking(
        rank_df,
        score_df,
        new_tournament_name,
        removed_tournament_name,
        tour,
    )

    today_sub = submission_df.loc[
        submission_df["day"] == day,
        ["user_id", "normal_match_id", "normal_match_id_alt", "player", "player_alt"],
    ]
    live_rank_df = live_rank_df.merge(today_sub, how="left", on="user_id")

    live_rank_df = get_today_status(live_rank_df, bye=False)
    # Today's pick board: only users alive at the open of the day.
    # Keep their picks even after settlement (球员输球 / 自杀); drop picks from
    # anyone already eliminated / 未参赛 before today.
    if "alive_at_open" in live_rank_df.columns:
        alive_open = live_rank_df["alive_at_open"].fillna(False).map(bool)
    else:
        alive_open = live_rank_df["fill_status"].eq("存活")
    clear_mask = ~alive_open
    live_rank_df.loc[clear_mask, ["player", "player_alt", "today_status"]] = [
        "",
        "",
        "未选",
    ]

    return _as_nullable_int(
        live_rank_df.loc[:, [c for c in OUTPUT_COLUMNS if c in live_rank_df.columns]]
    ).reset_index(drop=True)


def _normalize_removed_tournaments(
    removed_tournament_name: Optional[Union[str, List[str]]],
) -> List[str]:
    if removed_tournament_name is None:
        return []
    if isinstance(removed_tournament_name, str):
        return [removed_tournament_name] if removed_tournament_name else []
    return [x for x in removed_tournament_name if x]

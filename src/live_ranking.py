import pandas as pd
from typing import Tuple, Dict, Optional, Union, List
from points_calculation import calculate_points, parse_events
from live_settlement import clean_player_list


def remove_current_tournament(
    tournament_scores: Dict, removed_tournament: str
) -> Tuple[int, Dict]:
    """
    Remove expired tournament from the tournament scores.

    Args:
        tournament_scores: dict where key is tournament name and value is points earned.
        removed_tournament: title of the tournament to be removed

    Returns:
        updated_scores: the score dict with the selected tournament removed
        removed_score: the score that is removed from the list, if not found, returns 0
    """
    updated_scores = tournament_scores.copy()
    removed_score = updated_scores.pop(removed_tournament, 0)
    return updated_scores, removed_score


def add_new_tournament(tournament_scores: Dict, new_score: int, new_tournament: str):
    if pd.isna(new_score):
        return tournament_scores
    updated_scores = tournament_scores.copy()
    updated_scores[new_tournament] = new_score
    return updated_scores


def _build_live_ranking(df_rank: pd.DataFrame, df_score: pd.DataFrame) -> pd.DataFrame:
    # Select and rename ranking columns
    rank_cols = [
        "user_id",
        "rank",
        "event_num",
        "title_num",
        "score",
        "username",
        "details_text",
    ]
    live_ranking_df = df_rank.loc[:, rank_cols].rename(
        {
            "rank": "current_rank",
            "score": "current_score",
        },
        axis=1,
    )

    df_copy = df_score.copy()

    # Increment day (start from 1) for non-alive users\

    df_copy.loc[df_copy["status"] != 2, "select_day"] = (
        df_copy.loc[df_copy["status"] != 2, "day"] + 1
    )

    score_merge_cols = [
        "user_id",
        "day",
        "select_day",
        "score",
        "players",
        "fill_status",
    ]
    if "alive_at_open" in df_copy.columns:
        score_merge_cols.append("alive_at_open")

    # Merge score data for users that have a ranking
    live_ranking_df = live_ranking_df.merge(
        df_copy.loc[:, score_merge_cols],
        how="left",
        on="user_id",
    )
    if "players" in live_ranking_df.columns:
        live_ranking_df["players"] = live_ranking_df["players"].apply(clean_player_list)

    # Append users that have scores but no ranking
    no_rank_cols = [
        "user_id",
        "username",
        "day",
        "select_day",
        "score",
        "players",
        "fill_status",
    ]
    if "alive_at_open" in df_copy.columns:
        no_rank_cols.append("alive_at_open")
    no_ranking = (
        df_copy[~df_score["user_id"].isin(df_rank["user_id"])]
        .loc[:, no_rank_cols]
        .rename({"username": "username"}, axis=1)
    )
    live_ranking_df = pd.concat([live_ranking_df, no_ranking])

    # Fill NULLs for users without score data
    fill_map = {"event_num": 0, "title_num": 0, "current_score": 0, "details_text": ""}
    live_ranking_df[list(fill_map.keys())] = live_ranking_df[
        list(fill_map.keys())
    ].fillna(fill_map)

    # Update event number, status, and last selection for users with active score data
    has_score = live_ranking_df["select_day"].notna()
    live_ranking_df.loc[has_score, "event_num"] += 1
    def _last_pick(players) -> str:
        if isinstance(players, list):
            for item in reversed(players):
                text = str(item or "").strip()
                if text and text != "轮空":
                    return text
        return ""

    last_pick = live_ranking_df["players"].map(_last_pick)
    status_txt = (
        "Day "
        + live_ranking_df.loc[has_score, "select_day"].astype(str)
        + ": "
        + last_pick.loc[has_score]
    )
    # Avoid trailing "Day N: " when the only Day1 entry was a bye (no pick list).
    bare = last_pick.loc[has_score].eq("")
    status_txt = status_txt.where(
        ~bare,
        "Day " + live_ranking_df.loc[has_score, "select_day"].astype(str),
    )
    live_ranking_df.loc[has_score, "status"] = status_txt
    # 球员输球 / 球员退赛 both credit a killer (last pick when settlement left it blank).
    loser_mask = live_ranking_df["fill_status"].isin(["球员输球", "球员退赛"])
    # Prefer settlement killer when set; otherwise last pick. Never wipe with "".
    if "killer" not in live_ranking_df.columns:
        live_ranking_df["killer"] = ""
    existing_killer = (
        live_ranking_df["killer"].fillna("").astype(str).map(lambda s: s.strip())
    )
    inferred = last_pick.fillna("").astype(str).map(lambda s: s.strip())
    # Prefer non-empty settlement killer; else last pick.
    merged_killer = existing_killer.where(existing_killer.ne(""), inferred)
    live_ranking_df.loc[loser_mask, "killer"] = merged_killer.loc[loser_mask]
    live_ranking_df.loc[~has_score, "status"] = "未参赛"
    live_ranking_df["fill_status"] = live_ranking_df["fill_status"].fillna("未参赛")

    return live_ranking_df


def compute_live_ranking(
    current_ranking: pd.DataFrame,
    result: pd.DataFrame,
    new_tournament_name: str,
    removed_tournament_name: Optional[Union[str, List[str]]] = None,
    tour: str = "WTA",
):
    if new_tournament_name is None:
        raise ValueError("Must have a tournament name")

    live_ranking = _build_live_ranking(current_ranking, result)

    removed_tournaments = _normalize_removed_tournaments(removed_tournament_name)

    if removed_tournaments:
        def _remove_many(details_text):
            details = parse_events(details_text)
            removed_total = 0
            for tn in removed_tournaments:
                details, removed_score = remove_current_tournament(details, tn)
                removed_total += removed_score
            return pd.Series([details, removed_total])

        live_ranking[["new_details", "removed_point"]] = live_ranking[
            "details_text"
        ].apply(_remove_many)
    else:
        live_ranking["new_details"] = live_ranking["details_text"].apply(parse_events)
        live_ranking["removed_point"] = 0

    live_ranking["new_details"] = live_ranking.apply(
        lambda r: add_new_tournament(r["new_details"], r["score"], new_tournament_name),
        axis=1,
    )
    if removed_tournaments:
        live_ranking["event_num"] -= len(removed_tournaments)
    live_ranking["live_score"] = live_ranking.apply(
        lambda r: calculate_points(r["new_details"], tour=tour)["total_points"], axis=1
    )
    live_ranking = live_ranking[live_ranking["new_details"].map(len) > 0]
    live_ranking["live_rank"] = (
        live_ranking[["live_score", "event_num"]]
        .apply(lambda r: (-r["live_score"], r["event_num"]), axis=1)
        .rank(method="min")
        .astype("Int64")
    )
    live_ranking = live_ranking.sort_values(by="live_rank")
    live_ranking["rank_change"] = (
        live_ranking["current_rank"] - live_ranking["live_rank"]
    )
    return live_ranking.drop(
        ["title_num", "event_num", "select_day", "new_details", "details_text"],
        axis=1,
    )


def _normalize_removed_tournaments(
    removed_tournament_name: Optional[Union[str, List[str]]],
) -> List[str]:
    if removed_tournament_name is None:
        return []
    if isinstance(removed_tournament_name, str):
        return [removed_tournament_name] if removed_tournament_name else []
    return [x for x in removed_tournament_name if x]

import math
from logger import get_logger
import pandas as pd
from typing import Union, List

logger = get_logger(__name__)


def get_bye_status(
    rank: pd.DataFrame, submission: pd.DataFrame, bye_rate: float
) -> pd.DataFrame:
    logger.info(f"轮空状态基于{rank['monday'].unique()[0]}排名")
    p_df = submission.merge(
        rank.loc[:, ["user_id", "rank"]], on="user_id", how="left"
    ).sort_values(by="rank")
    n_byes = math.floor(len(submission) * bye_rate)
    byes = p_df.head(n_byes).reset_index(drop=True)
    logger.info(f"{len(submission)}人参赛，{n_byes}人轮空")
    p_df["bye"] = p_df["user_id"].isin(byes["user_id"])
    logger.info(f"轮空最低排名: {byes['rank'].max()}")
    return p_df


def _is_repeat_pick(row) -> bool:
    """True if today's primary was already used on a prior day.

    After live settlement, today's pick is appended to ``players`` for both
    wins (存活) and losses (球员输球) / suicides. That trailing entry must not
    count as 自杀（重复）. A backup is not judged unless the primary retired.
    """
    players = row.get("players")
    pick = row.get("player")
    if not isinstance(players, list) or pick is None or (isinstance(pick, float) and pd.isna(pick)):
        return False
    pick = str(pick).strip()
    if not pick or pick == "轮空":
        return False
    used = [str(p).strip() for p in players if str(p).strip() and str(p).strip() != "轮空"]
    # Settlement (win/loss/suicide) appends today's pick as the last entry.
    if used and used[-1] == pick:
        used = used[:-1]
    return pick in used


def get_today_status(p_df: pd.DataFrame, bye: bool = False) -> pd.DataFrame:
    p_df_copy = p_df.copy()
    if bye:
        if "bye" not in p_df.columns:
            raise ValueError(
                "Input dataframe must contain a column indicating bye status."
            )
        suicide = p_df_copy[
            (p_df_copy["normal_match_id"] == p_df_copy["normal_match_id_alt"])
            & (~p_df_copy["bye"])
        ]
        p_df_copy.loc[p_df_copy["user_id"].isin(suicide["user_id"]), "today_status"] = (
            "自杀（主备冲突）"
        )
        p_df_copy.loc[p_df_copy["bye"], "today_status"] = "轮空"
    else:
        if "players" not in p_df.columns:
            raise ValueError(
                "Input dataframe must contain a column indicating selected players."
            )
        suicide = p_df_copy[
            p_df_copy["normal_match_id"] == p_df_copy["normal_match_id_alt"]
        ]
        repeat = p_df_copy[p_df_copy.apply(_is_repeat_pick, axis=1)]
        p_df_copy.loc[p_df_copy["user_id"].isin(suicide["user_id"]), "today_status"] = (
            "自杀（主备冲突）"
        )
        p_df_copy.loc[p_df_copy["user_id"].isin(repeat["user_id"]), "today_status"] = (
            "自杀（重复）"
        )
        logger.info(f"{len(repeat)}人自杀（重复）")
    logger.info(f"{len(suicide)}人自杀（主备冲突）")
    p_df_copy.loc[p_df_copy["player"].isna(), "today_status"] = "未选"
    return p_df_copy


def compute_submission_stats(p_df: pd.DataFrame, bye: bool = False):
    if bye:
        if "bye" not in p_df.columns:
            raise ValueError(
                "Input dataframe must contain a column indicating bye status."
            )
        result = (
            p_df.groupby(["player", "today_status"], dropna=False)
            .agg(
                non_bye_count=("bye", lambda x: (~x).sum()),
                bye_count=("bye", "sum"),
                total_count=("bye", "count"),
            )
            .sort_values(["today_status", "non_bye_count"], ascending=[True, False])
            .reset_index()
        )
        result["bye_count"] = result["bye_count"].astype("Int64")
        result.loc[result["today_status"], "bye_count"] = pd.NA
    else:
        result = (
            p_df.groupby(["player", "today_status"], dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values(["today_status", "count"], ascending=[True, False])
            .reset_index(drop=True)
        )
    return result


def process_submission_stats(
    bye: bool = False,
    rank_table: pd.DataFrame = None,
    submission_table: pd.DataFrame = None,
    score_table: pd.DataFrame = None,
    bye_rate: float = 0,
    target_day: int = 2,
):
    if bye:
        if all(x is not None for x in [rank_table, submission_table, bye_rate]):
            p_df = get_bye_status(rank_table, submission_table, bye_rate)
        else:
            raise ValueError("Missing required inputs.")
    else:
        if all(x is not None for x in [submission_table, score_table, target_day]):
            p_df = score_table[score_table["status"] == 2].merge(
                submission_table.loc[
                    submission_table["day"] == target_day,
                    [
                        "user_id",
                        "normal_match_id",
                        "normal_match_id_alt",
                        "player",
                        "player_alt",
                    ],
                ],
                on="user_id",
                how="left",
            )
        else:
            raise ValueError("Missing required inputs.")
    p_df = get_today_status(p_df, bye)
    stats = compute_submission_stats(p_df, bye)
    return stats


def get_alt_stats(
    bye: bool = False,
    rank_table: pd.DataFrame = None,
    submission_table: pd.DataFrame = None,
    score_table: pd.DataFrame = None,
    bye_rate: float = 0,
    target_day: int = 2,
    main: Union[List[str], str] = None,
):
    if bye:
        if all(x is not None for x in [rank_table, submission_table, bye_rate]):
            p_df = get_bye_status(rank_table, submission_table, bye_rate)
            p_df = p_df[p_df["player"].isin(main)]
            p_df = get_today_status(p_df, bye)
            result = (
                p_df.groupby(["player_alt", "today_status", "player"], dropna=False)
                .agg(
                    non_bye_count=("bye", lambda x: (~x).sum()),
                    bye_count=("bye", "sum"),
                    total_count=("bye", "count"),
                )
                .sort_values(
                    ["player", "today_status", "non_bye_count"],
                    ascending=[True, True, False],
                )
                .reset_index()
            )
            result["bye_count"] = result["bye_count"].astype("Int64")
            result.loc[result["today_status"], "bye_count"] = pd.NA
        else:
            raise ValueError("Missing required inputs.")
    else:
        if all(x is not None for x in [submission_table, score_table, target_day]):
            p_df = submission_table.loc[
                (submission_table["day"] == target_day)
                & (submission_table["player"].isin(main)),
                [
                    "user_id",
                    "normal_match_id",
                    "normal_match_id_alt",
                    "player",
                    "player_alt",
                ],
            ].merge(
                score_table[score_table["status"] == 2],
                on="user_id",
            )
            p_df = get_today_status(p_df, bye)
            n_suicide = len(p_df[p_df["today_status"] == "自杀（重复）"])
            p_df["today_status"] = p_df["today_status"] | (
                p_df["player_alt"].isin(p_df["players"])
            )
            logger.info(f"{len(p_df[p_df['today_status']]) - n_suicide}人备选重复")
            result = (
                p_df.groupby(["player_alt", "today_status", "player"], dropna=False)
                .size()
                .reset_index(name="count")
                .sort_values(
                    ["player", "today_status", "count"], ascending=[True, True, False]
                )
                .reset_index(drop=True)
            )
        else:
            raise ValueError("Missing required inputs.")
    return result


def get_availability_stats(
    submission_table: pd.DataFrame,
    score_table: pd.DataFrame,
    options: List[str],
    target_day: int,
):
    alive_users = score_table[score_table["status"] == 2].merge(
        submission_table.loc[
            submission_table["day"] == target_day,
            [
                "user_id",
                "normal_match_id",
                "normal_match_id_alt",
                "player",
                "player_alt",
            ],
        ],
        on="user_id",
        how="left",
    )
    alive_users = get_today_status(alive_users)
    alive_users["possible_selection"] = alive_users["players"].apply(
        lambda x: [i for i in options if i not in x]
    )
    stats = (
        alive_users.groupby(
            ["player", "today_status", alive_users["possible_selection"].apply(tuple)],
            dropna=False,
        )
        .size()
        .reset_index(name="count")
        .sort_values(["today_status", "count"], ascending=[True, False])
        .reset_index(drop=True)
    )
    return stats

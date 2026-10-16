"""
Live draw settlement — advance survivor outcomes ahead of official score updates.

Adapted from chen_web ``survivor.process.apply_live_settlement``, using frog's
English score/submission column names.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import pandas as pd

from draw_status import (
    DrawStatus,
    beijing_now,
    opening_round_name,
    opening_round_rank,
    retirement_backup_allowed,
)
from logger import get_logger

logger = get_logger(__name__)

SUICIDE_REPEAT = "自杀(重复)"
SUICIDE_CONFLICT = "自杀(主备冲突)"

FILL_TO_STATUS = {
    "存活": 2,
    "球员输球": -2,
    "自杀(重复)": -3,
    "自杀(主备冲突)": -4,
    "自杀(退赛)": 0,
    "未参赛": pd.NA,
}


def _as_key(value: object) -> str:
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


def _has_id(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text != "0"


def _details_by_user(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        uid = _as_key(item.get("user_id"))
        if uid:
            grouped[uid].append(item)
    for items in grouped.values():
        items.sort(key=lambda row: int(row.get("day") or 0))
    return grouped


def _backup_is_elim_opponent(
    detail: dict[str, Any], draw: DrawStatus | None
) -> bool:
    """True when 备选 is the opponent who eliminated 主选 (both sides of one match)."""
    if draw is None or not draw.by_id:
        return False
    pick = str(detail.get("player") or "").strip()
    alt = str(detail.get("player_alt") or "").strip()
    if not pick or not alt or pick == "轮空" or alt == "轮空":
        return False
    primary = draw.lookup(detail.get("fill"), pick)
    if primary is None or not primary.eliminated:
        return False
    opp = str(primary.elim_opponent or "").strip()
    return bool(opp) and opp == alt


def _primary_early_retirement(detail: dict[str, Any], draw: DrawStatus | None) -> bool:
    """True when 主选退赛/赛前退赛, so 备选 is actually played."""
    if draw is None or not draw.by_id:
        return False
    pick = str(detail.get("player") or "").strip()
    if not pick or pick == "轮空":
        return False
    player = draw.lookup(detail.get("fill"), pick)
    if player is None or not player.eliminated:
        return False
    return retirement_backup_allowed(player.elim_score)


def _suicide_reason(
    detail: dict[str, Any],
    used: list[str],
    draw: DrawStatus | None = None,
) -> str | None:
    """
    主选未退赛时，备选不参与判定，只保留主备冲突。
    主选退赛并启用备选后，备选重复才是自杀(重复)。
    """
    pick = str(detail.get("player") or "").strip()
    alt = str(detail.get("player_alt") or "").strip()
    if pick and pick != "轮空" and pick in used:
        return SUICIDE_REPEAT
    if pick and alt and pick == alt and pick != "轮空":
        return SUICIDE_CONFLICT
    fill = str(detail.get("fill") or "").strip()
    fill_alt = str(detail.get("fill_alt") or "").strip()
    if fill and fill_alt and fill == fill_alt and fill not in {"0", ""}:
        return SUICIDE_CONFLICT
    match_id = detail.get("normal_match_id")
    match_alt = detail.get("normal_match_id_alt")
    if _has_id(match_id) and _has_id(match_alt) and str(match_id) == str(match_alt):
        return SUICIDE_CONFLICT
    # Match-id can disagree with the draw (e.g. Zoey day3 1210/1215) while
    # 主选/备选 are still the two sides of the elimination match.
    if _backup_is_elim_opponent(detail, draw):
        return SUICIDE_CONFLICT
    if (
        alt
        and alt != "轮空"
        and alt in used
        and _primary_early_retirement(detail, draw)
    ):
        return SUICIDE_REPEAT
    return None


def _alt_detail(detail: dict[str, Any]) -> dict[str, Any] | None:
    """Build a detail row that settles on 备选 instead of 主选."""
    alt = str(detail.get("player_alt") or "").strip()
    if not alt:
        return None
    fill_alt = str(detail.get("fill_alt") or "").strip()
    match_alt = detail.get("normal_match_id_alt")
    out = dict(detail)
    out["player"] = alt
    out["fill"] = fill_alt if fill_alt and fill_alt != "0" else detail.get("fill")
    if _has_id(match_alt):
        out["normal_match_id"] = match_alt
    # Prevent recursive backup-of-backup.
    out["player_alt"] = ""
    out["fill_alt"] = ""
    out["normal_match_id_alt"] = ""
    return out


def _pick_outcome(
    detail: dict[str, Any],
    draw: DrawStatus,
    fills_by_match: dict[Any, set[str]],
    live_round: int,
    min_still_round: int,
    *,
    allow_backup: bool = True,
) -> tuple[str | None, dict[str, Any]]:
    """
    Return ``(outcome, effective_detail)``.

    outcome: ``win`` / ``loss`` / ``None`` (pending).
    When primary is eliminated by retirement/W/O before set 1 ends and a
    backup pick exists, settle on the backup instead.
    """
    pick = str(detail.get("player") or "").strip()
    if pick == "轮空":
        return "win", detail
    player = draw.lookup(detail.get("fill"), pick)
    if player is None:
        return None, detail
    if player.eliminated:
        # Conflict / suicide already handled upstream; never activate backup
        # onto the opponent who just eliminated the primary.
        if allow_backup and retirement_backup_allowed(player.elim_score):
            if not _backup_is_elim_opponent(detail, draw):
                alt = _alt_detail(detail)
                if alt is not None:
                    return _pick_outcome(
                        alt,
                        draw,
                        fills_by_match,
                        live_round,
                        min_still_round,
                        allow_backup=False,
                    )
        return "loss", detail
    if player.live:
        return None, detail
    fill = str(detail.get("fill") or "").strip()
    for opp_id in fills_by_match.get(detail.get("normal_match_id")) or set():
        if opp_id == fill:
            continue
        opp = draw.lookup(opp_id, None)
        if opp and opp.eliminated:
            return "win", detail
    if live_round and player.round_rank > live_round:
        return "win", detail
    if min_still_round and player.round_rank > min_still_round:
        return "win", detail
    return None, detail


def _settled_event_points(
    draw: DrawStatus,
    detail: dict[str, Any],
    current: int,
    day: int,
    user_bye: bool = False,
) -> int:
    current = int(current or 0)
    if user_bye:
        day = 1
    if draw.day_points and 1 <= day <= len(draw.day_points):
        return max(current, int(draw.day_points[day - 1]))
    if user_bye:
        opening = opening_round_name(len(draw.by_id))
        points = draw.round_points.get(opening) if opening else None
        if points is not None:
            return max(current, int(points))
        return current
    player = draw.lookup(detail.get("fill"), detail.get("player"))
    if player is None or not player.round:
        return current
    points = draw.round_points.get(player.round)
    if points is None:
        return current
    return max(current, int(points))


def first_day_bye_quota(draw: DrawStatus | None, n_fillers: int) -> int:
    if draw is None or draw.is_slam or n_fillers <= 0:
        return 0
    if draw.first_day_bye_quota > 0:
        return int(draw.first_day_bye_quota)
    seeds, bracket = draw.tennis_bye_count, draw.bracket_size
    if seeds <= 0 or bracket <= 0:
        return 0
    return seeds * n_fillers // bracket


def first_day_bye_users(
    detail_rows: list[dict[str, Any]],
    draw: DrawStatus | None,
    rank_by_id: dict[str, int] | None,
) -> set[str]:
    fillers: list[str] = []
    seen: set[str] = set()
    for item in detail_rows:
        if int(item.get("day") or 0) != 1:
            continue
        if not str(item.get("player") or "").strip():
            continue
        uid = _as_key(item.get("user_id"))
        if not uid or uid in seen:
            continue
        seen.add(uid)
        fillers.append(uid)
    quota = first_day_bye_quota(draw, len(fillers))
    ranks = rank_by_id or {}
    if quota <= 0 or not fillers or not ranks:
        return set()
    fillers.sort(key=lambda uid: (ranks.get(uid, 10**9), uid))
    return set(fillers[:quota])


def _survivor_round_rank(label: str, field_n: int) -> int:
    text = str(label or "").strip().upper().replace("轮", "")
    # Pick-day labels may be R1/1, QF/2 when a round spans multiple days.
    if "/" in text:
        text = text.split("/", 1)[0].strip()
    opening = opening_round_rank(field_n)
    if not text:
        return 0
    if text in {"R1", "1"}:
        return opening
    if text in {"R2", "2"}:
        return opening + 1 if opening else 0
    if text in {"R3", "3"}:
        return opening + 2 if opening else 0
    if text in {"R4", "4"}:
        return opening + 3 if opening else 0
    return {
        "R128": 1,
        "R64": 2,
        "R32": 3,
        "R16": 4,
        "QF": 5,
        "SF": 6,
        "F": 7,
        "W": 8,
    }.get(text, 0)


def _round_still_going(draw: DrawStatus | None, round_rank: int) -> bool:
    if draw is None or not draw.by_id or not round_rank:
        return bool(draw and any(player.live for player in draw.by_id.values()))
    return any(
        player.round_rank == round_rank and (player.live or not player.eliminated)
        for player in draw.by_id.values()
    )


def _next_day_open(
    draw: DrawStatus | None,
    detail_rows: list[dict[str, Any]],
    day: int,
) -> bool:
    nxt = day + 1
    for item in draw.pick_days if draw else []:
        if int(item.get("day") or 0) == nxt and (
            item.get("open") or item.get("has_cards")
        ):
            return True
    return any(
        int(item.get("day") or 0) == nxt and str(item.get("player") or "").strip()
        for item in detail_rows
    )


def current_play_day(
    draw: DrawStatus | None,
    detail_rows: list[dict[str, Any]] | None = None,
) -> int:
    detail_rows = detail_rows or []
    today = beijing_now().date()
    schedule = [item for item in (draw.pick_days if draw else []) if item.get("day")]
    if not schedule:
        days = sorted(
            {
                int(item.get("day") or 0)
                for item in detail_rows
                if int(item.get("day") or 0) > 0
            }
        )
        return days[0] if days else 1
    play = int(schedule[0]["day"])
    for item in schedule:
        date = item.get("date")
        if date is None or date <= today:
            play = int(item["day"])
        if date == today:
            break
        if date is not None and date > today:
            break
    field_n = len(draw.by_id) if draw else 0
    while True:
        nxt = play + 1
        if not _next_day_open(draw, detail_rows, play):
            break
        current = next(
            (item for item in schedule if int(item.get("day") or 0) == play), None
        )
        round_rank = _survivor_round_rank(
            str((current or {}).get("round") or ""), field_n
        )
        if not round_rank:
            round_rank = opening_round_rank(field_n) + play - 1
        if _round_still_going(draw, round_rank):
            break
        nxt_item = next(
            (item for item in schedule if int(item.get("day") or 0) == nxt), None
        )
        nxt_date = (nxt_item or {}).get("date")
        play = nxt
        if nxt_date is not None and nxt_date > today:
            break
    return play


def submission_to_detail_rows(submission_df: pd.DataFrame) -> list[dict[str, Any]]:
    if submission_df is None or submission_df.empty:
        return []
    return submission_df.to_dict(orient="records")


def rank_by_id_from_df(rank_df: Optional[pd.DataFrame]) -> dict[str, int]:
    if rank_df is None or rank_df.empty:
        return {}
    if "user_id" not in rank_df.columns or "rank" not in rank_df.columns:
        return {}
    ranks = pd.to_numeric(rank_df["rank"], errors="coerce")
    out: dict[str, int] = {}
    for uid, rank in zip(rank_df["user_id"], ranks):
        key = _as_key(uid)
        if key and pd.notna(rank):
            out[key] = int(rank)
    return out


def clean_player_list(value) -> list:
    """Drop empty labels. Keep a leading Day1 ``轮空`` so 选人明细 can show it."""
    if isinstance(value, list):
        items = value
    elif value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    else:
        try:
            if pd.isna(value):
                return []
        except (TypeError, ValueError):
            pass
        items = list(value) if value else []
    return [p for p in items if str(p).strip()]


def _had_day1_bye(value) -> bool:
    items = value if isinstance(value, list) else []
    return any(str(p).strip() == "轮空" for p in items)


def _players_without_bye(value) -> list:
    """Settlement copy: Day1 bye is not a picked player."""
    return [p for p in clean_player_list(value) if str(p).strip() != "轮空"]


def _with_day1_bye(players, show_bye: bool) -> list:
    picks = _players_without_bye(players)
    if show_bye:
        return ["轮空", *picks]
    return picks


def _detail_for_pick(
    details: list[dict[str, Any]], pick: str
) -> dict[str, Any] | None:
    """Latest submission row whose primary equals ``pick``."""
    pick = str(pick or "").strip()
    if not pick:
        return None
    matched = [
        item
        for item in details
        if str(item.get("player") or "").strip() == pick
    ]
    if not matched:
        return None
    matched.sort(key=lambda row: int(row.get("day") or 0))
    return matched[-1]


def _repair_early_retirement_rows(
    result: pd.DataFrame,
    grouped: dict[str, list[dict[str, Any]]],
    draw: DrawStatus,
) -> int:
    """
    Fix official rows that already marked death on an early-ret/W/O primary.

    - With backup: revive to 存活 and drop the primary from ``players`` so the
      main loop can settle on the backup (killer follows backup outcome).
    - Without backup: normalize ``自杀(退赛)`` → ``球员输球`` with killer=primary.
    """
    repaired = 0
    for index, row in result.iterrows():
        status = str(row.get("fill_status") or "").strip()
        if status not in {"球员输球", "自杀(退赛)"}:
            continue
        used = _players_without_bye(row.get("players"))
        if not used:
            continue
        last = str(used[-1]).strip()
        uid = _as_key(row.get("user_id"))
        detail = _detail_for_pick(grouped.get(uid, []), last)
        if detail is None:
            if status == "自杀(退赛)":
                result.at[index, "fill_status"] = "球员输球"
                result.at[index, "killer"] = last
                result.at[index, "players"] = used
                repaired += 1
            continue
        player = draw.lookup(detail.get("fill"), last)
        if player is None or not player.eliminated:
            if status == "自杀(退赛)":
                result.at[index, "fill_status"] = "球员输球"
                result.at[index, "killer"] = last
                result.at[index, "players"] = used
                repaired += 1
            continue
        early = retirement_backup_allowed(player.elim_score)
        alt = str(detail.get("player_alt") or "").strip()
        if early and alt:
            # Suicide/conflict first: backup cannot be the elim opponent.
            if _backup_is_elim_opponent(detail, draw):
                result.at[index, "fill_status"] = SUICIDE_CONFLICT
                result.at[index, "killer"] = ""
                result.at[index, "players"] = used
                if "status" in result.columns:
                    result.at[index, "status"] = FILL_TO_STATUS.get(
                        SUICIDE_CONFLICT, -4
                    )
                repaired += 1
                continue
            alt_player = draw.lookup(detail.get("fill_alt"), alt)
            # Backup already eliminated: official death on primary stands
            # (e.g. 哈恰诺夫 W/O with 门希克 backup who was already out).
            # Only revive when backup can still change the outcome.
            if alt_player is not None and alt_player.eliminated:
                result.at[index, "fill_status"] = "球员输球"
                result.at[index, "killer"] = last
                result.at[index, "players"] = used
                if "status" in result.columns:
                    result.at[index, "status"] = FILL_TO_STATUS.get("球员输球", -2)
                repaired += 1
                continue
            # Wrongly died on primary despite usable backup — revive for re-settle.
            used = used[:-1]
            death_day = int(detail.get("day") or 0) or (len(used) + 1)
            result.at[index, "players"] = used
            result.at[index, "fill_status"] = "存活"
            result.at[index, "killer"] = ""
            result.at[index, "day"] = max(0, death_day - 1)
            if "status" in result.columns:
                result.at[index, "status"] = FILL_TO_STATUS.get("存活", 2)
            repaired += 1
            continue
        if early and not alt:
            result.at[index, "fill_status"] = "球员输球"
            result.at[index, "killer"] = last
            result.at[index, "players"] = used
            if "status" in result.columns:
                result.at[index, "status"] = FILL_TO_STATUS.get("球员输球", -2)
            repaired += 1
            continue
        if status == "自杀(退赛)":
            result.at[index, "fill_status"] = "球员输球"
            result.at[index, "killer"] = last
            result.at[index, "players"] = used
            if "status" in result.columns:
                result.at[index, "status"] = FILL_TO_STATUS.get("球员输球", -2)
            repaired += 1
    return repaired


def ensure_score_df(
    score_df: Optional[pd.DataFrame],
    submission_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Return a score table suitable for settlement (synthesize from submissions if needed)."""
    if score_df is not None and not score_df.empty:
        out = score_df.copy()
        if "players" in out.columns:
            out["players"] = out["players"].apply(clean_player_list)
        if "fill_status" not in out.columns:
            out["fill_status"] = "存活"
        out["fill_status"] = out["fill_status"].fillna("存活")
        if "day" not in out.columns:
            out["day"] = 0
        out["day"] = pd.to_numeric(out["day"], errors="coerce").fillna(0).astype(int)
        if "score" not in out.columns:
            out["score"] = 0
        out["score"] = pd.to_numeric(out["score"], errors="coerce").fillna(0).astype(int)
        return out

    if submission_df is None or submission_df.empty:
        return None

    first = submission_df.sort_values("day").drop_duplicates(
        subset=["user_id"], keep="first"
    )
    return pd.DataFrame(
        {
            "user_id": first["user_id"].values,
            "username": first["username"].values
            if "username" in first.columns
            else [""] * len(first),
            "status": 2,
            "day": 0,
            "score": 0,
            "players": [[] for _ in range(len(first))],
            "fill_status": "存活",
        }
    )


def summarize_backup_events(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Collapse raw backup events into panel rows.

    Each item: ``{primary, score, total, backs:[{name, alive, out, live, total}]}``.
    """
    if not events:
        return []
    by_primary: dict[str, dict[str, Any]] = {}
    for event in events:
        primary = str(event.get("primary") or "").strip()
        if not primary:
            continue
        bucket = by_primary.setdefault(
            primary,
            {"score": "", "backs": defaultdict(lambda: {"alive": 0, "out": 0, "live": 0})},
        )
        score = str(event.get("score") or "").strip()
        if score and not bucket["score"]:
            bucket["score"] = score
        backup = str(event.get("backup") or "").strip()
        result = str(event.get("result") or "").strip()
        if result not in {"alive", "out", "live"}:
            continue
        bucket["backs"][backup][result] += 1

    panels: list[dict[str, Any]] = []
    for primary, payload in by_primary.items():
        backs: list[dict[str, Any]] = []
        for name, counts in payload["backs"].items():
            total = int(counts["alive"]) + int(counts["out"]) + int(counts["live"])
            if total <= 0:
                continue
            backs.append(
                {
                    "name": name,
                    "alive": int(counts["alive"]),
                    "out": int(counts["out"]),
                    "live": int(counts["live"]),
                    "total": total,
                }
            )
        backs.sort(key=lambda row: (row["name"] == "", -row["total"], row["name"]))
        panels.append(
            {
                "primary": primary,
                "score": payload["score"],
                "total": sum(row["total"] for row in backs),
                "backs": backs,
            }
        )
    panels.sort(key=lambda row: -row["total"])
    return panels


def apply_live_settlement(
    score_df: pd.DataFrame,
    detail_rows: list[dict[str, Any]],
    draw: DrawStatus | None,
    rank_by_id: dict[str, int] | None = None,
) -> tuple[pd.DataFrame, dict[str, int], set[str], set[str], list[dict[str, Any]]]:
    """
    Settle alive users against the live draw.

    Returns
    -------
    score_df : updated score table (fill_status / day / score / players / killer)
    counts : win/loss/pending/suicide/bye tallies
    bye_users : first-day bye user_id keys
    pending_users : alive users whose current-day pick is not settled yet
    backup_events : early-retirement backup activations for the summary panel
    """
    empty = {"win": 0, "loss": 0, "pending": 0, "suicide": 0, "bye": 0}
    if score_df is None or score_df.empty or not detail_rows:
        return score_df, empty, set(), set(), []

    grouped = _details_by_user(detail_rows)
    bye_users = first_day_bye_users(detail_rows, draw, rank_by_id)
    play_day = current_play_day(draw, detail_rows)
    fills_by_match: dict[Any, set[str]] = defaultdict(set)
    pick_players = []
    if draw is not None and draw.by_id:
        for item in detail_rows:
            player = draw.lookup(item.get("fill"), item.get("player"))
            if player:
                pick_players.append(player)
            match_id = item.get("normal_match_id")
            fill = str(item.get("fill") or "").strip()
            if match_id and fill:
                fills_by_match[match_id].add(fill)
    live_round = min(
        (p.round_rank for p in pick_players if p.live and p.round_rank), default=0
    )
    still_ranks = [
        p.round_rank
        for p in pick_players
        if not p.eliminated and not p.live and p.round_rank
    ]
    min_still_round = min(still_ranks) if still_ranks else 0

    result = score_df.copy()
    if "killer" not in result.columns:
        result["killer"] = ""
    if "first_day_bye" not in result.columns:
        result["first_day_bye"] = False
    result["first_day_bye"] = False

    # Remember Day1 bye before settlement works on real picks only.
    had_day1_bye = result["players"].map(_had_day1_bye)
    result["players"] = result["players"].apply(_players_without_bye)
    result["fill_status"] = result["fill_status"].fillna("存活")
    result["day"] = pd.to_numeric(result["day"], errors="coerce").fillna(0).astype(int)
    result["score"] = pd.to_numeric(result["score"], errors="coerce").fillna(0).astype(int)
    # Snapshot before settlement mutates fill_status — today's pick summary
    # must only count users who were still alive at the open of the day.
    result["alive_at_open"] = result["fill_status"].astype(str).eq("存活")
    if draw is not None and draw.by_id:
        repaired_n = _repair_early_retirement_rows(result, grouped, draw)
        if repaired_n:
            logger.info(
                f"Repaired {repaired_n} early-retirement / 退赛 rows for backup"
            )
        # Revived rows were wrongly marked dead on primary; treat as alive at open
        # so today's pick board / summary still include them.
        result.loc[
            result["fill_status"].astype(str).eq("存活"), "alive_at_open"
        ] = True

    counts = dict(empty)
    pending_users: set[str] = set()
    backup_events: list[dict[str, Any]] = []
    for index, row in result.iterrows():
        if str(row.get("fill_status") or "") != "存活":
            continue
        used = _players_without_bye(row.get("players"))
        official_day = int(
            pd.to_numeric(row.get("day"), errors="coerce") or len(used) or 0
        )
        uid = _as_key(row.get("user_id"))
        day1_pick = any(
            int(item.get("day") or 0) == 1 and str(item.get("player") or "").strip()
            for item in grouped.get(uid, [])
        )
        if official_day <= 0 and not day1_pick:
            result.at[index, "fill_status"] = "未参赛"
            result.at[index, "killer"] = ""
            continue
        pending = False
        for detail in grouped.get(uid, []):
            day = int(detail.get("day") or 0)
            if day <= official_day:
                continue
            pick = str(detail.get("player") or "").strip()
            if not pick:
                pending = True
                break
            suicide = _suicide_reason(detail, used, draw)
            if suicide:
                if pick != "轮空":
                    used.append(pick)
                result.at[index, "players"] = used
                result.at[index, "fill_status"] = suicide
                result.at[index, "killer"] = ""
                result.at[index, "day"] = official_day
                counts["suicide"] += 1
                pending = False
                break
            if day > play_day:
                break
            if day == 1 and uid in bye_users:
                official_day = 1
                result.at[index, "day"] = 1
                result.at[index, "fill_status"] = "存活"
                result.at[index, "first_day_bye"] = True
                result.at[index, "killer"] = ""
                result.at[index, "players"] = _with_day1_bye(used, True)
                if draw is not None:
                    result.at[index, "score"] = _settled_event_points(
                        draw,
                        detail,
                        int(result.at[index, "score"] or 0),
                        day,
                        user_bye=True,
                    )
                counts["win"] += 1
                counts["bye"] += 1
                continue
            if draw is None or not draw.by_id:
                pending = True
                break
            outcome, effective = _pick_outcome(
                detail, draw, fills_by_match, live_round, min_still_round
            )
            eff_pick = str(effective.get("player") or pick).strip()
            alt = str(detail.get("player_alt") or "").strip()
            primary_player = draw.lookup(detail.get("fill"), pick)
            early_ret = bool(
                primary_player is not None
                and primary_player.eliminated
                and retirement_backup_allowed(primary_player.elim_score)
            )
            if early_ret:
                score_txt = str(primary_player.elim_score or "").strip()
                if alt and eff_pick == alt:
                    if outcome == "win":
                        bak_result = "alive"
                    elif outcome == "loss":
                        bak_result = "out"
                    else:
                        bak_result = "live"
                    backup_events.append(
                        {
                            "primary": pick,
                            "backup": alt,
                            "result": bak_result,
                            "score": score_txt,
                        }
                    )
                elif not alt and outcome == "loss":
                    backup_events.append(
                        {
                            "primary": pick,
                            "backup": "",
                            "result": "out",
                            "score": score_txt,
                        }
                    )
            if outcome == "win":
                if eff_pick and eff_pick != "轮空":
                    used.append(eff_pick)
                official_day = day
                result.at[index, "players"] = used
                result.at[index, "day"] = day
                result.at[index, "killer"] = ""
                result.at[index, "score"] = _settled_event_points(
                    draw, effective, int(result.at[index, "score"] or 0), day
                )
                counts["win"] += 1
                continue
            if outcome == "loss":
                if eff_pick and eff_pick != "轮空":
                    used.append(eff_pick)
                result.at[index, "players"] = used
                result.at[index, "fill_status"] = "球员输球"
                result.at[index, "killer"] = (
                    eff_pick if eff_pick and eff_pick != "轮空" else ""
                )
                result.at[index, "day"] = official_day
                counts["loss"] += 1
                pending = False
                break
            pending = True
            break
        if pending:
            counts["pending"] += 1
            if uid:
                pending_users.add(uid)

    result["players"] = [
        _with_day1_bye(players, bool(marked) or bool(flag))
        for players, marked, flag in zip(
            result["players"], had_day1_bye, result["first_day_bye"]
        )
    ]

    # Sync numeric status codes used by compute_live_ranking
    if "status" in result.columns:
        result["status"] = result["fill_status"].map(
            lambda s: FILL_TO_STATUS.get(str(s), 2)
        )

    return result, counts, bye_users, pending_users, backup_events


def settle_tour_scores(
    score_df: Optional[pd.DataFrame],
    submission_df: Optional[pd.DataFrame],
    draw: DrawStatus | None,
    rank_df: Optional[pd.DataFrame] = None,
) -> tuple[
    Optional[pd.DataFrame], dict[str, int], set[str], int, set[str], list[dict[str, Any]]
]:
    """
    High-level entry: ensure score table → settle → return play day.

    Returns ``(score_df, counts, bye_users, play_day, pending_users, backup_events)``.
    """
    detail_rows = submission_to_detail_rows(submission_df)
    ensured = ensure_score_df(score_df, submission_df)
    if ensured is None:
        return (
            None,
            {"win": 0, "loss": 0, "pending": 0, "suicide": 0, "bye": 0},
            set(),
            0,
            set(),
            [],
        )

    ranks = rank_by_id_from_df(rank_df)
    settled, counts, bye_users, pending_users, backup_events = apply_live_settlement(
        ensured, detail_rows, draw, ranks
    )
    play_day = current_play_day(draw, detail_rows)
    if any(counts.values()):
        logger.info(
            "Live settlement: "
            f"win={counts['win']} loss={counts['loss']} "
            f"bye={counts['bye']} suicide={counts['suicide']} "
            f"pending={counts['pending']} play_day={play_day}"
        )
    if backup_events:
        logger.info(
            "Backup activations: "
            f"{len(backup_events)} "
            f"({', '.join(sorted({e.get('primary','') for e in backup_events}))})"
        )
    return settled, counts, bye_users, play_day, pending_users, backup_events

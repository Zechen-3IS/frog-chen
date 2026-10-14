from __future__ import annotations

import re
from typing import Literal

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────
TourType = Literal["WTA", "ATP"]
GRAND_SLAMS = {"澳网", "法网", "温网", "美网"}
WTA1000_COMBINED = {
    "印第安维尔斯",
    "迈阿密",
    "马德里",
    "罗马",
    "蒙特利尔",
    "多伦多",
    "辛辛那提",
    "北京",
}
WTA1000_NON_COMBINED = {"多哈", "迪拜", "武汉"}
WTA_YEAR_END_FINAL = {"利雅得"}

ATP_MANDATORY = {
    "印第安维尔斯",
    "迈阿密",
    "马德里",
    "罗马",
    "蒙特利尔",
    "多伦多",
    "辛辛那提",
    "上海",
    "巴黎",
}
ATP_YEAR_END_FINALS = {"都灵"}

WTA_SPECIALS = (
    GRAND_SLAMS | WTA1000_COMBINED | WTA1000_NON_COMBINED | WTA_YEAR_END_FINAL
)
ATP_SPECIALS = GRAND_SLAMS | ATP_MANDATORY | ATP_YEAR_END_FINALS

MAX_TOURNAMENTS = 18
MIN_COMBINED = 6
MIN_NON_COMBINED = 1
MIN_MANDATORY = 5  # ATP


def _split_zeros_nonzeros(values: list[int]) -> tuple[list[int], list[int]]:
    """Split a list into zero and non-zero (descending) sub-lists."""
    zeros = [v for v in values if v == 0]
    nonzeros = sorted([v for v in values if v > 0], reverse=True)
    return zeros, nonzeros


def _mandatory_slots(values: list[int], min_slots: int) -> tuple[list[int], list[int]]:
    """
    Given attended scores and a minimum slot count:
        - 0s are always mandatory first.
        - Remaining slots (up to min_slots) filled by highest non-zero scores.
        - Scores beyond min_slots go to the optional pool.
    Returns (mandatory, optional).
    """

    zeros, nonzeros = _split_zeros_nonzeros(values)
    remaining = max(0, min_slots - len(zeros))
    mandatory = zeros + nonzeros[:remaining]
    optional = nonzeros[remaining:]
    return mandatory, optional


def _mandatory_slots_with_names(
    tournament_scores: dict[str, int], min_slots: int
) -> tuple[dict[str, int], dict[str, int]]:
    """
    Named variant of _mandatory_slots.

    Returns:
        (mandatory_dict, optional_dict)
    """
    zeros = sorted(
        [(name, pts) for name, pts in tournament_scores.items() if pts == 0],
        key=lambda x: x[0],
    )
    nonzeros = sorted(
        [(name, pts) for name, pts in tournament_scores.items() if pts > 0],
        key=lambda x: (-x[1], x[0]),
    )

    remaining = max(0, min_slots - len(zeros))
    mandatory = zeros + nonzeros[:remaining]
    optional = nonzeros[remaining:]

    return dict(mandatory), dict(optional)


def parse_events(s: str) -> dict[str, int]:
    """Parse details string into {tournament: points}.

    Supports both formats:
    - 【赛事(分数)】 -> points=int(分数)
    - 【赛事】 -> points=0
    """
    # normalize non-string inputs (NaN/None/etc.)
    if not isinstance(s, str):
        if pd.isna(s):
            s = ""
        else:
            s = str(s)

    # Step 1: tokenize by each full bracket block first, to avoid cross-token capture
    # such as: 【印第安维尔斯】 【罗马(390)】 being merged incorrectly.
    block_pattern = re.compile(r"【([^】]*)】")
    # Step 2: parse each token block as "event" or "event(points)"
    event_pattern = re.compile(r"^\s*(.*?)\s*(?:\((\d+)\))?\s*$")
    parsed: dict[str, int] = {}

    for block in block_pattern.findall(s or ""):
        m = event_pattern.match(block)
        if not m:
            continue
        event_raw, points_raw = m.groups()
        event = (event_raw or "").strip()
        if not event:
            continue
        points = int(points_raw) if points_raw else 0

        # Keep non-zero score if same event appears in mixed formats.
        if event in parsed:
            parsed[event] = max(parsed[event], points)
        else:
            parsed[event] = points

    return parsed


def _calculate_points_wta(tournament_scores: dict):
    """
    Calculate WTA ranking points based on tournament results.

    Args:
        tournament_scores: dict where key is tournament name and value is points earned.
                        A value of 0 means the player attended but earned 0 points
                        (mandatory 0 — counts as a used slot).
                        Absent keys mean the player did not attend.

    Returns:
        dict with total points and a detailed breakdown
    """
    # Step 1: Year-end Final (bonus on top of 18, never part of the 18)
    year_end_results = {
        k: v for k, v in tournament_scores.items() if k in WTA_YEAR_END_FINAL
    }
    year_end_points = sum(year_end_results.values())

    # Step 2: Grand Slams (only count attended ones; absent = no slot used)
    grand_slam_results = {
        k: v for k, v in tournament_scores.items() if k in GRAND_SLAMS
    }
    grand_slam_points = sum(grand_slam_results.values())
    slam_count = len(grand_slam_results)

    # Step 3: WTA-1000 Combined
    # Rules:
    #   0-point entries are mandatory and consume a slot first.
    #   After placing all 0s, fill remaining mandatory slots with the
    #     highest non-zero scores (up to MIN_COMBINED total slots).
    #   Attended tournaments beyond MIN_COMBINED flow to the optional pool.
    combined_results = {
        k: v for k, v in tournament_scores.items() if k in WTA1000_COMBINED
    }
    mandatory_combined_named, opt_c_named = _mandatory_slots_with_names(
        combined_results, MIN_COMBINED
    )
    mandatory_count_combined = len(mandatory_combined_named)

    # Step 4: WTA-1000 Non-Combined
    # Same rule: 0-point entries are mandatory first, then top scores fill the rest.
    non_combined_results = {
        k: v for k, v in tournament_scores.items() if k in WTA1000_NON_COMBINED
    }
    mandatory_non_combined_named, opt_nc_named = _mandatory_slots_with_names(
        non_combined_results, MIN_NON_COMBINED
    )
    mandatory_count_non_combined = len(mandatory_non_combined_named)

    # Step 5: Fill remaining slots with best from optional pool
    # Optional pool = leftover WTA1000 scores + all genuinely "other" tournaments
    mandatory_slots_used = (
        slam_count + mandatory_count_combined + mandatory_count_non_combined
    )
    remaining_slots = MAX_TOURNAMENTS - mandatory_slots_used

    optional_pool: list[tuple[str, int]] = list(opt_c_named.items()) + list(
        opt_nc_named.items()
    )
    for name, pts in tournament_scores.items():
        if name not in WTA_SPECIALS:
            optional_pool.append((name, pts))
    optional_pool.sort(key=lambda x: (-x[1], x[0]))
    best_others_named = dict(optional_pool[:remaining_slots])

    # Step 6: Total
    total = (
        year_end_points
        + grand_slam_points
        + sum(mandatory_combined_named.values())
        + sum(mandatory_non_combined_named.values())
        + sum(best_others_named.values())
    )

    counted_tournaments = {
        **year_end_results,
        **grand_slam_results,
        **mandatory_combined_named,
        **mandatory_non_combined_named,
        **best_others_named,
    }

    return {
        "tour": "WTA",
        "total_points": total,
        "counted_tournaments": dict(
            sorted(counted_tournaments.items(), key=lambda x: (-x[1], x[0]))
        ),
        "breakdown": {
            "year_end_final": {
                "tournaments": year_end_results,
                "points": year_end_points,
            },
            "grand_slams": {
                "tournaments": grand_slam_results,
                "points": grand_slam_points,
                "slots_used": slam_count,
            },
            "wta1000_combined": {
                "tournaments": dict(
                    sorted(combined_results.items(), key=lambda x: x[1], reverse=True)
                ),
                "counted_tournaments": mandatory_combined_named,
                "slots_used": mandatory_count_combined,
                "points": sum(mandatory_combined_named.values()),
            },
            "wta1000_non_combined": {
                "tournaments": dict(
                    sorted(
                        non_combined_results.items(), key=lambda x: x[1], reverse=True
                    )
                ),
                "counted_tournaments": mandatory_non_combined_named,
                "slots_used": mandatory_count_non_combined,
                "points": sum(mandatory_non_combined_named.values()),
            },
            "others": {
                "slots_available": remaining_slots,
                "tournaments_counted": best_others_named,
                "points_counted": list(best_others_named.values()),
                "points": sum(best_others_named.values()),
            },
        },
    }


def _calculate_points_atp(tournament_scores: dict):
    """
    Calculate ATP ranking points.

    tournament_scores: key = tournament name, value = points earned.
        A value of 0 means attended with 0 points (mandatory 0, uses a slot).
        Absent key means did not attend (no slot used).
    """
    # Step 1: Year-end Final (bonus, not part of the 18)
    year_end_results = {
        k: v for k, v in tournament_scores.items() if k in ATP_YEAR_END_FINALS
    }
    year_end_points = sum(year_end_results.values())

    # Step 2: Grand Slams
    grand_slam_results = {
        k: v for k, v in tournament_scores.items() if k in GRAND_SLAMS
    }
    grand_slam_points = sum(grand_slam_results.values())
    slam_count = len(grand_slam_results)

    # Step 3: ATP Mandatory tournaments (must count at least 5; 0s are mandatory)
    mandatory_results = {
        k: v for k, v in tournament_scores.items() if k in ATP_MANDATORY
    }
    mandatory_atp_named, opt_mandatory_named = _mandatory_slots_with_names(
        mandatory_results, MIN_MANDATORY
    )
    mandatory_count_atp = len(mandatory_atp_named)

    # Step 4: Optional pool → fill remaining slots
    mandatory_slots_used = slam_count + mandatory_count_atp
    remaining_slots = MAX_TOURNAMENTS - mandatory_slots_used

    optional_pool: list[tuple[str, int]] = list(opt_mandatory_named.items())
    for name, pts in tournament_scores.items():
        if name not in ATP_SPECIALS:
            optional_pool.append((name, pts))
    optional_pool.sort(key=lambda x: (-x[1], x[0]))
    best_others_named = dict(optional_pool[:remaining_slots])

    # Step 5: Total
    total = (
        year_end_points
        + grand_slam_points
        + sum(mandatory_atp_named.values())
        + sum(best_others_named.values())
    )
    counted_tournaments = {
        **year_end_results,
        **grand_slam_results,
        **mandatory_atp_named,
        **best_others_named,
    }

    return {
        "tour": "ATP",
        "total_points": total,
        "counted_tournaments": dict(
            sorted(counted_tournaments.items(), key=lambda x: (-x[1], x[0]))
        ),
        "breakdown": {
            "year_end_final": {
                "tournaments": year_end_results,
                "points": year_end_points,
            },
            "grand_slams": {
                "tournaments": grand_slam_results,
                "points": grand_slam_points,
                "slots_used": slam_count,
            },
            "atp_mandatory": {
                "tournaments": {
                    k: v
                    for k, v in sorted(
                        mandatory_results.items(), key=lambda x: x[1], reverse=True
                    )
                },
                "counted_tournaments": mandatory_atp_named,
                "slots_used": mandatory_count_atp,
                "points": sum(mandatory_atp_named.values()),
            },
            "others": {
                "slots_available": remaining_slots,
                "tournaments_counted": best_others_named,
                "points_counted": list(best_others_named.values()),
                "points": sum(best_others_named.values()),
            },
        },
    }


def print_breakdown(result: dict):
    """Pretty-print the ranking calculation breakdown for both WTA and ATP."""
    tour = result["tour"]
    b = result["breakdown"]

    print("=" * 50)
    print(f"  {tour} TOTAL POINTS: {result['total_points']}")
    print("=" * 50)

    # Year-end Final
    yef = b["year_end_final"]
    print(f"\nYear-End Final: {yef['points']} pts")
    for name, pts in yef["tournaments"].items():
        print(f"  {name}: {pts}")

    # Grand Slams
    gs = b["grand_slams"]
    print(f"\nGrand Slams ({gs['slots_used']} attended): {gs['points']} pts")
    for name, pts in gs["tournaments"].items():
        print(f"  {name}: {pts}")

    # Tour-specific mandatory section(s)
    if tour == "WTA":
        c = b["wta1000_combined"]
        print(f"\nWTA-1000 Combined ({c['slots_used']} slots used): {c['points']} pts")
        for name, pts in c["tournaments"].items():
            print(f"  {name}: {pts}")

        nc = b["wta1000_non_combined"]
        print(
            f"\nWTA-1000 Non-Combined ({nc['slots_used']} slots used): {nc['points']} pts"
        )
        for name, pts in nc["tournaments"].items():
            print(f"  {name}: {pts}")

    elif tour == "ATP":
        am = b["atp_mandatory"]
        print(f"\nATP Mandatory ({am['slots_used']} slots used): {am['points']} pts")
        for name, pts in am["tournaments"].items():
            print(f"  {name}: {pts}")

    # Others
    oth = b["others"]
    print(f"\nOthers ({oth['slots_available']} slots): {oth['points']} pts")
    print(f"  Points counted: {oth['points_counted']}")

    print("=" * 50)


def calculate_points(
    detailed_dict: dict[str, int],
    debugging: bool = False,
    tour: TourType = "WTA",
):
    tour_upper = str(tour).upper()
    if tour_upper == "WTA":
        results = _calculate_points_wta(detailed_dict)
    if tour_upper == "ATP":
        results = _calculate_points_atp(detailed_dict)
    if debugging:
        print_breakdown(results)
    return results

"""Draw /签表 parsing and fetch for live settlement."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from logger import get_logger

logger = get_logger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

DRAW_NAME_PREFIX_RE = re.compile(r"^(?:[WQL]|\d+)\s*")
SEED_PREFIX_RE = re.compile(r"^(\d+)\s*")
DAY_SCORE_RE = re.compile(r"当前分数：(\d+)")
FIRST_DAY_BYE_RE = re.compile(r"本站有(\d+)个首日轮空")
PICK_ROUND_RE = re.compile(r"当前轮次：(\S+)")
PICK_SELECTOR_RE = re.compile(r"Day\s+(\d+)\s+(\d{1,2})/(\d{1,2})")

ROUND_ORDER = {
    "R128": 1,
    "R64": 2,
    "R32": 3,
    "R16": 4,
    "QF": 5,
    "SF": 6,
    "F": 7,
    "W": 8,
    "冠军": 8,
    "决赛": 7,
    "半决赛": 6,
    "四分之一决赛": 5,
}
BRACKET_OPENING_ROUND = {
    128: "R128",
    64: "R64",
    32: "R32",
    16: "R16",
    8: "QF",
}


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def field_bracket_size(n: int) -> int:
    if n <= 1:
        return max(n, 0)
    return 1 << (n - 1).bit_length()


def opening_round_name(n: int) -> str:
    return BRACKET_OPENING_ROUND.get(field_bracket_size(n), "")


def opening_round_rank(n: int) -> int:
    return ROUND_ORDER.get(opening_round_name(n), 0)


@dataclass
class DrawPlayer:
    player_id: str
    name: str
    round: str = ""
    eliminated: bool = False
    live: bool = False
    seed: int | None = None
    bye: bool = False
    # Match score text when eliminated, e.g. ``52 Ret.`` / ``W/O`` / ``64 75``.
    elim_score: str = ""
    # Display name of the opponent who eliminated this player (if known).
    elim_opponent: str = ""

    @property
    def round_rank(self) -> int:
        return ROUND_ORDER.get(self.round, 0)


@dataclass
class DrawStatus:
    by_id: dict[str, DrawPlayer]
    by_name: dict[str, DrawPlayer]
    round_points: dict[str, int] = field(default_factory=dict)
    day_points: list[int] = field(default_factory=list)
    tennis_bye_count: int = 0
    bracket_size: int = 0
    first_day_bye_quota: int = 0
    is_slam: bool = False
    pick_days: list[dict[str, Any]] = field(default_factory=list)

    def lookup(self, player_id: str | None, name: str | None) -> DrawPlayer | None:
        pid = str(player_id or "").strip()
        if pid and pid != "0" and pid in self.by_id:
            return self.by_id[pid]
        label = str(name or "").strip()
        if label and label in self.by_name:
            return self.by_name[label]
        return None


# Set tokens in live-tennis score cells: ``63``, ``76(4)``, ``6-3``, ``5:2`` …
_SCORE_TOKEN_RE = re.compile(
    r"\d+-\d+(?:\(\d+\))?|\d+:\d+(?:\(\d+\))?|\d\d(?:\(\d+\))?"
)
_WO_RE = re.compile(r"\bW\s*/\s*O\b|\bWO\b", re.I)
_RET_RE = re.compile(r"\bRet\.?\b", re.I)


# Live game-point values (not set games). ``15:0`` after set 1 means set 2 started.
_GAME_POINT_VALUES = frozenset({15, 30, 40})


def _set_token_complete(token: str) -> bool | None:
    """Whether a single set token is a finished set. None if unparseable."""
    text = str(token or "").strip()
    if not text:
        return None
    m = re.fullmatch(r"(\d+)[-:](\d+)(?:\((\d+)\))?", text)
    if not m:
        m = re.fullmatch(r"(\d)(\d)(?:\((\d+)\))?", text)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if a > 20 or b > 20:
        return None
    # ``15:0`` / ``30-0`` are game points inside a set, not a finished set.
    if a in _GAME_POINT_VALUES or b in _GAME_POINT_VALUES:
        return False
    if max(a, b) >= 6 and abs(a - b) >= 2:
        return True
    if max(a, b) >= 7:  # 7-6 / 7-5
        return True
    return False


def score_tokens(score_text: str) -> list[str]:
    return _SCORE_TOKEN_RE.findall(str(score_text or ""))


def retirement_backup_allowed(score_text: str) -> bool:
    """
    True when primary-pick retirement/walkover happened before set 1 finished.

    Rules (survivor):
    - ``W/O`` → backup allowed
    - Incomplete first set only (e.g. ``41``, ``52``, ``52 Ret.``) → allowed
    - First set finished, or set 2 started (e.g. ``64 Ret.``, ``63 15``,
      ``63 15:0 Ret.``, ``63 22 Ret.``) → not allowed
    """
    text = " ".join(str(score_text or "").split())
    if not text:
        return False
    has_wo = bool(_WO_RE.search(text))
    has_ret = bool(_RET_RE.search(text))
    body = _RET_RE.sub(" ", text)
    body = _WO_RE.sub(" ", body)
    body = " ".join(body.split())
    tokens = score_tokens(body)
    # Bare walkover / retirement, before any set is recorded.
    if not tokens:
        return has_wo or has_ret
    # Set 2 started or finished (``64 Ret.``, ``63 15``, ``63 64``) → no backup.
    if len(tokens) >= 2:
        return False
    first = _set_token_complete(tokens[0])
    if first is True:
        return False  # first set completed (e.g. ``64 Ret.``)
    if first is False:
        return True  # incomplete first set (e.g. ``41``, ``52``, ``52 Ret.``)
    return has_ret or has_wo


def _score_candidate_rank(text: str) -> tuple:
    """Lower tuple wins when choosing among score cells in one gutter.

    A finished score beats a conflicting Ret. / W/O. Those markers have been
    copied in from a neighbouring match (哈恰诺夫 ``63 64`` vs ``W/O``,
    鲁德 ``46 64 63`` vs ``52 Ret.``).
    """
    tokens = score_tokens(text)
    early = retirement_backup_allowed(text)
    completed = 0 if tokens and not early else 1
    return (completed, -len(tokens), len(text))


def _score_candidates_in_column(
    group: list[list[dict[str, Any]]], score_col: int
) -> list[str]:
    candidates: list[str] = []
    for cells in group:
        if score_col >= len(cells):
            continue
        cell = cells[score_col]
        if cell.get("players"):
            continue
        text = " ".join(str(cell.get("text") or "").split())
        if not text:
            continue
        # Skip live odds / clock fragments (e.g. ``8:3`` betting lines).
        if ":" in text and not score_tokens(text) and not _WO_RE.search(text):
            continue
        if _WO_RE.search(text) or _RET_RE.search(text) or score_tokens(text):
            candidates.append(text)
    return candidates


def _score_text_from_match_group(
    group: list[list[dict[str, Any]]], col: int
) -> str:
    """Best score / Ret / W/O text for the match at player column ``col``.

    The gutter after this round (``col+1``) is this match. Earlier columns in
    the same block are previous-round scores (e.g. 鲁德 d. 阿利亚西姆 ``52 Ret.``
    sitting beside 霍达尔 d. 鲁德 ``46 64 63``). Do not let that earlier Ret
    replace a score already written for this round.
    """
    candidates: list[str] = []
    for score_col in (col + 1, col, col - 1):
        if score_col < 0:
            continue
        found = _score_candidates_in_column(group, score_col)
        if found:
            candidates = found
            break
    if not candidates:
        return ""
    return sorted(set(candidates), key=_score_candidate_rank)[0]


def assign_draw_byes(players: dict[str, DrawPlayer] | list[DrawPlayer]) -> None:
    items = list(players.values()) if isinstance(players, dict) else list(players)
    n_byes = field_bracket_size(len(items)) - len(items)
    if n_byes <= 0:
        return
    ranked = sorted(
        (player for player in items if player.seed), key=lambda player: player.seed or 0
    )
    for player in ranked[:n_byes]:
        player.bye = True


def _parse_seed_and_name(text: str) -> tuple[int | None, str]:
    text = " ".join(str(text or "").split())
    match = SEED_PREFIX_RE.match(text)
    if match:
        return int(match.group(1)), text[match.end() :].strip()
    return None, DRAW_NAME_PREFIX_RE.sub("", text).strip()


def _clean_draw_name(tag) -> str:
    return _parse_seed_and_name(tag.get_text(" ", strip=True))[1]


def _draw_row_cells(tr) -> list[dict[str, Any]]:
    cells = []
    for td in tr.find_all("td", recursive=False):
        classes = td.get("class") or []
        if "cDrawSeq" in classes:
            continue
        pnames = td.select("pname")
        players = []
        for pname in pnames:
            pid = str(pname.get("data-id") or "").strip()
            if not pid or pid in {"LIVE", "0"}:
                continue
            players.append((pid, _clean_draw_name(pname)))
        text = " ".join(td.get_text(" ", strip=True).split())
        cells.append(
            {
                "players": players,
                "live": "进行中" in text
                or any(p.get("data-id") == "LIVE" for p in pnames),
                "text": text,
            }
        )
    return cells


def _first_player_in_rows(
    rows: list[list[dict[str, Any]]], col: int
) -> tuple[str, str] | None:
    for cells in rows:
        if col < len(cells) and cells[col]["players"]:
            return cells[col]["players"][0]
    return None


def _live_pairs_from_table(
    table,
) -> list[tuple[tuple[str, str] | None, tuple[str, str] | None]]:
    body = table.find("tbody") or table
    rows = [_draw_row_cells(tr) for tr in body.find_all("tr", recursive=False)]
    if not rows:
        rows = [_draw_row_cells(tr) for tr in table.select("tr")]
    pairs = []
    for index, cells in enumerate(rows):
        for col, cell in enumerate(cells):
            if not cell["live"]:
                continue
            # 「进行中」在对手格只表示下一轮未产生，不代表此侧正在打球
            if cell["players"] or col == 0:
                continue
            player_col = col - 1 if col > 0 else 0
            span = 2 ** (player_col + 1)
            start = (index // span) * span
            group = rows[start : start + span]
            if len(group) < span:
                continue
            half = span // 2
            left = _first_player_in_rows(group[:half], player_col)
            right = _first_player_in_rows(group[half:], player_col)
            if not left or not right:
                continue
            if left[0] in {"LIVE", "COMEUP"} or right[0] in {"LIVE", "COMEUP"}:
                continue
            pairs.append((left, right))
    return pairs


def _completed_matches_from_table(table) -> list[dict[str, str]]:
    """Finished matches in one bracket block: both sides present + winner advanced."""
    body = table.find("tbody") or table
    rows = [_draw_row_cells(tr) for tr in body.find_all("tr", recursive=False)]
    if not rows:
        rows = [_draw_row_cells(tr) for tr in table.select("tr")]
    if not rows:
        return []
    n_cols = max((len(r) for r in rows), default=0)
    out: list[dict[str, str]] = []
    for col in range(max(n_cols - 1, 0)):
        span = 2 ** (col + 1)
        for start in range(0, len(rows), span):
            if start + span > len(rows):
                break
            group = rows[start : start + span]
            half = span // 2
            left = _first_player_in_rows(group[:half], col)
            right = _first_player_in_rows(group[half:], col)
            winner = _first_player_in_rows(group, col + 1)
            if not left or not right or not winner:
                continue
            if left[0] in {"LIVE", "COMEUP"} or right[0] in {"LIVE", "COMEUP"}:
                continue
            if winner[0] in {"LIVE", "COMEUP"}:
                continue
            left_name = str(left[1] or "").strip()
            right_name = str(right[1] or "").strip()
            win_name = str(winner[1] or "").strip()
            if not left_name or not right_name or not win_name:
                continue
            if win_name == left_name:
                loser_name = right_name
            elif win_name == right_name:
                loser_name = left_name
            else:
                continue
            if loser_name == win_name:
                continue
            score = _score_text_from_match_group(group, col)
            out.append(
                {
                    "left": left_name,
                    "right": right_name,
                    "winner": win_name,
                    "loser": loser_name,
                    "score": score,
                }
            )
    return out


def parse_completed_matches(html: str, tour: str) -> list[dict[str, str]]:
    """
    Parse finished singles matches from draw ajax HTML.

    Each item: ``{left, right, winner, loser, score}`` (display names).
    """
    tour = str(tour or "").strip().upper()
    if tour not in {"MS", "WS"}:
        return []
    soup = BeautifulSoup(html, "html.parser")
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for part in soup.select(".cDrawPart"):
        if part.get("data-id") != tour:
            continue
        for table in part.select("table.cDrawBlock"):
            for match in _completed_matches_from_table(table):
                key = (match["winner"], match["loser"])
                prev = by_key.get(key)
                if prev is None:
                    by_key[key] = match
                    continue
                preferred = _prefer_elim_score(prev.get("score") or "", match.get("score") or "")
                if preferred != str(prev.get("score") or "").strip():
                    by_key[key] = match
                elif not str(prev.get("score") or "").strip() and str(match.get("score") or "").strip():
                    by_key[key] = match
    return list(by_key.values())


def _prefer_elim_score(prev: str, new: str) -> str:
    """Resolve duplicate bracket scores for the same loser (summary vs detail blocks)."""
    a = str(prev or "").strip()
    b = str(new or "").strip()
    if not a:
        return b
    if not b:
        return a
    a_tokens = score_tokens(a)
    b_tokens = score_tokens(b)
    a_early = retirement_backup_allowed(a)
    b_early = retirement_backup_allowed(b)
    a_done = bool(a_tokens) and not a_early
    b_done = bool(b_tokens) and not b_early
    # Duplicate blocks sometimes attach another match's Ret. / W/O. A finished
    # score stays; a real early retirement is kept only when it is the score
    # this match actually has.
    if a_done and not b_done:
        return a
    if b_done and not a_done:
        return b
    if len(b_tokens) > len(a_tokens):
        return b
    if len(a_tokens) > len(b_tokens):
        return a
    return a


def _annotate_elim_scores(status: DrawStatus, soup: BeautifulSoup, tour: str) -> None:
    """Attach bracket score text to eliminated players (for retirement backup)."""
    tour = str(tour or "").strip().upper()
    for player in status.by_id.values():
        player.elim_score = ""
        player.elim_opponent = ""
    for part in soup.select(".cDrawPart"):
        if part.get("data-id") != tour:
            continue
        for table in part.select("table.cDrawBlock"):
            for match in _completed_matches_from_table(table):
                score = str(match.get("score") or "").strip()
                if not score:
                    continue
                loser = status.lookup(None, match.get("loser"))
                if loser is None or not loser.eliminated:
                    continue
                prev = str(loser.elim_score or "").strip()
                preferred = _prefer_elim_score(prev, score)
                winner = str(match.get("winner") or "").strip()
                if preferred != prev:
                    loser.elim_score = preferred
                    # Opponent follows the score we kept.
                    if preferred == score and winner:
                        loser.elim_opponent = winner
                elif not loser.elim_opponent and winner:
                    loser.elim_opponent = winner


def fetch_draw_matches(
    event_id: str | int,
    year: str | int,
    tour: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: int = 60,
) -> list[dict[str, str]]:
    """Fetch draw ajax and return completed match list (no survivor my-page)."""
    tour = str(tour).strip().upper()
    if tour not in {"MS", "WS"}:
        return []
    sess = session or requests.Session()
    draw_url = (
        f"https://www.live-tennis.cn/zh/draw/ajax/"
        f"{event_id}/{year}/device/0/horizontal/true"
    )
    try:
        html = sess.get(
            draw_url,
            headers={
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://www.live-tennis.cn/zh/draw/{event_id}/{year}",
            },
            timeout=timeout,
        ).text
    except requests.RequestException as err:
        logger.warning(f"Draw match fetch failed for {event_id}: {err}")
        return []
    return parse_completed_matches(html, tour)


def _parse_round_points(soup: BeautifulSoup, gender: str) -> dict[str, int]:
    pap = soup.find("div", class_="cDrawPart", attrs={"data-id": "PAP"})
    if not pap:
        return {}
    table = pap.find(
        "table", class_="cDrawPointAndPrizeTable", attrs={"data-id": gender}
    )
    if not table:
        return {}
    points: dict[str, int] = {}
    for row in table.select("tbody tr"):
        cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
        if len(cells) < 2 or not cells[0]:
            continue
        try:
            points[cells[0]] = int(cells[1].replace(",", ""))
        except ValueError:
            continue
    return points


def parse_draw_status(html: str, gender: str) -> DrawStatus:
    gender = str(gender).strip().upper()
    soup = BeautifulSoup(html, "html.parser")
    part_id = f"{gender}_ENTRY"
    entry = soup.find("div", class_="cDrawPart", attrs={"data-id": part_id})
    by_id: dict[str, DrawPlayer] = {}
    if entry:
        for item in entry.select(".cDrawEntry"):
            player_id = ""
            img = item.select_one(".cDrawEntryPortraitImg")
            if img and img.get("data-original"):
                player_id = str(img["data-original"]).rstrip("/").split("/")[-1]
            name_el = item.select_one(".cDrawEntryPlayer")
            seed, name = _parse_seed_and_name(
                name_el.get_text(" ", strip=True) if name_el else ""
            )
            round_el = item.select_one(".cDrawEntryRank")
            round_name = round_el.get_text(strip=True) if round_el else ""
            eliminated = bool(item.select_one(".cDrawEntryEliminated"))
            if not player_id and not name:
                continue
            player = DrawPlayer(
                player_id=player_id,
                name=name,
                round=round_name,
                eliminated=eliminated,
                seed=seed,
            )
            if player_id:
                by_id[player_id] = player
    live_ids: set[str] = set()
    live_names: set[str] = set()
    for part in soup.select(".cDrawPart"):
        if part.get("data-id") != gender:
            continue
        for table in part.select("table.cDrawBlock"):
            for left, right in _live_pairs_from_table(table):
                for item in (left, right):
                    if not item:
                        continue
                    live_ids.add(item[0])
                    if item[1]:
                        live_names.add(item[1])
    for player in by_id.values():
        if player.player_id in live_ids or player.name in live_names:
            player.live = True
    for part in soup.select(".cDrawPart"):
        if part.get("data-id") != gender:
            continue
        for pname in part.select("pname"):
            pid = str(pname.get("data-id") or "").strip()
            player = by_id.get(pid)
            if player is None:
                continue
            seed, name = _parse_seed_and_name(pname.get_text(" ", strip=True))
            if seed and not player.seed:
                player.seed = seed
            if name and not player.name:
                player.name = name
    assign_draw_byes(by_id)
    by_name = {player.name: player for player in by_id.values() if player.name}
    status = DrawStatus(
        by_id=by_id, by_name=by_name, round_points=_parse_round_points(soup, gender)
    )
    _annotate_elim_scores(status, soup, gender)
    return status


def parse_pick_days(html: str, year: str | int | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    year_int = int(year) if str(year or "").isdigit() else beijing_now().year
    by_day: dict[int, dict[str, Any]] = {}
    for selector in soup.select(".cSurvivorDayPickSelector"):
        text = selector.get_text(" ", strip=True)
        match = PICK_SELECTOR_RE.search(text)
        if not match:
            continue
        day = int(match.group(1))
        date = datetime(year_int, int(match.group(2)), int(match.group(3))).date()
        by_day[day] = {
            "day": day,
            "date": date,
            "round": "",
            "open": False,
            "has_cards": False,
        }
    for info in soup.select(".cSurvivorDayPickInfo"):
        cards = info.select(".cSurvivorSmallCard, .cSurvivorCard")
        card_days = [
            int(card.get("data-day") or 0) for card in cards if card.get("data-day")
        ]
        card_dates = [card.get("data-date") for card in cards if card.get("data-date")]
        fillable = {str(card.get("data-fillable") or "") for card in cards}
        notice = " ".join(
            node.get_text(" ", strip=True)
            for node in info.select(".cSurvivorFillNotice")
        )
        round_match = PICK_ROUND_RE.search(notice)
        day = card_days[0] if card_days else int(info.get("data-id") or 0) + 1
        item = by_day.setdefault(
            day,
            {"day": day, "date": None, "round": "", "open": False, "has_cards": False},
        )
        if card_dates and not item.get("date"):
            try:
                item["date"] = datetime.strptime(card_dates[0][:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        if round_match:
            item["round"] = round_match.group(1).strip()
        item["has_cards"] = bool(cards)
        item["open"] = item["open"] or ("0" in fillable or "1" in fillable)
    return [by_day[day] for day in sorted(by_day)]


def fetch_draw_status(
    event_id: str | int,
    year: str | int,
    tour: str,
    *,
    is_slam: bool = False,
    session: Optional[requests.Session] = None,
    timeout: int = 60,
) -> DrawStatus:
    """
    Fetch签表 + survivor my-page metadata (day points, bye quota, pick days).

    ``tour`` must be ``MS`` or ``WS``.
    """
    tour = str(tour).strip().upper()
    if tour not in {"MS", "WS"}:
        raise ValueError("tour must be 'MS' or 'WS'")

    sess = session or requests.Session()
    draw_url = (
        f"https://www.live-tennis.cn/zh/draw/ajax/"
        f"{event_id}/{year}/device/0/horizontal/true"
    )
    try:
        html = sess.get(
            draw_url,
            headers={
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://www.live-tennis.cn/zh/draw/{event_id}/{year}",
            },
            timeout=timeout,
        ).text
    except requests.RequestException as err:
        logger.warning(f"Draw fetch failed for {event_id}: {err}")
        return DrawStatus(by_id={}, by_name={})

    status = parse_draw_status(html, tour)
    field = len(status.by_id)
    status.bracket_size = field_bracket_size(field)
    status.tennis_bye_count = max(status.bracket_size - field, 0)
    status.is_slam = bool(is_slam)

    my_url = (
        f"https://www.live-tennis.cn/zh/survivor/event/"
        f"{event_id}/{year}/{tour}/my"
    )
    try:
        my_html = sess.get(
            my_url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        ).text
    except requests.RequestException as err:
        logger.warning(f"Survivor my-page fetch failed for {event_id}: {err}")
        my_html = ""

    if my_html:
        status.day_points = [int(value) for value in DAY_SCORE_RE.findall(my_html)]
        notice = FIRST_DAY_BYE_RE.search(my_html)
        if notice:
            status.first_day_bye_quota = int(notice.group(1))
        status.pick_days = parse_pick_days(my_html, year)

    live_n = sum(1 for p in status.by_id.values() if p.live)
    elim_n = sum(1 for p in status.by_id.values() if p.eliminated)
    logger.info(
        f"Draw {event_id}/{tour}: {field} players, "
        f"elim={elim_n}, live={live_n}, "
        f"bye_quota={status.first_day_bye_quota or status.tennis_bye_count}"
    )
    return status

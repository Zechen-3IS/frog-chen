from __future__ import annotations

from datetime import date as _date
from geopy.geocoders import Nominatim
import html as html_lib
from logger import get_logger
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import RequestException
import time
from typing import Dict, List, Tuple, Optional

logger = get_logger(__name__)

RANK_PAGE_URL = "https://www.live-tennis.cn/zh/survivor/rank/"
EVENT_BASE_URL = "https://www.live-tennis.cn/zh/survivor/event/"
CALENDAR_YEAR = 2026
CALENDAR_URL = f"https://www.live-tennis.cn/zh/survivor/calendar/{CALENDAR_YEAR}"
FETCH_ALL = True  # True: fetch all pages; False: first page only
PAGE_SIZE = 100  # DataTables page length
DEVICE = "pc"  # matches site request payload
DRAW = "1"  # matches site request payload

MAX_RETRIES = 5
REQUEST_TIMEOUT = 90
RETRY_BACKOFF = 1.5

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

INT_COLS = {
    "rank": ["rank", "event_num", "title_num", "score"],
    "submission": ["status", "normal_match_id", "normal_match_id_alt"],
    "score": ["status", "day", "score"],
    "race": ["rank", "event_num", "title_num", "score"],
}


def _request_with_retry(
    session: Session, method: str, url: str, **kwargs
) -> requests.Response:
    """HTTP request with simple retry/backoff for transient failures."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.request(
                method=method, url=url, timeout=REQUEST_TIMEOUT, **kwargs
            )
            if resp.status_code >= 500:
                raise RequestException(f"Server error status: {resp.status_code}")
            return resp
        except RequestException as err:
            last_err = err
            if attempt == MAX_RETRIES:
                break
            sleep_s = RETRY_BACKOFF * attempt
            logger.warning(
                f"Request failed (attempt {attempt}/{MAX_RETRIES}): {err}. Retrying in {sleep_s:.1f}s..."
            )

    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {last_err}")


def _extract_csrf_token(page_html: str) -> str:
    """
    Extract the CSRF token from a page's HTML content.

    Searches for a meta tag of the form:
        <meta name="_token" content="<token>">

    Args:
        page_html: Raw HTML string of the page to parse.

    Returns:
        The CSRF token string found in the meta tag's content attribute.

    Raises:
        RuntimeError: If no matching meta tag is found, indicating the page
            structure may have changed.
    """

    m = re.search(
        r"<meta\s+name=[\"\']_token[\"\']\s+content=[\"\']([^\"\']+)[\"\']", page_html
    )
    if not m:
        raise RuntimeError(
            "Could not find CSRF token in page HTML. The page structure may have changed."
        )
    return m.group(1)


def _strip_html(text: str) -> str:
    """
    Remove HTML tags from a string and decode HTML entities.

    Converts <br> tags to newlines, strips all other HTML tags,
    and unescapes HTML entities (e.g. &amp; -> &).

    Args:
        text: Input string, possibly containing HTML. If None, returns "".

    Returns:
        Plain text string with HTML removed and entities decoded.
    """

    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html_lib.unescape(text).strip()


def _extract_api_url(page_html: str) -> str:
    """Extract DataTables ajax URL from inline scripts."""
    patterns = [
        r'"ajax"\s*:\s*\{[^{}]*url\s*:\s*"(https://www\.live-tennis\.cn/zh/survivor/event/[^"]+)"',
        r'"ajax"\s*:\s*\{[^{}]*"url"\s*:\s*"(https://www\.live-tennis\.cn/zh/survivor/event/[^"]+)"',
        r'"ajax"\s*:\s*\{[^{}]*url\s*:\s*"(/zh/survivor/event/[^"]+)"',
        r'"ajax"\s*:\s*\{[^{}]*"url"\s*:\s*"(/zh/survivor/event/[^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, page_html, flags=re.S)
        if m:
            u = m.group(1)
            if u.startswith("/"):
                u = f"https://www.live-tennis.cn{u}"
            return u

    raise RuntimeError(
        "Could not find DataTables API URL from page source. "
        "Likely login required, or page script changed."
    )


def _build_survivor_event_url(
    event_id: int | str, year: int | str, tour: str
) -> Dict[str, str]:
    tour = str(tour).strip().upper()
    if tour not in {"WS", "MS"}:
        raise ValueError("tour must be 'WS' or 'MS'")
    return {
        "score": f"{EVENT_BASE_URL}{event_id}/{year}/{tour}/score",
        "submission": f"{EVENT_BASE_URL}{event_id}/{year}/{tour}/detail",
    }


def _build_survivor_rank_url(tour: str, race: bool = False) -> Dict[str, str]:
    tour = str(tour).strip().upper()
    if tour not in {"WS", "MS"}:
        raise ValueError("tour must be 'WS' or 'MS'")
    api_indicator = 1 if tour == "MS" else 2
    if race:
        return {
            "page": f"{RANK_PAGE_URL}{tour}/race",
            "api": f"{RANK_PAGE_URL}{api_indicator}/race",
        }
    else:
        return {
            "page": f"{RANK_PAGE_URL}{tour}/year",
            "api": f"{RANK_PAGE_URL}{api_indicator}/year",
        }


def _create_nullable_int_col(option: str, df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy[INT_COLS[option]] = df_copy[INT_COLS[option]].astype("Int64")
    return df_copy


def create_session(
    page_url: str, extract_api_url: bool = False
) -> Tuple[Session, str] | Tuple[Session, str, str]:
    """Initialize anonymous session, fetch CSRF token, and optionally extract the API URL."""
    session = requests.Session()
    headers = {"User-Agent": USER_AGENT}

    resp = _request_with_retry(session, "GET", page_url, headers=headers)
    resp.raise_for_status()

    csrf_token = _extract_csrf_token(resp.text)
    if extract_api_url:
        api_url = _extract_api_url(resp.text)
        return session, csrf_token, api_url
    return session, csrf_token


def fetch_datatable_page(
    session: Session,
    csrf_token: str,
    page_url: str,
    api_url: str,
    start: int = 0,
    length: int = 100,
    draw: Optional[str] = None,
) -> Dict:
    """
    Generic DataTables page fetcher with one CSRF-refresh retry.

    Returns:
        dict JSON response, must contain "data" key.
    """
    payload = {
        "device": DEVICE,
        "is_yec": "0",
        "start": str(start),
        "length": str(length),
        "_token": csrf_token,
    }

    if draw is not None:
        payload["draw"] = str(draw)

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": page_url,
        "X-Requested-With": "XMLHttpRequest",
    }

    resp = _request_with_retry(session, "POST", api_url, data=payload, headers=headers)

    # One retry for expired CSRF
    if resp.status_code == 419:
        logger.warning("CSRF expired (419), refreshing token and retrying once...")
        page = _request_with_retry(
            session, "GET", page_url, headers={"User-Agent": USER_AGENT}
        )
        page.raise_for_status()
        new_token = _extract_csrf_token(page.text)
        payload["_token"] = new_token
        resp = _request_with_retry(
            session, "POST", api_url, data=payload, headers=headers
        )

    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, dict) or "data" not in data:
        raise RuntimeError(f"Unexpected API response shape: {data}")

    return data


def fetch_table(option: str, page_size: int = 10000, **kwargs):
    option = option.strip().lower()
    if option not in {"rank", "submission", "score", "race"}:
        raise ValueError("Options must be one of: rank, race, submission or score")
    tour = kwargs.get("tour", "").strip().upper()
    if option == "rank":
        if tour not in {"WS", "MS"}:
            raise ValueError("tour must be 'WS' or 'MS'")
        url_dict = _build_survivor_rank_url(tour)
        session, csrf_token = create_session(url_dict["page"])
        page_url = url_dict["page"]
        api_url = url_dict["api"]
    elif option == "race":
        if tour not in {"WS", "MS"}:
            raise ValueError("tour must be 'WS' or 'MS'")
        url_dict = _build_survivor_rank_url(tour, race=True)
        session, csrf_token = create_session(url_dict["page"])
        page_url = url_dict["page"]
        api_url = url_dict["api"]
    else:
        event_id = kwargs.get("event_id", None)
        year = kwargs.get("year", None)
        if event_id is None:
            raise ValueError("Must give a valid event id")
        if year is None:
            raise ValueError("Must give a valid year")
        url_dict = _build_survivor_event_url(event_id=event_id, year=year, tour=tour)
        page_url = url_dict[option]
        session, csrf_token, api_url = create_session(page_url, extract_api_url=True)

    data = fetch_datatable_page(
        session,
        csrf_token,
        page_url,
        api_url,
        length=page_size,
        draw=DRAW,
    )
    records_total = int(data.get("recordsTotal", len(data.get("data", []))))
    rows = list(data.get("data", []))

    next_start = page_size
    while next_start < records_total:
        chunk = fetch_datatable_page(
            session,
            csrf_token,
            page_url,
            api_url,
            start=next_start,
            length=page_size,
            draw=DRAW,
        )
        chunk_rows = chunk.get("data", [])
        if not chunk_rows:
            break
        rows.extend(chunk_rows)
        next_start += page_size

    df = pd.DataFrame(rows)

    if "username" in df.columns:
        df = df.rename({"username": "username_raw"}, axis=1)
        df["username"] = df["username_raw"].map(_strip_html)
    if "details" in df.columns:
        df["details_text"] = df["details"].map(_strip_html)
    if "players" in df.columns:
        df["players"] = df["players"].str[1:-1].str.split("】 【")

    df = _create_nullable_int_col(option, df)
    return df, records_total


def _parse_calendar_event_url(url: str, language: str) -> dict:
    """
    Parse route shape: /zh/survivor/event/{event_id}/{year}/{tour}/{page_type}
    Keep event_id as string (supports numeric IDs and AO-like IDs).
    """
    out = {
        "event_id": "",
        "event_year": pd.NA,
        "event_tour": "",
        "page_type": "",
    }
    if not url:
        return out

    m = re.search(rf"/{language}/survivor/event/([^/]+)/([^/]+)/([^/]+)/([^/?#]+)", url)
    if not m:
        return out

    out["event_id"] = m.group(1).strip()
    year_raw = m.group(2).strip()
    out["event_year"] = int(year_raw) if year_raw.isdigit() else pd.NA
    out["event_tour"] = m.group(3).strip().upper()
    out["page_type"] = m.group(4).strip().lower()
    return out


# Calendar cell logos: …/level_logo/WTA-500-2025.png, GS-AO.png, ATP-Final-2019.png
_LEVEL_LOGO_STEM_RE = re.compile(r"/level_logo/([^/?#]+)\.png", re.I)
_LEVEL_LOGO_YEAR_SUFFIX_RE = re.compile(r"-\d{4}$")
_LEVEL_LOGO_TO_LABELS: dict[str, tuple[str, str]] = {
    # champion type label, chart bucket (matches tournament_meta.classify_level)
    "WTA-250": ("WTA250", "W250"),
    "WTA-500": ("WTA500", "W500"),
    "WTA-1000": ("WTA1000", "W1000"),
    "ATP-250": ("ATP250", "M250"),
    "ATP-500": ("ATP500", "M500"),
    "ATP-1000": ("ATP1000", "M1000"),
    "WTA-Final": ("年终总决赛", "W1000"),
    "ATP-Final": ("年终总决赛", "M1000"),
    "ITF-OL": ("奥运会", "奥运会"),
}


def parse_survivor_level_logo(src: str) -> tuple[str, str]:
    """Map live-tennis level logo URL → (type label, chart level).

    Levels change by season (e.g. 新加坡 2025=WTA250, 2026=WTA500), so callers
    should persist these on each year's calendar row rather than hard-coding by city.
    """
    if not src:
        return "", ""
    m = _LEVEL_LOGO_STEM_RE.search(str(src))
    if not m:
        return "", ""
    stem = _LEVEL_LOGO_YEAR_SUFFIX_RE.sub("", m.group(1).strip())
    if stem in _LEVEL_LOGO_TO_LABELS:
        return _LEVEL_LOGO_TO_LABELS[stem]
    if stem.startswith("GS-") or stem == "GS":
        return "大满贯", "大满贯"
    return "", ""


def fetch_survivor_calendar_event_df(
    calendar_year: int, language: str = "zh"
) -> tuple[pd.DataFrame, dict]:
    """Fetch and parse the survivor calendar page into a DataFrame of events."""
    calendar_url = (
        f"https://www.live-tennis.cn/{language}/survivor/calendar/{int(calendar_year)}"
    )
    headers = {"User-Agent": USER_AGENT}

    session = requests.Session()
    resp = _request_with_retry(session, "GET", calendar_url, headers=headers)
    resp.raise_for_status()

    from lxml import html as lxml_html

    doc = lxml_html.fromstring(resp.text)

    rows = []
    parse_warnings = []

    calendar_rows = doc.xpath("//div[contains(@class, 'cSurvivorCalendarRow')]")
    for r in calendar_rows:
        mmdd_txt = " ".join(
            " ".join(
                r.xpath(".//div[contains(@class, 'cSurvivorDateColumn')]//text()")
            ).split()
        )
        mmdd_txt = mmdd_txt.replace("/", "-").strip()

        # Construct date using calendar year; fallback NaT when malformed
        week_start_date = pd.NaT
        if re.fullmatch(r"\d{1,2}-\d{1,2}", mmdd_txt):
            m0, d0 = mmdd_txt.split("-")
            mmdd_norm = f"{int(m0):02d}-{int(d0):02d}"
            try:
                week_start_date = pd.to_datetime(
                    f"{int(calendar_year)}-{mmdd_norm}",
                    format="%Y-%m-%d",
                    errors="coerce",
                )
            except Exception:
                week_start_date = pd.NaT
        else:
            mmdd_norm = mmdd_txt
            if mmdd_norm:
                parse_warnings.append(f"Unrecognized week_start_mmdd: {mmdd_norm}")

        def emit_from_column(col_class: str, tour_label: str):
            cell = r.xpath(f".//div[contains(@class, '{col_class}')]")
            if not cell:
                return

            a = cell[0].xpath(".//a[1]")
            if not a:
                return

            href = (a[0].get("href") or "").strip()
            city = " ".join(" ".join(a[0].xpath(".//text()")).split())
            city = _strip_html(city)

            parsed = _parse_calendar_event_url(href, language)
            logo_srcs = a[0].xpath(
                ".//img[contains(@class, 'cSurvivorLevelImg')]/@src"
            )
            type_label, level = parse_survivor_level_logo(
                logo_srcs[0] if logo_srcs else ""
            )

            rows.append(
                {
                    "year": int(calendar_year),
                    "week_start_mmdd": mmdd_norm,
                    "week_start_date": week_start_date,
                    "tour": tour_label,
                    "city": city,
                    "url": href,
                    "event_id": parsed["event_id"],
                    "event_year": parsed["event_year"],
                    "event_tour": parsed["event_tour"],
                    "page_type": parsed["page_type"],
                    "type": type_label,
                    "level": level,
                }
            )

        emit_from_column("cSurvivorMSColumn", "MS")
        emit_from_column("cSurvivorWSColumn", "WS")

    df = pd.DataFrame(rows)

    # Normalize dtypes for stable downstream behavior
    if not df.empty:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        df["event_year"] = pd.to_numeric(df["event_year"], errors="coerce").astype(
            "Int64"
        )

    mismatch = 0
    if not df.empty:
        mismatch = int(
            (
                (
                    df["event_tour"].fillna("").astype(str).str.upper()
                    != df["tour"].astype(str).str.upper()
                )
                & (df["event_tour"].fillna("") != "")
            ).sum()
        )

    meta = {
        "calendar_url": calendar_url,
        "calendar_year": int(calendar_year),
        "rows_total": len(df),
        "weeks_total": int(df["week_start_mmdd"].nunique()) if not df.empty else 0,
        "tours": (
            sorted(df["tour"].dropna().astype(str).unique().tolist())
            if not df.empty
            else []
        ),
        "event_year_mismatch_count": (
            int(
                (
                    (df["event_year"].notna())
                    & (df["event_year"].astype("Int64") != int(calendar_year))
                ).sum()
            )
            if not df.empty
            else 0
        ),
        "event_tour_mismatch_count": mismatch,
        "parse_warnings": sorted(set(parse_warnings)),
    }

    return df, meta


def find_ongoing_event(calendar_df: pd.DataFrame, tour: str) -> dict:
    """Return the earliest active event for the given tour from a calendar DataFrame.

    Filters for rows where page_type == 'my' and tour matches, sorts ascending
    by week_start_date, and returns the first row as a dict. Returns {} if none found.
    """
    mask = (calendar_df["page_type"] == "my") & (
        calendar_df["tour"].str.upper() == tour.strip().upper()
    )
    filtered = calendar_df.loc[mask].sort_values("week_start_date")
    if filtered.empty:
        return {}
    return filtered.iloc[0].to_dict()


def fetch_event_detail(
    event_id: int | str,
    year: int | str,
    tour: str,
    language: str = "zh",
) -> dict:
    """Fetch and parse the survivor event detail (day-pick) page.

    Returns:
        {
            "players": [{"section": str, "player_id": str, "name": str}, ...],
            "n_byes": int,
            "dates": {"1": "2026-07-27", ...},       # day str -> ISO date
            "rounds": {"1": {"round": "R1", "score": 30}, ...}  # day str -> dict
        }
    """
    tour = str(tour).strip().upper()
    if tour not in {"WS", "MS"}:
        raise ValueError("tour must be 'WS' or 'MS'")

    url = f"https://www.live-tennis.cn/{language}/survivor/event/{event_id}/{year}/{tour}/my"
    session = requests.Session()
    resp = _request_with_retry(session, "GET", url, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # --- players ---
    players = []
    n_byes = 0
    seen_ids = set()

    # Players in detailed candidate sections
    for section_div in soup.select(".cSurvivorDayPickCandidatesSection"):
        section_title = section_div.select_one(
            ".cSurvivorDayPickCandidatesSectionTitle > div:first-child"
        ).get_text(" ", strip=True)

        for card in section_div.select(".cSurvivorSmallCard"):
            pid = (card.get("data-id") or "").strip()
            name = (card.get("data-name") or "").strip()

            if pid == "BYE":
                n_byes += 1
                continue

            if pid in {"QUAL", ""} or pid in seen_ids:
                continue

            seen_ids.add(pid)
            players.append(
                {
                    "section": section_title,
                    "player_id": pid,
                    "name": name,
                }
            )

    # Players shown directly in the main section cards
    for card in soup.select(".cSurvivorDayPickSection .cSurvivorCard"):
        pid = (card.get("data-id") or "").strip()
        name = (card.get("data-name") or "").strip()

        if pid == "BYE":
            n_byes += 1
            continue

        if pid in {"QUAL", ""} or pid in seen_ids:
            continue

        section_div = card.find_parent("div", class_="cSurvivorDayPickSection")

        title_element = section_div.select_one(".cSurvivorDayPickSectionTitle")

        section_title = title_element.get_text(" ", strip=True)

        seen_ids.add(pid)
        players.append(
            {
                "section": section_title,
                "player_id": pid,
                "name": name,
            }
        )

    # --- days: date + round + score keyed by day number string ---
    days: dict[str, dict] = {}

    selector_root = soup.select_one("#iSurvivorDayPickSelector")
    if selector_root:
        for item in selector_root.select(".cSurvivorDayPickSelector"):
            raw = item.get_text(separator="|", strip=True)
            parts = [p.strip() for p in raw.split("|")]
            day_part = next((p for p in parts if p.lower().startswith("day")), None)
            date_part = next(
                (p for p in parts if re.fullmatch(r"\d{1,2}/\d{1,2}", p)), None
            )
            if day_part and date_part:
                day_num = re.sub(r"[Dd]ay\s*", "", day_part).strip()
                m, d = date_part.split("/")
                try:
                    days[day_num] = {
                        "date": _date(int(year), int(m), int(d)).isoformat()
                    }
                except ValueError:
                    pass

    for i, info_div in enumerate(soup.select(".cSurvivorDayPickInfo"), start=1):
        notice = info_div.select_one(".cSurvivorFillNotice")
        if not notice:
            continue
        text = notice.get_text(" ", strip=True)
        round_m = re.search(r"当前轮次\s*[:：]\s*([A-Za-z0-9/]+)", text)
        score_m = re.search(r"当前分数\s*[:：]\s*(\d+)", text)
        entry = days.setdefault(str(i), {})
        entry["round"] = round_m.group(1) if round_m else None
        entry["score"] = int(score_m.group(1)) if score_m else None

    # Same tennis round on consecutive pick days → R1/1, R1/2, QF/1, QF/2 …
    annotated = annotate_multi_day_rounds(
        {
            int(k): (v.get("round") or "")
            for k, v in days.items()
            if str(k).isdigit()
        }
    )
    for day_num, label in annotated.items():
        entry = days.setdefault(str(day_num), {})
        entry["round"] = label or entry.get("round")

    return {"players": players, "n_byes": n_byes, "days": days}


def annotate_multi_day_rounds(round_by_day: dict[int, str]) -> dict[int, str]:
    """Label pick days that share a round as ``R2/1``, ``R2/2``, ``QF/1`` …

    Single-day rounds stay bare (``SF``, ``F``). If the source already has a
    ``/n`` suffix it is kept as-is.
    """
    from collections import defaultdict

    cleaned: dict[int, str] = {}
    for day, raw in round_by_day.items():
        try:
            d = int(day)
        except (TypeError, ValueError):
            continue
        text = str(raw or "").strip()
        cleaned[d] = text

    groups: dict[str, list[int]] = defaultdict(list)
    for day in sorted(cleaned):
        text = cleaned[day]
        if not text:
            continue
        base = text.split("/", 1)[0].strip()
        if base:
            groups[base].append(day)

    out: dict[int, str] = {}
    for day, text in cleaned.items():
        if not text:
            out[day] = ""
            continue
        if "/" in text:
            out[day] = text
            continue
        base = text
        bucket = groups.get(base) or [day]
        if len(bucket) <= 1:
            out[day] = base
        else:
            out[day] = f"{base}/{bucket.index(day) + 1}"
    return out


def pick_rounds_to_result_rounds(round_by_day: dict[int, str]) -> dict[int, str]:
    """Map pick-page ``当前轮次`` → result round for survivor day scores.

    The pick page labels the round being selected (championship day is ``F``)
    while surviving that day awards the next-stage points (``500`` = ``W``).
    Shift non-``R1`` days to the following pick label; the final ``F`` becomes
    ``W``. Early ``R1/…`` days stay as-is (first-round exits).
    """
    cleaned: dict[int, str] = {}
    for day, raw in round_by_day.items():
        try:
            d = int(day)
        except (TypeError, ValueError):
            continue
        text = str(raw or "").strip()
        if text:
            cleaned[d] = text
    if not cleaned:
        return {}

    days = sorted(cleaned)
    out: dict[int, str] = {}
    for idx, day in enumerate(days):
        pick = cleaned[day]
        base = pick.split("/", 1)[0].strip().upper()
        if base == "R1":
            out[day] = pick
            continue
        if idx + 1 < len(days):
            out[day] = cleaned[days[idx + 1]]
        else:
            out[day] = "W" if base == "F" else pick
    return out


def day_round_labels(days: dict) -> list[str]:
    """Ordered *result* round labels for Day 1..N (empty string when unknown).

    Converts pick-page rounds (``F`` on title day) to score-board rounds
    (``W`` for champions, ``F`` for finalists, …).
    """
    if not days:
        return []
    nums = []
    for k in days:
        try:
            nums.append(int(k))
        except (TypeError, ValueError):
            continue
    if not nums:
        return []
    max_day = max(nums)
    pick: dict[int, str] = {}
    for i in range(1, max_day + 1):
        info = days.get(str(i)) or days.get(i) or {}
        label = str(info.get("round") or "").strip()
        if label:
            pick[i] = label
    result = pick_rounds_to_result_rounds(pick)
    return [result.get(i, pick.get(i, "")) for i in range(1, max_day + 1)]


def get_coordinates(city):
    geolocator = Nominatim(user_agent="survivor_event")
    try:
        location = geolocator.geocode(city)
        if location:
            return location.latitude, location.longitude
        else:
            logger.error(f"city {city} not found")
            return None
    except Exception as e:
        logger.error(e)
        return None

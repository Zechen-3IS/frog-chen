"""Homepage renderer."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from site_html import state
from site_html.css import _CSS_BASE, _FONTS
from site_html.fragments import (
    _INDEX_CALENDAR_SECTION,
    _INDEX_COMBINED_SECTION,
    _INDEX_PLAYER_STATS_SECTION,
)
from site_html.js import _JS_THEME
from site_html.logos import _logo_pair
from site_html.state import VERSION


def _fmt_names(names: list[str], limit: Optional[int] = None) -> str:
    """Comma-separated plain names (legacy / title text)."""
    clean = [html.escape(str(n).strip()) for n in names if str(n).strip()]
    if not clean:
        return ""
    if limit is not None and len(clean) > limit:
        return ", ".join(clean[:limit]) + f" 等{len(clean)}人"
    return ", ".join(clean)


def _fmt_name_chips(names: list[str], limit: int = 4) -> str:
    """One chip per player; always show the full list (no collapse)."""
    del limit  # kept for call-site compatibility; never truncate
    clean = [html.escape(str(n).strip()) for n in names if str(n).strip()]
    if not clean:
        return ""
    chips = "".join(f'<span class="wk-chip">{n}</span>' for n in clean)
    return f'<span class="wk-chips">{chips}</span>'


def _week_panel_html(card) -> str:
    """Render one ATP/WTA week panel (copy aligned with chen_web home cards)."""
    tour = html.escape(str(getattr(card, "tour", "") or ""))
    kind = str(getattr(card, "kind", "") or "")
    tour_cls = tour.lower() if tour.lower() in {"atp", "wta"} else "all"
    empty = str(getattr(card, "empty_label", "") or "")
    city = str(getattr(card, "city", "") or "")
    level = str(getattr(card, "level", "") or "")
    week_start = getattr(card, "week_start", None)
    week_txt = ""
    if week_start is not None:
        try:
            week_txt = pd.Timestamp(week_start).strftime("%m/%d")
        except Exception:
            week_txt = ""

    kind_title = {"last": "上周", "this": "本周", "next": "下周"}.get(kind, "")
    eye = f"{tour} · {kind_title}"

    if empty:
        inner = f'<div class="wk-empty">{html.escape(empty)}</div>'
    else:
        level_html = (
            f'<span class="wk-level">{html.escape(level)}</span>' if level else ""
        )
        date_html = (
            f'<span class="wk-date">{html.escape(week_txt)}开赛</span>' if week_txt else ""
        )
        head = f"""\
            <div class="wk-event">
                <span class="wk-city">{html.escape(city)}</span>
                {level_html}
                {date_html}
            </div>"""

        body_parts: list[str] = []
        if kind == "last":
            champs = list(getattr(card, "champions", []) or [])
            top = int(getattr(card, "top_score", 0) or 0)
            top_names = list(getattr(card, "top_names", []) or [])
            if champs:
                body_parts.append('<div class="wk-label win">夺冠</div>')
                body_parts.append(
                    f'<div class="wk-people">{_fmt_name_chips(champs)}</div>'
                )  # expand ctrl inside _fmt_name_chips
            elif getattr(card, "ongoing", False):
                body_parts.append('<div class="wk-label pending">赛事进行中</div>')
            else:
                body_parts.append('<div class="wk-label out">本站无人生还</div>')
                if top_names and top:
                    body_parts.append(
                        f'<div class="wk-label soft">最高分 {top}</div>'
                    )
                    body_parts.append(
                        f'<div class="wk-people">{_fmt_name_chips(top_names)}</div>'
                    )
                elif top:
                    body_parts.append(
                        f'<div class="wk-sub">赛事最高分：{top}</div>'
                    )
        elif kind == "this":
            parts = []
            participants = getattr(card, "participants", None)
            survivors = getattr(card, "survivors", None)
            if participants is not None:
                parts.append(
                    f'<span class="wk-stat"><span class="wk-stat-lbl">参赛</span>'
                    f"<b>{int(participants)}</b></span>"
                )
            if survivors is not None:
                parts.append(
                    f'<span class="wk-stat"><span class="wk-stat-lbl">幸存</span>'
                    f"<b>{int(survivors)}</b></span>"
                )
            if parts:
                body_parts.append(f'<div class="wk-stats">{"".join(parts)}</div>')

            corr = list(getattr(card, "corresponding", []) or [])
            defend = list(getattr(card, "defending_names", []) or [])
            d_top = list(getattr(card, "defending_top_names", []) or [])
            d_score = int(getattr(card, "defending_score", 0) or 0)
            d_level = str(getattr(card, "defending_level", "") or "")
            if corr:
                corr_city = html.escape(str(corr[0]))
                extra_cities = ""
                if len(corr) > 1:
                    extra_cities = "、" + "、".join(
                        html.escape(c) for c in corr[1:]
                    )
                d_lvl = (
                    f'<span class="wk-level">{html.escape(d_level)}</span>'
                    if d_level
                    else ""
                )
                body_parts.append('<div class="wk-defend-card">')
                body_parts.append(
                    '<div class="wk-defend-title">卫冕赛事</div>'
                )
                body_parts.append(
                    f'<div class="wk-defend-event">'
                    f'<span class="wk-defend-city">{corr_city}{extra_cities}</span>'
                    f"{d_lvl}</div>"
                )
                if defend:
                    body_parts.append(
                        '<div class="wk-label win">卫冕冠军</div>'
                    )
                    body_parts.append(
                        f'<div class="wk-people">{_fmt_name_chips(defend)}</div>'
                    )
                elif d_top and d_score:
                    body_parts.append(
                        '<div class="wk-label out">卫冕站无人生还</div>'
                    )
                    body_parts.append(
                        f'<div class="wk-label soft">最高分 {d_score}</div>'
                    )
                    body_parts.append(
                        f'<div class="wk-people">{_fmt_name_chips(d_top)}</div>'
                    )
                elif d_score:
                    body_parts.append(
                        '<div class="wk-label out">卫冕站无人生还</div>'
                    )
                    body_parts.append(
                        f'<div class="wk-sub">赛事最高分：{d_score}</div>'
                    )
                else:
                    body_parts.append(
                        '<div class="wk-label out">卫冕站无人生还</div>'
                    )
                body_parts.append("</div>")
        else:  # next — event name/level only
            pass

        inner = head + "\n".join(body_parts)

    # Display-only panels — do not wrap as links / navigate on click.
    return f"""\
        <div class="wk-panel {tour_cls}">
            <div class="wk-eye">{html.escape(eye)}</div>
            {inner}
        </div>"""


def _week_section_html(week_data: Optional[dict]) -> str:
    if not week_data:
        return ""
    tours = week_data.get("tours") or {}
    if not tours:
        return ""

    blocks = []
    for kind, label in (
        ("last", "上周赛事结果"),
        ("this", "本周赛事"),
    ):
        panels = []
        for tour in ("ATP", "WTA"):
            card = (tours.get(tour) or {}).get(kind)
            if card is None:
                continue
            panels.append(_week_panel_html(card))
        if not panels:
            continue
        blocks.append(f"""\
    <div class="wk-block">
        <div class="wk-block-hd">{html.escape(label)}</div>
        <div class="wk-grid">
{"".join(panels)}
        </div>
    </div>""")

    if not blocks:
        return ""
    return f"""\
    <div class="section week-section">
        <div class="sec-hd"><span class="sec-label">赛况日历</span><div class="sec-rule"></div></div>
{"".join(blocks)}
    </div>
"""


def render_index(
    stats: dict,
    version: str = VERSION,
    weather=None,
    weather_label: str = "赛地天气",
    week_data: Optional[dict] = None,
    output_path: str | Path = "index.html",
) -> str:
    """
    Build and write the homepage HTML.

    Parameters
    ----------
    stats : dict
        Keys used:
          "season" – int or str, current season year (killer links, footer)
        (Live 参赛/幸存 now live in week_data 本周 cards.)
    version : str
        Version string shown in logo sub-line and footer.
    weather :
        Weather strip(s) to render. Accepts:
          - None / ""           → no weather strip
          - str                 → single shared strip (ATP & WTA same site).
                                  Output of build_weather_cards().
          - list of (label, cards) tuples
                                → one strip per venue (ATP & WTA different
                                  sites), each with its own sub-label, e.g.
                                  [("ATP · 罗马", atp_cards),
                                   ("WTA · 马德里", wta_cards)]
    weather_label : str
        Small-caps section label shown above the weather block(s).
    output_path : str or Path
        Where to write the HTML file.

    Returns
    -------
    str : the generated HTML string.
    """

    season = stats.get("season", datetime.now().year)

    # ── normalise weather input into a list of (label, cards) blocks ─────────
    if weather is None:
        weather_blocks = []
    elif isinstance(weather, str):
        weather_blocks = [(None, weather)] if weather.strip() else []
    else:
        # assume iterable of (label, cards)
        weather_blocks = [
            (lbl, cards) for lbl, cards in weather if cards and str(cards).strip()
        ]

    # ── build the weather section HTML ───────────────────────────────────────
    if weather_blocks:
        strips = []
        for lbl, cards in weather_blocks:
            summary = html.escape(str(lbl)) if lbl else html.escape(weather_label)
            strips.append(f"""\
        <details class="weather-details" open>
            <summary class="weather-venue">{summary}</summary>
            <div class="weather-scroll">
{cards}
            </div>
        </details>""")
        strips_html = "\n".join(strips)
        weather_section = f"""\
    <div class="section weather-section">
        <div class="sec-hd"><span class="sec-label">{html.escape(weather_label)}</span><div class="sec-rule"></div></div>
{strips_html}
    </div>
"""
    else:
        weather_section = ""

    week_section = _week_section_html(week_data)

    html_str = f"""\
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>签表幸存者数据中心</title>
    {_FONTS}
    <style>
{state.css_vars}
{_CSS_BASE}
        .page{{position:relative;z-index:1;max-width:820px;margin:0 auto;padding:40px 24px 80px;}}

        /* header */
        header{{display:flex;align-items:center;justify-content:space-between;
            margin-bottom:52px;flex-wrap:wrap;gap:12px;}}
        .logo{{display:flex;align-items:center;gap:12px;text-decoration:none;}}
        .logo-text{{display:flex;flex-direction:column;gap:2px;}}
        .logo-cn{{font-family:'Noto Serif SC',serif;font-size:17px;font-weight:700;
            color:var(--ink);letter-spacing:.06em;line-height:1;}}
        .logo-en{{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted);
            letter-spacing:.22em;text-transform:uppercase;line-height:1;}}
        .theme-btn{{border:1px solid var(--border);background:var(--surface);color:var(--muted);
            padding:7px 16px;border-radius:20px;cursor:pointer;font-size:12px;
            font-family:'Noto Sans SC',sans-serif;transition:all .2s;}}
        .theme-btn:hover{{border-color:var(--primary);color:var(--primary);}}

        /* hero */
        .hero{{padding:36px 0 36px 20px;border-left:3px solid var(--primary);margin-bottom:52px;}}
        .hero-label{{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.28em;
            text-transform:uppercase;color:var(--primary);margin-bottom:14px;}}
        .hero-title{{font-family:'Noto Serif SC',serif;font-size:clamp(26px,5vw,42px);
            font-weight:700;color:var(--ink);line-height:1.25;margin-bottom:14px;}}
        .hero-desc{{font-size:14px;color:var(--muted);line-height:1.85;max-width:500px;}}

        /* ── weather strip ── */
        .weather-section{{margin-bottom:44px;}}
        .weather-details{{margin-bottom:14px;}}
        .weather-details + .weather-details{{margin-top:4px;}}
        .weather-venue{{font-family:'Space Mono',monospace;font-size:10px;
            letter-spacing:.14em;text-transform:uppercase;color:var(--primary);
            margin:4px 0 6px 2px;cursor:pointer;list-style:none;
            display:flex;align-items:center;gap:6px;user-select:none;}}
        .weather-venue::-webkit-details-marker{{display:none;}}
        .weather-venue::before{{content:'▾';font-size:10px;transition:transform .2s;}}
        .weather-details:not([open]) .weather-venue::before{{transform:rotate(-90deg);}}
        .weather-scroll{{display:flex;gap:10px;overflow-x:auto;
            padding:4px 2px 12px;scroll-snap-type:x proximity;
            -webkit-overflow-scrolling:touch;}}
        .weather-scroll::-webkit-scrollbar{{height:5px;}}
        .weather-scroll::-webkit-scrollbar-track{{background:transparent;}}
        .weather-scroll::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px;}}
        .wx{{flex:0 0 auto;width:84px;background:var(--surface);
            border:1px solid var(--border);border-radius:10px;
            padding:12px 8px 11px;text-align:center;scroll-snap-align:start;
            transition:border-color .2s,transform .2s,box-shadow .2s;}}
        .wx:hover{{border-color:var(--primary-rim);transform:translateY(-2px);
            box-shadow:0 4px 14px rgba(26,26,26,.06);}}
        body.dark .wx:hover{{box-shadow:0 4px 14px rgba(0,0,0,.3);}}
        .wx.now{{border-color:var(--primary);background:var(--primary-dim);}}
        .wx-day{{font-family:'Space Mono',monospace;font-size:9px;
            letter-spacing:.1em;text-transform:uppercase;color:var(--faint);
            min-height:11px;line-height:1;margin-bottom:3px;}}
        .wx-time{{font-family:'Space Mono',monospace;font-size:11px;
            color:var(--muted);line-height:1;margin-bottom:7px;}}
        .wx.now .wx-time{{color:var(--primary-dark);font-weight:700;}}
        body.dark .wx.now .wx-time{{color:var(--primary);}}
        .wx-icon{{font-size:24px;line-height:1;margin-bottom:7px;}}
        .wx-temp{{font-family:'Space Mono',monospace;font-size:17px;font-weight:700;
            color:var(--ink);line-height:1;margin-bottom:3px;}}
        .wx-cond{{font-size:11px;color:var(--muted);line-height:1.3;
            min-height:14px;margin-bottom:8px;}}
        .wx-row{{font-size:10px;color:var(--faint);line-height:1.7;
            font-variant-numeric:tabular-nums;}}
        .wx-rain{{color:var(--secondary);}}

        /* week status (上/本周) */
        .week-section{{margin-bottom:44px;}}
        .wk-block{{margin-bottom:16px;}}
        .wk-block:last-child{{margin-bottom:0;}}
        .wk-block-hd{{font-family:'Noto Serif SC',serif;font-size:14px;font-weight:600;
            color:var(--ink);margin:0 0 10px 2px;letter-spacing:.02em;}}
        .wk-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;}}
        .wk-panel{{display:block;text-decoration:none;background:var(--surface);
            border:1px solid var(--border);border-radius:8px;padding:14px 16px;
            position:relative;overflow:hidden;transition:border-color .18s,transform .18s;}}
        .wk-panel::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
            opacity:.85;}}
        .wk-panel.atp::before{{background:var(--secondary);}}
        .wk-panel.wta::before{{background:var(--primary);}}
        .wk-eye{{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.16em;
            text-transform:uppercase;margin-bottom:8px;}}
        .wk-panel.atp .wk-eye{{color:var(--secondary);}}
        .wk-panel.wta .wk-eye{{color:var(--primary);}}
        .wk-event{{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 8px;margin-bottom:8px;}}
        .wk-city{{font-family:'Noto Serif SC',serif;font-size:18px;font-weight:700;color:var(--ink);}}
        .wk-level{{font-size:10px;padding:1px 6px;border-radius:8px;background:var(--surface2);
            color:var(--muted);border:0.5px solid var(--border);}}
        .wk-date{{font-family:'Space Mono',monospace;font-size:10px;color:var(--faint);}}
        .wk-stats{{display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 10px;}}
        .wk-stat{{display:inline-flex;align-items:baseline;gap:6px;
            padding:4px 10px;border-radius:999px;background:var(--surface2);
            border:0.5px solid var(--border);font-size:12px;}}
        .wk-stat-lbl{{color:var(--faint);font-size:10px;letter-spacing:.04em;}}
        .wk-stats b{{font-family:'Space Mono',monospace;color:var(--primary-dark);font-weight:700;}}
        body.dark .wk-stats b{{color:var(--primary);}}
        .wk-label{{font-size:11px;font-weight:600;letter-spacing:.04em;margin:8px 0 6px;}}
        .wk-label.win{{color:#2a6b4f;}}
        .wk-label.out{{color:var(--muted);}}
        .wk-label.pending{{color:#8a5a18;}}
        .wk-label.soft{{color:var(--faint);font-weight:500;margin-top:4px;}}
        body.dark .wk-label.win{{color:#7dcea0;}}
        body.dark .wk-label.pending{{color:#e0b56a;}}
        .wk-people{{margin:0 0 2px;}}
        .wk-chips{{display:flex;flex-wrap:wrap;gap:5px;}}
        .wk-chip{{display:inline-block;max-width:100%;padding:3px 9px;border-radius:999px;
            background:rgba(42,107,79,.08);border:0.5px solid rgba(42,107,79,.18);
            color:#1f4f3a;font-size:12px;line-height:1.35;white-space:nowrap;
            overflow:hidden;text-overflow:ellipsis;}}
        body.dark .wk-chip{{background:rgba(125,206,160,.12);border-color:rgba(125,206,160,.22);
            color:#b7e0c6;}}
        .wk-sub{{font-size:12px;color:var(--muted);line-height:1.55;margin-top:4px;}}
        .wk-defend-card{{margin-top:10px;padding:10px 12px;border-radius:8px;
            background:var(--surface2);border:0.5px solid var(--border);}}
        .wk-defend-title{{font-family:'Space Mono',monospace;font-size:9px;
            letter-spacing:.14em;text-transform:uppercase;color:var(--faint);
            margin:0 0 6px;}}
        .wk-defend-event{{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px;
            margin-bottom:2px;}}
        .wk-defend-city{{font-size:14px;font-weight:600;color:var(--ink);}}
        .wk-empty,.muted{{color:var(--faint);font-size:13px;}}

        /* sections */
        .section{{margin-bottom:44px;}}
        .sec-hd{{display:flex;align-items:center;gap:10px;margin-bottom:16px;}}
        .sec-label{{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.22em;
            text-transform:uppercase;color:var(--faint);}}
        .sec-rule{{flex:1;height:1px;background:var(--border2);}}

        /* cards */
        .card-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;}}
        .card{{display:block;text-decoration:none;background:var(--surface);
            border:1px solid var(--border);border-radius:8px;
            padding:20px 20px 20px 18px;position:relative;overflow:hidden;
            transition:transform .2s,box-shadow .2s,border-color .2s;}}
        .card::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
            border-radius:2px 0 0 2px;opacity:0;transition:opacity .2s;}}
        .card:hover{{transform:translateY(-2px);box-shadow:0 4px 16px rgba(26,26,26,.07);}}
        body.dark .card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.3);}}
        .card:hover::before{{opacity:1;}}
        .card.atp::before{{background:var(--secondary);}}
        .card.wta::before{{background:var(--primary);}}
        .card.all::before{{background:var(--primary-dark);}}
        .card-eye{{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.18em;
            text-transform:uppercase;margin-bottom:8px;}}
        .card.atp .card-eye{{color:var(--secondary);}}
        .card.wta .card-eye{{color:var(--primary);}}
        .card.all .card-eye{{color:var(--primary-dark);}}
        .card-title{{font-family:'Noto Serif SC',serif;font-size:17px;font-weight:600;
            color:var(--ink);margin-bottom:5px;}}
        .card-desc{{font-size:12px;color:var(--muted);line-height:1.6;}}
        .card-arrow{{position:absolute;right:18px;bottom:18px;font-size:15px;
            color:var(--faint);transition:all .2s;font-family:monospace;}}
        .card:hover .card-arrow{{color:var(--primary);transform:translateX(3px);}}

        /* footer */
        footer{{margin-top:36px;padding-top:24px;border-top:1px solid var(--border2);
            display:flex;justify-content:space-between;align-items:flex-end;
            flex-wrap:wrap;gap:12px;}}
        .credits{{font-size:12px;color:var(--faint);line-height:2;}}
        .credits a{{color:var(--muted);text-decoration:none;border-bottom:1px dashed var(--border);transition:all .2s;}}
        .credits a:hover{{color:var(--primary);border-bottom-color:var(--primary);}}
        .ver{{font-family:'Space Mono',monospace;font-size:9px;color:var(--faint);
            letter-spacing:.16em;padding:5px 9px;border:1px solid var(--border2);border-radius:3px;}}

        @media(max-width:600px){{
            .page{{padding:24px 16px 60px;}}
            header{{margin-bottom:32px;}}
            .hero{{margin-bottom:36px;}}
            .card-grid{{grid-template-columns:1fr;}}
            .wk-grid{{grid-template-columns:1fr;}}
        }}
    </style>
</head>
<body>
<div class="page">
    <header>
        <a class="logo" href="#">
            {_logo_pair(44)}
            <div class="logo-text">
                <span class="logo-cn">签表幸存者</span>
                <span class="logo-en">Data Center</span>
            </div>
        </a>
        <button class="theme-btn" id="themeBtn" onclick="toggleTheme()">🌙 暗色</button>
    </header>

    <div class="hero">
        <div class="hero-label">Tennis Draw Survivor · 2026 Hard-Court Swing</div>
        <h1 class="hero-title">每一场，都是生死之战</h1>
        <p class="hero-desc">ATP · WTA 签表幸存者游戏数据中心<br>即时排名、冠军积分、杀手榜一览无余</p>
    </div>

{week_section}
{weather_section}
    <div class="section">
        <div class="sec-hd"><span class="sec-label">排名查询</span><div class="sec-rule"></div></div>
        <div class="card-grid">
            <a href="atp_ranking.html"      class="card atp">
                <div class="card-eye"><b>ATP · Live Ranking</b></div>
                <div class="card-title">即时排名</div>
                <div class="card-desc">球员当前幸存者积分排名</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="wta_ranking.html"      class="card wta">
                <div class="card-eye"><b>WTA · Live Ranking</b></div>
                <div class="card-title">即时排名</div>
                <div class="card-desc">球员当前幸存者积分排名</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="atp_race_ranking.html" class="card atp">
                <div class="card-eye"><b>ATP · Race to Turin</b></div>
                <div class="card-title">即时冠军排名</div>
                <div class="card-desc">年终总决赛资格积分榜</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="wta_race_ranking.html" class="card wta">
                <div class="card-eye"><b>WTA · Race to Indian Wells</b></div>
                <div class="card-title">即时冠军排名</div>
                <div class="card-desc">年终总决赛资格积分榜</div>
                <span class="card-arrow">→</span>
            </a>
        </div>
    </div>

    {_INDEX_COMBINED_SECTION}

    {_INDEX_CALENDAR_SECTION}

    {_INDEX_PLAYER_STATS_SECTION}

    <div class="section">
        <div class="sec-hd"><span class="sec-label">幸存者杀手榜</span><div class="sec-rule"></div></div>
        <div class="card-grid">
            <a href="2026atpkiller.html" class="card atp">
                <div class="card-eye"><b>ATP · {season} Season</b></div>
                <div class="card-title">赛季杀手榜</div>
                <div class="card-desc">本赛季带走幸存者最多的球员</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="2026wtakiller.html" class="card wta">
                <div class="card-eye"><b>WTA · {season} Season</b></div>
                <div class="card-title">赛季杀手榜</div>
                <div class="card-desc">本赛季带走幸存者最多的球员</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="atpkiller.html"    class="card atp">
                <div class="card-eye"><b>ATP · All Time</b></div>
                <div class="card-title">历年总榜</div>
                <div class="card-desc">历史最佳幸存者杀手</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="wtakiller.html"    class="card wta">
                <div class="card-eye"><b>WTA · All Time</b></div>
                <div class="card-title">历年总榜</div>
                <div class="card-desc">历史最佳幸存者杀手</div>
                <span class="card-arrow">→</span>
            </a>
        </div>
    </div>

    <div class="section">
        <div class="sec-hd"><span class="sec-label">对战记录</span><div class="sec-rule"></div></div>
        <div class="card-grid">
            <a href="h2h_atp.html" class="card atp">
                <div class="card-eye"><b>ATP · Head to Head</b></div>
                <div class="card-title">ATP 对战记录</div>
                <div class="card-desc">查询你与任意球员的历史胜负对战记录</div>
                <span class="card-arrow">→</span>
            </a>
            <a href="h2h_wta.html" class="card wta">
                <div class="card-eye"><b>WTA · Head to Head</b></div>
                <div class="card-title">WTA 对战记录</div>
                <div class="card-desc">查询你与任意球员的历史胜负对战记录</div>
                <span class="card-arrow">→</span>
            </a>
        </div>
    </div>

    <footer>
        <div class="credits">
            <div>开发者：哭的没分蛙</div>
            <div>数据来源：<a href="https://www.live-tennis.cn/zh/survivor/calendar/{season}" target="_blank">丘的网球</a></div>
            <div>特别鸣谢：<a href="https://zechen-3is.github.io/survivor_champion_ranking/" target="_blank">旧纳</a></div>
            <div>数据仅供参考，一切以官方数据为准</div>
            </div>
        <span class="ver">v{html.escape(version)}</span>
    </footer>

</div>
<script>
{_JS_THEME}
</script>
</body>
</html>"""

    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


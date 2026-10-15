"""Ranking page renderer."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pandas as pd

from site_html.breakdown_ui import (
    _CSS_BREAKDOWN,
    breakdown_boot_script,
    breakdown_modal_html,
)
from site_html.common import (
    _df_to_html_table,
    _inner_page_shell,
    _killer_panel_html,
    _load_available_players,
    _route_query_block,
    _summary_bar_html,
)
from site_html.js import (
    _CSS_CAREER_DETAIL,
    _JS_CAREER_DETAIL,
    _JS_RANKING_DETAIL,
    _JS_ROUTE_QUERY,
)

def render_ranking_page(
    df: pd.DataFrame,
    title: str,
    tour: str,
    eyebrow: str,
    updated: str,
    summary_df: Optional[pd.DataFrame] = None,
    summary_top_n: int = 3,
    killer_df: Optional[pd.DataFrame] = None,
    rank_change_col: Optional[str] = "排名变化",
    extra_tags: Optional[list[str]] = None,
    available_players: Union[list[str], str, Path, None] = None,
    live_players: Optional[list[str]] = None,
    backup_events: Optional[list] = None,
    output_path: str | Path = "ranking.html",
    enable_detail: bool = True,
    enable_career_detail: bool = False,
    enable_breakdown: bool = False,
    breakdown_atp_url: str = "data/breakdown_live_atp.json",
    breakdown_wta_url: str = "data/breakdown_live_wta.json",
) -> str:
    """
    Build and write a ranking-table page.

    Parameters
    ----------
    df : pd.DataFrame
        Main ranking data. Every column becomes a filterable/sortable column.
    title : str
        Large page title, e.g. "即时冠军排名".
    tour : str
        "ATP" or "WTA" — controls pill colour.
    eyebrow : str
        Small label above the title, e.g. "ATP · Race to Turin · 2026".
    updated : str
        Timestamp string shown in the topbar, e.g. "2026年05月08日 16:22".
    summary_df : pd.DataFrame or None
        Output of generate_summary(). Pass None to hide the panel entirely.
        Mode (normal / bye) is auto-detected from column names:
        - Normal: columns contain "已选"
        - Day-1 bye: columns contain "非轮空" and "轮空"
    summary_top_n : int
        Number of player rows shown before the "show all" toggle (default 5).
    killer_df : pd.DataFrame or None
        Output of daily_killer_stats(); collapsible「每日杀手统计」panel.
    rank_change_col : str or None
        Column in df whose values are rendered as ▲/▼ badges.
    extra_tags : list[str] or None
        Additional pill tags next to the title (e.g. ["Race"]).
    available_players : list[str], str, Path, or None
        Players still alive in the draw, used to power the "夺冠路线查询"
        feature (a modal where the user multiselects players and sees
        which 存活 users have not picked any of them yet, alongside
        each matching user's 今日主选/今日备选). Pass a plain list, or a
        path to a JSON file (e.g. "available_players.json") containing
        a flat array of player names. Pass None to render the entry bar
        with an empty player list.
    live_players : list[str] or None
        Subset of available_players whose match is still in progress
        (未完赛). Used by the summary panel to distinguish 未完赛 vs
        已完赛确认存活.
    backup_events : list or None
        Aggregated early-retirement backup activations for the summary panel
        (``summarize_backup_events`` output).
    output_path : str or Path
        Destination file.
    enable_detail : bool
        When True (default), clicking a row opens the 选人明细 modal.
        Set False for pages without pick history.
    enable_career_detail : bool
        Career stats: row click opens 夺冠/夺亚 chip modal from ``_生涯明细``.
    enable_breakdown : bool
        Combined-ranking mode: row click opens ATP/WTA points charts.
    breakdown_atp_url / breakdown_wta_url : str
        JSON paths (relative to the HTML file) for per-user event composition.

    Returns
    -------
    str : the generated HTML string.
    """
    _players = _load_available_players(available_players)

    # Build optional summary panel
    if summary_df is not None:
        summary_block = _summary_bar_html(
            summary_df,
            top_n=summary_top_n,
            available_players=_players,
            live_players=live_players,
            backup_events=backup_events,
        )
        summary_js = ""  # JS is inlined inside _summary_bar_html
    else:
        summary_block = ""
        summary_js = ""

    killer_block = _killer_panel_html(killer_df)

    if enable_career_detail:
        detail_col = "_生涯明细"
    elif enable_detail:
        detail_col = "选人明细"
    else:
        detail_col = None

    main_table_html = _df_to_html_table(
        df,
        rank_change_col=rank_change_col,
        detail_col=detail_col,
        hide_detail_col=True,
        uid_col="主键" if enable_breakdown else None,
        hide_uid_col=True,
        row_click_class="bd-clickable" if enable_breakdown else "",
    )

    route_query_html = _route_query_block(_players) if _players else ""

    detail_modal = ""
    no_detail_style = ""
    detail_title = "生涯明细" if enable_career_detail else "选人明细"
    if enable_detail or enable_career_detail:
        detail_modal = f"""\
    <div id="detail-modal" class="detail-modal">
      <div class="detail-card">
        <div class="detail-hd">
          <div class="detail-title-wrap">
            <div class="detail-icon">📋</div>
            <div>
              <div class="detail-title">{detail_title}</div>
              <div class="detail-meta" id="detail-meta-line"></div>
            </div>
          </div>
          <button id="detail-close" class="detail-close" type="button">✕ 关闭</button>
        </div>
        <div class="detail-scroll">
          <div id="detail-body" class="detail-list"></div>
        </div>
        <div class="detail-footer" id="detail-footer"></div>
      </div>
    </div>"""
    elif not enable_breakdown:
        no_detail_style = (
            "<style>.filterable-table tbody tr{{cursor:default;}}</style>"
        )

    bd_modal = breakdown_modal_html() if enable_breakdown else ""
    bd_boot = (
        breakdown_boot_script(breakdown_atp_url, breakdown_wta_url)
        if enable_breakdown
        else ""
    )

    body = f"""\
        {no_detail_style}
        {summary_block}
        {killer_block}

        {route_query_html}

        <div class="stats-row">
        <div class="row-count">显示 <b id="visible-count">0</b> / <b id="total-count">0</b> 行</div>
        </div>

        <div class="table-wrapper">
            <div id="table-container">
            {main_table_html}
        </div>
    </div>
{detail_modal}"""

    if enable_career_detail:
        detail_js = _JS_CAREER_DETAIL
    elif enable_detail:
        detail_js = _JS_RANKING_DETAIL
    else:
        detail_js = ""
    route_js = _JS_ROUTE_QUERY if _players else ""
    extra_css_parts = []
    if enable_breakdown:
        extra_css_parts.append(_CSS_BREAKDOWN)
    if enable_career_detail:
        extra_css_parts.append(_CSS_CAREER_DETAIL)
    html_str = _inner_page_shell(
        page_title=title,
        title=title,
        tour=tour,
        eyebrow=eyebrow,
        updated=updated,
        extra_tags=extra_tags,
        body_content=body,
        extra_js=summary_js + "\n" + detail_js + "\n" + route_js + "\n" + bd_boot,
        extra_css="\n".join(extra_css_parts),
        # Modal must sit outside .page stacking context or it can be covered
        after_page=bd_modal,
    )

    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


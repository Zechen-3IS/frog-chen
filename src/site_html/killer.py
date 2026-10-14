"""Killer-board page renderer."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Optional

import pandas as pd

from site_html.common import _df_to_html_table, _inner_page_shell

def render_killer_page(
    df: pd.DataFrame,
    tour: str,
    eyebrow: str,
    updated: str,
    title: str = "幸存者杀手榜",
    extra_tags: Optional[list[str]] = None,
    kills_col: str = "带走人数",
    rate_col: str = "杀人率",
    name_col: str = "球员",
    output_path: str | Path = "killer.html",
) -> str:
    """
    Build and write a killer-board page with a top-3 podium.

    Parameters
    ----------
    df : pd.DataFrame
        Killer stats data. Expected columns (in order):
        排名 | 球员 | 带走人数 | 杀人率 | 最高单次带走人数 | 选择人数
    title : str
        Large page title, e.g. "幸存者杀手榜".
    tour : str
        "ATP" or "WTA".
    eyebrow : str
        Small label above the title.
    updated : str
        Timestamp string.
    extra_tags : list[str] or None
        Additional pill tags, e.g. ["历年总榜"] or ["2026"].
    kills_col : str
        Column name for kill count (shown large in podium).
    rate_col : str
        Column name for kill rate.
    name_col : str
        Column name for player name.
    output_path : str or Path

    Returns
    -------
    str : the generated HTML string.
    """
    # Build podium from first 3 rows
    pod_classes = ["p1", "p2", "p3"]
    medals = ["#1", "#2", "#3"]
    podium_cards = []
    for i, (_, row) in enumerate(df.head(3).iterrows()):
        name = html.escape(str(row.get(name_col, "")))
        kills = html.escape(str(row.get(kills_col, "")))
        rate = html.escape(str(row.get(rate_col, "")))
        podium_cards.append(f"""\
<div class="pod-card {pod_classes[i]}">
  <div class="pod-medal">{medals[i]}</div>
  <div class="pod-name">{name}</div>
  <div class="pod-kills">{kills}</div>
  <div class="pod-kills-lbl">带走人数</div>
  <div class="pod-rate">杀人率 {rate}</div>
</div>""")

    podium_html = '<div class="podium">\n' + "\n".join(podium_cards) + "\n</div>"
    main_table_html = _df_to_html_table(df, rank_change_col=None)

    body = f"""\
{podium_html}

<div class="stats-row">
  <div class="row-count">显示 <b id="visible-count">0</b> / <b id="total-count">0</b> 行</div>
</div>

<div class="table-wrapper">
  <div id="table-container">
    {main_table_html}
  </div>
</div>"""

    html_str = _inner_page_shell(
        page_title=title,
        title=title,
        tour=tour,
        eyebrow=eyebrow,
        updated=updated,
        extra_tags=extra_tags,
        body_content=body,
    )

    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


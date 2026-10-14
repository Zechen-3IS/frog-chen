"""
site_html — static page generators for 签表幸存者数据中心.

Public renderers live in submodules; this package re-exports the API
used by main.py / champion_stats.py / h2h.py.
"""
from __future__ import annotations

from themes import THEMES

from site_html.calendar import (
    render_calendar_hub_page,
    render_calendar_page,
    render_event_score_page,
)
from site_html.champion import render_champion_page
from site_html.h2h import render_h2h_page
from site_html.index import render_index
from site_html.killer import render_killer_page
from site_html.ranking import render_ranking_page
from site_html.state import VERSION, apply_theme, set_css_vars

__all__ = [
    "VERSION",
    "THEMES",
    "set_css_vars",
    "apply_theme",
    "render_index",
    "render_ranking_page",
    "render_killer_page",
    "render_champion_page",
    "render_h2h_page",
    "render_calendar_hub_page",
    "render_calendar_page",
    "render_event_score_page",
]

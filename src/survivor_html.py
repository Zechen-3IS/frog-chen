"""
survivor_html — backward-compatible facade for page generators.

Implementation lives in the ``site_html`` package. Prefer importing from
here (or from ``site_html``) so existing callers keep working.

Theme selection
---------------
Use ``apply_theme(name)`` or ``set_css_vars(...)`` instead of assigning
``survivor_html._CSS_VARS`` (that binding no longer drives renderers).
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
from site_html import state as _state

__all__ = [
    "VERSION",
    "THEMES",
    "apply_theme",
    "set_css_vars",
    "render_index",
    "render_ranking_page",
    "render_killer_page",
    "render_champion_page",
    "render_h2h_page",
    "render_calendar_hub_page",
    "render_calendar_page",
    "render_event_score_page",
]


def __getattr__(name: str):
    # Read-only compat for old ``survivor_html._CSS_VARS`` lookups.
    if name == "_CSS_VARS":
        return _state.css_vars
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Mutable theme/CSS state shared by all page renderers."""
from __future__ import annotations

from themes import CSS_VARS_HARD, THEMES

VERSION = "0.4.2"

# Mutated at runtime via apply_theme() / set_css_vars().
css_vars: str = CSS_VARS_HARD


def set_css_vars(value: str) -> None:
    """Replace the active CSS variable block (light/dark surface themes)."""
    global css_vars
    css_vars = value


def apply_theme(theme: str) -> None:
    """Apply a named theme from themes.THEMES (hard / clay / grass)."""
    set_css_vars(THEMES[theme])

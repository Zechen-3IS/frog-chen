"""Site logo SVG fragments."""
from __future__ import annotations

_LOGO_RACKET_INNER = """\
  <line x1="23" y1="28" x2="40" y2="28" stroke="#E8541A" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="23" y1="37" x2="40" y2="37" stroke="#E8541A" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="23" y1="51" x2="40" y2="51" stroke="#E8541A" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="23" y1="60" x2="40" y2="60" stroke="#E8541A" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="40" y1="28" x2="40" y2="37" stroke="#E8541A" stroke-width="1.8"/>
  <line x1="40" y1="51" x2="40" y2="60" stroke="#E8541A" stroke-width="1.8"/>
  <line x1="40" y1="32.5" x2="57" y2="32.5" stroke="#E8541A" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="40" y1="55.5" x2="57" y2="55.5" stroke="#E8541A" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="57" y1="32.5" x2="57" y2="55.5" stroke="#E8541A" stroke-width="1.8"/>
  <line x1="57" y1="44"   x2="67" y2="44"   stroke="#E8541A" stroke-width="2.2" stroke-linecap="round"/>
  <circle cx="72" cy="44" r="5.5" fill="#E8541A"/>
  <circle cx="72" cy="44" r="2.5" fill="#ffffff"/>"""

_LOGO_HANDLE_LIGHT = """\
  <ellipse cx="50" cy="43" rx="33" ry="37"
    fill="rgba(0,0,0,0.03)" stroke="rgba(26,32,53,0.75)" stroke-width="2.5"/>
  <line x1="43" y1="79" x2="57" y2="79"
    stroke="rgba(26,32,53,0.75)" stroke-width="3" stroke-linecap="round"/>
  <line x1="50" y1="80" x2="50" y2="96"
    stroke="rgba(26,32,53,0.75)" stroke-width="4" stroke-linecap="round"/>"""

_LOGO_HANDLE_DARK = """\
  <ellipse cx="50" cy="43" rx="33" ry="37"
    fill="rgba(255,255,255,0.03)" stroke="rgba(240,244,255,0.82)" stroke-width="2.5"/>
  <line x1="43" y1="79" x2="57" y2="79"
    stroke="rgba(240,244,255,0.82)" stroke-width="3" stroke-linecap="round"/>
  <line x1="50" y1="80" x2="50" y2="96"
    stroke="rgba(240,244,255,0.82)" stroke-width="4" stroke-linecap="round"/>"""


def _logo_svg(mode: str = "light", size: int = 44, extra_style: str = "") -> str:
    """Return one logo SVG element (light or dark variant)."""
    handle = _LOGO_HANDLE_LIGHT if mode == "light" else _LOGO_HANDLE_DARK
    display = "" if mode == "light" else "display:none;"
    css_cls = f"logo-{mode}"
    return (
        f'<svg class="{css_cls}" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 100 100" '
        f'style="width:{size}px;height:{size}px;flex-shrink:0;{display}{extra_style}">\n'
        f"{handle}\n{_LOGO_RACKET_INNER}\n</svg>"
    )


def _logo_pair(size: int = 44) -> str:
    return _logo_svg("light", size) + "\n" + _logo_svg("dark", size)


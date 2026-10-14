"""
themes.py
=========
CSS variable blocks.
Three palettes, identical variable names — swap by assigning _CSS_VARS.

Usage
-----
    from themes import CSS_VARS_CLAY, CSS_VARS_GRASS, CSS_VARS_HARD

    # In survivor_html.py, replace the _CSS_VARS constant with:
    _CSS_VARS = CSS_VARS_CLAY     # clay / red-clay swing  (Roland Garros)
    _CSS_VARS = CSS_VARS_GRASS    # grass swing            (Wimbledon)
    _CSS_VARS = CSS_VARS_HARD     # hard-court swings      (AO, ME, Sunshine,
                                  #                         US series, Asia)

Variable contract
-----------------
Every palette exposes exactly these tokens.
"Primary" = main accent (bar fill, links, count highlights).
"Secondary" = bye-day split bar + 轮空 chips.

  Surfaces
  --------
  --bg            page background
  --bg2           slightly darker page bg (used in body::before gradient)
  --surface       card / panel background
  --surface2      subtly tinted surface (hover bg, toggle bg)

  Primary accent  (clay=terracotta | grass=green | hard=court-blue)
  ---------------
  --primary           full-strength accent
  --primary-dark      darker shade  (light-mode chip text, sbar-iv)
  --primary-dim       ~10% alpha fill  (chip backgrounds, tag fills)
  --primary-rim       ~25% alpha border (chip borders, tag borders)

  Secondary accent  (clay=cobalt | grass=straw-gold | hard=baseline-red)
  ----------------
  --secondary         full-strength
  --secondary-dim     ~10% alpha fill
  --secondary-rim     ~25% alpha border

  Typography
  ----------
  --ink           primary text
  --ink2          slightly lighter body text
  --muted         secondary / label text
  --faint         tertiary / placeholder / border-adjacent text

  Borders
  -------
  --border        standard border  (~10% alpha)
  --border2       hairline border  (~6% alpha)

  Table chrome
  ------------
  --th-bg         sticky header background
  --th-text       sticky header text / accent line colour
  --row-hover     row hover tint
  --row-even      zebra stripe tint
  --filter-bg     filter-row background
  --drop-bg       dropdown menu background
  --track-bg      bar track empty-fill background

  Podium medals
  -------------
  --rank1         #1 medal colour
  --rank2         #2 medal colour
  --rank3         #3 medal colour
"""

# ── Clay & Chalk ──────────────────────────────────────────────────────────────
# Primary   : terracotta clay   #e06040 / #e8603c
# Secondary : cobalt blue       #2856a8 / #90bcf4
# Context   : Roland Garros, Monte Carlo, Rome, Madrid, Hamburg
CSS_VARS_CLAY = """\
:root {
    /* surfaces */
    --bg:#faf6f0; --bg2:#f0e8dc; --surface:#ffffff; --surface2:#fdf9f5;

    /* primary: terracotta clay */
    --primary:#e06040; --primary-dark:#c04830;
    --primary-dim:rgba(224,96,64,.10); --primary-rim:rgba(224,96,64,.25);

    /* secondary: cobalt blue */
    --secondary:#2856a8;
    --secondary-dim:rgba(40,86,168,.10); --secondary-rim:rgba(40,86,168,.25);

    /* typography */
    --ink:#1a1a1a; --ink2:#3a3530; --muted:#7a7268; --faint:#b0a898;

    /* borders */
    --border:rgba(26,26,26,.10); --border2:rgba(26,26,26,.06);

    /* table chrome */
    --th-bg:#1a1a1a; --th-text:#e8541a;
    --row-hover:rgba(224,96,64,.05); --row-even:rgba(26,26,26,.02);
    --filter-bg:#f5f0e8; --drop-bg:#ffffff; --track-bg:#ede8e0;

    /* podium medals */
    --rank1:#c04830; --rank2:#7a7268; --rank3:#8a6030;
    /* h2h result colors */
    --win:#2a7a4a; --win-bg:rgba(42,122,74,.08); --win-rim:rgba(42,122,74,.20);
    --lose:#c04830; --lose-bg:rgba(192,72,48,.08); --lose-rim:rgba(192,72,48,.20);
}
body.dark {
    /* surfaces */
    --bg:#161210; --bg2:#1e1916; --surface:#221e1a; --surface2:#2c2622;

    /* primary */
    --primary:#e8603c; --primary-dark:#ff7a54;
    --primary-dim:rgba(232,96,60,.13); --primary-rim:rgba(232,96,60,.30);

    /* secondary */
    --secondary:#90bcf4;
    --secondary-dim:rgba(144,188,244,.12); --secondary-rim:rgba(144,188,244,.28);

    /* typography */
    --ink:#f0ece6; --ink2:#c8c0b4; --muted:#8a8278; --faint:#4a4540;

    /* borders */
    --border:rgba(240,236,230,.10); --border2:rgba(240,236,230,.06);

    /* table chrome */
    --th-bg:#0e0c0a; --th-text:#e8541a;
    --row-hover:rgba(232,96,60,.07); --row-even:rgba(255,255,255,.025);
    --filter-bg:#1e1916; --drop-bg:#2c2622; --track-bg:#2c2622;

    /* podium medals */
    --rank1:#ff7a54; --rank2:#8a8278; --rank3:#c8a060;
    /* h2h result colors */
    --win:#4aaa6a; --win-bg:rgba(74,170,106,.10); --win-rim:rgba(74,170,106,.25);
    --lose:#ff7a54; --lose-bg:rgba(255,122,84,.10); --lose-rim:rgba(255,122,84,.25);
}"""


# ── Grass & Wimbledon ─────────────────────────────────────────────────────────
# Primary   : Wimbledon forest green  #1b5e37  (centre-circle green)
# Secondary : Wimbledon purple        #7b3f9e  (outer ring / band)
# Context   : Wimbledon, Queen's, Halle, 's-Hertogenbosch, Eastbourne
#
# Colour source: The Championships Wimbledon official logo
#   Centre green  ≈ #1b5e37   Purple ring  ≈ #7b3f9e
CSS_VARS_GRASS = """\
:root {
    /* surfaces — pale sage parchment, Centre Court chalk-line feel */
    --bg:#f4f8f2; --bg2:#e6f0e2; --surface:#ffffff; --surface2:#f7fbf5;
 
    /* primary: Wimbledon forest green #1b5e37 */
    --primary:#1b5e37; --primary-dark:#0f3d22;
    --primary-dim:rgba(27,94,55,.10); --primary-rim:rgba(27,94,55,.28);
 
    /* secondary: Wimbledon purple #7b3f9e */
    --secondary:#7b3f9e;
    --secondary-dim:rgba(123,63,158,.10); --secondary-rim:rgba(123,63,158,.26);
 
    /* typography */
    --ink:#161d18; --ink2:#2e3d30; --muted:#526055; --faint:#9ab09a;
 
    /* borders */
    --border:rgba(22,29,24,.10); --border2:rgba(22,29,24,.06);
 
    /* table chrome */
    --th-bg:#0f2a1a; --th-text:#1b5e37;
    --row-hover:rgba(27,94,55,.05); --row-even:rgba(22,29,24,.02);
    --filter-bg:#ecf5e8; --drop-bg:#ffffff; --track-bg:#d8e8d0;
 
    /* podium medals */
    --rank1:#0f3d22; --rank2:#7b3f9e; --rank3:#5a3200;
}
body.dark {
    /* surfaces — deep forest night */
    --bg:#090f0b; --bg2:#0f1a12; --surface:#131d16; --surface2:#1a2b1e;

    /* primary: brightened green for dark bg */
    --primary:#4ca86a; --primary-dark:#7acc90;
    --primary-dim:rgba(76,168,106,.13); --primary-rim:rgba(76,168,106,.30);

    /* secondary: brightened purple for dark bg */
    --secondary:#c090e8;
    --secondary-dim:rgba(192,144,232,.12); --secondary-rim:rgba(192,144,232,.28);
 
    /* typography */
    --ink:#e2ece4; --ink2:#b8ccba; --muted:#78987a; --faint:#344838;
 
    /* borders */
    --border:rgba(226,236,228,.10); --border2:rgba(226,236,228,.06);
 
    /* table chrome */
    --th-bg:#070d09; --th-text:#4ca86a;
    --row-hover:rgba(76,168,106,.07); --row-even:rgba(255,255,255,.025);
    --filter-bg:#0f1a12; --drop-bg:#1a2b1e; --track-bg:#1a2b1e;
 
    /* podium medals */
    --rank1:#7acc90; --rank2:#c090e8; --rank3:#c8a058;
}"""


# ── Hard Court — AO by Day, US Open by Night ──────────────────────────────────
# Primary   : Australian Open cyan  #0088bb  (the iconic "AO" logotype blue)
# Secondary : US Open gold          #c49800  (torch / wordmark, darkened for
#                                             legibility on light background)
# Context   : Australian Open, Dubai, Miami, Indian Wells,
#             US Open, Cincinnati, Beijing, Shanghai, Tokyo, Vienna
#
# Colour source:
#   AO logo background cyan  ≈ #009fd4  → deepened to #0088bb for contrast
#   US Open gold wordmark    ≈ #ffcc00  → darkened to #c49800 for light bg
#   Light mode: AO daylight icy arena feel
#   Dark  mode: US Open night session — deep navy + full-brightness gold
CSS_VARS_HARD = """\
:root {
    /* surfaces — icy pale blue, AO arena daylight */
    --bg:#f0f7fb; --bg2:#e0eef6; --surface:#ffffff; --surface2:#f4fafd;
 
    /* primary: AO cyan #0088bb */
    --primary:#0088bb; --primary-dark:#005f85;
    --primary-dim:rgba(0,136,187,.10); --primary-rim:rgba(0,136,187,.28);
 
    /* secondary: US Open gold #c49800 */
    --secondary:#c49800;
    --secondary-dim:rgba(196,152,0,.10); --secondary-rim:rgba(196,152,0,.26);
 
    /* typography */
    --ink:#051420; --ink2:#0e2a3c; --muted:#4a6878; --faint:#90aabf;
 
    /* borders */
    --border:rgba(5,20,32,.10); --border2:rgba(5,20,32,.06);
 
    /* table chrome — deep navy header, bright AO cyan accent */
    --th-bg:#002d44; --th-text:#00aaee;
    --row-hover:rgba(0,136,187,.05); --row-even:rgba(5,20,32,.02);
    --filter-bg:#e6f3fa; --drop-bg:#ffffff; --track-bg:#cce6f4;
 
    /* podium medals */
    --rank1:#005f85; --rank2:#5a6e80; --rank3:#a07800;
}
body.dark {
    /* surfaces — US Open night: deep navy stadium */
    --bg:#030c14; --bg2:#071422; --surface:#0a1d30; --surface2:#102840;
 
    /* primary: bright AO cyan for night */
    --primary:#00b8f0; --primary-dark:#40d0ff;
    --primary-dim:rgba(0,184,240,.13); --primary-rim:rgba(0,184,240,.30);
 
    /* secondary: US Open gold at full brightness */
    --secondary:#f0c000;
    --secondary-dim:rgba(240,192,0,.12); --secondary-rim:rgba(240,192,0,.28);
 
    /* typography */
    --ink:#ddeef8; --ink2:#a8c8de; --muted:#5a84a0; --faint:#1e3850;
 
    /* borders */
    --border:rgba(221,238,248,.10); --border2:rgba(221,238,248,.06);
 
    /* table chrome */
    --th-bg:#010810; --th-text:#00b8f0;
    --row-hover:rgba(0,184,240,.07); --row-even:rgba(255,255,255,.025);
    --filter-bg:#071422; --drop-bg:#102840; --track-bg:#102840;
 
    /* podium medals */
    --rank1:#40d0ff; --rank2:#6a88a8; --rank3:#f0c000;
}"""


# Convenience mapping for programmatic selection
THEMES = {
    "clay": CSS_VARS_CLAY,
    "grass": CSS_VARS_GRASS,
    "hard": CSS_VARS_HARD,
}

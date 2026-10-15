"""Shared CSS string blocks inlined into generated pages."""
from __future__ import annotations

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:'
    "wght@400;600;700&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:"
    'wght@300;400;500;700&display=swap" rel="stylesheet">'
)

_CSS_BASE = """\
*{margin:0;padding:0;box-sizing:border-box;}
body{
    font-family:'Noto Sans SC',sans-serif;
    background:var(--bg);color:var(--ink);min-height:100vh;
    transition:background .3s,color .3s;
}
body::before{
    content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
    background:
        radial-gradient(ellipse 80% 50% at 10% 0%,rgba(224,96,64,.05) 0%,transparent 60%),
        radial-gradient(ellipse 60% 40% at 90% 100%,rgba(26,58,112,.04) 0%,transparent 55%);
}"""

# CSS used on inner pages (ranking / killer)
_CSS_INNER = """\
body{padding:24px 20px 60px;}
.page{position:relative;z-index:1;max-width:1280px;margin:0 auto;}

/* topbar */
.topbar{display:flex;align-items:center;justify-content:space-between;
    margin-bottom:28px;padding-bottom:18px;border-bottom:1px solid var(--border2);
    flex-wrap:wrap;gap:12px;}
.back-link{display:inline-flex;align-items:center;gap:10px;text-decoration:none;
    color:var(--muted);font-family:'Space Mono',monospace;font-size:11px;
    letter-spacing:.14em;text-transform:uppercase;transition:color .2s;}
.back-link:hover{color:var(--primary);}
.topbar-right{display:flex;align-items:center;gap:12px;}
.updated{font-family:'Space Mono',monospace;font-size:10px;color:var(--faint);
    letter-spacing:.08em;padding:5px 10px;border:1px solid var(--border2);border-radius:3px;}
.theme-btn{background:var(--surface);border:1px solid var(--border);color:var(--muted);
    padding:7px 16px;border-radius:20px;cursor:pointer;font-size:12px;
    font-family:'Noto Sans SC',sans-serif;transition:all .2s;}
.theme-btn:hover{border-color:var(--primary);color:var(--primary);}

/* page header */
.page-header{margin-bottom:24px;}
.page-eye{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.28em;
    color:var(--primary);text-transform:uppercase;margin-bottom:10px;}
.page-title{font-family:'Noto Serif SC',serif;font-size:clamp(22px,3vw,32px);
    font-weight:700;color:var(--ink);line-height:1.2;
    display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.ttag{font-family:'Space Mono',monospace;font-size:10px;padding:4px 10px;
    border-radius:3px;font-weight:400;letter-spacing:.1em;text-transform:uppercase;}
.ttag-atp{background:var(--secondary-dim);color:var(--secondary);border:1px solid rgba(26,58,112,.2);}
.ttag-wta{background:var(--primary-dim);color:var(--primary-dark);border:1px solid rgba(224,96,64,.2);}
.ttag-all{background:rgba(26,26,26,.05);color:var(--muted);border:1px solid var(--border);}
body.dark .ttag-atp{border-color:rgba(111,160,224,.25);}
body.dark .ttag-wta{border-color:rgba(232,96,60,.25);}

/* ── summary bar panel ── */
.sum-box{margin-bottom:18px;background:var(--surface);border:1px solid var(--border);
    border-radius:10px;overflow:hidden;max-width:700px;margin-left:auto;margin-right:auto;}
.sum-header{padding:10px 14px 9px;border-bottom:1px solid var(--border2);}
.sum-title{font-family:'Space Mono',monospace;font-size:10px;font-weight:500;
    letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:7px;}
.sum-meta{display:flex;flex-wrap:wrap;align-items:center;gap:5px;}
.meta-chip{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;
    border-radius:20px;font-size:11px;font-weight:500;white-space:nowrap;}
.chip-valid  {background:var(--primary-dim);color:var(--primary-dark);border:0.5px solid rgba(224,96,64,.25);}
.chip-bye    {background:var(--secondary-dim);color:var(--secondary);border:0.5px solid rgba(26,58,112,.25);}
.chip-nosel  {background:var(--surface2);color:var(--muted);border:0.5px solid var(--border);}
.chip-suicide{background:rgba(192,72,48,.10);color:var(--primary-dark);border:0.5px solid rgba(192,72,48,.22);}
.chip-live   {background:rgba(184,122,42,.10);color:#8a5a18;border:0.5px solid rgba(184,122,42,.24);}
.chip-alive  {background:rgba(46,125,92,.10);color:#2a6b4f;border:0.5px solid rgba(46,125,92,.22);}
.chip-out    {background:rgba(120,124,132,.10);color:#6a7078;border:0.5px solid rgba(120,124,132,.22);}
.chip-live .sdot,.chip-alive .sdot,.chip-out .sdot{
    width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0;}
.chip-live .sdot{background:#c4892e;}
.chip-alive .sdot{background:#2f8a62;}
.chip-out .sdot{background:#8a9098;}
body.dark .chip-valid  {border-color:rgba(232,96,60,.32);}
body.dark .chip-bye    {color:var(--secondary);border-color:rgba(111,160,224,.28);}
body.dark .chip-suicide{color:var(--primary-dark);}
body.dark .chip-live   {background:rgba(212,160,72,.14);color:#e0b56a;border-color:rgba(212,160,72,.28);}
body.dark .chip-alive  {background:rgba(72,168,120,.14);color:#7dcea0;border-color:rgba(72,168,120,.28);}
body.dark .chip-out    {background:rgba(150,156,164,.12);color:#a8adb4;border-color:rgba(150,156,164,.24);}
body.dark .chip-live .sdot{background:#e0b56a;}
body.dark .chip-alive .sdot{background:#7dcea0;}
body.dark .chip-out .sdot{background:#a8adb4;}
.meta-sep  {font-size:11px;color:var(--faint);}
.meta-total{font-size:12px;color:var(--ink);font-weight:500;}
/* early-retirement backup nested under pick rows */
.tag-bak{background:rgba(184,122,42,.10);color:#8a5a18;border:0.5px solid rgba(184,122,42,.22);}
.sbar-row.is-bak .sbar-dot{background:#c4892e;opacity:1;box-shadow:0 0 0 2px rgba(196,137,46,.16);}
.sbar-row.is-bak .sbar-label{color:#7a4e14;font-weight:500;}
.seg-bak{background:#c4892e;}
.sbar-track.solo-bak{background:rgba(184,122,42,.12);}
.sbar-bak{display:flex;align-items:center;gap:8px;padding:2px 14px 4px;
    font-size:12px;color:var(--muted);}
.sbar-bak.s-hidden{display:none;}
.sbar-bak-main{display:inline-flex;flex-wrap:wrap;align-items:center;gap:6px;
    padding-left:22px;min-width:0;}
.bak-arrow{color:var(--faint);font-size:12px;flex-shrink:0;}
.bak-alt{font-size:12px;color:var(--ink);min-width:3.5em;}
.bak-chips{display:inline-flex;flex-wrap:wrap;gap:4px;}
body.dark .tag-bak{background:rgba(212,160,72,.14);color:#e0b56a;border-color:rgba(212,160,72,.28);}
body.dark .sbar-row.is-bak .sbar-dot{background:#e0b56a;box-shadow:0 0 0 2px rgba(224,181,106,.16);}
body.dark .sbar-row.is-bak .sbar-label{color:#ead0a0;}
body.dark .seg-bak{background:#e0b56a;}
/* col header */
.sum-col-hd{display:flex;align-items:center;gap:8px;padding:5px 14px 3px;}
.sch-rank{width:16px;flex-shrink:0;}
.sch-name{width:190px;flex-shrink:0;}
.sch-bar{flex:1;}
.sch-right{display:flex;align-items:center;gap:3px;flex-shrink:0;}
.sch-tag{font-size:10px;font-weight:500;padding:1px 6px;border-radius:10px;white-space:nowrap;}
.sch-tag-v{background:var(--primary-dim);color:var(--primary-dark);border:0.5px solid rgba(224,96,64,.25);}
.sch-tag-b{background:var(--secondary-dim);color:var(--secondary);border:0.5px solid rgba(26,58,112,.25);}
body.dark .sch-tag-v{border-color:rgba(232,96,60,.32);}
body.dark .sch-tag-b{color:var(--secondary);border-color:rgba(111,160,224,.28);}
.sch-sep  {font-size:11px;color:var(--faint);}
.sch-count{font-size:11px;color:var(--faint);width:30px;text-align:right;}
.sch-pct  {font-size:11px;color:var(--faint);width:42px;text-align:right;}
/* bar rows */
.sum-list{padding:4px 0;}
.sbar-row{display:flex;align-items:center;gap:8px;padding:5px 14px;transition:background .12s;}
.sbar-row:hover{background:var(--surface2);}
.sbar-rank{font-size:11px;color:var(--faint);width:16px;text-align:right;
    flex-shrink:0;font-variant-numeric:tabular-nums;}
.sbar-name{font-size:13px;color:var(--ink);width:190px;flex-shrink:0;
    display:inline-flex;align-items:center;gap:5px;min-width:0;}
.sbar-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;
    background:var(--faint);opacity:.55;}
.sbar-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}
.sbar-tag{font-size:9px;font-weight:500;letter-spacing:.04em;padding:1px 5px;
    border-radius:8px;flex-shrink:0;line-height:1.35;white-space:nowrap;}
.tag-live{background:rgba(184,122,42,.10);color:#8a5a18;border:0.5px solid rgba(184,122,42,.22);}
.tag-alive{background:rgba(46,125,92,.10);color:#2a6b4f;border:0.5px solid rgba(46,125,92,.20);}
.tag-out{background:rgba(120,124,132,.10);color:#6a7078;border:0.5px solid rgba(120,124,132,.20);}
.sbar-row.is-live .sbar-dot{background:#c4892e;opacity:1;box-shadow:0 0 0 2px rgba(196,137,46,.16);}
.sbar-row.is-live .sbar-label{color:#7a4e14;font-weight:500;}
.sbar-row.is-alive .sbar-dot{background:#2f8a62;opacity:1;box-shadow:0 0 0 2px rgba(47,138,98,.14);}
.sbar-row.is-alive .sbar-label{color:#1f4f3a;font-weight:500;}
.sbar-row.is-out{opacity:.92;}
.sbar-row.is-out .sbar-dot{background:#9aa0a8;opacity:1;}
.sbar-row.is-out .sbar-label{color:var(--muted);}
.sbar-row.is-out .sbar-count,.sbar-row.is-out .sbar-pct{color:var(--muted);}
body.dark .tag-live{background:rgba(212,160,72,.14);color:#e0b56a;border-color:rgba(212,160,72,.28);}
body.dark .tag-alive{background:rgba(72,168,120,.14);color:#7dcea0;border-color:rgba(72,168,120,.28);}
body.dark .tag-out{background:rgba(150,156,164,.12);color:#a8adb4;border-color:rgba(150,156,164,.24);}
body.dark .sbar-row.is-live .sbar-dot{background:#e0b56a;box-shadow:0 0 0 2px rgba(224,181,106,.16);}
body.dark .sbar-row.is-live .sbar-label{color:#ead0a0;}
body.dark .sbar-row.is-alive .sbar-dot{background:#7dcea0;box-shadow:0 0 0 2px rgba(125,206,160,.16);}
body.dark .sbar-row.is-alive .sbar-label{color:#b7e0c8;}
body.dark .sbar-row.is-out .sbar-dot{background:#8a9098;}
.sbar-track{flex:1;background:var(--surface2);border-radius:20px;height:8px;
    display:flex;overflow:hidden;}
body.dark .sbar-track{background:var(--bg2);}
.sbar-seg{height:100%;transition:width .38s cubic-bezier(.4,0,.2,1);}
.seg-v{background:var(--primary);}
.seg-b{background:var(--secondary);}
.seg-live{background:linear-gradient(90deg,#d4a04a,#c4892e);}
.seg-alive{background:linear-gradient(90deg,#3fa873,#2f8a62);}
.seg-out{background:linear-gradient(90deg,rgba(140,146,154,.55),rgba(140,146,154,.38));}
body.dark .seg-b{background:var(--secondary);}
body.dark .seg-live{background:linear-gradient(90deg,#e0b56a,#c4892e);}
body.dark .seg-alive{background:linear-gradient(90deg,#5fbf8a,#3fa873);}
body.dark .seg-out{background:linear-gradient(90deg,rgba(130,136,144,.45),rgba(130,136,144,.28));}
.sbar-track.solo-v .seg-v,
.sbar-track.solo-live .seg-live,
.sbar-track.solo-alive .seg-alive,
.sbar-track.solo-out .seg-out{border-radius:20px;}
.sbar-track.solo-b .seg-b{border-radius:20px;}
.sbar-track.both   .seg-v{border-radius:20px 0 0 20px;}
.sbar-track.both   .seg-b{border-radius:0 20px 20px 0;}
.sbar-inline{display:flex;align-items:center;gap:2px;flex-shrink:0;
    font-size:12px;font-variant-numeric:tabular-nums;width:60px;justify-content:flex-end;}
.sbar-iv{color:var(--primary-dark);font-weight:500;}
.sbar-ib{color:var(--secondary);font-weight:500;}
body.dark .sbar-iv{color:var(--primary-dark);}
body.dark .sbar-ib{color:var(--secondary);}
.sbar-isep{font-size:11px;color:var(--faint);}
.sbar-right{display:flex;align-items:center;flex-shrink:0;}
.sbar-count{font-size:13px;font-weight:500;color:var(--ink);
    width:28px;text-align:right;font-variant-numeric:tabular-nums;}
.sbar-pct{font-size:12px;color:var(--faint);width:42px;text-align:right;
    font-variant-numeric:tabular-nums;}
/* totals row */
.sbar-row.stotal{border-top:1px solid var(--border2);margin-top:2px;
    padding-top:8px;padding-bottom:8px;}
.sbar-row.stotal .sbar-name{font-size:12px;color:var(--muted);}
.sbar-row.stotal .sbar-dot,.sbar-row.stotal .sbar-tag{display:none;}
.sbar-row.stotal .sbar-count{color:var(--primary);}
/* hidden / expanded rows */
.sbar-row.s-hidden{display:none;}
.sbar-row.s-hidden.s-exp{display:flex;}
/* toggle */
.sum-toggle{width:100%;padding:9px 14px;border:none;
    border-top:1px solid var(--border2);background:var(--surface2);
    color:var(--muted);font-size:12px;cursor:pointer;
    display:flex;align-items:center;justify-content:center;gap:6px;
    transition:background .15s,color .15s;font-family:'Noto Sans SC',sans-serif;}
.sum-toggle:hover{color:var(--primary);}
.sum-ticon{font-size:10px;display:inline-block;transition:transform .25s;}
.sum-toggle.open .sum-ticon{transform:rotate(180deg);}
/* copy button */
.sum-copy-btn{
    display:inline-flex;align-items:center;gap:5px;
    padding:3px 10px;border-radius:20px;cursor:pointer;
    border:1px solid var(--border);background:var(--surface2);
    color:var(--muted);font-size:11px;font-family:'Space Mono',monospace;
    letter-spacing:.04em;transition:all .18s;flex-shrink:0;
    white-space:nowrap;
}
.sum-copy-btn:hover{border-color:var(--primary-rim);color:var(--primary-dark);}
.sum-copy-btn.copied{border-color:var(--primary-rim);color:var(--primary-dark);
    background:var(--primary-dim);}
body.dark .sum-copy-btn.copied{color:var(--primary);}
.sum-title-row{display:flex;align-items:center;justify-content:space-between;
    gap:8px;margin-bottom:7px;}

/* daily killer panel (F7) */
.dk-box{margin:0 auto 18px;max-width:700px;background:var(--surface);
    border:1px solid var(--border);border-radius:10px;overflow:hidden;}
.dk-toggle{width:100%;padding:10px 14px;border:none;background:var(--surface2);
    color:var(--muted);font-size:12px;cursor:pointer;font-family:'Noto Sans SC',sans-serif;
    display:flex;align-items:center;justify-content:center;gap:8px;
    transition:color .15s,background .15s;}
.dk-toggle:hover{color:var(--primary);}
.dk-arrow{font-size:10px;display:inline-block;transition:transform .25s;}
.dk-box.open .dk-arrow{transform:rotate(180deg);}
.dk-body{display:none;border-top:1px solid var(--border2);padding:8px 0 10px;}
.dk-box.open .dk-body{display:block;}
.dk-hd{display:grid;grid-template-columns:56px 1fr 1fr;gap:8px;padding:4px 14px 6px;
    font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--faint);}
.dk-row{display:grid;grid-template-columns:56px 1fr 1fr;gap:8px;padding:7px 14px;
    align-items:center;border-top:1px solid var(--border2);}
.dk-row:hover{background:var(--surface2);}
.dk-day{font-family:'Space Mono',monospace;font-size:11px;color:var(--faint);}
.dk-killers{display:contents;}
.dk-k{font-size:13px;color:var(--ink);display:flex;align-items:baseline;gap:6px;min-width:0;}
.dk-k b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.dk-k em{font-style:normal;font-family:'Space Mono',monospace;font-size:11px;
    color:var(--primary-dark);font-weight:700;flex-shrink:0;}
.dk-k.alt em{color:var(--secondary);}
body.dark .dk-k em{color:var(--primary);}
body.dark .dk-k.alt em{color:var(--secondary);}
@media(max-width:640px){
    .dk-hd,.dk-row{grid-template-columns:44px 1fr; }
    .dk-hd-k:last-child,.dk-row .dk-k.alt{display:none;}
}

/* stats row */
.stats-row{display:flex;align-items:center;justify-content:space-between;
    margin-bottom:10px;flex-wrap:wrap;gap:8px;}
.row-count{font-family:'Space Mono',monospace;font-size:11px;
    color:var(--faint);letter-spacing:.08em;}
.row-count b{color:var(--primary);font-weight:700;}

/* table wrapper */
.table-wrapper{max-height:72vh;overflow-y:auto;overflow-x:auto;
    border:1px solid var(--border2);border-radius:6px;}
.table-wrapper::-webkit-scrollbar{width:5px;height:5px;}
.table-wrapper::-webkit-scrollbar-track{background:transparent;}
.table-wrapper::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}

/* filterable table */
.filterable-table{width:100%;border-collapse:collapse;font-size:12px;}
.filterable-table thead tr:first-child th{
    background:var(--th-bg);color:var(--th-text);
    padding:11px 10px;text-align:left;font-weight:500;
    position:sticky;top:0;z-index:20;cursor:pointer;
    user-select:none;white-space:nowrap;
    font-family:'Space Mono',monospace;font-size:10px;
    letter-spacing:.08em;text-transform:uppercase;
    border-bottom:1px solid rgba(232,84,26,.3);transition:color .15s;}
.filterable-table thead tr:first-child th:hover{color:#E8541A;}
.filterable-table td{padding:8px 10px;border-bottom:1px solid var(--border2);
    vertical-align:middle;color:var(--ink);font-size:12px;}
.filterable-table tr:hover td{background:var(--row-hover);}
.filterable-table tr:nth-child(even) td{background:var(--row-even);}
.filterable-table tr:nth-child(even):hover td{background:var(--row-hover);}

/* filter row */
.filter-row{background:var(--filter-bg) !important;position:sticky;z-index:19;}
.filter-row th{padding:3px 4px;background:var(--filter-bg) !important;
    cursor:default;border-bottom:1px solid var(--border);}
.filter-dropdown{position:relative;width:100%;}
.filter-trigger{width:100%;padding:3px 5px;border:1px solid var(--border);
    border-radius:3px;background:var(--drop-bg);color:var(--muted);font-size:10px;
    cursor:pointer;display:flex;justify-content:space-between;align-items:center;
    font-family:'Space Mono',monospace;letter-spacing:.04em;transition:border-color .15s;}
.filter-trigger:hover{border-color:var(--primary);color:var(--ink2);}
.dropdown-content{display:none;position:fixed;background:var(--drop-bg);
    min-width:160px;max-height:240px;overflow-y:auto;
    border:1px solid var(--border);border-radius:4px;
    box-shadow:0 8px 24px rgba(26,26,26,.12);z-index:9999;}
body.dark .dropdown-content{box-shadow:0 8px 24px rgba(0,0,0,.4);}
.dropdown-content.show{display:block;}
.option-item{padding:7px 10px;cursor:pointer;display:flex;align-items:center;
    gap:8px;font-size:12px;border-bottom:1px solid var(--border2);
    color:var(--ink2);transition:background .12s;}
.option-item:last-child{border-bottom:none;}
.option-item:hover{background:var(--row-hover);}
.option-item input[type=checkbox]{margin:0;accent-color:var(--primary);}
.dropdown-search{width:100%;padding:8px 10px;border:none;
    border-bottom:1px solid var(--border2);background:var(--drop-bg);
    color:var(--ink);font-size:12px;outline:none;}
.dropdown-search::placeholder{color:var(--faint);}
.dropdown-search:focus{border-bottom-color:var(--primary);}
th.sort-asc::after{content:" ▲";font-size:9px;}
th.sort-desc::after{content:" ▼";font-size:9px;}

/* rank change badges */
.rank{font-weight:600;display:inline-flex;align-items:center;gap:3px;font-size:11px;}
.rank.up{color:#2a7a4a;}.rank.up::before{content:"▲";font-size:9px;}
.rank.down{color:#c04830;}.rank.down::before{content:"▼";font-size:9px;}
.rank.same{color:var(--faint);}.rank.same::before{content:"▶";font-size:9px;}

/* user status: 存活 / 未完赛·未选 / 淘汰(含自杀·球员输球) */
.st-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;
    border-radius:10px;font-size:11px;font-weight:500;line-height:1.35;
    white-space:nowrap;border:0.5px solid transparent;}
.st-badge::before{content:'';width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.st-alive{background:rgba(46,125,92,.10);color:#2a6b4f;border-color:rgba(46,125,92,.22);}
.st-alive::before{background:#2f8a62;}
.st-live{background:rgba(184,122,42,.10);color:#8a5a18;border-color:rgba(184,122,42,.22);}
.st-live::before{background:#c4892e;}
.st-out{background:rgba(120,124,132,.10);color:#6a7078;border-color:rgba(120,124,132,.22);}
.st-out::before{background:#9aa0a8;}
.st-other{background:rgba(120,124,132,.10);color:#6a7078;border-color:rgba(120,124,132,.22);}
.st-other::before{background:#9aa0a8;}
body.dark .st-alive{background:rgba(72,168,120,.14);color:#7dcea0;border-color:rgba(72,168,120,.28);}
body.dark .st-alive::before{background:#7dcea0;}
body.dark .st-live{background:rgba(212,160,72,.14);color:#e0b56a;border-color:rgba(212,160,72,.28);}
body.dark .st-live::before{background:#e0b56a;}
body.dark .st-out{background:rgba(150,156,164,.12);color:#a8adb4;border-color:rgba(150,156,164,.24);}
body.dark .st-out::before{background:#a8adb4;}
body.dark .st-other{background:rgba(150,156,164,.12);color:#a8adb4;border-color:rgba(150,156,164,.24);}
body.dark .st-other::before{background:#a8adb4;}
.filterable-table tr.row-alive td:first-child{box-shadow:inset 3px 0 0 #2f8a62;}
.filterable-table tr.row-live td:first-child{box-shadow:inset 3px 0 0 #c4892e;}
.filterable-table tr.row-out td{color:var(--muted);}
.filterable-table tr.row-out td:first-child{box-shadow:inset 3px 0 0 rgba(154,160,168,.55);}
body.dark .filterable-table tr.row-alive td:first-child{box-shadow:inset 3px 0 0 #7dcea0;}
body.dark .filterable-table tr.row-live td:first-child{box-shadow:inset 3px 0 0 #e0b56a;}

/* podium (killer page) */
.podium{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;}
.pod-card{background:var(--surface);border:1px solid var(--border2);border-radius:8px;
    padding:18px 14px;text-align:center;transition:border-color .2s;}
.pod-card:hover{border-color:var(--border);}
.pod-card.p1{border-top:3px solid var(--rank1);}
.pod-card.p2{border-top:3px solid var(--rank2);}
.pod-card.p3{border-top:3px solid var(--rank3);}
.pod-medal{font-family:'Space Mono',monospace;font-size:20px;font-weight:700;
    line-height:1;margin-bottom:8px;}
.p1 .pod-medal{color:var(--rank1);}
.p2 .pod-medal{color:var(--rank2);}
.p3 .pod-medal{color:var(--rank3);}
.pod-name{font-family:'Noto Serif SC',serif;font-size:14px;font-weight:600;
    color:var(--ink);margin-bottom:10px;}
.pod-kills{font-family:'Space Mono',monospace;font-size:24px;font-weight:700;
    color:var(--primary);line-height:1;margin-bottom:3px;}
.pod-kills-lbl{font-size:10px;color:var(--faint);letter-spacing:.08em;}
.pod-rate{margin-top:8px;font-size:11px;color:var(--muted);font-family:'Space Mono',monospace;}

/* kill-count & rank cols */
.filterable-table td:nth-child(3){font-family:'Space Mono',monospace;font-weight:600;color:var(--primary);}
.filterable-table td:nth-child(4){font-family:'Space Mono',monospace;font-size:11px;}
.filterable-table td:first-child{font-family:'Space Mono',monospace;color:var(--faint);font-size:11px;}

/* ── numeric range-slider filter ── */
.filter-slider{padding:10px 12px 12px;min-width:190px;}
.filter-slider-readout{
    display:flex;align-items:center;justify-content:center;gap:6px;
    margin-bottom:10px;font-family:'Space Mono',monospace;font-size:11px;
    color:var(--ink2);
}
.filter-slider-readout input[type=number]{
    width:58px;padding:3px 5px;border:1px solid var(--border);border-radius:3px;
    background:var(--drop-bg);color:var(--ink);font-size:11px;text-align:center;
    font-family:'Space Mono',monospace;
}
.filter-slider-readout input[type=number]:focus{outline:none;border-color:var(--primary);}
.filter-slider-sep{color:var(--faint);}
.filter-slider-range{position:relative;height:28px;}
.filter-slider-track{
    position:absolute;top:12px;left:0;right:0;height:4px;
    background:var(--border2);border-radius:2px;
}
.filter-slider-fill{
    position:absolute;top:12px;height:4px;background:var(--primary);border-radius:2px;
}
.filter-slider-range input[type=range]{
    position:absolute;top:0;left:0;width:100%;height:28px;margin:0;
    background:transparent;-webkit-appearance:none;appearance:none;pointer-events:none;
}
.filter-slider-range input[type=range]::-webkit-slider-thumb{
    pointer-events:auto;-webkit-appearance:none;width:14px;height:14px;
    border-radius:50%;background:var(--primary);border:2px solid var(--surface);
    cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.35);margin-top:8px;
}
.filter-slider-range input[type=range]::-moz-range-thumb{
    pointer-events:auto;width:14px;height:14px;border-radius:50%;
    background:var(--primary);border:2px solid var(--surface);cursor:pointer;
}
.filter-slider-reset{
    width:100%;margin-top:4px;padding:5px 0;border:1px solid var(--border);
    border-radius:3px;background:var(--surface2);color:var(--muted);
    font-size:10px;cursor:pointer;font-family:'Noto Sans SC',sans-serif;
    transition:all .15s;
}
.filter-slider-reset:hover{border-color:var(--primary);color:var(--primary);}

/* detail modal */
.detail-modal{
    position:fixed;inset:0;z-index:9999;
    background:rgba(0,0,0,0);
    display:none;align-items:center;justify-content:center;padding:18px;
    transition:background .22s;
}
.detail-modal.show{display:flex;background:rgba(0,0,0,.52);}
.detail-card{
    width:min(560px,96vw);max-height:85vh;
    background:var(--surface);
    border:1px solid var(--border);border-radius:14px;
    box-shadow:0 20px 60px rgba(0,0,0,.28),0 4px 12px rgba(0,0,0,.12);
    display:flex;flex-direction:column;overflow:hidden;
    transform:translateY(14px) scale(.97);opacity:0;
    transition:transform .26s cubic-bezier(.22,.68,0,1.2),opacity .22s;
}
body.dark .detail-card{box-shadow:0 20px 60px rgba(0,0,0,.55),0 4px 12px rgba(0,0,0,.3);}
.detail-modal.show .detail-card{transform:translateY(0) scale(1);opacity:1;}
.detail-hd{
    flex-shrink:0;
    display:flex;align-items:center;justify-content:space-between;gap:10px;
    padding:16px 18px 14px;
    background:var(--th-bg);
}
.detail-title-wrap{display:flex;align-items:center;gap:10px;}
.detail-icon{
    width:30px;height:30px;border-radius:8px;
    background:var(--primary-dim);
    display:flex;align-items:center;justify-content:center;
    font-size:15px;flex-shrink:0;
}
.detail-title{
    font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600;
    color:var(--th-text);letter-spacing:.02em;
}
.detail-meta{font-family:'Space Mono',monospace;font-size:10px;color:var(--faint);margin-top:2px;}
.detail-close{
    border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.06);
    color:rgba(255,255,255,.5);
    border-radius:8px;padding:5px 11px;cursor:pointer;font-size:12px;
    transition:all .18s;line-height:1.4;flex-shrink:0;
}
.detail-close:hover{border-color:var(--primary);color:var(--primary);background:var(--primary-dim);}
.detail-scroll{overflow-y:auto;padding:10px 10px 14px;}
.detail-scroll::-webkit-scrollbar{width:4px;}
.detail-scroll::-webkit-scrollbar-track{background:transparent;}
.detail-scroll::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
.detail-list{display:grid;gap:5px;padding:4px 2px;}
.detail-empty{
    padding:28px 0;text-align:center;
    font-size:13px;color:var(--faint);font-family:'Space Mono',monospace;
    letter-spacing:.06em;
}
.detail-item{
    display:flex;align-items:center;gap:10px;
    padding:8px 12px;border-radius:8px;
    border:1px solid var(--border2);background:var(--surface2);
    transition:background .12s,border-color .12s;
}
.detail-item:hover{background:var(--row-hover);border-color:var(--border);}
.detail-day{
    font-family:'Space Mono',monospace;font-size:10px;font-weight:700;
    color:var(--primary);letter-spacing:.06em;
    min-width:44px;flex-shrink:0;
    padding:3px 7px;border-radius:5px;
    background:var(--primary-dim);border:0.5px solid rgba(224,96,64,.22);
    text-align:center;
}
body.dark .detail-day{border-color:rgba(232,96,60,.28);}
.detail-val{font-size:13px;color:var(--ink);line-height:1.4;flex:1;}
.detail-footer{
    flex-shrink:0;
    display:flex;align-items:center;justify-content:center;
    padding:10px 18px 12px;
    border-top:1px solid var(--border2);
    font-family:'Space Mono',monospace;font-size:10px;color:var(--faint);
    letter-spacing:.06em;
}
.filterable-table tbody tr{cursor:pointer;}
.filterable-table tbody tr:hover td{background:var(--row-hover);}

@media(max-width:640px){
    body{padding:14px 12px 40px;}
    .topbar{margin-bottom:18px;}
    .page-title{font-size:20px;}
    .filterable-table{font-size:11px;}
    .filterable-table thead tr:first-child th,
    .filterable-table td{padding:5px 6px;white-space:nowrap;}
    .table-wrapper{max-height:62vh;}
    .podium{grid-template-columns:1fr;}
    .sch-name,.sbar-name{width:112px;}
    .sbar-tag{display:none;}
}"""


_CSS_ROUTE_QUERY = """\
.route-entry{display:flex;align-items:center;gap:14px;background:var(--surface);
    border:1px solid var(--border);border-radius:8px;padding:14px 18px;
    cursor:pointer;margin-bottom:18px;transition:border-color .15s,transform .15s;}
.route-entry:hover{border-color:var(--primary-rim);transform:translateY(-1px);}
.route-entry-icon{width:34px;height:34px;border-radius:8px;background:var(--primary-dim);
    display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px;}
.route-entry-text{flex:1;}
.route-entry-title{font-family:'Noto Serif SC',serif;font-size:14px;font-weight:600;color:var(--ink);}
.route-entry-desc{font-size:11.5px;color:var(--muted);margin-top:2px;}
.route-entry-arrow{font-size:15px;color:var(--faint);transition:transform .15s;}
.route-entry:hover .route-entry-arrow{transform:translateX(3px);color:var(--primary);}

.rq-select-box{border:1px solid var(--border);border-radius:6px;background:var(--surface2);
    margin-bottom:10px;overflow:hidden;}
.rq-search{width:100%;border:none;background:transparent;padding:8px 10px;font-size:12px;
    border-bottom:1px solid var(--border2);box-sizing:border-box;color:var(--ink);outline:none;
    font-family:'Noto Sans SC',sans-serif;}
.rq-search::placeholder{color:var(--faint);}
.rq-opt-list{max-height:160px;overflow-y:auto;}
.rq-opt{display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12px;cursor:pointer;
    border-bottom:1px solid var(--border2);color:var(--ink2);transition:background .12s;}
.rq-opt:last-child{border-bottom:none;}
.rq-opt:hover{background:var(--row-hover);}
.rq-opt.sel{background:var(--primary-dim);}
.rq-opt input[type=checkbox]{margin:0;accent-color:var(--primary);pointer-events:none;}
.rq-tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;min-height:24px;}
.rq-tag{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;
    font-size:11px;background:var(--primary-dim);color:var(--primary-dark);
    border:0.5px solid var(--primary-rim);}
.rq-tag-rm{cursor:pointer;opacity:.65;font-size:11px;}
.rq-tag-rm:hover{opacity:1;}
.rq-run-btn{width:100%;background:var(--primary);color:#fff;border:none;padding:9px;
    border-radius:6px;font-size:13px;cursor:pointer;margin-bottom:16px;
    font-family:'Noto Sans SC',sans-serif;transition:background .15s;}
.rq-run-btn:hover{background:var(--primary-dark);}
.rq-result-count{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;
    color:var(--faint);margin-bottom:8px;}
.rq-result-list{display:flex;flex-direction:column;gap:6px;max-height:280px;overflow-y:auto;}
.rq-result-row{display:flex;align-items:center;gap:10px;padding:8px 12px;
    border:1px solid var(--border2);background:var(--surface2);border-radius:8px;}
.rq-badge{font-size:9px;font-weight:700;color:var(--primary-dark);background:var(--primary-dim);
    padding:2px 7px;border-radius:5px;flex-shrink:0;white-space:nowrap;}
.rq-result-name{flex:1;font-size:12.5px;color:var(--ink);overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap;}
.rq-result-pick{font-size:11px;color:var(--faint);flex-shrink:0;white-space:nowrap;}
.rq-result-pick b{color:var(--ink);font-weight:500;}
.rq-empty{padding:28px 0;text-align:center;font-size:12.5px;color:var(--faint);
    font-family:'Space Mono',monospace;letter-spacing:.04em;}

@media(max-width:640px){
    .rq-result-pick{white-space:normal;}
}"""


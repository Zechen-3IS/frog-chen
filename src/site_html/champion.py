"""Champion hall page renderer."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from site_html import state
from site_html.common import _topbar, _title_tags
from site_html.css import _CSS_BASE, _CSS_INNER, _FONTS
from site_html.js import _JS_THEME
from site_html.types_meta import _type_cls, _type_order

_CSS_CHAMPION = """\
/* ── champion page: filter bar ── */
.filter-bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;padding:14px;
    background:var(--surface);border:1px solid var(--border2);border-radius:8px;
    align-items:center;}
.filter-group{display:flex;align-items:center;gap:6px;}
.filter-lbl{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);
    letter-spacing:.06em;white-space:nowrap;}
.filter-chips{display:flex;gap:5px;flex-wrap:wrap;}
.fchip{font-size:11px;padding:3px 10px;border-radius:20px;cursor:pointer;
    border:1px solid var(--border);background:var(--surface2);color:var(--muted);
    transition:all .15s;white-space:nowrap;font-family:'Noto Sans SC',sans-serif;}
.fchip:hover{border-color:var(--primary-rim);color:var(--primary-dark);}
.fchip.active{background:var(--primary-dim);color:var(--primary-dark);
    border-color:var(--primary-rim);font-weight:500;}
body.dark .fchip.active{color:var(--primary);}
.filter-divider{width:1px;height:20px;background:var(--border2);flex-shrink:0;}
.result-count{font-family:'Space Mono',monospace;font-size:11px;color:var(--faint);
    margin-left:auto;}
.result-count b{color:var(--primary);}
 
/* ── champion page: tournament accordion ── */
.tournament-list{display:flex;flex-direction:column;gap:10px;}
 
.t-card{background:var(--surface);border:1px solid var(--border);
    border-radius:8px;overflow:hidden;transition:border-color .15s;}
.t-card:hover{border-color:rgba(26,26,26,.2);}
body.dark .t-card:hover{border-color:rgba(240,236,230,.2);}
.t-card.open{border-color:var(--primary-rim);}
 
.t-header{display:flex;align-items:center;gap:12px;padding:14px 16px;
    cursor:pointer;user-select:none;}
.t-chevron{font-size:11px;color:var(--faint);transition:transform .2s;flex-shrink:0;}
.t-card.open .t-chevron{transform:rotate(180deg);}
 
.t-left{flex:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0;}
.t-name{font-size:14px;font-weight:600;color:var(--ink);}
.t-season{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;
    color:var(--faint);padding:2px 7px;border:1px solid var(--border2);border-radius:3px;}
.t-type{font-size:10px;padding:2px 8px;border-radius:10px;
    font-weight:500;white-space:nowrap;}
 
/* type pill colours — all 8 types in champions.csv */
.t-type.gs     {background:rgba(138,96,48,.10); color:#7a5020;
    border:.5px solid rgba(138,96,48,.28);}
.t-type.finals {background:rgba(100,60,160,.10);color:#5a30a0;
    border:.5px solid rgba(100,60,160,.28);}
.t-type.m1000  {background:var(--secondary-dim);color:var(--secondary);
    border:.5px solid var(--secondary-rim);}
.t-type.w1000  {background:var(--primary-dim);  color:var(--primary-dark);
    border:.5px solid var(--primary-rim);}
.t-type.m500   {background:rgba(40,86,168,.08); color:#4a6aaa;
    border:.5px solid rgba(40,86,168,.20);}
.t-type.w500   {background:rgba(224,96,64,.08); color:#b84828;
    border:.5px solid rgba(224,96,64,.20);}
.t-type.m250   {background:rgba(40,86,168,.05); color:#6a8ab8;
    border:.5px solid rgba(40,86,168,.14);}
.t-type.w250   {background:rgba(224,96,64,.05); color:#c86048;
    border:.5px solid rgba(224,96,64,.14);}
.t-type.other  {background:rgba(26,26,26,.05);  color:var(--muted);
    border:.5px solid var(--border);}
 
body.dark .t-type.gs     {color:#c8a060;}
body.dark .t-type.finals {color:#b090f0;}
body.dark .t-type.m500   {color:#90b8f4;}
body.dark .t-type.w500   {color:#e8806a;}
body.dark .t-type.m250   {color:#7898c8;}
body.dark .t-type.w250   {color:#d87060;}
body.dark .t-type.m1000  {color:var(--secondary);}
body.dark .t-type.w1000  {color:var(--primary);}
 
.t-right{display:flex;align-items:center;gap:6px;flex-shrink:0;}
.t-count{font-family:'Space Mono',monospace;font-size:11px;color:var(--faint);}
.t-count b{color:var(--primary);font-weight:700;}
 
.t-body{display:none;border-top:1px solid var(--border2);padding:14px 16px;}
.t-card.open .t-body{display:block;}
 
.winners-grid{display:grid;
    grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;}
.winner-chip{display:flex;align-items:center;gap:8px;padding:8px 10px;
    background:var(--surface2);border:1px solid var(--border2);border-radius:6px;
    cursor:pointer;transition:border-color .15s,background .15s;}
.winner-chip:hover{border-color:var(--primary-rim);background:var(--primary-dim);}
.winner-num{font-family:'Space Mono',monospace;font-size:11px;
    color:var(--faint);flex-shrink:0;width:18px;text-align:right;}
.winner-name{font-size:12px;color:var(--ink2);
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
 
@media(max-width:640px){
    .filter-bar{gap:6px;padding:10px;}
    .filter-divider{display:none;}
    .filter-group{width:100%;}
    .result-count{width:100%;margin-left:0;}
    .winners-grid{grid-template-columns:repeat(auto-fill,minmax(120px,1fr));}
}"""

_JS_CHAMPION = """\
(function(){
    var seasonFilter = 'all';
    var typeFilter   = 'all';
 
    function applyFilters(){
        var cards = document.querySelectorAll('.t-card[data-season]');
        var shown = 0;
        cards.forEach(function(card){
            var ok = (seasonFilter === 'all' || card.dataset.season === seasonFilter)
                  && (typeFilter   === 'all' || card.dataset.type   === typeFilter);
            card.style.display = ok ? '' : 'none';
            if (ok) shown++;
        });
        var rc = document.getElementById('resultCount');
        if (rc) rc.innerHTML =
            '显示 <b>' + shown + '</b> / <b>' + cards.length + '</b> 场赛事';
    }
 
    window.championSetFilter = function(el, kind, val) {
        el.closest('.filter-chips')
          .querySelectorAll('.fchip')
          .forEach(function(c){ c.classList.remove('active'); });
        el.classList.add('active');
        if (kind === 'season') seasonFilter = val;
        else                   typeFilter   = val;
        applyFilters();
    };
 
    window.toggleTCard = function(header){
        header.parentElement.classList.toggle('open');
    };

    window.championShowWinnerDetail = function(username){
        var allStats = window.CHAMPION_USER_STATS || {};
        var st = allStats[username];
        var modal = document.getElementById('champion-detail-modal');
        var closeBtn = document.getElementById('champion-detail-close');
        var metaLine = document.getElementById('champion-detail-meta-line');
        var body = document.getElementById('champion-detail-body');
        var footer = document.getElementById('champion-detail-footer');
        if (!modal || !closeBtn || !metaLine || !body || !footer) return;

        function closeModal(){
            var card = modal.querySelector('.detail-card');
            if(card){ card.style.transform='translateY(10px) scale(.97)'; card.style.opacity='0'; }
            setTimeout(function(){
                modal.classList.remove('show');
                if(card){ card.style.transform=''; card.style.opacity=''; }
            },220);
        }

        if (!modal.dataset.bound){
            closeBtn.addEventListener('click', closeModal);
            modal.addEventListener('click', function(e){ if(e.target===modal) closeModal(); });
            document.addEventListener('keydown', function(e){
                if(e.key==='Escape' && modal.classList.contains('show')) closeModal();
            });
            modal.dataset.bound = '1';
        }

        metaLine.textContent = username || '';
        if (!st){
            body.innerHTML = '<div class="detail-empty">暂无冠军记录</div>';
            footer.textContent = '';
            modal.classList.add('show');
            return;
        }

        var byType = Array.isArray(st.by_type) ? st.by_type : [];
        var total = Number(st.total || 0);

        var rows = [];
        rows.push(
            '<div class="detail-item">'
          + '<span class="detail-day">总计</span>'
          + '<span class="detail-val">' + total + '个冠军头衔</span>'
          + '</div>'
        );
        byType.forEach(function(item){
            var events = Array.isArray(item.events) ? item.events : [];
            var eventText = events.length ? '（' + events.join('，') + '）' : '';
            rows.push(
                '<div class="detail-item">'
              + '<span class="detail-day">' + item.type + '</span>'
              + '<span class="detail-val">' + item.count + ' ' + eventText + '</span>'
              + '</div>'
            );
        });
        body.innerHTML = rows.join('');
        footer.textContent = '共 ' + byType.length + ' 种赛事类型';
        modal.classList.add('show');
    };
 
    applyFilters();
})();"""

def render_champion_page(
    df: pd.DataFrame,
    title: str,
    tour: str,
    eyebrow: str,
    updated: str,
    extra_tags: Optional[list[str]] = None,
    username_col: str = "username",
    tournament_col: str = "tournament",
    tournament_type_col: str = "type",
    season_col: str = "season",
    week_col: str = "week",
    output_path: str | Path = "champion.html",
    theme: str = "clay",
) -> str:
    """
    Build and write a 冠军榜 page.

    Parameters
    ----------
    df : pd.DataFrame
        Slice of champions.csv for one tour, e.g.
            pd.read_csv("champions.csv", encoding="utf-8-sig")
              .pipe(lambda d: d[d["tour"] == "ATP"])

        Expected columns (defaults match champions.csv exactly):
            username | tournament | type | season

    title      : str    e.g. "ATP冠军榜"
    tour       : str    "ATP" | "WTA"
    eyebrow    : str    e.g. "ATP · Hall of Champions · All Time"
    updated    : str    timestamp string
    extra_tags : list[str] | None

    username_col / tournament_col / tournament_type_col / season_col / week_col
        Column-name overrides — only needed if your CSV differs from
        the champions.csv schema.

    output_path : str | Path

    Returns
    -------
    str : generated HTML
    """
    # ── build filter chips from data ─────────────────────────────────────────
    seasons = sorted(
        df[season_col].dropna().astype(str).unique().tolist(),
        reverse=True,
    )
    df[tournament_type_col] = df[tournament_type_col].astype(str).str.strip()
    raw_types = df[tournament_type_col].replace("nan", pd.NA).dropna().unique().tolist()
    types = sorted(raw_types, key=lambda t: (_type_order(t), t))

    def _season_chips() -> str:
        chips = [
            '<span class="fchip active" '
            "onclick=\"championSetFilter(this,'season','all')\">全部</span>"
        ]
        for s in seasons:
            chips.append(
                f'<span class="fchip" '
                f"onclick=\"championSetFilter(this,'season','{html.escape(s)}')\">"
                f"{html.escape(s)}</span>"
            )
        return "\n      ".join(chips)

    def _type_chips() -> str:
        chips = [
            '<span class="fchip active" '
            "onclick=\"championSetFilter(this,'type','all')\">全部</span>"
        ]
        for t in types:
            chips.append(
                f'<span class="fchip" '
                f"onclick=\"championSetFilter(this,'type','{html.escape(t)}')\">"
                f"{html.escape(t)}</span>"
            )
        return "\n      ".join(chips)

    # ── sort rows: week desc (latest first), then season/type/name fallback ──
    df2 = df.copy()
    df2["_s"] = df2[season_col].astype(str)
    df2["_w"] = df2[tournament_type_col].apply(_type_order)
    if week_col in df2.columns:
        df2["_week_dt"] = pd.to_datetime(df2[week_col], errors="coerce")
        # Missing/unparseable dates are sent to the end.
        df2 = df2.sort_values(
            ["_week_dt", "_s", "_w", tournament_col],
            ascending=[False, False, True, True],
            na_position="last",
        )
    else:
        df2 = df2.sort_values(
            ["_s", "_w", tournament_col], ascending=[False, True, True]
        )

    # ── group into ordered dict: (tournament, season) → {type, winners} ──────
    groups: dict[tuple[str, str], dict] = {}
    for _, row in df2.iterrows():
        key = (str(row[tournament_col]), str(row["_s"]))
        if key not in groups:
            groups[key] = {"type": str(row[tournament_type_col]), "winners": []}
        w = str(row[username_col])
        if w and w not in groups[key]["winners"]:
            groups[key]["winners"].append(w)

    total = len(groups)

    # ── winner stats for click detail popup: username -> total + type breakdown ─
    # include tournament list per type, e.g. "WTA500: 2 (2025东京，2026布里斯班)"
    type_ordered = sorted(types, key=lambda t: (_type_order(t), t))
    df_stats = df[
        df[username_col].notna()
        & df[tournament_type_col].notna()
        & (df[username_col].astype(str).str.strip() != "")
    ].copy()
    user_total_counts = df_stats.groupby(username_col).size().to_dict()
    user_type_events: dict[tuple[str, str], list[str]] = {}
    for _, r in df_stats.iterrows():
        uname = str(r[username_col])
        ttype = str(r[tournament_type_col])
        seas = str(r[season_col])
        tname = str(r[tournament_col])
        label = f"{seas}{tname}"
        key = (uname, ttype)
        if key not in user_type_events:
            user_type_events[key] = []
        if label not in user_type_events[key]:
            user_type_events[key].append(label)

    winner_stats: dict[str, dict] = {}
    for user, total_cnt in user_total_counts.items():
        uname = str(user)
        by_type = []
        for t in type_ordered:
            events = user_type_events.get((uname, str(t)), [])
            cnt = len(events)
            if cnt > 0:
                by_type.append({"type": str(t), "count": cnt, "events": events})
        winner_stats[uname] = {"total": int(total_cnt), "by_type": by_type}

    # ── accordion cards ───────────────────────────────────────────────────────
    card_parts: list[str] = []
    for i, ((tname, tseason), info) in enumerate(groups.items()):
        ttype = info["type"]
        winners = info["winners"]
        open_cls = "open" if i == 0 else ""

        winner_chips_html = "\n      ".join(
            f'<div class="winner-chip" '
            f'data-username="{html.escape(w, quote=True)}" '
            f'onclick="championShowWinnerDetail(this.dataset.username)" '
            f'title="点击查看 {html.escape(w)} 的冠军明细">'
            f'<span class="winner-num">{j + 1}.</span>'
            f'<span class="winner-name" title="{html.escape(w)}">'
            f"{html.escape(w)}</span>"
            f"</div>"
            for j, w in enumerate(winners)
        )

        card_parts.append(f"""\
<div class="t-card {open_cls}"
     data-season="{html.escape(tseason)}"
     data-type="{html.escape(ttype)}">
  <div class="t-header" onclick="toggleTCard(this)">
    <span class="t-chevron">▼</span>
    <div class="t-left">
      <span class="t-name">{html.escape(tname)}</span>
      <span class="t-season">{html.escape(tseason)}</span>
      <span class="t-type {_type_cls(ttype)}">{html.escape(ttype)}</span>
    </div>
    <div class="t-right">
      <span class="t-count"><b>{len(winners)}</b> 位冠军</span>
    </div>
  </div>
  <div class="t-body">
    <div class="winners-grid">
      {winner_chips_html}
    </div>
  </div>
</div>""")

    # ── page body ─────────────────────────────────────────────────────────────
    body = f"""\
<div class="filter-bar">
  <div class="filter-group">
    <span class="filter-lbl">赛季</span>
    <div class="filter-chips">
      {_season_chips()}
    </div>
  </div>
  <div class="filter-divider"></div>
  <div class="filter-group">
    <span class="filter-lbl">赛事类型</span>
    <div class="filter-chips">
      {_type_chips()}
    </div>
  </div>
  <span class="result-count" id="resultCount">
    显示 <b>{total}</b> / <b>{total}</b> 场赛事
  </span>
</div>
 
<div class="tournament-list">
{"".join(card_parts)}
</div>

<div id="champion-detail-modal" class="detail-modal">
  <div class="detail-card">
    <div class="detail-hd">
      <div class="detail-title-wrap">
        <div class="detail-icon">🏆</div>
        <div>
          <div class="detail-title">冠军明细</div>
          <div class="detail-meta" id="champion-detail-meta-line"></div>
        </div>
      </div>
      <button id="champion-detail-close" class="detail-close" type="button">✕ 关闭</button>
    </div>
    <div class="detail-scroll">
      <div id="champion-detail-body" class="detail-list"></div>
    </div>
    <div class="detail-footer" id="champion-detail-footer"></div>
  </div>
</div>"""

    # ── full page shell ───────────────────────────────────────────────────────
    tags_html = _title_tags(tour, extra_tags)

    html_str = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
{_FONTS}
<style>
{state.css_vars}
{_CSS_BASE}
{_CSS_INNER}
{_CSS_CHAMPION}
</style>
</head>
<body>
<div class="page">
 
{_topbar(updated)}
 
<div class="page-header">
  <div class="page-eye">{html.escape(eyebrow)}</div>
  <div class="page-title">
    {html.escape(title)}
    {tags_html}
  </div>
</div>
 
{body}
 
</div>
<script>
window.CHAMPION_USER_STATS = {json.dumps(winner_stats, ensure_ascii=False)};
{_JS_THEME}
{_JS_CHAMPION}
</script>
</body>
</html>"""

    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


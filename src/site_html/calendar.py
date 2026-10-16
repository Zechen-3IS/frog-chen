"""Survivor calendar + per-event score detail page renderers."""
from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from site_html.common import (
    _df_to_html_table,
    _inner_page_shell,
)
from site_html.js import _JS_RANKING_DETAIL
from site_html.types_meta import (
    _type_cls,
    _type_order,
    champion_type_label,
    type_filters_for_tour,
)

_CSS_CALENDAR = """\
.filter-bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;padding:14px;
    background:var(--surface);border:1px solid var(--border2);border-radius:8px;
    align-items:center;}
.filter-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.filter-lbl{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);
    letter-spacing:.06em;white-space:nowrap;}
.filter-chips{display:flex;gap:5px;flex-wrap:wrap;}
.filter-divider{width:1px;height:20px;background:var(--border2);flex-shrink:0;}
.fchip{font-size:11px;padding:3px 10px;border-radius:20px;cursor:pointer;
    border:1px solid var(--border);background:var(--surface2);color:var(--muted);
    transition:all .15s;white-space:nowrap;}
.fchip:hover{border-color:var(--primary-rim);color:var(--primary-dark);}
.fchip.active{background:var(--primary-dim);color:var(--primary-dark);
    border-color:var(--primary-rim);font-weight:500;}
body.dark .fchip.active{color:var(--primary);}
.result-count{font-family:'Space Mono',monospace;font-size:11px;color:var(--faint);
    margin-left:auto;}
.result-count b{color:var(--primary);}

.cal-legend{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px;
    font-size:11px;color:var(--muted);}
.cal-legend span{display:inline-flex;align-items:center;gap:6px;}

.cal-table{width:100%;border-collapse:separate;border-spacing:0 8px;}
.cal-table th{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.12em;
    text-transform:uppercase;color:var(--faint);font-weight:500;text-align:left;
    padding:0 12px 4px;}
.cal-row{display:none;}
.cal-row.show{display:table-row;}
.cal-table td{background:var(--surface);border-top:1px solid var(--border2);
    border-bottom:1px solid var(--border2);padding:12px 14px;vertical-align:middle;}
.cal-table td:first-child{border-left:1px solid var(--border2);border-radius:8px 0 0 8px;}
.cal-table td:last-child{border-right:1px solid var(--border2);border-radius:0 8px 8px 0;}
.cal-date{font-family:'Space Mono',monospace;font-size:13px;font-weight:600;
    color:var(--ink);white-space:nowrap;width:72px;}
.cal-cells{display:flex;flex-wrap:wrap;gap:8px;}
.cal-link{display:inline-flex;align-items:center;gap:8px;padding:7px 12px;
    border-radius:6px;border:1px solid var(--border2);text-decoration:none;
    background:var(--surface2);color:var(--ink);font-size:13px;font-weight:500;
    transition:border-color .15s,transform .15s;}
.cal-link:hover{border-color:var(--primary-rim);transform:translateY(-1px);}
.cal-link.disabled{opacity:.45;pointer-events:none;cursor:default;}
.cal-link.hide{display:none;}
.cal-city{font-size:13px;font-weight:600;color:var(--ink);}
.cal-meta{font-family:'Space Mono',monospace;font-size:10px;color:var(--faint);}
.cal-empty{padding:28px 12px;color:var(--faint);font-size:13px;}
.cal-note{margin-top:16px;font-size:12px;color:var(--faint);line-height:1.7;}
.cal-note a{color:var(--muted);}

/* type pills — same palette as champion hall */
.t-type{font-size:10px;padding:2px 8px;border-radius:10px;
    font-weight:500;white-space:nowrap;}
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

.score-meta{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;
    font-size:12px;color:var(--muted);align-items:center;}
.score-meta b{color:var(--ink);font-weight:600;}
.score-meta a{color:var(--muted);}

.score-stats{display:flex;flex-direction:column;gap:10px;margin-bottom:16px;}
.score-stats-row{display:grid;gap:10px;}
.score-stats-row.solo{grid-template-columns:1fr;}
.score-stats-row.pair{grid-template-columns:1fr 1fr;}
@media(max-width:640px){
    .score-stats-row.pair{grid-template-columns:1fr;}
}
.score-stat{padding:12px 14px;border:1px solid var(--border2);border-radius:8px;
    background:var(--surface);}
.score-stat-lbl{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;
    color:var(--faint);margin-bottom:6px;}
.score-stat-val{font-size:14px;font-weight:600;color:var(--ink);line-height:1.45;
    word-break:break-word;}
.score-stat-val .muted{font-weight:500;color:var(--muted);font-size:12px;}
.score-stat-val .sub{display:block;margin-top:4px;font-size:11px;font-weight:500;
    color:var(--faint);font-family:'Space Mono',monospace;}
.score-stat-val .sub + .sub{margin-top:2px;}
/* Champion / upset pickers — same chips as homepage 赛况 */
.score-stat-val .wk-chips{display:flex;flex-wrap:wrap;gap:5px;font-weight:400;}
.score-stat-val .wk-chip{display:inline-block;max-width:100%;padding:3px 9px;border-radius:999px;
    background:rgba(42,107,79,.08);border:0.5px solid rgba(42,107,79,.18);
    color:#1f4f3a;font-size:12px;line-height:1.35;font-weight:500;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis;}
body.dark .score-stat-val .wk-chip{background:rgba(125,206,160,.12);
    border-color:rgba(125,206,160,.22);color:#b7e0c6;}



.cal-hub{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;
    margin-top:8px;}
.cal-hub a{display:block;padding:20px 18px;border:1px solid var(--border2);border-radius:10px;
    background:var(--surface);text-decoration:none;color:var(--ink);
    transition:border-color .15s,transform .15s;}
.cal-hub a:hover{border-color:var(--primary-rim);transform:translateY(-1px);}
.cal-hub .eye{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.12em;
    color:var(--faint);margin-bottom:8px;}
.cal-hub .ttl{font-family:'Noto Serif SC',serif;font-size:20px;font-weight:700;margin-bottom:6px;}
.cal-hub .desc{font-size:13px;color:var(--muted);line-height:1.5;}

@media(max-width:640px){
    .filter-divider{display:none;}
    .filter-group{width:100%;}
    .result-count{width:100%;margin-left:0;}
}
"""

_JS_CALENDAR = """\
(function(){
  var yearFilter = null;
  var typeFilter = 'all';
  var yearChips = document.querySelectorAll('.fchip[data-year]');
  var typeChips = document.querySelectorAll('.fchip[data-type]');
  var rows = document.querySelectorAll('.cal-row[data-year]');
  var countEl = document.getElementById('cal-count');

  function apply(){
    var shown = 0;
    rows.forEach(function(row){
      var yearOk = !yearFilter || row.getAttribute('data-year') === yearFilter;
      var links = row.querySelectorAll('.cal-link[data-type]');
      var any = false;
      links.forEach(function(link){
        var typeOk = typeFilter === 'all' || link.getAttribute('data-type') === typeFilter;
        var show = yearOk && typeOk;
        link.classList.toggle('hide', !show);
        if (show) any = true;
      });
      row.classList.toggle('show', yearOk && any);
      if (yearOk && any) shown++;
    });
    if (countEl) countEl.textContent = String(shown);
  }

  yearChips.forEach(function(chip){
    chip.addEventListener('click', function(){
      yearChips.forEach(function(c){ c.classList.remove('active'); });
      chip.classList.add('active');
      yearFilter = chip.getAttribute('data-year');
      apply();
    });
  });
  typeChips.forEach(function(chip){
    chip.addEventListener('click', function(){
      typeChips.forEach(function(c){ c.classList.remove('active'); });
      chip.classList.add('active');
      typeFilter = chip.getAttribute('data-type') || 'all';
      apply();
    });
  });

  var activeYear = document.querySelector('.fchip.active[data-year]');
  yearFilter = activeYear ? activeYear.getAttribute('data-year') : null;
  var activeType = document.querySelector('.fchip.active[data-type]');
  typeFilter = activeType ? (activeType.getAttribute('data-type') || 'all') : 'all';
  apply();
})();
"""


def _tour_label(tour: str) -> str:
    t = str(tour or "").upper()
    if t in {"MS", "ATP"}:
        return "ATP"
    if t in {"WS", "WTA"}:
        return "WTA"
    return t or "ALL"


def _tour_code(tour: str) -> str:
    t = str(tour or "").upper()
    if t in {"MS", "ATP"}:
        return "MS"
    if t in {"WS", "WTA"}:
        return "WS"
    return t


def _enrich_event(ev: dict[str, Any]) -> dict[str, Any]:
    out = dict(ev)
    city = str(out.get("city") or "")
    tour = str(out.get("tour") or "")
    label = str(out.get("type") or "").strip() or champion_type_label(city, tour)
    out["type"] = label
    out["type_cls"] = _type_cls(label)
    return out


def _group_weeks(events: list[dict[str, Any]]) -> list[tuple[str, str, list[dict]]]:
    """Return [(year, week_start, [events...]), ...] sorted."""
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ev in events:
        year = str(ev.get("year") or "")
        week = str(ev.get("week_start") or "")
        buckets[(year, week)].append(ev)
    out = []
    for (year, week) in sorted(buckets.keys(), reverse=True):
        items = sorted(
            buckets[(year, week)],
            key=lambda e: (_type_order(e.get("type") or ""), e.get("city") or ""),
        )
        out.append((year, week, items))
    return out


def render_calendar_page(
    events: list[dict[str, Any]],
    years: list[int],
    updated: str,
    output_path: str | Path,
    *,
    tour: str = "ALL",
    default_year: Optional[int] = None,
) -> str:
    tour_code = _tour_code(tour) if str(tour).upper() not in {"", "ALL"} else ""
    tour_lbl = _tour_label(tour_code) if tour_code else "ALL"
    filtered = []
    for ev in events:
        if tour_code and str(ev.get("tour") or "").upper() != tour_code:
            continue
        filtered.append(_enrich_event(ev))

    years_sorted = sorted({int(y) for y in years}, reverse=True)
    default_year = int(default_year or (years_sorted[0] if years_sorted else 0))

    year_chips = []
    for y in years_sorted:
        active = " active" if int(y) == default_year else ""
        year_chips.append(
            f'<button type="button" class="fchip{active}" data-year="{int(y)}">{int(y)}</button>'
        )
    year_chips_html = "\n".join(year_chips)

    type_chips = [
        '<button type="button" class="fchip active" data-type="all">全部</button>'
    ]
    for t in type_filters_for_tour(tour_code or "MS"):
        type_chips.append(
            f'<button type="button" class="fchip" data-type="{html.escape(t)}">{html.escape(t)}</button>'
        )
    type_chips_html = "\n".join(type_chips)

    weeks = _group_weeks(filtered)
    row_html = []
    for year, week, items in weeks:
        mmdd = ""
        for ev in items:
            if ev.get("week_mmdd"):
                mmdd = str(ev["week_mmdd"])
                break
        if not mmdd and week:
            mmdd = week[5:10] if len(week) >= 10 else week

        cells = []
        for ev in items:
            city = html.escape(str(ev.get("city") or ""))
            href = html.escape(str(ev.get("href") or "#"))
            n = int(ev.get("n_players") or 0)
            has = bool(ev.get("has_scores"))
            tlabel = html.escape(str(ev.get("type") or ""))
            tcls = html.escape(str(ev.get("type_cls") or "other"))
            meta = f"{n} 人" if has else "暂无得分"
            disabled = "" if has else " disabled"
            tag = "a" if has else "span"
            href_attr = f' href="{href}"' if has else ""
            cells.append(
                f'<{tag} class="cal-link{disabled}" data-type="{tlabel}"{href_attr}>'
                f'<span class="t-type {tcls}">{tlabel}</span>'
                f'<span class="cal-city">{city}</span>'
                f'<span class="cal-meta">{meta}</span>'
                f"</{tag}>"
            )
        cells_html = (
            f'<div class="cal-cells">{"".join(cells)}</div>'
            if cells
            else '<span class="cal-meta">休赛</span>'
        )
        show = " show" if int(year) == default_year else ""
        row_html.append(
            f'<tr class="cal-row{show}" data-year="{html.escape(str(year))}">'
            f'<td class="cal-date">{html.escape(mmdd)}</td>'
            f"<td>{cells_html}</td>"
            f"</tr>"
        )

    title = f"{tour_lbl}幸存者赛历" if tour_lbl != "ALL" else "幸存者赛历"
    eyebrow = (
        f"{tour_lbl} · Survivor Calendar"
        if tour_lbl != "ALL"
        else "Survivor · Calendar"
    )
    sibling = ""
    if tour_lbl == "ATP":
        sibling = (
            '<div class="cal-note">切换：'
            '<a href="survivor_calendar_wta.html">WTA 赛历</a></div>'
        )
    elif tour_lbl == "WTA":
        sibling = (
            '<div class="cal-note">切换：'
            '<a href="survivor_calendar_atp.html">ATP 赛历</a></div>'
        )

    body = f"""\
<div class="filter-bar">
  <div class="filter-group">
    <span class="filter-lbl">年份</span>
    <div class="filter-chips">
      {year_chips_html}
    </div>
  </div>
  <div class="filter-divider"></div>
  <div class="filter-group">
    <span class="filter-lbl">级别</span>
    <div class="filter-chips">
      {type_chips_html}
    </div>
  </div>
  <div class="result-count">显示 <b id="cal-count">0</b> 周</div>
</div>

<div class="cal-legend">
  <span>级别标签与冠军榜一致 · 点击赛事查看本站得分与选人明细</span>
</div>

<table class="cal-table">
  <thead>
    <tr><th>开赛周</th><th>赛事</th></tr>
  </thead>
  <tbody>
    {''.join(row_html) if row_html else '<tr><td colspan="2" class="cal-empty">暂无赛历数据</td></tr>'}
  </tbody>
</table>

{sibling}
<div class="cal-note">
  数据对齐
  <a href="https://www.live-tennis.cn/zh/survivor/calendar/{default_year}" target="_blank" rel="noopener">丘的网球 · 签表幸存者赛历</a>
  ；得分明细对应各站 score 榜（按本站得分从高到低）。
</div>
"""

    html_str = _inner_page_shell(
        page_title=title,
        title=title,
        tour=tour_lbl if tour_lbl != "ALL" else "ALL",
        eyebrow=eyebrow,
        updated=updated,
        extra_tags=["历年", "级别"],
        body_content=body,
        extra_js=_JS_CALENDAR,
        extra_css=_CSS_CALENDAR,
    )
    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


def render_calendar_hub_page(
    *,
    updated: str,
    output_path: str | Path,
) -> str:
    """Legacy combined URL → choose ATP / WTA calendar."""
    body = """\
<div class="cal-hub">
  <a href="survivor_calendar_atp.html" class="atp">
    <div class="eye">ATP · MEN</div>
    <div class="ttl">ATP 幸存者赛历</div>
    <div class="desc">男单赛程 · 按年份与级别浏览，查看本站得分</div>
  </a>
  <a href="survivor_calendar_wta.html" class="wta">
    <div class="eye">WTA · WOMEN</div>
    <div class="ttl">WTA 幸存者赛历</div>
    <div class="desc">女单赛程 · 按年份与级别浏览，查看本站得分</div>
  </a>
</div>
"""
    html_str = _inner_page_shell(
        page_title="幸存者赛历",
        title="幸存者赛历",
        tour="ALL",
        eyebrow="Survivor · Calendar",
        updated=updated,
        extra_tags=["ATP", "WTA"],
        body_content=body,
        extra_css=_CSS_CALENDAR,
    )
    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


def _format_champions(names: list[str], *, max_show: int = 6) -> str:
    """One chip per name — same look as homepage 赛况 ``wk-chip`` list."""
    del max_show  # keep call-site compat; never truncate (matches index 赛况)
    clean = [html.escape(str(x).strip()) for x in (names or []) if str(x).strip()]
    if not clean:
        return '<span class="muted">未产生</span>'
    chips = "".join(f'<span class="wk-chip">{n}</span>' for n in clean)
    return f'<span class="wk-chips">{chips}</span>'


def render_event_score_page(
    df: pd.DataFrame,
    *,
    city: str,
    tour: str,
    year: int,
    event_id: str,
    updated: str,
    output_path: str | Path,
    source_url: str = "",
    stats: Optional[dict[str, Any]] = None,
    type_label: str = "",
) -> str:
    tour_u = str(tour).upper()
    tour_lbl = _tour_label(tour_u)
    type_label = str(type_label or "").strip() or champion_type_label(city, tour_u)
    type_cls = _type_cls(type_label)
    title = f"{city} · {year}"
    table_html = _df_to_html_table(
        df,
        rank_change_col=None,
        detail_col="选人明细",
        hide_detail_col=True,
    )
    n = len(df)
    back_href = (
        "../../survivor_calendar_atp.html"
        if tour_lbl == "ATP"
        else "../../survivor_calendar_wta.html"
    )
    stats = stats or {}
    champions = list(stats.get("champions") or [])
    day_killer = str(stats.get("day_killer") or "").strip()
    day_detail = stats.get("day_detail") or None
    total_killer = str(
        stats.get("total_killer") or stats.get("top_killer") or ""
    ).strip()
    total_kills = int(stats.get("total_kills") or stats.get("top_kills") or 0)
    total_details = list(stats.get("total_details") or [])
    upset = stats.get("biggest_upset") or None
    champ_html = _format_champions(champions)
    n_champs = len([x for x in champions if str(x).strip()])
    champ_lbl = f"冠军 · {n_champs}人"

    def _kill_line(detail: dict[str, Any]) -> str:
        idx = int(detail.get("day_index") or 0)
        loser = html.escape(str(detail.get("loser") or "").strip() or "?")
        kills = int(detail.get("kills") or 0)
        return f"第{idx + 1}日胜{loser} · 带走 {kills} 人"

    if day_killer and isinstance(day_detail, dict):
        day_killer_html = (
            f"{html.escape(day_killer)}"
            f'<span class="sub">{_kill_line(day_detail)}</span>'
        )
    elif day_killer:
        idx = int(stats.get("day_index") or 0)
        kills = int(stats.get("day_kills") or 0)
        loser = str(stats.get("day_loser") or "").strip()
        line = (
            f"第{idx + 1}日胜{html.escape(loser)} · 带走 {kills} 人"
            if loser
            else f"第{idx + 1}日带走 {kills} 人"
        )
        day_killer_html = (
            f"{html.escape(day_killer)}<span class=\"sub\">{line}</span>"
        )
    else:
        day_killer_html = '<span class="muted">暂无</span>'

    if total_killer:
        detail_html = "".join(
            f'<span class="sub">{_kill_line(d)}</span>'
            for d in total_details
            if isinstance(d, dict)
        )
        if not detail_html:
            detail_html = f'<span class="sub">共带走 {total_kills} 人</span>'
        elif len(total_details) > 1:
            detail_html += f'<span class="sub">合计 {total_kills} 人</span>'
        total_killer_html = f"{html.escape(total_killer)}{detail_html}"
    else:
        total_killer_html = '<span class="muted">暂无</span>'
    if isinstance(upset, dict) and upset.get("winner") and upset.get("loser"):
        w = html.escape(str(upset["winner"]))
        l = html.escape(str(upset["loser"]))
        nw = int(upset.get("winner_picks") or 0)
        nl = int(upset.get("loser_picks") or 0)
        users = [
            str(u).strip()
            for u in (upset.get("winner_users") or [])
            if str(u).strip()
        ]
        # Main: users who picked the underdog; sub: match + pick counts.
        if users:
            users_html = _format_champions(users)
        elif nw > 0:
            users_html = f'<span class="muted">{nw} 人</span>'
        else:
            users_html = '<span class="muted">暂无</span>'
        upset_html = (
            f"{users_html}"
            f'<span class="sub">{w}胜{l} · 选人 {nw}:{nl}</span>'
        )
    else:
        upset_html = '<span class="muted">暂无</span>'

    detail_modal = """\
    <div id="detail-modal" class="detail-modal">
      <div class="detail-card">
        <div class="detail-hd">
          <div class="detail-title-wrap">
            <div class="detail-icon">📋</div>
            <div>
              <div class="detail-title">选人明细</div>
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

    body = f"""\
<div class="score-meta">
  <span class="t-type {html.escape(type_cls)}">{html.escape(type_label)}</span>
  <span>参赛 <b>{n}</b> 人</span>
</div>
<div class="score-stats">
  <div class="score-stats-row solo">
    <div class="score-stat">
      <div class="score-stat-lbl">{html.escape(champ_lbl)}</div>
      <div class="score-stat-val">{champ_html}</div>
    </div>
  </div>
  <div class="score-stats-row pair">
    <div class="score-stat">
      <div class="score-stat-lbl">单日克星</div>
      <div class="score-stat-val">{day_killer_html}</div>
    </div>
    <div class="score-stat">
      <div class="score-stat-lbl">累计克星</div>
      <div class="score-stat-val">{total_killer_html}</div>
    </div>
  </div>
  <div class="score-stats-row solo">
    <div class="score-stat">
      <div class="score-stat-lbl">最大爆冷</div>
      <div class="score-stat-val">{upset_html}</div>
    </div>
  </div>
</div>
<div class="stats-row">
  <div class="row-count">显示 <b id="visible-count">0</b> / <b id="total-count">0</b> 行</div>
</div>
<div class="table-wrapper">
  <div id="table-container">
  {table_html}
  </div>
</div>
{detail_modal}
"""

    html_str = _inner_page_shell(
        page_title=f"{city} {year} 本站得分",
        title=title,
        tour=tour_lbl,
        eyebrow=f"{tour_lbl} · Event Score · {event_id}",
        updated=updated,
        extra_tags=[str(year), type_label, "得分"],
        body_content=body,
        extra_js=_JS_RANKING_DETAIL,
        back_label=f"← {tour_lbl}赛历",
        back_href=back_href,
        extra_css=_CSS_CALENDAR,
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_str, encoding="utf-8")
    return html_str

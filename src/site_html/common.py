"""Shared HTML helpers: tables, summary bar, route query, page shell."""
from __future__ import annotations

import ast
import html
import json
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from site_html import state
from site_html.css import _CSS_BASE, _CSS_INNER, _CSS_ROUTE_QUERY, _FONTS
from site_html.js import _JS_TABLE, _JS_THEME
from site_html.logos import _logo_pair

def _rank_change_cell(value) -> str:
    """Convert a numeric rank-change value to a styled <span>."""
    try:
        v = int(value)
    except (ValueError, TypeError):
        return f'<span class="rank same"></span>'
    if v > 0:
        return f'<span class="rank up">+{v}</span>'
    if v < 0:
        return f'<span class="rank down">{v}</span>'
    return f'<span class="rank same"></span>'


def _status_badge_html(val) -> str:
    """Color badge for 当前状态 (存活 / 未完赛·未选 / 淘汰)."""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(val).strip()
    if not text:
        return ""
    if text == "存活":
        cls = "st-alive"
    elif text in {"未完赛", "未选", "轮空"}:
        cls = "st-live"
    elif text in {"球员输球", "未参赛"} or text.startswith("自杀"):
        # 自杀 / 球员输球 share one淘汰色
        cls = "st-out"
    else:
        cls = "st-other"
    return f'<span class="st-badge {cls}">{html.escape(text)}</span>'


def _row_status_class(val) -> str:
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(val).strip()
    if text == "存活":
        return "row-alive"
    if text in {"未完赛", "未选", "轮空"}:
        return "row-live"
    if text in {"球员输球", "未参赛"} or text.startswith("自杀"):
        return "row-out"
    return ""


# Count / day / rank columns must never show trailing ".0".
_INT_COL_HINTS = (
    "天数",
    "排名",
    "积分",
    "得分",
    "周数",
    "参赛",
    "冠军",
    "亚军",
    "连胜",
    "连败",
)


def _format_table_cell(col: object, val: object) -> str:
    """Stringify a cell; force whole numbers for day/rank/score columns."""
    try:
        if hasattr(val, "item"):
            val = val.item()
    except (TypeError, ValueError, OverflowError):
        pass
    col_s = str(col or "")
    want_int = any(h in col_s for h in _INT_COL_HINTS) and "率" not in col_s
    if want_int:
        try:
            num = float(val)
            if num == num:  # not NaN
                return str(int(round(num)))
        except (TypeError, ValueError, OverflowError):
            pass
    try:
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
    except (TypeError, ValueError, OverflowError):
        pass
    text = str(val).strip()
    if text.endswith(".0"):
        head = text[:-2]
        if head.lstrip("-").isdigit():
            return head
    return text


def _df_to_html_table(
    df: pd.DataFrame,
    rank_change_col: Optional[str] = "排名变化",
    detail_col: Optional[str] = None,
    hide_detail_col: bool = True,
    uid_col: Optional[str] = "主键",
    hide_uid_col: bool = True,
    row_click_class: str = "",
) -> str:
    """
    Convert a DataFrame to a styled filterable HTML table.

    Parameters
    ----------
    df : pd.DataFrame
    rank_change_col : str or None
        Column name whose values are rendered as ▲/▼ badges.
        Pass None to skip badge rendering entirely.
    uid_col : str or None
        When present, emit ``data-uid`` on each row (for combined breakdown).
    """
    skip = set()
    if hide_detail_col and detail_col:
        skip.add(detail_col)
    if hide_uid_col and uid_col and uid_col in df.columns:
        skip.add(uid_col)
    render_cols = [c for c in df.columns if c not in skip]
    status_cols = {
        c
        for c in render_cols
        if c == "当前状态" or str(c).endswith("状态")
    }
    status_col = "当前状态" if "当前状态" in status_cols else (
        next(iter(status_cols), None)
    )
    lines = ['<table class="dataframe filterable-table">']

    # thead
    lines.append("  <thead><tr>")
    for col in render_cols:
        lines.append(f"    <th>{html.escape(str(col))}</th>")
    lines.append("  </tr></thead>")

    # tbody
    lines.append("  <tbody>")
    for _, row in df.iterrows():
        row_cls = ""
        if "当前状态" in status_cols:
            row_cls = _row_status_class(row.get("当前状态"))
        if row_click_class:
            row_cls = f"{row_cls} {row_click_class}".strip()
        cls_attr = f' class="{row_cls}"' if row_cls else ""
        extra_attrs = ""
        if uid_col and uid_col in df.columns:
            uid_val = row.get(uid_col)
            try:
                if pd.isna(uid_val):
                    uid_val = ""
            except (TypeError, ValueError):
                pass
            uid_text = html.escape(str(uid_val).strip(), quote=True)
            if uid_text:
                extra_attrs += f' data-uid="{uid_text}"'
        if detail_col and detail_col in df.columns:
            raw_detail = row.get(detail_col, [])
            if isinstance(raw_detail, dict):
                details = raw_detail
            elif isinstance(raw_detail, list):
                details = [str(x) for x in raw_detail]
            elif isinstance(raw_detail, str):
                s = raw_detail.strip()
                if not s:
                    details = []
                else:
                    try:
                        parsed = ast.literal_eval(s)
                        details = (
                            [str(x) for x in parsed]
                            if isinstance(parsed, list)
                            else (
                                parsed if isinstance(parsed, dict) else [s]
                            )
                        )
                    except Exception:
                        details = [s]
            else:
                try:
                    is_na = bool(pd.isna(raw_detail))
                except (TypeError, ValueError):
                    is_na = False
                details = [] if is_na else [str(raw_detail)]
            detail_json = html.escape(
                json.dumps(details, ensure_ascii=False), quote=True
            )
            lines.append(
                f'  <tr{cls_attr}{extra_attrs} data-detail="{detail_json}">'
            )
        else:
            lines.append(f"  <tr{cls_attr}{extra_attrs}>")
        for col in render_cols:
            val = row[col]
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            if rank_change_col and col == rank_change_col:
                cell_html = _rank_change_cell(val)
            elif col in status_cols:
                cell_html = _status_badge_html(val)
            else:
                try:
                    is_na = bool(pd.isna(val))
                except (TypeError, ValueError):
                    is_na = False
                if is_na:
                    cell_html = ""
                else:
                    cell_html = html.escape(_format_table_cell(col, val))
            lines.append(f"    <td>{cell_html}</td>")
        lines.append("  </tr>")
    lines.append("  </tbody>")
    lines.append("</table>")
    return "\n".join(lines)

def _summary_bar_html(
    df: pd.DataFrame,
    top_n: int = 3,
    available_players: Optional[list[str]] = None,
    live_players: Optional[list[str]] = None,
    backup_events: Optional[list] = None,
) -> str:
    """
    Convert a generate_summary() DataFrame into the bar-chart summary panel.

    Detects mode automatically from column names:
        - Normal day : columns include "已选"   (no "轮空" column)
        - Day-1 bye  : columns include "非轮空" AND "轮空"

    The total row is identified by  df["今日主选"] == "总计".

    Parameters
    ----------
    df     : output of generate_summary()
    top_n  : rows shown before "show all" toggle (default 5)
    available_players : still-alive draw players
    live_players : subset still in a live match (未完赛); others in
        available_players are treated as 存活
    backup_events : aggregated early-retirement backup activations

    Returns
    -------
    str : self-contained HTML + <script> block for the panel.
    """
    # Gracefully handle empty / malformed summary input
    if df is None or df.empty:
        return ""

    cols = df.columns.tolist()
    if "今日主选" not in cols:
        return ""

    has_bye = "轮空" in cols
    normal_col = "非轮空" if has_bye else "已选"
    if normal_col not in cols:
        # Fallback for slight label drift, e.g. "已选 " or " 非轮空"
        for c in cols:
            c2 = str(c).strip()
            if (not has_bye and c2.startswith("已选")) or (
                has_bye and c2.startswith("非轮空")
            ):
                normal_col = c
                break
    suicide_col = "自杀（重复）" if "自杀（重复）" in cols else None
    invalid_col = "自杀（主备冲突）" if "自杀（主备冲突）" in cols else None
    nosel_col = "未选" if "未选" in cols else None
    alive_set = {
        str(p).strip()
        for p in (available_players or [])
        if str(p).strip()
    }
    live_set = {
        str(p).strip()
        for p in (live_players or [])
        if str(p).strip()
    }
    status_known = bool(alive_set)

    def _player_status(name: str) -> Optional[str]:
        if not status_known:
            return None
        if name in live_set:
            return "live"
        if name in alive_set:
            return "confirmed"
        return "out"

    # ── split data rows from totals row ──────────────────────────────────────
    mask_total = df["今日主选"] == "总计"
    data_df = df[~mask_total].copy()
    total_row = df[mask_total].iloc[0] if mask_total.any() else None

    # ── derive meta numbers from totals row ──────────────────────────────────
    def _int(series_or_val) -> int:
        try:
            return int(series_or_val)
        except (ValueError, TypeError):
            return 0

    if total_row is not None:
        valid_total = _int(total_row.get(normal_col, 0))
        bye_total = _int(total_row.get("轮空", 0)) if has_bye else 0
        repeat_total = _int(total_row.get(suicide_col, 0)) if suicide_col else 0
        invalid_total = _int(total_row.get(invalid_col, 0)) if invalid_col else 0
        nosel_total = _int(total_row.get(nosel_col, 0)) if nosel_col else 0
        suicide_total = repeat_total + invalid_total
        grand_total = _int(total_row.get("总计", 0))
    else:
        valid_total = int(data_df[normal_col].sum()) if normal_col in cols else 0
        bye_total = int(data_df["轮空"].sum()) if has_bye else 0
        repeat_total = int(data_df[suicide_col].sum()) if suicide_col in cols else 0
        invalid_total = int(data_df[invalid_col].sum()) if suicide_col in cols else 0
        nosel_total = int(data_df[nosel_col].sum()) if nosel_col in cols else 0
        suicide_total = repeat_total + invalid_total
        grand_total = valid_total + bye_total + suicide_total

    # denominator for % column = all valid selections (non-suicide)
    valid_denom = valid_total + bye_total or 1

    # ── max bar value (for scaling) ───────────────────────────────────────────
    data_df["_total"] = data_df.get(
        normal_col, pd.Series(0, index=data_df.index)
    ).fillna(0).astype(int) + (
        data_df.get("轮空", pd.Series(0, index=data_df.index)).fillna(0).astype(int)
        if has_bye
        else 0
    )
    max_val = int(data_df["_total"].max()) or 1

    # ── meta chips HTML ───────────────────────────────────────────────────────
    meta_parts = [
        f'<span class="meta-chip chip-valid">✓ 非轮空 {valid_total} 人</span>',
    ]
    if has_bye:
        meta_parts = [
            f'<span class="meta-chip chip-valid">✓ 非轮空 {valid_total} 人</span>',
        ]
        meta_parts += [
            '<span class="meta-sep">｜</span>',
            f'<span class="meta-chip chip-bye">◎ 轮空 {bye_total} 人</span>',
        ]
    else:
        meta_parts = [
            f'<span class="meta-chip chip-valid">✓ {valid_total} 人已选</span>',
        ]
        meta_parts += [
            '<span class="meta-sep">｜</span>',
            f'<span class="meta-chip chip-nosel">{nosel_total} 人未选</span>',
        ]

    if suicide_total > 0:
        meta_parts += [
            '<span class="meta-sep">｜</span>',
            f'<span class="meta-chip chip-suicide">⚠ {suicide_total} 人自杀</span>',
        ]

    meta_parts += [
        '<span class="meta-sep">｜</span>',
        f'<span class="meta-total">总计 {grand_total} 人</span>',
    ]
    meta_html = "\n    ".join(meta_parts)

    # ── column-header HTML ────────────────────────────────────────────────────
    if has_bye:
        col_hd_html = """\
    <div class="sum-col-hd">
    <span class="sch-rank"></span>
    <span class="sch-name"></span>
    <span class="sch-bar"></span>
    <div class="sch-right">
    <span class="sch-tag sch-tag-v">已选</span>
    <span class="sch-sep">/</span>
    <span class="sch-tag sch-tag-b">轮空</span>
    </div>
    <span class="sch-count">人数</span>
    <span class="sch-pct">占比</span>
    </div>"""
    else:
        col_hd_html = """\
    <div class="sum-col-hd">
    <span class="sch-rank"></span>
    <span class="sch-name"></span>
    <span class="sch-bar"></span>
    <span class="sch-count">人数</span>
    <span class="sch-pct">占比</span>
    </div>"""

    # ── build JSON data for JS renderer ──────────────────────────────────────
    import json

    backup_by_primary: dict[str, list] = {}
    for item in backup_events or []:
        primary = str(item.get("primary") or "").strip()
        if not primary:
            continue
        backs = []
        for back in item.get("backs") or []:
            backs.append(
                {
                    "name": str(back.get("name") or "").strip(),
                    "alive": int(back.get("alive") or 0),
                    "live": int(back.get("live") or 0),
                    "out": int(back.get("out") or 0),
                }
            )
        if backs:
            backup_by_primary[primary] = backs

    rows_js = []
    for _, r in data_df.iterrows():
        normal_n = int(r.get(normal_col, 0) or 0)
        bye_n = int(r.get("轮空", 0) or 0) if has_bye else 0
        name = str(r["今日主选"]).strip()
        # Skip empty / synthetic bye label — bye count lives in meta chips only.
        if name and name != "轮空":
            status = _player_status(name)
            backs = backup_by_primary.get(name) or []
            if backs:
                status = "backup"
            row_obj = {
                "name": name,
                "normal": normal_n,
                "bye": bye_n,
                "status": status,
            }
            if backs:
                row_obj["backs"] = backs
            rows_js.append(row_obj)

    rows_json = json.dumps(rows_js, ensure_ascii=False)
    totals_json = json.dumps(
        {
            "normal": valid_total,
            "bye": bye_total,
            "grand": valid_denom,
        },
        ensure_ascii=False,
    )

    # ── meta summary text for clipboard (header line) ────────────────────────
    if has_bye:
        header_parts = [f"非轮空{valid_total}", f"轮空{bye_total}"]
    else:
        header_parts = [f"已选{valid_total}", f"未选{nosel_total}"]
    if suicide_total > 0:
        header_parts.append(f"自杀{suicide_total}")
    clipboard_header = json.dumps(" ".join(header_parts), ensure_ascii=False)

    # ── assemble HTML ─────────────────────────────────────────────────────────
    return f"""\
        <div class="sum-box">
        <div class="sum-header">
        <div class="sum-title-row">
        <span class="sum-title">今日选人统计</span>
        <button class="sum-copy-btn" id="sumCopyBtn" onclick="copySumStats()" title="复制选人统计文本">
            <span id="sumCopyIcon">⎘</span>
            <span id="sumCopyTxt">复制</span>
        </button>
        </div>
        <div class="sum-meta">
        {meta_html}
        </div>
        </div>
        {col_hd_html}
        <div class="sum-list" id="sumList"></div>
        <button class="sum-toggle" id="sumToggle" onclick="toggleSumPanel()">
        <span id="sumToggleTxt">显示全部 {len(rows_js)} 名球员）</span>
        <span class="sum-ticon" id="sumTicon">▼</span>
        </button>
    </div>
    <script>
    (function(){{
        var TOP_N   = {top_n};
        var HAS_BYE = {'true' if has_bye else 'false'};
        var ROWS    = {rows_json};
        var TOTALS  = {totals_json};
        var MAX_VAL = {max_val};
        var CLIPBOARD_HEADER = {clipboard_header};
        var expanded = false;

        function pct(n){{ return ((n / TOTALS.grand) * 100).toFixed(1) + '%'; }}

        function trackClass(r){{
        if (r.status === 'out') return 'solo-out';
        if (r.status === 'backup') return 'solo-bak';
        if (r.status === 'live') return 'solo-live';
        if (r.status === 'confirmed') return 'solo-alive';
        if (!HAS_BYE) return 'solo-v';
        if (r.normal > 0 && r.bye > 0) return 'both';
        return r.bye > 0 ? 'solo-b' : 'solo-v';
        }}

        function statusClass(r){{
        if (r.status === 'live') return 'is-live';
        if (r.status === 'backup') return 'is-bak';
        if (r.status === 'confirmed') return 'is-alive';
        if (r.status === 'out') return 'is-out';
        return '';
        }}

        function nameHtml(r){{
        var tip = r.name;
        var tag = '';
        if (r.status === 'live') {{
            tip += ' · 未完赛';
            tag = '<span class="sbar-tag tag-live">未完赛</span>';
        }} else if (r.status === 'backup') {{
            tip += ' · 启用备选';
            tag = '<span class="sbar-tag tag-bak">启用备选</span>';
        }} else if (r.status === 'confirmed') {{
            tip += ' · 存活';
            tag = '<span class="sbar-tag tag-alive">存活</span>';
        }} else if (r.status === 'out') {{
            tip += ' · 淘汰';
            tag = '<span class="sbar-tag tag-out">淘汰</span>';
        }}
        return '<span class="sbar-name" title="' + tip + '">' +
            '<i class="sbar-dot" aria-hidden="true"></i>' +
            '<span class="sbar-label">' + r.name + '</span>' +
            tag +
            '</span>';
        }}

        function segClass(r){{
        if (r.status === 'out') return 'seg-out';
        if (r.status === 'backup') return 'seg-bak';
        if (r.status === 'live') return 'seg-live';
        if (r.status === 'confirmed') return 'seg-alive';
        return 'seg-v';
        }}

        function statusMark(r){{
        if (r.status === 'out') return '❌';
        if (r.status === 'backup') return '↪️';
        if (r.status === 'confirmed') return '✅';
        if (r.status === 'live') return '⭕️';
        return '';
        }}

        function bakChips(b){{
        var parts = [];
        if (b.alive) parts.push('<span class="meta-chip chip-alive">' + b.alive + ' 人存活</span>');
        if (b.live) parts.push('<span class="meta-chip chip-live">' + b.live + ' 人未完赛</span>');
        if (b.out) parts.push('<span class="meta-chip chip-out">' + b.out + ' 人淘汰</span>');
        return parts.join('');
        }}

        function renderList(){{
        var list = document.getElementById('sumList');
        list.innerHTML = '';

        ROWS.forEach(function(r, i){{
            var tot   = r.normal + r.bye;
        var normW = Math.round(r.normal / MAX_VAL * 100);
        var byeW  = Math.round(r.bye    / MAX_VAL * 100);
            var hidden = i >= TOP_N;
            var hideCls = hidden && !expanded ? 's-hidden' : '';
            var expCls = hidden && expanded ? 's-exp' : '';

            var cls = ['sbar-row',
            statusClass(r),
            hideCls,
            expCls,
            ].filter(Boolean).join(' ');

            var inlineHtml = HAS_BYE
            ? '<div class="sbar-inline">' +
                '<span class="sbar-iv">' + r.normal + '</span>' +
                '<span class="sbar-isep">/</span>' +
                '<span class="sbar-ib">' + r.bye + '</span>' +
                '</div>'
            : '';

            var row = document.createElement('div');
            row.className = cls;
            row.innerHTML =
            '<span class="sbar-rank">' + (i+1) + '</span>' +
            nameHtml(r) +
            '<div class="sbar-track ' + trackClass(r) + '">' +
                '<div class="sbar-seg ' + segClass(r) + '" style="width:' + normW + '%"></div>' +
                (HAS_BYE && r.status !== 'out' && r.status !== 'backup' ? '<div class="sbar-seg seg-b" style="width:' + byeW + '%"></div>' : '') +
            '</div>' +
            inlineHtml +
            '<div class="sbar-right">' +
                '<span class="sbar-count">' + tot + '</span>' +
                '<span class="sbar-pct">'  + pct(tot) + '</span>' +
            '</div>';
            list.appendChild(row);

            if (r.backs && r.backs.length) {{
                r.backs.forEach(function(b){{
                    var chips = bakChips(b);
                    if (!chips) return;
                    var bak = document.createElement('div');
                    bak.className = ['sbar-bak', hideCls, expCls].filter(Boolean).join(' ');
                    bak.innerHTML =
                        '<span class="sbar-rank"></span>' +
                        '<span class="sbar-bak-main">' +
                          '<span class="bak-arrow">→</span>' +
                          '<span class="bak-alt">' + (b.name || '无备选') + '</span>' +
                          '<span class="bak-chips">' + chips + '</span>' +
                        '</span>';
                    list.appendChild(bak);
                }});
            }}
        }});

        /* totals row */
        var totInline = HAS_BYE
            ? '<div class="sbar-inline">' +
            '<span class="sbar-iv">' + TOTALS.normal + '</span>' +
            '<span class="sbar-isep">/</span>' +
            '<span class="sbar-ib">' + TOTALS.bye + '</span>' +
            '</div>'
            : '';
        var tot = document.createElement('div');
        tot.className = 'sbar-row stotal';
        tot.innerHTML =
            '<span class="sbar-rank"></span>' +
            '<span class="sbar-name">有效总计</span>' +
            '<div class="sbar-track" style="opacity:0;flex:1;pointer-events:none"></div>' +
            totInline +
            '<div class="sbar-right">' +
            '<span class="sbar-count">' + TOTALS.grand + '</span>' +
            '<span class="sbar-pct">100%</span>' +
            '</div>';
        list.appendChild(tot);

        /* button label */
        var hidN = ROWS.length - TOP_N;
        var btn  = document.getElementById('sumToggle');
        var txt  = document.getElementById('sumToggleTxt');
        var ico  = document.getElementById('sumTicon');
        btn.classList.toggle('open', expanded);
        ico.style.transform = expanded ? 'rotate(180deg)' : '';
        txt.textContent = expanded
            ? '收起'
            : '显示全部 ' + ROWS.length + ' 名球员';
        }}

        window.toggleSumPanel = function(){{
        expanded = !expanded;
        renderList();
        if (expanded) {{
            var segs = document.querySelectorAll('#sumList .sbar-row.s-exp .sbar-seg');
            segs.forEach(function(el){{
            var w = el.style.width; el.style.width = '0%';
            requestAnimationFrame(function(){{ el.style.width = w; }});
            }});
            }}
        }};

        window.copySumStats = function(){{
            var lines = [CLIPBOARD_HEADER];
            ROWS.forEach(function(r){{
                if (r.normal === 0 && r.bye === 0) return;
                var mark = statusMark(r);
                var named = mark ? (mark + r.name) : r.name;
                var line;
                if (HAS_BYE) {{
                    line = named + ' ' + r.normal + '(' + r.bye + ')';
                }} else {{
                    line = named + ' ' + r.normal;
                }}
                lines.push(line);
                if (r.backs && r.backs.length) {{
                    r.backs.forEach(function(b){{
                        var bits = [];
                        if (b.alive) bits.push('存活' + b.alive);
                        if (b.live) bits.push('未完赛' + b.live);
                        if (b.out) bits.push('淘汰' + b.out);
                        if (bits.length) {{
                            lines.push('→ ' + (b.name || '无备选') + ' ' + bits.join(' '));
                        }}
                    }});
                }}
            }});
            var text = lines.join('\\n');
            navigator.clipboard.writeText(text).then(function(){{
                var btn = document.getElementById('sumCopyBtn');
                var txt = document.getElementById('sumCopyTxt');
                if (!btn) return;
                btn.classList.add('copied');
                txt.textContent = '已复制';
                setTimeout(function(){{
                    btn.classList.remove('copied');
                    txt.textContent = '复制';
                }}, 2000);
            }}).catch(function(){{
                /* fallback for older browsers */
                var ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                var btn = document.getElementById('sumCopyBtn');
                var t   = document.getElementById('sumCopyTxt');
                if (btn) {{ btn.classList.add('copied'); }}
                if (t)   {{ t.textContent = '已复制'; }}
                setTimeout(function(){{
                    if (btn) {{ btn.classList.remove('copied'); }}
                    if (t)   {{ t.textContent = '复制'; }}
                }}, 2000);
            }});
        }};

        renderList();
    }})();
    </script>"""


def _killer_panel_html(stats_df: Optional[pd.DataFrame], panel_id: str = "dayKiller") -> str:
    """
    Collapsible「每日杀手统计」panel (chen F7).

    Expects columns: 天数, 杀手球员1, 死亡人数1, 杀手球员2, 死亡人数2.
    """
    if stats_df is None or stats_df.empty:
        return ""

    rows_html = []
    for _, r in stats_df.iterrows():
        day = html.escape(str(r.get("天数", "")))
        k1 = html.escape(str(r.get("杀手球员1", "") or ""))
        n1 = html.escape(str(r.get("死亡人数1", "") or ""))
        k2 = html.escape(str(r.get("杀手球员2", "") or ""))
        n2 = html.escape(str(r.get("死亡人数2", "") or ""))
        rows_html.append(
            f'<div class="dk-row">'
            f'<span class="dk-day">Day {day}</span>'
            f'<div class="dk-killers">'
            f'<span class="dk-k"><b>{k1}</b><em>{n1}</em></span>'
            + (f'<span class="dk-k alt"><b>{k2}</b><em>{n2}</em></span>' if k2 else "")
            + f"</div></div>"
        )

    return f"""\
    <div class="dk-box" id="{html.escape(panel_id)}">
      <button type="button" class="dk-toggle" onclick="toggleDayKiller('{html.escape(panel_id)}')">
        <span class="dk-toggle-txt">显示每日杀手统计</span>
        <span class="dk-arrow">▼</span>
      </button>
      <div class="dk-body">
        <div class="dk-hd">
          <span class="dk-hd-day">天数</span>
          <span class="dk-hd-k">杀手 Top1</span>
          <span class="dk-hd-k">杀手 Top2</span>
        </div>
        {"".join(rows_html)}
      </div>
    </div>
    <script>
    (function(){{
      if (window.toggleDayKiller) return;
      window.toggleDayKiller = function(id){{
        var box = document.getElementById(id);
        if (!box) return;
        box.classList.toggle('open');
        var txt = box.querySelector('.dk-toggle-txt');
        if (txt) txt.textContent = box.classList.contains('open')
          ? '收起每日杀手统计' : '显示每日杀手统计';
      }};
    }})();
    </script>"""


def _load_available_players(
    available_players: Union[list[str], str, Path, None],
) -> list[str]:
    """Accept a plain list, or a path to a JSON file containing a flat
    list of player names (e.g. available_players.json), and normalize
    to a list[str]."""
    if available_players is None:
        return []
    if isinstance(available_players, (str, Path)):
        with open(available_players, encoding="utf-8") as f:
            data = json.load(f)
        return [str(p) for p in data]
    return [str(p) for p in available_players]


def _route_query_block(available_players: Optional[list[str]] = None) -> str:
    """
    Build the "夺冠路线查询" entry bar + modal HTML.

    Parameters
    ----------
    available_players : list[str] or None
        Players still alive in the draw (e.g. loaded from
        available_players.json). Rendered as a searchable multi-select
        inside the modal. Pass None / [] to render the bar with an
        empty player list (the modal will just show no options).

    Returns
    -------
    str : HTML fragment (entry bar + modal), meant to be placed between
          the summary panel and the ranking table in render_ranking_page().
    """
    players = available_players or []
    opts_html = "\n".join(
        f'          <div class="rq-opt" data-player="{html.escape(p, quote=True)}">'
        f'<input type="checkbox">{html.escape(p)}</div>'
        for p in players
    )
    if not opts_html:
        opts_html = '          <div class="rq-empty">暂无可选球员</div>'

    return f"""\
<div class="route-entry" id="rq-entry">
  <div class="route-entry-icon">🏆</div>
  <div class="route-entry-text">
    <div class="route-entry-title">夺冠路线查询</div>
    <div class="route-entry-desc">选择球员，查看谁还没选过ta们</div>
  </div>
  <span class="route-entry-arrow">🔍</span>
</div>

<div id="rq-modal" class="detail-modal">
  <div class="detail-card">
    <div class="detail-hd">
      <div class="detail-title-wrap">
        <div class="detail-icon">🏆</div>
        <div>
          <div class="detail-title">夺冠路线查询</div>
          <div class="detail-meta">选择球员后点击查询</div>
        </div>
      </div>
      <button id="rq-close" class="detail-close" type="button">✕ 关闭</button>
    </div>
    <div class="detail-scroll">
      <div style="font-size:11px;color:var(--muted);margin-bottom:6px;">选择球员</div>
      <div class="rq-select-box">
        <input type="text" class="rq-search" id="rq-search" placeholder="搜索球员...">
        <div class="rq-opt-list" id="rq-opt-list">
{opts_html}
        </div>
      </div>
      <div class="rq-tags" id="rq-tags"></div>
      <button class="rq-run-btn" id="rq-run-btn" type="button">查询 →</button>
      <div class="rq-result-count" id="rq-result-count"></div>
      <div class="rq-result-list" id="rq-result-list">
        <div class="rq-empty">选择球员后点击查询查看结果</div>
      </div>
    </div>
  </div>
</div>"""


# ── Shared HTML fragments ──────────────────────────────────────────────────────


def _topbar(
    updated: str, back_label: str = "← 首页", back_href: str = "index.html"
) -> str:
    return f"""\
<div class="topbar">
  <a class="back-link" href="{back_href}">
    {_logo_pair(28)}
    {html.escape(back_label)}
  </a>
  <div class="topbar-right">
    <span class="updated">⏱ {html.escape(updated)}</span>
    <button class="theme-btn" id="themeBtn" onclick="toggleTheme()">🌙 暗色</button>
  </div>
</div>"""


def _title_tags(tour: str, extra_tags: list[str] | None = None) -> str:
    """Render the coloured pill tags next to the page title."""
    css = {"ATP": "ttag-atp", "WTA": "ttag-wta"}.get(tour.upper(), "ttag-all")
    out = f'<span class="ttag {css}">{html.escape(tour)}</span>'
    for tag in extra_tags or []:
        out += f'\n      <span class="ttag ttag-all">{html.escape(tag)}</span>'
    return out


def _inner_page_shell(
    page_title: str,
    title: str,
    tour: str,
    eyebrow: str,
    updated: str,
    extra_tags: list[str] | None,
    body_content: str,
    extra_js: str = "",
    back_label: str = "← 首页",
    back_href: str = "index.html",
    extra_css: str = "",
    after_page: str = "",
) -> str:
    """Wrap body_content in the full inner-page HTML shell."""
    tags_html = _title_tags(tour, extra_tags)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(page_title)}</title>
{_FONTS}
<style>
{state.css_vars}
{_CSS_BASE}
{_CSS_INNER}
{_CSS_ROUTE_QUERY}
{extra_css}
</style>
</head>
<body>
<div class="page">

{_topbar(updated, back_label=back_label, back_href=back_href)}

<div class="page-header">
  <div class="page-eye">{html.escape(eyebrow)}</div>
  <div class="page-title">
    {html.escape(title)}
    {tags_html}
  </div>
</div>

{body_content}

</div>
{after_page}
<script>
{extra_js}
{_JS_THEME}
{_JS_TABLE}
</script>
</body>
</html>"""


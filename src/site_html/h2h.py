"""H2H lookup page renderer."""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from site_html import state
from site_html.common import _topbar, _title_tags
from site_html.css import _CSS_BASE, _CSS_INNER, _FONTS
from site_html.js import _JS_THEME

_CSS_H2H = """\
/* ── selector panel ── */
.selector-panel{background:var(--surface);border:1px solid var(--border);
    border-radius:10px;padding:20px;margin-bottom:20px;}
.selector-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px;}
@media(max-width:700px){.selector-grid{grid-template-columns:1fr;}}
.sel-group{display:flex;flex-direction:column;gap:6px;}
.sel-label{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--muted);}
.multisel-box{border:1px solid var(--border);border-radius:6px;
    background:var(--surface2);overflow:hidden;}
.multisel-search{width:100%;padding:7px 10px;border:none;
    border-bottom:1px solid var(--border2);background:transparent;
    color:var(--ink);font-size:12px;outline:none;font-family:'Noto Sans SC',sans-serif;}
.multisel-search::placeholder{color:var(--faint);}
.multisel-search:focus{border-bottom-color:var(--primary);}
.multisel-list{max-height:160px;overflow-y:auto;padding:4px 0;}
.multisel-list::-webkit-scrollbar{width:4px;}
.multisel-list::-webkit-scrollbar-track{background:transparent;}
.multisel-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
.opt-item{display:flex;align-items:center;gap:8px;padding:6px 10px;
    cursor:pointer;font-size:12px;color:var(--ink2);
    border-bottom:1px solid var(--border2);transition:background .1s;}
.opt-item:last-child{border-bottom:none;}
.opt-item:hover{background:var(--row-hover);}
.opt-item.checked{background:var(--primary-dim);}
.opt-item input[type=checkbox]{margin:0;accent-color:var(--primary);cursor:pointer;flex-shrink:0;}
.opt-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.opt-empty{padding:14px 10px;font-size:12px;color:var(--faint);text-align:center;}
.sel-footer{display:flex;align-items:center;justify-content:space-between;
    flex-wrap:wrap;gap:8px;padding-top:4px;}
.sel-tags{display:flex;flex-wrap:wrap;gap:5px;flex:1;min-height:28px;align-items:center;}
.sel-tag{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;
    border-radius:20px;font-size:11px;
    background:var(--primary-dim);color:var(--primary-dark);border:0.5px solid var(--primary-rim);}
.sel-tag-player{background:var(--secondary-dim);color:var(--secondary);border-color:var(--secondary-rim);}
body.dark .sel-tag-player{color:var(--secondary);}
.sel-tag-season{background:rgba(26,26,26,.06);color:var(--muted);border-color:var(--border);}
body.dark .sel-tag-season{background:rgba(255,255,255,.06);}
.sel-tag-rm{background:none;border:none;cursor:pointer;color:inherit;
    font-size:13px;line-height:1;padding:0;opacity:.65;}
.sel-tag-rm:hover{opacity:1;}
.sel-summary{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.sel-summary-pill{
    display:inline-flex;align-items:center;gap:6px;
    padding:3px 10px;border-radius:999px;font-size:11px;
    font-family:'Space Mono',monospace;letter-spacing:.02em;
    border:0.5px solid var(--primary-rim);
    background:var(--primary-dim);color:var(--primary-dark);
}
.sel-summary-pill b{font-weight:700;}
.sel-summary-pill.player{
    background:var(--secondary-dim);color:var(--secondary);border-color:var(--secondary-rim);
}
.sel-summary-pill.season{
    background:rgba(26,26,26,.06);color:var(--muted);border-color:var(--border);
}
body.dark .sel-summary-pill.player{color:var(--secondary);}
body.dark .sel-summary-pill.season{background:rgba(255,255,255,.06);}
.sel-summary-toggle{
    background:none;border:1px solid var(--border);color:var(--muted);
    padding:3px 10px;border-radius:999px;font-size:11px;
    font-family:'Noto Sans SC',sans-serif;cursor:pointer;line-height:1.3;
    transition:all .2s;
}
.sel-summary-toggle:hover{border-color:var(--primary);color:var(--primary);}
.sel-expanded{
    width:100%;margin-top:6px;padding-top:6px;border-top:1px dashed var(--border2);
    display:flex;flex-wrap:wrap;gap:5px;max-height:120px;overflow:auto;
}
.sel-expanded::-webkit-scrollbar{width:4px;height:4px;}
.sel-expanded::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
.sel-actions{display:flex;gap:8px;flex-shrink:0;}
.run-btn{background:var(--primary);color:#fff;border:none;
    padding:9px 22px;border-radius:6px;font-size:13px;
    font-family:'Noto Sans SC',sans-serif;cursor:pointer;font-weight:500;
    letter-spacing:.02em;transition:background .2s;white-space:nowrap;}
.run-btn:hover{background:var(--primary-dark);}
.run-btn:disabled{opacity:.45;cursor:not-allowed;}
.clear-btn{background:none;border:1px solid var(--border);color:var(--muted);
    padding:9px 16px;border-radius:6px;font-size:12px;
    font-family:'Noto Sans SC',sans-serif;cursor:pointer;transition:all .2s;}
.clear-btn:hover{border-color:var(--primary);color:var(--primary);}
/* ── section divider ── */
.section-div{display:flex;align-items:center;gap:10px;margin:20px 0 14px;}
.div-label{font-family:'Space Mono',monospace;font-size:10px;
    letter-spacing:.22em;text-transform:uppercase;color:var(--faint);}
.div-rule{flex:1;height:1px;background:var(--border2);}
/* ── scoreboard ── */
.scoreboard{display:grid;grid-template-columns:1fr auto 1fr;
    background:var(--surface);border:1px solid var(--border);
    border-radius:10px;overflow:hidden;margin-bottom:16px;}
.score-side{padding:20px 24px;text-align:center;}
.score-side.left{border-right:1px solid var(--border2);}
.score-side.right{border-left:1px solid var(--border2);}
.score-vs-col{padding:20px 16px;display:flex;align-items:center;
    justify-content:center;background:var(--surface2);}
.vs-text{font-family:'Space Mono',monospace;font-size:11px;color:var(--faint);letter-spacing:.1em;}
.score-label{font-family:'Space Mono',monospace;font-size:9px;
    letter-spacing:.18em;text-transform:uppercase;color:var(--faint);margin-bottom:4px;}
.score-names{font-size:11px;color:var(--muted);margin-bottom:10px;
    min-height:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.score-num{font-family:'Space Mono',monospace;font-size:38px;font-weight:700;line-height:1;}
.score-num.win{color:var(--win,#2a7a4a);}
.score-num.lose{color:var(--lose,#c04830);}
.score-sub{font-size:11px;color:var(--faint);margin-top:4px;}
/* ── stat strip ── */
.stat-strip{display:grid;grid-template-columns:repeat(4,1fr);
    border:1px solid var(--border);border-radius:8px;overflow:hidden;
    background:var(--surface);margin-bottom:20px;}
.stat-cell{padding:14px 12px;text-align:center;border-right:1px solid var(--border);}
.stat-cell:last-child{border-right:none;}
.stat-val{font-family:'Space Mono',monospace;font-size:18px;
    font-weight:700;color:var(--primary);line-height:1;margin-bottom:4px;}
.stat-val.win{color:var(--win,#2a7a4a);}
.stat-lbl{font-size:10px;color:var(--faint);letter-spacing:.04em;}
/* ── table ── */
.table-header{display:flex;align-items:center;justify-content:space-between;
    margin-bottom:10px;flex-wrap:wrap;gap:8px;}
.row-count{font-family:'Space Mono',monospace;font-size:11px;
    color:var(--faint);letter-spacing:.08em;}
.row-count b{color:var(--primary);font-weight:700;}
.table-wrapper{
    border:1px solid var(--border2);border-radius:6px;
    max-height:68vh;overflow:auto;
}
.table-wrapper::-webkit-scrollbar{width:5px;height:5px;}
.table-wrapper::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
.h2h-table{width:100%;border-collapse:collapse;font-size:12px;}
.h2h-table th{background:var(--th-bg);color:var(--th-text);
    padding:10px;text-align:left;font-weight:500;
    font-family:'Space Mono',monospace;font-size:10px;
    letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;}
.h2h-table thead tr:first-child th{
    position:sticky;top:0;z-index:22;background:var(--th-bg);
}
.h2h-table td{padding:8px 10px;border-bottom:1px solid var(--border2);
    vertical-align:middle;color:var(--ink);}
.h2h-table tr:hover td{background:var(--row-hover);}
.h2h-table tr:nth-child(even) td{background:var(--row-even);}
.h2h-table tr:nth-child(even):hover td{background:var(--row-hover);}
.result-badge{display:inline-flex;align-items:center;justify-content:center;
    width:22px;height:22px;border-radius:4px;
    font-family:'Space Mono',monospace;font-size:11px;font-weight:700;}
.badge-w{background:var(--win-bg,rgba(42,122,74,.08));color:var(--win,#2a7a4a);border:0.5px solid var(--win-rim,rgba(42,122,74,.20));}
.badge-l{background:var(--lose-bg,rgba(192,72,48,.08));color:var(--lose,#c04830);border:0.5px solid var(--lose-rim,rgba(192,72,48,.20));}
.tour-tag{font-size:10px;padding:1px 7px;border-radius:3px;
    background:var(--surface2);color:var(--muted);
    border:0.5px solid var(--border);font-family:'Space Mono',monospace;}
.day-pill{font-family:'Space Mono',monospace;font-size:10px;
    color:var(--faint);background:var(--surface2);
    padding:1px 6px;border-radius:3px;border:0.5px solid var(--border2);}
/* ── column filter dropdowns ── */
.filter-row{background:var(--filter-bg) !important;}
.filter-row th{padding:3px 4px;background:var(--filter-bg) !important;
    cursor:default;border-bottom:1px solid var(--border);
    position:sticky;top:34px;z-index:21;}
.filter-dropdown{position:relative;width:100%;}
.filter-trigger{width:100%;padding:3px 5px;border:1px solid var(--border);
    border-radius:3px;background:var(--drop-bg);color:var(--muted);font-size:10px;
    cursor:pointer;display:flex;justify-content:space-between;align-items:center;
    font-family:'Space Mono',monospace;letter-spacing:.04em;transition:border-color .15s;}
.filter-trigger:hover{border-color:var(--primary);color:var(--ink2);}
.dropdown-content{display:none;position:fixed;background:var(--drop-bg);
    min-width:140px;max-height:240px;overflow-y:auto;
    border:1px solid var(--border);border-radius:4px;
    box-shadow:0 8px 24px rgba(26,26,26,.12);z-index:9999;}
body.dark .dropdown-content{box-shadow:0 8px 24px rgba(0,0,0,.4);}
.dropdown-content.show{display:block;}
.option-item{padding:6px 10px;cursor:pointer;display:flex;align-items:center;
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
/* ── empty state ── */
.empty-state{padding:60px 0;text-align:center;}
.empty-icon{font-size:36px;margin-bottom:14px;opacity:.25;}
.empty-title{font-family:'Noto Serif SC',serif;font-size:16px;color:var(--muted);margin-bottom:8px;}
.empty-desc{font-size:12px;color:var(--faint);line-height:1.7;max-width:320px;margin:0 auto;}
/* ── h2h badge ── */
.ttag-h2h{background:rgba(42,122,74,.08);color:#1a6a3a;border:1px solid rgba(42,122,74,.2);}
body.dark .ttag-h2h{background:rgba(74,170,106,.12);color:#6ada90;border-color:rgba(74,170,106,.25);}
@media(max-width:640px){
    .score-num{font-size:28px;}
    .stat-strip{grid-template-columns:repeat(2,1fr);}
    .stat-cell:nth-child(2){border-right:none;}
    .stat-cell:nth-child(3){border-top:1px solid var(--border);}
}

/* ── tab bar ── */
.mode-tabs{display:flex;gap:6px;margin-bottom:20px;border-bottom:1px solid var(--border2);}
.mode-tab{background:none;border:none;cursor:pointer;padding:10px 4px 12px;
    font-size:13px;color:var(--muted);font-family:'Noto Sans SC',sans-serif;
    position:relative;transition:color .2s;}
.mode-tab + .mode-tab{margin-left:14px;}
.mode-tab:hover{color:var(--ink)}
.mode-tab.active{color:var(--primary-dark);font-weight:600;}
body.dark .mode-tab.active{color:var(--primary);}
.mode-tab.active::after{content:'';position:absolute;left:0;right:0;bottom:-1px;
    height:2px;background:var(--primary);border-radius:2px 2px 0 0;}
.tab-panel{display:none;}
.tab-panel.active{display:block;}

/* ── summary: user picker ── */
.summary-picker{background:var(--surface);border:1px solid var(--border);
    border-radius:10px;padding:18px 20px;margin-bottom:20px;}
.summary-picker .sel-label{margin-bottom:6px;}
.summary-picker-cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;}
.summary-picker-col{min-width:0;}
@media(max-width:600px){
    .summary-picker-cols{grid-template-columns:1fr;}
}

/* ── summary: profile header bar ── */
.sumr-card{border:1px solid var(--border);border-radius:10px;overflow:hidden;
    margin-bottom:18px;}
.sumr-headbar{display:grid;grid-template-columns:1fr auto;}
.sumr-head-name{background:var(--th-bg);color:#fff;padding:14px 20px;
    font-family:'Noto Serif SC',serif;font-size:16px;font-weight:600;
    display:flex;align-items:center;gap:12px;}
.sumr-avatar{width:32px;height:32px;border-radius:50%;flex-shrink:0;
    background:var(--primary);color:#fff;display:flex;align-items:center;
    justify-content:center;font-family:'Space Mono',monospace;font-size:13px;
    font-weight:700;}
.sumr-head-scope{background:var(--primary);color:#fff;padding:14px 20px;
    font-size:12px;display:flex;align-items:center;justify-content:flex-end;
    letter-spacing:.02em;white-space:nowrap;}
body.dark .sumr-head-name{background:var(--th-bg);}
body.dark .sumr-head-scope{background:var(--primary-dark);}

/* ── summary: stat row w/ donut ── */
.sumr-statrow{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
    padding:26px 20px;background:var(--surface);gap:12px;}
.sumr-stat{text-align:center;}
.sumr-stat-num{font-family:'Space Mono',monospace;font-size:40px;font-weight:700;
    color:var(--ink);line-height:1;}
.sumr-stat-num.win{color:#2a7a4a;}
.sumr-stat-num.lose{color:var(--primary);}
.sumr-stat-lbl{margin-top:8px;font-size:13px;color:var(--muted);}
.sumr-stat-lbl b{font-weight:700;}
.sumr-stat-lbl.win b{color:#2a7a4a;}
.sumr-stat-lbl.lose b{color:var(--primary);}
.sumr-donut-wrap{display:flex;align-items:center;justify-content:center;}

/* ── summary: opponent record list ── */
.sumr-oppo-list{border-top:1px solid var(--border2);}
.sumr-oppo-row{display:flex;align-items:stretch;border-bottom:1px solid var(--border2);}
.sumr-oppo-row:last-child{border-bottom:none;}
.sumr-oppo-row:nth-child(even){background:var(--row-even);}
.sumr-oppo-score{flex:0 0 64px;display:flex;align-items:center;justify-content:center;
    font-family:'Space Mono',monospace;font-size:13px;font-weight:700;color:var(--primary-dark);
    background:var(--primary-dim);border-right:1px solid var(--border2);}
body.dark .sumr-oppo-score{color:var(--primary);}
.sumr-oppo-players{flex:1;display:flex;flex-wrap:wrap;gap:6px 22px;align-items:center;
    padding:11px 16px;}
.sumr-oppo-player{font-size:13px;color:var(--ink2);}
.sumr-empty{padding:40px 0;text-align:center;color:var(--faint);font-size:13px;
    font-family:'Space Mono',monospace;letter-spacing:.06em;}

@media(max-width:640px){
    .sumr-headbar{grid-template-columns:1fr;}
    .sumr-head-scope{justify-content:flex-start;}
    .sumr-statrow{grid-template-columns:1fr;gap:18px;}
    .sumr-donut-wrap{order:-1;}
}"""

_JS_H2H = """\
(function(){
const RECORDS = __RECORDS_JSON__;
const USERS   = __USERS_JSON__;
const PLAYERS = __PLAYERS_JSON__;
const SEASONS = __SEASONS_JSON__;

let selU = new Set(), selP = new Set(), selS = new Set();
let tagsExpanded = false;

function optLabel(u){
    return u.rank != null ? u.username+' ('+u.rank+')' : u.username+' (-)';
}

function buildList(listId, items, type){
    var el = document.getElementById(listId);
    el.innerHTML = '';
    if(!items.length){ el.innerHTML='<div class="opt-empty">无结果</div>'; return; }
    var saDiv = document.createElement('div');
    saDiv.className = 'opt-item opt-select-all';
    saDiv.style.borderBottom = '2px solid var(--border)';
    var saCb = document.createElement('input');
    saCb.type = 'checkbox';
    var saLbl = document.createElement('span');
    saLbl.className = 'opt-name'; saLbl.textContent = '全选'; saLbl.style.fontWeight = '600';
    saDiv.appendChild(saCb); saDiv.appendChild(saLbl);
    saDiv.addEventListener('click', function(e){ if(e.target !== saCb) saCb.click(); });
    el.appendChild(saDiv);
    items.forEach(function(item){
        var key   = type==='user' ? item.username : String(item);
        var label = type==='user' ? optLabel(item) : String(item);
        var sel   = type==='user' ? selU.has(key) : type==='player' ? selP.has(key) : selS.has(key);
        var div = document.createElement('div');
        div.className = 'opt-item'+(sel?' checked':'');
        var cb = document.createElement('input');
        cb.type='checkbox'; cb.checked=sel;
        cb.addEventListener('change',function(e){ toggle(key,type,e.target.checked); });
        var nameSpan = document.createElement('span');
        nameSpan.className='opt-name'; nameSpan.title=label; nameSpan.textContent=label;
        div.appendChild(cb); div.appendChild(nameSpan);
        div.addEventListener('click',function(e){ if(e.target!==cb) cb.click(); });
        el.appendChild(div);
    });
    var allCbs = Array.from(el.querySelectorAll('.opt-item:not(.opt-select-all) input'));
    saCb.checked = allCbs.length > 0 && allCbs.every(function(c){ return c.checked; });
    saCb.addEventListener('change', function(){
        var checked = saCb.checked;
        var src = type==='user' ? USERS : type==='player' ? PLAYERS : SEASONS;
        src.forEach(function(item){
            var key = type==='user' ? item.username : String(item);
            var label = type==='user' ? optLabel(item) : String(item);
            var q = type==='user' ? document.getElementById('uSearch').value
                  : type==='player' ? document.getElementById('pSearch').value
                  : document.getElementById('sSearch').value;
            if(label.toLowerCase().indexOf(q.toLowerCase()) !== -1){
                if(checked){
                    if(type==='user') selU.add(key);
                    else if(type==='player') selP.add(key);
                    else selS.add(key);
                } else {
                    if(type==='user') selU.delete(key);
                    else if(type==='player') selP.delete(key);
                    else selS.delete(key);
                }
            }
        });
        filterList('uList',  document.getElementById('uSearch').value, 'user');
        filterList('pList',  document.getElementById('pSearch').value, 'player');
        filterList('sList',  document.getElementById('sSearch').value, 'season');
        renderTags(); updateRunBtn();
    });
}

function filterList(listId, q, type){
    var src = type==='user' ? USERS : type==='player' ? PLAYERS : SEASONS;
    buildList(listId, src.filter(function(item){
        var label = type==='user' ? optLabel(item) : String(item);
        return label.toLowerCase().indexOf(q.toLowerCase()) !== -1;
    }), type);
}

function toggle(key, type, checked){
    if(type==='user')        { checked ? selU.add(key) : selU.delete(key); }
    else if(type==='player') { checked ? selP.add(key) : selP.delete(key); }
    else                     { checked ? selS.add(key) : selS.delete(key); }
    filterList('uList',  document.getElementById('uSearch').value, 'user');
    filterList('pList',  document.getElementById('pSearch').value, 'player');
    filterList('sList',  document.getElementById('sSearch').value, 'season');
    renderTags(); updateRunBtn();
}

function renderTags(){
    var el = document.getElementById('selTags');
    el.innerHTML = '';
    var box = document.createElement('div');
    box.className = 'sel-summary';
    var hasAny = (selU.size>0 || selP.size>0 || selS.size>0);
    if(!hasAny){
        var none = document.createElement('span');
        none.className = 'row-count';
        none.textContent = '未选择筛选条件';
        box.appendChild(none);
        tagsExpanded = false;
    } else {
        if(selU.size>0) box.appendChild(makeSummaryPill('用户', selU, ''));
        if(selP.size>0) box.appendChild(makeSummaryPill('球员', selP, 'player'));
        if(selS.size>0) box.appendChild(makeSummaryPill('赛季', selS, 'season'));
        var tg = document.createElement('button');
        tg.type = 'button';
        tg.className = 'sel-summary-toggle';
        tg.textContent = tagsExpanded ? '收起' : '展开';
        tg.addEventListener('click', function(){
            tagsExpanded = !tagsExpanded;
            renderTags();
        });
        box.appendChild(tg);
    }
    el.appendChild(box);

    if(hasAny && tagsExpanded){
        var expanded = document.createElement('div');
        expanded.className = 'sel-expanded';
        selU.forEach(function(u){ expanded.appendChild(makeTag(u,'user','')); });
        selP.forEach(function(p){ expanded.appendChild(makeTag(p,'player',' sel-tag-player')); });
        selS.forEach(function(s){ expanded.appendChild(makeTag(s,'season',' sel-tag-season')); });
        el.appendChild(expanded);
    }
}

function makeSummaryPill(label, setObj, extraClass){
    var arr = Array.from(setObj);
    var pill = document.createElement('span');
    pill.className = 'sel-summary-pill' + (extraClass ? (' ' + extraClass) : '');
    pill.innerHTML = label + ' <b>' + arr.length + '</b>';
    var preview = arr.slice(0, 8).join('、');
    if(arr.length > 8) preview += '…';
    pill.title = preview || ('已选择 ' + arr.length + ' 项');
    return pill;
}

function makeTag(key, type, extraClass){
    var tag = document.createElement('span');
    tag.className = 'sel-tag'+extraClass;
    var rm = document.createElement('button');
    rm.className='sel-tag-rm'; rm.textContent='\\u00d7';
    rm.addEventListener('click',function(){ toggle(key,type,false); });
    tag.appendChild(document.createTextNode(key+' '));
    tag.appendChild(rm);
    return tag;
}

function updateRunBtn(){
    document.getElementById('runBtn').disabled = (selU.size===0 || selP.size===0);
}

window.clearAll = function(){
    selU.clear(); selP.clear(); selS.clear();
    tagsExpanded = false;
    ['uSearch','pSearch','sSearch'].forEach(function(id){ document.getElementById(id).value=''; });
    buildList('uList',USERS,'user');
    buildList('pList',PLAYERS,'player');
    buildList('sList',SEASONS,'season');
    renderTags(); updateRunBtn();
    document.getElementById('results').style.display    = 'none';
    document.getElementById('emptyState').style.display = '';
};

var _colDropdowns = [];

function _makeColDropdown(colIdx, vals){
    var wrap = document.createElement('div');
    wrap.className = 'filter-dropdown';
    var trigger = document.createElement('div');
    trigger.className = 'filter-trigger';
    trigger.innerHTML = '<span>\\u5168\\u90e8</span><span style="font-size:10px">\\u25bc</span>';
    var dropdown = document.createElement('div');
    dropdown.className = 'dropdown-content';
    _colDropdowns.push(dropdown);
    var searchEl = document.createElement('input');
    searchEl.type='text'; searchEl.className='dropdown-search'; searchEl.placeholder='\\u641c\\u7d22...';
    dropdown.appendChild(searchEl);
    var saItem = document.createElement('div');
    saItem.className='option-item'; saItem.dataset.selectAll='1';
    saItem.style.borderBottom='2px solid var(--border)';
    var saCb = document.createElement('input');
    saCb.type='checkbox'; saCb.checked=true;
    var saLbl = document.createElement('span');
    saLbl.textContent='\\u5168\\u9009'; saLbl.style.fontWeight='600';
    saItem.appendChild(saCb); saItem.appendChild(saLbl);
    dropdown.appendChild(saItem);
    vals.forEach(function(val){
        var item = document.createElement('div');
        item.className='option-item';
        var cb = document.createElement('input');
        cb.type='checkbox'; cb.value=val; cb.checked=true;
        var lbl = document.createElement('span');
        lbl.textContent = val;
        item.appendChild(cb); item.appendChild(lbl);
        dropdown.appendChild(item);
    });
    function getVisibleCbs(){
        return Array.from(dropdown.querySelectorAll('.option-item:not([data-select-all])'))
            .filter(function(i){ return i.style.display!=='none'; })
            .map(function(i){ return i.querySelector('input'); });
    }
    searchEl.addEventListener('input',function(){
        var q = searchEl.value.toLowerCase();
        dropdown.querySelectorAll('.option-item:not([data-select-all])').forEach(function(it){
            it.style.display = it.querySelector('span').textContent.toLowerCase().includes(q)?'':'none';
        });
        var vis = getVisibleCbs();
        saCb.checked = vis.length>0 && vis.every(function(cb){ return cb.checked; });
    });
    saCb.addEventListener('change',function(){
        getVisibleCbs().forEach(function(cb){ cb.checked=saCb.checked; });
        applyColFilters();
    });
    dropdown.addEventListener('change',function(e){
        if(!e.target.closest('[data-select-all]')){
            var vis = getVisibleCbs();
            saCb.checked = vis.length>0 && vis.every(function(cb){ return cb.checked; });
        }
        var allCbs = Array.from(dropdown.querySelectorAll('.option-item:not([data-select-all]) input'));
        var sel = allCbs.filter(function(cb){ return cb.checked; });
        var trigSpan = trigger.querySelector('span:first-child');
        if(sel.length===0) trigSpan.textContent='\\u5df2\\u53d6\\u6d88';
        else if(sel.length===allCbs.length) trigSpan.textContent='\\u5168\\u90e8';
        else trigSpan.textContent='\\u5df2\\u9009 '+sel.length+' \\u9879';
        applyColFilters();
    });
    dropdown.addEventListener('click',function(e){ e.stopPropagation(); });
    trigger.addEventListener('click',function(e){
        e.stopPropagation();
        _colDropdowns.forEach(function(d){ if(d!==dropdown) d.classList.remove('show'); });
        var isOpen = dropdown.classList.contains('show');
        dropdown.classList.toggle('show');
        if(!isOpen){
            var rect = trigger.getBoundingClientRect();
            var spaceBelow = window.innerHeight-rect.bottom;
            var dropH = Math.min(250, dropdown.scrollHeight);
            dropdown.style.width  = rect.width+'px';
            dropdown.style.left   = rect.left+'px';
            dropdown.style.top    = (spaceBelow>=dropH||spaceBelow>=120 ? rect.bottom : rect.top-dropH)+'px';
        }
    });
    wrap.appendChild(trigger);
    document.body.appendChild(dropdown);
    return wrap;
}

var COL_KEYS = ['u','p','t','d','s','r'];

function rebuildFilters(){
    _colDropdowns.forEach(function(d){ if(d.parentNode) d.parentNode.removeChild(d); });
    _colDropdowns = [];
    var table = document.querySelector('.h2h-table');
    if(!table) return;
    var thead = table.querySelector('thead');
    var tbody = document.getElementById('recBody');
    var rows  = Array.from(tbody.querySelectorAll('tr[data-u]'));
    var old = thead.querySelector('.filter-row');
    if(old) thead.removeChild(old);
    var valSets = COL_KEYS.map(function(){ return new Set(); });
    rows.forEach(function(row){
        COL_KEYS.forEach(function(key,i){
            var v = row.getAttribute('data-'+key);
            if(v!=null) valSets[i].add(v);
        });
    });
    var filterRow = document.createElement('tr');
    filterRow.className = 'filter-row';
    COL_KEYS.forEach(function(key, i){
        var sorted = Array.from(valSets[i]).sort(function(a,b){
            var nA=parseFloat(a), nB=parseFloat(b);
            if(!isNaN(nA)&&!isNaN(nB)) return nA-nB;
            return a.localeCompare(b,'zh');
        });
        var th = document.createElement('th');
        th.appendChild(_makeColDropdown(i, sorted));
        filterRow.appendChild(th);
    });
    thead.appendChild(filterRow);
    var wrapper = document.querySelector('.table-wrapper');
    if(wrapper){
        wrapper.addEventListener('scroll',function(){
            _colDropdowns.forEach(function(d){ d.classList.remove('show'); });
        });
    }
}

function applyColFilters(){
    var tbody = document.getElementById('recBody');
    var rows  = Array.from(tbody.querySelectorAll('tr[data-u]'));
    var visible = 0;
    var selectedPerCol = _colDropdowns.map(function(dropdown){
        return Array.from(dropdown.querySelectorAll('.option-item:not([data-select-all]) input:checked'))
            .map(function(cb){ return cb.value; });
    });
    rows.forEach(function(row){
        var show = COL_KEYS.every(function(key,i){
            var sel = selectedPerCol[i];
            if(!sel || sel.length===0) return true;
            return sel.includes(row.getAttribute('data-'+key));
        });
        row.style.display = show?'':'none';
        if(show) visible++;
    });
    document.getElementById('visCount').textContent = fmtInt(visible);
}

document.addEventListener('click',function(){
    _colDropdowns.forEach(function(d){ d.classList.remove('show'); });
});

window.runQuery = function(){
    var recs = RECORDS.filter(function(r){
        var uOk = selU.size===0 || selU.has(r.u);
        var pOk = selP.size===0 || selP.has(r.p);
        var sOk = selS.size===0 || selS.has(String(r.s));
        return uOk && pOk && sOk;
    });
    var W = recs.filter(function(r){ return r.r===1; }).length;
    var L = recs.filter(function(r){ return r.r===0; }).length;
    var nSeasons = new Set(recs.map(function(r){ return r.s; })).size;
    var nTours   = new Set(recs.map(function(r){ return r.t; })).size;
    document.getElementById('scoreW').textContent = fmtInt(W);
    document.getElementById('scoreL').textContent = fmtInt(L);
    var uArr=[...selU], pArr=[...selP];
    document.getElementById('scoreUsers').textContent   = uArr.slice(0,2).join('\\u3001')+(uArr.length>2?'\\u2026':'');
    document.getElementById('scorePlayers').textContent = pArr.slice(0,2).join('\\u3001')+(pArr.length>2?'\\u2026':'');
    document.getElementById('statTotal').textContent    = fmtInt(recs.length);
    document.getElementById('statWR').textContent       = recs.length?(W/recs.length*100).toFixed(1)+'%':'\\u2014';
    document.getElementById('statSeasons').textContent  = fmtInt(nSeasons);
    document.getElementById('statTours').textContent    = fmtInt(nTours);
    document.getElementById('visCount').textContent     = fmtInt(recs.length);
    var tbody = document.getElementById('recBody');
    if(recs.length===0){
        tbody.innerHTML='<tr><td colspan="6" style="text-align:center;padding:32px;'
            +'color:var(--faint);font-family:\\'Space Mono\\',monospace;font-size:11px;">'
            +'\\u6682\\u65e0\\u7b26\\u5408\\u6761\\u4ef6\\u7684\\u8bb0\\u5f55</td></tr>';
    } else {
        tbody.innerHTML = recs.map(function(r){
            var badge = r.r===1
                ? '<span class="result-badge badge-w">W</span>'
                : '<span class="result-badge badge-l">L</span>';
            var rVal = r.r===1?'W':r.r===0?'L':'?';
            return '<tr data-u="'+escAttr(r.u)+'" data-p="'+escAttr(r.p)
                +'" data-t="'+escAttr(r.t)+'" data-d="'+r.d
                +'" data-s="'+r.s+'" data-r="'+rVal+'">'
                +'<td style="color:var(--ink2)">'+escHtml(r.u)+'</td>'
                +'<td style="font-weight:500">'+escHtml(r.p)+'</td>'
                +'<td><span class="tour-tag">'+escHtml(r.t)+'</span></td>'
                +'<td><span class="day-pill">Day '+r.d+'</span></td>'
                +'<td style="font-family:\\'Space Mono\\',monospace;font-size:11px;color:var(--faint)">'+r.s+'</td>'
                +'<td>'+badge+'</td>'
                +'</tr>';
        }).join('');
    }
    rebuildFilters();
    document.getElementById('results').style.display    = '';
    document.getElementById('emptyState').style.display = 'none';
};

function escHtml(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtInt(n){
    return Number(n || 0).toLocaleString('en-US');
}
function escAttr(s){ return escHtml(s); }

document.getElementById('uSearch').addEventListener('input',function(){ filterList('uList',this.value,'user'); });
document.getElementById('pSearch').addEventListener('input',function(){ filterList('pList',this.value,'player'); });
document.getElementById('sSearch').addEventListener('input',function(){ filterList('sList',this.value,'season'); });

buildList('uList',USERS,'user');
buildList('pList',PLAYERS,'player');
buildList('sList',SEASONS,'season');
updateRunBtn();

/* ── mode tabs ── */
window.switchMode = function(mode){
    var isQuery = (mode === 'query');
    document.getElementById('tabBtnQuery').classList.toggle('active', isQuery);
    document.getElementById('tabBtnSummary').classList.toggle('active', !isQuery);
    document.getElementById('tabQuery').classList.toggle('active', isQuery);
    document.getElementById('tabSummary').classList.toggle('active', !isQuery);
};

/* ── summary tab: single-user picker ── */
var sumSelectedUser = null;

function buildSumUserList(items){
    var el = document.getElementById('sumUList');
    el.innerHTML = '';
    if(!items.length){ el.innerHTML = '<div class="opt-empty">无结果</div>'; return; }
    items.forEach(function(item){
        var label = optLabel(item);
        var div = document.createElement('div');
        div.className = 'opt-item' + (sumSelectedUser === item.username ? ' checked' : '');
        var cb = document.createElement('input');
        cb.type = 'radio'; cb.name = 'sumUserRadio';
        cb.checked = (sumSelectedUser === item.username);
        cb.addEventListener('change', function(){
            sumSelectedUser = item.username;
            document.getElementById('sumUSearch').value = item.username;
            filterSumUserList('');
            renderUserSummary(sumSelectedUser);
        });
        var nameSpan = document.createElement('span');
        nameSpan.className = 'opt-name'; nameSpan.title = label; nameSpan.textContent = label;
        div.appendChild(cb); div.appendChild(nameSpan);
        div.addEventListener('click', function(e){ if(e.target !== cb) cb.click(); });
        el.appendChild(div);
    });
}

function filterSumUserList(q){
    buildSumUserList(USERS.filter(function(item){
        return optLabel(item).toLowerCase().indexOf(q.toLowerCase()) !== -1;
    }));
}

document.getElementById('sumUSearch').addEventListener('input', function(){
    filterSumUserList(this.value);
});

/* ── summary tab: donut chart ── */
function sumrDonutSvg(winPct){
    var r = 46, c = 2 * Math.PI * r;
    var winLen = c * (winPct / 100);
    return '<svg width="128" height="128" viewBox="0 0 128 128">'
        + '<circle cx="64" cy="64" r="' + r + '" fill="none" stroke="var(--primary)" stroke-width="16"/>'
        + '<circle cx="64" cy="64" r="' + r + '" fill="none" stroke="var(--th-bg)" stroke-width="16" '
        + 'stroke-dasharray="' + winLen.toFixed(1) + ' ' + c.toFixed(1) + '" '
        + 'transform="rotate(-90 64 64)" stroke-linecap="butt"/>'
        + '</svg>';
}

/* ── summary tab: season filter ── */
var sumSelectedSeason = null;  /* null = all time */

function buildSumSeasonList(){
    var el = document.getElementById('sumSList');
    el.innerHTML = '';
    var allDiv = document.createElement('div');
    allDiv.className = 'opt-item' + (sumSelectedSeason === null ? ' checked' : '');
    var allCb = document.createElement('input');
    allCb.type = 'radio'; allCb.name = 'sumSeasonRadio';
    allCb.checked = (sumSelectedSeason === null);
    allCb.addEventListener('change', function(){
        sumSelectedSeason = null;
        buildSumSeasonList();
        if(sumSelectedUser) renderUserSummary(sumSelectedUser);
    });
    var allSpan = document.createElement('span');
    allSpan.className = 'opt-name'; allSpan.textContent = '全部赛季';
    allDiv.appendChild(allCb); allDiv.appendChild(allSpan);
    allDiv.addEventListener('click', function(e){ if(e.target !== allCb) allCb.click(); });
    el.appendChild(allDiv);

    SEASONS.forEach(function(s){
        var div = document.createElement('div');
        div.className = 'opt-item' + (sumSelectedSeason === s ? ' checked' : '');
        var cb = document.createElement('input');
        cb.type = 'radio'; cb.name = 'sumSeasonRadio';
        cb.checked = (sumSelectedSeason === s);
        cb.addEventListener('change', function(){
            sumSelectedSeason = s;
            buildSumSeasonList();
            if(sumSelectedUser) renderUserSummary(sumSelectedUser);
        });
        var span = document.createElement('span');
        span.className = 'opt-name'; span.textContent = String(s);
        div.appendChild(cb); div.appendChild(span);
        div.addEventListener('click', function(e){ if(e.target !== cb) cb.click(); });
        el.appendChild(div);
    });
}

/* ── summary tab: main render ── */
function renderUserSummary(username){
    var container = document.getElementById('sumResults');
    var empty = document.getElementById('sumEmptyState');
    var recs = RECORDS.filter(function(r){ return r.u === username; });
    if(sumSelectedSeason !== null){
        recs = recs.filter(function(r){ return r.s === sumSelectedSeason; });
    }

    if(recs.length === 0){
        container.innerHTML = '';
        empty.style.display = '';
        return;
    }
    empty.style.display = 'none';

    var wins = recs.filter(function(r){ return r.r === 1; }).length;
    var losses = recs.filter(function(r){ return r.r === 0; }).length;
    var decided = wins + losses;
    var winPct = decided ? Math.round((wins / decided) * 100) : 0;
    var losePct = decided ? (100 - winPct) : 0;

    var byPlayer = {};
    recs.forEach(function(r){
        if(r.r !== 1 && r.r !== 0) return;
        if(!byPlayer[r.p]) byPlayer[r.p] = { w: 0, l: 0 };
        if(r.r === 1) byPlayer[r.p].w++; else byPlayer[r.p].l++;
    });

    var groups = {};
    Object.keys(byPlayer).forEach(function(p){
        var rec = byPlayer[p];
        var key = rec.w + ':' + rec.l;
        if(!groups[key]) groups[key] = { w: rec.w, l: rec.l, players: [] };
        groups[key].players.push(p);
    });
    var groupArr = Object.keys(groups).map(function(k){ return groups[k]; });
    groupArr.sort(function(a, b){
        if(b.w !== a.w) return b.w - a.w;
        return a.l - b.l;
    });

    var initials = username.trim().charAt(0).toUpperCase();
    var scopeLabel = sumSelectedSeason !== null ? String(sumSelectedSeason) + ' 赛季' : '全部赛季';

    var rowsHtml = groupArr.map(function(g){
        var playersHtml = g.players.map(function(p){
            return '<span class="sumr-oppo-player">' + escHtml(p) + '</span>';
        }).join('');
        return '<div class="sumr-oppo-row">'
            + '<div class="sumr-oppo-score">' + g.w + ':' + g.l + '</div>'
            + '<div class="sumr-oppo-players">' + playersHtml + '</div>'
            + '</div>';
    }).join('');

    container.innerHTML =
        '<div class="sumr-card">'
        + '<div class="sumr-headbar">'
        +   '<div class="sumr-head-name"><span class="sumr-avatar">' + escHtml(initials) + '</span>' + escHtml(username) + '</div>'
        +   '<div class="sumr-head-scope">共 ' + fmtInt(recs.length) + ' 场比赛 · ' + escHtml(scopeLabel) + '</div>'
        + '</div>'
        + '<div class="sumr-statrow">'
        +   '<div class="sumr-stat"><div class="sumr-stat-num win">' + fmtInt(wins) + '</div>'
        +     '<div class="sumr-stat-lbl win">胜 <b>' + winPct + '%</b></div></div>'
        +   '<div class="sumr-donut-wrap">' + sumrDonutSvg(winPct) + '</div>'
        +   '<div class="sumr-stat"><div class="sumr-stat-num lose">' + fmtInt(losses) + '</div>'
        +     '<div class="sumr-stat-lbl lose">负 <b>' + losePct + '%</b></div></div>'
        + '</div>'
        + '<div class="sumr-oppo-list">' + (rowsHtml || '<div class="sumr-empty">暂无对阵记录</div>') + '</div>'
        + '</div>';
}

filterSumUserList('');
buildSumSeasonList();
})();"""

def _h2h_user_list(df: pd.DataFrame) -> list[dict]:
    has_rank = "rank" in df.columns
    if has_rank:
        sub = df[["username", "rank"]].drop_duplicates("username").copy()
        sub["rank"] = pd.to_numeric(sub["rank"], errors="coerce")
        sub = sub.sort_values(
            ["rank", "username"],
            key=lambda s: s.fillna(float("inf")) if s.name == "rank" else s,
        )
        rows = []
        for _, r in sub.iterrows():
            rank_val = None if pd.isna(r["rank"]) else int(r["rank"])
            rows.append({"username": str(r["username"]), "rank": rank_val})
    else:
        users = sorted(df["username"].dropna().unique().tolist())
        rows = [{"username": str(u), "rank": None} for u in users]
    return rows


def _h2h_player_list(df: pd.DataFrame) -> list[str]:
    return sorted(df["player"].dropna().astype(str).unique().tolist())


def _h2h_season_list(df: pd.DataFrame) -> list[int]:
    seasons = pd.to_numeric(df["season"], errors="coerce").dropna().unique()
    return sorted([int(s) for s in seasons], reverse=True)


def _h2h_records_json(df: pd.DataFrame) -> str:
    cols_needed = [
        "username",
        "player",
        "tournament",
        "day",
        "season",
        "result",
        "week_start_date",
    ]
    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")
    out = df[cols_needed].copy()
    out["week_start_date"] = out["week_start_date"].astype(str)
    out["day"] = pd.to_numeric(out["day"], errors="coerce").fillna(0).astype(int)
    out["season"] = pd.to_numeric(out["season"], errors="coerce").fillna(0).astype(int)
    out["result"] = (
        out["result"]
        .astype(str)
        .str.upper()
        .map({"W": 1, "L": 0})
        .fillna(-1)
        .astype(int)
    )
    out = out.sort_values(["week_start_date", "day"], ascending=[False, False])
    records = []
    for _, row in out.iterrows():
        records.append(
            {
                "u": str(row["username"]),
                "p": str(row["player"]),
                "t": str(row["tournament"]),
                "d": int(row["day"]),
                "s": int(row["season"]),
                "r": int(row["result"]),
                "dt": str(row["week_start_date"]),
            }
        )
    return json.dumps(records, ensure_ascii=False)


def render_h2h_page(
    df: pd.DataFrame,
    updated: str,
    tour: str = "ALL",
    eyebrow: str = "H2H · Head to Head · All Time",
    title: str = "对战记录查询",
    output_path: str | Path = "h2h.html",
) -> str:
    """
    Build and write a head-to-head lookup page.

    Parameters
    ----------
    df : pd.DataFrame
        Output of ``h2h.prepare_h2h_for_render()``, already filtered to
        the desired tour.  Required columns:
            username | player | tournament | day | season | result |
            week_start_date
        Optional column: rank (used to sort the user list).

    updated    : str    timestamp string shown in the topbar
    tour       : str    "ATP" | "WTA" | "ALL" — controls the pill badge colour
    eyebrow    : str    small-caps label above the title
    title      : str    page heading
    output_path: str | Path

    Returns
    -------
    str : generated HTML
    """
    users_json = json.dumps(_h2h_user_list(df), ensure_ascii=False)
    players_json = json.dumps(_h2h_player_list(df), ensure_ascii=False)
    seasons_json = json.dumps(_h2h_season_list(df), ensure_ascii=False)
    records_json = _h2h_records_json(df)

    tour_upper = tour.upper()
    if tour_upper == "ATP":
        ttag_html = '<span class="ttag ttag-atp">ATP</span>'
    elif tour_upper == "WTA":
        ttag_html = '<span class="ttag ttag-wta">WTA</span>'
    else:
        ttag_html = '<span class="ttag ttag-all">ALL</span>'
    ttag_html += '\n    <span class="ttag ttag-h2h">H2H</span>'

    js = (
        _JS_H2H.replace("__RECORDS_JSON__", records_json)
        .replace("__USERS_JSON__", users_json)
        .replace("__PLAYERS_JSON__", players_json)
        .replace("__SEASONS_JSON__", seasons_json)
    )

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
{_CSS_H2H}
</style>
</head>
<body>
<div class="page">

{_topbar(updated)}

<div class="page-eye">{html.escape(eyebrow)}</div>
<div class="page-title">
  {html.escape(title)}
  {ttag_html}
</div>

<div class="mode-tabs">
  <button class="mode-tab active" id="tabBtnQuery" onclick="switchMode('query')">对战查询</button>
  <button class="mode-tab" id="tabBtnSummary" onclick="switchMode('summary')">用户汇总</button>
</div>

<div id="tabQuery" class="tab-panel active">

<div class="selector-panel">
  <div class="selector-grid">
    <div class="sel-group">
      <div class="sel-label">选择用户</div>
      <div class="multisel-box">
        <input class="multisel-search" id="uSearch" placeholder="搜索用户名…">
        <div class="multisel-list" id="uList"></div>
      </div>
    </div>
    <div class="sel-group">
      <div class="sel-label">选择球员</div>
      <div class="multisel-box">
        <input class="multisel-search" id="pSearch" placeholder="搜索球员名…">
        <div class="multisel-list" id="pList"></div>
      </div>
    </div>
    <div class="sel-group">
      <div class="sel-label">选择赛季</div>
      <div class="multisel-box">
        <input class="multisel-search" id="sSearch" placeholder="搜索赛季…">
        <div class="multisel-list" id="sList"></div>
      </div>
    </div>
  </div>
  <div class="sel-footer">
    <div class="sel-tags" id="selTags"></div>
    <div class="sel-actions">
      <button class="clear-btn" onclick="clearAll()">清空</button>
      <button class="run-btn" id="runBtn" onclick="runQuery()" disabled>查询 →</button>
    </div>
  </div>
</div>

<div id="results" style="display:none;">
  <div class="section-div">
    <span class="div-label">胜负统计</span><div class="div-rule"></div>
  </div>
  <div class="scoreboard">
    <div class="score-side left">
      <div class="score-label">总胜场</div>
      <div class="score-names" id="scoreUsers"></div>
      <div class="score-num win" id="scoreW">—</div>
      <div class="score-sub">场胜利</div>
    </div>
    <div class="score-vs-col"><span class="vs-text">VS</span></div>
    <div class="score-side right">
      <div class="score-label">总败场</div>
      <div class="score-names" id="scorePlayers"></div>
      <div class="score-num lose" id="scoreL">—</div>
      <div class="score-sub">场失利</div>
    </div>
  </div>
  <div class="stat-strip">
    <div class="stat-cell">
      <div class="stat-val" id="statTotal">—</div>
      <div class="stat-lbl">总计场次</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val win" id="statWR">—</div>
      <div class="stat-lbl">胜率</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val" id="statSeasons">—</div>
      <div class="stat-lbl">涉及赛季</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val" id="statTours">—</div>
      <div class="stat-lbl">涉及赛事</div>
    </div>
  </div>
  <div class="section-div">
    <span class="div-label">详细记录</span><div class="div-rule"></div>
  </div>
  <div class="table-header">
    <div class="row-count">显示 <b id="visCount">0</b> 条记录</div>
  </div>
  <div class="table-wrapper">
    <table class="h2h-table">
      <thead>
        <tr>
          <th>用户名</th><th>球员</th><th>赛事</th>
          <th>Day</th><th>赛季</th><th>结果</th>
        </tr>
      </thead>
      <tbody id="recBody"></tbody>
    </table>
  </div>
</div>

<div id="emptyState">
  <div class="empty-state">
    <div class="empty-icon">⚔</div>
    <div class="empty-title">选择用户和球员开始查询</div>
    <div class="empty-desc">
      支持多选，点击「查询」查看完整对战记录
    </div>
  </div>
</div>

</div>

<div id="tabSummary" class="tab-panel">

<div class="summary-picker">
  <div class="summary-picker-cols">
    <div class="summary-picker-col">
      <div class="sel-label">选择用户</div>
      <div class="multisel-box">
        <input class="multisel-search" id="sumUSearch" placeholder="搜索用户名…">
        <div class="multisel-list" id="sumUList"></div>
      </div>
    </div>
    <div class="summary-picker-col">
      <div class="sel-label">选择赛季</div>
      <div class="multisel-box">
        <div class="multisel-list" id="sumSList" style="max-height:160px;"></div>
      </div>
    </div>
  </div>
</div>

<div id="sumResults"></div>

<div id="sumEmptyState">
  <div class="empty-state">
    <div class="empty-icon">🎯</div>
    <div class="empty-title">选择一位用户查看汇总战绩</div>
    <div class="empty-desc">
      展示该用户对阵每一位球员的累计胜负记录
    </div>
  </div>
</div>

</div>

</div>
<script>
{_JS_THEME}
{js}
</script>
</body>
</html>"""

    Path(output_path).write_text(html_str, encoding="utf-8")
    return html_str


"""HTML/CSS/JS fragments for combined-ranking points breakdown modal."""
from __future__ import annotations

_CSS_BREAKDOWN = """\
.filterable-table tbody tr.bd-clickable{cursor:pointer;}
.bd-modal{display:none;position:fixed;inset:0;z-index:10050;background:rgba(20,22,28,.55);
    align-items:center;justify-content:center;padding:20px;}
.bd-modal.open{display:flex;}
.bd-card{width:min(1120px,96vw);max-height:92vh;background:#fff;border-radius:12px;
    box-shadow:0 18px 50px rgba(0,0,0,.22);display:flex;flex-direction:column;overflow:hidden;
    color:#1a1a1a;}
.bd-hd{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;
    padding:16px 18px;border-bottom:1px solid #e8e8e8;background:#fff;}
.bd-title{font-family:'Noto Serif SC',serif;font-size:18px;font-weight:600;}
.bd-sub{font-size:12px;color:#6a7078;margin-top:4px;}
.bd-close{border:1px solid #ddd;background:#f7f7f7;border-radius:6px;padding:6px 10px;
    cursor:pointer;font-size:12px;}
.bd-close:hover{border-color:#bbb;}
.bd-body{padding:14px 18px 20px;overflow:auto;background:#fff;}
.bd-filters{display:flex;flex-direction:column;gap:10px;margin-bottom:14px;}
.bd-filter-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
.bd-gender-lbl,.bd-view-lbl{font-size:12px;color:#6a7078;margin-right:4px;min-width:4.5em;}
.bd-chip{font-size:12px;padding:5px 14px;border-radius:16px;border:1px solid #d8d8d8;
    background:#f5f5f5;color:#555;cursor:pointer;}
.bd-chip.active{background:#1a1a1a;color:#fff;border-color:#1a1a1a;}
.bd-view{display:none;}
.bd-view.active{display:block;}
.bd-split{display:grid;grid-template-columns:minmax(280px,1.05fr) minmax(280px,1fr);gap:14px;}
.bd-panel{border:1px solid #ececec;border-radius:10px;background:#fff;overflow:hidden;}
.bd-panel-hd{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:12px;color:#666;
    background:#fafafa;}
.bd-list{max-height:420px;overflow:auto;}
.bd-group-hd{padding:8px 12px;font-size:11px;font-weight:600;letter-spacing:.04em;
    background:#f3f3f3;color:#444;border-top:1px solid #eaeaea;position:sticky;top:0;}
.bd-group-hd.surf-hard{border-left:3px solid #2f6fed;}
.bd-group-hd.surf-clay{border-left:3px solid #c23b2a;}
.bd-group-hd.surf-grass{border-left:3px solid #2f9e44;}
.bd-row{display:grid;grid-template-columns:1.4fr .7fr .9fr 1fr;gap:8px;padding:8px 12px;
    font-size:12px;border-top:1px solid #f2f2f2;}
.bd-row:hover{background:#fafafa;}
.bd-row .pts{font-family:'Space Mono',monospace;font-weight:600;}
.bd-chart{height:420px;width:100%;}
.bd-chart.tall{height:460px;}
.bd-empty{padding:28px;text-align:center;color:#999;font-size:13px;}
@media(max-width:860px){
  .bd-split{grid-template-columns:1fr;}
  .bd-chart{height:360px;}
}
"""

_JS_BREAKDOWN = r"""
(function(){
  if (!window.__BREAKDOWN__) return;
  var CFG = window.__BREAKDOWN__;
  var cache = {atp:null, wta:null};
  var state = {uid:null, name:'', gender:'atp', view:'level', loading:false};
  var charts = {level:null, surface:null, month:null};
  var SURFACE_COLORS = {'硬地':'#2f6fed', '红土':'#c23b2a', '草地':'#2f9e44'};

  function $(id){ return document.getElementById(id); }
  function ensureCharts(){
    if (!window.echarts) return false;
    if (!charts.level) charts.level = echarts.init($('bd-chart-level'), null, {renderer:'canvas'});
    if (!charts.surface) charts.surface = echarts.init($('bd-chart-surface'), null, {renderer:'canvas'});
    if (!charts.month) charts.month = echarts.init($('bd-chart-month'), null, {renderer:'canvas'});
    return true;
  }
  function disposeCharts(){
    Object.keys(charts).forEach(function(k){
      if (charts[k]) { charts[k].dispose(); charts[k]=null; }
    });
  }
  function loadScript(src){
    return new Promise(function(resolve, reject){
      if (window.echarts) { resolve(); return; }
      var s = document.createElement('script');
      s.src = src; s.async = true;
      s.onload = function(){ resolve(); };
      s.onerror = function(){ reject(new Error('echarts load failed')); };
      document.head.appendChild(s);
    });
  }
  function globalBag(tour){
    if (tour==='atp') return CFG.atpGlobal || '__BD_LIVE_ATP';
    return CFG.wtaGlobal || '__BD_LIVE_WTA';
  }
  function loadScriptOnce(src){
    return new Promise(function(resolve, reject){
      var existed = document.querySelector('script[data-bd-src="'+src+'"]');
      if (existed){
        if (existed.getAttribute('data-bd-ready')==='1') resolve();
        else existed.addEventListener('load', function(){ resolve(); });
        return;
      }
      var s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.setAttribute('data-bd-src', src);
      s.onload = function(){ s.setAttribute('data-bd-ready','1'); resolve(); };
      s.onerror = function(){ reject(new Error('脚本加载失败: '+src)); };
      document.head.appendChild(s);
    });
  }
  function fetchTour(tour){
    if (cache[tour]) return Promise.resolve(cache[tour]);
    var gname = globalBag(tour);
    if (window[gname]) {
      cache[tour] = window[gname] || {};
      return Promise.resolve(cache[tour]);
    }
    var jsUrl = (tour==='atp' ? CFG.atpUrl : CFG.wtaUrl).replace(/\.json$/i, '.js');
    return loadScriptOnce(jsUrl).then(function(){
      if (!window[gname]) throw new Error('数据未就绪');
      cache[tour] = window[gname] || {};
      return cache[tour];
    });
  }
  function userPayload(){
    var bag = cache[state.gender] || {};
    return bag[state.uid] || null;
  }
  function levelOrder(payload){
    return (payload && payload.levels) || (state.gender==='wta'
      ? ['大满贯','W1000','W500','W250']
      : ['大满贯','M1000','M500','M250']);
  }
  function surfaceOrder(payload){
    return (payload && payload.surfaces) || ['硬地','红土','草地'];
  }
  function totalOf(payload){
    if (!payload) return 0;
    var sum = 0;
    (payload.events||[]).forEach(function(e){ if ((e.points||0)>0) sum += e.points; });
    return sum || payload.total || 0;
  }
  function esc(s){
    return String(s).replace(/[&<>"']/g, function(c){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]);
    });
  }
  function renderGroupedList(listId, payload, groupKey, order){
    var box = $(listId);
    if (!payload || !(payload.events||[]).length){
      box.innerHTML = '<div class="bd-empty">暂无赛事积分明细</div>';
      return;
    }
    var groups = {};
    order.forEach(function(g){ groups[g]=[]; });
    payload.events.forEach(function(e){
      if ((e.points||0)<=0) return;
      var g = e[groupKey] || order[order.length-1];
      if (!groups[g]) groups[g]=[];
      groups[g].push(e);
    });
    var html = '';
    order.forEach(function(g){
      var rows = groups[g] || [];
      if (!rows.length) return;
      var surfCls = g==='硬地'?' surf-hard':(g==='红土'?' surf-clay':(g==='草地'?' surf-grass':''));
      html += '<div class="bd-group-hd'+surfCls+'">'+esc(g)+'</div>';
      rows.forEach(function(e){
        html += '<div class="bd-row">'
          + '<div>'+esc(e.name||'')+'</div>'
          + '<div class="pts">'+(e.points||0)+'</div>'
          + '<div>'+esc(e.round||'—')+'</div>'
          + '<div>'+esc(e.expires_month || (e.expires ? String(e.expires).slice(0,7).replace('-','.') : '') || '—')+'</div>'
          + '</div>';
      });
    });
    box.innerHTML = html || '<div class="bd-empty">暂无赛事</div>';
  }
  function renderCategoryDonut(chartKey, elId, payload, groupKey, order, titleTip){
    if (!ensureCharts()) return;
    var totals = {};
    order.forEach(function(g){ totals[g]=0; });
    (payload.events||[]).forEach(function(e){
      var p = e.points||0;
      if (p<=0) return;
      var g = e[groupKey] || order[order.length-1];
      totals[g] = (totals[g]||0) + p;
    });
    var total = totalOf(payload);
    var data = order.filter(function(g){ return (totals[g]||0)>0; }).map(function(g){
      var item = {name:g, value:totals[g]};
      if (groupKey==='surface' && SURFACE_COLORS[g]) {
        item.itemStyle = {color: SURFACE_COLORS[g]};
      }
      return item;
    });
    if (!charts[chartKey]) charts[chartKey] = echarts.init($(elId), null, {renderer:'canvas'});
    charts[chartKey].setOption({
      backgroundColor:'#fff',
      tooltip:{trigger:'item', formatter:function(p){
        var pct = total? ((p.value/total)*100).toFixed(1):'0';
        return (titleTip? (titleTip+' · ') : '')+p.name+'<br/>积分：'+p.value+'（'+pct+'%）';
      }},
      series:[{
        type:'pie', radius:['48%','72%'],
        itemStyle:{borderColor:'#fff', borderWidth:3},
        label:{formatter:function(p){
          var pct = total? ((p.value/total)*100).toFixed(1):'0';
          return p.name+'\n'+p.value+' · '+pct+'%';
        }},
        data:data,
        emphasis:{itemStyle:{shadowBlur:12, shadowColor:'rgba(0,0,0,.18)'}}
      }],
      graphic:[{
        type:'group', left:'center', top:'center',
        children:[
          {type:'text', style:{text:'总分', fill:'#888', fontSize:12, textAlign:'center'}, top:-14},
          {type:'text', style:{text:String(total), fill:'#111', fontSize:22, fontWeight:600, textAlign:'center', fontFamily:'Space Mono, monospace'}, top:6}
        ]
      }]
    }, true);
  }
  function renderMonthBars(payload){
    if (!ensureCharts()) return;
    var byMonth = {};
    (payload.events||[]).forEach(function(e){
      if ((e.points||0)<=0) return;
      var m = e.expires_month || '';
      if (!m && e.expires) m = String(e.expires).slice(0,7).replace('-','.');
      if (!m) m = '未知';
      if (!byMonth[m]) byMonth[m] = {points:0, events:[]};
      byMonth[m].events.push(e);
      byMonth[m].points += e.points;
    });
    // Latest expiry first in data → ECharts category axis draws index 0 at BOTTOM.
    var months = Object.keys(byMonth).sort().reverse();
    var values = months.map(function(m){ return byMonth[m].points; });
    charts.month.setOption({
      backgroundColor:'#fff',
      tooltip:{trigger:'axis', axisPointer:{type:'shadow'}, formatter:function(params){
        var p = params[0];
        var m = p.name;
        var g = byMonth[m];
        var lines = [(m+' · 合计 '+((g&&g.points)||0))];
        (g&&g.events||[]).forEach(function(e){
          lines.push((e.name||'')+'：'+(e.points||0));
        });
        return lines.join('<br/>');
      }},
      grid:{left:72, right:72, top:20, bottom:24, containLabel:false},
      xAxis:{type:'value', name:'积分', splitLine:{lineStyle:{color:'#eee'}}, axisLabel:{color:'#666'}},
      yAxis:{type:'category', data:months, axisLabel:{color:'#333'}, axisTick:{show:false}},
      series:[{
        type:'bar', data:values, barWidth:14,
        itemStyle:{borderRadius:[0,6,6,0]},
        label:{show:true, position:'right', color:'#333',
          formatter:function(p){ return p.value>0 ? p.value : ''; }}
      }],
      graphic:[]
    }, true);
    var H = $('bd-chart-month').clientHeight || 460;
    var n = months.length || 1;
    var topPad = 20, botPad = 24;
    var plotH = H - topPad - botPad;
    var children = [];
    // Index 0 is at the bottom of the plot; place detail text just under each bar.
    months.forEach(function(m, i){
      var g = byMonth[m];
      var text = (g.events||[]).map(function(e){ return (e.name||'')+' '+(e.points||0); }).join('  ·  ');
      var y = topPad + (plotH / n) * ((n - 1 - i) + 0.82);
      children.push({
        type:'text', left:78, top:y, z:10,
        style:{text:text, fill:'#8a8a8a', fontSize:10, width: Math.max(200, ($('bd-chart-month').clientWidth||600)-160), overflow:'truncate'}
      });
    });
    charts.month.setOption({graphic:children});
  }
  function applyView(){
    document.querySelectorAll('.bd-view').forEach(function(pane){
      pane.classList.toggle('active', pane.getAttribute('data-view')===state.view);
    });
    document.querySelectorAll('.bd-chip[data-view]').forEach(function(btn){
      btn.classList.toggle('active', btn.getAttribute('data-view')===state.view);
    });
  }
  function renderAll(){
    var payload = userPayload();
    var total = totalOf(payload);
    $('bd-title').textContent = (state.name || '用户') + ' · 积分构成';
    $('bd-sub').textContent = (state.gender==='atp'?'ATP 男单':'WTA 女单') + ' · 总分 ' + total;
    applyView();
    if (!payload){
      ['bd-list-level','bd-list-surface'].forEach(function(id){
        $(id).innerHTML = '<div class="bd-empty">暂无该侧积分明细</div>';
      });
      if (ensureCharts()){
        Object.keys(charts).forEach(function(k){ if (charts[k]) charts[k].clear(); });
      }
      return;
    }
    renderGroupedList('bd-list-level', payload, 'level', levelOrder(payload));
    renderGroupedList('bd-list-surface', payload, 'surface', surfaceOrder(payload));
    renderCategoryDonut('level', 'bd-chart-level', payload, 'level', levelOrder(payload), '赛事类型');
    renderCategoryDonut('surface', 'bd-chart-surface', payload, 'surface', surfaceOrder(payload), '场地类型');
    renderMonthBars(payload);
    setTimeout(function(){
      Object.keys(charts).forEach(function(k){ if (charts[k]) charts[k].resize(); });
    }, 50);
  }
  function setGender(g){
    state.gender = g;
    document.querySelectorAll('.bd-chip[data-gender]').forEach(function(btn){
      btn.classList.toggle('active', btn.getAttribute('data-gender')===g);
    });
    state.loading = true;
    fetchTour(g).then(function(){
      state.loading = false;
      renderAll();
    }).catch(function(err){
      state.loading = false;
      ['bd-list-level','bd-list-surface'].forEach(function(id){
        $(id).innerHTML = '<div class="bd-empty">加载失败：'+esc(err.message||err)+'</div>';
      });
    });
  }
  function setView(v){
    state.view = v || 'level';
    applyView();
    setTimeout(function(){
      Object.keys(charts).forEach(function(k){ if (charts[k]) charts[k].resize(); });
    }, 30);
  }
  function openModal(uid, name, prefer){
    state.uid = String(uid||'');
    state.name = name||'';
    var modal = $('bd-modal');
    if (!modal) return;
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
    $('bd-title').textContent = (state.name || '用户') + ' · 积分构成';
    $('bd-sub').textContent = '加载中…';
    ['bd-list-level','bd-list-surface'].forEach(function(id){
      $(id).innerHTML = '<div class="bd-empty">加载积分数据中…</div>';
    });
    setView(state.view || 'level');
    var first = prefer || 'atp';
    var echartsUrls = [CFG.echartsUrl, CFG.echartsCdn].filter(Boolean);
    (function loadE(i){
      if (i >= echartsUrls.length){
        $('bd-list-level').innerHTML = '<div class="bd-empty">图表库加载失败</div>';
        return;
      }
      loadScript(echartsUrls[i]).then(function(){ setGender(first); })
        .catch(function(){ loadE(i+1); });
    })(0);
  }
  function closeModal(){
    var modal = $('bd-modal');
    if (modal) modal.classList.remove('open');
    document.body.style.overflow = '';
    disposeCharts();
  }
  function eventEl(ev){
    var t = ev.target;
    if (!t) return null;
    if (t.nodeType === 3) t = t.parentElement;
    return t && t.nodeType === 1 ? t : null;
  }
  document.addEventListener('click', function(ev){
    var el = eventEl(ev);
    if (!el) return;
    if (el.closest && el.closest('.bd-card')) {
      if (el.id === 'bd-close' || (el.closest && el.closest('#bd-close'))) closeModal();
      return;
    }
    var tr = el.closest ? el.closest('table.filterable-table tbody tr[data-uid]') : null;
    if (tr){
      var uid = tr.getAttribute('data-uid');
      var table = tr.closest('table');
      var heads = Array.prototype.map.call(table.querySelectorAll('thead th'), function(th){ return th.textContent.trim(); });
      var nameIdx = heads.indexOf('用户名');
      var name = nameIdx>=0 ? (tr.children[nameIdx].textContent||'').trim() : '';
      var atpIdx = heads.indexOf('ATP总分');
      var wtaIdx = heads.indexOf('WTA总分');
      var atp = atpIdx>=0 ? parseInt((tr.children[atpIdx].textContent||'0').replace(/\D/g,''),10)||0 : 0;
      var wta = wtaIdx>=0 ? parseInt((tr.children[wtaIdx].textContent||'0').replace(/\D/g,''),10)||0 : 0;
      openModal(uid, name, (wta>atp) ? 'wta' : 'atp');
      return;
    }
    if (el.id==='bd-close' || el=== $('bd-modal') || (el.classList && el.classList.contains('bd-modal'))) closeModal();
  });
  document.addEventListener('keydown', function(ev){
    if (ev.key==='Escape') closeModal();
  });
  document.querySelectorAll('.bd-chip[data-gender]').forEach(function(btn){
    btn.addEventListener('click', function(ev){
      ev.preventDefault(); ev.stopPropagation();
      setGender(btn.getAttribute('data-gender'));
    });
  });
  document.querySelectorAll('.bd-chip[data-view]').forEach(function(btn){
    btn.addEventListener('click', function(ev){
      ev.preventDefault(); ev.stopPropagation();
      setView(btn.getAttribute('data-view'));
    });
  });
  window.addEventListener('resize', function(){
    Object.keys(charts).forEach(function(k){ if (charts[k]) charts[k].resize(); });
  });
})();
"""


def breakdown_modal_html() -> str:
    return """\
<div id="bd-modal" class="bd-modal" aria-hidden="true">
  <div class="bd-card" role="dialog" aria-modal="true">
    <div class="bd-hd">
      <div>
        <div class="bd-title" id="bd-title">积分构成</div>
        <div class="bd-sub" id="bd-sub"></div>
      </div>
      <button type="button" class="bd-close" id="bd-close">✕ 关闭</button>
    </div>
    <div class="bd-body">
      <div class="bd-filters">
        <div class="bd-filter-row">
          <span class="bd-gender-lbl">性别</span>
          <button type="button" class="bd-chip active" data-gender="atp">男 · ATP</button>
          <button type="button" class="bd-chip" data-gender="wta">女 · WTA</button>
        </div>
        <div class="bd-filter-row">
          <span class="bd-view-lbl">视图</span>
          <button type="button" class="bd-chip active" data-view="level">按赛事类型</button>
          <button type="button" class="bd-chip" data-view="surface">按场地类型</button>
          <button type="button" class="bd-chip" data-view="month">按失效时间</button>
        </div>
      </div>

      <div class="bd-view active" data-view="level">
        <div class="bd-split">
          <div class="bd-panel">
            <div class="bd-panel-hd">赛事清单（按级别）</div>
            <div class="bd-list" id="bd-list-level"></div>
          </div>
          <div class="bd-panel">
            <div class="bd-panel-hd">赛事类型聚合</div>
            <div class="bd-chart" id="bd-chart-level"></div>
          </div>
        </div>
      </div>

      <div class="bd-view" data-view="surface">
        <div class="bd-split">
          <div class="bd-panel">
            <div class="bd-panel-hd">赛事清单（按场地）</div>
            <div class="bd-list" id="bd-list-surface"></div>
          </div>
          <div class="bd-panel">
            <div class="bd-panel-hd">场地类型聚合</div>
            <div class="bd-chart" id="bd-chart-surface"></div>
          </div>
        </div>
      </div>

      <div class="bd-view" data-view="month">
        <div class="bd-panel">
          <div class="bd-panel-hd">积分失效月度分布</div>
          <div class="bd-chart tall" id="bd-chart-month"></div>
        </div>
      </div>
    </div>
  </div>
</div>
"""


def breakdown_boot_script(atp_url: str, wta_url: str) -> str:
    import json

    def _global_for(url: str) -> str:
        name = str(url).rsplit("/", 1)[-1].lower()
        return {
            "breakdown_live_atp.json": "__BD_LIVE_ATP",
            "breakdown_live_wta.json": "__BD_LIVE_WTA",
            "breakdown_race_atp.json": "__BD_RACE_ATP",
            "breakdown_race_wta.json": "__BD_RACE_WTA",
            "breakdown_live_atp.js": "__BD_LIVE_ATP",
            "breakdown_live_wta.js": "__BD_LIVE_WTA",
            "breakdown_race_atp.js": "__BD_RACE_ATP",
            "breakdown_race_wta.js": "__BD_RACE_WTA",
        }.get(name, "__BD_DATA")

    cfg = {
        "atpUrl": atp_url,
        "wtaUrl": wta_url,
        "atpGlobal": _global_for(atp_url),
        "wtaGlobal": _global_for(wta_url),
        "echartsUrl": "assets/echarts.min.js",
        "echartsCdn": "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js",
    }
    # Bare JS only — injected inside the page's single <script> block.
    return (
        f"window.__BREAKDOWN__ = {json.dumps(cfg, ensure_ascii=False)};\n"
        f"{_JS_BREAKDOWN}\n"
    )

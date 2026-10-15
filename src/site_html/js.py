"""Shared JS string blocks inlined into generated pages."""
from __future__ import annotations

_JS_THEME = """\
function toggleTheme(){
    const going=!document.body.classList.contains('dark');
    document.body.classList.toggle('dark',going);
    document.getElementById('themeBtn').textContent=going?'☀ 亮色':'🌙 暗色';
    document.querySelectorAll('.logo-light').forEach(e=>e.style.display=going?'none':'block');
    document.querySelectorAll('.logo-dark').forEach(e=>e.style.display=going?'block':'none');
    localStorage.setItem('theme',going?'dark':'light');
}
(function(){
    const dark=localStorage.getItem('theme')==='dark';
    document.body.classList.toggle('dark',dark);
    document.querySelectorAll('.logo-light').forEach(e=>e.style.display=dark?'none':'block');
    document.querySelectorAll('.logo-dark').forEach(e=>e.style.display=dark?'block':'none');
    const btn=document.getElementById('themeBtn');
    if(btn)btn.textContent=dark?'☀ 亮色':'🌙 暗色';
})();"""

# Full interactive filter+sort JS (identical logic to original pages)
_JS_TABLE = """\
document.addEventListener('DOMContentLoaded',function(){
    const table=document.querySelector('.filterable-table');
    if(!table)return;
    const thead=table.querySelector('thead');
    const tbody=table.querySelector('tbody');
    const rows=tbody.querySelectorAll('tr');
    const totalCount=rows.length;
    document.getElementById('total-count').textContent=totalCount;
    document.getElementById('visible-count').textContent=totalCount;
    const headerRow=thead.querySelector('tr');
    const headers=headerRow.querySelectorAll('th');
    const filterRow=document.createElement('tr');
    filterRow.className='filter-row';
    const allOptionContainers=[];
    const columnMeta=[]; // {type:'numeric'|'category', ...}

    // strip % , currency chars etc. before parsing
    function parseCellNumber(text){
        const cleaned=String(text).trim().replace(/[%,\\s]/g,'');
        if(cleaned===''||cleaned==='-'||cleaned.toLowerCase()==='nan')return NaN;
        const n=parseFloat(cleaned);
        return n;
    }

    headers.forEach((header,index)=>{
        let sortDirection='none';
        const thCell=document.createElement('th');

        // collect all non-empty values for this column
        const rawValues=[];
        rows.forEach(row=>{
            const cell=row.children[index];
            if(cell)rawValues.push(cell.textContent.trim());
        });
        const nonEmpty=rawValues.filter(v=>v!==''&&v.toLowerCase()!=='nan'&&v!=='-');
        const parsedNums=nonEmpty.map(parseCellNumber);
        const isNumericCol = nonEmpty.length>0 && parsedNums.every(n=>!isNaN(n));

        if(isNumericCol){
            // ── build slider filter ──────────────────────────────
            const headerText=header.textContent.trim();
            const forceInt=/天数|排名|周数|参赛|冠军数|亚军|连胜|连败|得分|积分/.test(headerText)
                && !/率/.test(headerText);
            const isIntCol=forceInt || parsedNums.every(n=>Number.isInteger(n));
            let minVal=Math.min(...parsedNums);
            let maxVal=Math.max(...parsedNums);
            if(isIntCol){ minVal=Math.floor(minVal); maxVal=Math.ceil(maxVal); }
            const step=isIntCol ? 1 : ((maxVal-minVal)>20 ? 1 : (maxVal-minVal)/100 || 1);

            columnMeta[index]={type:'numeric', min:minVal, max:maxVal,
                                curMin:minVal, curMax:maxVal, intCol:isIntCol};

            const dropdownWrapper=document.createElement('div');
            dropdownWrapper.className='filter-dropdown';
            const trigger=document.createElement('div');
            trigger.className='filter-trigger';
            trigger.innerHTML='<span>全部</span><span style="font-size:10px">▼</span>';

            const panel=document.createElement('div');
            panel.className='dropdown-content filter-slider';

            const readout=document.createElement('div');
            readout.className='filter-slider-readout';
            const inMin=document.createElement('input');
            inMin.type='number'; inMin.value=minVal; inMin.step=step;
            if(isIntCol){ inMin.step='1'; inMin.setAttribute('inputmode','numeric'); }
            const sep=document.createElement('span');
            sep.className='filter-slider-sep'; sep.textContent='~';
            const inMax=document.createElement('input');
            inMax.type='number'; inMax.value=maxVal; inMax.step=step;
            if(isIntCol){ inMax.step='1'; inMax.setAttribute('inputmode','numeric'); }
            readout.append(inMin,sep,inMax);

            const rangeWrap=document.createElement('div');
            rangeWrap.className='filter-slider-range';
            const track=document.createElement('div');
            track.className='filter-slider-track';
            const fill=document.createElement('div');
            fill.className='filter-slider-fill';
            const rMin=document.createElement('input');
            rMin.type='range'; rMin.min=minVal; rMin.max=maxVal; rMin.step=step; rMin.value=minVal;
            const rMax=document.createElement('input');
            rMax.type='range'; rMax.min=minVal; rMax.max=maxVal; rMax.step=step; rMax.value=maxVal;
            rangeWrap.append(track,fill,rMin,rMax);

            const resetBtn=document.createElement('button');
            resetBtn.type='button'; resetBtn.className='filter-slider-reset';
            resetBtn.textContent='重置范围';

            panel.append(readout,rangeWrap,resetBtn);

            function syncUI(){
                let lo=parseFloat(rMin.value), hi=parseFloat(rMax.value);
                if(isIntCol){ lo=Math.round(lo); hi=Math.round(hi); }
                if(lo>hi){ const t=lo; lo=hi; hi=t; }
                columnMeta[index].curMin=lo;
                columnMeta[index].curMax=hi;
                inMin.value=isIntCol?String(lo):lo; inMax.value=isIntCol?String(hi):hi;
                rMin.value=lo; rMax.value=hi;
                const pct=v=>((v-minVal)/(maxVal-minVal||1))*100;
                fill.style.left=pct(lo)+'%';
                fill.style.width=(pct(hi)-pct(lo))+'%';
                const trigSpan=trigger.querySelector('span:first-child');
                trigSpan.textContent=(lo===minVal&&hi===maxVal)?'全部':(lo+' ~ '+hi);
                filterTable();
            }
            rMin.addEventListener('input',()=>{ if(+rMin.value>+rMax.value)rMin.value=rMax.value; syncUI(); });
            rMax.addEventListener('input',()=>{ if(+rMax.value<+rMin.value)rMax.value=rMin.value; syncUI(); });
            inMin.addEventListener('change',()=>{
                let v=parseFloat(inMin.value); if(isNaN(v))v=minVal;
                if(isIntCol) v=Math.round(v);
                rMin.value=v; syncUI();
            });
            inMax.addEventListener('change',()=>{
                let v=parseFloat(inMax.value); if(isNaN(v))v=maxVal;
                if(isIntCol) v=Math.round(v);
                rMax.value=v; syncUI();
            });
            resetBtn.addEventListener('click',()=>{ rMin.value=minVal; rMax.value=maxVal; syncUI(); });
            syncUI();

            dropdownWrapper.appendChild(trigger);
            document.body.appendChild(panel);
            allOptionContainers.push(panel);

            trigger.addEventListener('click',(e)=>{
                e.stopPropagation();
                document.querySelectorAll('.dropdown-content').forEach(d=>{
                    if(d!==panel)d.classList.remove('show');
                });
                const isOpen=panel.classList.contains('show');
                panel.classList.toggle('show');
                if(!isOpen){
                    const rect=trigger.getBoundingClientRect();
                    panel.style.width=Math.max(rect.width,190)+'px';
                    panel.style.left=rect.left+'px';
                    const dropH=panel.scrollHeight;
                    const spaceBelow=window.innerHeight-rect.bottom;
                    panel.style.top=(spaceBelow>=dropH||spaceBelow>=140?rect.bottom:(rect.top-dropH))+'px';
                }
            });
            panel.addEventListener('click',(e)=>e.stopPropagation());
            thCell.appendChild(dropdownWrapper);

        } else {
            // ── original categorical checkbox dropdown ───────────
            columnMeta[index]={type:'category'};
            const dropdownWrapper=document.createElement('div');
            dropdownWrapper.className='filter-dropdown';
            const trigger=document.createElement('div');
            trigger.className='filter-trigger';
            trigger.innerHTML='<span>筛选...</span><span style="font-size:10px">▼</span>';
            const optionsContainer=document.createElement('div');
            optionsContainer.className='dropdown-content';
            const searchInput=document.createElement('input');
            searchInput.type='text';
            searchInput.className='dropdown-search';
            searchInput.placeholder='搜索...';
            optionsContainer.prepend(searchInput);
            searchInput.addEventListener('input',(e)=>{
                const query=e.target.value.toLowerCase().trim();
                optionsContainer.querySelectorAll('.option-item').forEach(item=>{
                    if(item.dataset.selectAll)return;
                    const label=item.querySelector('span').textContent.toLowerCase();
                    item.style.display=label.includes(query)?'flex':'none';
                });
                const visibleCbs=Array.from(
                    optionsContainer.querySelectorAll('.option-item:not([data-select-all])')
                ).filter(i=>i.style.display!=='none')
                 .map(i=>i.querySelector('input[type="checkbox"]'));
                selectAllCb.checked=visibleCbs.length>0&&visibleCbs.every(cb=>cb.checked);
            });
            const selectAllItem=document.createElement('div');
            selectAllItem.className='option-item select-all-item';
            selectAllItem.dataset.selectAll='1';
            selectAllItem.style.borderBottom='2px solid var(--border)';
            const selectAllCb=document.createElement('input');
            selectAllCb.type='checkbox';
            selectAllCb.checked=true;
            const selectAllLabel=document.createElement('span');
            selectAllLabel.textContent='全选';
            selectAllLabel.style.fontWeight='600';
            selectAllItem.appendChild(selectAllCb);
            selectAllItem.appendChild(selectAllLabel);
            optionsContainer.appendChild(selectAllItem);
            selectAllCb.addEventListener('change',()=>{
                const checked=selectAllCb.checked;
                optionsContainer.querySelectorAll('.option-item:not([data-select-all])').forEach(item=>{
                    if(item.style.display!=='none')
                        item.querySelector('input[type="checkbox"]').checked=checked;
                });
                filterTable();
            });
            Array.from(new Set(rawValues)).sort((a,b)=>a.localeCompare(b,'zh')).forEach(val=>{
                const item=document.createElement('div');
                item.className='option-item';
                const cb=document.createElement('input');
                cb.type='checkbox';cb.value=val;cb.checked=true;
                const label=document.createElement('span');
                label.textContent=val;
                item.appendChild(cb);item.appendChild(label);
                optionsContainer.appendChild(item);
            });
            dropdownWrapper.appendChild(trigger);
            document.body.appendChild(optionsContainer);
            allOptionContainers.push(optionsContainer);
            thCell.appendChild(dropdownWrapper);

            trigger.addEventListener('click',(e)=>{
                e.stopPropagation();
                document.querySelectorAll('.dropdown-content').forEach(d=>{
                    if(d!==optionsContainer)d.classList.remove('show');
                });
                const isOpen=optionsContainer.classList.contains('show');
                optionsContainer.classList.toggle('show');
                if(!isOpen){
                    const rect=trigger.getBoundingClientRect();
                    const dropH=Math.min(250,optionsContainer.scrollHeight);
                    const spaceBelow=window.innerHeight-rect.bottom;
                    optionsContainer.style.width=rect.width+'px';
                    optionsContainer.style.top=(spaceBelow>=dropH||spaceBelow>=120?rect.bottom:(rect.top-dropH))+'px';
                    optionsContainer.style.left=rect.left+'px';
                }
            });
            optionsContainer.addEventListener('change',(e)=>{
                if(!e.target.closest('[data-select-all]')){
                    const visibleCbs=Array.from(
                        optionsContainer.querySelectorAll('.option-item:not([data-select-all])')
                    ).filter(i=>i.style.display!=='none')
                     .map(i=>i.querySelector('input[type="checkbox"]'));
                    selectAllCb.checked=visibleCbs.length>0&&visibleCbs.every(cb=>cb.checked);
                }
                filterTable();
            });
            optionsContainer.addEventListener('click',(e)=>e.stopPropagation());
        }

        filterRow.appendChild(thCell);
        header.addEventListener('click',()=>{
            headers.forEach(h=>h.classList.remove('sort-asc','sort-desc'));
            if(sortDirection==='none')sortDirection='asc';
            else if(sortDirection==='asc')sortDirection='desc';
            else sortDirection='none';
            if(sortDirection!=='none'){
                header.classList.add('sort-'+sortDirection);
                const rowsArray=Array.from(tbody.querySelectorAll('tr'));
                rowsArray.sort((a,b)=>{
                    const A=a.children[index].textContent.trim();
                    const B=b.children[index].textContent.trim();
                    const emA=A===''||A.toLowerCase()==='nan'||A==='-';
                    const emB=B===''||B.toLowerCase()==='nan'||B==='-';
                    if(emA&&!emB)return 1;
                    if(!emA&&emB)return -1;
                    if(emA&&emB)return 0;
                    const nA=parseFloat(A),nB=parseFloat(B);
                    if(!isNaN(nA)&&!isNaN(nB))return(nA-nB)*(sortDirection==='asc'?1:-1);
                    return A.localeCompare(B,'zh')*(sortDirection==='asc'?1:-1);
                });
                rowsArray.forEach(row=>tbody.appendChild(row));
            }
        });
    });

    thead.appendChild(filterRow);
    document.querySelector('.table-wrapper').addEventListener('scroll',()=>{
        allOptionContainers.forEach(oc=>oc.classList.remove('show'));
    });
    function updateFilterRowTop(){
        filterRow.style.top=headerRow.getBoundingClientRect().height+'px';
    }
    updateFilterRowTop();
    new ResizeObserver(updateFilterRowTop).observe(headerRow);

    function filterTable(){
        let visibleCount=0;
        rows.forEach(row=>{
            let showRow=true;
            const cells=row.querySelectorAll('td');
            columnMeta.forEach((meta,index)=>{
                if(!showRow||!cells[index])return;
                const cellText=cells[index].textContent.trim();
                if(meta.type==='numeric'){
                    const n=parseCellNumber(cellText);
                    if(!isNaN(n) && (n<meta.curMin || n>meta.curMax)) showRow=false;
                } else {
                    const oc=allOptionContainers[index];
                    const checkboxes=Array.from(oc.querySelectorAll('.option-item:not([data-select-all]) input[type="checkbox"]'));
                    const selected=checkboxes.filter(cb=>cb.checked).map(cb=>cb.value);
                    if(selected.length>0 && !selected.includes(cellText)) showRow=false;
                }
            });
            row.style.display=showRow?'':'none';
            if(showRow)visibleCount++;
        });
        document.getElementById('visible-count').textContent=visibleCount;
    }

    document.addEventListener('click',()=>{
        allOptionContainers.forEach(oc=>oc.classList.remove('show'));
    });
});"""

_JS_RANKING_DETAIL = """\
document.addEventListener('DOMContentLoaded',()=>{
    const modal=document.getElementById('detail-modal');
    const closeBtn=document.getElementById('detail-close');
    const body=document.getElementById('detail-body');
    const metaLine=document.getElementById('detail-meta-line');
    const footer=document.getElementById('detail-footer');
    if(!modal||!closeBtn||!body)return;

    function closeModal(){
        const card=modal.querySelector('.detail-card');
        if(card){ card.style.transform='translateY(10px) scale(.97)'; card.style.opacity='0'; }
        setTimeout(()=>{ modal.classList.remove('show'); if(card){ card.style.transform=''; card.style.opacity=''; } },220);
    }
    closeBtn.addEventListener('click',closeModal);
    modal.addEventListener('click',(e)=>{ if(e.target===modal)closeModal(); });
    document.addEventListener('keydown',(e)=>{ if(e.key==='Escape'&&modal.classList.contains('show'))closeModal(); });

    function getPlayerName(row){
        const cells=row.querySelectorAll('td');
        for(let i=0;i<cells.length;i++){
            const t=cells[i].textContent.trim();
            if(t&&i>0&&isNaN(parseFloat(t)))return t;
        }
        return '';
    }

    const rows=document.querySelectorAll('.filterable-table tbody tr');
    rows.forEach((row)=>{
        row.addEventListener('click',()=>{
            let details=[];
            try{ details=JSON.parse(row.dataset.detail||'[]'); }catch(_e){ details=[]; }
            if(!Array.isArray(details)) details=[];

            const name=getPlayerName(row);
            if(metaLine) metaLine.textContent=name?name:'';

            const survived=details.filter(v=>String(v).trim()!=='' && String(v).toLowerCase()!=='nan').length;

            if(details.length===0){
                body.innerHTML='<div class="detail-empty">暂无选人记录</div>';
                if(footer) footer.textContent='';
            }else{
                body.innerHTML=details.map((v,i)=>{
                    const val=String(v).trim();
                    const isEmpty=val===''||val.toLowerCase()==='nan';
                    return '<div class="detail-item">'
                        +'<span class="detail-day">Day '+(i+1)+'</span>'
                        +'<span class="detail-val">'+(isEmpty?'<span style="color:var(--faint)">—</span>':val)+'</span>'
                        +'</div>';
                }).join('');
                if(footer) footer.textContent='共 '+details.length+' 天 · '+survived+' 天有效选人';
            }
            modal.classList.add('show');
        });
    });
});
"""

_JS_CAREER_DETAIL = """\
document.addEventListener('DOMContentLoaded',function(){
    var modal=document.getElementById('detail-modal');
    var closeBtn=document.getElementById('detail-close');
    var body=document.getElementById('detail-body');
    var metaLine=document.getElementById('detail-meta-line');
    var footer=document.getElementById('detail-footer');
    if(!modal||!closeBtn||!body)return;

    function esc(s){
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    function closeModal(){
        var card=modal.querySelector('.detail-card');
        if(card){ card.style.transform='translateY(10px) scale(.97)'; card.style.opacity='0'; }
        setTimeout(function(){
            modal.classList.remove('show');
            if(card){ card.style.transform=''; card.style.opacity=''; }
        },220);
    }
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function(e){ if(e.target===modal) closeModal(); });
    document.addEventListener('keydown', function(e){
        if(e.key==='Escape'&&modal.classList.contains('show')) closeModal();
    });

    function getPlayerName(row){
        var cells=row.querySelectorAll('td');
        for(var i=0;i<cells.length;i++){
            var t=cells[i].textContent.trim();
            if(t&&i>0&&isNaN(parseFloat(t))) return t;
        }
        return '';
    }

    function chipBlock(title, items, emptyText){
        var list=Array.isArray(items)?items:[];
        var chips=list.length
            ? list.map(function(x){ return '<span class="career-chip">'+esc(x)+'</span>'; }).join('')
            : '<span class="career-empty">'+esc(emptyText)+'</span>';
        return '<div class="career-sec">'
            +'<div class="career-sec-hd"><span>'+esc(title)+'</span>'
            +'<em>'+list.length+'</em></div>'
            +'<div class="career-chips">'+chips+'</div></div>';
    }

    function textBlock(title, text){
        var t=String(text||'').trim();
        return '<div class="career-sec">'
            +'<div class="career-sec-hd"><span>'+esc(title)+'</span></div>'
            +'<div class="career-note">'+(t?esc(t):'<span class="career-empty">暂无</span>')+'</div></div>';
    }

    document.querySelectorAll('.filterable-table tbody tr').forEach(function(row){
        row.style.cursor='pointer';
        row.addEventListener('click', function(){
            var data={};
            try{ data=JSON.parse(row.dataset.detail||'{}'); }catch(_e){ data={}; }
            if(!data||typeof data!=='object'||Array.isArray(data)) data={};
            var name=getPlayerName(row);
            if(metaLine) metaLine.textContent=name||'';
            body.innerHTML =
                chipBlock('夺冠明细', data.titles, '暂无夺冠')
                + chipBlock('夺亚明细', data.runners, '暂无夺亚')
                + textBlock('连胜细节', data.win_streak)
                + textBlock('连败细节', data.lose_streak);
            var nT=(data.titles||[]).length, nR=(data.runners||[]).length;
            if(footer) footer.textContent='冠军 '+nT+' · 亚军 '+nR+' · 点击空白处关闭';
            modal.classList.add('show');
        });
    });
});
"""

_CSS_CAREER_DETAIL = """\
.career-sec{margin:0 0 14px;}
.career-sec:last-child{margin-bottom:0;}
.career-sec-hd{display:flex;align-items:baseline;justify-content:space-between;
  gap:10px;margin-bottom:8px;font-size:12px;color:var(--muted);}
.career-sec-hd span{font-family:'Space Mono',monospace;letter-spacing:.08em;
  text-transform:uppercase;font-size:10px;color:var(--faint);}
.career-sec-hd em{font-style:normal;font-family:'Space Mono',monospace;
  color:var(--primary-dark);font-weight:700;}
body.dark .career-sec-hd em{color:var(--primary);}
.career-chips{display:flex;flex-wrap:wrap;gap:6px;}
.career-chip{display:inline-block;padding:4px 9px;border-radius:999px;
  background:var(--surface2);border:0.5px solid var(--border);font-size:12px;
  color:var(--ink);line-height:1.35;max-width:100%;}
.career-note{font-size:13px;line-height:1.6;color:var(--ink2,var(--muted));
  padding:8px 10px;border-radius:8px;background:var(--surface2);}
.career-empty{font-size:12px;color:var(--faint);}
.filterable-table tbody tr{cursor:pointer;}
"""


_JS_ROUTE_QUERY = """\
document.addEventListener('DOMContentLoaded',function(){
    var modal = document.getElementById('rq-modal');
    var closeBtn = document.getElementById('rq-close');
    if (!modal || !closeBtn) return;

    function findColIndex(headerText){
        var ths = document.querySelectorAll('.filterable-table thead tr:first-child th');
        for (var i=0;i<ths.length;i++){
            if (ths[i].textContent.trim() === headerText) return i;
        }
        return -1;
    }

    function closeModal(){
        var card = modal.querySelector('.detail-card');
        if (card){ card.style.transform='translateY(10px) scale(.97)'; card.style.opacity='0'; }
        setTimeout(function(){
            modal.classList.remove('show');
            if (card){ card.style.transform=''; card.style.opacity=''; }
        },220);
    }
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function(e){ if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', function(e){
        if (e.key === 'Escape' && modal.classList.contains('show')) closeModal();
    });

    var entryBar = document.getElementById('rq-entry');
    if (entryBar){
        entryBar.addEventListener('click', function(){ modal.classList.add('show'); });
    }

    var selected = new Set();
    var searchInput = document.getElementById('rq-search');
    var optList = document.getElementById('rq-opt-list');
    var tagsEl = document.getElementById('rq-tags');
    var runBtn = document.getElementById('rq-run-btn');
    var countEl = document.getElementById('rq-result-count');
    var resultEl = document.getElementById('rq-result-list');

    function renderTags(){
        tagsEl.innerHTML = '';
        selected.forEach(function(p){
            var tag = document.createElement('span');
            tag.className = 'rq-tag';
            tag.appendChild(document.createTextNode(p + ' '));
            var rm = document.createElement('span');
            rm.className = 'rq-tag-rm';
            rm.textContent = '\\u00d7';
            rm.addEventListener('click', function(){ toggle(p); });
            tag.appendChild(rm);
            tagsEl.appendChild(tag);
        });
    }

    function syncOptUI(){
        if (!optList) return;
        optList.querySelectorAll('.rq-opt').forEach(function(opt){
            var p = opt.dataset.player;
            var cb = opt.querySelector('input[type=checkbox]');
            var isSel = selected.has(p);
            if (cb) cb.checked = isSel;
            opt.classList.toggle('sel', isSel);
        });
    }

    function toggle(p){
        if (selected.has(p)) selected.delete(p); else selected.add(p);
        syncOptUI();
        renderTags();
    }

    if (optList){
        optList.querySelectorAll('.rq-opt').forEach(function(opt){
            opt.addEventListener('click', function(){ toggle(opt.dataset.player); });
        });
    }

    if (searchInput){
        searchInput.addEventListener('input', function(){
            var q = searchInput.value.toLowerCase().trim();
            optList.querySelectorAll('.rq-opt').forEach(function(opt){
                var label = opt.textContent.toLowerCase();
                opt.style.display = label.indexOf(q) !== -1 ? 'flex' : 'none';
            });
        });
    }

    function runQuery(){
        var statusIdx = findColIndex('当前状态');
        var nameIdx   = findColIndex('用户名');
        var mainIdx   = findColIndex('今日主选');
        var backIdx   = findColIndex('今日备选');
        var rows = document.querySelectorAll('.filterable-table tbody tr');
        var matches = [];

        rows.forEach(function(row){
            var cells = row.querySelectorAll('td');
            if (statusIdx < 0 || nameIdx < 0 || !cells[statusIdx] || !cells[nameIdx]) return;
            var status = cells[statusIdx].textContent.trim();
            if (status !== '存活' && status !== '未完赛'
                && status !== '未选' && status !== '轮空') return;

            var detail = [];
            try { detail = JSON.parse(row.dataset.detail || '[]'); } catch (err) { detail = []; }
            if (!Array.isArray(detail)) detail = [];

            var hasSelected = false;
            selected.forEach(function(p){ if (detail.indexOf(p) !== -1) hasSelected = true; });
            if (hasSelected) return;

            var name = cells[nameIdx].textContent.trim();
            var main = mainIdx >= 0 && cells[mainIdx] ? cells[mainIdx].textContent.trim() : '';
            var back = backIdx >= 0 && cells[backIdx] ? cells[backIdx].textContent.trim() : '';
            matches.push({ name: name, main: main, back: back });
        });

        if (!countEl || !resultEl) return;

        countEl.textContent = selected.size === 0
            ? '请至少选择一名球员'
            : ('符合条件 · ' + matches.length + ' 位存活用户未选过以上球员');

        if (selected.size === 0 || matches.length === 0){
            resultEl.innerHTML = '<div class="rq-empty">'
                + (selected.size === 0 ? '选择球员后点击查询查看结果' : '暂无符合条件的用户')
                + '</div>';
            return;
        }

        function esc(s){
            return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        }

        resultEl.innerHTML = matches.map(function(m){
            var pickText;
            if (m.main || m.back){
                pickText = '今日主选：<b>' + esc(m.main || '\\u2014') + '</b>'
                    + (m.back ? ' / 备选：<b>' + esc(m.back) + '</b>' : '');
            } else {
                pickText = '今日：未选';
            }
            return '<div class="rq-result-row">'
                + '<span class="rq-badge">' + (status || '存活') + '</span>'
                + '<span class="rq-result-name" title="' + esc(m.name) + '">' + esc(m.name) + '</span>'
                + '<span class="rq-result-pick">' + pickText + '</span>'
                + '</div>';
        }).join('');
    }

    if (runBtn) runBtn.addEventListener('click', runQuery);
});
"""


#!/usr/bin/env python3
from __future__ import annotations
from eec_report_common import *

def library_ecu_files(root: Path, cfg: dict[str, Any], only: str | None = None) -> list[Path]:
    files=[]
    for pat in cfg.get('library_ecu_globs', ['library/ecus/*.json']):
        files.extend(sorted(root.glob(pat)))
    if only:
        want=only.lower().replace('.json','')
        files=[p for p in files if p.stem.lower()==want or want in p.stem.lower()]
    return files

def rows_for_ecu(path: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    data=load_json(path); rows=[]
    for pin in data.get('pins',[]) if isinstance(data.get('pins'),list) else []:
        if not isinstance(pin,dict): continue
        rows.append({'ecu':data.get('name',''),'variant':data.get('variant',''),'connector':pin.get('connector',''),'pin':pin.get('physical_number',pin.get('number','')),'name':pin.get('name',''),'role':pin.get('role',''),'type':pin.get('type',''),'group':pin.get('group',''),'electrical':decode_mask(pin.get('electrical_capability',0), cfg.get('electrical_flags',{})),'diagnostics':decode_mask(pin.get('diagnostic_flags',0), cfg.get('diagnostic_flags',{}))})
    return rows


def main() -> int:
    parser=standard_arg_parser('Generate v4 generic combined library ECU pinouts.'); args=parser.parse_args(); cfg=load_config(Path(args.config) if args.config else None); root=resolve_root(args.root)
    files=library_ecu_files(root,cfg)

    # Build data dict for JSON injection
    ecus_data = []
    for p in files:
        rows = rows_for_ecu(p, cfg)
        ecus_data.append({
            "name": load_json(p).get("name", p.stem) if p.exists() else p.stem,
            "variant": load_json(p).get("variant", "") if p.exists() else "",
            "file": p.name,
            "rows": rows,
        })

    data = {"ecus": ecus_data}
    data_json = json.dumps(data, ensure_ascii=False)

    html_content = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Library ECU Pinouts</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
:root{{
  --bg:#0d0f14;--surface:#131720;--raised:#1a1f2e;--hover:#1f2538;--active:#242b42;
  --b0:rgba(255,255,255,.06);--b1:rgba(255,255,255,.10);--b2:rgba(255,255,255,.16);
  --tp:#e8ecf4;--ts:#8993a8;--tm:#5a6278;--ta:#60a5fa;
  --accent:#3b82f6;--accent-dim:rgba(59,130,246,.15);
  --r:6px;--rm:10px;--rl:16px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;overflow:hidden}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--tp);font-size:13px;line-height:1.5;display:flex;flex-direction:column}}
button,input{{font:inherit;color:inherit}}

/* Topbar */
.topbar{{display:flex;align-items:center;gap:16px;padding:0 24px;height:56px;background:var(--surface);border-bottom:1px solid var(--b0);flex-shrink:0;z-index:20}}
.topbar-brand{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px;color:var(--tp);letter-spacing:-.01em;white-space:nowrap}}
.topbar-brand svg{{color:var(--accent)}}
.topbar-divider{{width:1px;height:24px;background:var(--b1);margin:0 4px}}
.topbar-kpis{{display:flex;gap:20px;flex:1}}
.kpi-item{{display:flex;flex-direction:column;align-items:flex-start}}
.kpi-item .kpi-val{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:var(--tp);line-height:1.2}}
.kpi-item .kpi-lbl{{font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--tm)}}
.topbar-search{{margin-left:auto;display:flex;align-items:center;gap:8px}}
.search-input{{padding:6px 12px 6px 32px;background:var(--raised);border:1px solid var(--b1);border-radius:var(--rm);color:var(--tp);outline:none;font-size:12px;width:220px;transition:border-color .15s}}
.search-input:focus{{border-color:var(--accent)}}
.search-input::placeholder{{color:var(--tm)}}
.search-wrap{{position:relative}}
.search-wrap svg{{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--tm);pointer-events:none}}

/* App body */
.app-body{{display:flex;flex:1;overflow:hidden}}

/* Sidebar */
.sidebar{{width:220px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--b0);display:flex;flex-direction:column;overflow:hidden}}
.sidebar-header{{padding:14px 16px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--tm);border-bottom:1px solid var(--b0);flex-shrink:0}}
.sidebar-list{{flex:1;overflow-y:auto;padding:8px 0}}
.sidebar-item{{display:flex;align-items:center;gap:8px;padding:8px 16px;cursor:pointer;border-radius:0;transition:background .12s;border-left:2px solid transparent}}
.sidebar-item:hover{{background:var(--hover)}}
.sidebar-item.active{{background:var(--accent-dim);border-left-color:var(--accent)}}
.sidebar-item .si-name{{font-size:12px;font-weight:500;color:var(--ts);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}}
.sidebar-item.active .si-name{{color:var(--tp)}}
.sidebar-item .si-count{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm);background:var(--raised);border:1px solid var(--b0);border-radius:4px;padding:1px 5px;flex-shrink:0}}
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--b1);border-radius:2px}}

/* Main content */
.main-content{{flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:20px}}

/* ECU sections */
.ecu-section{{background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);overflow:hidden}}
.ecu-section.hidden{{display:none}}
.ecu-header{{display:flex;align-items:center;gap:12px;padding:16px 20px;background:var(--raised);border-bottom:1px solid var(--b0);cursor:pointer;user-select:none}}
.ecu-header:hover{{background:var(--hover)}}
.ecu-toggle{{color:var(--tm);transition:transform .2s;flex-shrink:0}}
.ecu-toggle.open{{transform:rotate(90deg)}}
.ecu-title{{font-size:14px;font-weight:700;color:var(--tp);flex:1}}
.ecu-variant{{font-size:10px;font-weight:600;font-family:'JetBrains Mono',monospace;background:var(--accent-dim);color:var(--ta);border:1px solid rgba(59,130,246,.25);border-radius:4px;padding:2px 8px}}
.ecu-file{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm);margin-left:auto}}
.ecu-body{{display:none;flex-direction:column;gap:0}}
.ecu-body.open{{display:flex}}

/* Connector utilization grid */
.connector-grid-wrap{{padding:16px 20px;border-bottom:1px solid var(--b0);background:var(--surface)}}
.connector-grid-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--tm);margin-bottom:10px}}
.connector-grid{{display:flex;flex-wrap:wrap;gap:8px}}
.conn-card{{background:var(--raised);border:1px solid var(--b1);border-radius:var(--rm);padding:10px 14px;min-width:90px;display:flex;flex-direction:column;gap:2px}}
.conn-card-name{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:var(--tp)}}
.conn-card-count{{font-size:10px;color:var(--tm)}}
.conn-card-bar{{margin-top:6px;height:3px;border-radius:2px;background:var(--b0);overflow:hidden}}
.conn-card-bar-fill{{height:100%;background:var(--accent);border-radius:2px}}

/* Table area */
.table-wrap-outer{{padding:0}}
.table-toolbar{{display:flex;gap:8px;align-items:center;padding:12px 20px;border-bottom:1px solid var(--b0)}}
.table-search{{padding:6px 10px;background:var(--raised);border:1px solid var(--b1);border-radius:var(--r);color:var(--tp);outline:none;font-size:12px;width:200px;transition:border-color .15s}}
.table-search:focus{{border-color:var(--accent)}}
.table-search::placeholder{{color:var(--tm)}}
.csv-btn{{padding:5px 10px;background:var(--raised);border:1px solid var(--b1);border-radius:var(--r);color:var(--ts);cursor:pointer;font-size:11px;transition:all .12s}}
.csv-btn:hover{{border-color:var(--b2);color:var(--tp)}}
.row-count{{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm)}}
.table-scroll{{overflow:auto;max-height:520px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{position:sticky;top:0;background:var(--raised);z-index:2;padding:8px 12px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--tm);border-bottom:1px solid var(--b1);cursor:pointer;white-space:nowrap;user-select:none}}
th:hover{{background:var(--active);color:var(--ts)}}
th .sort-indicator{{margin-left:4px;opacity:.4}}
td{{padding:7px 12px;border-bottom:1px solid var(--b0);vertical-align:top;color:var(--ts)}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.025);color:var(--tp)}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:11px}}

/* Interface pills */
.pill{{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap;border:1px solid transparent}}
.pill-ANALOG{{background:rgba(245,158,11,.12);color:#f59e0b;border-color:rgba(245,158,11,.25)}}
.pill-DIGITAL{{background:rgba(16,185,129,.12);color:#10b981;border-color:rgba(16,185,129,.25)}}
.pill-CAN{{background:rgba(34,211,238,.12);color:#22d3ee;border-color:rgba(34,211,238,.25)}}
.pill-PWM{{background:rgba(249,115,22,.12);color:#f97316;border-color:rgba(249,115,22,.25)}}
.pill-FREQ{{background:rgba(139,92,246,.12);color:#8b5cf6;border-color:rgba(139,92,246,.25)}}
.pill-POWER{{background:rgba(52,211,153,.12);color:#34d399;border-color:rgba(52,211,153,.25)}}
.pill-GROUND{{background:rgba(107,114,128,.12);color:#6b7280;border-color:rgba(107,114,128,.25)}}
.pill-RESISTANCE{{background:rgba(100,116,139,.12);color:#64748b;border-color:rgba(100,116,139,.25)}}
.pill-LIN{{background:rgba(167,139,250,.12);color:#a78bfa;border-color:rgba(167,139,250,.25)}}
.pill-default{{background:rgba(148,163,184,.08);color:#94a3b8;border-color:rgba(148,163,184,.2)}}

/* Empty state */
.empty-state{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;color:var(--tm);gap:8px;text-align:center}}
.empty-state svg{{opacity:.3}}
.empty-state p{{font-size:13px}}
</style></head>
<body>
<header class="topbar">
  <div class="topbar-brand">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
    Library ECU Pinouts
  </div>
  <div class="topbar-divider"></div>
  <div class="topbar-kpis">
    <div class="kpi-item"><span class="kpi-val" id="kpi-ecus">0</span><span class="kpi-lbl">ECUs</span></div>
    <div class="kpi-item"><span class="kpi-val" id="kpi-pins">0</span><span class="kpi-lbl">Total Pins</span></div>
    <div class="kpi-item"><span class="kpi-val" id="kpi-connectors">0</span><span class="kpi-lbl">Connectors</span></div>
  </div>
  <div class="topbar-search">
    <div class="search-wrap">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input class="search-input" id="global-search" placeholder="Search ECUs…" oninput="filterECUs(this.value)"/>
    </div>
  </div>
</header>
<div class="app-body">
  <nav class="sidebar">
    <div class="sidebar-header">ECU Files</div>
    <div class="sidebar-list" id="sidebar-list"></div>
  </nav>
  <main class="main-content" id="main-content"></main>
</div>
<script>
var DATA = {data_json};

var PILL_CLASSES = {{
  ANALOG:'pill-ANALOG',DIGITAL:'pill-DIGITAL',CAN:'pill-CAN',PWM:'pill-PWM',
  FREQ:'pill-FREQ',POWER:'pill-POWER',GROUND:'pill-GROUND',RESISTANCE:'pill-RESISTANCE',LIN:'pill-LIN'
}};

function pillClass(type){{
  if(!type)return 'pill-default';
  var k=(type||'').toUpperCase().trim();
  return PILL_CLASSES[k]||'pill-default';
}}

function esc(s){{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function buildConnectorGrid(rows){{
  var counts={{}};
  rows.forEach(function(r){{
    var c=r.connector||'(no connector)';
    counts[c]=(counts[c]||0)+1;
  }});
  var entries=Object.entries(counts).sort(function(a,b){{return a[0].localeCompare(b[0]);}});
  if(entries.length===0)return '';
  var max=Math.max.apply(null,entries.map(function(e){{return e[1]}}));
  var cards=entries.map(function(e){{
    var pct=max>0?Math.round((e[1]/max)*100):0;
    return '<div class="conn-card">'+
      '<div class="conn-card-name">'+esc(e[0])+'</div>'+
      '<div class="conn-card-count">'+e[1]+' pin'+(e[1]!==1?'s':'')+'</div>'+
      '<div class="conn-card-bar"><div class="conn-card-bar-fill" style="width:'+pct+'%"></div></div>'+
      '</div>';
  }}).join('');
  return '<div class="connector-grid-wrap">'+
    '<div class="connector-grid-title">Connector Utilization</div>'+
    '<div class="connector-grid">'+cards+'</div>'+
    '</div>';
}}

var tableSortState={{}};

function sortTable(tableId, colIdx){{
  var tbl=document.getElementById(tableId);
  if(!tbl)return;
  var key=tableId+'_'+colIdx;
  var asc=tableSortState[key]!==true;
  tableSortState[key]=asc;
  var tbody=tbl.querySelector('tbody');
  var rows=[].slice.call(tbody.querySelectorAll('tr'));
  rows.sort(function(a,b){{
    var A=a.cells[colIdx]?a.cells[colIdx].getAttribute('data-val')||a.cells[colIdx].innerText:'';
    var B=b.cells[colIdx]?b.cells[colIdx].getAttribute('data-val')||b.cells[colIdx].innerText:'';
    var x=parseFloat(A),y=parseFloat(B);
    if(!isNaN(x)&&!isNaN(y))return asc?x-y:y-x;
    return asc?A.localeCompare(B):B.localeCompare(A);
  }});
  rows.forEach(function(r){{tbody.appendChild(r);}});
  tbl.querySelectorAll('th .sort-indicator').forEach(function(el){{el.textContent='';el.style.opacity='.4';}});
  var th=tbl.querySelectorAll('th')[colIdx];
  if(th){{var ind=th.querySelector('.sort-indicator');if(ind){{ind.textContent=asc?' ↑':' ↓';ind.style.opacity='1';}}}}
}}

function filterTableLocal(tableId, q){{
  var tbl=document.getElementById(tableId);
  if(!tbl)return;
  var lq=(q||'').toLowerCase();
  var rows=[].slice.call(tbl.querySelectorAll('tbody tr'));
  rows.forEach(function(r){{
    r.style.display=r.innerText.toLowerCase().indexOf(lq)>-1?'':'none';
  }});
  var visible=rows.filter(function(r){{return r.style.display!=='none';}}).length;
  var rc=document.getElementById(tableId+'_count');
  if(rc)rc.textContent=visible+' / '+rows.length+' rows';
}}

function exportCSV(tableId){{
  var tbl=document.getElementById(tableId);
  if(!tbl)return;
  var rows=[].slice.call(tbl.querySelectorAll('tr')).filter(function(r){{return r.style.display!=='none';}});
  var csv=rows.map(function(r){{
    return [].slice.call(r.cells).map(function(c){{return '"'+c.innerText.replace(/"/g,'""')+'"';}}).join(',');
  }}).join('\\n');
  var a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download=tableId+'.csv';a.click();
}}

function buildTable(rows, ecuIdx){{
  var cols=[
    {{key:'connector',label:'Connector'}},
    {{key:'pin',label:'Pin'}},
    {{key:'name',label:'Name'}},
    {{key:'role',label:'Role'}},
    {{key:'type',label:'Type'}},
    {{key:'group',label:'Group'}},
    {{key:'electrical',label:'Electrical'}},
    {{key:'diagnostics',label:'Diagnostics'}},
  ];
  var tableId='tbl_'+ecuIdx;
  var head=cols.map(function(c,i){{
    return '<th onclick="sortTable(\\''+tableId+'\\','+i+')" style="cursor:pointer">'+esc(c.label)+'<span class="sort-indicator"></span></th>';
  }}).join('');
  var tbody=rows.map(function(r){{
    var cells=cols.map(function(c){{
      if(c.key==='type'){{
        var t=r[c.key]||'';
        return '<td><span class="pill '+pillClass(t)+'">'+esc(t||'—')+'</span></td>';
      }}
      return '<td class="'+(c.key==='pin'||c.key==='connector'?'mono':'')+'" data-val="'+esc(r[c.key]||'')+'">'+esc(r[c.key]||'')+'</td>';
    }}).join('');
    return '<tr>'+cells+'</tr>';
  }}).join('');
  var html='<div class="table-toolbar">'+
    '<input class="table-search" placeholder="Filter rows…" oninput="filterTableLocal(\\''+tableId+'\\',this.value)"/>'+
    '<button class="csv-btn" onclick="exportCSV(\\''+tableId+'\\')">↓ CSV</button>'+
    '<span class="row-count" id="'+tableId+'_count">'+rows.length+' rows</span>'+
    '</div>'+
    '<div class="table-scroll">'+
    '<table id="'+tableId+'"><thead><tr>'+head+'</tr></thead>'+
    '<tbody>'+tbody+'</tbody></table></div>';
  return html;
}}

function buildECUSection(ecu, idx){{
  var sectionId='ecu-section-'+idx;
  var bodyId='ecu-body-'+idx;
  var toggleId='ecu-toggle-'+idx;

  var connGrid=buildConnectorGrid(ecu.rows);
  var tableHtml=ecu.rows.length>0?buildTable(ecu.rows,idx):'<div class="empty-state"><p>No pins found in this ECU.</p></div>';
  var variantBadge=ecu.variant?'<span class="ecu-variant">'+esc(ecu.variant)+'</span>':'';

  return '<div class="ecu-section" id="'+sectionId+'" data-name="'+esc((ecu.name||ecu.file||'').toLowerCase())+'">'+
    '<div class="ecu-header" onclick="toggleSection(\\''+bodyId+'\\',\\''+toggleId+'\\')" id="hdr-'+idx+'">'+
    '<svg id="'+toggleId+'" class="ecu-toggle" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>'+
    '<span class="ecu-title">'+esc(ecu.name||ecu.file)+'</span>'+
    variantBadge+
    '<span class="ecu-file">'+esc(ecu.file)+'</span>'+
    '</div>'+
    '<div class="ecu-body" id="'+bodyId+'">'+
    connGrid+
    '<div class="table-wrap-outer">'+tableHtml+'</div>'+
    '</div>'+
    '</div>';
}}

function toggleSection(bodyId, toggleId){{
  var body=document.getElementById(bodyId);
  var toggle=document.getElementById(toggleId);
  if(!body)return;
  var isOpen=body.classList.contains('open');
  body.classList.toggle('open',!isOpen);
  toggle.classList.toggle('open',!isOpen);
}}

function setSidebarActive(idx){{
  document.querySelectorAll('.sidebar-item').forEach(function(el){{el.classList.remove('active');}});
  var item=document.getElementById('sidebar-item-'+idx);
  if(item)item.classList.add('active');
}}

function scrollToECU(idx){{
  setSidebarActive(idx);
  var section=document.getElementById('ecu-section-'+idx);
  if(section){{
    section.scrollIntoView({{behavior:'smooth',block:'start'}});
    // Auto-open if closed
    var bodyEl=document.getElementById('ecu-body-'+idx);
    var toggleEl=document.getElementById('ecu-toggle-'+idx);
    if(bodyEl&&!bodyEl.classList.contains('open')){{
      bodyEl.classList.add('open');
      toggleEl.classList.add('open');
    }}
  }}
}}

function filterECUs(q){{
  var lq=(q||'').toLowerCase();
  DATA.ecus.forEach(function(ecu,idx){{
    var section=document.getElementById('ecu-section-'+idx);
    var sideItem=document.getElementById('sidebar-item-'+idx);
    if(!section)return;
    var name=(ecu.name||ecu.file||'').toLowerCase();
    var visible=!lq||name.indexOf(lq)>-1;
    section.classList.toggle('hidden',!visible);
    if(sideItem)sideItem.style.display=visible?'':'none';
  }});
}}

function init(){{
  var ecus=DATA.ecus;
  var totalPins=0;
  var connectorSet=new Set();

  ecus.forEach(function(ecu){{
    totalPins+=ecu.rows.length;
    ecu.rows.forEach(function(r){{if(r.connector)connectorSet.add(r.connector);}});
  }});

  document.getElementById('kpi-ecus').textContent=ecus.length;
  document.getElementById('kpi-pins').textContent=totalPins;
  document.getElementById('kpi-connectors').textContent=connectorSet.size;

  // Build sidebar
  var sidebarList=document.getElementById('sidebar-list');
  ecus.forEach(function(ecu,idx){{
    var item=document.createElement('div');
    item.className='sidebar-item';
    item.id='sidebar-item-'+idx;
    item.innerHTML='<span class="si-name">'+esc(ecu.name||ecu.file)+'</span><span class="si-count">'+ecu.rows.length+'</span>';
    item.onclick=function(){{scrollToECU(idx);}};
    sidebarList.appendChild(item);
  }});

  // Build main content
  var main=document.getElementById('main-content');
  if(ecus.length===0){{
    main.innerHTML='<div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg><p>No ECU JSON files found.</p></div>';
    return;
  }}

  ecus.forEach(function(ecu,idx){{
    var div=document.createElement('div');
    div.innerHTML=buildECUSection(ecu,idx);
    main.appendChild(div.firstChild);
  }});

  // Scroll spy
  var observer=new IntersectionObserver(function(entries){{
    entries.forEach(function(e){{
      if(e.isIntersecting){{
        var id=e.target.id.replace('ecu-section-','');
        setSidebarActive(parseInt(id,10));
      }}
    }});
  }},{{threshold:0.1,rootMargin:'-10% 0px -80% 0px'}});
  ecus.forEach(function(_,idx){{
    var section=document.getElementById('ecu-section-'+idx);
    if(section)observer.observe(section);
  }});
}}

document.addEventListener('DOMContentLoaded',init);
</script>
</body></html>"""

    out=get_output_file(root,cfg,'library_ecu_pinouts',args.output,args.outdir)
    write_text(out, html_content)
    print(out)
    return 0

if __name__=='__main__': raise SystemExit(main())

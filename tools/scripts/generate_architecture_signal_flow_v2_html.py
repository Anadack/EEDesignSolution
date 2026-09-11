#!/usr/bin/env python3
from __future__ import annotations
import json
from eec_report_common import *

def main() -> int:
    parser = standard_arg_parser('Generate v4 generic Signal Flow v2 HTML.')
    args = parser.parse_args()
    cfg = load_config(Path(args.config) if args.config else None)
    root = resolve_root(args.root)
    src, arch = load_architecture_from_args(args, cfg, physical=False)
    rows = collect_allocation_rows(arch, cfg)

    data = {
        "source": str(src.relative_to(root) if src.is_relative_to(root) else src),
        "rows": rows,
    }
    data_json = json.dumps(data, ensure_ascii=False)

    html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Signal Flow v2</title>
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
  --c-analog:#f59e0b;--c-digital:#10b981;--c-can:#22d3ee;--c-pwm:#f97316;
  --c-freq:#8b5cf6;--c-power:#34d399;--c-ground:#6b7280;--c-resistance:#64748b;
  --c-lin:#a78bfa;--c-default:#94a3b8;
  --ok:#22c55e;--warn:#f59e0b;--err:#ef4444;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{min-height:100vh;background:var(--bg);color:var(--tp);font-family:'Inter',system-ui,sans-serif;font-size:13px;line-height:1.5}}
button,input,select{{font:inherit;color:inherit}}

/* ── topbar ── */
.topbar{{
  position:sticky;top:0;z-index:50;
  background:rgba(13,15,20,.92);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--b0);
  padding:0 24px;
  display:flex;align-items:center;gap:16px;min-height:56px;flex-wrap:wrap;
}}
.topbar-title{{font-size:1rem;font-weight:700;letter-spacing:-.01em;color:var(--tp);white-space:nowrap}}
.topbar-kpis{{display:flex;gap:8px;flex-wrap:wrap}}
.kpi-chip{{
  background:var(--raised);border:1px solid var(--b1);border-radius:var(--r);
  padding:4px 12px;display:flex;align-items:center;gap:6px;
}}
.kpi-chip .kv{{font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:700;color:var(--tp)}}
.kpi-chip .kl{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--tm)}}
.tabs{{display:flex;gap:2px;margin-left:auto}}
.tab{{
  padding:6px 16px;border-radius:var(--r);border:1px solid transparent;
  background:transparent;color:var(--ts);cursor:pointer;font-size:12px;font-weight:600;
  transition:all .15s;
}}
.tab:hover{{background:var(--raised);color:var(--tp)}}
.tab.active{{background:var(--accent-dim);border-color:var(--accent);color:var(--ta)}}

/* ── app body ── */
.app-body{{padding:20px 24px;display:grid;gap:12px;max-width:1600px;margin:0 auto}}

/* ── filter bar ── */
.filterbar{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rm);
  padding:12px 16px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;
}}
.filterbar label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);margin-right:4px}}
.pill-btn{{
  padding:4px 10px;border-radius:20px;border:1px solid var(--b1);
  background:var(--raised);color:var(--ts);cursor:pointer;font-size:11px;font-weight:600;
  transition:all .12s;
}}
.pill-btn:hover{{border-color:var(--b2);color:var(--tp)}}
.pill-btn.on{{color:#fff;border-color:transparent}}
input.search{{
  padding:7px 12px;background:var(--raised);border:1px solid var(--b1);
  border-radius:var(--r);color:var(--tp);outline:none;transition:border-color .15s;min-width:200px;
}}
input.search:focus{{border-color:var(--accent)}}
input.search::placeholder{{color:var(--tm)}}

/* ── tab panels ── */
.tab-panel{{display:none}}
.tab-panel.active{{display:block}}

/* ── ECU groups ── */
.ecu-group{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);
  margin-bottom:10px;overflow:hidden;
}}
.ecu-group-header{{
  display:flex;align-items:center;gap:10px;padding:12px 18px;
  background:var(--raised);border-bottom:1px solid var(--b0);
  cursor:pointer;user-select:none;
}}
.ecu-group-header:hover{{background:var(--hover)}}
.ecu-name{{font-size:.95rem;font-weight:700;color:var(--ta);font-family:'JetBrains Mono',monospace}}
.ecu-count{{font-size:10px;color:var(--tm);padding:2px 8px;background:var(--active);border-radius:20px;font-weight:600}}
.ecu-chevron{{margin-left:auto;color:var(--tm);font-size:12px;transition:transform .2s}}
.ecu-group.collapsed .ecu-chevron{{transform:rotate(-90deg)}}
.ecu-body{{padding:12px 18px;display:grid;gap:4px}}
.ecu-group.collapsed .ecu-body{{display:none}}
.signal-row{{
  display:grid;grid-template-columns:auto 1fr auto auto auto auto;
  align-items:center;gap:10px;padding:7px 10px;border-radius:var(--r);
  background:var(--raised);border:1px solid var(--b0);
  transition:background .12s;
}}
.signal-row:hover{{background:var(--hover)}}
.sig-name{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:var(--tp)}}
.sig-device{{font-size:11px;color:var(--ts)}}
.sig-pin{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm)}}
.sys-badge{{
  display:inline-flex;align-items:center;padding:2px 8px;border-radius:4px;
  font-size:10px;font-weight:700;background:var(--accent-dim);color:var(--ta);
  border:1px solid rgba(59,130,246,.25);white-space:nowrap;
}}
.status-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.dot-mapped{{background:var(--ok)}}
.dot-unmapped{{background:var(--err)}}

/* ── By System ── */
.sys-group{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);
  margin-bottom:10px;overflow:hidden;
}}
.sys-group-header{{
  display:flex;align-items:center;gap:10px;padding:10px 18px;
  background:var(--raised);border-bottom:1px solid var(--b0);
  font-size:.85rem;font-weight:700;color:var(--tp);
  cursor:pointer;user-select:none;
}}
.sys-group-header:hover{{background:var(--hover)}}
.sys-body{{padding:10px 18px;display:grid;gap:6px}}
.sys-signal-row{{
  display:grid;grid-template-columns:auto auto 1fr auto auto auto;
  align-items:center;gap:10px;padding:6px 10px;border-radius:var(--r);
  background:var(--raised);border:1px solid var(--b0);
}}
.sys-signal-row:hover{{background:var(--hover)}}
.comp-badge{{
  display:inline-flex;align-items:center;padding:2px 8px;border-radius:4px;
  font-size:10px;font-weight:700;background:rgba(139,92,246,.12);color:#c4b5fd;
  border:1px solid rgba(139,92,246,.25);white-space:nowrap;
}}
.ecu-route{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--ts)}}

/* ── Table tab ── */
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{
  position:sticky;top:0;background:var(--raised);z-index:1;
  padding:8px 12px;text-align:left;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;color:var(--tm);
  border-bottom:1px solid var(--b1);cursor:pointer;white-space:nowrap;
}}
th:hover{{background:var(--active);color:var(--ts)}}
td{{padding:8px 12px;border-bottom:1px solid var(--b0);vertical-align:top;color:var(--ts)}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.025);color:var(--tp)}}
.tbl-wrap{{overflow:auto;max-height:72vh;border-radius:10px;border:1px solid var(--b0)}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:11px}}

/* ── pills ── */
.iface-pill{{
  display:inline-flex;align-items:center;padding:2px 8px;border-radius:20px;
  font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;
  white-space:nowrap;flex-shrink:0;
}}

/* ── scrollbar ── */
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--b1);border-radius:2px}}
</style>
</head>
<body>
<header class="topbar">
  <span class="topbar-title">Signal Flow v2</span>
  <div class="topbar-kpis" id="kpi-bar"></div>
  <div class="tabs">
    <button class="tab active" onclick="switchTab('ecu')">By ECU</button>
    <button class="tab" onclick="switchTab('sys')">By System</button>
    <button class="tab" onclick="switchTab('tbl')">Table</button>
  </div>
</header>
<div class="app-body">
  <div class="filterbar" id="filterbar">
    <label>Interface</label>
    <div id="iface-pills" style="display:flex;gap:4px;flex-wrap:wrap"></div>
    <div style="width:1px;background:var(--b1);height:20px;margin:0 4px"></div>
    <label>ECU</label>
    <input class="search" id="ecu-filter" placeholder="Filter ECU…" style="min-width:140px;max-width:180px" oninput="applyFilters()"/>
    <input class="search" id="global-search" placeholder="Search signals…" style="min-width:200px" oninput="applyFilters()"/>
    <span id="row-count" style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm)"></span>
  </div>
  <div id="panel-ecu" class="tab-panel active"></div>
  <div id="panel-sys" class="tab-panel"></div>
  <div id="panel-tbl" class="tab-panel">
    <div class="tbl-wrap" id="tbl-wrap">
      <table id="main-table">
        <thead><tr id="tbl-head"></tr></thead>
        <tbody id="tbl-body"></tbody>
      </table>
    </div>
  </div>
</div>
<script>
var DATA = {data_json};

var IFACE_COLORS = {{
  ANALOG:'#f59e0b',DIGITAL:'#10b981',CAN:'#22d3ee',PWM:'#f97316',
  FREQ:'#8b5cf6',POWER:'#34d399',GROUND:'#6b7280',RESISTANCE:'#64748b',
  LIN:'#a78bfa'
}};
function ifaceColor(i){{return IFACE_COLORS[i.toUpperCase()]||'#94a3b8';}}
function ifacePill(i){{
  var c=ifaceColor(i);
  return '<span class="iface-pill" style="background:'+c+'22;color:'+c+';border:1px solid '+c+'44">'+esc(i)+'</span>';
}}
function esc(s){{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}
function statusDot(s){{
  return '<span class="status-dot '+(s==='MAPPED'?'dot-mapped':'dot-unmapped')+'" title="'+esc(s)+'"></span>';
}}

/* ── state ── */
var activeIfaces = new Set();
var allIfaces = [];
var currentTab = 'ecu';

/* ── tabs ── */
function switchTab(t){{
  currentTab = t;
  document.querySelectorAll('.tab-panel').forEach(function(p){{p.classList.remove('active');}});
  document.querySelectorAll('.tab').forEach(function(b,i){{b.classList.remove('active');}});
  document.getElementById('panel-'+t).classList.add('active');
  var tabs = document.querySelectorAll('.tab');
  var idx = {{ecu:0,sys:1,tbl:2}}[t];
  tabs[idx].classList.add('active');
  applyFilters();
}}

/* ── KPIs ── */
function buildKPIs(rows){{
  var ecus = new Set(), syss = new Set(), mapped=0, unmapped=0;
  rows.forEach(function(r){{
    if(r.ecu) ecus.add(r.ecu);
    if(r.system) syss.add(r.system);
    if(r.status==='MAPPED') mapped++; else unmapped++;
  }});
  var bar = document.getElementById('kpi-bar');
  bar.innerHTML = [
    [ecus.size,'ECUs'],
    [syss.size,'Systems'],
    [mapped,'Mapped'],
    [unmapped,'Unmapped'],
  ].map(function(x){{
    return '<div class="kpi-chip"><span class="kv">'+x[0]+'</span><span class="kl">'+x[1]+'</span></div>';
  }}).join('');
}}

/* ── interface pills filter ── */
function buildIfacePills(rows){{
  var set = new Set();
  rows.forEach(function(r){{if(r.interface) set.add(r.interface.toUpperCase());}});
  allIfaces = Array.from(set).sort();
  allIfaces.forEach(function(i){{activeIfaces.add(i);}});
  var c = document.getElementById('iface-pills');
  c.innerHTML = allIfaces.map(function(i){{
    var col = ifaceColor(i);
    return '<button class="pill-btn on" id="pill-'+i+'" style="background:'+col+'22;color:'+col+';border-color:'+col+'44" onclick="toggleIface(\''+i+'\')">'
      +esc(i)+'</button>';
  }}).join('');
}}
function toggleIface(i){{
  if(activeIfaces.has(i)) activeIfaces.delete(i); else activeIfaces.add(i);
  var btn = document.getElementById('pill-'+i);
  var col = ifaceColor(i);
  if(activeIfaces.has(i)){{
    btn.classList.add('on');
    btn.style.background=col+'22'; btn.style.color=col; btn.style.borderColor=col+'44';
  }} else {{
    btn.classList.remove('on');
    btn.style.background=''; btn.style.color=''; btn.style.borderColor='';
  }}
  applyFilters();
}}

/* ── filtering ── */
function rowVisible(r){{
  var iface = (r.interface||'').toUpperCase();
  if(iface && allIfaces.length && !activeIfaces.has(iface)) return false;
  var ecuF = (document.getElementById('ecu-filter').value||'').toLowerCase();
  if(ecuF && !(r.ecu||'').toLowerCase().includes(ecuF)) return false;
  var q = (document.getElementById('global-search').value||'').toLowerCase();
  if(q){{
    var haystack = [r.system,r.component,r.device,r.device_pin,r.signal,r.interface,r.ecu,r.ecu_connector,r.ecu_pin,r.status].join(' ').toLowerCase();
    if(!haystack.includes(q)) return false;
  }}
  return true;
}}

function applyFilters(){{
  var rows = DATA.rows.filter(rowVisible);
  document.getElementById('row-count').textContent = rows.length+' / '+DATA.rows.length+' signals';
  if(currentTab==='ecu') buildECUTab(rows);
  if(currentTab==='sys') buildSysTab(rows);
  if(currentTab==='tbl') filterTable(rows);
}}

/* ── By ECU tab ── */
function buildECUTab(rows){{
  var groups = {{}};
  rows.forEach(function(r){{
    var key = r.ecu||'__UNASSIGNED__';
    if(!groups[key]) groups[key]=[];
    groups[key].push(r);
  }});
  var keys = Object.keys(groups).filter(function(k){{return k!=='__UNASSIGNED__';}}).sort();
  if(groups['__UNASSIGNED__']) keys.push('__UNASSIGNED__');

  var html = keys.map(function(key){{
    var items = groups[key];
    var label = key==='__UNASSIGNED__'?'UNASSIGNED':key;
    var nameHtml = key==='__UNASSIGNED__'
      ? '<span class="ecu-name" style="color:var(--tm)">UNASSIGNED</span>'
      : '<span class="ecu-name">'+esc(label)+'</span>';
    var rows_html = items.map(function(r){{
      return '<div class="signal-row">'
        +ifacePill(r.interface||'—')
        +'<span class="sig-name">'+esc(r.signal)+'</span>'
        +'<span class="sig-device">'+esc(r.device)+'</span>'
        +'<span class="sig-pin">'+esc(r.device_pin)+'</span>'
        +(r.system?'<span class="sys-badge">'+esc(r.system)+'</span>':'<span></span>')
        +statusDot(r.status)
        +'</div>';
    }}).join('');
    return '<div class="ecu-group" id="egrp-'+esc(key)+'">'
      +'<div class="ecu-group-header" onclick="toggleECUGroup(\'egrp-'+esc(key)+'\')">'
      +nameHtml
      +'<span class="ecu-count">'+items.length+'</span>'
      +'<span class="ecu-chevron">&#9660;</span>'
      +'</div>'
      +'<div class="ecu-body">'+rows_html+'</div>'
      +'</div>';
  }}).join('');
  document.getElementById('panel-ecu').innerHTML = html||'<div style="color:var(--tm);padding:24px;text-align:center">No signals match current filters.</div>';
}}
function toggleECUGroup(id){{
  document.getElementById(id).classList.toggle('collapsed');
}}

/* ── By System tab ── */
function buildSysTab(rows){{
  var groups = {{}};
  rows.forEach(function(r){{
    var key = r.system||'(no system)';
    if(!groups[key]) groups[key]=[];
    groups[key].push(r);
  }});
  var keys = Object.keys(groups).sort();
  var html = keys.map(function(sys){{
    var items = groups[sys];
    var rows_html = items.map(function(r){{
      var route = [r.ecu,r.ecu_connector,r.ecu_pin].filter(Boolean).join(':');
      return '<div class="sys-signal-row">'
        +(r.component?'<span class="comp-badge">'+esc(r.component)+'</span>':'<span></span>')
        +'<span style="font-size:11px;color:var(--ts)">'+esc(r.device)+'</span>'
        +ifacePill(r.interface||'—')
        +'<span class="sig-name">'+esc(r.signal)+'</span>'
        +(route?'<span class="ecu-route">&#8594; '+esc(route)+'</span>':'<span></span>')
        +statusDot(r.status)
        +'</div>';
    }}).join('');
    return '<div class="sys-group">'
      +'<div class="sys-group-header">'+esc(sys)+'<span style="margin-left:8px;font-size:10px;font-weight:400;color:var(--tm)">'+items.length+' signals</span></div>'
      +'<div class="sys-body">'+rows_html+'</div>'
      +'</div>';
  }}).join('');
  document.getElementById('panel-sys').innerHTML = html||'<div style="color:var(--tm);padding:24px;text-align:center">No signals match current filters.</div>';
}}

/* ── Table tab ── */
var COL_KEYS  = ['system','component','device','device_pin','signal','interface','role','ecu','ecu_connector','ecu_pin','ecu_role','status'];
var COL_HEADS = ['System','Component','Device','Device Pin','Signal/Net','Interface','Device Role','ECU','ECU Connector','ECU Pin','ECU Role','Status'];
var sortCol=-1, sortAsc=true;

function buildTableHeader(){{
  var tr = document.getElementById('tbl-head');
  tr.innerHTML = COL_HEADS.map(function(h,i){{
    return '<th onclick="sortTable('+i+')">'+esc(h)+'</th>';
  }}).join('');
}}
function filterTable(rows){{
  var tbody = document.getElementById('tbl-body');
  if(sortCol>=0){{
    var k=COL_KEYS[sortCol];
    rows = rows.slice().sort(function(a,b){{
      var A=String(a[k]||''),B=String(b[k]||'');
      var x=parseFloat(A),y=parseFloat(B);
      if(!isNaN(x)&&!isNaN(y)) return sortAsc?x-y:y-x;
      return sortAsc?A.localeCompare(B):B.localeCompare(A);
    }});
  }}
  tbody.innerHTML = rows.map(function(r){{
    return '<tr>'+COL_KEYS.map(function(k){{
      if(k==='interface') return '<td>'+ifacePill(r[k]||'')+'</td>';
      if(k==='status') return '<td>'+statusDot(r[k])+'<span style="margin-left:5px;font-size:10px">'+esc(r[k])+'</span></td>';
      if(k==='signal') return '<td class="mono">'+esc(r[k]||'')+'</td>';
      return '<td>'+esc(r[k]||'')+'</td>';
    }}).join('')+'</tr>';
  }}).join('');
}}
function sortTable(i){{
  if(sortCol===i) sortAsc=!sortAsc; else{{sortCol=i;sortAsc=true;}}
  applyFilters();
}}

/* ── init ── */
(function(){{
  var rows = DATA.rows;
  buildKPIs(rows);
  buildIfacePills(rows);
  buildTableHeader();
  applyFilters();
}})();
</script>
</body></html>"""

    out = get_output_file(root, cfg, 'signal_flow_v2', args.output, args.outdir)
    write_text(out, html)
    print(out)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

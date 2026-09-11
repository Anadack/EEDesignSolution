#!/usr/bin/env python3
"""Generate a professional, interactive Architecture Object Tree HTML report."""
from __future__ import annotations
import json
import datetime
from pathlib import Path
from eec_report_common import (
    standard_arg_parser, load_config, resolve_root,
    load_architecture_from_args, get_output_file, write_text,
    iter_devices, iter_device_pin_records, signal_name, normalize_token, esc,
)

IFACE_COLORS = {
    "ANALOG": "#f59e0b", "DIGITAL": "#3b82f6", "PWM": "#8b5cf6",
    "CAN": "#06b6d4", "FREQ": "#ec4899", "POWER": "#dc2626",
    "GROUND": "#6b7280", "RESISTANCE": "#14b8a6",
}
DEFAULT_IFACE_COLOR = "#94a3b8"

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
:root{
  --bg:#0d0f14;--card:#131720;--border:rgba(255,255,255,.10);--shadow:0 4px 24px rgba(0,0,0,.4);
  --ha:#0f172a;--hb:#1e3a5f;--text:#e8ecf4;--muted:#8993a8;
  --sensor:#0d9488;--actuator:#d97706;--ecu:#6366f1;
  --r:12px;--rs:7px;--tr:170ms cubic-bezier(.4,0,.2,1);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Inter','Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.5;min-height:100vh}
::-webkit-scrollbar{width:4px;height:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:2px}
.site-header{background:linear-gradient(135deg,var(--ha),var(--hb));color:#fff;padding:38px 32px 34px;position:relative;overflow:hidden}
.site-header::before{content:"";position:absolute;inset:0;background:radial-gradient(ellipse at 75% 40%,rgba(99,102,241,.2),transparent 60%)}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(148,163,184,.85);margin-bottom:10px}
h1{font-size:clamp(1.6rem,3.5vw,2.6rem);font-weight:900;letter-spacing:-.03em;line-height:1.1}
.subtitle{margin-top:8px;font-size:14px;color:rgba(148,163,184,.8)}
.generated{margin-top:12px;font-size:11px;color:rgba(100,116,139,.65)}
.kpi-strip{display:flex;gap:10px;flex-wrap:wrap;padding:0 32px;margin-top:-22px;margin-bottom:4px;position:relative;z-index:10}
.kpi-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--r);padding:13px 18px;box-shadow:0 4px 24px rgba(0,0,0,.4);min-width:120px;flex:1;max-width:200px}
.kpi-val{font-size:2rem;font-weight:900;letter-spacing:-.04em;line-height:1}
.kpi-lbl{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:4px}
.filter-bar{position:sticky;top:0;z-index:100;background:rgba(13,15,20,.95);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.06);padding:11px 32px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.filter-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.filter-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);white-space:nowrap}
.fb{border:1px solid rgba(255,255,255,.10);border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer;background:#1a1f2e;color:#8993a8;transition:all var(--tr);white-space:nowrap;font-family:inherit}
.fb:hover{border-color:rgba(255,255,255,.20);color:#e8ecf4}.fb.active{color:#fff!important;border-color:transparent!important}
.search-box{margin-left:auto;display:flex;align-items:center;gap:6px}
.search-input{border:1px solid rgba(255,255,255,.10);border-radius:var(--rs);padding:5px 12px;font-size:13px;font-family:inherit;background:#1a1f2e;color:#e8ecf4;outline:none;width:220px;transition:border-color var(--tr)}
.search-input:focus{border-color:#3b82f6}
.fb-reset{border:1px solid rgba(255,255,255,.10);border-radius:var(--rs);padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;background:#1a1f2e;color:#8993a8;transition:all var(--tr);font-family:inherit}
.fb-reset:hover{background:#1f2538;color:#e8ecf4}
.layout{display:flex;min-height:calc(100vh - 250px)}
.sidebar{width:270px;flex-shrink:0;background:#131720;border-right:1px solid rgba(255,255,255,.06);position:sticky;top:57px;height:calc(100vh - 57px);overflow-y:auto;padding:16px 0}
.sb-section-hdr{display:flex;align-items:center;gap:8px;padding:8px 16px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);cursor:pointer;user-select:none;transition:background var(--tr)}
.sb-section-hdr:hover{background:rgba(255,255,255,.03)}.sb-arrow{font-size:10px;margin-left:auto;transition:transform var(--tr)}.sb-section-hdr.open .sb-arrow{transform:rotate(90deg)}
.sb-items{display:none}.sb-section-hdr.open+.sb-items{display:block}
.sb-item{display:flex;align-items:center;gap:7px;padding:6px 16px 6px 28px;font-size:12px;cursor:pointer;color:var(--text);transition:background var(--tr);border-left:3px solid transparent}
.sb-item:hover{background:#1f2538}.sb-item.active{background:rgba(59,130,246,.12);border-left-color:#3b82f6;color:#60a5fa;font-weight:600}
.sb-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.main{flex:1;padding:24px 28px 40px;min-width:0}
.section-hdr{display:flex;align-items:center;gap:10px;margin:24px 0 14px;padding-bottom:10px;border-bottom:2px solid rgba(255,255,255,.10)}
.section-hdr h2{font-size:1.1rem;font-weight:800;letter-spacing:-.01em;color:#e8ecf4}
.section-count{background:#1a1f2e;color:#e8ecf4;border-radius:999px;padding:2px 10px;font-size:11px;font-weight:700;border:1px solid rgba(255,255,255,.10)}
.system-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--r);box-shadow:0 4px 24px rgba(0,0,0,.4);margin-bottom:14px;overflow:hidden}
.system-card-hdr{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:14px 18px;cursor:pointer;user-select:none;background:rgba(255,255,255,.02);border-bottom:1px solid transparent;transition:background var(--tr)}
.system-card-hdr:hover{background:rgba(255,255,255,.04)}
.system-card.open .system-card-hdr{border-bottom-color:rgba(255,255,255,.10)}
.sys-toggle{font-size:12px;color:var(--muted);transition:transform var(--tr);flex-shrink:0}
.system-card.open .sys-toggle{transform:rotate(90deg)}
.sys-name{font-size:15px;font-weight:800;letter-spacing:-.01em;flex:1;color:#e8ecf4}
.system-body{display:none;padding:12px}.system-card.open .system-body{display:block}
.comp-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:6px 10px;background:rgba(255,255,255,.04);border-radius:var(--rs);margin-bottom:6px;margin-top:6px;display:flex;align-items:center;gap:6px}
.device-card{border:1px solid rgba(255,255,255,.08);border-radius:var(--rs);margin-bottom:6px;overflow:hidden;background:#1a1f2e;transition:box-shadow var(--tr)}
.device-card:hover{box-shadow:0 2px 12px rgba(0,0,0,.4)}
.device-card.sensor{border-left:3px solid var(--sensor)}.device-card.actuator{border-left:3px solid var(--actuator)}
.device-card-hdr{display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;user-select:none}
.device-card-hdr:hover{background:rgba(255,255,255,.03)}
.dev-toggle{font-size:10px;color:var(--muted);transition:transform var(--tr);flex-shrink:0}
.device-card.open .dev-toggle{transform:rotate(90deg)}
.dev-name{font-size:12px;font-weight:700;flex:1;color:#e8ecf4}
.dev-pin-count{font-size:11px;font-weight:600;color:#8993a8;background:rgba(255,255,255,.06);border-radius:999px;padding:2px 8px;flex-shrink:0}
.device-body{display:none;padding:0 10px 8px}.device-card.open .device-body{display:block}
.pin-table{width:100%;border-collapse:collapse;font-size:11px}
.pin-table th{text-align:left;padding:4px 8px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#5a6278;border-bottom:1px solid rgba(255,255,255,.08);background:#1a1f2e}
.pin-table td{padding:4px 8px;border-bottom:1px solid rgba(255,255,255,.04);font-family:'JetBrains Mono',monospace;color:#8993a8}
.pin-table tr:last-child td{border-bottom:none}.pin-table tr:hover td{background:rgba(255,255,255,.03)}
.pin-row.hidden{display:none}
.iface-pill{display:inline-flex;border-radius:999px;padding:1px 7px;font-size:10px;font-weight:700;color:#fff;white-space:nowrap}
.pin-sig{font-weight:600;color:#e8ecf4}
.badge{display:inline-flex;border-radius:4px;padding:1px 5px;font-size:10px;font-weight:700;border:1px solid;white-space:nowrap}
.ecu-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--r);border-left:4px solid #6366f1;margin-bottom:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.3)}
.ecu-card-hdr{display:flex;align-items:center;gap:10px;padding:12px 16px;cursor:pointer;user-select:none}
.ecu-card-hdr:hover{background:rgba(255,255,255,.03)}
.ecu-toggle{font-size:11px;color:var(--muted);transition:transform var(--tr)}
.ecu-card.open .ecu-toggle{transform:rotate(90deg)}
.ecu-name{font-size:13px;font-weight:800;letter-spacing:-.01em;flex:1;color:#e8ecf4}
.ecu-body{display:none;padding:0 14px 10px}.ecu-card.open .ecu-body{display:block}
.card-hidden{display:none}
.empty{padding:30px;text-align:center;color:#5a6278;font-size:12px;font-style:italic}
.site-footer{text-align:center;padding:20px 32px;color:#5a6278;font-size:12px;border-top:1px solid rgba(255,255,255,.06)}
@media(max-width:860px){.layout{flex-direction:column}.sidebar{width:100%;height:auto;position:static;border-right:none;border-bottom:1px solid rgba(255,255,255,.06)}.kpi-strip,.filter-bar,.main{padding-left:16px;padding-right:16px}.site-header{padding:26px 16px 22px}}
"""

_JS = r"""
(function(){
var D=__DATA__;
function ic(k){return D.iface_colors[k]||D.default_iface_color}
function sc(k){var m={QM:'#22c55e',AGPL_A:'#84cc16',AGPL_B:'#eab308',AGPL_C:'#f97316',AGPL_D:'#ef4444'};return m[k]||'#64748b'}
var flt={kind:new Set(),safety:new Set(),q:''};
function matches(row){
  var q=flt.q.toLowerCase();
  if(q&&row.dataset.search.toLowerCase().indexOf(q)===-1)return false;
  if(flt.kind.size&&!flt.kind.has(row.dataset.kind))return false;
  if(flt.safety.size&&!flt.safety.has(row.dataset.safety))return false;
  return true;
}
function applyFilters(){
  document.querySelectorAll('.pin-row').forEach(function(r){r.classList.toggle('hidden',!matches(r));});
  document.querySelectorAll('.ecu-pin-row').forEach(function(r){r.classList.toggle('hidden',!matches(r));});
  document.querySelectorAll('.device-card').forEach(function(card){
    var rows=card.querySelectorAll('.pin-row');
    var vis=0;rows.forEach(function(r){if(!r.classList.contains('hidden'))vis++;});
    card.classList.toggle('card-hidden',rows.length>0&&vis===0);
    var cnt=card.querySelector('.dev-pin-count');if(cnt)cnt.textContent=vis+'/'+rows.length+' pins';
  });
  document.querySelectorAll('.system-card').forEach(function(card){
    var vis=card.querySelectorAll('.device-card:not(.card-hidden)').length;
    card.classList.toggle('card-hidden',vis===0);
  });
  document.querySelectorAll('.ecu-card').forEach(function(card){
    var rows=card.querySelectorAll('.ecu-pin-row');
    var vis=0;rows.forEach(function(r){if(!r.classList.contains('hidden'))vis++;});
    card.classList.toggle('card-hidden',rows.length>0&&vis===0);
  });
}
function tog(btn,cat,val,colorFn){
  if(flt[cat].has(val)){flt[cat].delete(val);btn.classList.remove('active');btn.style.cssText='';}
  else{flt[cat].add(val);btn.classList.add('active');var c=colorFn(val);btn.style.background=c;btn.style.borderColor=c;btn.style.color='#fff';}
  applyFilters();
}
function el(tag,cls,html){var e=document.createElement(tag);if(cls)e.className=cls;if(html!==undefined)e.innerHTML=html;return e;}
function buildFilterBar(){
  var bar=document.getElementById('filter-bar');
  function grp(label,items,cat,colorFn){
    var g=el('div','filter-group');
    g.appendChild(el('span','filter-label',label+':'));
    var all=el('button','fb active','ALL');
    all.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';
    all.addEventListener('click',function(){flt[cat].clear();g.querySelectorAll('.fb:not(.fb-all)').forEach(function(b){b.classList.remove('active');b.style.cssText='';});all.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';applyFilters();});
    all.classList.add('fb-all');g.appendChild(all);
    items.forEach(function(v){
      var b=el('button','fb',v);
      b.addEventListener('click',function(){all.style.cssText='';tog(b,cat,v,colorFn);if(flt[cat].size===0){all.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';}});
      g.appendChild(b);
    });
    return g;
  }
  var kc={SENSOR:'#0d9488',ACTUATOR:'#d97706',DEVICE:'#6366f1'};
  bar.appendChild(grp('Kind',D.kind_list,'kind',function(k){return kc[k]||'#64748b'}));
  bar.appendChild(grp('Safety',D.safety_list,'safety',sc));
  var sb=el('div','search-box');
  var si=el('input','search-input');si.type='text';si.placeholder='Search signals, pins, ECUs…';
  si.addEventListener('input',function(){flt.q=si.value;applyFilters();});
  sb.appendChild(si);bar.appendChild(sb);
  var rst=el('button','fb-reset','Reset');
  rst.addEventListener('click',function(){flt.kind.clear();flt.safety.clear();flt.q='';si.value='';bar.querySelectorAll('.fb').forEach(function(b){b.classList.remove('active');b.style.cssText='';});bar.querySelectorAll('.fb-all').forEach(function(b){b.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';});applyFilters();});
  bar.appendChild(rst);
}
function pill(iface){return '<span class="iface-pill" style="background:'+ic(iface)+'">'+iface+'</span>';}
function safeBadge(s){if(!s)return '';var c=sc(s);return '<span class="badge" style="color:'+c+';border-color:'+c+'44;background:'+c+'16">'+s+'</span>';}
function esc2(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function buildPinRow(p){
  var row=el('tr','pin-row');
  row.dataset.kind=p.kind||'DEVICE';row.dataset.safety=p.safety||'';
  row.dataset.search=[p.name,p.signal,p.interface,p.role,p.connector].join(' ');
  row.innerHTML='<td>'+esc2(p.connector)+'</td><td>'+esc2(p.number)+'</td><td class="pin-sig">'+esc2(p.name)+'</td><td>'+pill(p.interface)+'</td><td>'+esc2(p.signal)+'</td><td>'+esc2(p.role)+'</td>'+(p.safety?'<td>'+safeBadge(p.safety)+'</td>':'<td></td>');
  return row;
}
function buildDeviceCard(dev,kind){
  var cls='device-card '+(kind==='SENSOR'?'sensor':kind==='ACTUATOR'?'actuator':'');
  var card=el('div',cls.trim());
  var hdr=el('div','device-card-hdr','<span class="dev-toggle">&#9658;</span><span class="dev-name">'+esc2(dev.name)+'</span><span class="dev-pin-count">'+dev.pins.length+' pins</span>');
  hdr.addEventListener('click',function(){card.classList.toggle('open');});
  card.appendChild(hdr);
  var body=el('div','device-body');
  var tbl=el('table','pin-table','<thead><tr><th>Conn.</th><th>#</th><th>Pin</th><th>Interface</th><th>Signal</th><th>Role</th><th>Safety</th></tr></thead>');
  var tbody=document.createElement('tbody');
  if(!dev.pins.length){var r=el('tr');r.innerHTML='<td colspan="7" class="empty">No pin records</td>';tbody.appendChild(r);}
  else{dev.pins.forEach(function(p){tbody.appendChild(buildPinRow(p));});}
  tbl.appendChild(tbody);body.appendChild(tbl);card.appendChild(body);
  return card;
}
function buildSystemCard(sys){
  var card=el('div','system-card');
  var safety=sys.safety?safeBadge(sys.safety):'';
  var slBadge=sys.sl?'<span class="badge" style="background:#f1f5f9;color:#475569;border-color:#e2e8f0">'+esc2(sys.sl)+'</span>':'';
  var hdr=el('div','system-card-hdr','<span class="sys-toggle">&#9658;</span><span class="sys-name">'+esc2(sys.name)+'</span>'+safety+slBadge);
  hdr.addEventListener('click',function(){card.classList.toggle('open');});
  card.appendChild(hdr);
  var body=el('div','system-body');
  sys.devices.forEach(function(dg){
    if(dg.comp_name){body.appendChild(el('div','comp-label','&#128279; '+esc2(dg.comp_name)));}
    dg.devices.forEach(function(d){body.appendChild(buildDeviceCard(d,dg.kind));});
  });
  card.appendChild(body);
  return card;
}
function buildEcuCard(ecu){
  var card=el('div','ecu-card');
  var varBadge=ecu.variant?'<span class="badge" style="background:#eef2ff;color:#4338ca;border-color:#c7d2fe">'+esc2(ecu.variant)+'</span>':'';
  var hdr=el('div','ecu-card-hdr','<span class="ecu-toggle">&#9658;</span><span class="ecu-name">'+esc2(ecu.name)+'</span>'+varBadge+'<span style="font-size:11px;color:#64748b">'+ecu.pins.length+' pins</span>');
  hdr.addEventListener('click',function(){card.classList.toggle('open');});
  card.appendChild(hdr);
  var body=el('div','ecu-body');
  var tbl=el('table','pin-table','<thead><tr><th>Connector</th><th>Pin</th><th>Name</th><th>Interface</th><th>Signal</th><th>Role</th></tr></thead>');
  var tbody=document.createElement('tbody');
  ecu.pins.forEach(function(p){
    var row=el('tr','ecu-pin-row');row.dataset.kind='ECU';row.dataset.safety='';
    row.dataset.search=[p.connector,p.number,p.name,p.signal,p.role].join(' ');
    row.innerHTML='<td>'+esc2(p.connector)+'</td><td>'+esc2(p.number)+'</td><td class="pin-sig">'+esc2(p.name)+'</td><td>'+pill(p.interface)+'</td><td>'+esc2(p.signal)+'</td><td>'+esc2(p.role)+'</td>';
    tbody.appendChild(row);
  });
  tbl.appendChild(tbody);body.appendChild(tbl);card.appendChild(body);
  return card;
}
function buildSidebar(){
  var sb=document.getElementById('sidebar');
  function section(label,items,colorFn){
    var hdr=el('div','sb-section-hdr open',label+' <span class="sb-arrow">&#9658;</span>');
    sb.appendChild(hdr);
    var list=el('div','sb-items');
    items.forEach(function(item){
      var it=el('div','sb-item');
      var dot=el('span','sb-dot');dot.style.background=colorFn(item.kind);it.appendChild(dot);
      it.appendChild(document.createTextNode(item.label));
      it.addEventListener('click',function(){
        var t=document.getElementById('anchor-'+item.id);
        if(t)t.scrollIntoView({behavior:'smooth',block:'start'});
        document.querySelectorAll('.sb-item').forEach(function(x){x.classList.remove('active');});it.classList.add('active');
      });
      list.appendChild(it);
    });
    sb.appendChild(list);
    hdr.addEventListener('click',function(){hdr.classList.toggle('open');});
  }
  var kc={SENSOR:'#0d9488',ACTUATOR:'#d97706',DEVICE:'#64748b',ECU:'#6366f1'};
  section('Systems',D.sidebar_systems,function(k){return kc[k]||'#94a3b8';});
  section('ECUs',D.sidebar_ecus,function(){return kc.ECU;});
}
function render(){
  buildFilterBar();buildSidebar();
  var sysSection=document.getElementById('systems-section');
  D.systems.forEach(function(sys){
    var a=document.createElement('div');a.id='anchor-sys-'+sys.id;sysSection.appendChild(a);
    sysSection.appendChild(buildSystemCard(sys));
  });
  document.getElementById('sys-count').textContent=D.systems.length;
  var ecuSection=document.getElementById('ecus-section');
  D.ecus.forEach(function(ecu){
    var a=document.createElement('div');a.id='anchor-ecu-'+ecu.id;ecuSection.appendChild(a);
    ecuSection.appendChild(buildEcuCard(ecu));
  });
  document.getElementById('ecu-count').textContent=D.ecus.length;
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',render);}else{render();}
})();
"""

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>__CSS__</style>
</head>
<body>
<header class="site-header">
  <div class="eyebrow">E/E Architecture Design &mdash; Agricultural Machinery</div>
  <h1>Architecture Object Tree</h1>
  <div class="subtitle">__SUBTITLE__</div>
  <div class="generated">Generated __GEN__ &bull; Source: __SRC__</div>
</header>
<div class="kpi-strip">__KPIS__</div>
<div id="filter-bar" class="filter-bar"></div>
<div class="layout">
  <nav id="sidebar" class="sidebar"></nav>
  <main class="main">
    <div class="section-hdr"><h2>Systems</h2><span id="sys-count" class="section-count">0</span></div>
    <div id="systems-section"></div>
    <div class="section-hdr" style="margin-top:36px"><h2>ECUs</h2><span id="ecu-count" class="section-count">0</span></div>
    <div id="ecus-section"></div>
  </main>
</div>
<footer class="site-footer">E/E Architect Design &mdash; Architecture Object Tree &bull; __GEN__</footer>
<script>__JS__</script>
</body>
</html>"""


def _kpi(val: int, label: str, color: str) -> str:
    return (f'<div class="kpi-card"><div class="kpi-val" style="color:{color}">{val}</div>'
            f'<div class="kpi-lbl">{label}</div></div>')


def _build_data(arch: dict) -> dict:
    systems_out, all_kinds, all_safety = [], set(), set()
    total_devices = total_pins = 0

    for sys in (arch.get("systems") or []):
        if not isinstance(sys, dict):
            continue
        sys_name = str(sys.get("name") or "System")
        sys_safety = normalize_token(sys.get("safety") or "")
        sys_sl = str(sys.get("system_level") or sys.get("sl") or "")
        if sys_safety:
            all_safety.add(sys_safety)

        device_groups: list[dict] = []
        prev_comp = object()
        current_group: dict | None = None

        for comp, dev, kind in iter_devices(sys):
            comp_name = str(comp.get("name") or "") if isinstance(comp, dict) else ""
            if comp is not prev_comp:
                current_group = {"comp_name": comp_name, "kind": kind, "devices": []}
                device_groups.append(current_group)
                prev_comp = comp

            pins_out = []
            for rec in iter_device_pin_records(dev):
                sig = rec.get("signal") or {}
                sig_safety = normalize_token((sig.get("safety") if isinstance(sig, dict) else "") or sys_safety)
                iface = normalize_token(rec.get("interface") or "")
                all_kinds.add(kind)
                if sig_safety:
                    all_safety.add(sig_safety)
                pins_out.append({
                    "connector": str(rec.get("connector") or ""),
                    "number": str(rec.get("number") or ""),
                    "name": str(rec.get("name") or ""),
                    "interface": iface,
                    "signal": signal_name(sig) or str(rec.get("name") or ""),
                    "role": str(rec.get("role") or ""),
                    "safety": sig_safety,
                    "kind": kind,
                })
                total_pins += 1

            if current_group is not None:
                current_group["devices"].append({
                    "name": str(dev.get("name") or "Device"),
                    "pins": pins_out,
                })
                total_devices += 1

        systems_out.append({
            "id": normalize_token(sys_name).replace(" ", "_"),
            "name": sys_name,
            "safety": sys_safety,
            "sl": sys_sl,
            "devices": device_groups,
        })

    ecus_out = []
    for ecu in (arch.get("ecus") or []):
        if not isinstance(ecu, dict):
            continue
        ecu_name = str(ecu.get("name") or "ECU")
        ecu_pins = []
        for pin in (ecu.get("pins") or []):
            if not isinstance(pin, dict):
                continue
            sig = pin.get("signal") or {}
            iface = normalize_token((sig.get("interface") if isinstance(sig, dict) else "") or str(pin.get("type") or ""))
            ecu_pins.append({
                "connector": str(pin.get("connector") or ""),
                "number": str(pin.get("physical_number") or pin.get("number") or ""),
                "name": str(pin.get("name") or ""),
                "interface": iface,
                "signal": signal_name(sig) or str(pin.get("signal_name") or ""),
                "role": str(pin.get("role") or ""),
            })
        ecus_out.append({
            "id": normalize_token(ecu_name).replace(" ", "_"),
            "name": ecu_name,
            "variant": str(ecu.get("variant") or ""),
            "pins": ecu_pins,
        })

    _SAFETY_ORDER = ["QM", "AGPL_A", "AGPL_B", "AGPL_C", "AGPL_D"]
    safety_list = [s for s in _SAFETY_ORDER if s in all_safety] + sorted(s for s in all_safety if s not in _SAFETY_ORDER)

    return {
        "arch_name": str(arch.get("name") or "Architecture"),
        "systems": systems_out,
        "ecus": ecus_out,
        "kind_list": sorted(all_kinds),
        "safety_list": safety_list,
        "iface_colors": IFACE_COLORS,
        "default_iface_color": DEFAULT_IFACE_COLOR,
        "sidebar_systems": [{"id": "sys-" + s["id"], "label": s["name"], "kind": "SENSOR"} for s in systems_out],
        "sidebar_ecus": [{"id": "ecu-" + e["id"], "label": e["name"], "kind": "ECU"} for e in ecus_out],
        "kpi": {
            "systems": len(systems_out),
            "ecus": len(ecus_out),
            "devices": total_devices,
            "pins": total_pins,
        },
    }


def main() -> int:
    parser = standard_arg_parser("Generate professional Architecture Object Tree HTML report.")
    args = parser.parse_args()
    cfg = load_config(Path(args.config) if args.config else None)
    root = resolve_root(args.root)

    src, arch = load_architecture_from_args(args, cfg, physical=False)
    try:
        src_label = str(src.relative_to(root))
    except ValueError:
        src_label = str(src)

    data = _build_data(arch)
    kpi = data["kpi"]
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    kpis = (
        _kpi(kpi["systems"], "Systems", "#3b82f6") +
        _kpi(kpi["ecus"], "ECUs", "#6366f1") +
        _kpi(kpi["devices"], "Devices", "#0d9488") +
        _kpi(kpi["pins"], "Signal Pins", "#8b5cf6")
    )
    subtitle = f"Architecture: {data['arch_name']} · {kpi['systems']} systems · {kpi['ecus']} ECUs · {kpi['devices']} devices"

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    content = _TEMPLATE
    content = content.replace("__TITLE__", esc(f"Architecture Tree — {data['arch_name']}"))
    content = content.replace("__CSS__", _CSS)
    content = content.replace("__JS__", _JS.replace("__DATA__", data_json))
    content = content.replace("__SUBTITLE__", esc(subtitle))
    content = content.replace("__GEN__", esc(generated))
    content = content.replace("__SRC__", esc(src_label))
    content = content.replace("__KPIS__", kpis)

    out = get_output_file(root, cfg, "tree", args.output, args.outdir)
    write_text(out, content)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

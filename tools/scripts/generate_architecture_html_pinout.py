#!/usr/bin/env python3
from __future__ import annotations
from collections import defaultdict
from eec_report_common import *


def pinout_rows(arch: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for ecu, pin in iter_ecu_pins(arch):
        sig = pin.get('signal')
        rows.append({
            'ecu': str(ecu.get('name', '')),
            'variant': str(ecu.get('variant', '')),
            'connector': str(pin.get('connector', '')),
            'pin': str(pin.get('physical_number', pin.get('number', ''))),
            'name': str(pin.get('name', '')),
            'role': str(pin.get('role', '')),
            'type': str(pin.get('type', '')),
            'group': str(pin.get('group', '')),
            'signal': signal_name(sig) or str(pin.get('signal_name', '')),
            'interface': signal_interface(sig, pin.get('type', '')),
            'elec': decode_mask(pin.get('electrical_capability', 0), cfg.get('electrical_flags', {})),
            'diag': decode_mask(pin.get('diagnostic_flags', 0), cfg.get('diagnostic_flags', {})),
            'occupied': 'yes' if pin.get('is_occupied') or signal_name(sig) else 'no',
        })
    return rows


def build_data(src: Any, rows: list[dict[str, Any]], root: Any) -> dict:
    """Group flat rows into ECU→connector→pins hierarchy for the JS renderer."""
    ecu_map: dict[str, dict] = {}
    for r in rows:
        ecu_key = r['ecu']
        if ecu_key not in ecu_map:
            ecu_map[ecu_key] = {'name': r['ecu'], 'variant': r['variant'], 'connectors': {}}
        conn_key = r['connector'] or '(default)'
        conns = ecu_map[ecu_key]['connectors']
        if conn_key not in conns:
            conns[conn_key] = {'name': conn_key, 'pins': []}
        conns[conn_key]['pins'].append({
            'pin':      r['pin'],
            'name':     r['name'],
            'type':     r['type'],
            'signal':   r['signal'],
            'role':     r['role'],
            'group':    r['group'],
            'elec':     r['elec'],
            'diag':     r['diag'],
            'occupied': r['occupied'],
            'interface': r['interface'],
        })

    ecus = []
    for ecu_key, ecu_data in ecu_map.items():
        connectors = []
        for conn_key, conn_data in ecu_data['connectors'].items():
            pins = conn_data['pins']
            occupied = sum(1 for p in pins if p['occupied'] == 'yes')
            connectors.append({
                'name': conn_data['name'],
                'total': len(pins),
                'occupied': occupied,
                'pins': pins,
            })
        ecus.append({'name': ecu_data['name'], 'variant': ecu_data['variant'], 'connectors': connectors})

    src_str = str(src.relative_to(root) if hasattr(src, 'is_relative_to') and src.is_relative_to(root) else src)
    return {'source': src_str, 'ecus': ecus}


def build_html(data: dict, title: str) -> str:
    import json as _json
    json_blob = _json.dumps(data, ensure_ascii=False)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
:root{{
  --bg:#0d0f14;--surface:#131720;--raised:#1a1f2e;--hover:#1f2538;--active:#242b42;
  --b0:rgba(255,255,255,.06);--b1:rgba(255,255,255,.10);--b2:rgba(255,255,255,.16);
  --tp:#e8ecf4;--ts:#8993a8;--tm:#5a6278;--ta:#60a5fa;
  --accent:#3b82f6;--accent-dim:rgba(59,130,246,.15);
  --ok:#22c55e;--err:#ef4444;
  --r:6px;--rm:10px;--rl:16px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;overflow:hidden}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--tp);font-size:13px;display:flex;flex-direction:column}}
button,input,select{{font:inherit;color:inherit}}

/* ── topbar ────────────────────────────────────────────────── */
.topbar{{
  flex:0 0 auto;display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:0 20px;height:56px;
  background:var(--surface);border-bottom:1px solid var(--b1);
  position:sticky;top:0;z-index:200;
}}
.topbar-logo{{display:flex;align-items:center;gap:9px}}
.topbar-logo svg{{color:var(--accent)}}
.topbar-title{{font-size:1rem;font-weight:700;letter-spacing:-.02em;white-space:nowrap}}
.topbar-source{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}}
.kpi-strip{{display:flex;gap:6px;align-items:center;margin-left:auto;flex-wrap:wrap}}
.kpi-pill{{display:flex;flex-direction:column;align-items:center;padding:4px 12px;
  border-radius:20px;background:var(--raised);border:1px solid var(--b1);min-width:72px}}
.kp-label{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);line-height:1.2}}
.kp-val{{font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:700;color:var(--tp);line-height:1.2}}
.kp-val.ok{{color:#4ade80}}.kp-val.err{{color:#f87171}}.kp-val.acc{{color:#60a5fa}}

/* ── layout ────────────────────────────────────────────────── */
.app-body{{flex:1;display:flex;overflow:hidden}}

/* ── sidebar ────────────────────────────────────────────────── */
.sidebar{{
  flex:0 0 240px;display:flex;flex-direction:column;
  background:var(--surface);border-right:1px solid var(--b0);
  overflow:hidden;
}}
.sidebar-header{{
  padding:12px 14px 8px;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.07em;color:var(--tm);
  border-bottom:1px solid var(--b0);flex-shrink:0;
}}
.sidebar-search{{padding:8px 10px;flex-shrink:0;border-bottom:1px solid var(--b0)}}
.sidebar-search input{{
  width:100%;padding:6px 10px;border-radius:var(--r);
  background:var(--raised);border:1px solid var(--b1);color:var(--tp);
  outline:none;font-size:12px;transition:border-color .15s;
}}
.sidebar-search input:focus{{border-color:var(--accent)}}
.sidebar-search input::placeholder{{color:var(--tm)}}
.sidebar-list{{overflow-y:auto;flex:1;padding:6px 0}}
.sidebar-item{{
  display:flex;align-items:center;gap:8px;padding:8px 14px;
  cursor:pointer;border-left:3px solid transparent;transition:all .12s;
}}
.sidebar-item:hover{{background:var(--hover);color:var(--tp)}}
.sidebar-item.active{{
  background:var(--accent-dim);border-left-color:var(--accent);color:var(--ta);
}}
.sidebar-item-name{{font-size:12px;font-weight:500;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sidebar-item-cnt{{
  font-family:'JetBrains Mono',monospace;font-size:9.5px;color:var(--tm);
  background:var(--raised);border:1px solid var(--b0);border-radius:10px;
  padding:1px 6px;flex-shrink:0;
}}

/* ── main content ───────────────────────────────────────────── */
.main-content{{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:0}}

/* ── filterbar ──────────────────────────────────────────────── */
.filterbar{{
  position:sticky;top:0;z-index:100;
  display:flex;gap:8px;flex-wrap:wrap;align-items:center;
  background:var(--surface);border-bottom:1px solid var(--b0);
  padding:9px 18px;flex-shrink:0;
}}
.filterbar-label{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);white-space:nowrap}}
.filter-btn{{
  padding:4px 10px;border-radius:20px;border:1px solid var(--b1);
  background:transparent;color:var(--ts);font-size:11px;font-weight:500;
  cursor:pointer;transition:all .12s;white-space:nowrap;
}}
.filter-btn:hover{{background:var(--hover);color:var(--tp);border-color:var(--b2)}}
.filter-btn.active{{background:var(--accent-dim);color:var(--ta);border-color:var(--accent)}}
.filter-input{{
  padding:5px 10px;border-radius:var(--r);
  background:var(--raised);border:1px solid var(--b1);color:var(--tp);outline:none;
  font-size:12px;min-width:140px;transition:border-color .15s;
}}
.filter-input:focus{{border-color:var(--accent)}}
.filter-input::placeholder{{color:var(--tm)}}

/* ── ECU sections ───────────────────────────────────────────── */
.ecu-sections{{padding:18px 20px;display:flex;flex-direction:column;gap:22px}}
.ecu-section{{display:flex;flex-direction:column;gap:12px}}
.ecu-section[hidden]{{display:none!important}}
.ecu-header{{
  display:flex;align-items:center;gap:10px;
  padding-bottom:10px;border-bottom:1px solid var(--b0);
}}
.ecu-header h2{{font-size:1.05rem;font-weight:700;letter-spacing:-.01em}}
.variant-badge{{
  padding:2px 9px;border-radius:12px;font-size:10px;font-weight:700;
  font-family:'JetBrains Mono',monospace;
  background:var(--accent-dim);color:var(--ta);border:1px solid rgba(59,130,246,.25);
}}

/* ── connector grid ─────────────────────────────────────────── */
.conn-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}}
.conn-card{{
  background:var(--raised);border:1px solid var(--b0);border-radius:var(--rm);
  padding:12px 14px;display:flex;flex-direction:column;gap:8px;
}}
.conn-card-name{{font-size:11px;font-weight:700;color:var(--tp);font-family:'JetBrains Mono',monospace}}
.conn-card-counts{{display:flex;justify-content:space-between;font-size:10px;color:var(--ts)}}
.conn-card-counts .used{{color:#4ade80}}
.conn-prog-track{{height:3px;border-radius:2px;background:var(--b0);overflow:hidden}}
.conn-prog-fill{{height:100%;border-radius:2px;background:#22c55e;transition:width .3s}}

/* ── pin table ──────────────────────────────────────────────── */
.pin-table-wrap{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rm);overflow:auto;
}}
table{{width:100%;border-collapse:collapse;font-size:11.5px}}
thead th{{
  position:sticky;top:0;z-index:5;
  background:var(--raised);padding:8px 12px;
  text-align:left;font-size:9.5px;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;color:var(--tm);
  border-bottom:1px solid var(--b1);cursor:pointer;white-space:nowrap;user-select:none;
}}
thead th:hover{{background:var(--active);color:var(--ts)}}
thead th .sa{{margin-left:3px;opacity:.35;font-size:9px}}
thead th.sort-asc .sa::after{{content:'▲';opacity:1}}
thead th.sort-desc .sa::after{{content:'▼';opacity:1}}
thead th:not(.sort-asc):not(.sort-desc) .sa::after{{content:'⇅'}}
td{{padding:7px 12px;border-bottom:1px solid var(--b0);vertical-align:middle;color:var(--ts)}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.025);color:var(--tp)}}
tbody tr[hidden]{{display:none!important}}
.pin-num{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:var(--tp)}}
.sig-name{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:var(--ta)}}
.iface-pill{{
  display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;
  font-family:'JetBrains Mono',monospace;font-size:9.5px;font-weight:700;
  white-space:nowrap;border:1px solid transparent;
}}
.occ-badge{{
  display:inline-flex;align-items:center;gap:5px;
  font-size:10px;font-weight:600;
}}
.occ-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.occ-yes .occ-dot{{background:#22c55e}}
.occ-yes{{color:#4ade80}}
.occ-no .occ-dot{{background:var(--tm)}}
.occ-no{{color:var(--tm)}}
.elec-tag{{
  display:inline-block;padding:1px 5px;border-radius:3px;
  background:rgba(255,255,255,.05);color:var(--ts);
  font-size:9.5px;font-family:'JetBrains Mono',monospace;border:1px solid var(--b0);
  margin:1px 2px 1px 0;
}}

::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--b1);border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:var(--b2)}}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-logo">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
         stroke-linecap="round" stroke-linejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2"/>
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
      <line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/>
    </svg>
    <span class="topbar-title">ECU Pinout</span>
  </div>
  <span class="topbar-source" id="src-label"></span>
  <div class="kpi-strip">
    <div class="kpi-pill"><span class="kp-label">ECUs</span><span class="kp-val acc" id="kpi-ecus">—</span></div>
    <div class="kpi-pill"><span class="kp-label">Total Pins</span><span class="kp-val" id="kpi-total">—</span></div>
    <div class="kpi-pill"><span class="kp-label">Occupied</span><span class="kp-val ok" id="kpi-occ">—</span></div>
    <div class="kpi-pill"><span class="kp-label">Free</span><span class="kp-val err" id="kpi-free">—</span></div>
  </div>
</header>

<div class="app-body">
  <!-- sidebar -->
  <nav class="sidebar">
    <div class="sidebar-header">ECUs</div>
    <div class="sidebar-search"><input id="sidebar-search" placeholder="Filter ECUs…"/></div>
    <div class="sidebar-list" id="sidebar-list"></div>
  </nav>

  <!-- main -->
  <div class="main-content" id="main-content">
    <div class="filterbar">
      <span class="filterbar-label">ECU</span>
      <input class="filter-input" id="f-ecu" placeholder="ECU name…" style="min-width:130px"/>
      <span class="filterbar-label" style="margin-left:8px">Connector</span>
      <input class="filter-input" id="f-conn" placeholder="Connector…" style="min-width:120px"/>
      <span class="filterbar-label" style="margin-left:8px">Type</span>
      <div id="f-type-group" style="display:flex;gap:4px;flex-wrap:wrap"></div>
      <span class="filterbar-label" style="margin-left:8px">Occupied</span>
      <div id="f-occ-group" style="display:flex;gap:4px">
        <button class="filter-btn active" data-occ="ALL">All</button>
        <button class="filter-btn" data-occ="yes">Occupied</button>
        <button class="filter-btn" data-occ="no">Free</button>
      </div>
    </div>
    <div class="ecu-sections" id="ecu-sections"></div>
  </div>
</div>

<script>
var DATA = {json_blob};

var IFACE_COLORS = {{
  'ANALOG':    {{bg:'rgba(245,158,11,.15)',  color:'#f59e0b', border:'rgba(245,158,11,.35)'}},
  'DIGITAL':   {{bg:'rgba(16,185,129,.15)',  color:'#10b981', border:'rgba(16,185,129,.35)'}},
  'CAN':       {{bg:'rgba(34,211,238,.15)',  color:'#22d3ee', border:'rgba(34,211,238,.35)'}},
  'PWM':       {{bg:'rgba(249,115,22,.15)',  color:'#f97316', border:'rgba(249,115,22,.35)'}},
  'FREQ':      {{bg:'rgba(139,92,246,.15)',  color:'#8b5cf6', border:'rgba(139,92,246,.35)'}},
  'POWER':     {{bg:'rgba(52,211,153,.15)',  color:'#34d399', border:'rgba(52,211,153,.35)'}},
  'GROUND':    {{bg:'rgba(107,114,128,.15)', color:'#6b7280', border:'rgba(107,114,128,.35)'}},
  'RESISTANCE':{{bg:'rgba(100,116,139,.15)', color:'#64748b', border:'rgba(100,116,139,.35)'}},
  'LIN':       {{bg:'rgba(167,139,250,.15)', color:'#a78bfa', border:'rgba(167,139,250,.35)'}},
}};
var IFACE_DEFAULT = {{bg:'rgba(148,163,184,.1)', color:'#94a3b8', border:'rgba(148,163,184,.25)'}};

function escHtml(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function ifacePill(val) {{
  var key = (val||'').toUpperCase().trim();
  var c = IFACE_COLORS[key] || IFACE_DEFAULT;
  if(!val) return '<span style="color:var(--tm);font-size:10px">—</span>';
  return '<span class="iface-pill" style="background:'+c.bg+';color:'+c.color+';border-color:'+c.border+'">'
       + escHtml(val) + '</span>';
}}

function occBadge(val) {{
  var yes = val === 'yes';
  return '<span class="occ-badge '+(yes?'occ-yes':'occ-no')+'">'
       + '<span class="occ-dot"></span>'+(yes?'Occupied':'Free')+'</span>';
}}

function elecTags(val) {{
  if(!val) return '<span style="color:var(--tm)">—</span>';
  return val.split('|').map(function(t){{
    return '<span class="elec-tag">'+escHtml(t.trim())+'</span>';
  }}).join('');
}}

// ── state ────────────────────────────────────────────────────────────────────
var filterEcu  = '';
var filterConn = '';
var filterType = 'ALL';
var filterOcc  = 'ALL';

var ecus = DATA.ecus || [];

// ── KPIs ─────────────────────────────────────────────────────────────────────
(function() {{
  var totalPins = 0, totalOcc = 0;
  ecus.forEach(function(e) {{
    e.connectors.forEach(function(c) {{
      totalPins += c.total;
      totalOcc  += c.occupied;
    }});
  }});
  document.getElementById('kpi-ecus').textContent  = ecus.length;
  document.getElementById('kpi-total').textContent = totalPins;
  document.getElementById('kpi-occ').textContent   = totalOcc;
  document.getElementById('kpi-free').textContent  = totalPins - totalOcc;
  document.getElementById('src-label').textContent = DATA.source || '';
}})();

// ── collect unique types ──────────────────────────────────────────────────────
(function() {{
  var seen = {{}};
  ecus.forEach(function(e) {{
    e.connectors.forEach(function(c) {{
      c.pins.forEach(function(p) {{ if(p.type) seen[p.type] = 1; }});
    }});
  }});
  var tg = document.getElementById('f-type-group');
  var allBtn = document.createElement('button');
  allBtn.className = 'filter-btn active';
  allBtn.textContent = 'All';
  allBtn.dataset.type = 'ALL';
  allBtn.addEventListener('click', function() {{
    filterType = 'ALL';
    tg.querySelectorAll('.filter-btn').forEach(function(b){{b.classList.toggle('active',b.dataset.type==='ALL');}});
    applyFilters();
  }});
  tg.appendChild(allBtn);
  Object.keys(seen).sort().forEach(function(t) {{
    var btn = document.createElement('button');
    btn.className = 'filter-btn';
    btn.textContent = t;
    btn.dataset.type = t;
    btn.addEventListener('click', function() {{
      filterType = t;
      tg.querySelectorAll('.filter-btn').forEach(function(b){{b.classList.toggle('active',b.dataset.type===t);}});
      applyFilters();
    }});
    tg.appendChild(btn);
  }});
}})();

// ── occupied filter ───────────────────────────────────────────────────────────
document.querySelectorAll('#f-occ-group .filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    filterOcc = btn.dataset.occ;
    document.querySelectorAll('#f-occ-group .filter-btn').forEach(function(b){{
      b.classList.toggle('active',b.dataset.occ===filterOcc);
    }});
    applyFilters();
  }});
}});

document.getElementById('f-ecu').addEventListener('input', function()  {{ filterEcu  = this.value.toLowerCase(); applyFilters(); }});
document.getElementById('f-conn').addEventListener('input', function() {{ filterConn = this.value.toLowerCase(); applyFilters(); }});

// ── sidebar ──────────────────────────────────────────────────────────────────
function buildSidebar() {{
  var list = document.getElementById('sidebar-list');
  list.innerHTML = '';
  ecus.forEach(function(ecu) {{
    var totalPins = 0, occPins = 0;
    ecu.connectors.forEach(function(c){{ totalPins += c.total; occPins += c.occupied; }});
    var item = document.createElement('div');
    item.className = 'sidebar-item';
    item.dataset.ecuName = ecu.name;
    item.innerHTML = '<span class="sidebar-item-name">'+escHtml(ecu.name)+'</span>'
                   + '<span class="sidebar-item-cnt">'+occPins+'/'+totalPins+'</span>';
    item.addEventListener('click', function() {{
      document.querySelectorAll('.sidebar-item').forEach(function(i){{i.classList.remove('active');}});
      item.classList.add('active');
      var sec = document.getElementById('ecu-sec-'+slugify(ecu.name));
      if(sec) sec.scrollIntoView({{behavior:'smooth',block:'start'}});
    }});
    list.appendChild(item);
  }});
}}

document.getElementById('sidebar-search').addEventListener('input', function() {{
  var q = this.value.toLowerCase();
  document.querySelectorAll('.sidebar-item').forEach(function(item) {{
    var name = (item.dataset.ecuName||'').toLowerCase();
    item.style.display = name.indexOf(q) >= 0 ? '' : 'none';
  }});
}});

function slugify(s) {{
  return String(s||'').replace(/[^A-Za-z0-9_.-]+/g,'_').replace(/^_|_$/g,'') || 'item';
}}

// ── render ECU sections ───────────────────────────────────────────────────────
function buildEcuSections() {{
  var container = document.getElementById('ecu-sections');
  container.innerHTML = '';
  ecus.forEach(function(ecu) {{
    var secId = 'ecu-sec-' + slugify(ecu.name);
    var sec = document.createElement('div');
    sec.className = 'ecu-section';
    sec.id = secId;
    sec.dataset.ecuName = ecu.name.toLowerCase();

    // header
    var hdr = document.createElement('div');
    hdr.className = 'ecu-header';
    hdr.innerHTML = '<h2>'+escHtml(ecu.name)+'</h2>'
                  + (ecu.variant ? '<span class="variant-badge">'+escHtml(ecu.variant)+'</span>' : '');
    sec.appendChild(hdr);

    // connector utilization grid
    var grid = document.createElement('div');
    grid.className = 'conn-grid';
    grid.dataset.connGrid = '1';
    ecu.connectors.forEach(function(conn) {{
      var pct = conn.total > 0 ? Math.round(conn.occupied / conn.total * 100) : 0;
      var card = document.createElement('div');
      card.className = 'conn-card';
      card.dataset.connName = conn.name.toLowerCase();
      card.innerHTML = '<div class="conn-card-name">'+escHtml(conn.name)+'</div>'
        + '<div class="conn-card-counts">'
        + '  <span><span class="used">'+conn.occupied+'</span> used</span>'
        + '  <span>'+conn.total+' total</span>'
        + '</div>'
        + '<div class="conn-prog-track"><div class="conn-prog-fill" style="width:'+pct+'%"></div></div>';
      grid.appendChild(card);
    }});
    sec.appendChild(grid);

    // pin tables (one per connector)
    ecu.connectors.forEach(function(conn) {{
      var tbl = buildPinTable(ecu.name, conn);
      sec.appendChild(tbl);
    }});

    container.appendChild(sec);
  }});
}}

function buildPinTable(ecuName, conn) {{
  var wrap = document.createElement('div');
  wrap.className = 'pin-table-wrap';
  wrap.dataset.connName = conn.name.toLowerCase();

  var connLabel = document.createElement('div');
  connLabel.style.cssText = 'padding:10px 14px 0;font-size:10px;font-weight:700;'
    +'text-transform:uppercase;letter-spacing:.07em;color:var(--tm)';
  connLabel.textContent = conn.name;
  wrap.appendChild(connLabel);

  var tbl = document.createElement('table');
  tbl.dataset.ecuName = ecuName;
  tbl.dataset.connName = conn.name;
  var PIN_COLS = ['pin','name','type','signal','role','group','elec','diag','occupied'];
  var PIN_LABELS = ['Pin #','Name','Type','Signal','Role','Group','Electrical','Diagnostics','Status'];

  var thead = document.createElement('thead');
  var trh = document.createElement('tr');
  PIN_LABELS.forEach(function(lbl, idx) {{
    var th = document.createElement('th');
    th.innerHTML = escHtml(lbl)+'<span class="sa"></span>';
    th.dataset.idx = idx;
    th.addEventListener('click', function() {{
      var rows = Array.from(tbl.querySelectorAll('tbody tr'));
      var asc  = tbl.dataset.sortIdx === String(idx) ? tbl.dataset.sortDir !== 'asc' : true;
      tbl.dataset.sortIdx = idx;
      tbl.dataset.sortDir = asc ? 'asc' : 'desc';
      trh.querySelectorAll('th').forEach(function(h) {{ h.classList.remove('sort-asc','sort-desc'); }});
      th.classList.add(asc ? 'sort-asc' : 'sort-desc');
      rows.sort(function(a,b) {{
        var A = a.children[idx].dataset.sortVal || a.children[idx].textContent;
        var B = b.children[idx].dataset.sortVal || b.children[idx].textContent;
        var na = parseFloat(A), nb = parseFloat(B);
        var cmp = (!isNaN(na)&&!isNaN(nb)) ? na-nb : A.localeCompare(B);
        return asc ? cmp : -cmp;
      }});
      rows.forEach(function(r) {{ tbl.querySelector('tbody').appendChild(r); }});
    }});
    trh.appendChild(th);
  }});
  thead.appendChild(trh);
  tbl.appendChild(thead);

  var tbody = document.createElement('tbody');
  conn.pins.forEach(function(p) {{
    var tr = document.createElement('tr');
    tr.dataset.pinType = (p.type||'').toLowerCase();
    tr.dataset.pinOcc  = p.occupied;

    var cells = [
      '<span class="pin-num">'+escHtml(p.pin)+'</span>',
      escHtml(p.name),
      ifacePill(p.type || p.interface),
      p.signal ? '<span class="sig-name">'+escHtml(p.signal)+'</span>' : '<span style="color:var(--tm)">—</span>',
      escHtml(p.role) || '<span style="color:var(--tm)">—</span>',
      escHtml(p.group) || '<span style="color:var(--tm)">—</span>',
      elecTags(p.elec),
      elecTags(p.diag),
      occBadge(p.occupied),
    ];
    cells.forEach(function(c, ci) {{
      var td = document.createElement('td');
      td.innerHTML = c;
      if(ci===0) td.dataset.sortVal = parseFloat(p.pin)||0;
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }});
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
  return wrap;
}}

// ── filtering ─────────────────────────────────────────────────────────────────
function applyFilters() {{
  document.querySelectorAll('.ecu-section').forEach(function(sec) {{
    var ecuName = sec.dataset.ecuName || '';
    var ecuMatch = !filterEcu || ecuName.indexOf(filterEcu) >= 0;
    if(!ecuMatch) {{ sec.hidden = true; return; }}
    sec.hidden = false;

    // connector cards + pin tables
    var hasVisibleConn = false;
    var connCards  = Array.from(sec.querySelectorAll('.conn-card'));
    var pinTables  = Array.from(sec.querySelectorAll('.pin-table-wrap'));

    pinTables.forEach(function(wrap) {{
      var connName = wrap.dataset.connName || '';
      var connMatch = !filterConn || connName.indexOf(filterConn) >= 0;
      if(!connMatch) {{ wrap.hidden = true; return; }}

      // filter rows
      var anyRow = false;
      wrap.querySelectorAll('tbody tr').forEach(function(tr) {{
        var typeOk = filterType === 'ALL' || tr.dataset.pinType === filterType.toLowerCase();
        var occOk  = filterOcc  === 'ALL' || tr.dataset.pinOcc  === filterOcc;
        var show = typeOk && occOk;
        tr.hidden = !show;
        if(show) anyRow = true;
      }});
      wrap.hidden = !anyRow;
      if(anyRow) hasVisibleConn = true;
    }});

    // sync connector cards visibility
    connCards.forEach(function(card) {{
      var cname = card.dataset.connName || '';
      var connMatch = !filterConn || cname.indexOf(filterConn) >= 0;
      card.style.display = connMatch ? '' : 'none';
    }});

    sec.hidden = !hasVisibleConn && !!filterConn;
  }});

  // sync sidebar highlights
  document.querySelectorAll('.sidebar-item').forEach(function(item) {{
    var name = (item.dataset.ecuName||'').toLowerCase();
    var sec  = document.getElementById('ecu-sec-'+slugify(item.dataset.ecuName));
    item.style.display = (!filterEcu || name.indexOf(filterEcu)>=0) && sec && !sec.hidden ? '' : 'none';
  }});
}}

// ── scroll spy ────────────────────────────────────────────────────────────────
var mainContent = document.getElementById('main-content');
mainContent.addEventListener('scroll', function() {{
  var mid = mainContent.scrollTop + 80;
  var secs = document.querySelectorAll('.ecu-section:not([hidden])');
  var current = null;
  secs.forEach(function(sec) {{
    if(sec.offsetTop <= mid) current = sec;
  }});
  document.querySelectorAll('.sidebar-item').forEach(function(item) {{
    var active = current && current.dataset.ecuName === (item.dataset.ecuName||'').toLowerCase();
    item.classList.toggle('active', !!active);
  }});
}});

// ── init ──────────────────────────────────────────────────────────────────────
buildSidebar();
buildEcuSections();
</script>
</body></html>"""


def main() -> int:
    parser = standard_arg_parser('Generate v4 generic ECU pinout HTML from architecture export.')
    args = parser.parse_args()
    cfg = load_config(Path(args.config) if args.config else None)
    root = resolve_root(args.root)
    src, arch = load_architecture_from_args(args, cfg, physical=True)
    rows = pinout_rows(arch, cfg)
    data = build_data(src, rows, root)
    out = get_output_file(root, cfg, 'pinout', args.output, args.outdir)
    write_text(out, build_html(data, 'Architecture ECU Pinout'))
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

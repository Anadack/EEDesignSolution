#!/usr/bin/env python3
from __future__ import annotations
import json
from typing import Any
from collections import Counter, defaultdict
from eec_report_common import *


def bus_rows(arch: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    excluded = {str(x).upper() for x in cfg.get("excluded_bus_interfaces", [])}
    rows = []
    for ecu, pin in iter_ecu_pins(arch):
        sig = pin.get("signal")
        iface = normalize_token(signal_interface(sig, pin.get("type", "")))
        if not iface or iface in excluded:
            continue
        rows.append({
            "interface": iface,
            "signal": signal_name(sig) or str(pin.get("signal_name", "")),
            "ecu": str(ecu.get("name", "")),
            "variant": str(ecu.get("variant", "")),
            "connector": str(pin.get("connector", "")),
            "pin": str(pin.get("physical_number", pin.get("number", ""))),
            "role": str(pin.get("role", "")),
            "pin_type": str(pin.get("type", "")),
        })
    return rows


def main() -> int:
    parser = standard_arg_parser("Generate v4 generic Bus Backbone HTML.")
    args = parser.parse_args()
    cfg = load_config(Path(args.config) if args.config else None)
    root = resolve_root(args.root)
    src, arch = load_architecture_from_args(args, cfg, physical=True)
    rows = bus_rows(arch, cfg)

    data = {
        "source": str(src.relative_to(root) if src.is_relative_to(root) else src),
        "rows": rows,
    }
    data_json = json.dumps(data, ensure_ascii=False)

    html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Bus Backbone</title>
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

/* ── app body ── */
.app-body{{padding:20px 24px;display:grid;gap:14px;max-width:1600px;margin:0 auto}}

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
  border-radius:var(--r);color:var(--tp);outline:none;transition:border-color .15s;min-width:160px;
}}
input.search:focus{{border-color:var(--accent)}}
input.search::placeholder{{color:var(--tm)}}

/* ── bar chart ── */
.chart-card{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);padding:18px 24px;
}}
.chart-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);margin-bottom:14px}}
.chart-rows{{display:grid;gap:8px}}
.chart-row{{display:grid;grid-template-columns:110px 1fr 48px;align-items:center;gap:10px}}
.chart-label{{font-size:11px;font-weight:600;color:var(--ts);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.chart-track{{background:var(--raised);border-radius:4px;height:18px;overflow:hidden;border:1px solid var(--b0)}}
.chart-bar{{height:100%;border-radius:4px;transition:width .4s cubic-bezier(.4,0,.2,1)}}
.chart-val{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:var(--tp);text-align:right}}

/* ── interface cards ── */
.iface-card{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);
  overflow:hidden;margin-bottom:0;
}}
.iface-card.hidden{{display:none}}
.iface-card-header{{
  display:flex;align-items:center;gap:10px;padding:12px 18px;
  background:var(--raised);border-bottom:1px solid var(--b0);
  cursor:pointer;user-select:none;
}}
.iface-card-header:hover{{background:var(--hover)}}
.iface-pill{{
  display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;
  font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap;
}}
.iface-pin-count{{font-size:10px;color:var(--tm);padding:2px 8px;background:var(--active);border-radius:20px;font-weight:600}}
.iface-chevron{{margin-left:auto;color:var(--tm);font-size:12px;transition:transform .2s}}
.iface-card.collapsed .iface-chevron{{transform:rotate(-90deg)}}
.iface-body{{padding:14px 18px;display:grid;gap:14px}}
.iface-card.collapsed .iface-body{{display:none}}

/* ── ECU summary chips inside card ── */
.ecu-summary{{}}
.ecu-summary-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--tm);margin-bottom:8px}}
.ecu-block{{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap;margin-bottom:6px}}
.ecu-lbl{{font-size:11px;font-weight:700;color:var(--ta);min-width:100px;padding-top:3px;white-space:nowrap}}
.chip-wrap{{display:flex;gap:4px;flex-wrap:wrap}}
.conn-chip{{
  display:inline-flex;align-items:center;padding:2px 8px;border-radius:4px;
  font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;
  background:var(--active);border:1px solid var(--b1);color:var(--ts);
  white-space:nowrap;
}}

/* ── detail table ── */
.detail-section{{}}
.detail-toggle{{
  background:none;border:none;color:var(--ta);font-size:11px;font-weight:600;
  cursor:pointer;padding:0;margin-bottom:8px;display:flex;align-items:center;gap:4px;
}}
.detail-toggle:hover{{color:var(--tp)}}
.detail-wrap{{display:none;overflow:auto;max-height:50vh;border-radius:var(--r);border:1px solid var(--b0)}}
.detail-wrap.open{{display:block}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{
  position:sticky;top:0;background:var(--raised);z-index:1;
  padding:8px 12px;text-align:left;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;color:var(--tm);
  border-bottom:1px solid var(--b1);white-space:nowrap;
}}
td{{padding:7px 12px;border-bottom:1px solid var(--b0);vertical-align:top;color:var(--ts)}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.025);color:var(--tp)}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:11px}}

/* ── no results ── */
.empty-state{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);
  padding:40px;text-align:center;color:var(--tm);display:none;
}}

/* ── scrollbar ── */
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--b1);border-radius:2px}}
</style>
</head>
<body>
<header class="topbar">
  <span class="topbar-title">Bus Backbone</span>
  <div class="topbar-kpis" id="kpi-bar"></div>
</header>
<div class="app-body">
  <div class="filterbar" id="filterbar">
    <label>Bus Type</label>
    <div id="iface-pills" style="display:flex;gap:4px;flex-wrap:wrap"></div>
    <div style="width:1px;background:var(--b1);height:20px;margin:0 4px"></div>
    <label>ECU</label>
    <input class="search" id="ecu-filter" placeholder="Filter ECU…" style="max-width:180px" oninput="applyFilters()"/>
    <input class="search" id="global-search" placeholder="Search…" oninput="applyFilters()"/>
    <span id="row-count" style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm)"></span>
  </div>

  <div class="chart-card" id="chart-card">
    <div class="chart-title">Pin count per bus type</div>
    <div class="chart-rows" id="chart-rows"></div>
  </div>

  <div id="iface-groups" style="display:grid;gap:10px"></div>
  <div class="empty-state" id="empty-state">No bus connections match current filters.</div>
</div>
<script>
var DATA = {data_json};

var IFACE_COLORS = {{
  ANALOG:'#f59e0b',DIGITAL:'#10b981',CAN:'#22d3ee',PWM:'#f97316',
  FREQ:'#8b5cf6',POWER:'#34d399',GROUND:'#6b7280',RESISTANCE:'#64748b',
  LIN:'#a78bfa'
}};
function ifaceColor(i){{return IFACE_COLORS[i.toUpperCase()]||'#94a3b8';}}
function esc(s){{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

var activeIfaces = new Set();
var allIfaces = [];

/* ── collect interfaces ── */
(function(){{
  var set = new Set();
  DATA.rows.forEach(function(r){{if(r.interface) set.add(r.interface.toUpperCase());}});
  allIfaces = Array.from(set).sort();
  allIfaces.forEach(function(i){{activeIfaces.add(i);}});
}})();

/* ── KPIs ── */
function buildKPIs(){{
  var bar = document.getElementById('kpi-bar');
  var total = DATA.rows.length;
  bar.innerHTML = [
    [allIfaces.length,'Bus Types'],
    [total,'Total Connections'],
  ].map(function(x){{
    return '<div class="kpi-chip"><span class="kv">'+x[0]+'</span><span class="kl">'+x[1]+'</span></div>';
  }}).join('');
}}

/* ── interface toggle pills ── */
function buildIfacePills(){{
  var c = document.getElementById('iface-pills');
  c.innerHTML = allIfaces.map(function(i){{
    var col = ifaceColor(i);
    return '<button class="pill-btn on" id="pill-'+i+'"'
      +' style="background:'+col+'22;color:'+col+';border-color:'+col+'44"'
      +' onclick="toggleIface(\''+i+'\')">'
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
    btn.style.background='var(--raised)'; btn.style.color='var(--ts)'; btn.style.borderColor='var(--b1)';
  }}
  applyFilters();
}}

/* ── filter rows ── */
function filteredRows(){{
  var ecuF = (document.getElementById('ecu-filter').value||'').toLowerCase();
  var q = (document.getElementById('global-search').value||'').toLowerCase();
  return DATA.rows.filter(function(r){{
    var iface = (r.interface||'').toUpperCase();
    if(!activeIfaces.has(iface)) return false;
    if(ecuF && !(r.ecu||'').toLowerCase().includes(ecuF)) return false;
    if(q){{
      var h=[r.interface,r.signal,r.ecu,r.connector,r.pin,r.role].join(' ').toLowerCase();
      if(!h.includes(q)) return false;
    }}
    return true;
  }});
}}

/* ── bar chart ── */
function buildChart(rows){{
  var counts = {{}};
  rows.forEach(function(r){{counts[r.interface]=(counts[r.interface]||0)+1;}});
  var max = Math.max.apply(null,Object.values(counts).concat([1]));
  var sorted = Object.keys(counts).sort(function(a,b){{return counts[b]-counts[a];}});
  document.getElementById('chart-rows').innerHTML = sorted.map(function(k){{
    var col = ifaceColor(k);
    var pct = Math.round(counts[k]/max*100);
    return '<div class="chart-row">'
      +'<div class="chart-label" style="color:'+col+'">'+esc(k)+'</div>'
      +'<div class="chart-track"><div class="chart-bar" style="width:'+pct+'%;background:'+col+'"></div></div>'
      +'<div class="chart-val">'+counts[k]+'</div>'
      +'</div>';
  }}).join('');
}}

/* ── interface cards ── */
function buildCards(rows){{
  var groups = {{}};
  rows.forEach(function(r){{
    if(!groups[r.interface]) groups[r.interface]=[];
    groups[r.interface].push(r);
  }});

  var container = document.getElementById('iface-groups');
  container.innerHTML = '';

  var visible = 0;
  allIfaces.forEach(function(iface){{
    if(!activeIfaces.has(iface)) return;
    var items = groups[iface]||[];
    if(!items.length) return;
    visible++;

    var col = ifaceColor(iface);
    var card = document.createElement('div');
    card.className = 'iface-card';
    card.id = 'icard-'+iface;

    /* ECU summary */
    var ecuMap = {{}};
    items.forEach(function(r){{
      if(!ecuMap[r.ecu]) ecuMap[r.ecu]=[];
      var label = [r.connector,r.pin].filter(Boolean).join(':');
      if(label) ecuMap[r.ecu].push(label);
    }});
    var ecuKeys = Object.keys(ecuMap).sort();
    var summaryHtml = '<div class="ecu-summary">'
      +'<div class="ecu-summary-title">ECU Connections</div>'
      +ecuKeys.map(function(ecu){{
        var chips = ecuMap[ecu].slice(0,30).map(function(l){{return '<span class="conn-chip">'+esc(l)+'</span>';}}).join('');
        var more = ecuMap[ecu].length>30?'<span class="conn-chip" style="color:var(--tm)">+'+( ecuMap[ecu].length-30)+' more</span>':'';
        return '<div class="ecu-block">'
          +'<span class="ecu-lbl">'+esc(ecu)+'</span>'
          +'<div class="chip-wrap">'+chips+more+'</div>'
          +'</div>';
      }}).join('')
      +'</div>';

    /* detail table */
    var tblId = 'dtbl-'+iface;
    var wrapId = 'dwrap-'+iface;
    var tblHead = '<thead><tr>'
      +'<th>Signal</th><th>ECU</th><th>Connector</th><th>Pin</th><th>Role</th>'
      +'</tr></thead>';
    var tblBody = '<tbody>'+items.map(function(r){{
      return '<tr>'
        +'<td class="mono">'+esc(r.signal)+'</td>'
        +'<td>'+esc(r.ecu)+'</td>'
        +'<td class="mono">'+esc(r.connector)+'</td>'
        +'<td class="mono">'+esc(r.pin)+'</td>'
        +'<td>'+esc(r.role)+'</td>'
        +'</tr>';
    }}).join('')+'</tbody>';

    var detailHtml = '<div class="detail-section">'
      +'<button class="detail-toggle" onclick="toggleDetail(\''+wrapId+'\')">'
      +'&#9658; Show detail table ('+items.length+' pins)</button>'
      +'<div class="detail-wrap" id="'+wrapId+'">'
      +'<table id="'+tblId+'">'+tblHead+tblBody+'</table>'
      +'</div>'
      +'</div>';

    card.innerHTML = '<div class="iface-card-header" onclick="toggleCard(\'icard-'+iface+'\')">'
      +'<span class="iface-pill" style="background:'+col+'22;color:'+col+';border:1px solid '+col+'44">'+esc(iface)+'</span>'
      +'<span class="iface-pin-count">'+items.length+' pins</span>'
      +'<span class="iface-chevron">&#9660;</span>'
      +'</div>'
      +'<div class="iface-body">'+summaryHtml+detailHtml+'</div>';

    container.appendChild(card);
  }});

  document.getElementById('empty-state').style.display = visible===0?'block':'none';
}}

function toggleCard(id){{
  document.getElementById(id).classList.toggle('collapsed');
}}
function toggleDetail(wrapId){{
  var w = document.getElementById(wrapId);
  w.classList.toggle('open');
  var btn = w.previousElementSibling;
  btn.innerHTML = w.classList.contains('open')
    ? '&#9660; Hide detail table'
    : '&#9658; Show detail table ('+w.querySelector('tbody').rows.length+' pins)';
}}

function applyFilters(){{
  var rows = filteredRows();
  document.getElementById('row-count').textContent = rows.length+' / '+DATA.rows.length+' connections';
  buildChart(rows);
  buildCards(rows);
}}

/* ── init ── */
buildKPIs();
buildIfacePills();
applyFilters();
</script>
</body></html>"""

    out = get_output_file(root, cfg, "bus_backbone", args.output, args.outdir)
    write_text(out, html)
    print(out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

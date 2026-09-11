#!/usr/bin/env python3
"""E/E Architect Design — Architecture Topology HTML Report (v4, professional).

Shows the ECU fleet with utilisation bars and, per system, how each device's
signals are routed to ECUs.  Filter by system, ECU, mapping status, and
interface type.

Usage:
    python3 generate_architecture_topology_html.py --root /path/to/project
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from eec_report_common import (
    collect_allocation_rows, esc, get_output_file,
    load_architecture_from_args, load_config, normalize_token,
    resolve_root, signal_name, standard_arg_parser, write_text,
)

# ── design tokens ─────────────────────────────────────────────────────────────

IFACE_COLORS: dict[str, str] = {
    "ANALOG":         "#f59e0b",
    "ANALOG_INPUT":   "#f59e0b",
    "DIGITAL":        "#3b82f6",
    "DIGITAL_INPUT":  "#3b82f6",
    "DIGITAL_OUTPUT": "#ef4444",
    "PWM":            "#8b5cf6",
    "CAN":            "#06b6d4",
    "FREQUENCY":      "#ec4899",
    "POWER":          "#dc2626",
    "SUPPLY":         "#dc2626",
    "GROUND":         "#6b7280",
    "RESISTANCE":     "#14b8a6",
}
DEFAULT_IFACE_COLOR = "#64748b"

SAFETY_COLORS: dict[str, str] = {
    "QM":     "#22c55e",
    "AGPL_A": "#84cc16",
    "AGPL_B": "#eab308",
    "AGPL_C": "#f97316",
    "AGPL_D": "#ef4444",
}

PRIORITY_COLORS: dict[str, str] = {
    "LOW":      "#64748b",
    "MEDIUM":   "#3b82f6",
    "HIGH":     "#f59e0b",
    "CRITICAL": "#ef4444",
}

_IFACE_ORDER    = ["ANALOG", "DIGITAL", "PWM", "CAN", "FREQUENCY", "POWER", "GROUND", "RESISTANCE"]
_SAFETY_ORDER   = ["QM", "AGPL_A", "AGPL_B", "AGPL_C", "AGPL_D"]
_PRIORITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _tok(v: object) -> str:
    return normalize_token(v)


def _order_set(vals: set, reference: list) -> list:
    known   = [v for v in reference if v in vals]
    unknown = sorted(v for v in vals if v not in reference)
    return known + unknown


# ── data extraction ────────────────────────────────────────────────────────────

def _ecu_used_pins(ecu: dict) -> int:
    """Count occupied pins from ecu['pins'] list."""
    total = 0
    for p in (ecu.get("pins") or []):
        if isinstance(p, dict) and (p.get("is_occupied") or p.get("signal")):
            total += 1
    return total


def _build_data(arch: dict, cfg: dict) -> dict:
    """Build the JSON payload consumed by the embedded JavaScript renderer."""
    rows = collect_allocation_rows(arch, cfg)

    # ── ECU fleet ──────────────────────────────────────────────────────────────
    ecus_out: list = []
    for ecu in (arch.get("ecus") or []):
        if not isinstance(ecu, dict):
            continue
        name     = str(ecu.get("name") or "")
        variant  = str(ecu.get("variant") or "")
        pins     = ecu.get("pins") or []
        total    = len(pins) if isinstance(pins, list) else 0
        used     = _ecu_used_pins(ecu)
        free     = total - used
        can_ids  = [str(a) for a in (ecu.get("can_addresses") or []) if a]
        pct      = round(100 * used / total) if total else 0
        # bar colour: green < 60%, amber < 85%, red >= 85%
        bar_color = "#22c55e" if pct < 60 else "#f59e0b" if pct < 85 else "#ef4444"
        ecus_out.append({
            "name":      name,
            "variant":   variant,
            "can_ids":   can_ids,
            "total":     total,
            "used":      used,
            "free":      free,
            "pct":       pct,
            "bar_color": bar_color,
        })

    # ── system routing ─────────────────────────────────────────────────────────
    # Group rows: system -> device -> ecu -> [signals]
    # Also track unmapped separately
    by_system: dict[str, dict] = {}
    all_ifaces: set  = set()
    all_ecu_names: set = set()
    all_sys_names: set = set()

    for row in rows:
        sys_name = str(row.get("system") or "Unknown System")
        dev_name = str(row.get("device") or "Unknown Device")
        dev_type = str(row.get("device_type") or "")
        sig_name = str(row.get("signal") or "")
        iface    = _tok(row.get("interface") or "")
        ecu_name = str(row.get("ecu") or "")
        status   = str(row.get("status") or "UNMAPPED")

        all_ifaces.add(iface)
        all_sys_names.add(sys_name)
        if ecu_name:
            all_ecu_names.add(ecu_name)

        if sys_name not in by_system:
            by_system[sys_name] = {"name": sys_name, "devices": {}}

        devs = by_system[sys_name]["devices"]
        if dev_name not in devs:
            devs[dev_name] = {
                "name":     dev_name,
                "type":     dev_type,
                "mapped":   {},    # ecu_name -> [signal chips]
                "unmapped": [],    # [signal chips]
            }

        chip = {"signal": sig_name, "iface": iface, "status": status}
        if status == "MAPPED" and ecu_name:
            devs[dev_name]["mapped"].setdefault(ecu_name, []).append(chip)
        else:
            devs[dev_name]["unmapped"].append(chip)

    # Convert to serialisable lists
    systems_out: list = []
    for sys_name, sys_data in sorted(by_system.items()):
        devs_out = []
        for dev_name, dev_data in sorted(sys_data["devices"].items()):
            mapped_list = [
                {"ecu": en, "signals": ss}
                for en, ss in sorted(dev_data["mapped"].items())
            ]
            devs_out.append({
                "name":     dev_data["name"],
                "type":     dev_data["type"],
                "mapped":   mapped_list,
                "unmapped": dev_data["unmapped"],
            })
        systems_out.append({"name": sys_name, "devices": devs_out})

    # KPI totals
    mapped_count   = sum(1 for r in rows if r.get("status") == "MAPPED")
    unmapped_count = len(rows) - mapped_count
    total_pins     = sum(e["total"] for e in ecus_out)
    used_pins      = sum(e["used"]  for e in ecus_out)

    all_ifaces.discard("")

    return {
        "ecus":         ecus_out,
        "systems":      systems_out,
        "iface_list":   _order_set(all_ifaces, _IFACE_ORDER),
        "ecu_list":     sorted(all_ecu_names),
        "sys_list":     sorted(all_sys_names),
        "iface_colors": IFACE_COLORS,
        "default_iface_color": DEFAULT_IFACE_COLOR,
        "kpi": {
            "systems":       len(systems_out),
            "devices":       sum(len(s["devices"]) for s in systems_out),
            "routed_signals":mapped_count,
            "ecus":          len(ecus_out),
            "allocated_pins":used_pins,
            "free_pins":     total_pins - used_pins,
            "unmapped":      unmapped_count,
        },
    }


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = "\n".join([
    "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');",
    ":root{",
    "  --bg:#0d0f14;--card:#131720;--card-border:rgba(255,255,255,.10);",
    "  --shadow:0 4px 24px rgba(0,0,0,.4);",
    "  --header-from:#131720;--header-to:#1a1f2e;",
    "  --text:#e8ecf4;--muted:#8993a8;",
    "  --mapped:#22c55e;--unmapped:#ef4444;",
    "  --accent:#3b82f6;--accent-text:#60a5fa;",
    "  --radius:14px;--radius-sm:8px;",
    "  --tr:180ms cubic-bezier(.4,0,.2,1);",
    "}",
    "*{box-sizing:border-box;margin:0;padding:0}",
    "body{background:var(--bg);color:var(--text);font-family:'Inter','Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.5}",
    "::-webkit-scrollbar{width:4px;height:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:2px}",
    # header
    ".site-header{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);color:#fff;padding:40px 32px 36px;position:relative;overflow:hidden;}",
    ".site-header::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 80% 50%,rgba(6,182,212,.15) 0%,transparent 65%);}",
    ".eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(148,163,184,.9);margin-bottom:10px;}",
    ".site-header h1{font-size:clamp(1.7rem,4vw,2.8rem);font-weight:900;letter-spacing:-.03em;line-height:1.1}",
    ".subtitle{margin-top:8px;font-size:15px;color:rgba(148,163,184,.85);max-width:70ch}",
    ".generated{margin-top:14px;font-size:11px;color:rgba(100,116,139,.7)}",
    # kpi strip
    ".kpi-strip{display:flex;gap:12px;flex-wrap:wrap;padding:0 32px;margin-top:-24px;margin-bottom:4px;position:relative;z-index:10;}",
    ".kpi-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--radius);padding:14px 20px;box-shadow:0 4px 24px rgba(0,0,0,.4);min-width:120px;flex:1;max-width:200px;}",
    ".kpi-val{font-size:2rem;font-weight:900;letter-spacing:-.04em;line-height:1}",
    ".kpi-lbl{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:4px}",
    # filter bar
    ".filter-bar{position:sticky;top:0;z-index:100;background:rgba(13,15,20,.95);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid rgba(255,255,255,.06);padding:12px 32px;display:flex;gap:14px;flex-wrap:wrap;align-items:center;}",
    ".filter-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap}",
    ".filter-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);white-space:nowrap}",
    ".fb{border:1px solid rgba(255,255,255,.10);border-radius:999px;padding:4px 11px;font-size:12px;font-weight:600;cursor:pointer;background:#1a1f2e;color:#8993a8;transition:all var(--tr);white-space:nowrap;font-family:inherit;}",
    ".fb:hover{border-color:rgba(255,255,255,.20);color:#e8ecf4}",
    ".fb-reset{margin-left:auto;border:1px solid rgba(255,255,255,.10);border-radius:var(--radius-sm);padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer;background:#1a1f2e;color:#8993a8;transition:all var(--tr);font-family:inherit;}",
    ".fb-reset:hover{background:#1f2538;color:#e8ecf4}",
    # main
    ".main{padding:24px 32px 40px}",
    ".section-title{font-size:1rem;font-weight:800;letter-spacing:-.02em;margin-bottom:16px;color:#e8ecf4;display:flex;align-items:center;gap:10px;}",
    ".section-title::after{content:'';flex:1;height:1px;background:rgba(255,255,255,.10)}",
    # ECU fleet
    ".ecu-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-bottom:32px;}",
    ".ecu-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--radius);padding:18px;box-shadow:0 4px 24px rgba(0,0,0,.4);border-left:4px solid #6366f1;transition:box-shadow var(--tr);}",
    ".ecu-card:hover{box-shadow:0 8px 32px rgba(0,0,0,.5)}",
    ".ecu-name{font-size:15px;font-weight:800;letter-spacing:-.02em;margin-bottom:4px;color:#e8ecf4}",
    ".ecu-variant{font-size:11px;font-weight:600;color:var(--muted);margin-bottom:10px}",
    ".ecu-can{font-family:'JetBrains Mono',Consolas,monospace;font-size:11px;color:#f59e0b;margin-bottom:10px;min-height:16px}",
    ".util-bar-wrap{margin-bottom:8px}",
    ".util-bar-label{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:4px}",
    ".util-bar{height:8px;background:rgba(255,255,255,.08);border-radius:999px;overflow:hidden;}",
    ".util-bar-fill{height:100%;border-radius:999px;transition:width .4s ease;}",
    ".ecu-stats{display:flex;gap:10px;font-size:11px;font-weight:600;}",
    ".ecu-stat{background:#1a1f2e;border:1px solid rgba(255,255,255,.10);border-radius:6px;padding:4px 10px;text-align:center;}",
    ".ecu-stat-val{font-size:15px;font-weight:900;display:block;color:#e8ecf4}",
    ".ecu-stat-lbl{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em}",
    # system routing
    ".routing-section{margin-bottom:32px}",
    ".sys-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--radius);margin-bottom:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.4);}",
    ".sys-card-header{background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;padding:12px 18px;display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none;}",
    ".sys-card-header:hover{filter:brightness(1.08)}",
    ".sys-toggle{font-size:12px;transition:transform var(--tr);flex-shrink:0}",
    ".sys-card.open .sys-toggle{transform:rotate(90deg)}",
    ".sys-card-name{font-size:14px;font-weight:800;flex:1}",
    ".sys-card-body{padding:12px;display:none;background:rgba(255,255,255,.02);}",
    ".sys-card.open .sys-card-body{display:block}",
    ".sys-card.filtered-out{display:none}",
    # device sub-cards
    ".dev-subcard{background:#1a1f2e;border:1px solid rgba(255,255,255,.08);border-radius:10px;margin-bottom:8px;padding:12px;}",
    ".dev-subcard.filtered-out{display:none}",
    ".dev-name{font-size:12px;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;color:#e8ecf4}",
    ".dev-type-badge{font-size:10px;font-weight:700;padding:1px 7px;border-radius:999px;background:rgba(6,182,212,.15);color:#22d3ee;}",
    # ECU group inside device
    ".ecu-group{margin-bottom:8px}",
    ".ecu-group-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:5px;display:flex;align-items:center;gap:5px;}",
    ".ecu-group-label .ecu-dot{width:8px;height:8px;border-radius:50%;background:#06b6d4;display:inline-block;}",
    ".chip-wrap{display:flex;flex-wrap:wrap;gap:5px}",
    ".sig-chip{display:inline-flex;align-items:center;border-radius:6px;padding:3px 8px;font-size:10px;font-weight:600;transition:opacity var(--tr);}",
    ".sig-chip.chip-mapped{border:1px solid}",
    ".sig-chip.chip-unmapped{background:rgba(239,68,68,.12);color:#fca5a5;border:1px solid rgba(239,68,68,.25);}",
    ".sig-chip.filtered-out{display:none}",
    ".unmapped-label{font-size:10px;font-weight:700;color:#ef4444;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px;}",
    ".no-sigs{font-size:11px;color:var(--muted);font-style:italic;padding:4px 0}",
    # footer
    ".site-footer{text-align:center;padding:24px 32px;color:#5a6278;font-size:12px;border-top:1px solid rgba(255,255,255,.06);}",
    # empty
    ".empty-state{text-align:center;padding:64px 32px;color:var(--muted);}",
    ".empty-state h2{font-size:1.2rem;font-weight:700;color:var(--text);margin-bottom:8px}",
    # responsive
    "@media(max-width:900px){",
    "  .kpi-strip,.filter-bar,.main{padding-left:16px;padding-right:16px}",
    "  .site-header{padding:28px 16px 24px}",
    "  .ecu-grid{grid-template-columns:1fr 1fr}",
    "}",
    "@media(max-width:560px){.ecu-grid{grid-template-columns:1fr}}",
])

# ── JavaScript ─────────────────────────────────────────────────────────────────
# __DATA__ is replaced at render time with the serialised JSON payload.

_JS = r"""(function(){
"use strict";
var DATA=__DATA__;
var IC=DATA.iface_colors;
var DC=DATA.default_iface_color;
function ic(k){return IC[k]||DC;}
/* ── filter state ── */
var active={system:new Set(),ecu:new Set(),status:new Set(),iface:new Set()};
function anyActive(cat){return active[cat].size>0;}
function sysVisible(sysName){return!anyActive('system')||active.system.has(sysName);}
function chipVisible(chip){
  if(anyActive('status')&&!active.status.has(chip.status))return false;
  if(anyActive('iface')&&!active.iface.has(chip.iface))return false;
  return true;
}
function ecuGroupVisible(ecuName){return!anyActive('ecu')||active.ecu.has(ecuName);}
function applyFilters(){
  document.querySelectorAll('.sys-card').forEach(function(card){
    var sn=card.dataset.sys;
    if(!sysVisible(sn)){card.classList.add('filtered-out');return;}
    card.classList.remove('filtered-out');
    /* dev subcards */
    card.querySelectorAll('.dev-subcard').forEach(function(dc){
      var vis=false;
      /* ecu groups */
      dc.querySelectorAll('.ecu-group').forEach(function(grp){
        var en=grp.dataset.ecu;
        if(!ecuGroupVisible(en)){grp.style.display='none';return;}
        grp.style.display='';
        grp.querySelectorAll('.sig-chip').forEach(function(chip){
          var ok=chipVisible({status:chip.dataset.status,iface:chip.dataset.iface});
          chip.classList.toggle('filtered-out',!ok);
          if(ok)vis=true;
        });
      });
      /* unmapped chips */
      dc.querySelectorAll('.sig-chip.chip-unmapped').forEach(function(chip){
        var ok=chipVisible({status:'UNMAPPED',iface:chip.dataset.iface});
        chip.classList.toggle('filtered-out',!ok);
        if(ok)vis=true;
      });
      dc.classList.toggle('filtered-out',!vis);
    });
  });
}
/* ── DOM builders ── */
function E(tag,cls){var e=document.createElement(tag);if(cls)e.className=cls;return e;}
function T(s){return document.createTextNode(String(s==null?'':s));}
function setStyle(el,css){el.style.cssText=css;return el;}
function buildFilterBar(){
  var bar=E('div','filter-bar');
  function group(label,items,cat,colorFn){
    var g=E('div','filter-group');
    var lbl=E('span','filter-label');lbl.textContent=label+':';g.appendChild(lbl);
    var allBtn=E('button','fb');allBtn.textContent='ALL';
    setStyle(allBtn,'background:#0f172a;color:#fff;border-color:#0f172a');
    function resetAll(){
      active[cat].clear();
      g.querySelectorAll('.fb.item-btn').forEach(function(b){b.style.cssText='';b.classList.remove('active');});
      setStyle(allBtn,'background:#0f172a;color:#fff;border-color:#0f172a');
      applyFilters();
    }
    allBtn.addEventListener('click',resetAll);
    g.appendChild(allBtn);
    (items||[]).forEach(function(val){
      var col=colorFn?colorFn(val):'#0f172a';
      var btn=E('button','fb item-btn');btn.textContent=val;
      btn.addEventListener('click',function(){
        allBtn.style.cssText='';
        if(active[cat].has(val)){active[cat].delete(val);btn.style.cssText='';btn.classList.remove('active');}
        else{active[cat].add(val);btn.style.cssText='background:'+col+';color:#fff;border-color:'+col;btn.classList.add('active');}
        if(!active[cat].size)setStyle(allBtn,'background:#0f172a;color:#fff;border-color:#0f172a');
        applyFilters();
      });
      g.appendChild(btn);
    });
    return g;
  }
  var statusColor=function(s){return s==='MAPPED'?'#22c55e':'#ef4444';};
  bar.appendChild(group('System', DATA.sys_list,'system',null));
  bar.appendChild(group('ECU',    DATA.ecu_list,'ecu',null));
  bar.appendChild(group('Status', ['MAPPED','UNMAPPED'],'status',statusColor));
  bar.appendChild(group('Interface',DATA.iface_list,'iface',ic));
  var rst=E('button','fb-reset');rst.textContent='Reset Filters';
  rst.addEventListener('click',function(){
    ['system','ecu','status','iface'].forEach(function(c){active[c].clear();});
    bar.querySelectorAll('.item-btn').forEach(function(b){b.style.cssText='';b.classList.remove('active');});
    bar.querySelectorAll('.fb:not(.item-btn)').forEach(function(b){setStyle(b,'background:#0f172a;color:#fff;border-color:#0f172a');});
    applyFilters();
  });
  bar.appendChild(rst);
  return bar;
}
/* ── ECU fleet ── */
function buildEcuFleet(){
  var wrap=E('div');
  var title=E('div','section-title');title.textContent='ECU Fleet';wrap.appendChild(title);
  if(!DATA.ecus||!DATA.ecus.length){
    var e=E('p','no-sigs');e.textContent='No ECUs defined in export.';wrap.appendChild(e);return wrap;
  }
  var grid=E('div','ecu-grid');
  DATA.ecus.forEach(function(ecu){
    var card=E('div','ecu-card');
    /* name */
    var nm=E('div','ecu-name');nm.textContent=ecu.name;card.appendChild(nm);
    /* variant */
    if(ecu.variant){var vr=E('div','ecu-variant');vr.textContent=ecu.variant;card.appendChild(vr);}
    /* CAN IDs */
    var can=E('div','ecu-can');can.textContent=ecu.can_ids&&ecu.can_ids.length?ecu.can_ids.join('  '):'';card.appendChild(can);
    /* util bar */
    var ubw=E('div','util-bar-wrap');
    var ubl=E('div','util-bar-label');
    var l1=E('span');l1.textContent='Pin utilisation';
    var l2=E('span');l2.textContent=ecu.pct+'% ('+ecu.used+' / '+ecu.total+')';l2.style.fontWeight='700';
    ubl.appendChild(l1);ubl.appendChild(l2);ubw.appendChild(ubl);
    var ub=E('div','util-bar');
    var ubf=E('div','util-bar-fill');
    ubf.style.width=ecu.pct+'%';ubf.style.background=ecu.bar_color;
    ub.appendChild(ubf);ubw.appendChild(ub);card.appendChild(ubw);
    /* stats */
    var stats=E('div','ecu-stats');
    function stat(val,lbl,color){
      var s=E('div','ecu-stat');
      var v=E('span','ecu-stat-val');v.textContent=val;if(color)v.style.color=color;
      var l=E('span','ecu-stat-lbl');l.textContent=lbl;
      s.appendChild(v);s.appendChild(l);return s;
    }
    stats.appendChild(stat(ecu.used,'Used','#0f172a'));
    stats.appendChild(stat(ecu.free,'Free','#22c55e'));
    stats.appendChild(stat(ecu.total,'Total','#64748b'));
    card.appendChild(stats);
    grid.appendChild(card);
  });
  wrap.appendChild(grid);
  return wrap;
}
/* ── system routing ── */
function buildSigChip(chip){
  var s=E('span','sig-chip chip-'+chip.status.toLowerCase());
  s.dataset.status=chip.status;
  s.dataset.iface=chip.iface||'';
  s.title=chip.signal+(chip.iface?' ['+chip.iface+']':'');
  if(chip.status==='MAPPED'){
    var col=ic(chip.iface);
    s.style.background=col+'1a';s.style.color=col;s.style.borderColor=col+'44';
  }
  var label=chip.signal||'?';
  if(label.length>22)label=label.slice(0,20)+'...';
  s.textContent=label;
  return s;
}
function buildRoutingSection(){
  var wrap=E('div','routing-section');
  var title=E('div','section-title');title.textContent='System Signal Routing';wrap.appendChild(title);
  if(!DATA.systems||!DATA.systems.length){
    var e=E('p','no-sigs');e.textContent='No systems in export.';wrap.appendChild(e);return wrap;
  }
  DATA.systems.forEach(function(sys){
    var card=E('div','sys-card');
    card.dataset.sys=sys.name;
    /* header */
    var hdr=E('div','sys-card-header');
    var tog=E('span','sys-toggle');tog.innerHTML='&#9658;';hdr.appendChild(tog);
    var nm=E('span','sys-card-name');nm.textContent=sys.name;hdr.appendChild(nm);
    /* count badge */
    var total=0,mapped=0;
    sys.devices.forEach(function(d){
      d.mapped.forEach(function(g){total+=g.signals.length;mapped+=g.signals.length;});
      total+=d.unmapped.length;
    });
    var cb=E('span','fb');
    cb.style.cssText='background:rgba(255,255,255,.15);color:#fff;border-color:rgba(255,255,255,.3);font-size:11px;padding:2px 10px;';
    cb.textContent=mapped+' mapped / '+(total-mapped)+' unmapped';
    hdr.appendChild(cb);
    hdr.addEventListener('click',function(){card.classList.toggle('open');});
    card.appendChild(hdr);
    /* body */
    var body=E('div','sys-card-body');
    if(!sys.devices||!sys.devices.length){
      var np=E('p','no-sigs');np.textContent='No devices.';body.appendChild(np);
    }else{
      sys.devices.forEach(function(dev){
        var dc=E('div','dev-subcard');
        /* device header */
        var dn=E('div','dev-name');
        dn.appendChild(T(dev.name));
        if(dev.type){var tb=E('span','dev-type-badge');tb.textContent=dev.type;dn.appendChild(tb);}
        dc.appendChild(dn);
        /* mapped groups */
        dev.mapped.forEach(function(grp){
          var g=E('div','ecu-group');g.dataset.ecu=grp.ecu;
          var gl=E('div','ecu-group-label');
          var dot=E('span','ecu-dot');gl.appendChild(dot);gl.appendChild(T(grp.ecu));
          g.appendChild(gl);
          var cw=E('div','chip-wrap');
          grp.signals.forEach(function(chip){cw.appendChild(buildSigChip(chip));});
          g.appendChild(cw);
          dc.appendChild(g);
        });
        /* unmapped */
        if(dev.unmapped&&dev.unmapped.length){
          var ul=E('div','unmapped-label');ul.textContent='Unmapped';dc.appendChild(ul);
          var ucw=E('div','chip-wrap');
          dev.unmapped.forEach(function(chip){ucw.appendChild(buildSigChip(chip));});
          dc.appendChild(ucw);
        }
        if(!dev.mapped.length&&!dev.unmapped.length){
          var ns=E('p','no-sigs');ns.textContent='No signal records.';dc.appendChild(ns);
        }
        body.appendChild(dc);
      });
    }
    card.appendChild(body);
    wrap.appendChild(card);
  });
  return wrap;
}
/* ── render ── */
function render(){
  var root=document.getElementById('app');
  if(!root)return;
  root.appendChild(buildFilterBar());
  var main=E('div','main');
  main.appendChild(buildEcuFleet());
  main.appendChild(buildRoutingSection());
  root.appendChild(main);
}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',render):render();
})();"""

# ── HTML assembly ──────────────────────────────────────────────────────────────

def _kpi_card(value: int, label: str, color: str) -> str:
    return (
        '<div class="kpi-card">'
        '<div class="kpi-val" style="color:' + esc(color) + '">' + esc(str(value)) + '</div>'
        '<div class="kpi-lbl">' + esc(label) + '</div>'
        '</div>'
    )


def _render_html(data: dict, arch_name: str, source: str) -> str:
    import datetime
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    kpi = data["kpi"]

    kpis = (
        _kpi_card(kpi["systems"],        "Systems",        "#3b82f6") +
        _kpi_card(kpi["devices"],        "Devices",        "#0d9488") +
        _kpi_card(kpi["routed_signals"], "Routed Signals", "#22c55e") +
        _kpi_card(kpi["ecus"],           "ECUs",           "#06b6d4") +
        _kpi_card(kpi["allocated_pins"], "Allocated Pins", "#f59e0b") +
        _kpi_card(kpi["free_pins"],      "Free Pins",      "#64748b")
    )

    subtitle = (
        "Architecture: " + arch_name
        + " · " + str(kpi["systems"]) + " systems"
        + " · " + str(kpi["ecus"]) + " ECUs"
        + " · " + str(kpi["routed_signals"]) + " routed signals"
        + " · " + str(kpi["unmapped"]) + " unmapped"
    )

    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    js_block  = _JS.replace("__DATA__", data_json)

    parts = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\"/>",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>",
        "<title>" + esc("Architecture Topology — " + arch_name) + "</title>",
        "<style>" + _CSS + "</style>",
        "</head>",
        "<body>",
        "<header class=\"site-header\">",
        "  <div class=\"eyebrow\">E/E Architecture Design &mdash; Agricultural Machinery</div>",
        "  <h1>Architecture Topology</h1>",
        "  <div class=\"subtitle\">" + esc(subtitle) + "</div>",
        "  <div class=\"generated\">Generated " + esc(generated)
            + " &nbsp;&bull;&nbsp; Source: " + esc(source) + "</div>",
        "</header>",
        "<div class=\"kpi-strip\">",
        kpis,
        "</div>",
        "<div id=\"app\"></div>",
        "<footer class=\"site-footer\">",
        "  E/E Architect Design &mdash; Architecture Topology Report &bull; " + esc(generated),
        "</footer>",
        "<script>" + js_block + "</script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = standard_arg_parser("Generate professional Architecture Topology HTML report.")
    args   = parser.parse_args()
    cfg    = load_config(Path(args.config) if args.config else None)
    root   = resolve_root(args.root)

    src, arch = load_architecture_from_args(args, cfg, physical=False)

    try:
        source_label = str(src.relative_to(root))
    except ValueError:
        source_label = str(src)

    data    = _build_data(arch, cfg)
    content = _render_html(data, str(arch.get("name") or "Architecture"), source_label)

    out = get_output_file(root, cfg, "topology", args.output, args.outdir)
    write_text(out, content)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

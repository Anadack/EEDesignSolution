#!/usr/bin/env python3
"""E/E Architect Design — Logical Architecture HTML Report (v4, professional).

Renders a system-by-system view: sensors <- system block -> actuators.
Each device is a collapsible card listing signal rows with interface pills,
range, safety, and priority badges.  A sticky filter bar lets users narrow
by interface type, safety level, and priority.

Usage:
    python3 generate_logical_architecture_html.py --root /path/to/project
"""
from __future__ import annotations

import json
from pathlib import Path

from eec_report_common import (
    collect_allocation_rows, esc, get_output_file, iter_device_pin_records,
    iter_devices, load_architecture_from_args, load_config, normalize_token,
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

_SAFETY_ORDER   = ["QM", "AGPL_A", "AGPL_B", "AGPL_C", "AGPL_D"]
_PRIORITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_number(v: object) -> str:
    """Format a numeric value compactly, stripping unnecessary decimals."""
    try:
        f = float(v)  # type: ignore[arg-type]
        return str(int(f)) if f == int(f) else str(round(f, 4))
    except (TypeError, ValueError):
        return str(v)


def _signal_range(sig: object) -> str:
    """Return 'min - max unit' string when signal dict has range data."""
    if not isinstance(sig, dict):
        return ""
    mn   = sig.get("min_value", sig.get("min", ""))
    mx   = sig.get("max_value", sig.get("max", ""))
    unit = sig.get("unit", "")
    if mn == "" and mx == "":
        return ""
    lo = _fmt_number(mn) if mn != "" else "?"
    hi = _fmt_number(mx) if mx != "" else "?"
    return (lo + " - " + hi + (" " + str(unit) if unit else "")).strip()


def _tok(v: object) -> str:
    return normalize_token(v)


def _order_set(vals: set, reference: list) -> list:
    known   = [v for v in reference if v in vals]
    unknown = sorted(v for v in vals if v not in reference)
    return known + unknown


# ── data extraction ────────────────────────────────────────────────────────────

def _build_data(arch: dict, cfg: dict) -> dict:
    """Produce the JSON payload consumed by the embedded JavaScript renderer."""
    systems_out: list  = []
    all_ifaces:  set   = set()
    all_safety:  set   = set()
    all_prio:    set   = set()
    total_sigs   = 0
    total_devs   = 0

    for sys_obj in (arch.get("systems") or []):
        if not isinstance(sys_obj, dict):
            continue

        sys_name  = str(sys_obj.get("name") or "Unnamed System")
        sys_saf   = _tok(sys_obj.get("safety")       or "QM")
        sys_prio  = _tok(sys_obj.get("priority")     or "LOW")
        sys_sl    = str(sys_obj.get("system_level")  or "")
        sys_take  = sys_obj.get("take_rate")
        sys_mand  = bool(sys_obj.get("is_mandatory", False))
        sys_loc   = str(sys_obj.get("location")     or "")
        sys_pn    = str(sys_obj.get("part_number")  or "")

        sensors_out:   list = []
        actuators_out: list = []

        for _comp, dev, kind in iter_devices(sys_obj):
            dev_name = str(dev.get("name") or "Unknown Device")
            pins     = list(iter_device_pin_records(dev))

            sigs_out: list = []
            for rec in pins:
                sig   = rec.get("signal") or {}
                iface = _tok(rec.get("interface") or
                             (sig.get("interface") if isinstance(sig, dict) else "") or "")
                sname = signal_name(sig) or str(rec.get("name") or "")
                role  = _tok(rec.get("role") or
                             (sig.get("role") if isinstance(sig, dict) else "") or "")
                s_saf = _tok((sig.get("safety")   if isinstance(sig, dict) else "") or sys_saf)
                s_pri = _tok((sig.get("priority") if isinstance(sig, dict) else "") or sys_prio)
                rng   = _signal_range(sig if isinstance(sig, dict) else {})

                all_ifaces.add(iface)
                all_safety.add(s_saf)
                all_prio.add(s_pri)

                sigs_out.append({
                    "name":     sname,
                    "iface":    iface,
                    "role":     role,
                    "safety":   s_saf,
                    "priority": s_pri,
                    "range":    rng,
                })
                total_sigs += 1

            entry = {"name": dev_name, "signals": sigs_out, "count": len(sigs_out)}
            if "SENSOR" in kind:
                sensors_out.append(entry)
            else:
                actuators_out.append(entry)
            total_devs += 1

        all_safety.add(sys_saf)
        all_prio.add(sys_prio)

        systems_out.append({
            "name":      sys_name,
            "safety":    sys_saf,
            "priority":  sys_prio,
            "sl":        sys_sl,
            "take_rate": float(sys_take) if sys_take is not None else None,
            "mandatory": sys_mand,
            "location":  sys_loc,
            "pn":        sys_pn,
            "sensors":   sensors_out,
            "actuators": actuators_out,
        })

    # supplement interface list from allocation table
    for row in (collect_allocation_rows(arch, cfg) or []):
        iface = _tok(row.get("interface") or "")
        if iface:
            all_ifaces.add(iface)

    all_ifaces.discard("")
    all_safety.discard("")
    all_prio.discard("")

    return {
        "arch_name":           str(arch.get("name") or "Architecture"),
        "systems":             systems_out,
        "iface_list":          sorted(all_ifaces),
        "safety_list":         _order_set(all_safety, _SAFETY_ORDER),
        "prio_list":           _order_set(all_prio,   _PRIORITY_ORDER),
        "iface_colors":        IFACE_COLORS,
        "safety_colors":       dict(SAFETY_COLORS),
        "priority_colors":     PRIORITY_COLORS,
        "default_iface_color": DEFAULT_IFACE_COLOR,
        "kpi": {
            "systems": len(systems_out),
            "devices": total_devs,
            "signals": total_sigs,
            "ifaces":  len(all_ifaces),
        },
    }


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = "\n".join([
    "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');",
    ":root{",
    "  --bg:#0d0f14; --card:#131720; --card-border:rgba(255,255,255,.10);",
    "  --shadow:0 4px 24px rgba(0,0,0,.4);",
    "  --header-from:#131720; --header-to:#1a1f2e;",
    "  --text:#e8ecf4; --muted:#8993a8;",
    "  --sensor-accent:#0d9488; --actuator-accent:#d97706;",
    "  --accent:#3b82f6; --accent-text:#60a5fa;",
    "  --radius:14px; --radius-sm:8px;",
    "  --tr:180ms cubic-bezier(.4,0,.2,1);",
    "}",
    "*{box-sizing:border-box;margin:0;padding:0}",
    "body{background:var(--bg);color:var(--text);font-family:'Inter','Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.5}",
    "::-webkit-scrollbar{width:4px;height:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:2px}",
    # header
    ".site-header{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);color:#fff;padding:40px 32px 36px;position:relative;overflow:hidden;}",
    ".site-header::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 80% 50%,rgba(59,130,246,.18) 0%,transparent 65%);}",
    ".eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(148,163,184,.9);margin-bottom:10px;}",
    ".site-header h1{font-size:clamp(1.7rem,4vw,2.8rem);font-weight:900;letter-spacing:-.03em;line-height:1.1}",
    ".subtitle{margin-top:8px;font-size:15px;color:rgba(148,163,184,.85);max-width:70ch}",
    ".generated{margin-top:14px;font-size:11px;color:rgba(100,116,139,.7)}",
    # kpi strip
    ".kpi-strip{display:flex;gap:12px;flex-wrap:wrap;padding:0 32px;margin-top:-24px;margin-bottom:4px;position:relative;z-index:10;}",
    ".kpi-card{background:#131720;border:1px solid rgba(255,255,255,.10);border-radius:var(--radius);padding:14px 20px;box-shadow:0 4px 24px rgba(0,0,0,.4);min-width:130px;flex:1;max-width:220px;}",
    ".kpi-val{font-size:2rem;font-weight:900;letter-spacing:-.04em;line-height:1}",
    ".kpi-lbl{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:4px}",
    # filter bar
    ".filter-bar{position:sticky;top:0;z-index:100;background:rgba(13,15,20,.95);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid rgba(255,255,255,.06);padding:12px 32px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;}",
    ".filter-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap}",
    ".filter-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);white-space:nowrap}",
    ".fb{border:1px solid rgba(255,255,255,.10);border-radius:999px;padding:4px 11px;font-size:12px;font-weight:600;cursor:pointer;background:#1a1f2e;color:#8993a8;transition:all var(--tr);white-space:nowrap;font-family:inherit;}",
    ".fb:hover{border-color:rgba(255,255,255,.20);color:#e8ecf4}",
    ".fb-reset{margin-left:auto;border:1px solid rgba(255,255,255,.10);border-radius:var(--radius-sm);padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer;background:#1a1f2e;color:#8993a8;transition:all var(--tr);font-family:inherit;}",
    ".fb-reset:hover{background:#1f2538;color:#e8ecf4}",
    # main
    ".main{padding:24px 32px 40px}",
    # system
    ".system-section{margin-bottom:28px}",
    ".system-header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;border-radius:var(--radius) var(--radius) 0 0;padding:14px 20px;border:1px solid rgba(255,255,255,.08);}",
    ".system-name{font-size:1rem;font-weight:800;letter-spacing:-.01em}",
    ".system-meta{font-size:11px;color:rgba(148,163,184,.8);margin-left:4px}",
    ".system-body{display:grid;grid-template-columns:1fr 200px 1fr;gap:0;border:1px solid rgba(255,255,255,.10);border-top:none;border-radius:0 0 var(--radius) var(--radius);overflow:hidden;background:#131720;}",
    ".sensors-col{background:rgba(13,148,136,.08);border-right:1px solid rgba(255,255,255,.10)}",
    ".actuators-col{background:rgba(217,119,6,.08);border-left:1px solid rgba(255,255,255,.10)}",
    ".col-header{font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.10);}",
    ".sensors-col .col-header{color:#0d9488}",
    ".actuators-col .col-header{color:#d97706}",
    ".center-col{background:linear-gradient(180deg,#0f172a 0%,#1e3a5f 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px 12px;color:#fff;text-align:center;}",
    ".center-name{font-size:13px;font-weight:800;letter-spacing:-.01em;line-height:1.2}",
    ".center-sub{font-size:10px;color:rgba(148,163,184,.7);margin-top:4px}",
    ".center-counts{display:flex;gap:8px;margin-top:10px;}",
    ".center-count{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);border-radius:6px;padding:4px 10px;text-align:center;}",
    ".cc-val{font-weight:800;font-size:14px}",
    ".cc-lbl{font-size:9px;color:rgba(148,163,184,.7);text-transform:uppercase;letter-spacing:.05em}",
    # device cards
    ".device-list{padding:8px}",
    ".device-card{background:#1a1f2e;border-radius:var(--radius-sm);border:1px solid rgba(255,255,255,.10);margin-bottom:6px;overflow:hidden;transition:box-shadow var(--tr);}",
    ".device-card:hover{box-shadow:0 2px 12px rgba(0,0,0,.4)}",
    ".sensors-col .device-card{border-left:3px solid #0d9488}",
    ".actuators-col .device-card{border-left:3px solid #d97706}",
    ".device-card-header{display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;user-select:none;}",
    ".device-card-header:hover{background:rgba(255,255,255,.03)}",
    ".device-toggle{color:var(--muted);font-size:12px;transition:transform var(--tr);flex-shrink:0}",
    ".device-card.open .device-toggle{transform:rotate(90deg)}",
    ".device-name{font-size:12px;font-weight:700;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e8ecf4}",
    ".device-pin-count{font-size:11px;font-weight:600;color:#8993a8;background:rgba(255,255,255,.06);border-radius:999px;padding:2px 8px;flex-shrink:0;}",
    ".device-signals{padding:0 10px 8px;display:none}",
    ".device-card.open .device-signals{display:block}",
    # signal rows
    ".signal-row{display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap;padding:5px 2px;border-bottom:1px solid rgba(255,255,255,.06);font-size:11px;}",
    ".signal-row:last-child{border-bottom:none}",
    ".signal-row.hidden{display:none}",
    ".pill-iface{display:inline-flex;align-items:center;border-radius:999px;padding:2px 8px;font-size:10px;font-weight:700;color:#fff;flex-shrink:0;white-space:nowrap;}",
    ".signal-name{font-family:'JetBrains Mono',Consolas,monospace;font-size:10.5px;font-weight:700;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e8ecf4;}",
    ".badge{display:inline-flex;align-items:center;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;border:1px solid;flex-shrink:0;white-space:nowrap;}",
    ".badge-role{background:rgba(255,255,255,.06);color:#8993a8;border-color:rgba(255,255,255,.10)}",
    ".badge-range{background:rgba(255,255,255,.06);color:#8993a8;border-color:rgba(255,255,255,.10);font-family:'JetBrains Mono',monospace}",
    ".no-device{padding:20px;text-align:center;color:#5a6278;font-size:12px;font-style:italic;}",
    ".all-hidden-msg{padding:10px;text-align:center;color:#5a6278;font-size:11px;font-style:italic;display:none;}",
    # footer
    ".site-footer{text-align:center;padding:24px 32px;color:#5a6278;font-size:12px;border-top:1px solid rgba(255,255,255,.06);}",
    # empty
    ".empty-state{text-align:center;padding:64px 32px;color:var(--muted);}",
    ".empty-state h2{font-size:1.2rem;font-weight:700;color:var(--text);margin-bottom:8px}",
    # responsive
    "@media(max-width:900px){",
    "  .system-body{grid-template-columns:1fr}",
    "  .sensors-col{border-right:none;border-bottom:1px solid rgba(255,255,255,.10)}",
    "  .actuators-col{border-left:none;border-top:1px solid rgba(255,255,255,.10)}",
    "  .center-col{border-top:1px solid rgba(255,255,255,.1);border-bottom:1px solid rgba(255,255,255,.1)}",
    "  .kpi-strip,.filter-bar,.main{padding-left:16px;padding-right:16px}",
    "  .site-header{padding:28px 16px 24px}",
    "}",
])

# ── JavaScript ─────────────────────────────────────────────────────────────────
# __DATA__ is replaced at render time with the serialised JSON payload.

_JS = r"""(function(){
"use strict";
var DATA=__DATA__;
var IC=DATA.iface_colors;
var DC=DATA.default_iface_color;
var SM={QM:'#22c55e',AGPL_A:'#84cc16',AGPL_B:'#eab308',AGPL_C:'#f97316',AGPL_D:'#ef4444'};
var PM={LOW:'#64748b',MEDIUM:'#3b82f6',HIGH:'#f59e0b',CRITICAL:'#ef4444'};
function ic(k){return IC[k]||DC;}
function sc(k){return SM[k]||'#64748b';}
function pc(k){return PM[k]||'#64748b';}
var active={iface:new Set(),safety:new Set(),priority:new Set()};
function passes(row){
  var d=row.dataset;
  if(active.iface.size&&!active.iface.has(d.iface))return false;
  if(active.safety.size&&!active.safety.has(d.safety))return false;
  if(active.priority.size&&!active.priority.has(d.prio))return false;
  return true;
}
function applyFilters(){
  document.querySelectorAll('.device-card').forEach(function(card){
    var rows=card.querySelectorAll('.signal-row');
    var vis=0;
    rows.forEach(function(r){var ok=passes(r);r.classList.toggle('hidden',!ok);if(ok)vis++;});
    card.style.opacity=vis||!rows.length?'':'.4';
    var m=card.querySelector('.all-hidden-msg');
    if(m)m.style.display=(!vis&&rows.length)?'block':'none';
  });
}
function E(tag,cls,html){
  var e=document.createElement(tag);
  if(cls)e.className=cls;
  if(html!==undefined)e.innerHTML=html;
  return e;
}
function T(s){return document.createTextNode(String(s==null?'':s));}
function pill(iface){
  var s=E('span','pill-iface');s.style.background=ic(iface);s.appendChild(T(iface||'?'));return s;
}
function badge(text,cls,color){
  var s=E('span','badge '+cls);
  if(color){s.style.color=color;s.style.borderColor=color+'44';s.style.background=color+'1a';}
  s.appendChild(T(text));return s;
}
function sigRow(sig){
  var r=E('div','signal-row');
  r.dataset.iface=sig.iface||'';r.dataset.safety=sig.safety||'';r.dataset.prio=sig.priority||'';
  r.appendChild(pill(sig.iface));
  r.appendChild(Object.assign(E('span','signal-name'),{textContent:sig.name||'?'}));
  if(sig.role)r.appendChild(badge(sig.role,'badge-role'));
  if(sig.range)r.appendChild(badge(sig.range,'badge-range'));
  if(sig.safety)r.appendChild(badge(sig.safety,'badge badge-safety',sc(sig.safety)));
  if(sig.priority)r.appendChild(badge(sig.priority,'badge badge-priority',pc(sig.priority)));
  return r;
}
function devCard(dev){
  var card=E('div','device-card');
  var hdr=E('div','device-card-header');
  var tog=E('span','device-toggle','&#9658;');
  hdr.appendChild(tog);
  hdr.appendChild(Object.assign(E('span','device-name'),{textContent:dev.name}));
  hdr.appendChild(Object.assign(E('span','device-pin-count'),{textContent:dev.count+' pins'}));
  card.appendChild(hdr);
  var body=E('div','device-signals');
  if(!dev.signals||!dev.signals.length){
    body.appendChild(Object.assign(E('div','no-device'),{textContent:'No signal records'}));
  }else{
    dev.signals.forEach(function(s){body.appendChild(sigRow(s));});
    body.appendChild(Object.assign(E('div','all-hidden-msg'),{textContent:'All signals hidden by filters'}));
  }
  card.appendChild(body);
  hdr.addEventListener('click',function(){card.classList.toggle('open');});
  return card;
}
function devList(devs,empty){
  var wrap=E('div','device-list');
  if(!devs||!devs.length){wrap.appendChild(Object.assign(E('div','no-device'),{textContent:empty}));return wrap;}
  devs.forEach(function(d){wrap.appendChild(devCard(d));});
  return wrap;
}
function colorBadge(text,colorFn){
  var c=colorFn(text);
  var s=E('span','badge');
  s.style.color=c;s.style.borderColor=c+'44';s.style.background=c+'1a';
  s.appendChild(T(text));return s;
}
function sysSection(sys){
  var wrap=E('div','system-section');
  /* header */
  var hdr=E('div','system-header');
  hdr.appendChild(Object.assign(E('span','system-name'),{textContent:sys.name}));
  if(sys.safety)hdr.appendChild(colorBadge(sys.safety,sc));
  if(sys.priority)hdr.appendChild(colorBadge(sys.priority,pc));
  if(sys.sl)hdr.appendChild(Object.assign(E('span','badge badge-role'),{textContent:sys.sl}));
  var meta=[];
  if(sys.take_rate!=null)meta.push('TR: '+(sys.take_rate*100).toFixed(0)+'%');
  if(sys.mandatory)meta.push('MANDATORY');
  if(sys.location)meta.push(sys.location);
  if(sys.pn)meta.push(sys.pn);
  if(meta.length)hdr.appendChild(Object.assign(E('span','system-meta'),{textContent:meta.join(' · ')}));
  wrap.appendChild(hdr);
  /* 3-col body */
  var body=E('div','system-body');
  /* sensors */
  var sc2=E('div','sensors-col');
  var sh=E('div','col-header');sh.innerHTML='&#9650; Sensors <span style="color:#64748b;font-weight:500">('+sys.sensors.length+')</span>';
  sc2.appendChild(sh);sc2.appendChild(devList(sys.sensors,'No sensors'));
  body.appendChild(sc2);
  /* center */
  var cc=E('div','center-col');
  cc.appendChild(Object.assign(E('div','center-name'),{textContent:sys.name}));
  if(sys.sl)cc.appendChild(Object.assign(E('div','center-sub'),{textContent:sys.sl}));
  var cnts=E('div','center-counts');
  function cnt(v,lbl){var d=E('div','center-count');d.innerHTML='<div class="cc-val">'+v+'</div><div class="cc-lbl">'+lbl+'</div>';return d;}
  cnts.appendChild(cnt(sys.sensors.length,'Sensors'));
  cnts.appendChild(cnt(sys.actuators.length,'Actuators'));
  cc.appendChild(cnts);
  body.appendChild(cc);
  /* actuators */
  var ac=E('div','actuators-col');
  var ah=E('div','col-header');ah.innerHTML='&#9660; Actuators <span style="color:#64748b;font-weight:500">('+sys.actuators.length+')</span>';
  ac.appendChild(ah);ac.appendChild(devList(sys.actuators,'No actuators'));
  body.appendChild(ac);
  wrap.appendChild(body);
  return wrap;
}
function filterBar(){
  var bar=E('div','filter-bar');
  function group(label,items,cat,colorFn){
    var g=E('div','filter-group');
    g.appendChild(Object.assign(E('span','filter-label'),{textContent:label+':'}));
    var allBtn=E('button','fb');
    allBtn.textContent='ALL';
    allBtn.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';
    function resetAll(){
      active[cat].clear();
      g.querySelectorAll('.fb.item-btn').forEach(function(b){b.style.background='';b.style.color='';b.style.borderColor='';b.classList.remove('active');});
      allBtn.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';
      applyFilters();
    }
    allBtn.addEventListener('click',resetAll);
    g.appendChild(allBtn);
    items.forEach(function(val){
      var col=colorFn(val);
      var btn=E('button','fb item-btn');
      btn.textContent=val;
      btn.addEventListener('click',function(){
        allBtn.style.cssText='';
        if(active[cat].has(val)){
          active[cat].delete(val);
          btn.style.background='';btn.style.color='';btn.style.borderColor='';btn.classList.remove('active');
        }else{
          active[cat].add(val);
          btn.style.background=col;btn.style.color='#fff';btn.style.borderColor=col;btn.classList.add('active');
        }
        if(!active[cat].size){allBtn.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';}
        applyFilters();
      });
      g.appendChild(btn);
    });
    return g;
  }
  bar.appendChild(group('Interface',DATA.iface_list,'iface',ic));
  bar.appendChild(group('Safety',DATA.safety_list,'safety',sc));
  bar.appendChild(group('Priority',DATA.prio_list,'priority',pc));
  var rst=E('button','fb-reset');rst.textContent='Reset Filters';
  rst.addEventListener('click',function(){
    ['iface','safety','priority'].forEach(function(cat){active[cat].clear();});
    bar.querySelectorAll('.item-btn').forEach(function(b){b.style.background='';b.style.color='';b.style.borderColor='';b.classList.remove('active');});
    bar.querySelectorAll('.fb:not(.item-btn)').forEach(function(b){b.style.cssText='background:#0f172a;color:#fff;border-color:#0f172a';});
    applyFilters();
  });
  bar.appendChild(rst);
  return bar;
}
function render(){
  var root=document.getElementById('app');
  if(!root)return;
  root.appendChild(filterBar());
  var main=E('div','main');
  if(!DATA.systems||!DATA.systems.length){
    var es=E('div','empty-state');
    es.appendChild(Object.assign(E('h2'),{textContent:'No systems found'}));
    es.appendChild(Object.assign(E('p'),{textContent:'Architecture export contains no system definitions.'}));
    main.appendChild(es);
  }else{
    DATA.systems.forEach(function(s){main.appendChild(sysSection(s));});
  }
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
        _kpi_card(kpi["systems"],  "Systems",     "#3b82f6") +
        _kpi_card(kpi["devices"],  "Devices",     "#0d9488") +
        _kpi_card(kpi["signals"],  "Signal Pins", "#8b5cf6") +
        _kpi_card(kpi["ifaces"],   "Interfaces",  "#f59e0b")
    )

    subtitle = (
        "Architecture: " + arch_name
        + " · " + str(kpi["systems"]) + " systems"
        + " · " + str(kpi["devices"]) + " devices"
        + " · " + str(kpi["signals"]) + " signal pins"
    )

    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    js_block  = _JS.replace("__DATA__", data_json)

    # Build HTML using string concatenation (no f-string for template)
    parts = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\"/>",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>",
        "<title>" + esc("Logical Architecture — " + arch_name) + "</title>",
        "<style>" + _CSS + "</style>",
        "</head>",
        "<body>",
        "<header class=\"site-header\">",
        "  <div class=\"eyebrow\">E/E Architecture Design &mdash; Agricultural Machinery</div>",
        "  <h1>Logical Architecture</h1>",
        "  <div class=\"subtitle\">" + esc(subtitle) + "</div>",
        "  <div class=\"generated\">Generated " + esc(generated)
            + " &nbsp;&bull;&nbsp; Source: " + esc(source) + "</div>",
        "</header>",
        "<div class=\"kpi-strip\">",
        kpis,
        "</div>",
        "<div id=\"app\"></div>",
        "<footer class=\"site-footer\">",
        "  E/E Architect Design &mdash; Logical Architecture Report &bull; " + esc(generated),
        "</footer>",
        "<script>" + js_block + "</script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = standard_arg_parser("Generate professional Logical Architecture HTML report.")
    args   = parser.parse_args()
    cfg    = load_config(Path(args.config) if args.config else None)
    root   = resolve_root(args.root)

    src, arch = load_architecture_from_args(args, cfg, physical=False)

    try:
        source_label = str(src.relative_to(root))
    except ValueError:
        source_label = str(src)

    data    = _build_data(arch, cfg)
    content = _render_html(data, data["arch_name"], source_label)

    out = get_output_file(root, cfg, "logical_architecture", args.output, args.outdir)
    write_text(out, content)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""E/E Architect Design — single-file architecture console.

Bundles every report already produced by the pipeline (generated_doc/exports,
generated_doc/architecture_html, generated_doc/system_viewer) into one
self-contained HTML file: a sidebar + workspace + tab console with live
framework KPIs, instant search, and per-report open/download actions.

Each report is embedded as base64 inside a JSON <script> blob and decoded
client-side into a sandboxed iframe, so the output is a single portable
.html file with zero external dependencies. Run this last in the pipeline —
it only includes reports that already exist on disk; anything missing is
skipped (and reported), never invented.
"""
from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from eec_archdoc_common import (
    make_argparser, cli_context, esc,
    iter_systems, iter_ecus, flatten_components, build_signal_index,
)
from eec_design import gen_base_css

SCRIPT_NAME = "generate_architecture_console_html.py"

# ---------------------------------------------------------------------------
# Workspace taxonomy — each tab points at a real file under generated_doc/.
# Files missing on disk at generation time are skipped automatically (see
# collect_workspaces); nothing here is invented, only curated/labelled.
# ---------------------------------------------------------------------------
WORKSPACES: list[dict[str, Any]] = [
    {
        "id": "overview",
        "title": "Executive Overview",
        "intent": "Program-level snapshot: platform scope, data completeness, cost estimate and the full document index.",
        "tabs": [
            {"file": "final_architecture_document.html", "dir": "architecture_html", "title": "Final Architecture Document", "description": "Consolidated narrative design document: scope, systems, ECUs/network, signals, power, safety, wiring and completeness."},
            {"file": "system_overview.html", "dir": "architecture_html", "title": "System Overview", "description": "Platform snapshot — systems, ECUs, buses and devices at a glance."},
            {"file": "architecture_documentation_index.html", "dir": "architecture_html", "title": "Documentation Index", "description": "Linked index of every generated architecture document."},
            {"file": "architecture_completeness_report.html", "dir": "architecture_html", "title": "Completeness Report", "description": "Data-quality scoring across signals, pins, connectors and traceability."},
            {"file": "architecture_estimation.html", "dir": "exports", "title": "Cost & Effort Estimation", "description": "Engineering estimation derived from system signal counts and design rules."},
        ],
    },
    {
        "id": "architecture",
        "title": "System Architecture & Allocation",
        "intent": "Structural decomposition of the platform and signal-to-ECU pin allocation.",
        "tabs": [
            {"file": "architecture_tree.html", "dir": "exports", "title": "Architecture Tree", "description": "Hierarchical tree of systems, components and devices."},
            {"file": "logical_architecture.html", "dir": "exports", "title": "Logical Architecture", "description": "Logical view of systems, ECUs and signal interconnects."},
            {"file": "architecture_allocation_matrix.html", "dir": "exports", "title": "Allocation Matrix", "description": "Signal-to-ECU-pin allocation matrix with free/used pin tracking."},
            {"file": "architecture_pinouts_stacked.html", "dir": "exports", "title": "Pinouts (Stacked)", "description": "All ECU pinouts stacked into one scrollable view."},
        ],
    },
    {
        "id": "network",
        "title": "Network & Communication",
        "intent": "Bus topology, backbone wiring and the cross-system communication matrix.",
        "tabs": [
            {"file": "architecture_bus_backbone.html", "dir": "exports", "title": "Bus Backbone", "description": "Physical backbone diagram of CAN/LIN/Ethernet buses."},
            {"file": "architecture_bus_diagram.html", "dir": "exports", "title": "Bus Diagram", "description": "Bus-centric diagram of ECUs and drop connections."},
            {"file": "architecture_topology.html", "dir": "exports", "title": "Network Topology", "description": "Network topology across all communication buses."},
            {"file": "communication_matrix.html", "dir": "architecture_html", "title": "Communication Matrix", "description": "Message/signal matrix across bus interfaces."},
            {"file": "network_diagram.html", "dir": "architecture_html", "title": "Network Diagram", "description": "Bus rails with ECU chips, multi-bus badges, zone grouping and connection legends."},
            {"file": "network_schematic_diagram.html", "dir": "architecture_html", "title": "Network Schematic Diagram", "description": "Freeform IC-chip canvas with ECUs, networked devices, variant clustering and optional manual annotations."},
            {"file": "ecu_dataflow_diagram.html", "dir": "architecture_html", "title": "ECU Network Dataflow Diagram", "description": "Interactive bus-deck canvas — pan/zoom, search and click-a-bus-to-highlight, auto-laid-out from the real export."},
        ],
    },
    {
        "id": "wiring",
        "title": "Wiring, Connectors & Pinouts",
        "intent": "Harness book, connector pinouts and per-ECU physical pin tables.",
        "tabs": [
            {"file": "connector_view.html", "dir": "architecture_html", "title": "Connector & Pin View", "description": "Interactive connector picker with per-pin detail."},
            {"file": "harness_connector_book.html", "dir": "architecture_html", "title": "Harness & Connector Book", "description": "Full harness book: connectors, cavities and mating parts."},
            {"file": "wiring_netlist.html", "dir": "architecture_html", "title": "Wiring Netlist", "description": "Point-to-point netlist of every wired connection."},
            {"file": "architecture_wiring_diagram.html", "dir": "exports", "title": "Wiring Diagram", "description": "Overall wiring overview across the platform."},
            {"file": "library_ecu_pinouts.html", "dir": "exports", "title": "Library ECU Pinouts", "description": "Pinout reference for every ECU in the component library."},
            {"file": "AEC_LARGE_01_pinout.html", "dir": "exports", "title": "AEC_LARGE_01 Pinout", "description": "Physical pinout for ECU AEC_LARGE_01."},
            {"file": "AEC_MEDIUM_01_pinout.html", "dir": "exports", "title": "AEC_MEDIUM_01 Pinout", "description": "Physical pinout for ECU AEC_MEDIUM_01."},
            {"file": "AEC_SMALL_01_pinout.html", "dir": "exports", "title": "AEC_SMALL_01 Pinout", "description": "Physical pinout for ECU AEC_SMALL_01."},
            {"file": "VALIDATION_IO_ECU_pinout.html", "dir": "exports", "title": "VALIDATION_IO_ECU Pinout", "description": "Physical pinout for the validation I/O ECU."},
        ],
    },
    {
        "id": "power",
        "title": "Power & Grounding",
        "intent": "Power distribution tree and grounding architecture.",
        "tabs": [
            {"file": "power_distribution.html", "dir": "architecture_html", "title": "Power Distribution", "description": "Power source-to-load distribution tree."},
            {"file": "grounding_architecture.html", "dir": "architecture_html", "title": "Grounding Architecture", "description": "Ground points, return paths and bonding."},
        ],
    },
    {
        "id": "dataflow",
        "title": "Functional Dataflow",
        "intent": "Signal flow across systems, from sensor input to actuator output.",
        "tabs": [
            {"file": "dataflow_context_diagram.html", "dir": "architecture_html", "title": "Dataflow Context", "description": "Context-level dataflow across the whole platform."},
            {"file": "dataflow_system_diagram.html", "dir": "architecture_html", "title": "Dataflow per System", "description": "Per-system sensor → ECU → actuator dataflow diagrams."},
            {"file": "dataflow_signal_detail.html", "dir": "architecture_html", "title": "Dataflow Signal Detail", "description": "Signal-level dataflow drill-down."},
            {"file": "architecture_signal_flow.html", "dir": "exports", "title": "Signal Flow", "description": "Signal flow across ECUs and buses."},
            {"file": "architecture_signal_flow_v2.html", "dir": "exports", "title": "Signal Flow v2", "description": "Alternate signal-flow layout."},
        ],
    },
    {
        "id": "signals",
        "title": "Signal Catalog & Naming",
        "intent": "The full signal dictionary and the project naming-convention reference.",
        "tabs": [
            {"file": "signal_dictionary.html", "dir": "architecture_html", "title": "Signal Dictionary", "description": "Every signal: interface, unit, priority, safety, range."},
            {"file": "signal_naming_convention.html", "dir": "architecture_html", "title": "Naming Convention", "description": "SYSTEM_Function_[POSITION_]TYPE naming rules and validation."},
        ],
    },
    {
        "id": "safety",
        "title": "Safety, Diagnostics & Change Control",
        "intent": "Safety concept traceability, diagnostics coverage and variant/change tracking.",
        "tabs": [
            {"file": "diagnostics_matrix.html", "dir": "architecture_html", "title": "Diagnostics Matrix", "description": "Diagnostic coverage per pin and signal."},
            {"file": "safety_concept_trace.html", "dir": "architecture_html", "title": "Safety Concept Trace", "description": "AgPL / safety-related signal traceability."},
            {"file": "variant_option_matrix.html", "dir": "architecture_html", "title": "Variant/Option Matrix", "description": "Variant codes and optional-content mapping."},
            {"file": "change_impact_report.html", "dir": "architecture_html", "title": "Change Impact Report", "description": "Impact analysis between architecture revisions."},
        ],
    },
    {
        "id": "configurator",
        "title": "System Configurator & I/O Sizing",
        "intent": "Interactive system selector and ECU I/O reservation sizing tool.",
        "tabs": [
            {"file": "index.html", "dir": "system_viewer", "title": "System Configuration Viewer", "description": "Pick systems, compare alternative/cumulative I/O sizing, inspect every pin."},
        ],
    },
]


def collect_workspaces(root: Path, workspaces_def: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    gendir = root / "generated_doc"
    out_workspaces: list[dict[str, Any]] = []
    views: dict[str, str] = {}
    skipped: list[str] = []
    for ws in workspaces_def:
        tabs: list[dict[str, Any]] = []
        for tab in ws["tabs"]:
            path = gendir / tab["dir"] / tab["file"]
            if not path.is_file():
                skipped.append(f"{tab['dir']}/{tab['file']}")
                continue
            raw = path.read_bytes()
            views[tab["file"]] = base64.b64encode(raw).decode("ascii")
            tabs.append({
                "file": tab["file"],
                "dir": tab["dir"],
                "title": tab["title"],
                "description": tab["description"],
                "size_kb": round(len(raw) / 1024, 1),
            })
        if tabs:
            out_workspaces.append({"id": ws["id"], "title": ws["title"], "intent": ws["intent"], "tabs": tabs})
    return out_workspaces, views, skipped


def gather_kpis(arch: dict[str, Any]) -> list[dict[str, str]]:
    systems = list(iter_systems(arch))
    ecus = list(iter_ecus(arch))
    devices = sum(len(flatten_components(s)) for s in systems)
    signals = len(build_signal_index(arch))
    buses = arch.get("buses", []) if isinstance(arch.get("buses"), list) else []
    alloc = arch.get("allocation_summary", {}) if isinstance(arch.get("allocation_summary"), dict) else {}
    pct = alloc.get("allocation_percent")
    pct_str = f"{pct:.1f}% used" if isinstance(pct, (int, float)) else ""
    return [
        {"label": "Systems", "value": str(len(systems))},
        {"label": "ECUs", "value": str(len(ecus))},
        {"label": "Devices", "value": str(devices)},
        {"label": "Signals", "value": str(signals)},
        {"label": "Buses", "value": str(len(buses))},
        {"label": "Pins", "value": f"{alloc.get('allocated_pins', '—')}/{alloc.get('total_pins', '—')}", "sub": pct_str},
    ]


def json_for_html(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render_html(project_title: str, arch_name: str, kpis: list[dict[str, str]],
                 workspaces: list[dict[str, Any]], views: dict[str, str],
                 source_file: str, generated: str) -> str:
    total_kb = sum(t["size_kb"] for ws in workspaces for t in ws["tabs"])
    total_reports = sum(len(ws["tabs"]) for ws in workspaces)
    total_size_label = f"{total_kb / 1024:.1f} MB" if total_kb >= 1024 else f"{total_kb:.0f} KB"

    kpi_html = "".join(
        f'<div class="kpi-chip"><span class="v">{esc(k["value"])}</span>'
        f'<span class="l">{esc(k["label"])}{(" · " + esc(k["sub"])) if k.get("sub") else ""}</span></div>'
        for k in kpis
    )

    title = esc(f"{project_title} — Architecture Console")

    console_css = """
html,body{height:100%}
body{overflow:hidden}
.console{display:flex;flex-direction:column;height:100vh;font-family:var(--font-primary)}

.console-topbar{display:flex;align-items:center;gap:var(--spacing-element-gap);padding:10px var(--spacing-page-padding-sm);background:linear-gradient(180deg,var(--dark-surface1),var(--dark-surface2));border-bottom:1px solid var(--dark-border1);box-shadow:var(--shadow-md);flex-wrap:wrap;flex-shrink:0}
.console-brand{display:flex;align-items:baseline;gap:9px;white-space:nowrap}
.console-brand .kicker{font-size:.68rem;text-transform:uppercase;letter-spacing:.12em;color:var(--accent-cyan);font-weight:800}
.console-brand h1{font-size:1.05rem;margin:0;letter-spacing:-.01em;color:var(--text-primary);font-weight:800}

.console-kpis{display:flex;gap:8px;flex-wrap:wrap;flex:1;min-width:0}
.kpi-chip{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:60px;padding:4px 10px;border-radius:var(--radius-md);background:var(--dark-surface3);border:1px solid var(--dark-border1)}
.kpi-chip .v{font-weight:800;font-size:.92rem;color:var(--accent-cyan);line-height:1.15}
.kpi-chip .l{font-size:.6rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim);font-weight:700;white-space:nowrap}

.console-search{position:relative;min-width:220px}
.console-search input{width:100%;padding:8px 34px 8px 32px;border-radius:var(--radius-full);border:1px solid var(--dark-border2);background:var(--dark-surface3);color:var(--text-primary);font-size:.85rem}
.console-search input:focus{border-color:var(--accent-cyan);outline:none}
.console-search svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--text-dim);pointer-events:none}
.console-search kbd{position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:.64rem;color:var(--text-fade);border:1px solid var(--dark-border1);border-radius:4px;padding:1px 5px;font-family:var(--font-mono)}

.console-body{display:flex;flex:1;min-height:0}

.console-sidebar{width:var(--layout-sidebar-width);flex-shrink:0;overflow-y:auto;background:var(--dark-surface1);border-right:1px solid var(--dark-border1);padding:10px}
.ws-group{margin-bottom:3px;border-radius:var(--radius-md);overflow:hidden}
.ws-group.hidden{display:none}
.ws-head{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:9px 10px;border-radius:var(--radius-md);cursor:pointer;background:transparent;border:none;color:var(--text-secondary);font-weight:700;font-size:.84rem;transition:background .12s}
.ws-head:hover{background:var(--dark-surface2)}
.ws-group.active>.ws-head{color:var(--accent-cyan);background:var(--dark-surface2)}
.ws-head .chev{transition:transform .15s;flex-shrink:0;color:var(--text-fade)}
.ws-group.collapsed .ws-head .chev{transform:rotate(-90deg)}
.ws-head .ws-title{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ws-head .ws-count{font-size:.66rem;color:var(--text-fade);background:var(--dark-surface3);border-radius:var(--radius-full);padding:1px 7px;font-weight:700}

.ws-tabs{display:flex;flex-direction:column;gap:2px;padding:2px 4px 8px 26px}
.ws-group.collapsed .ws-tabs{display:none}
.ws-tab{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;padding:7px 9px;border-radius:var(--radius-sm);cursor:pointer;background:transparent;border:1px solid transparent;color:var(--text-tertiary);font-size:.78rem;text-align:left}
.ws-tab:hover{background:var(--dark-surface2);color:var(--text-primary)}
.ws-tab.hidden{display:none}
.ws-tab.active{background:rgba(46,230,255,.1);border-color:var(--accent-cyan);color:var(--accent-cyan);font-weight:700}
.ws-tab-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ws-tab-size{flex-shrink:0;font-size:.64rem;color:var(--text-fade)}

.console-stage{flex:1;display:flex;flex-direction:column;min-width:0;min-height:0;padding:14px 16px;gap:10px}
.stage-header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.stage-header h2{margin:0;font-size:1.25rem;color:var(--text-primary);letter-spacing:-.01em}
.stage-header p{margin:4px 0 0;color:var(--text-secondary);font-size:.85rem;max-width:80ch}
.stage-meta{font-size:.78rem;color:var(--text-dim);white-space:nowrap}

.tabstrip{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;flex-shrink:0}
.tabstrip-btn{flex-shrink:0;padding:7px 13px;border-radius:var(--radius-full);border:1px solid var(--dark-border1);background:var(--dark-surface2);color:var(--text-secondary);font-size:.8rem;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .12s}
.tabstrip-btn:hover{border-color:var(--accent-cyan);color:var(--accent-cyan)}
.tabstrip-btn.active{background:var(--accent-cyan);border-color:var(--accent-cyan);color:#06222b}

.frame-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-shrink:0}
.frame-toolbar .meta{font-size:.78rem;color:var(--text-dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:8px}
.frame-toolbar .status{color:var(--accent-orange);font-weight:700}
.frame-actions{display:flex;gap:8px;flex-shrink:0}

.frame-wrap{flex:1;min-height:0;border-radius:var(--radius-lg);overflow:hidden;border:1px solid var(--dark-border1);box-shadow:var(--shadow-md);background:var(--dark-bg)}
.frame-wrap iframe{width:100%;height:100%;border:0;background:var(--dark-bg)}

.console-footer{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:7px 16px;font-size:.72rem;color:var(--text-fade);border-top:1px solid var(--dark-border1);background:var(--dark-surface1);flex-shrink:0}

@media(max-width:1100px){.console-kpis{display:none}}
@media(max-width:900px){.console-body{flex-direction:column}.console-sidebar{width:100%;max-height:38vh;border-right:none;border-bottom:1px solid var(--dark-border1)}}
"""

    js = r"""
const WORKSPACES = JSON.parse(document.getElementById('eec-workspaces').textContent);
const VIEWS = JSON.parse(document.getElementById('eec-views').textContent);
const cache = new Map();
const state = { ws: null, tab: null };

function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function fmtSize(kb){return kb>=1024 ? (kb/1024).toFixed(1)+' MB' : kb.toFixed(0)+' KB';}
function b64ToUtf8(b64){const bin=atob(b64);const bytes=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);return new TextDecoder('utf-8').decode(bytes);}
function getView(file){if(cache.has(file))return cache.get(file);const html=b64ToUtf8(VIEWS[file]||'');cache.set(file,html);return html;}
function findTab(file){for(const ws of WORKSPACES)for(const t of ws.tabs)if(t.file===file)return {ws,tab:t};return null;}

function renderSidebar(){
  const root=document.getElementById('sidebarTree');
  root.innerHTML=WORKSPACES.map(ws=>`
    <div class="ws-group" data-ws="${ws.id}">
      <button type="button" class="ws-head" data-ws-head="${ws.id}">
        <svg class="chev" viewBox="0 0 24 24" width="13" height="13"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span class="ws-title">${esc(ws.title)}</span>
        <span class="ws-count">${ws.tabs.length}</span>
      </button>
      <div class="ws-tabs">
        ${ws.tabs.map(t=>`<button type="button" class="ws-tab" data-file="${esc(t.file)}"><span class="ws-tab-title">${esc(t.title)}</span><span class="ws-tab-size">${fmtSize(t.size_kb)}</span></button>`).join('')}
      </div>
    </div>`).join('');
  root.querySelectorAll('.ws-head').forEach(btn=>btn.addEventListener('click',()=>onWsHeadClick(btn.dataset.wsHead)));
  root.querySelectorAll('.ws-tab').forEach(btn=>btn.addEventListener('click',()=>selectTab(btn.dataset.file)));
}

function onWsHeadClick(wsId){
  const ws=WORKSPACES.find(w=>w.id===wsId);
  const group=document.querySelector(`.ws-group[data-ws="${wsId}"]`);
  if(state.ws===wsId){group.classList.toggle('collapsed');}
  else{group.classList.remove('collapsed');selectTab(ws.tabs[0].file);}
}

function selectTab(file){
  const found=findTab(file);
  if(!found)return;
  state.ws=found.ws.id;state.tab=file;
  document.querySelectorAll('.ws-group').forEach(g=>g.classList.toggle('active',g.dataset.ws===found.ws.id));
  const activeGroup=document.querySelector(`.ws-group[data-ws="${found.ws.id}"]`);
  if(activeGroup)activeGroup.classList.remove('collapsed');
  document.querySelectorAll('.ws-tab').forEach(b=>b.classList.toggle('active',b.dataset.file===file));
  renderStageHeader(found.ws);
  renderTabStrip(found.ws,file);
  loadFrame(found.tab);
  history.replaceState(null,'',`#${found.ws.id}/${file}`);
}

function renderStageHeader(ws){
  document.getElementById('wsTitle').textContent=ws.title;
  document.getElementById('wsDesc').textContent=ws.intent;
  const totalKb=ws.tabs.reduce((a,t)=>a+t.size_kb,0);
  document.getElementById('wsMeta').textContent=`${ws.tabs.length} report${ws.tabs.length===1?'':'s'} · ${fmtSize(totalKb)}`;
}

function renderTabStrip(ws,activeFile){
  const strip=document.getElementById('tabstrip');
  strip.innerHTML='';
  ws.tabs.forEach(t=>{
    const b=document.createElement('button');
    b.type='button';
    b.className='tabstrip-btn'+(t.file===activeFile?' active':'');
    b.textContent=t.title;
    b.addEventListener('click',()=>selectTab(t.file));
    strip.appendChild(b);
  });
}

function loadFrame(tab){
  const frame=document.getElementById('stage');
  const statusEl=document.getElementById('frameStatus');
  document.getElementById('frameMeta').textContent=`${tab.dir}/${tab.file} · ${fmtSize(tab.size_kb)}`;
  statusEl.textContent='Decoding…';
  document.getElementById('btnOpenNewTab').onclick=()=>openInNewTab(tab.file);
  document.getElementById('btnDownload').onclick=()=>downloadFile(tab.file);
  requestAnimationFrame(()=>{frame.srcdoc=getView(tab.file);statusEl.textContent='';});
}

function openInNewTab(file){
  const blob=new Blob([getView(file)],{type:'text/html'});
  const url=URL.createObjectURL(blob);
  window.open(url,'_blank');
  setTimeout(()=>URL.revokeObjectURL(url),60000);
}

function downloadFile(file){
  const blob=new Blob([getView(file)],{type:'text/html'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download=file;document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),5000);
}

function applySearch(q){
  q=q.trim().toLowerCase();
  document.querySelectorAll('.ws-group').forEach(group=>{
    const ws=WORKSPACES.find(w=>w.id===group.dataset.ws);
    let anyVisible=false;
    group.querySelectorAll('.ws-tab').forEach(btn=>{
      const tab=ws.tabs.find(t=>t.file===btn.dataset.file);
      const hay=(tab.title+' '+tab.description+' '+tab.file).toLowerCase();
      const show=!q||hay.includes(q);
      btn.classList.toggle('hidden',!show);
      if(show)anyVisible=true;
    });
    const headHay=(ws.title+' '+ws.intent).toLowerCase();
    const show=!q||anyVisible||headHay.includes(q);
    group.classList.toggle('hidden',!show);
    if(q&&anyVisible)group.classList.remove('collapsed');
  });
}

function onGlobalKeydown(e){
  const search=document.getElementById('globalSearch');
  if(e.key==='/'&&document.activeElement!==search){e.preventDefault();search.focus();search.select();}
  else if(e.key==='Escape'&&document.activeElement===search){search.value='';applySearch('');search.blur();}
}

function init(){
  renderSidebar();
  let initial=null;
  const hash=decodeURIComponent(location.hash.replace(/^#/,''));
  if(hash.includes('/')){
    const idx=hash.indexOf('/');
    const wsId=hash.slice(0,idx), file=hash.slice(idx+1);
    const ws=WORKSPACES.find(w=>w.id===wsId);
    if(ws&&ws.tabs.some(t=>t.file===file))initial=file;
  }
  if(!initial)initial=WORKSPACES[0]?.tabs[0]?.file;
  if(initial)selectTab(initial);
  document.getElementById('globalSearch').addEventListener('input',e=>applySearch(e.target.value));
  document.addEventListener('keydown',onGlobalKeydown);
}
document.addEventListener('DOMContentLoaded',init);
"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>{gen_base_css()}{console_css}</style>
</head>
<body>
<div class="console">
  <header class="console-topbar">
    <div class="console-brand">
      <span class="kicker">{esc(project_title)}</span>
      <h1>Architecture Console</h1>
    </div>
    <div class="console-kpis">{kpi_html}</div>
    <div class="console-search">
      <svg viewBox="0 0 24 24" width="15" height="15"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="M20 20l-3.5-3.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input id="globalSearch" type="text" placeholder="Search reports…" autocomplete="off" />
      <kbd>/</kbd>
    </div>
  </header>
  <div class="console-body">
    <nav class="console-sidebar" id="sidebarTree"></nav>
    <main class="console-stage">
      <div class="stage-header">
        <div>
          <h2 id="wsTitle"></h2>
          <p id="wsDesc"></p>
        </div>
        <div class="stage-meta" id="wsMeta"></div>
      </div>
      <div class="tabstrip" id="tabstrip"></div>
      <div class="frame-toolbar">
        <span class="meta"><span id="frameMeta"></span><span class="status" id="frameStatus"></span></span>
        <div class="frame-actions">
          <button type="button" class="btn" id="btnOpenNewTab">Open in new tab ↗</button>
          <button type="button" class="btn" id="btnDownload">Download ⭳</button>
        </div>
      </div>
      <div class="frame-wrap"><iframe id="stage" sandbox="allow-scripts allow-downloads" title="Report viewer"></iframe></div>
    </main>
  </div>
  <footer class="console-footer">
    <span>Generated {esc(generated)} from {esc(source_file)} · architecture: {esc(arch_name)}</span>
    <span>{total_reports} reports embedded · {esc(total_size_label)} total · single-file console, no external dependencies</span>
  </footer>
</div>
<script id="eec-workspaces" type="application/json">{json_for_html(workspaces)}</script>
<script id="eec-views" type="application/json">{json_for_html(views)}</script>
<script>{js}</script>
</body>
</html>"""


def main() -> int:
    parser = make_argparser("Generate the single-file E/E Architect Design architecture console, embedding every generated report into one HTML shell.")
    parser.add_argument("--filename", default="architecture_console.html", help="Output file name (written under generated_doc/ unless --outdir is given).")
    args = parser.parse_args()
    root, cfg, arch, arch_path, _unused_outdir = cli_context(args)

    outdir = Path(args.outdir).expanduser() if args.outdir else (root / "generated_doc")
    if not outdir.is_absolute():
        outdir = root / outdir
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / args.filename

    workspaces, views, skipped = collect_workspaces(root, WORKSPACES)
    kpis = gather_kpis(arch)
    project_title = cfg.get("html", {}).get("project_title", "E/E Architect Design")
    arch_name = str(arch.get("name") or "Imported Architecture")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = render_html(
        project_title=project_title,
        arch_name=arch_name,
        kpis=kpis,
        workspaces=workspaces,
        views=views,
        source_file=str(Path(arch_path).name),
        generated=generated,
    )
    out_path.write_text(html, encoding="utf-8")

    total_reports = sum(len(ws["tabs"]) for ws in workspaces)
    total_kb = sum(t["size_kb"] for ws in workspaces for t in ws["tabs"])
    size_label = f"{total_kb / 1024:.1f} MB" if total_kb >= 1024 else f"{total_kb:.0f} KB"
    print(f"[OK] {out_path}  ({total_reports} reports, {size_label} embedded, {len(workspaces)} workspaces)")
    if skipped:
        print(f"[INFO] Skipped {len(skipped)} configured report(s) not found on disk:")
        for s in skipped:
            print(f"       - {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

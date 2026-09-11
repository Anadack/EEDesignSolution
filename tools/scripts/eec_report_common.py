#!/usr/bin/env python3
"""Common helpers for E/E Architect Design v4 generic HTML/report tools.

The module intentionally keeps framework-specific names in a JSON config file
(`eec_report_config.v4.json`) instead of duplicating hard-coded constants in
individual report scripts.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from eec_design import gen_base_css, gen_advanced_css
from eec_ui_components import kpi_row, kpi_tile, page_header, IOColorMap

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = TOOL_DIR / "eec_report_config.v4.json"


def esc(value: Any) -> str:
    return html.escape(str("" if value is None else value), quote=True)


def slug(value: Any) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "item")).strip("_")
    return s or "item"


def strip_tags(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str("" if value is None else value)).strip()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if cfg_path.exists():
        return load_json(cfg_path)
    return {}


def find_workspace(start: Path | None = None) -> Path:
    start = Path(start or Path.cwd()).resolve()
    if start.is_file():
        start = start.parent
    cur = start
    markers = (("generated_doc",), ("src", "inc"), ("library",), ("tools",))
    while True:
        for marker in markers:
            if all((cur / m).exists() for m in marker):
                return cur
        if cur.parent == cur:
            return start
        cur = cur.parent


def resolve_root(raw_root: str | None) -> Path:
    if raw_root:
        return Path(raw_root).expanduser().resolve()
    return find_workspace(Path.cwd())


def first_existing(root: Path, candidates: Iterable[str | Path]) -> Path | None:
    for item in candidates:
        p = Path(item)
        if not p.is_absolute():
            p = root / p
        if p.exists():
            return p
    return None


def get_architecture(data: dict[str, Any]) -> dict[str, Any]:
    arch = data.get("architecture", data)
    if not isinstance(arch, dict):
        raise ValueError("architecture must be a JSON object")
    return arch


def get_output_dir(root: Path, cfg: dict[str, Any], outdir: str | None) -> Path:
    if outdir:
        p = Path(outdir)
        return p if p.is_absolute() else root / p
    return root / str(cfg.get("default_output_dir", "generated_doc/exports"))


def get_output_file(root: Path, cfg: dict[str, Any], key: str, explicit: str | None = None, outdir: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else root / p
    out = get_output_dir(root, cfg, outdir)
    filename = cfg.get("output_files", {}).get(key, f"{key}.html")
    return out / filename


def load_architecture_from_args(args: argparse.Namespace, cfg: dict[str, Any], physical: bool = False) -> tuple[Path, dict[str, Any]]:
    root = resolve_root(getattr(args, "root", None))
    if getattr(args, "input", None):
        p = Path(args.input)
        if not p.is_absolute():
            p = root / p
    else:
        key = "physical_architecture_json_candidates" if physical else "architecture_json_candidates"
        p = first_existing(root, cfg.get(key, []))
        if p is None:
            raise FileNotFoundError(f"No architecture export found. Tried: {cfg.get(key, [])}")
    data = load_json(p)
    return p, get_architecture(data)


def normalize_token(value: Any) -> str:
    return str(value or "").strip().upper()


def signal_name(sig: Any) -> str:
    if isinstance(sig, dict):
        # Prefer clean_name (standardized) over original name
        if sig.get("clean_name"):
            return str(sig.get("clean_name"))
        return str(sig.get("name") or sig.get("prefix") or sig.get("id") or "")
    if isinstance(sig, str):
        return sig
    return ""


def signal_interface(sig: Any, fallback: Any = "") -> str:
    if isinstance(sig, dict):
        return str(sig.get("interface") or sig.get("interface_type") or fallback or "")
    return str(fallback or "")


def signal_role(sig: Any, fallback: Any = "") -> str:
    if isinstance(sig, dict):
        return str(sig.get("role") or fallback or "")
    return str(fallback or "")


def signal_prefix(sig: Any) -> str:
    if isinstance(sig, dict):
        return str(sig.get("prefix") or sig.get("name") or sig.get("id") or "")
    return str(sig or "")


def find_signal_in_device(device: dict[str, Any], ref: Any) -> dict[str, Any] | None:
    if isinstance(ref, dict):
        return ref
    name = str(ref or "")
    if not name:
        return None
    for s in device.get("signals", []) if isinstance(device.get("signals"), list) else []:
        if not isinstance(s, dict):
            continue
        keys = {str(s.get("name", "")), str(s.get("prefix", "")), str(s.get("id", ""))}
        if name in keys:
            return s
    return {"name": name, "prefix": name}


def iter_components(system: dict[str, Any]) -> Iterable[dict[str, Any]]:
    comps = system.get("components")
    if isinstance(comps, list):
        for comp in comps:
            if isinstance(comp, dict):
                yield comp


def iter_devices(system: dict[str, Any]) -> Iterable[tuple[dict[str, Any] | None, dict[str, Any], str]]:
    """Yield (component, device, kind) for v4 `components[]` and legacy `devices[]`."""
    seen = set()
    for comp in iter_components(system):
        for key, kind in (("sensors", "SENSOR"), ("actuators", "ACTUATOR"), ("devices", "DEVICE")):
            values = comp.get(key)
            if not isinstance(values, list):
                continue
            for dev in values:
                if isinstance(dev, dict):
                    seen.add(id(dev))
                    yield comp, dev, str(dev.get("device_type") or dev.get("type") or kind).upper()
    for dev in system.get("devices", []) if isinstance(system.get("devices"), list) else []:
        if isinstance(dev, dict) and id(dev) not in seen:
            yield None, dev, str(dev.get("device_type") or dev.get("type") or "DEVICE").upper()


def connector_cavity_sum(device: dict[str, Any]) -> int:
    total = 0
    for conn in device.get("connectors", []) if isinstance(device.get("connectors"), list) else []:
        if isinstance(conn, dict):
            total += int(conn.get("used_cavities", conn.get("total_cavities", 0)) or 0)
    return total


def iter_device_pin_records(device: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield normalized pin records, synthesizing legacy signals[] into pins if needed."""
    pins = device.get("pins")
    if isinstance(pins, list) and pins:
        for index, pin in enumerate(pins, 1):
            if not isinstance(pin, dict):
                continue
            sig = find_signal_in_device(device, pin.get("signal")) or {}
            if not sig and isinstance(device.get("signals"), list) and index <= len(device["signals"]):
                sig = device["signals"][index - 1]
            yield {
                "number": pin.get("number", pin.get("pin_number", pin.get("cavity", index))),
                "name": str(pin.get("name", signal_prefix(sig) or f"PIN_{index}")),
                "connector": str(pin.get("connector", pin.get("connector_name", ""))),
                "cavity": pin.get("cavity", pin.get("number", index)),
                "role": str(pin.get("role", signal_role(sig))),
                "interface": str(pin.get("interface_type", signal_interface(sig, pin.get("type", "")))),
                "signal": sig if isinstance(sig, dict) else {"name": str(sig)},
                "raw_pin": pin,
            }
    else:
        for index, sig in enumerate(device.get("signals", []) if isinstance(device.get("signals"), list) else [], 1):
            if not isinstance(sig, dict):
                continue
            yield {
                "number": index,
                "name": signal_prefix(sig) or f"PIN_{index}",
                "connector": "",
                "cavity": index,
                "role": signal_role(sig),
                "interface": signal_interface(sig),
                "signal": sig,
                "raw_pin": {},
            }


def iter_ecu_pins(arch: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for ecu in arch.get("ecus", []) if isinstance(arch.get("ecus"), list) else []:
        if not isinstance(ecu, dict):
            continue
        for pin in ecu.get("pins", []) if isinstance(ecu.get("pins"), list) else []:
            if isinstance(pin, dict):
                yield ecu, pin


def build_route_index(arch: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    routes: dict[str, list[dict[str, Any]]] = {}
    for ecu, pin in iter_ecu_pins(arch):
        sig = pin.get("signal")
        name = signal_name(sig)
        if not name:
            # Some exporters put signal_name directly on the pin.
            name = str(pin.get("signal_name", ""))
        if not name:
            continue
        entry = {
            "ecu": str(ecu.get("name", "")),
            "variant": str(ecu.get("variant", "")),
            "connector": str(pin.get("connector", "")),
            "ecu_pin": str(pin.get("physical_number", pin.get("number", ""))),
            "ecu_pin_name": str(pin.get("name", "")),
            "ecu_role": str(pin.get("role", "")),
            "ecu_type": str(pin.get("type", "")),
            "interface": signal_interface(sig, pin.get("type", "")),
            "electrical_capability": int(pin.get("electrical_capability", 0) or 0),
            "diagnostic_flags": int(pin.get("diagnostic_flags", 0) or 0),
        }
        routes.setdefault(name, []).append(entry)
    return routes


def collect_allocation_rows(arch: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    routes = build_route_index(arch)
    rows: list[dict[str, Any]] = []
    for system in arch.get("systems", []) if isinstance(arch.get("systems"), list) else []:
        if not isinstance(system, dict):
            continue
        sys_name = str(system.get("name", ""))
        for comp, dev, kind in iter_devices(system):
            comp_name = str(comp.get("name", "")) if isinstance(comp, dict) else ""
            dev_name = str(dev.get("name", ""))
            for rec in iter_device_pin_records(dev):
                sig = rec["signal"]
                sn = signal_name(sig) or str(rec["name"])
                matched = routes.get(sn, [])
                if not matched:
                    rows.append({
                        "system": sys_name, "component": comp_name, "device": dev_name, "device_type": kind,
                        "device_connector": rec["connector"], "device_cavity": rec["cavity"], "device_pin": rec["name"],
                        "signal": sn, "interface": rec["interface"], "role": rec["role"],
                        "ecu": "", "variant": "", "ecu_connector": "", "ecu_pin": "", "ecu_pin_name": "",
                        "ecu_role": "", "ecu_type": "", "status": "UNMAPPED"
                    })
                else:
                    for route in matched:
                        rows.append({
                            "system": sys_name, "component": comp_name, "device": dev_name, "device_type": kind,
                            "device_connector": rec["connector"], "device_cavity": rec["cavity"], "device_pin": rec["name"],
                            "signal": sn, "interface": rec["interface"] or route["interface"], "role": rec["role"],
                            "ecu": route["ecu"], "variant": route["variant"], "ecu_connector": route["connector"],
                            "ecu_pin": route["ecu_pin"], "ecu_pin_name": route["ecu_pin_name"],
                            "ecu_role": route["ecu_role"], "ecu_type": route["ecu_type"], "status": "MAPPED"
                        })
    return rows


def decode_mask(value: Any, labels: dict[str, str]) -> str:
    try:
        number = int(value or 0)
    except Exception:
        return ""
    if number == 0:
        return ""
    out = [label for bit, label in sorted(((int(k), v) for k, v in labels.items())) if number & bit]
    return " | ".join(out) if out else str(number)


def html_page(title: str, body: str, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\"/>
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>{esc(title)}</title>
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\"/>
<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin/>
<link href=\"https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap\" rel=\"stylesheet\"/>
<style>
:root{{
  --bg:#0d0f14;--surface:#131720;--raised:#1a1f2e;--hover:#1f2538;--active:#242b42;
  --b0:rgba(255,255,255,.06);--b1:rgba(255,255,255,.10);--b2:rgba(255,255,255,.16);
  --tp:#e8ecf4;--ts:#8993a8;--tm:#5a6278;--ta:#60a5fa;
  --accent:#3b82f6;--accent-dim:rgba(59,130,246,.15);--accent-glow:rgba(59,130,246,.25);
  --ok:#22c55e;--warn:#f59e0b;--err:#ef4444;
  --r:6px;--rm:10px;--rl:16px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{min-height:100vh}}
body{{font-family:'Inter',system-ui,sans-serif;background:radial-gradient(circle at 15% 0%,rgba(59,130,246,.10),transparent 32%),radial-gradient(circle at 85% 0%,rgba(124,58,237,.08),transparent 32%),var(--bg);color:var(--tp);font-size:13px;line-height:1.5}}
button,input,select{{font:inherit;color:inherit}}
.page{{max-width:1480px;margin:0 auto;padding:24px;display:grid;gap:16px;overflow-x:hidden}}
.page-header{{background:radial-gradient(circle at 85% -20%,rgba(59,130,246,.18),transparent 55%),linear-gradient(135deg,#131720,#1a1f2e);border:1px solid var(--b0);border-radius:var(--rl);padding:24px 28px}}
.page-header h1{{font-size:1.6rem;font-weight:800;letter-spacing:-.02em;margin-bottom:6px}}
.page-header .src{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm)}}
.card{{background:var(--surface);border:1px solid var(--b0);border-radius:var(--rl);padding:18px 20px}}
h1{{font-size:1.5rem;font-weight:800;letter-spacing:-.02em;margin-bottom:6px;color:var(--tp)}}
h2{{font-size:1.1rem;font-weight:700;margin-bottom:12px;color:var(--tp)}}
.muted{{color:var(--tm);font-size:11px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}}
.kpi{{background:var(--raised);border:1px solid var(--b1);border-radius:var(--rm);padding:14px 16px;position:relative;overflow:hidden}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent)}}
.kpi div{{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);margin-bottom:6px}}
.kpi b{{font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:800;color:var(--tp);line-height:1}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0;align-items:center}}
input,select{{padding:7px 10px;background:var(--raised);border:1px solid var(--b1);border-radius:var(--r);color:var(--tp);outline:none;transition:border-color .15s}}
input:focus,select:focus{{border-color:var(--accent)}}
input::placeholder{{color:var(--tm)}}
button{{padding:7px 12px;background:var(--raised);border:1px solid var(--b1);border-radius:var(--r);color:var(--ts);cursor:pointer;transition:all .12s}}
button:hover{{border-color:var(--b2);color:var(--tp)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{position:sticky;top:0;background:var(--raised);z-index:1;padding:8px 12px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--tm);border-bottom:1px solid var(--b1);cursor:pointer;white-space:nowrap}}
th:hover{{background:var(--active);color:var(--ts)}}
tr.filters th{{position:sticky;top:28px;cursor:default;padding:4px 6px;background:var(--surface)}}
tr.filters select,tr.filters input{{width:100%;padding:4px 6px;font-size:11px}}
td{{padding:8px 12px;border-bottom:1px solid var(--b0);vertical-align:top;color:var(--ts);max-width:320px;overflow-wrap:anywhere;word-break:break-word}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.025);color:var(--tp)}}
.badge{{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;background:rgba(255,255,255,.06);color:var(--ts);border:1px solid var(--b1);white-space:nowrap;margin:1px 2px 1px 0}}
.ok{{background:rgba(34,197,94,.12)!important;color:#86efac!important;border-color:rgba(34,197,94,.25)!important}}
.warn{{background:rgba(245,158,11,.12)!important;color:#fcd34d!important;border-color:rgba(245,158,11,.25)!important}}
.err{{background:rgba(239,68,68,.12)!important;color:#fca5a5!important;border-color:rgba(239,68,68,.25)!important}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:11px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
details{{background:var(--raised);border:1px solid var(--b1);border-radius:var(--rm);padding:10px;margin:6px 0}}
details summary{{cursor:pointer;font-weight:700;color:var(--tp);padding:2px 0}}
details summary:hover{{color:var(--ta)}}
.node{{padding:8px 12px;border-left:3px solid var(--accent);background:var(--raised);border-radius:var(--r);margin:5px 0;font-size:11px;color:var(--ts)}}
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--b1);border-radius:2px}}
</style>
<style>{gen_advanced_css()}</style>
{extra_head}
</head>
<body><div class=\"page\">{body}</div></body></html>"""


def table_html(rows: list[dict[str, Any]], columns: list[tuple[str, str]], table_id: str = "data", max_filter_options: int = 20) -> str:
    head = "".join(f"<th onclick=\"sortTable('{table_id}',{i})\">{esc(label)}</th>" for i, (_, label) in enumerate(columns))
    filter_cells = []
    for i, (key, label) in enumerate(columns):
        values = sorted({strip_tags(r.get(key, "")) for r in rows if strip_tags(r.get(key, ""))})
        if 0 < len(values) <= max_filter_options:
            opts = "".join(f"<option value=\"{esc(v)}\">{esc(v)}</option>" for v in values)
            filter_cells.append(f"<th><select class='colfilter' data-col='{i}' onchange=\"applyFilters('{table_id}')\"><option value=''>All</option>{opts}</select></th>")
        else:
            filter_cells.append(f"<th><input class='colfilter' data-col='{i}' placeholder=\"Filter {esc(label)}…\" oninput=\"applyFilters('{table_id}')\"/></th>")
    filter_row = f"<tr class='filters'>{''.join(filter_cells)}</tr>"
    body = []
    for row in rows:
        cells = "".join(f"<td>{esc(row.get(key,''))}</td>" for key, _ in columns)
        body.append(f"<tr>{cells}</tr>")
    js = f"""
<script>
function applyFilters(id){{const t=document.getElementById(id);const qEl=document.getElementById(id+'_q');const ql=((qEl&&qEl.value)||'').toLowerCase();const filters=[...t.querySelectorAll('.colfilter')].map(el=>({{c:+el.dataset.col,v:el.value.toLowerCase(),sel:el.tagName==='SELECT'}}));let n=0;t.querySelectorAll('tbody tr').forEach(r=>{{let ok=!ql||r.innerText.toLowerCase().includes(ql);if(ok)for(const f of filters){{if(!f.v)continue;const cl=((r.cells[f.c]||{{}}).innerText||'').toLowerCase();ok=f.sel?cl===f.v:cl.includes(f.v);if(!ok)break;}}r.style.display=ok?'':'none';if(ok)n++;}});const cnt=document.getElementById(id+'_count');if(cnt)cnt.textContent=n+' rows';}}
function clearFilters(id){{const t=document.getElementById(id);t.querySelectorAll('.colfilter').forEach(el=>el.value='');const q=document.getElementById(id+'_q');if(q)q.value='';applyFilters(id);}}
function sortTable(id,n){{let t=document.getElementById(id),b=t.tBodies[0],r=[...b.rows];let asc=t.dataset.sort!==String(n);r.sort((a,b)=>{{let A=a.cells[n].innerText,B=b.cells[n].innerText;let x=parseFloat(A),y=parseFloat(B);if(!isNaN(x)&&!isNaN(y))return asc?x-y:y-x;return asc?A.localeCompare(B):B.localeCompare(A);}});r.forEach(x=>b.appendChild(x));t.dataset.sort=asc?String(n):'';}}
function exportCSV(id){{let rows=[...document.querySelectorAll('#'+id+' tr')].filter(r=>r.style.display!=='none');let csv=rows.map(r=>[...r.cells].map(c=>'"'+c.innerText.replaceAll('"','""')+'"').join(',')).join('\\n');let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download=id+'.csv';a.click();}}
</script>"""
    toolbar = (f"<div class='toolbar'>"
               f"<input id='{table_id}_q' placeholder='Search…' oninput=\"applyFilters('{table_id}')\" style='min-width:240px'/>"
               f"<button onclick=\"clearFilters('{table_id}')\">Clear filters</button>"
               f"<button onclick=\"exportCSV('{table_id}')\">&#8595; CSV</button>"
               f"<span id='{table_id}_count' style='margin-left:auto;font-family:JetBrains Mono,monospace;font-size:10px;color:#5a6278'>{len(rows)} rows</span>"
               f"</div>")
    return (toolbar +
            f"<div style='overflow:auto;max-height:72vh;border-radius:10px;border:1px solid rgba(255,255,255,.06)'>"
            f"<table id='{table_id}'><thead><tr>{head}</tr>{filter_row}</thead><tbody>{''.join(body)}</tbody></table>"
            f"</div>" + js)


def standard_arg_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--root", help="Workspace root. Defaults to auto-detection from current directory.")
    p.add_argument("--config", help="Path to eec_report_config.v4.json.")
    p.add_argument("--input", help="Architecture/estimation JSON input. Defaults come from config candidates.")
    p.add_argument("--output", help="Output file path. Defaults come from config output_files.")
    p.add_argument("--outdir", help="Output directory. Defaults to config default_output_dir.")
    return p


def default_compiler(cfg: dict[str, Any]) -> str:
    env_name = str(cfg.get("default_compiler_env", "CC"))
    return os.environ.get(env_name) or shutil.which("cc") or shutil.which("gcc") or "cc"


def default_python(cfg: dict[str, Any]) -> str:
    env_name = str(cfg.get("default_python_env", "PYTHON"))
    return os.environ.get(env_name) or sys.executable


def default_app_name(cfg: dict[str, Any]) -> str:
    app = cfg.get("default_executable", {})
    if sys.platform.startswith("win"):
        return str(app.get("windows", "app.exe"))
    return str(app.get("posix", "app"))


def run_command(command: list[str], cwd: Path, label: str) -> None:
    print(f"[STEP] {label}")
    print(" ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def build_demo(root: Path, compiler: str, app_name: str) -> Path:
    src_dir = root / "src"
    sources = sorted(src_dir.glob("*.c"))
    if not sources:
        raise FileNotFoundError(f"No C source files found in {src_dir}")
    app_path = root / app_name
    cmd = [compiler, "-std=c11", "-Wall", "-Wextra", "-pedantic", "-O2", "-Iinc", *[str(p.relative_to(root)) for p in sources], "-o", str(app_path.relative_to(root))]
    run_command(cmd, root, "Build demo executable")
    return app_path


def run_demo(root: Path, app_path: Path) -> None:
    run_command([str(app_path)], root, "Run demo executable")

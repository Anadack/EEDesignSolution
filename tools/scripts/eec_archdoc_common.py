#!/usr/bin/env python3
"""Common helpers for E/E Architect Design v4 architecture documentation scripts.

The helpers are intentionally data-driven: scripts read JSON exports produced by
framework compilation/run (normally generated_doc/exports/example_architecture.json
and generated_doc/exports/example_physical_architecture.json). If export filenames,
bit masks or output paths change, update eec_archdoc_config.v4.json, not every script.
"""
from __future__ import annotations

import argparse
import colorsys
import csv
import difflib
import html
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from eec_design import gen_all_css
from eec_ui_components import (
    kpi_row, kpi_tile, io_grid, bar_chart, flow_diagram,
    detail_panel, semantic_badge, legend, page_header,
    main_layout, sidebar_section, IOColorMap
)

CONFIG_FILENAME = "eec_archdoc_config.v4.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "architecture_json_candidates": [
        "generated_doc/exports/exported_architecture.json",
        "generated_doc/exports/example_architecture.json",
        "generated_doc/exports/architecture.json",
        "example_architecture.json"
    ],
    "physical_architecture_json_candidates": [
        "generated_doc/exports/exported_physical_architecture.json",
        "generated_doc/exports/example_physical_architecture.json",
        "generated_doc/exports/physical_architecture.json",
        "example_physical_architecture.json"
    ],
    "estimation_json_candidates": [
        "generated_doc/exports/estimation_result.json",
        "estimation_result.json"
    ],
    "default_output_dir": "generated_doc/architecture_html",
    "library_system_globs": ["library/systems/**/*.json"],
    "library_ecu_globs": ["library/ecus/**/*.json"],
    "bus_interfaces": ["CAN", "LIN", "ETHERNET", "FLEXRAY", "ISOBUS"],
    "excluded_bus_interfaces": [
        "POWER", "GROUND", "RESERVED", "SENSOR_SUPPLY", "SUPPLY", "IGNITION",
        "ANALOG", "PWM", "DIGITAL", "SENT", "IO", "INPUT", "OUTPUT",
        "CURRENT", "FREQUENCY", "RESISTANCE", "VOLTAGE"
    ],
    "electrical_flags": {
        "1": "PULLUP", "2": "PULLDOWN", "4": "HIGH_SIDE", "8": "LOW_SIDE",
        "16": "PUSH_PULL", "32": "CURRENT_SENSE", "64": "VOLTAGE_IN", "128": "DIFFERENTIAL"
    },
    "diagnostic_flags": {
        "1": "OPEN_LOAD", "2": "SHORT_GND", "4": "SHORT_BAT", "8": "RANGE_CHECK",
        "16": "OVERCURRENT", "32": "THERMAL", "64": "LINE_BREAK", "128": "PLAUSIBILITY"
    },
    "safety_values": ["SAFETY_RELATED", "AgPL_A", "AgPL_B", "AgPL_C", "AgPL_D", "AgPL_E"],
    "quality": {
        "required_signal_fields": ["name", "interface", "role", "unit", "priority", "safety"],
        "required_pin_fields": ["number", "name", "role", "signal"],
        "recommended_pin_fields": ["electrical_requirement", "nominal_current", "max_voltage", "diagnostics_required"],
        "recommended_connector_fields": ["name", "total_cavities", "used_cavities", "max_pin_number"],
        "recommended_traceability_fields": ["requirement_ids", "test_case_ids", "variant_codes"]
    },
    "html": {
        "project_title": "E/E Architect Design",
        "accent": "#2ee6ff"
    }
}

PALETTE = [
    "#2ee6ff", "#2ee6a0", "#ffb43d", "#b388ff", "#ff5a78", "#19d6c0", "#ff9e6e", "#5aa6ff",
]


def unique_bus_colors(names: Sequence[str]) -> dict[str, str]:
    """Assign every name a color guaranteed distinct from every other one,
    for any count. Uses the curated PALETTE (hand-picked hues) first, then
    falls back to evenly-spaced HSL hues for any names beyond it, so two
    buses never end up sharing a color no matter how many an export has."""
    colors: dict[str, str] = {}
    overflow = max(0, len(names) - len(PALETTE))
    for i, name in enumerate(names):
        if i < len(PALETTE):
            colors[name] = PALETTE[i]
        else:
            hue = (i - len(PALETTE)) / overflow
            r, g, b = colorsys.hls_to_rgb(hue, 0.60, 0.72)
            colors[name] = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
    return colors


KNOWN_IFACE_COLORS = {
    "ANALOG": "#5aa6ff", "PWM": "#ffb43d", "DIGITAL": "#2ee6a0", "SENT": "#b388ff",
    "CAN": "#ff5a78", "LIN": "#ff9e6e", "ETHERNET": "#19d6c0", "FLEXRAY": "#b388ff",
    "ISOBUS": "#2ee6a0", "POWER": "#6c83a2", "GROUND": "#46566e", "CURRENT": "#19d6c0",
    "FREQUENCY": "#ffb43d", "RESISTANCE": "#2ee6a0", "SENSOR_SUPPLY": "#2ee6ff"
}

ICON_SVG: dict[str, str] = {
    "ecu": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="8" height="8" rx="1.5"/><path d="M10 8V5M14 8V5M10 16v3M14 16v3M8 10H5M8 14H5M16 10h3M16 14h3"/></svg>',
    "sensor": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="17" r="2.5"/><path d="M12 14.5V9"/><path d="M8.8 11C9.7 9.2 10.7 8 12 8s2.3 1.2 3.2 3"/><path d="M6 12.5C7.3 9.2 9.4 7 12 7s4.7 2.2 6 5.5"/></svg>',
    "actuator": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></svg>',
    "can": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 12h5M12 12l5-4.5M12 12l5 4.5"/></svg>',
    "ethernet": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 4 9 15 15 0 0 1-4 9 15 15 0 0 1-4-9 15 15 0 0 1 4-9z"/></svg>',
    "lin": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><path d="M7 12h3M14 12h3"/></svg>',
    "flexray": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="10" width="18" height="4" rx="2"/><path d="M7 10V7M12 10V7M17 10V7M7 14v3M12 14v3M17 14v3"/></svg>',
    "isobus": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 15c0-4 3-6 6-6h6c3 0 6 2 6 6"/><circle cx="8" cy="17" r="2"/><circle cx="16" cy="17" r="2"/><path d="M10 17h4"/></svg>',
    "warning": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.5L2 20h20L13.7 3.5a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r=".5" fill="currentColor"/></svg>',
    "ok": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-5"/></svg>',
    "gnd": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v7"/><path d="M6 13h12"/><path d="M8.5 16.5h7"/><path d="M11 20h2"/></svg>',
    "battery": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h5"/><path d="M7 7v10"/><path d="M11 9.5v5"/><path d="M11 12h11"/></svg>',
    "resistor": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h3l1.5-4 3 8 3-8 3 8 1.5-4H22"/></svg>',
    "switch": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="4" cy="16" r="1.6"/><circle cx="20" cy="16" r="1.6"/><path d="M5.5 15L17 8"/></svg>',
    "pulse": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 16h4V8h4v8h4V8h4v8h4"/></svg>',
    "coil": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h2"/><path d="M4 12a2.2 2.2 0 1 1 4 0 2.2 2.2 0 1 1 4 0 2.2 2.2 0 1 1 4 0 2.2 2.2 0 1 1 4 0"/><path d="M20 12h2"/></svg>',
    "reserved": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="3 3"><circle cx="12" cy="12" r="8"/></svg>',
}

_IFACE_ICON_MAP: dict[str, str] = {
    "CAN": "can", "LIN": "lin", "ETHERNET": "ethernet",
    "ISOBUS": "isobus", "FLEXRAY": "flexray",
}


def icon(name: str, color: str = "currentColor", size: int = 18) -> str:
    svg = ICON_SVG.get(name.lower(), "")
    if not svg:
        return ""
    if color != "currentColor":
        svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    return (f'<span class="icon" style="display:inline-flex;align-items:center;'
            f'width:{size}px;height:{size}px;flex-shrink:0;vertical-align:middle">{svg}</span>')


def iface_icon(iface: str) -> str:
    key = _IFACE_ICON_MAP.get(normalize_iface(iface), "")
    return icon(key, iface_color(iface)) if key else ""


def device_type_icon(device_type: str, color: str = "currentColor") -> str:
    dt = str(device_type).upper()
    if "SENSOR" in dt:
        return icon("sensor", color)
    if dt in ("ACTUATOR", "VALVE", "COIL", "MOTOR", "PUMP"):
        return icon("actuator", color)
    return ""


def esc(value: Any) -> str:
    return html.escape(str("" if value is None else value), quote=True)


def slug(value: Any) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value).strip()).strip("-")
    return s.lower() or "item"


def strip_tags(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str("" if value is None else value)).strip()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def repo_root_from_script() -> Path:
    p = Path.cwd().resolve()
    return p


def load_config(root: Path | None = None, config_path: Path | None = None) -> dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    candidates: list[Path] = []
    if config_path:
        candidates.append(config_path)
    if root:
        candidates += [root / "tools" / CONFIG_FILENAME, root / CONFIG_FILENAME]
    candidates.append(Path(__file__).resolve().parent / CONFIG_FILENAME)
    for c in candidates:
        if c.exists():
            try:
                user = read_json(c)
                deep_update(cfg, user)
                cfg["_config_path"] = str(c)
                break
            except Exception as exc:
                raise RuntimeError(f"Failed to load config {c}: {exc}") from exc
    return cfg


def deep_update(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v


def resolve_root(value: str | Path | None = None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    cwd = Path.cwd().resolve()
    # If executed from tools/, root is parent. Otherwise cwd.
    if cwd.name == "tools" and (cwd.parent / "generated_doc" / "exports").exists():
        return cwd.parent
    return cwd


def find_first_existing(root: Path, candidates: Sequence[str]) -> Path | None:
    for item in candidates:
        p = (root / item).resolve()
        if p.exists():
            return p
    return None


def load_architecture(root: Path, cfg: dict[str, Any], explicit: str | Path | None = None, prefer_physical: bool = False) -> tuple[dict[str, Any], Path]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = root / path
    else:
        keys = ["physical_architecture_json_candidates", "architecture_json_candidates"] if prefer_physical else ["architecture_json_candidates", "physical_architecture_json_candidates"]
        path = None
        for key in keys:
            path = find_first_existing(root, cfg.get(key, []))
            if path:
                break
        if not path:
            raise FileNotFoundError("No architecture export JSON found. Run the framework first or pass --input.")
    data = read_json(path)
    arch = data.get("architecture", data) if isinstance(data, dict) else None
    if not isinstance(arch, dict):
        raise ValueError(f"{path}: architecture must be an object")
    return arch, path


def output_path(root: Path, cfg: dict[str, Any], outdir: str | Path | None, filename: str) -> Path:
    base = Path(outdir) if outdir else Path(cfg.get("default_output_dir", "generated_doc/architecture_html"))
    if not base.is_absolute():
        base = root / base
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


def normalize_iface(value: Any) -> str:
    if value is None:
        return ""
    v = str(value).strip().upper()
    if v == "BUS_ETH": return "ETHERNET"
    if v == "BUS_ETHERNET": return "ETHERNET"
    if v == "BUS_CAN": return "CAN"
    return v


def iface_color(iface: str) -> str:
    k = normalize_iface(iface)
    if k in KNOWN_IFACE_COLORS:
        return KNOWN_IFACE_COLORS[k]
    return PALETTE[abs(hash(k)) % len(PALETTE)]


def safety_rank(value: Any) -> int:
    order = {"QM": 0, "SAFETY_RELATED": 1, "AGPL_A": 2, "AGPL_B": 3, "AGPL_C": 4, "AGPL_D": 5, "AGPL_E": 6}
    return order.get(str(value).upper(), 0)


def priority_rank(value: Any) -> int:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    return order.get(str(value).upper(), 0)


def bitmask_labels(value: Any, labels: dict[str, str]) -> list[str]:
    try:
        v = int(value or 0)
    except Exception:
        return []
    out = []
    for bit_s, name in sorted(labels.items(), key=lambda x: int(x[0])):
        bit = int(bit_s)
        if v & bit:
            out.append(name)
    return out


def signal_name(signal: Any, fallback: str = "") -> str:
    if isinstance(signal, dict):
        # Prefer clean_name (standardized) over original name
        if signal.get("clean_name"):
            return str(signal.get("clean_name"))
        for key in ("name", "id", "prefix"):
            if signal.get(key):
                return str(signal.get(key))
    if isinstance(signal, str):
        return signal
    return fallback


def signal_iface(signal: Any, pin: Any = None) -> str:
    if isinstance(signal, dict):
        for key in ("interface_type", "interface"):
            if signal.get(key):
                return normalize_iface(signal.get(key))
    if isinstance(pin, dict):
        for key in ("interface_type", "interface", "type"):
            if pin.get(key):
                return normalize_iface(pin.get(key))
    return ""


def signal_role(signal: Any, pin: Any = None, default: str = "") -> str:
    if isinstance(signal, dict) and signal.get("role"):
        return str(signal.get("role")).upper()
    if isinstance(pin, dict) and pin.get("role"):
        return str(pin.get("role")).upper()
    return default


def signal_unit(signal: Any) -> str:
    if isinstance(signal, dict):
        return str(signal.get("unit", ""))
    return ""


def flatten_components(system: dict[str, Any]) -> list[dict[str, Any]]:
    """Return device-like dictionaries from v4 components or legacy devices."""
    out: list[dict[str, Any]] = []
    if isinstance(system.get("devices"), list):
        for dev in system["devices"]:
            if isinstance(dev, dict):
                d = dict(dev)
                d.setdefault("_component", "")
                out.append(d)
    comps = system.get("components")
    if isinstance(comps, list):
        for comp in comps:
            if not isinstance(comp, dict):
                continue
            comp_name = str(comp.get("name", ""))
            for group, dtype in (("sensors", "SENSOR"), ("actuators", "ACTUATOR"), ("devices", "")):
                items = comp.get(group, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict):
                        d = dict(item)
                        d.setdefault("device_type", dtype or d.get("type", ""))
                        d.setdefault("type", dtype or d.get("device_type", ""))
                        d["_component"] = comp_name
                        out.append(d)
    return out


def iter_systems(arch: dict[str, Any]) -> Iterable[dict[str, Any]]:
    systems = arch.get("systems", [])
    if isinstance(systems, list):
        for sys_obj in systems:
            if isinstance(sys_obj, dict):
                yield sys_obj


def iter_ecus(arch: dict[str, Any]) -> Iterable[dict[str, Any]]:
    ecus = arch.get("ecus", [])
    if isinstance(ecus, list):
        for ecu in ecus:
            if isinstance(ecu, dict):
                yield ecu


def iter_device_pins(arch: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for sys_obj in iter_systems(arch):
        sys_name = str(sys_obj.get("name", ""))
        for dev in flatten_components(sys_obj):
            dev_name = str(dev.get("name", ""))
            dev_type = str(dev.get("device_type", dev.get("type", ""))).upper()
            pins = dev.get("pins", [])
            if not isinstance(pins, list):
                continue
            for pin in pins:
                if not isinstance(pin, dict):
                    continue
                sig = pin.get("signal")
                sn = signal_name(sig, str(pin.get("signal", "")))
                yield {
                    "system": sys_name,
                    "component": str(dev.get("_component", "")),
                    "device": dev_name,
                    "device_type": dev_type,
                    "device_priority": str(dev.get("priority", sys_obj.get("priority", ""))),
                    "device_safety": str(dev.get("safety", sys_obj.get("safety", ""))),
                    "pin": pin,
                    "pin_number": str(pin.get("number", pin.get("physical_number", ""))),
                    "pin_name": str(pin.get("name", "")),
                    "pin_role": signal_role(sig, pin),
                    "signal": sig,
                    "signal_name": sn,
                    "interface": signal_iface(sig, pin),
                    "unit": signal_unit(sig),
                    "priority": str((sig or {}).get("priority", dev.get("priority", sys_obj.get("priority", ""))) if isinstance(sig, dict) else dev.get("priority", sys_obj.get("priority", ""))),
                    "safety": str((sig or {}).get("safety", dev.get("safety", sys_obj.get("safety", ""))) if isinstance(sig, dict) else dev.get("safety", sys_obj.get("safety", ""))),
                    "electrical_requirement": int(pin.get("electrical_requirement", (sig or {}).get("electrical_requirement", 0) if isinstance(sig, dict) else 0) or 0),
                    "min": (sig or {}).get("min", (sig or {}).get("min_value", "")) if isinstance(sig, dict) else "",
                    "max": (sig or {}).get("max", (sig or {}).get("max_value", "")) if isinstance(sig, dict) else "",
                    "resolution": (sig or {}).get("resolution", "") if isinstance(sig, dict) else "",
                    "scaling": (sig or {}).get("scaling", "") if isinstance(sig, dict) else "",
                }


def iter_ecu_pins(arch: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for ecu in iter_ecus(arch):
        ecu_name = str(ecu.get("name", ""))
        variant = str(ecu.get("variant", ""))
        for pin in ecu.get("pins", []) if isinstance(ecu.get("pins"), list) else []:
            if not isinstance(pin, dict):
                continue
            sig = pin.get("signal")
            sn = signal_name(sig, "")
            yield {
                "ecu": ecu_name,
                "variant": variant,
                "ecu_priority": str(ecu.get("priority", "")),
                "ecu_safety": str(ecu.get("safety", "")),
                "connector": str(pin.get("connector", "")),
                "physical_number": str(pin.get("physical_number", pin.get("number", ""))),
                "pin_name": str(pin.get("name", "")),
                "pin_role": str(pin.get("role", "")),
                "pin_type": normalize_iface(pin.get("type", pin.get("interface", ""))),
                "pin_group": str(pin.get("group", "")),
                "is_occupied": bool(pin.get("is_occupied") or sig),
                "signal": sig,
                "signal_name": sn,
                "interface": signal_iface(sig, pin),
                "unit": signal_unit(sig),
                "priority": str((sig or {}).get("priority", ecu.get("priority", "")) if isinstance(sig, dict) else ecu.get("priority", "")),
                "safety": str((sig or {}).get("safety", ecu.get("safety", "")) if isinstance(sig, dict) else ecu.get("safety", "")),
                "electrical_capability": int(pin.get("electrical_capability", 0) or 0),
                "diagnostic_flags": int(pin.get("diagnostic_flags", 0) or 0),
                "electrical": str(pin.get("electrical", "")),
                "sw_config": str(pin.get("sw_config", "")),
            }


def build_signal_index(arch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for row in iter_device_pins(arch):
        sn = row.get("signal_name")
        if not sn:
            continue
        e = idx.setdefault(sn, {"name": sn, "device_pins": [], "ecu_pins": []})
        e["device_pins"].append(row)
        for key in ("interface", "unit", "priority", "safety", "min", "max", "resolution", "scaling"):
            if row.get(key) not in (None, ""):
                e.setdefault(key, row.get(key))
    for row in iter_ecu_pins(arch):
        sn = row.get("signal_name")
        if not sn:
            continue
        e = idx.setdefault(sn, {"name": sn, "device_pins": [], "ecu_pins": []})
        e["ecu_pins"].append(row)
        for key in ("interface", "unit", "priority", "safety"):
            if row.get(key) not in (None, ""):
                e.setdefault(key, row.get(key))
    return idx


def html_page(title: str, body: str, cfg: dict[str, Any] | None = None, subtitle: str = "", nav: Sequence[tuple[str, str]] | None = None) -> str:
    cfg = cfg or DEFAULT_CONFIG
    project_title = cfg.get("html", {}).get("project_title", "E/E Architect Design")
    nav_html = ""
    if nav:
        nav_html = '<nav class="topnav">' + ''.join(f'<a href="{esc(h)}">{esc(t)}</a>' for t, h in nav) + '</nav>'
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)}</title>
<style>{base_css()}</style>
</head>
<body>
<div class="page">
  <section class="hero">
    <div class="kicker">{esc(project_title)}</div>
    <h1>{esc(title)}</h1>
    <p>{esc(subtitle)}</p>
    <div class="stamp">Generated {esc(generated)} from framework JSON exports</div>
    {nav_html}
  </section>
  {body}
</div>
<script>{base_js()}</script>
</body>
</html>"""


def base_css() -> str:
    """Generate all CSS from design system configuration + advanced components."""
    return gen_all_css()


def base_js() -> str:
    return r"""
function applyFilters(tableId){const t=document.getElementById(tableId);const qEl=document.getElementById(tableId+'_search');const ql=((qEl&&qEl.value)||'').toLowerCase();const filters=[...t.querySelectorAll('.colfilter')].map(el=>({c:+el.dataset.col,v:el.value.toLowerCase(),sel:el.tagName==='SELECT'}));let n=0;t.querySelectorAll('tbody tr').forEach(tr=>{let ok=!ql||tr.innerText.toLowerCase().includes(ql);if(ok)for(const f of filters){if(!f.v)continue;const cl=((tr.cells[f.c]||{}).innerText||'').toLowerCase();ok=f.sel?cl===f.v:cl.includes(f.v);if(!ok)break;}tr.style.display=ok?'':'none';if(ok)n++;});const cnt=document.getElementById(tableId+'_count');if(cnt)cnt.textContent=n+' rows';}
function clearFilters(tableId){const t=document.getElementById(tableId);t.querySelectorAll('.colfilter').forEach(el=>el.value='');const q=document.getElementById(tableId+'_search');if(q)q.value='';applyFilters(tableId);}
function sortTable(tableId,n){const table=document.getElementById(tableId);const rows=Array.from(table.tBodies[0].rows);const asc=table.getAttribute('data-sort-col')!=n||table.getAttribute('data-sort-dir')==='desc';rows.sort((a,b)=>{let A=a.cells[n].innerText.trim(),B=b.cells[n].innerText.trim();let NA=parseFloat(A.replace(/[^0-9.-]/g,'')),NB=parseFloat(B.replace(/[^0-9.-]/g,''));let r=(!isNaN(NA)&&!isNaN(NB))?NA-NB:A.localeCompare(B);return asc?r:-r});rows.forEach(r=>table.tBodies[0].appendChild(r));table.setAttribute('data-sort-col',n);table.setAttribute('data-sort-dir',asc?'asc':'desc');}
function downloadTableCsv(tableId, filename){const rows=[...document.querySelectorAll('#'+tableId+' tr')].filter(r=>r.style.display!=='none');const csv=rows.map(r=>[...r.cells].map(c=>'"'+c.innerText.replaceAll('"','""')+'"').join(',')).join('\n');const blob=new Blob([csv],{type:'text/csv'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click();}
"""


def pill(text: Any, color: str | None = None) -> str:
    t = str("" if text is None else text)
    if not t:
        return ""
    c = color or iface_color(t)
    return f'<span class="pill" style="background:{esc(c)}16;color:{esc(c)};border-color:{esc(c)}44">{esc(t)}</span>'


def card_grid(items: Sequence[tuple[str, Any, str]]) -> str:
    cards = []
    for label, value, sub in items:
        cards.append(f'<div class="card"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div><div class="sub">{esc(sub)}</div></div>')
    return '<div class="grid cards">' + ''.join(cards) + '</div>'


def table_html(table_id: str, columns: Sequence[tuple[str, str]], rows: Sequence[dict[str, Any]], csv_name: str | None = None, max_filter_options: int = 20) -> str:
    search_id = table_id + "_search"
    headers = ''.join(f'<th onclick="sortTable(\'{table_id}\',{i})">{esc(label)}</th>' for i, (_, label) in enumerate(columns))
    filter_cells = []
    for i, (key, label) in enumerate(columns):
        values = sorted({strip_tags(r.get(key, "")) for r in rows if strip_tags(r.get(key, ""))})
        if 0 < len(values) <= max_filter_options:
            opts = ''.join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values)
            filter_cells.append(f'<th><select class="colfilter" data-col="{i}" onchange="applyFilters(\'{table_id}\')"><option value="">All</option>{opts}</select></th>')
        else:
            filter_cells.append(f'<th><input class="colfilter" data-col="{i}" placeholder="Filter {esc(label)}…" oninput="applyFilters(\'{table_id}\')"/></th>')
    filter_row = '<tr class="filters">' + ''.join(filter_cells) + '</tr>'
    body = []
    for row in rows:
        body.append('<tr>' + ''.join(f'<td>{row.get(key, "")}</td>' for key, _ in columns) + '</tr>')
    csv_button = f'<button class="btn" onclick="downloadTableCsv(\'{table_id}\',\'{esc(csv_name or table_id + ".csv")}\')">Export CSV</button>'
    clear_button = f'<button class="btn" onclick="clearFilters(\'{table_id}\')">Clear filters</button>'
    count_span = f'<span id="{table_id}_count" class="small" style="margin-left:auto">{len(rows)} rows</span>'
    return (f'<div class="toolbar"><input id="{search_id}" class="search" placeholder="Search..." oninput="applyFilters(\'{table_id}\')" />{clear_button}{csv_button}{count_span}</div>'
            f'<div class="table-scroll"><table id="{table_id}"><thead><tr>{headers}</tr>{filter_row}</thead><tbody>{"".join(body)}</tbody></table></div>')


def linked_index(items: Sequence[tuple[str, str, str]]) -> str:
    rows = ''.join(f'<tr><td><a href="{esc(href)}">{esc(title)}</a></td><td>{esc(desc)}</td></tr>' for title, href, desc in items)
    return '<table><thead><tr><th>Document</th><th>Description</th></tr></thead><tbody>' + rows + '</tbody></table>'


def make_argparser(description: str, input_help: str = "Architecture export JSON. Defaults to configured candidates.") -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--root", default=".", help="Framework workspace root containing generated_doc/, library/, src/, tools/.")
    p.add_argument("--input", default=None, help=input_help)
    p.add_argument("--outdir", default=None, help="Output directory. Default from eec_archdoc_config.v4.json.")
    p.add_argument("--config", default=None, help="Optional config JSON path.")
    p.add_argument("--prefer-physical", action="store_true", help="Prefer physical architecture export candidates.")
    return p


def cli_context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Any], Path, Path]:
    root = resolve_root(args.root)
    cfg = load_config(root, Path(args.config) if args.config else None)
    arch, arch_path = load_architecture(root, cfg, args.input, prefer_physical=getattr(args, "prefer_physical", False))
    outdir = Path(args.outdir) if args.outdir else Path(cfg.get("default_output_dir", "generated_doc/architecture_html"))
    if not outdir.is_absolute():
        outdir = root / outdir
    outdir.mkdir(parents=True, exist_ok=True)
    return root, cfg, arch, arch_path, outdir


def run_command(cmd: Sequence[str], cwd: Path) -> None:
    print("[RUN]", " ".join(str(x) for x in cmd))
    subprocess.run(list(cmd), cwd=cwd, check=True)


def build_and_run(root: Path, compiler: str | None = None, app_name: str | None = None, skip_build: bool = False, skip_run: bool = False) -> None:
    app_name = app_name or ("app.exe" if sys.platform.startswith("win") else "app")
    app = root / app_name
    if not skip_build:
        compiler = compiler or os.environ.get("EEC_CC", "gcc")
        srcs = sorted((root / "src").glob("*.c"))
        if not srcs:
            raise FileNotFoundError("No C source files found under src/")
        cmd = [compiler, "-std=c11", "-Wall", "-Wextra", "-pedantic", "-O2", "-Iinclude", "-Iinc"] + [str(p.relative_to(root)) for p in srcs] + ["-o", str(app.relative_to(root))]
        run_command(cmd, root)
    if not skip_run:
        run_command([str(app)], root)


def file_summary(path: Path) -> str:
    try:
        size = path.stat().st_size
        return f"{path} ({size:,} bytes)"
    except Exception:
        return str(path)

def signal_display_name(signal: dict[str, Any]) -> str:
    """Get the preferred display name for a signal.

    Returns clean_name if available (auto-generated following SYSTEM_Function_[POSITION_]TYPE),
    otherwise returns the original signal name. This allows generators to use standardized
    signal names throughout documentation while gracefully falling back for signals
    without auto-generated clean names.

    Args:
        signal: Signal dict from JSON export (should have 'name' and optionally 'clean_name')

    Returns:
        Preferred signal name as a string
    """
    if isinstance(signal, dict):
        clean = signal.get('clean_name', '')
        if clean:
            return clean
        return signal.get('name', '?')
    return str(signal)

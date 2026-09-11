
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared E/E Architect Design v4 JSON tooling.

All framework-specific values are loaded from ``eec_json_contract.v4.json`` or
from a user-supplied contract file.  Scripts using this module should not embed
framework enum values or project-specific paths.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIR / "eec_json_contract.v4.json"

@dataclass
class Issue:
    level: str
    path: str
    code: str
    message: str

@dataclass
class FileReport:
    file: str
    kind: str = "unknown"
    issues: list[Issue] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)

    def add(self, level: str, path: str, code: str, message: str) -> None:
        self.issues.append(Issue(level, path, code, message))

    @property
    def errors(self) -> int:
        return sum(1 for i in self.issues if i.level == "ERROR")

    @property
    def warnings(self) -> int:
        return sum(1 for i in self.issues if i.level in ("WARN", "WARNING"))

@dataclass
class ValidationResult:
    reports: list[FileReport] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(r.errors for r in self.reports)

    @property
    def warnings(self) -> int:
        return sum(r.warnings for r in self.reports)

    @property
    def ok(self) -> bool:
        return self.errors == 0


def load_contract(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_CONTRACT
    if not p.exists():
        raise FileNotFoundError(f"contract file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        c = json.load(f)
    return c


def discover_root(start: str | Path | None = None) -> Path:
    start_path = Path(start or os.getcwd()).resolve()
    if start_path.is_file():
        start_path = start_path.parent
    markers = ["library", "src", "inc", "Makefile", "CMakeLists.txt", "tools"]
    cur = start_path
    for _ in range(12):
        if any((cur / m).exists() for m in markers):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start_path


def expand_patterns(patterns: Sequence[str], root: str | Path | None = None) -> list[Path]:
    rootp = Path(root or os.getcwd()).resolve()
    out: list[Path] = []
    seen: set[Path] = set()
    for raw in patterns:
        p = Path(raw)
        raw_for_glob = str(p if p.is_absolute() else rootp / p)
        matches = glob.glob(raw_for_glob, recursive=True) if any(ch in raw_for_glob for ch in "*?[]") else [raw_for_glob]
        for m in matches:
            path = Path(m).resolve()
            if path.is_file() and path not in seen:
                out.append(path); seen.add(path)
    return sorted(out)


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def read_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def enum_values(contract: dict, name: str) -> set[str]:
    return set(contract.get("enums", {}).get(name, []))


def known_keys(contract: dict, name: str) -> set[str]:
    return set(contract.get("known_keys", {}).get(name, []))


def required_keys(contract: dict, name: str) -> set[str]:
    return set(contract.get("required_keys", {}).get(name, []))


def canon_token(contract: dict, category: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    v = value.strip()
    if not v:
        return v
    up = v.upper().replace(" ", "_").replace("-", "_")
    aliases = contract.get("aliases", {}).get(category, {})
    return aliases.get(up, up)


def signal_id(sig: dict[str, Any]) -> str:
    return str(sig.get("prefix") or sig.get("name") or sig.get("id") or "")


def connector_used_sum(connectors: list[dict[str, Any]]) -> tuple[int, int, bool]:
    used = 0; total = 0; ok = True
    for c in connectors:
        u = c.get("used_cavities", c.get("total_cavities"))
        t = c.get("total_cavities", u)
        if isinstance(u, int) and not isinstance(u, bool): used += u
        else: ok = False
        if isinstance(t, int) and not isinstance(t, bool): total += t
        else: ok = False
    return used, total, ok


def infer_kind(data: Any) -> str:
    if not isinstance(data, dict): return "unknown"
    t = data.get("type")
    if isinstance(t, str): return t
    if "architecture" in data: return "architecture_export"
    if "sensor" in data: return "sensor"
    if "actuator" in data: return "actuator"
    if "ecu" in data: return "ecu"
    return "unknown"


def check_unknown(obj: dict[str, Any], keyspace: str, path: str, rpt: FileReport, contract: dict, level: str = "WARN") -> None:
    known = known_keys(contract, keyspace)
    if not known:
        return
    for k in obj:
        if k.startswith("_"):
            continue
        if k not in known:
            rpt.add(level, path, "UNKNOWN_KEY", f"key '{k}' is not listed in contract keyspace '{keyspace}' and may be ignored by import/export")


def check_required(obj: dict[str, Any], keyspace: str, path: str, rpt: FileReport, contract: dict) -> None:
    for k in sorted(required_keys(contract, keyspace)):
        if k not in obj or obj.get(k) in (None, ""):
            rpt.add("ERROR", path, "MISSING_KEY", f"required key '{k}' is missing or empty")


def check_enum(value: Any, enum_name: str, path: str, rpt: FileReport, contract: dict, required: bool = False) -> None:
    if value is None or value == "":
        if required:
            rpt.add("ERROR", path, "MISSING_ENUM", f"required enum value for '{enum_name}' is missing")
        return
    vals = enum_values(contract, enum_name)
    if vals and value not in vals:
        rpt.add("ERROR", path, "INVALID_ENUM", f"'{value}' is not in contract enum '{enum_name}'")


def validate_connectors(connectors: Any, path: str, rpt: FileReport, contract: dict, strict: bool = True) -> list[dict[str, Any]]:
    if not isinstance(connectors, list):
        rpt.add("ERROR" if strict else "WARN", path, "CONNECTORS_NOT_ARRAY", "connectors must be an array")
        return []
    names: set[str] = set()
    valid: list[dict[str, Any]] = []
    for i, c in enumerate(connectors):
        cp = f"{path}.connectors[{i}]"
        if not isinstance(c, dict):
            rpt.add("ERROR", cp, "CONNECTOR_NOT_OBJECT", "connector must be an object")
            continue
        check_unknown(c, "connector", cp, rpt, contract)
        check_required(c, "connector", cp, rpt, contract)
        name = c.get("name")
        if nonempty_str(name):
            if name in names: rpt.add("ERROR", cp, "DUPLICATE_CONNECTOR", f"duplicate connector name '{name}'")
            names.add(str(name))
        for key in ("total_cavities", "used_cavities", "max_pin_number"):
            if key in c and (not isinstance(c[key], int) or isinstance(c[key], bool) or c[key] < 0):
                rpt.add("ERROR", f"{cp}.{key}", "INVALID_INTEGER", f"{key} must be a non-negative integer")
        if isinstance(c.get("used_cavities"), int) and isinstance(c.get("total_cavities"), int) and c["used_cavities"] > c["total_cavities"]:
            rpt.add("ERROR", cp, "CAVITY_OVERUSE", "used_cavities must not exceed total_cavities")
        check_enum(c.get("family"), "connector_families", f"{cp}.family", rpt, contract)
        check_enum(c.get("gender"), "connector_genders", f"{cp}.gender", rpt, contract)
        valid.append(c)
    rpt.counters["connectors"] = rpt.counters.get("connectors", 0) + len(valid)
    return valid


def validate_signal(sig: Any, path: str, rpt: FileReport, contract: dict, device_type: str | None = None) -> str:
    if not isinstance(sig, dict):
        rpt.add("ERROR", path, "SIGNAL_NOT_OBJECT", "signal must be an object")
        return ""
    check_unknown(sig, "signal", path, rpt, contract)
    check_required(sig, "signal", path, rpt, contract)
    if "name" in sig and "prefix" not in sig:
        rpt.add("WARN", path, "LEGACY_SIGNAL_NAME", "signal uses 'name' without 'prefix'; normalizer can migrate it")
    prefix = signal_id(sig)
    count = sig.get("count", 1)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        rpt.add("ERROR", f"{path}.count", "INVALID_COUNT", "count must be integer >= 1")
    for key in ("min", "max", "resolution", "scaling"):
        if key in sig and not is_num(sig[key]): rpt.add("ERROR", f"{path}.{key}", "INVALID_NUMBER", f"{key} must be numeric")
    if is_num(sig.get("min")) and is_num(sig.get("max")) and sig["min"] > sig["max"]:
        rpt.add("ERROR", path, "MIN_GT_MAX", "min must not be greater than max")
    if is_num(sig.get("resolution")) and sig["resolution"] <= 0: rpt.add("ERROR", f"{path}.resolution", "INVALID_RESOLUTION", "resolution must be > 0")
    if is_num(sig.get("scaling")) and sig["scaling"] <= 0: rpt.add("ERROR", f"{path}.scaling", "INVALID_SCALING", "scaling must be > 0")
    iface = canon_token(contract, "interfaces", sig.get("interface", sig.get("interface_type")))
    role = canon_token(contract, "roles", sig.get("role"))
    unit = canon_token(contract, "units", sig.get("unit"))
    check_enum(iface, "interfaces", f"{path}.interface", rpt, contract, required=True)
    check_enum(role, "roles", f"{path}.role", rpt, contract, required=True)
    check_enum(unit, "units", f"{path}.unit", rpt, contract, required=True)
    check_enum(sig.get("type"), "signal_types", f"{path}.type", rpt, contract, required=True)
    check_enum(sig.get("priority"), "priorities", f"{path}.priority", rpt, contract)
    check_enum(sig.get("safety"), "safety_classes", f"{path}.safety", rpt, contract)
    bus_ifaces = set(contract.get("rules", {}).get("bus_interfaces", []))
    if contract.get("rules", {}).get("no_inout_except_bus_interfaces", True) and role == "INOUT" and iface not in bus_ifaces:
        rpt.add("ERROR", path, "INOUT_NOT_BUS", f"INOUT role is only allowed for bus interfaces {sorted(bus_ifaces)}")
    if device_type == "SENSOR" and role == "INPUT" and iface not in ("POWER", "GROUND"):
        rpt.add("WARN", path, "SENSOR_INPUT_ROLE", "device-centric sensor data signals are normally OUTPUT")
    if device_type == "ACTUATOR" and role == "OUTPUT" and iface not in ("POWER", "GROUND"):
        rpt.add("WARN", path, "ACTUATOR_OUTPUT_ROLE", "device-centric actuator command signals are normally INPUT")
    rpt.counters["signals"] = rpt.counters.get("signals", 0) + 1
    return prefix


def validate_pin(pin: Any, path: str, rpt: FileReport, contract: dict, signal_names: set[str], connector_names: set[str]) -> None:
    if not isinstance(pin, dict):
        rpt.add("ERROR", path, "PIN_NOT_OBJECT", "pin must be an object")
        return
    check_unknown(pin, "pin", path, rpt, contract)
    check_required(pin, "pin", path, rpt, contract)
    number = pin.get("number", pin.get("pin_number"))
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        rpt.add("ERROR", f"{path}.number", "INVALID_PIN_NUMBER", "number must be integer >= 1")
    cav = pin.get("cavity")
    if cav is not None and (not isinstance(cav, int) or isinstance(cav, bool) or cav < 1):
        rpt.add("ERROR", f"{path}.cavity", "INVALID_CAVITY", "cavity must be integer >= 1")
    conn = pin.get("connector")
    if connector_names and conn not in connector_names:
        rpt.add("ERROR", f"{path}.connector", "UNKNOWN_CONNECTOR_REF", f"pin references unknown connector '{conn}'")
    sigref = str(pin.get("signal", ""))
    if contract.get("rules", {}).get("pin_signal_reference_required", True):
        if not sigref:
            rpt.add("ERROR", f"{path}.signal", "MISSING_SIGNAL_REF", "each pin must reference one signal/net")
        elif sigref not in signal_names:
            rpt.add("ERROR", f"{path}.signal", "UNKNOWN_SIGNAL_REF", f"pin references unknown signal/net '{sigref}'")
    role = canon_token(contract, "roles", pin.get("role"))
    iface = canon_token(contract, "interfaces", pin.get("interface_type", pin.get("type", pin.get("interface"))))
    check_enum(role, "roles", f"{path}.role", rpt, contract, required=True)
    check_enum(iface, "interfaces", f"{path}.interface_type", rpt, contract, required=True)
    check_enum(pin.get("ground_class"), "ground_classes", f"{path}.ground_class", rpt, contract)
    reset = canon_token(contract, "reset_states", pin.get("required_reset_state"))
    check_enum(reset, "reset_states", f"{path}.required_reset_state", rpt, contract)
    for key in ("nominal_current", "inrush_current", "max_voltage", "required_supply_voltage", "required_supply_voltage_min", "required_supply_voltage_max", "preferred_supply_voltage", "current_max", "current_max_a", "voltage_nominal", "voltage_min", "voltage_max"):
        if key in pin and pin[key] not in (None, "") and not is_num(pin[key]):
            rpt.add("ERROR", f"{path}.{key}", "INVALID_NUMBER", f"{key} must be numeric")
    for key in ("electrical_requirement", "diagnostics_required", "diagnostic_flags"):
        if key in pin and pin[key] not in (None, "") and (not isinstance(pin[key], int) or isinstance(pin[key], bool) or pin[key] < 0):
            rpt.add("ERROR", f"{path}.{key}", "INVALID_BITMASK", f"{key} must be non-negative integer")
    rpt.counters["pins"] = rpt.counters.get("pins", 0) + 1


def validate_device(dev: Any, path: str, rpt: FileReport, contract: dict, allow_legacy_compact: bool = False) -> None:
    if not isinstance(dev, dict):
        rpt.add("ERROR", path, "DEVICE_NOT_OBJECT", "device must be an object")
        return
    check_unknown(dev, "device", path, rpt, contract)
    check_required(dev, "device", path, rpt, contract)
    dtype = dev.get("device_type")
    check_enum(dtype, "device_types", f"{path}.device_type", rpt, contract, required=True)
    if dev.get("drive_topology"):
        check_enum(dev.get("drive_topology"), "drive_topologies", f"{path}.drive_topology", rpt, contract)
    signals = dev.get("signals", [])
    connectors = dev.get("connectors", [])
    pins = dev.get("pins", [])
    if not isinstance(signals, list):
        rpt.add("ERROR", f"{path}.signals", "SIGNALS_NOT_ARRAY", "signals must be an array"); signals = []
    if connectors is None: connectors = []
    strict_connectors = not allow_legacy_compact
    conn_list = validate_connectors(connectors, path, rpt, contract, strict=strict_connectors) if isinstance(connectors, list) else []
    signal_names: set[str] = set()
    for i, sig in enumerate(signals):
        sid = validate_signal(sig, f"{path}.signals[{i}]", rpt, contract, device_type=dtype if isinstance(dtype, str) else None)
        if sid:
            if sid in signal_names: rpt.add("ERROR", f"{path}.signals[{i}]", "DUPLICATE_SIGNAL", f"duplicate signal/net id '{sid}'")
            signal_names.add(sid)
    if not isinstance(pins, list):
        if allow_legacy_compact:
            rpt.add("WARN", f"{path}.pins", "LEGACY_COMPACT", "pins[] absent or not array; accepted because legacy compact mode is enabled")
            return
        rpt.add("ERROR", f"{path}.pins", "PINS_NOT_ARRAY", "v4 requires explicit pins[]")
        pins = []
    connector_names = {str(c.get("name")) for c in conn_list if nonempty_str(c.get("name"))}
    pin_keys: set[tuple[str, int]] = set()
    for i, p in enumerate(pins):
        validate_pin(p, f"{path}.pins[{i}]", rpt, contract, signal_names, connector_names)
        if isinstance(p, dict):
            k = (str(p.get("connector", "")), int(p.get("cavity") or p.get("number") or -1))
            if k in pin_keys: rpt.add("ERROR", f"{path}.pins[{i}]", "DUPLICATE_PIN_CAVITY", f"duplicate connector/cavity {k}")
            pin_keys.add(k)
    if contract.get("rules", {}).get("pin_signal_cavity_equality", True) and not allow_legacy_compact:
        used, total, conn_ok = connector_used_sum(conn_list)
        if len(pins) != len(signals):
            rpt.add("ERROR", path, "PIN_SIGNAL_COUNT_MISMATCH", f"pins ({len(pins)}) must equal signals/nets ({len(signals)})")
        if conn_ok:
            if len(pins) != used:
                rpt.add("ERROR", path, "PIN_USED_CAVITY_MISMATCH", f"pins ({len(pins)}) must equal sum(connectors.used_cavities) ({used})")
            if used != total:
                rpt.add("ERROR", path, "USED_TOTAL_CAVITY_MISMATCH", f"sum(used_cavities) ({used}) must equal sum(total_cavities) ({total}) in v4 reusable device libraries")
    rpt.counters["devices"] = rpt.counters.get("devices", 0) + 1


def iter_system_devices(system: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for i, d in enumerate(system.get("devices", []) or []):
        if isinstance(d, dict): yield f"devices[{i}]", d
    for ci, comp in enumerate(system.get("components", []) or []):
        if not isinstance(comp, dict): continue
        for kind in ("sensors", "actuators", "devices"):
            for di, d in enumerate(comp.get(kind, []) or []):
                if isinstance(d, dict): yield f"components[{ci}].{kind}[{di}]", d


def validate_system(data: dict[str, Any], rpt: FileReport, contract: dict, allow_legacy_compact: bool = False) -> None:
    check_unknown(data, "system", "$", rpt, contract)
    check_required(data, "system", "$", rpt, contract)
    check_enum(data.get("priority"), "priorities", "$.priority", rpt, contract)
    check_enum(data.get("safety"), "safety_classes", "$.safety", rpt, contract)
    check_enum(data.get("system_level"), "system_levels", "$.system_level", rpt, contract)
    if "take_rate" in data and not is_num(data["take_rate"]): rpt.add("ERROR", "$.take_rate", "INVALID_NUMBER", "take_rate must be numeric percent")
    devices = list(iter_system_devices(data))
    if not devices:
        rpt.add("WARN", "$", "NO_DEVICES", "system contains no devices/components sensors/actuators")
    for p, d in devices:
        validate_device(d, "$.'" + p + "'" if "'" in p else f"$.{p}", rpt, contract, allow_legacy_compact=allow_legacy_compact)


def validate_component(data: dict[str, Any], rpt: FileReport, contract: dict, allow_legacy_compact: bool = False) -> None:
    check_unknown(data, "component", "$", rpt, contract)
    check_required(data, "component", "$", rpt, contract)
    found = False
    for kind in ("sensors", "actuators", "devices"):
        for i, d in enumerate(data.get(kind, []) or []):
            found = True
            validate_device(d, f"$.{kind}[{i}]", rpt, contract, allow_legacy_compact=allow_legacy_compact)
    if not found and ("signals" in data or "pins" in data):
        dtype = data.get("device_type") or ("SENSOR" if data.get("type") == "sensor" else "ACTUATOR" if data.get("type") == "actuator" else None)
        if dtype: data = dict(data, device_type=dtype)
        validate_device(data, "$", rpt, contract, allow_legacy_compact=allow_legacy_compact)


def validate_ecu(data: dict[str, Any], rpt: FileReport, contract: dict) -> None:
    check_unknown(data, "ecu", "$", rpt, contract)
    check_required(data, "ecu", "$", rpt, contract)
    check_enum(data.get("priority"), "priorities", "$.priority", rpt, contract)
    check_enum(data.get("safety"), "safety_classes", "$.safety", rpt, contract)
    connectors = data.get("connectors", []) or []
    if connectors:
        validate_connectors(connectors, "$", rpt, contract, strict=False)
    pins = data.get("pins")
    if not isinstance(pins, list):
        rpt.add("ERROR", "$.pins", "PINS_NOT_ARRAY", "ECU pins must be an array")
        return
    seen: set[tuple[str, int]] = set()
    for i, p in enumerate(pins):
        path = f"$.pins[{i}]"
        if not isinstance(p, dict):
            rpt.add("ERROR", path, "ECU_PIN_NOT_OBJECT", "ECU pin must be object"); continue
        check_unknown(p, "pin", path, rpt, contract, level="WARN")
        for k in required_keys(contract, "ecu_pin"):
            if k not in p or p.get(k) in (None, ""):
                rpt.add("ERROR", path, "MISSING_ECU_PIN_KEY", f"required ECU pin key '{k}' missing")
        conn = str(p.get("connector", "")); phys = p.get("physical_number")
        if not isinstance(phys, int) or isinstance(phys, bool) or phys < 1:
            rpt.add("ERROR", f"{path}.physical_number", "INVALID_PHYSICAL_NUMBER", "physical_number must be integer >= 1")
        else:
            key = (conn, phys)
            if key in seen: rpt.add("ERROR", path, "DUPLICATE_ECU_PIN", f"duplicate ECU pin {key}")
            seen.add(key)
        check_enum(canon_token(contract, "roles", p.get("role")), "roles", f"{path}.role", rpt, contract, required=True)
        check_enum(canon_token(contract, "interfaces", p.get("type")), "interfaces", f"{path}.type", rpt, contract, required=True)
        for key in ("electrical_capability", "diagnostic_flags"):
            if key in p and (not isinstance(p[key], int) or isinstance(p[key], bool) or p[key] < 0):
                rpt.add("ERROR", f"{path}.{key}", "INVALID_BITMASK", f"{key} must be non-negative integer")
        if p.get("role") == "OUTPUT" and p.get("electrical_capability", 0) == 0:
            rpt.add("WARN", path, "OUTPUT_WITHOUT_CAPABILITY", "OUTPUT pin has electrical_capability=0; strict mapper may not use it")
    rpt.counters["ecu_pins"] = len(pins)


def validate_file(path: Path, root: Path, contract: dict, allow_legacy_compact: bool = False) -> FileReport:
    rpt = FileReport(file=rel(path, root))
    data, err = read_json(path)
    if err:
        rpt.add("ERROR", "$", "INVALID_JSON", err); return rpt
    kind = infer_kind(data)
    rpt.kind = kind
    if not isinstance(data, dict):
        rpt.add("ERROR", "$", "TOP_NOT_OBJECT", "top-level JSON must be object"); return rpt
    if kind == "system": validate_system(data, rpt, contract, allow_legacy_compact=allow_legacy_compact)
    elif kind == "component": validate_component(data, rpt, contract, allow_legacy_compact=allow_legacy_compact)
    elif kind in ("sensor", "actuator"):
        d = dict(data)
        d.setdefault("device_type", "SENSOR" if kind == "sensor" else "ACTUATOR")
        validate_device(d, "$", rpt, contract, allow_legacy_compact=allow_legacy_compact)
    elif kind == "ecu": validate_ecu(data, rpt, contract)
    elif kind in ("bundle", "signal_group", "architecture", "architecture_export"):
        rpt.add("INFO", "$", "SKIPPED_KIND", f"kind '{kind}' has no strict library validator in this tool")
    else:
        rpt.add("WARN", "$", "UNKNOWN_KIND", f"cannot infer JSON kind; top-level type={data.get('type')!r}")
    return rpt


def render_text(result: ValidationResult, verbose: bool = False) -> str:
    lines: list[str] = []
    lines.append("E/E Architect Design JSON validation report")
    lines.append("=" * 40)
    for rpt in result.reports:
        status = "PASS" if rpt.errors == 0 else "FAIL"
        lines.append(f"{status:4s} {rpt.file} kind={rpt.kind} errors={rpt.errors} warnings={rpt.warnings}")
        if verbose or rpt.errors:
            for issue in rpt.issues:
                if verbose or issue.level == "ERROR":
                    lines.append(f"  [{issue.level}] {issue.path} {issue.code}: {issue.message}")
    lines.append("-" * 40)
    lines.append(f"files={len(result.reports)} errors={result.errors} warnings={result.warnings}")
    return "\n".join(lines) + "\n"


def write_reports(result: ValidationResult, outdir: Path, base_name: str = "validation_report") -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    json_obj = {
        "ok": result.ok, "files": len(result.reports), "errors": result.errors, "warnings": result.warnings,
        "reports": [
            {"file": r.file, "kind": r.kind, "errors": r.errors, "warnings": r.warnings, "counters": r.counters,
             "issues": [dataclasses.asdict(i) for i in r.issues]}
            for r in result.reports
        ]
    }
    (outdir / f"{base_name}.json").write_text(json.dumps(json_obj, indent=2, ensure_ascii=False), encoding="utf-8")
    (outdir / f"{base_name}.md").write_text("```text\n" + render_text(result, verbose=True) + "```\n", encoding="utf-8")
    with (outdir / f"{base_name}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["file", "kind", "errors", "warnings", "level", "path", "code", "message"])
        for r in result.reports:
            if not r.issues: w.writerow([r.file, r.kind, r.errors, r.warnings, "", "", "", ""])
            for i in r.issues:
                w.writerow([r.file, r.kind, r.errors, r.warnings, i.level, i.path, i.code, i.message])


def validate_paths(paths: Sequence[Path], root: Path, contract: dict, allow_legacy_compact: bool = False) -> ValidationResult:
    res = ValidationResult()
    for p in paths:
        res.reports.append(validate_file(p, root, contract, allow_legacy_compact=allow_legacy_compact))
    return res


def default_patterns_for_scope(contract: dict, scope: str) -> list[str]:
    dp = contract.get("default_paths", {})
    if scope == "systems": return list(dp.get("system_globs", []))
    if scope == "sensors": return list(dp.get("sensor_globs", []))
    if scope == "actuators": return list(dp.get("actuator_globs", []))
    if scope == "ecus": return list(dp.get("ecu_globs", []))
    return list(dp.get("library_globs", ["library/**/*.json"]))


def main_validate(scope: str = "library", description: str | None = None) -> int:
    ap = argparse.ArgumentParser(description=description or "Validate E/E Architect Design JSON files")
    ap.add_argument("paths", nargs="*", help="files or glob patterns. Defaults come from contract for the selected scope")
    ap.add_argument("--root", default=None, help="project root. Auto-detected by default")
    ap.add_argument("--contract", default=None, help="path to eec_json_contract.v4.json or project-specific contract")
    ap.add_argument("--legacy-compact", action="store_true", help="allow old signals[]-only devices without explicit pins[]")
    ap.add_argument("--outdir", default=None, help="optional output report directory")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON to stdout")
    ap.add_argument("--verbose", "-v", action="store_true", help="print warnings and info, not only failures")
    args = ap.parse_args()
    contract = load_contract(args.contract)
    root = discover_root(args.root or os.getcwd())
    patterns = args.paths or default_patterns_for_scope(contract, scope)
    paths = expand_patterns(patterns, root=root)
    res = validate_paths(paths, root, contract, allow_legacy_compact=args.legacy_compact)
    if args.outdir:
        write_reports(res, Path(args.outdir), base_name=f"{scope}_validation")
    if args.json:
        print(json.dumps({"ok": res.ok, "errors": res.errors, "warnings": res.warnings, "files": [r.file for r in res.reports]}, indent=2))
    else:
        print(render_text(res, verbose=args.verbose))
    return 0 if res.ok else 1


def backup_file(path: Path, suffix: str = ".bak") -> None:
    bak = path.with_suffix(path.suffix + suffix)
    if not bak.exists(): shutil.copy2(path, bak)


def normalize_inplace(data: Any, contract: dict) -> tuple[Any, bool]:
    modified = False
    def walk(obj: Any) -> None:
        nonlocal modified
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                if k in ("interface", "interface_type", "type") and isinstance(obj[k], str):
                    new = canon_token(contract, "interfaces", obj[k]) if k in ("interface", "interface_type", "type") else obj[k]
                    # For signal type fields, avoid changing U8 etc; only normalize known interface-like fields.
                    if k == "type" and obj.get("role") is None and obj.get("physical_number") is None:
                        new = obj[k]
                    if new != obj[k]: obj[k] = new; modified = True
                elif k == "unit" and isinstance(obj[k], str):
                    new = canon_token(contract, "units", obj[k]);
                    if new != obj[k]: obj[k] = new; modified = True
                elif k == "role" and isinstance(obj[k], str):
                    new = canon_token(contract, "roles", obj[k]);
                    if new != obj[k]: obj[k] = new; modified = True
                elif k == "required_reset_state" and isinstance(obj[k], str):
                    new = canon_token(contract, "reset_states", obj[k]);
                    if new != obj[k]: obj[k] = new; modified = True
                if isinstance(obj.get(k), (dict, list)): walk(obj[k])
        elif isinstance(obj, list):
            for item in obj: walk(item)
    walk(data)
    return data, modified


def migrate_legacy_device(data: dict[str, Any], contract: dict) -> tuple[dict[str, Any], bool]:
    modified = False
    # Unwrap runtime exports: {"sensor": {...}, "signals": [...]} or {"actuator": {...}}
    for nested_key, dtype in (("sensor", "SENSOR"), ("actuator", "ACTUATOR")):
        if nested_key in data and isinstance(data[nested_key], dict):
            nested = data[nested_key]
            new: dict[str, Any] = {"type": nested_key, "device_type": dtype}
            for k, v in {**nested, **{kk: vv for kk, vv in data.items() if kk not in ("sensor", "actuator")}}.items():
                if k not in ("sensor", "actuator"):
                    new[k] = v
            data = new; modified = True
            break
    kind = data.get("type")
    if kind in ("sensor", "actuator"):
        data.setdefault("device_type", "SENSOR" if kind == "sensor" else "ACTUATOR"); modified = True
    # signals: name -> prefix, interface_type -> interface, defaults
    if isinstance(data.get("signals"), list):
        for sig in data["signals"]:
            if not isinstance(sig, dict): continue
            if "prefix" not in sig and "name" in sig: sig["prefix"] = sig.get("name"); modified = True
            sig.setdefault("count", 1); sig.setdefault("type", "U1"); sig.setdefault("unit", "NONE")
            if "interface" not in sig and "interface_type" in sig: sig["interface"] = sig.get("interface_type"); modified = True
            if "min" not in sig and "min_value" in sig: sig["min"] = sig.get("min_value"); modified = True
            if "max" not in sig and "max_value" in sig: sig["max"] = sig.get("max_value"); modified = True
            sig.setdefault("min", 0); sig.setdefault("max", 1); sig.setdefault("resolution", 1); sig.setdefault("scaling", 1)
            if "role" not in sig:
                iface = canon_token(contract, "interfaces", sig.get("interface"))
                if iface == "POWER": sig["role"] = "SUPPLY"
                elif iface == "GROUND": sig["role"] = "GROUND"
                elif data.get("device_type") == "ACTUATOR": sig["role"] = contract.get("rules", {}).get("actuator_default_signal_role", "INPUT")
                else: sig["role"] = contract.get("rules", {}).get("sensor_default_signal_role", "OUTPUT")
                modified = True
            sig.setdefault("priority", data.get("priority", "MEDIUM")); sig.setdefault("safety", data.get("safety", "QM"))
    # create explicit pins/connectors from signals if needed
    if data.get("device_type") in ("SENSOR", "ACTUATOR") and isinstance(data.get("signals"), list):
        sigs = data["signals"]
        if "connectors" not in data or not isinstance(data["connectors"], list) or not data["connectors"]:
            data["connectors"] = [{"name": "X1", "family": "CUSTOM", "gender": "UNKNOWN", "total_cavities": len(sigs), "used_cavities": len(sigs), "max_pin_number": len(sigs)}]
            modified = True
        else:
            # make connector count v4-compliant for reusable library files
            total = sum(int(c.get("total_cavities", 0) or 0) for c in data["connectors"] if isinstance(c, dict))
            if total != len(sigs) and len(data["connectors"]) == 1 and isinstance(data["connectors"][0], dict):
                data["connectors"][0]["total_cavities"] = len(sigs); data["connectors"][0]["used_cavities"] = len(sigs); data["connectors"][0]["max_pin_number"] = max(int(data["connectors"][0].get("max_pin_number", 0) or 0), len(sigs))
                modified = True
        if "pins" not in data or not isinstance(data["pins"], list) or len(data["pins"]) != len(sigs):
            conn_name = data.get("connectors", [{}])[0].get("name", "X1") if isinstance(data.get("connectors"), list) else "X1"
            pins = []
            for i, sig in enumerate(sigs, start=1):
                prefix = signal_id(sig) or f"NET_{i}"
                iface = canon_token(contract, "interfaces", sig.get("interface"))
                role = canon_token(contract, "roles", sig.get("role"))
                pins.append({"number": i, "name": f"P{i}_{prefix}", "connector": conn_name, "cavity": i, "role": role, "interface_type": iface, "signal": prefix,
                             "electrical_requirement": int(sig.get("electrical_requirement", 0) or 0), "nominal_current": float(sig.get("nominal_current", 0.0) or 0.0), "inrush_current": float(sig.get("inrush_current", 0.0) or 0.0), "max_voltage": float(sig.get("max_voltage", 0.0) or 0.0), "diagnostics_required": int(sig.get("diagnostics_required", 0) or 0), "ground_class": sig.get("ground_class", "UNCLASSIFIED"), "required_reset_state": sig.get("required_reset_state", "OFF")})
            data["pins"] = pins; modified = True
    data, mod2 = normalize_inplace(data, contract); modified = modified or mod2
    return data, modified

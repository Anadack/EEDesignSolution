#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS


def esc(value: Any) -> str:
    return (
        str("" if value is None else value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object")
    return data


def find_base() -> Path:
    script_dir = Path(__file__).resolve().parent
    if (script_dir.parent / "exports").exists():
        return script_dir.parent
    return script_dir


def get_architecture(data: dict[str, Any]) -> dict[str, Any]:
    arch = data.get("architecture", data)
    if not isinstance(arch, dict):
        raise ValueError("architecture must be an object")
    return arch


def collect_signal_targets(arch: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    targets: dict[str, list[dict[str, str]]] = {}
    ecus = arch.get("ecus", [])
    if not isinstance(ecus, list):
        return targets
    for ecu in ecus:
        if not isinstance(ecu, dict):
            continue
        ecu_name = str(ecu.get("name", "ECU"))
        variant = str(ecu.get("variant", ""))
        pins = ecu.get("pins", [])
        if not isinstance(pins, list):
            continue
        for pin in pins:
            if not isinstance(pin, dict):
                continue
            signal = pin.get("signal")
            if not isinstance(signal, dict) or not signal.get("name"):
                continue
            signal_name = str(signal.get("name"))
            targets.setdefault(signal_name, []).append(
                {
                    "ecu": ecu_name,
                    "variant": variant,
                    "connector": str(pin.get("connector", "")),
                    "pin": str(pin.get("physical_number", "")),
                    "interface": str(signal.get("interface_type", pin.get("type", ""))),
                    "role": str(pin.get("role", "")),
                }
            )
    return targets


def summarize_systems(arch: dict[str, Any], signal_targets: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    systems_out: list[dict[str, Any]] = []
    systems = arch.get("systems", [])
    if not isinstance(systems, list):
        return systems_out

    for system in systems:
        if not isinstance(system, dict):
            continue
        devices = system.get("devices", [])
        if not isinstance(devices, list):
            devices = []
        devices_out = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            pins = device.get("pins", [])
            if not isinstance(pins, list):
                pins = []
            flows = []
            for pin in pins:
                if not isinstance(pin, dict):
                    continue
                signal = pin.get("signal")
                if not isinstance(signal, dict) or not signal.get("name"):
                    continue
                signal_name = str(signal.get("name"))
                flows.append(
                    {
                        "signal": signal_name,
                        "signal_type": str(signal.get("type", "")),
                        "source_pin": str(pin.get("name", "")),
                        "source_role": str(pin.get("role", "")),
                        "targets": signal_targets.get(signal_name, []),
                    }
                )
            flows.sort(key=lambda item: item["signal"])
            devices_out.append(
                {
                    "name": str(device.get("name", "Device")),
                    "type": str(device.get("type", "UNKNOWN")),
                    "flows": flows,
                }
            )
        systems_out.append({"name": str(system.get("name", "System")), "devices": devices_out})
    return systems_out


def render_target_cards(targets: list[dict[str, str]]) -> str:
    if not targets:
        return '<div class="target-card empty">No physical target resolved.</div>'
    return "".join(
        f"""
        <div class="target-card">
          <div class="target-head">
            <strong>{esc(target['ecu'])}</strong>
            <span>{esc(target['variant'])}</span>
          </div>
          <div class="target-meta">{esc(target['connector'])}/{esc(target['pin'])} · {esc(target['interface'])} · {esc(target['role'])}</div>
        </div>"""
        for target in targets
    )


def render_systems(systems: list[dict[str, Any]]) -> str:
    sections = []
    for system in systems:
        device_html = []
        for device in system["devices"]:
            flow_rows = []
            for flow in device["flows"]:
                flow_rows.append(
                    f"""
            <article class="flow-row">
              <div class="flow-source">
                <div class="flow-eyebrow">Source</div>
                <h4>{esc(flow['signal'])}</h4>
                <p>{esc(flow['source_pin'])} · {esc(flow['source_role'])} · {esc(flow['signal_type'])}</p>
              </div>
              <div class="flow-arrow">→</div>
              <div class="flow-targets">
{render_target_cards(flow['targets'])}
              </div>
            </article>"""
                )
            if not flow_rows:
                flow_rows.append('<div class="empty">No signal flow defined.</div>')
            device_html.append(
                f"""
          <article class="device-card {esc(device['type'].lower())}">
            <div class="device-head">
              <div>
                <span class="eyebrow">{esc(device['type'])}</span>
                <h3>{esc(device['name'])}</h3>
              </div>
              <span class="badge">{len(device['flows'])} flow(s)</span>
            </div>
            <div class="flow-stack">
{''.join(flow_rows)}
            </div>
          </article>"""
            )
        sections.append(
            f"""
      <section class="system-section">
        <div class="section-head">
          <h2>{esc(system['name'])}</h2>
          <p>Logical-to-physical signal routes grouped by device.</p>
        </div>
        <div class="device-grid">
{''.join(device_html)}
        </div>
      </section>"""
        )
    return "\n".join(sections)


def build_html(arch_name: str, systems: list[dict[str, Any]]) -> str:
    system_count = len(systems)
    device_count = sum(len(system["devices"]) for system in systems)
    flow_count = sum(len(device["flows"]) for system in systems for device in system["devices"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(arch_name)} - Signal Flow</title>
  <style>
    :root {{
      --bg: #070b12;
      --surface0: #0b1018;
      --surface1: #0f1622;
      --surface2: #151e2e;
      --surface3: #1d2939;
      --surface4: #273548;
      --border0: #1a2436;
      --border1: #233149;
      --border2: #2d3e5c;
      --text: #cfdaea;
      --text-dim: #6c83a2;
      --text-fade: #46566e;
      --cyan: #2ee6ff;
      --green: #2ee6a0;
      --amber: #ffb43d;
      --red: #ff5a78;
      --purple: #b388ff;
      --teal: #19d6c0;
      --blue: #5aa6ff;
      --accent: var(--teal);
      --accent2: var(--cyan);
      --ok: var(--green);
      --warn: var(--amber);
      --err: var(--red);
      --ink: var(--text);
      --muted: var(--text-dim);
      --panel: var(--surface1);
      --line: var(--border1);
      --shadow: 0 8px 30px rgba(0,0,0,.45);
      --sensor: #19d6c0;
      --actuator: #ffb43d;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Aptos, "Segoe UI Variable", sans-serif; color: var(--text); background: radial-gradient(circle at top left, rgba(46,230,255,0.06), transparent 28%), var(--bg); }}
    .page {{ max-width: 1480px; margin: 0 auto; padding: 28px; display: grid; gap: 24px; }}
    .hero, .summary, .system-section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 24px; box-shadow: var(--shadow); }}
    .hero {{ padding: 28px; display: grid; gap: 12px; }}
    .hero h1 {{ margin: 0; font-size: clamp(2rem, 4vw, 3.4rem); letter-spacing: -0.04em; }}
    .hero p {{ margin: 0; color: var(--muted); max-width: 72ch; }}
    .summary {{ padding: 18px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }}
    .summary-card {{ padding: 16px; border-radius: 18px; background: var(--surface2); border: 1px solid var(--border1); }}
    .summary-card .label {{ font-size: 0.82rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.08em; }}
    .summary-card .value {{ font-size: 2rem; font-weight: 700; margin-top: 8px; }}
    .system-section {{ padding: 22px; display: grid; gap: 18px; }}
    .section-head h2 {{ margin: 0; font-size: 1.6rem; }}
    .section-head p {{ margin: 6px 0 0; color: var(--muted); }}
    .device-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; }}
    .device-card {{ padding: 18px; border-radius: 20px; background: var(--surface2); border: 1px solid var(--border1); }}
    .device-card.sensor {{ border-left: 5px solid rgba(15, 118, 110, 0.85); }}
    .device-card.actuator {{ border-left: 5px solid rgba(180, 83, 9, 0.85); }}
    .device-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .device-head h3 {{ margin: 4px 0 0; font-size: 1.2rem; }}
    .eyebrow {{ font-size: 0.78rem; font-weight: 800; letter-spacing: 0.12em; color: var(--muted); text-transform: uppercase; }}
    .badge {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; background: rgba(46,230,255,0.1); color: var(--cyan); font-size: 0.8rem; font-weight: 700; }}
    .flow-stack {{ margin-top: 16px; display: grid; gap: 14px; }}
    .flow-row {{ display: grid; grid-template-columns: minmax(180px, 220px) 50px 1fr; gap: 14px; align-items: center; padding: 14px; border-radius: 18px; background: var(--surface2); border: 1px solid var(--border1); }}
    .flow-source h4 {{ margin: 4px 0 0; font-size: 1.05rem; }}
    .flow-source p {{ margin: 6px 0 0; color: var(--muted); font-size: 0.92rem; }}
    .flow-arrow {{ text-align: center; font-size: 1.8rem; color: var(--accent2); font-weight: 700; }}
    .flow-targets {{ display: grid; gap: 10px; }}
    .target-card {{ padding: 12px; border-radius: 14px; background: var(--surface3); border: 1px solid var(--border1); }}
    .target-head {{ display: flex; gap: 8px; align-items: baseline; }}
    .target-head span, .target-meta, .empty {{ color: var(--muted); }}
    .target-meta {{ margin-top: 6px; font-size: 0.9rem; }}
    @media (max-width: 980px) {{ .device-grid {{ grid-template-columns: 1fr; }} .flow-row {{ grid-template-columns: 1fr; }} .flow-arrow {{ display: none; }} }}
{OVERFLOW_GUARD_CSS}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">Signal Flow</span>
      <h1>{esc(arch_name)}</h1>
      <p>Trace each logical signal from its source device pin to the resolved physical ECU target, grouped by system and device for routing review.</p>
    </section>
    <section class="summary">
      <article class="summary-card"><div class="label">Systems</div><div class="value">{system_count}</div></article>
      <article class="summary-card"><div class="label">Devices</div><div class="value">{device_count}</div></article>
      <article class="summary-card"><div class="label">Signal Flows</div><div class="value">{flow_count}</div></article>
    </section>
{render_systems(systems)}
  </main>
</body>
</html>"""


def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_physical_architecture.json"
    if not json_path.exists():
        raise SystemExit(f"Missing file: {json_path}")
    output_path = base / "exports" / "architecture_signal_flow.html"

    arch = get_architecture(load_json(json_path))
    signal_targets = collect_signal_targets(arch)
    systems = summarize_systems(arch, signal_targets)
    output_path.write_text(build_html(str(arch.get("name", "Architecture")), systems), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
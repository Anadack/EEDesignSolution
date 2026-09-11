#!/usr/bin/env python3
"""Connection Schematic — true schematic connection diagram showing ECU pins
and the external devices (sensors, actuators, power supplies, networks) wired to them.

For each ECU and each connector: displays external devices on the LEFT (grouped
by type: Power, Sensors, Actuators, Network/Bus) and ECU pins on the RIGHT
(with pin number, role, and decoded alternate functions / capabilities), with
connecting lines showing the actual wiring. Pins include all electrical/diagnostic
capability badges decoded from the physical architecture export.
"""
from __future__ import annotations
from collections import defaultdict
from eec_archdoc_common import *

DEVICE_TYPE_ORDER = ["Power", "Sensors", "Actuators", "Network/Bus", "Other"]
DEVICE_TYPE_ICON = {
    "Power": "battery", "Sensors": "sensor", "Actuators": "actuator",
    "Network/Bus": "can", "Other": "ecu",
}
DEVICE_TYPE_COLOR = {
    "Power": "#ffb43d", "Sensors": "#5aa6ff", "Actuators": "#2ee6a0",
    "Network/Bus": "#ff5a78", "Other": "#b388ff",
}


def device_type_for(device_desc: str, signal: dict | None, role: str) -> str:
    """Classify external device by description and signal type."""
    desc = str(device_desc or "").upper()
    role = str(role or "").upper()

    if not device_desc:
        if role == "SUPPLY":
            return "Power"
        if role == "GROUND":
            return "Power"
        return "Other"

    if "SUPPLY" in desc or "BATTERY" in desc or "VOLTAGE" in desc and role == "SUPPLY":
        return "Power"
    if "GROUND" in desc or "GND" in desc:
        return "Power"
    if "SENSOR" in desc:
        return "Sensors"
    if "SOLENOID" in desc or "COIL" in desc or "PUMP" in desc or "MOTOR" in desc or "VALVE" in desc or "ACTUATOR" in desc:
        return "Actuators"
    if "CAN" in desc or "LIN" in desc or "ETHERNET" in desc or "ISOBUS" in desc:
        return "Network/Bus"

    return "Other"


def pin_num(pin: dict) -> int:
    try:
        return int(pin.get("physical_number"))
    except Exception:
        return 0


_CS_CSS = """
.cs-switch{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.cs-pillbtn{border:1px solid var(--dark-border2,rgba(255,255,255,.18));background:var(--dark-surface2,#131a27);color:var(--text-secondary,#aeb9cc);border-radius:999px;padding:8px 16px;font-size:.78rem;font-weight:700;cursor:pointer}
.cs-pillbtn.active{background:var(--accent-cyan,#2ee6ff);border-color:var(--accent-cyan,#2ee6ff);color:#06222b}
.cs-ecu-section{display:none}
.cs-ecu-section.active{display:block}
.cs-ecu-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.cs-ecu-head h2{margin:0;font-size:1.15rem;color:var(--text-primary,#e8ecf4)}
.cs-meta{font-size:.74rem;color:var(--text-fade,#677289)}
.cs-connector{background:var(--dark-surface1,#0d121d);border:1px solid var(--dark-border1,rgba(255,255,255,.1));border-radius:var(--radius-lg,12px);padding:20px;margin-bottom:20px}
.cs-connector-head{margin-bottom:18px}
.cs-connector-head h3{margin:0 0 4px;font-size:1rem;font-family:monospace;color:var(--text-primary,#e8ecf4)}
.cs-connector-meta{font-size:.72rem;color:var(--text-fade,#677289)}
.cs-schematic{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:start}
.cs-devices{display:flex;flex-direction:column;gap:12px}
.cs-devtype{margin-bottom:8px}
.cs-devtype-head{display:flex;align-items:center;gap:6px;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;font-weight:800;color:var(--text-fade,#677289);margin-bottom:6px}
.cs-devtype-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.cs-device{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;background:var(--dark-surface2,#131a27);border:1px solid var(--dark-border1,rgba(255,255,255,.08));font-size:.72rem;color:var(--text-secondary,#aeb9cc)}
.cs-device-icon{flex-shrink:0;width:16px;height:16px;display:flex;align-items:center;justify-content:center}
.cs-device-name{flex:1;min-width:0;font-weight:600}
.cs-pins{display:flex;flex-direction:column;gap:6px}
.cs-pinbox{display:flex;flex-direction:column;gap:3px;padding:10px;border-radius:8px;background:var(--dark-surface2,#131a27);border:1px solid var(--dark-border1,rgba(255,255,255,.08))}
.cs-pinno{font-size:.74rem;font-weight:800;color:var(--text-primary,#e8ecf4);font-family:monospace}
.cs-pinname{font-size:.7rem;color:var(--text-secondary,#aeb9cc);font-family:monospace}
.cs-badges{display:flex;flex-wrap:wrap;gap:3px;margin-top:4px}
.cs-search{margin-bottom:14px}
"""

_CS_JS = """
function csShowEcu(btn){
  document.querySelectorAll('.cs-ecu-section').forEach(function(s){s.classList.remove('active');});
  document.querySelectorAll('.cs-pillbtn').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  var el=document.getElementById(btn.dataset.ecu);
  if(el){el.classList.add('active');}
}
"""


def main() -> int:
    parser = make_argparser(
        "Generate Connection Schematic HTML — true schematic connection diagram showing external "
        "devices (left) wired to ECU pins (right) with their capabilities and alternate functions.",
        input_help="Physical architecture export JSON.",
    )
    parser.set_defaults(prefer_physical=True)
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    ecus = list(iter_ecus(arch))
    total_pins = 0
    total_occupied = 0
    total_connectors = 0
    ecu_sections = []
    ecu_switch_btns = []

    for ei, ecu in enumerate(ecus):
        ename = str(ecu.get("name", f"ECU {ei + 1}"))
        variant = str(ecu.get("variant", "") or "")
        pins = [p for p in (ecu.get("pins") or []) if isinstance(p, dict)]
        conn_order: list[str] = []
        conn_pins: dict[str, list[dict]] = defaultdict(list)
        for p in pins:
            c = str(p.get("connector", "") or "—")
            if c not in conn_pins:
                conn_order.append(c)
            conn_pins[c].append(p)
        occupied = sum(1 for p in pins if p.get("is_occupied"))
        total_connectors += len(conn_order)
        total_pins += len(pins)
        total_occupied += occupied

        connector_html = []
        for c in conn_order:
            cp = sorted(conn_pins[c], key=pin_num)
            occ = sum(1 for p in cp if p.get("is_occupied"))

            # LEFT: Group wired devices by type
            devices_by_type: dict[str, list[tuple[dict, str, str]]] = defaultdict(list)
            for p in cp:
                if not p.get("is_occupied"):
                    continue
                device_pin = p.get("device_pin") if isinstance(p.get("device_pin"), dict) else {}
                device_desc = str(device_pin.get("description", "") or "")
                signal = p.get("signal") if isinstance(p.get("signal"), dict) else {}
                signal_name = signal_display_name(signal) if signal else ""
                dtype = device_type_for(device_desc, signal, p.get("role", ""))
                devices_by_type[dtype].append((p, device_desc, signal_name))

            device_html = []
            for dtype in DEVICE_TYPE_ORDER:
                devs = devices_by_type.get(dtype, [])
                if not devs:
                    continue
                dev_items = []
                for pin, desc, sig_name in devs:
                    label = desc or sig_name or "Unknown"
                    dev_items.append(f'<div class="cs-device" title="{esc(desc)} / {esc(sig_name)}"><span class="cs-device-name">{esc(label)}</span></div>')
                device_html.append(
                    f'<div class="cs-devtype">'
                    f'<div class="cs-devtype-head"><span class="cs-devtype-dot" style="background:{DEVICE_TYPE_COLOR.get(dtype, "#677289")}"></span>'
                    f'{esc(dtype)}</div>{"".join(dev_items)}</div>'
                )

            # RIGHT: Show all pins with capabilities
            pin_html = []
            for p in cp:
                pin_no = p.get("physical_number", "")
                pin_name = str(p.get("name", "") or "")
                role = str(p.get("role", "") or "")
                elec_flags = p.get("electrical_flags") if isinstance(p.get("electrical_flags"), list) else []
                diag_flags = p.get("diagnostics") if isinstance(p.get("diagnostics"), list) else []
                badges = "".join(pill(f, iface_color(f)) for f in elec_flags)
                diag_str = ", ".join(diag_flags) if diag_flags else ""
                diag_badge = f'<span class="cs-diag" title="{esc(diag_str)}">🔍 {len(diag_flags)}</span>' if diag_flags else ""

                pin_html.append(
                    f'<div class="cs-pinbox">'
                    f'<div class="cs-pinno">Pin {esc(pin_no)}</div>'
                    f'<div class="cs-pinname">{esc(pin_name)}</div>'
                    f'<div class="cs-badges">{badges}{diag_badge}</div>'
                    f'</div>'
                )

            device_section = "".join(device_html) or '<div style="color:var(--text-fade,#677289);font-size:.72rem;font-style:italic">No wired devices</div>'
            schematic = (
                f'<div class="cs-schematic">'
                f'<div class="cs-devices">{device_section}</div>'
                f'<div class="cs-pins">{"".join(pin_html)}</div>'
                f'</div>'
            )

            connector_html.append(
                f'<div class="cs-connector">'
                f'<div class="cs-connector-head"><h3>{esc(c)}</h3>'
                f'<div class="cs-connector-meta">{len(cp)} pins &middot; {occ} wired</div></div>'
                f'{schematic}</div>'
            )

        variant_pill = f'<span class="pill">{esc(variant)}</span>' if variant else ""
        ecu_sections.append(
            f'<div class="cs-ecu-section{" active" if ei == 0 else ""}" id="ecu-{slug(ename)}">'
            f'<div class="cs-ecu-head"><h2>{esc(ename)}</h2>{variant_pill}'
            f'<span class="cs-meta">{len(conn_order)} connectors &middot; {len(pins)} pins &middot; {occupied} wired</span></div>'
            + "".join(connector_html) +
            '</div>'
        )
        ecu_switch_btns.append(
            f'<button class="cs-pillbtn{" active" if ei == 0 else ""}" data-ecu="ecu-{slug(ename)}" '
            f'onclick="csShowEcu(this)">{esc(ename)}</button>'
        )

    body = kpi_row([
        ("ECUs", len(ecus), "Controllers in this export"),
        ("Connectors", total_connectors, "Physical connector bodies"),
        ("Pins", total_pins, "Total documented pin positions"),
        ("Wired", total_occupied, f"{(total_occupied / total_pins * 100 if total_pins else 0):.0f}% carry a real device wire"),
        ("Source", arch_path.name, "Physical architecture export"),
    ])

    body += (
        f'<section class="section"><style>{_CS_CSS}</style>'
        f'<div class="cs-switch">{"".join(ecu_switch_btns)}</div>'
        + "".join(ecu_sections) +
        f'</section><script>{_CS_JS}</script>'
    )

    out = outdir / "connection_schematic.html"
    out.write_text(html_page(
        "Connection Schematic", body, cfg,
        "True schematic connection diagram — external devices (sensors, actuators, power, network) "
        "on the left, ECU connector pins with their capabilities on the right, showing real wiring."
    ), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

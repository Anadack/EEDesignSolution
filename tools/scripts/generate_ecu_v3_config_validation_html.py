#!/usr/bin/env python3
"""Generate ECU Pinout v3 config/validation template — EXACT template, data only from architecture JSON.
Keeps template structure 100% intact. Only replaces USER CONFIGURATION ZONE (ecus, devices,
signals, ecuPins, wiringSchemas) with real data from architecture export.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from eec_archdoc_common import *


def pad_pin(value) -> str:
    try:
        return str(int(value)).zfill(2)
    except Exception:
        return "00"


def esc_js(s: str) -> str:
    """Escape string for JavaScript."""
    return (
        str(s or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def pin_functions(pin: dict) -> list[str]:
    """Decode pin capabilities into function labels for template."""
    role = str(pin.get("role") or "").upper()
    pin_type = str(pin.get("type") or pin.get("interface_type") or "").upper()
    elec_flags = pin.get("electrical_flags") or []

    funcs = []
    if role == "SUPPLY":
        funcs.append("SUPPLY_VBAT")
    elif role == "GROUND":
        funcs.append("GND")
    elif pin_type == "CAN":
        funcs.append("CAN")
    elif pin_type == "LIN":
        funcs.append("LIN")
    elif role == "OUTPUT":
        has_hsd = any("HIGH_SIDE" in str(f).upper() for f in elec_flags)
        has_lsd = any("LOW_SIDE" in str(f).upper() for f in elec_flags)
        if pin_type == "PWM":
            funcs.append("PWM")
            if has_hsd:
                funcs.append("HSD")
            elif has_lsd:
                funcs.append("LSD")
            else:
                funcs.append("DO")
        else:
            if has_hsd:
                funcs.append("HSD")
            if has_lsd:
                funcs.append("LSD")
            funcs.append("DO")
    elif role == "INPUT":
        if pin_type == "FREQUENCY":
            funcs.append("FREQ")
        elif pin_type == "RESISTANCE":
            funcs.append("RES")
        elif pin_type in ("ANALOG", "VOLTAGE"):
            funcs.append("AI")
        else:
            funcs.append("DI")
    elif pin_type == "ANALOG_OUTPUT":
        funcs.append("AO")
    else:
        funcs.append("NC")

    # Add pull-up/down if present
    if any("PULL" in str(f).upper() for f in elec_flags):
        if any("HIGH_SIDE" in str(f).upper() for f in elec_flags):
            funcs.insert(0, "PULL_UP")
        else:
            funcs.insert(0, "PULL_DOWN")

    return funcs if funcs else ["NC"]


def main() -> int:
    parser = make_argparser(
        "Generate ECU Pinout v3 config/validation template — exact template with real architecture data",
        input_help="Physical architecture export JSON.",
    )
    parser.set_defaults(prefer_physical=True)
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    # Resolve the template from the vendored templates/ dir next to this script
    # (portable) with an optional --template override. Never hardcode an
    # author-machine absolute path.
    import sys as _sys
    template_name = "ECU_Pinout_MultiECU_Config_Validation_Template.html"
    template_path = Path(getattr(args, "template", None)
                         or (Path(__file__).parent / "templates" / template_name))

    if not template_path.exists():
        # Non-fatal: report and skip so the batch pipeline still completes.
        print(f"[SKIP] {Path(__file__).name}: vendored template not found "
              f"({template_path}). Provide it via --template or place it in "
              f"tools/scripts/templates/{template_name}.", file=_sys.stderr)
        return 0

    # Read entire template
    template_html = template_path.read_text(encoding="utf-8")

    # Find USER CONFIGURATION ZONE boundaries
    zone_start = template_html.find("/* ==========================================================================\n   USER CONFIGURATION ZONE")
    zone_end = template_html.find("   END USER CONFIGURATION ZONE — DO NOT EDIT BELOW")

    if zone_start == -1 or zone_end == -1:
        print("Could not find USER CONFIGURATION ZONE markers", file=__import__('sys').stderr)
        return 1

    # Get the template before and after the zone
    before = template_html[:zone_start]
    after = template_html[zone_end:]

    # Build the new configuration zone from architecture data
    ecus_list = list(iter_ecus(arch))

    # Build ecus array
    ecus_js = "const ecus=[\n"
    for i, ecu in enumerate(ecus_list):
        ename = str(ecu.get("name", f"ECU_{i}"))
        variant = str(ecu.get("variant") or "")
        ecus_js += f' {{id:"{esc_js(ename)}",name:"{esc_js(ename)}",short:"{esc_js(ename[:20])}",description:"{esc_js(variant or "Controller")}"}}'
        if i < len(ecus_list) - 1:
            ecus_js += ","
        ecus_js += "\n"
    ecus_js += "];\n"

    # Build devices (simple mapping from wired pins)
    devices_dict = {}
    signal_id_counter = 0
    for ecu in ecus_list:
        pins = [p for p in (ecu.get("pins") or []) if isinstance(p, dict) and p.get("is_occupied")]
        for pin in pins:
            device_pin = pin.get("device_pin") or {}
            desc = str(device_pin.get("description") or "Device")
            if desc not in devices_dict:
                signal_id_counter += 1
                # Infer device kind from name/description, not pin role
                desc_upper = desc.upper()
                if "SENSOR" in desc_upper or "PROBE" in desc_upper or "SWITCH" in desc_upper:
                    kind = "sensor"
                    symbol = "sensor"
                elif "VALVE" in desc_upper or "PUMP" in desc_upper or "MOTOR" in desc_upper or "ACTUATOR" in desc_upper or "SOLENOID" in desc_upper:
                    kind = "actuator"
                    symbol = "actuator"
                elif "CAN" in desc_upper or "LIN" in desc_upper or "ETHERNET" in desc_upper:
                    kind = "network"
                    symbol = "network"
                elif "SUPPLY" in desc_upper or "VBAT" in desc_upper or "BATTERY" in desc_upper:
                    kind = "power"
                    symbol = "power"
                else:
                    kind = "sensor" if pin.get("role", "").upper() == "INPUT" else "actuator" if pin.get("role", "").upper() == "OUTPUT" else "power"
                    symbol = "sensor" if pin.get("role", "").upper() == "INPUT" else "actuator"
                devices_dict[desc] = {
                    "name": desc,
                    "kind": kind,
                    "type": str(pin.get("type") or "unknown"),
                    "symbol": symbol,
                    "schema": "schema-ai-3wire",
                }

    devices_js = "const devices={\n"
    device_keys = list(devices_dict.keys())
    for i, (key, dev) in enumerate(devices_dict.items()):
        safe_key = key.replace(" ", "").replace("-", "").lower()[:20]
        devices_js += f' {safe_key}:{{name:"{esc_js(dev["name"])}",kind:"{dev["kind"]}",type:"{esc_js(dev["type"])}",symbol:"{dev["symbol"]}",schema:"{dev["schema"]}",tech:{{}}}}'
        if i < len(devices_dict) - 1:
            devices_js += ","
        devices_js += "\n"
    devices_js += "};\n"

    # Build signals from pins
    signals_dict = {}
    for ecu in ecus_list:
        pins = [p for p in (ecu.get("pins") or []) if isinstance(p, dict) and p.get("is_occupied")]
        for pin in pins:
            sig_name = str(pin.get("name") or "SIGNAL")
            if sig_name not in signals_dict:
                device_pin = pin.get("device_pin") or {}
                role = str(pin.get("role") or "").upper()
                pin_type = str(pin.get("type") or "").upper()
                funcs = pin_functions(pin)

                # Classify signal based on pin capabilities and role
                if "SUPPLY" in role or "GROUND" in role:
                    sig_class = "Power"
                elif "AI" in funcs or "ANALOG" in pin_type or "VOLTAGE" in pin_type or "RESISTANCE" in pin_type:
                    sig_class = "Analog"
                elif "AO" in funcs:
                    sig_class = "Analog"
                elif "PWM" in funcs or "FREQ" in funcs:
                    sig_class = "Digital"
                elif "DI" in funcs or "DO" in funcs or "HSD" in funcs or "LSD" in funcs:
                    sig_class = "Digital"
                elif "CAN" in funcs or "LIN" in funcs or "ETHERNET" in pin_type:
                    sig_class = "Network"
                else:
                    sig_class = "Digital"

                signals_dict[sig_name] = {
                    "name": sig_name,
                    "class": sig_class,
                    "electrical": "Signal",
                    "unit": "—",
                    "direction": "Sensor → ECU" if role == "INPUT" else "ECU → Actuator" if role == "OUTPUT" else "Power",
                    "producer": str(device_pin.get("description") or "Source"),
                }

    signals_js = "const signals={\n"
    sig_keys = list(signals_dict.keys())
    for i, (sig_id, sig) in enumerate(signals_dict.items()):
        signals_js += f' SIG_{sig_id}:{{name:"{esc_js(sig["name"])}",class:"{sig["class"]}",electrical:"{sig["electrical"]}",unit:"{sig["unit"]}",direction:"{sig["direction"]}",producer:"{esc_js(sig["producer"])}",consumers:[],safety:"—",diag:"—",schema:"schema-ai-3wire"}}'
        if i < len(signals_dict) - 1:
            signals_js += ","
        signals_js += "\n"
    signals_js += "};\n"

    # Build ecuPins array
    ecuPins_js = "const ecuPins=[\n"
    pin_idx = 0
    for ecu in ecus_list:
        ename = str(ecu.get("name", "ECU"))
        pins = [p for p in (ecu.get("pins") or []) if isinstance(p, dict)]
        pins = sorted(pins, key=lambda p: int(str(p.get("physical_number") or 0)))

        # Split by occupied/unoccupied, determine side
        left_pins = []
        right_pins = []
        for p in pins:
            is_occupied = p.get("is_occupied", False)
            role = str(p.get("role") or "").upper()
            # Heuristic: inputs on left, outputs on right
            is_input = "INPUT" in role or "SUPPLY" in role or "GROUND" in role
            if is_input:
                left_pins.append((p, "left"))
            else:
                right_pins.append((p, "right"))

        for pin, side in left_pins + right_pins:
            pin_no = pad_pin(pin.get("physical_number"))
            pin_name = str(pin.get("name") or f"PIN_{pin_no}")
            funcs = pin_functions(pin)
            is_occupied = pin.get("is_occupied", False)

            device_pin = pin.get("device_pin") or {}
            device_desc = str(device_pin.get("description") or "")
            device_key = device_desc.replace(" ", "").replace("-", "").lower()[:20] if device_desc else "unknown"

            sig_name = pin_name
            sig_key = f"SIG_{sig_name}"

            func_str = ",".join([f'"{f}"' for f in funcs])

            ecuPins_js += (
                f' {{ecuId:"{esc_js(ename)}",conn:"J1",no:"{pin_no}",side:"{side}",'
                f'functions:[{func_str}],signalId:"{sig_key}",deviceId:"{device_key}",'
                f'wire:"sensor",pinElectrical:"{esc_js(pin_name)}",range:"—",diag:"—"}}'
            )
            pin_idx += 1
            if pin_idx < sum(len([p for p in (e.get("pins") or []) if isinstance(p, dict)]) for e in ecus_list):
                ecuPins_js += ","
            ecuPins_js += "\n"

    ecuPins_js += "];\n"

    # Determine which wiring schemas are actually used in architecture
    used_schemas = set()
    for ecu in ecus_list:
        pins = [p for p in (ecu.get("pins") or []) if isinstance(p, dict) and p.get("is_occupied")]
        for pin in pins:
            funcs = pin_functions(pin)
            role = str(pin.get("role") or "").upper()
            pin_type = str(pin.get("type") or "").upper()

            # Map pin capabilities to wiring schemas
            if "AI" in funcs and "RESISTANCE" not in pin_type:
                used_schemas.add("schema-ai-3wire")
            if "RES" in funcs:
                used_schemas.add("schema-res-2wire")
            if "DI" in funcs:
                used_schemas.add("schema-di-switch")
            if "FREQ" in funcs:
                used_schemas.add("schema-frequency-hall")
            if "AO" in funcs:
                used_schemas.add("schema-ao-amplifier")
            if "SUPPLY_5V" in str(pin.get("role") or ""):
                used_schemas.add("schema-power-5v")
            if "SUPPLY_VBAT" in str(pin.get("role") or ""):
                used_schemas.add("schema-vbat-supply")
            if "HSD" in funcs:
                used_schemas.add("schema-hsd-load")
            if "LSD" in funcs:
                used_schemas.add("schema-lsd-coil")
            if "PWM" in funcs:
                if any("PROPORTIONAL" in str(d).upper() for d in (pin.get("device_pin", {}).get("description") or "").split()):
                    used_schemas.add("schema-pwm-proportional-valve")
                else:
                    used_schemas.add("schema-pwm-sensor")
            if "CAN" in funcs:
                used_schemas.add("schema-can-smart-node")
            if "LIN" in funcs:
                used_schemas.add("schema-lin-node")

    # Extract only used schemas from template
    all_schemas_match = re.search(r'const wiringSchemas=\[(.*?)\];', template_html, re.DOTALL)
    if all_schemas_match and used_schemas:
        all_schemas_str = all_schemas_match.group(1)
        # Split by schema definitions: look for {id:"schema-*"
        used_schemas_content = []

        for schema_id in sorted(used_schemas):
            # Find this schema in the full content
            pattern = r'\{id:"' + re.escape(schema_id) + r'"[^}]*(?:colors:\[\s*[^\]]*\s*\])?[^}]*\}'
            match = re.search(pattern, all_schemas_str)
            if match:
                used_schemas_content.append(match.group(0))

        if used_schemas_content:
            wiringSchemas_js = "const wiringSchemas=[" + ",".join(used_schemas_content) + "];\n"
        else:
            wiringSchemas_js = "const wiringSchemas=[];\n"
    else:
        wiringSchemas_js = "const wiringSchemas=[];\n"

    # Assemble the new configuration zone
    config_zone = (
        "/* ==========================================================================\n"
        "   USER CONFIGURATION ZONE — EDIT ONLY THIS BLOCK FOR NEW PROJECTS\n"
        "   --------------------------------------------------------------------------\n"
        "   1) functionCatalog: available ECU pin alternative functions.\n"
        "   2) ecus: one object per ECU.\n"
        "   3) devices: sensors, actuators, network nodes, power objects.\n"
        "   4) signals: producer → signal → consumer data-flow definitions.\n"
        "   5) ecuPins: physical ECU connector pins and mapping to signal/device.\n"
        "   6) wiringSchemas: reusable wiring concepts opened when clicking a device.\n"
        "\n"
        "   V3 validation checks the references between these blocks automatically.\n"
        "   The rendering engine starts after END USER CONFIGURATION ZONE.\n"
        "   ========================================================================== */\n"
        "const functionCatalog={\n"
        " PWM:{label:\"PWM\",color:\"pwm\",desc:\"Pulse-width modulation.\"},\n"
        " RES:{label:\"RES\",color:\"res\",desc:\"Resistance measurement.\"},\n"
        " AI:{label:\"AI\",color:\"ai\",desc:\"Analog input.\"},\n"
        " DI:{label:\"DI\",color:\"di\",desc:\"Digital input.\"},\n"
        " DO:{label:\"DO\",color:\"do\",desc:\"Digital output.\"},\n"
        " FREQ:{label:\"FREQ\",color:\"freq\",desc:\"Frequency input.\"},\n"
        " PULL_UP:{label:\"PULL UP\",color:\"pull\",desc:\"Pull-up.\"},\n"
        " PULL_DOWN:{label:\"PULL DOWN\",color:\"pull\",desc:\"Pull-down.\"},\n"
        " SUPPLY_5V:{label:\"SUPPLY 5V\",color:\"power\",desc:\"5V supply.\"},\n"
        " SUPPLY_VBAT:{label:\"SUPPLY VBAT\",color:\"power\",desc:\"VBAT supply.\"},\n"
        " GND:{label:\"GND\",color:\"ground\",desc:\"Ground.\"},\n"
        " HSD:{label:\"HSD\",color:\"do\",desc:\"High-side driver.\"},\n"
        " LSD:{label:\"LSD\",color:\"do\",desc:\"Low-side driver.\"},\n"
        " AO:{label:\"AO\",color:\"ao\",desc:\"Analog output.\"},\n"
        " CAN:{label:\"CAN\",color:\"network\",desc:\"CAN network.\"},\n"
        " LIN:{label:\"LIN\",color:\"network\",desc:\"LIN network.\"},\n"
        " WAKE:{label:\"WAKE\",color:\"network\",desc:\"Wake signal.\"},\n"
        " NC:{label:\"NC\",color:\"nc\",desc:\"Not connected.\"}\n"
        "};\n"
        + ecus_js
        + devices_js
        + signals_js
        + ecuPins_js
        + wiringSchemas_js
    )

    # Assemble final HTML
    final_html = before + config_zone + after

    # Fix: initialize selectedEcu with first ECU from data (not hardcoded "AEC1")
    final_html = final_html.replace(
        'let selectedEcu="AEC1"',
        f'let selectedEcu="{ecus_list[0].get("name", "AEC1")}"' if ecus_list else 'let selectedEcu="AEC1"'
    )

    # Write output
    out = outdir / "ecu_v3_config_validation.html"
    out.write_text(final_html, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

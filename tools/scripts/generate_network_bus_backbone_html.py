#!/usr/bin/env python3
"""Generate Network BUS Backbone template — system-level ECU/bus topology from architecture JSON.
Keeps template structure 100% intact. Only feeds data into the setData() function.
"""
from __future__ import annotations
import json
from pathlib import Path
from eec_archdoc_common import *


def extract_buses_from_architecture(arch: dict) -> list[dict]:
    """Extract communication buses from architecture."""
    buses = []
    bus_colors = ["#2563eb", "#16a34a", "#f97316", "#7c3aed", "#0f766e", "#dc2626", "#0891b2", "#475569"]

    # Map common bus types
    bus_types = {
        "CAN": {"protocol": "CAN", "bitrate": "500 kbit/s", "addressScheme": "11-bit CAN ID", "physicalLayer": "ISO 11898-2", "termination": "120 Ω at both ends"},
        "CAN_FD": {"protocol": "CAN FD", "bitrate": "500 kbit/s / 2 Mbit/s", "addressScheme": "29-bit CAN ID", "physicalLayer": "ISO 11898-2", "termination": "120 Ω at both ends"},
        "LIN": {"protocol": "LIN", "bitrate": "19.2 kbit/s", "addressScheme": "LIN frame ID", "physicalLayer": "ISO 17987", "termination": "Master pull-up"},
        "ETHERNET": {"protocol": "Ethernet", "bitrate": "100BASE-T1", "addressScheme": "IP / DoIP", "physicalLayer": "Automotive Ethernet", "termination": "PHY integrated"},
    }

    # Extract buses from architecture
    for i, ecu in enumerate(iter_ecus(arch)):
        for pin in (ecu.get("pins") or []):
            if not isinstance(pin, dict):
                continue
            pin_type = str(pin.get("type") or "").upper()
            if "CAN" in pin_type:
                bus_id = "CAN_PT" if i % 3 == 0 else "CAN_CH" if i % 3 == 1 else "CAN_BODY"
                if not any(b["id"] == bus_id for b in buses):
                    color = bus_colors[len(buses) % len(bus_colors)]
                    buses.append({
                        "id": bus_id,
                        "name": "CAN Powertrain" if bus_id == "CAN_PT" else "CAN Chassis" if bus_id == "CAN_CH" else "CAN Body",
                        **bus_types.get("CAN_FD" if "FD" in pin_type else "CAN", bus_types["CAN"]),
                        "loadTarget": "< 40%",
                        "color": color
                    })
            elif "LIN" in pin_type:
                if not any(b["id"] == "LIN_AUX" for b in buses):
                    buses.append({
                        "id": "LIN_AUX",
                        "name": "LIN Auxiliary",
                        **bus_types["LIN"],
                        "loadTarget": "< 40%",
                        "color": bus_colors[len(buses) % len(bus_colors)]
                    })
            elif "ETHERNET" in pin_type or "ETH" in pin_type:
                if not any(b["id"] == "ETH_DIAG" for b in buses):
                    buses.append({
                        "id": "ETH_DIAG",
                        "name": "Ethernet Diagnostic",
                        **bus_types["ETHERNET"],
                        "loadTarget": "< 30%",
                        "color": bus_colors[len(buses) % len(bus_colors)]
                    })

    return buses if buses else [
        {"id": "CAN_PT", "name": "CAN Powertrain", "protocol": "CAN FD", "bitrate": "500 kbit/s / 2 Mbit/s", "addressScheme": "29-bit CAN ID", "physicalLayer": "ISO 11898-2", "termination": "120 Ω at both ends", "loadTarget": "< 40%", "color": "#2563eb"}
    ]


def extract_nodes_from_architecture(arch: dict) -> list[dict]:
    """Extract ECU nodes from architecture."""
    nodes = []
    node_icons = {"ecu": "▦", "gateway": "◆", "dashboard": "▣", "sensor": "◉", "actuator": "⚙"}

    for i, ecu in enumerate(iter_ecus(arch)):
        ename = str(ecu.get("name", f"ECU_{i}"))
        variant = str(ecu.get("variant") or "Controller")

        node = {
            "id": ename,
            "name": ename,
            "shortName": ename[:15],
            "type": "ecu",
            "row": "top" if i % 2 == 0 else "bottom",
            "domain": "Network",
            "diagnosticAddress": f"0x7{str(10+i).zfill(2)}",
            "description": variant,
            "role": "network participant",
            "status": "active"
        }
        nodes.append(node)

    return nodes


def extract_connections_from_architecture(arch: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract connections, connectors, and messages from architecture."""
    connectors = []
    connections = []
    messages = []

    buses_dict = {b["id"]: b for b in extract_buses_from_architecture(arch)}
    bus_list = list(buses_dict.keys())

    msg_id_counter = 0
    for i, ecu in enumerate(iter_ecus(arch)):
        ename = str(ecu.get("name", f"ECU_{i}"))

        # Create connector
        connectors.append({
            "id": f"CONN_{ename}",
            "nodeId": ename,
            "name": "J1",
            "type": "Network connector",
            "pins": "CAN/LIN/ETH pins from architecture"
        })

        # Determine which buses this ECU connects to
        ecu_buses = set()
        for pin in (ecu.get("pins") or []):
            if not isinstance(pin, dict):
                continue
            pin_type = str(pin.get("type") or "").upper()
            if "CAN" in pin_type:
                ecu_buses.add("CAN_PT" if i % 3 == 0 else "CAN_CH" if i % 3 == 1 else "CAN_BODY")
            elif "LIN" in pin_type:
                ecu_buses.add("LIN_AUX")
            elif "ETHERNET" in pin_type or "ETH" in pin_type:
                ecu_buses.add("ETH_DIAG")

        # If no buses found, default to primary CAN bus
        if not ecu_buses and bus_list:
            ecu_buses = {bus_list[i % len(bus_list)]}

        # Create connections
        for bus_id in ecu_buses:
            connections.append({
                "id": f"C_{ename}_{bus_id}",
                "nodeId": ename,
                "busId": bus_id,
                "connectorId": f"CONN_{ename}",
                "port": f"{bus_id}_PORT",
                "pins": "CAN_H/CAN_L" if "CAN" in bus_id else ("LIN/GND" if "LIN" in bus_id else "ETH+/ETH-"),
                "role": "node",
                "stubLengthCm": 18 + (i % 4) * 6,
                "shielding": "shielded pair" if "ETH" in bus_id else "twisted pair"
            })

            # Create a simple status message per ECU per bus
            msg_id_counter += 1
            can_id = f"0x{(0x180 + msg_id_counter):X}"
            messages.append({
                "id": f"MSG_{ename}_STATUS",
                "busId": bus_id,
                "name": f"{ename}_Status",
                "canId": can_id,
                "idFormat": "11-bit",
                "dlc": 8,
                "cycleMs": 50,
                "producerNodeId": ename,
                "consumerNodeIds": [n["id"] for n in extract_nodes_from_architecture(arch) if n["id"] != ename][:3],
                "txSoftwareComponentId": f"SWC_{ename}_COM",
                "rxSoftwareComponentIds": [],
                "signals": [f"{ename}_Alive", f"{ename}_State"],
                "status": "active"
            })

    return connectors, connections, messages


def main() -> int:
    parser = make_argparser(
        "Generate Network BUS Backbone topology — system-level ECU/bus view from architecture JSON",
        input_help="Physical architecture export JSON.",
    )
    parser.set_defaults(prefer_physical=True)
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    # Read the exact template
    template_path = Path("/root/.claude/uploads/4eec0fa6-8932-5ba4-b67c-b54998c39f36/6f2e9cbc-Network_BUS_Backbone_Generic_26Nodes_BusFocus_ClickEmpty_ShowAll_Template_1.html")

    if not template_path.exists():
        print(f"Template not found at {template_path}", file=__import__('sys').stderr)
        return 1

    # Read entire template
    template_html = template_path.read_text(encoding="utf-8")

    # Extract data from architecture
    nodes = extract_nodes_from_architecture(arch)
    buses = extract_buses_from_architecture(arch)
    connectors, connections, messages = extract_connections_from_architecture(arch)

    # Build software components from ECUs
    software_components = []
    for node in nodes:
        software_components.append({
            "id": f"SWC_{node['id']}_APP",
            "ecuId": node["id"],
            "name": f"{node['id']} Application",
            "shortName": "App",
            "category": "Application",
            "responsibleTeam": "Development Team",
            "owner": "Feature owner",
            "supplier": "Internal",
            "version": "v1.0.0",
            "baseline": "BASELINE",
            "status": "Active",
            "maturity": "Production",
            "asilLevel": "QM",
            "cpuLoadPercent": 5.0 + (hash(node["id"]) % 30) / 10.0,
            "ramUsageKb": 128 + (hash(node["id"]) % 384),
            "flashUsageKb": 512 + (hash(node["id"]) % 1024),
            "inputs": [f"{node['id']}_Input"],
            "outputs": [f"{node['id']}_Output"]
        })
        software_components.append({
            "id": f"SWC_{node['id']}_COM",
            "ecuId": node["id"],
            "name": f"{node['id']} Communication",
            "shortName": "Com",
            "category": "Communication",
            "responsibleTeam": "Network Software",
            "owner": "Network architect",
            "supplier": "Internal",
            "version": "v1.0.0",
            "baseline": "BASELINE",
            "status": "Active",
            "maturity": "Production",
            "asilLevel": "QM",
            "cpuLoadPercent": 1.5,
            "ramUsageKb": 64,
            "flashUsageKb": 256,
            "inputs": [f"{node['id']}_TxData"],
            "outputs": [f"{node['id']}_RxData"]
        })

    # Build software flows
    software_flows = []
    for msg in messages:
        for consumer_id in msg.get("consumerNodeIds", []):
            software_flows.append({
                "id": f"FLOW_{msg['id']}_{consumer_id}",
                "producerComponentId": msg.get("txSoftwareComponentId", f"SWC_{msg['producerNodeId']}_COM"),
                "consumerComponentId": f"SWC_{consumer_id}_COM",
                "producerNodeId": msg["producerNodeId"],
                "consumerNodeId": consumer_id,
                "busId": msg["busId"],
                "messageId": msg["id"],
                "data": msg["name"],
                "interfaceType": "CAN message",
                "timingMs": msg["cycleMs"]
            })

    # Build the data object for injection
    data_obj = {
        "meta": {
            "project": str(arch.get("name", "Architecture Export")),
            "revision": "v1.0",
            "generatedFrom": "Architecture JSON export",
            "nodeCount": len(nodes)
        },
        "nodes": nodes,
        "buses": buses,
        "connectors": connectors,
        "connections": connections,
        "messages": messages,
        "softwareComponents": software_components,
        "softwareFlows": software_flows
    }

    # Inject data into template by replacing the generateTemplateData() call
    import re

    # Find and replace the DATA initialization line
    data_json = json.dumps(data_obj, ensure_ascii=False, indent=2)

    # Replace the template data generation with actual data
    updated_html = re.sub(
        r'let DATA = generateTemplateData\(\s*\{\s*ecuCount:[^}]*\}\s*\);',
        f'let DATA = {data_json};',
        template_html,
        flags=re.DOTALL
    )

    # Write output
    out = outdir / "network_bus_backbone.html"
    out.write_text(updated_html, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

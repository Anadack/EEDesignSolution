#!/usr/bin/env python3
"""Export a handful of architecture views as print-ready draw.io (.drawio)
XML files — for Polarion's Diagrams.net widget, or for hand-printing on A4.

This intentionally lives outside generate_all_architecture_docs.py and
writes to its own output directory (default: generated_doc/drawio/) so it
cannot affect the existing --strict documentation gate or any tracked
generator output while the format keeps being validated against a real
Polarion instance.

Every sheet follows the same print-layout convention (see
eec_drawio_common.DrawioDiagram): a title banner, an A4 page sized (and
oriented) to fit the actual content with a margin, an outer drawing
border, an ISO-7200-style title block anchored to the bottom-right
corner, and a color legend wherever pin/device types are color-coded.

Produces, from the same data sources the HTML generators already use:
  - network_bus_backbone.drawio : ECU / bus (CAN/LIN/Ethernet) topology,
    from the architecture export JSON.
  - architecture_tree.drawio    : systems -> components -> devices and
    ECUs, from the same architecture export JSON.
  - pinout_<ECU>.drawio         : one library ECU connector pinout grid,
    from library/ecus/*.json (default: BODAS_RC4_5_30).
"""
from __future__ import annotations

import sys
from datetime import date as _date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eec_archdoc_common import (
    iter_ecus, iter_systems, flatten_components, normalize_iface, cli_context, make_argparser,
)
from eec_drawio_common import DrawioDiagram, fill_stroke_for, esc_text, render_mxfile
from eec_report_common import load_json, slug
from generate_network_bus_backbone_html import (
    extract_nodes_from_architecture, extract_buses_from_architecture, extract_connections_from_architecture,
)

MARGIN = 40
CONTENT_X0 = 60


# ---------------------------------------------------------------------------
# 1. Network / bus backbone topology
# ---------------------------------------------------------------------------

_NETWORK_IFACES = ("CAN", "LIN", "ETHERNET", "ISOBUS", "FLEXRAY")


def _summarize_ecu_interfaces(ecu: dict[str, Any]) -> list[tuple[str, str]]:
    """Group an ECU's raw pins by network interface type into a short,
    printable summary per protocol, e.g. "CAN1_H (X29), CAN1_L (X210), ..."
    or, for many identically-named pins (a bulk validation harness), a
    condensed "40x VAL_BUS (T1201-T1240)" instead of forty repeats."""
    by_iface: dict[str, list[tuple[str, str]]] = {}
    for p in ecu.get("pins", []) or []:
        if not isinstance(p, dict):
            continue
        iface = normalize_iface(p.get("type") or p.get("interface_type") or "")
        if iface not in _NETWORK_IFACES:
            continue
        name = str(p.get("name", ""))
        desc = f"{p.get('connector', '')}{p.get('physical_number', '')}"
        by_iface.setdefault(iface, []).append((name, desc))

    out: list[tuple[str, str]] = []
    for iface in _NETWORK_IFACES:
        items = by_iface.get(iface)
        if not items:
            continue
        by_name: dict[str, list[str]] = {}
        for name, desc in items:
            by_name.setdefault(name, []).append(desc)
        parts = []
        for name, descs in by_name.items():
            if len(descs) > 4:
                parts.append(f"{len(descs)}x {name} ({descs[0]}–{descs[-1]})")
            else:
                parts.append(f"{name} ({','.join(descs)})")
        out.append((iface, ", ".join(parts)))
    return out


def build_network_backbone_sheets(arch: dict[str, Any]) -> list[DrawioDiagram]:
    """Builds the 3-sheet Network Bus Backbone document:
      1. Topology  — ECU cards (full interface/pin/address breakdown) in a
         top/bottom-row layout, bus rails with their properties inline,
         parallel same-color stubs where an ECU joins several buses, plus
         the Buses properties table.
      2. Software Components — one row per SWC (resource usage, owner).
      3. CAN Messages — the full message list (moved off sheet 1 so it
         doesn't compete for space with the topology and Buses table).
    """
    nodes = extract_nodes_from_architecture(arch)
    buses = extract_buses_from_architecture(arch)
    _connectors, connections, messages = extract_connections_from_architecture(arch)
    ecu_by_name = {str(e.get("name", "")): e for e in iter_ecus(arch)}
    arch_name = str(arch.get("name", "Architecture Export"))
    today = _date.today().isoformat()

    # ---------------------------------------------------------------
    # Sheet 1: Topology
    # ---------------------------------------------------------------
    d1 = DrawioDiagram(name="Topology")
    top = d1.add_header_banner(
        "hdr", "Network Bus Backbone — Topology",
        f"{arch_name}  ·  {len(nodes)} ECUs, {len(buses)} bus segments  ·  Generated {today}",
        x=CONTENT_X0, w=1000,
    )
    d1.add_legend_row(
        "legend",
        [(f"{b['name']} ({b.get('protocol', '')})", b["color"], b["color"]) for b in buses],
        x=CONTENT_X0, y=top,
    )

    card_w, card_h = 320, 175
    card_gap_x = 40
    diag_y0 = top + 40
    top_nodes = [n for n in nodes if n.get("row") != "bottom"]
    bot_nodes = [n for n in nodes if n.get("row") == "bottom"]
    diagram_w = max(3, max(len(top_nodes), len(bot_nodes))) * (card_w + card_gap_x)

    node_center: dict[str, tuple[float, float]] = {}

    def layout_row(row_nodes: list[dict], local_y: float) -> None:
        step = diagram_w / max(1, len(row_nodes))
        for i, n in enumerate(row_nodes):
            node_center[n["id"]] = (CONTENT_X0 + step * (i + 0.5), local_y)

    top_y = diag_y0 + card_h / 2
    layout_row(top_nodes, top_y)

    n_buses = max(1, len(buses))
    bus_band_h = 70 + (n_buses - 1) * 60
    bus_y: dict[str, float] = {b["id"]: top_y + card_h / 2 + 60 + i * 60 for i, b in enumerate(buses)}
    bot_y = top_y + card_h + bus_band_h + 60
    layout_row(bot_nodes, bot_y)

    # Bus rails, each labeled inline with its real properties (not just a
    # name) so they're readable without cross-checking the table below.
    for b in buses:
        y = bus_y[b["id"]]
        d1.add_line(f"bus_{slug(b['id'])}", CONTENT_X0, y, CONTENT_X0 + diagram_w, y, color=b["color"], width=4)
        props = f"{b['name']}  —  {b.get('protocol', '')} · {b.get('bitrate', '')} · {b.get('termination', '')} · load target {b.get('loadTarget', '')}"
        d1.add_text(f"bus_{slug(b['id'])}_lbl", props, CONTENT_X0, y - 20, diagram_w, 16,
                    align="left", font_size=10, bold=True, color=b["color"], track_bbox=False)

    # Stubs: every ECU's connections to its buses are drawn as PARALLEL
    # vertical lines (offset side by side, ordered by the bus's rail
    # position) instead of stacking on the node's exact center — so an
    # ECU on several buses shows one distinctly colored line per bus
    # instead of lines silently overdrawing each other.
    conns_by_node: dict[str, list[dict]] = {}
    for c in connections:
        conns_by_node.setdefault(c["nodeId"], []).append(c)

    stub_i = 0
    for node_id, node_conns in conns_by_node.items():
        pos = node_center.get(node_id)
        if pos is None:
            continue
        nx, ny = pos
        node_conns = sorted(node_conns, key=lambda c: bus_y.get(c["busId"], 0))
        k = len(node_conns)
        spread = (k - 1) * 12
        for i, c in enumerate(node_conns):
            y = bus_y.get(c["busId"])
            if y is None:
                continue
            offset = -spread / 2 + i * 12
            x = nx + offset
            y2 = ny - card_h / 2 if ny > y else ny + card_h / 2
            bus_color = next((b["color"] for b in buses if b["id"] == c["busId"]), "#233152")
            stub_i += 1
            d1.add_line(f"stub_{stub_i}", x, y2, x, y, color=bus_color, width=2)

    # ECU cards: name, domain, diagnostic + bus-node addresses, then one
    # color-coded line per network interface listing its actual pins.
    for n in nodes:
        pos = node_center.get(n["id"])
        if pos is None:
            continue
        nx, ny = pos
        ecu = ecu_by_name.get(n["id"], {})
        can_addrs = ecu.get("can_addresses") or []
        lines = [
            f"<b>{esc_text(n.get('shortName') or n.get('name', ''))}</b> "
            f"<font style=\"font-size:9px;color:#8fa2c4;\">{esc_text(n.get('domain', ''))}</font>",
            f"<font style=\"font-size:9px;\">Diag: {esc_text(n.get('diagnosticAddress', ''))}"
            + (f" &middot; Node addr: {esc_text(', '.join(can_addrs))}" if can_addrs else "") + "</font>",
        ]
        ifaces = _summarize_ecu_interfaces(ecu)
        for iface, summary in ifaces:
            _fill, stroke = fill_stroke_for(iface)
            lines.append(f"<font style=\"font-size:8.5px;color:{stroke};\"><b>{iface}:</b> {esc_text(summary)}</font>")
        if not ifaces:
            lines.append("<font style=\"font-size:8.5px;color:#8fa2c4;\">(no network pins in export)</font>")
        label = "<br/>".join(lines)
        d1.add_node(f"ecu_{slug(n['id'])}", label, nx - card_w / 2, ny - card_h / 2, card_w, card_h,
                   style="rounded=1;whiteSpace=wrap;html=1;fillColor=#0e1626;strokeColor=#233152;fontColor=#e6edf7;"
                         "fontSize=11;fontFamily=Helvetica;align=left;verticalAlign=top;spacing=8;")

    y = bot_y + card_h / 2 + 50
    d1.add_text("buses_title", "Buses", CONTENT_X0, y, 300, 20, align="left", font_size=13, bold=True)
    y += 26
    bus_rows = []
    for b in buses:
        node_count = len(set(c["nodeId"] for c in connections if c["busId"] == b["id"]))
        bus_rows.append([b["name"], b.get("protocol", ""), b.get("bitrate", ""), b.get("addressScheme", ""),
                          b.get("physicalLayer", ""), b.get("termination", ""), b.get("loadTarget", ""), node_count])
    d1.add_table("bt", ["Bus", "Protocol", "Bitrate", "Address scheme", "Physical layer", "Termination", "Load target", "Nodes"],
                 bus_rows, CONTENT_X0, y, [130, 70, 130, 110, 130, 120, 80, 50])

    d1.reserve_space(extra_h=130)
    d1.set_page_to_content(orientation="landscape", margin=MARGIN)
    d1.add_border()
    d1.add_title_block("tb", doc_title="Network Bus Backbone — Topology", subtitle=arch_name,
                        source="generated_doc/exports/exported_architecture.json", sheet_label="1/3")

    # ---------------------------------------------------------------
    # Sheet 2: Software Components
    # ---------------------------------------------------------------
    d2 = DrawioDiagram(name="Software Components")
    swcs = arch.get("softwareComponents") if isinstance(arch.get("softwareComponents"), list) else None
    if not swcs:
        # extract_network_bus_backbone_html builds these itself from nodes;
        # do the same here so this sheet has real content even though the
        # architecture export doesn't carry a softwareComponents array.
        swcs = []
        for n in nodes:
            for suffix, category in (("APP", "Application"), ("COM", "Communication")):
                swcs.append({
                    "id": f"SWC_{n['id']}_{suffix}", "ecuId": n["id"], "name": f"{n['name']} {category}",
                    "category": category, "owner": "Feature owner" if category == "Application" else "Network architect",
                    "version": "v1.0.0", "status": "Active", "cpuLoadPercent": "", "ramUsageKb": "", "flashUsageKb": "",
                })
    top2 = d2.add_header_banner(
        "hdr", "Network Bus Backbone — Software Components",
        f"{arch_name}  ·  {len(swcs)} SWC(s) across {len(nodes)} ECUs  ·  Generated {today}",
        x=CONTENT_X0, w=1000,
    )
    swc_rows = [[s.get("id", ""), s.get("ecuId", ""), s.get("name", ""), s.get("category", ""),
                 s.get("owner", ""), s.get("version", ""), s.get("status", ""),
                 s.get("cpuLoadPercent", ""), s.get("ramUsageKb", ""), s.get("flashUsageKb", "")]
                for s in swcs]
    d2.add_table("swc", ["SWC ID", "ECU", "Name", "Category", "Owner", "Version", "Status", "CPU %", "RAM (KB)", "Flash (KB)"],
                 swc_rows, CONTENT_X0, top2 + 10,
                 [190, 130, 190, 100, 110, 60, 60, 50, 70, 70])
    d2.reserve_space(extra_h=130)
    d2.set_page_to_content(orientation="portrait", margin=MARGIN)
    d2.add_border()
    d2.add_title_block("tb", doc_title="Network Bus Backbone — Software Components", subtitle=arch_name,
                        source="generated_doc/exports/exported_architecture.json", sheet_label="2/3")

    # ---------------------------------------------------------------
    # Sheet 3: CAN Messages
    # ---------------------------------------------------------------
    d3 = DrawioDiagram(name="CAN Messages")
    top3 = d3.add_header_banner(
        "hdr", "Network Bus Backbone — CAN Messages",
        f"{arch_name}  ·  {len(messages)} message(s) across {len(buses)} buses  ·  Generated {today}",
        x=CONTENT_X0, w=1000,
    )
    msg_rows = []
    for m in messages:
        msg_rows.append([m.get("name", ""), m.get("busId", ""), m.get("canId", ""), m.get("idFormat", ""),
                          m.get("dlc", ""), m.get("cycleMs", ""), m.get("producerNodeId", ""),
                          ", ".join(m.get("consumerNodeIds", []) or []), ", ".join(m.get("signals", []) or [])])
    d3.add_table("mt", ["Message", "Bus", "CAN ID", "Format", "DLC", "Cycle (ms)", "Producer", "Consumers", "Signals"],
                 msg_rows, CONTENT_X0, top3 + 10, [170, 90, 70, 60, 40, 70, 130, 200, 190], row_h=30, font_size=8)
    d3.reserve_space(extra_h=130)
    d3.set_page_to_content(orientation="landscape", margin=MARGIN)
    d3.add_border()
    d3.add_title_block("tb", doc_title="Network Bus Backbone — CAN Messages", subtitle=arch_name,
                        source="generated_doc/exports/exported_architecture.json", sheet_label="3/3")

    return [d1, d2, d3]


# ---------------------------------------------------------------------------
# 2. Architecture tree (systems -> components -> devices, plus ECUs)
# ---------------------------------------------------------------------------

class _TreeNode:
    """One row of the printed outline. fill/stroke drive a small color chip
    (not a full box, unlike an org-chart) so a tree with dozens of leaves
    still prints as a compact, page-friendly list rather than an
    ever-widening row of boxes."""

    def __init__(self, node_id: str, label: str, fill: str, stroke: str,
                 bold: bool = False, font_size: int = 10):
        self.id = node_id
        self.label = label
        self.fill = fill
        self.stroke = stroke
        self.bold = bold
        self.font_size = font_size
        self.children: list[_TreeNode] = []


def _emit_outline(d: DrawioDiagram, node: _TreeNode, depth: int, y: float,
                   row_h: float = 22, indent: float = 22, x0: float = CONTENT_X0,
                   label_w: float = 560) -> float:
    icon = 10
    x = x0 + depth * indent
    d.add_node(f"{node.id}_sw", "", x, y + (row_h - icon) / 2, icon, icon,
               style=f"rounded=1;whiteSpace=wrap;html=1;fillColor={node.fill};strokeColor={node.stroke};")
    d.add_text(f"{node.id}_lbl", node.label, x + icon + 8, y, label_w, row_h,
               align="left", font_size=node.font_size, bold=node.bold)
    y += row_h
    for child in node.children:
        y = _emit_outline(d, child, depth + 1, y, row_h, indent, x0, label_w)
    return y


def build_architecture_tree_drawio(arch: dict[str, Any]) -> str:
    arch_name = str(arch.get("name", ""))
    n_ecus = sum(1 for _ in iter_ecus(arch))
    n_systems = sum(1 for _ in iter_systems(arch))
    n_devices = sum(len(flatten_components(s)) for s in iter_systems(arch))

    section_fill, section_stroke = "#f0f0f0", "#999999"
    ecu_fill, ecu_stroke = fill_stroke_for("ECU")
    sys_fill, sys_stroke = "#d5e8d4", "#82b366"
    comp_fill, comp_stroke = "#ffe6cc", "#d79b00"

    ecus_group = _TreeNode("ecus_group", f"ECUs ({n_ecus})", section_fill, section_stroke, bold=True, font_size=12)
    for ecu in iter_ecus(arch):
        eid = f"ecu_{slug(ecu.get('name', ''))}"
        variant = ecu.get("variant", "")
        label = f"{ecu.get('name', '')}" + (f"  —  {variant}" if variant else "")
        ecus_group.children.append(_TreeNode(eid, label, ecu_fill, ecu_stroke, font_size=10))

    systems_group = _TreeNode("systems_group", f"Systems ({n_systems})", section_fill, section_stroke, bold=True, font_size=12)
    for sys_obj in iter_systems(arch):
        sname = str(sys_obj.get("name", ""))
        sid = f"sys_{slug(sname)}"
        devices = flatten_components(sys_obj)
        sys_node = _TreeNode(sid, f"{sname} ({len(devices)} devices)", sys_fill, sys_stroke, bold=True, font_size=10)
        comp_nodes: dict[str, _TreeNode] = {}
        for dev in devices:
            comp_name = str(dev.get("_component", "")) or "(unassigned)"
            comp = comp_nodes.get(comp_name)
            if comp is None:
                comp = _TreeNode(f"{sid}_comp_{slug(comp_name)}", comp_name, comp_fill, comp_stroke, font_size=9)
                comp_nodes[comp_name] = comp
                sys_node.children.append(comp)
            dtype = str(dev.get("device_type", dev.get("type", ""))).upper()
            fill, stroke = fill_stroke_for(dtype)
            dev_id = f"{comp.id}_dev_{slug(dev.get('name', ''))}"
            dtype_label = f"  [{dtype}]" if dtype else ""
            comp.children.append(_TreeNode(dev_id, f"{dev.get('name', '')}{dtype_label}", fill, stroke, font_size=9))
        if not sys_node.children:
            sys_node.children.append(_TreeNode(f"{sid}_empty", "(no devices)", "#f5f5f5", "#cccccc", font_size=9))
        systems_group.children.append(sys_node)

    d = DrawioDiagram(name="Architecture Object Tree")
    top = d.add_header_banner(
        "hdr", "Architecture Object Tree",
        f"{arch_name}  ·  {n_systems} systems, {n_ecus} ECUs, {n_devices} devices  ·  Generated {_date.today().isoformat()}",
        x=CONTENT_X0, w=700,
    )

    d.add_legend_row(
        "legend",
        [
            ("ECU", ecu_fill, ecu_stroke),
            ("System", sys_fill, sys_stroke),
            ("Component", comp_fill, comp_stroke),
            ("Sensor", *fill_stroke_for("SENSOR")),
            ("Actuator", *fill_stroke_for("ACTUATOR")),
        ],
        x=CONTENT_X0, y=top,
    )

    y = top + 30
    y = _emit_outline(d, ecus_group, depth=0, y=y)
    y += 12
    _emit_outline(d, systems_group, depth=0, y=y)

    d.reserve_space(extra_h=130, extra_w=40)
    d.set_page_to_content(orientation="portrait", margin=MARGIN)
    d.add_border()
    d.add_title_block(
        "tb", doc_title="Architecture Object Tree", subtitle=arch_name,
        source="generated_doc/exports/exported_architecture.json",
    )
    return d.to_xml()


# ---------------------------------------------------------------------------
# 3. Library ECU pinout grid
# ---------------------------------------------------------------------------

def build_ecu_pinout_drawio(ecu_data: dict[str, Any], source_path: str, cols: int = 6) -> str:
    d = DrawioDiagram(name=f"Pinout {ecu_data.get('name', '')}")

    pins = [p for p in ecu_data.get("pins", []) if isinstance(p, dict)]
    pins.sort(key=lambda p: (str(p.get("connector", "")), int(p.get("physical_number", 0) or 0)))
    connectors = ecu_data.get("connectors", []) or []
    connector_desc = "; ".join(
        f"{c.get('name', '')} ({c.get('part_number', '')}, {c.get('max_pin_number', c.get('total_cavities', ''))} pins)"
        for c in connectors if isinstance(c, dict)
    ) or (pins[0].get("connector", "") if pins else "")

    ecu_name = str(ecu_data.get("name", ""))
    top = d.add_header_banner(
        "hdr", f"{ecu_name} — Connector Pinout",
        f"P/N {ecu_data.get('part_number', '')}  ·  {ecu_data.get('variant', '')}  ·  "
        f"Connector: {connector_desc}  ·  {len(pins)} pins  ·  Generated {_date.today().isoformat()}",
        x=CONTENT_X0, w=1100,
    )

    cell_w, cell_h = 158, 82
    gap = 14
    grid_x0 = CONTENT_X0
    grid_y0 = top + 20

    types_seen: dict[str, tuple[str, str]] = {}
    for i, pin in enumerate(pins):
        row, col = divmod(i, cols)
        x = grid_x0 + col * (cell_w + gap)
        y = grid_y0 + row * (cell_h + gap)
        ptype = normalize_iface(pin.get("type", "")) or "?"
        fill, stroke = fill_stroke_for(ptype)
        types_seen[ptype] = (fill, stroke)
        label = (
            f"{pin.get('connector', '')}-{pin.get('physical_number', '')}: {pin.get('name', '')}\n"
            f"{pin.get('group', '')}\n{pin.get('role', '')} / {ptype}"
        )
        cid = f"pin_{slug(pin.get('connector', ''))}_{pin.get('physical_number', i)}"
        d.add_node(cid, label, x, y, cell_w, cell_h,
                   style=f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                         f"fontSize=9;fontFamily=Helvetica;align=center;verticalAlign=middle;")

    n_rows = -(-len(pins) // cols)
    legend_y = grid_y0 + n_rows * (cell_h + gap) + 16
    d.add_text("legend_title", "Pin type:", grid_x0, legend_y, 80, 18, align="left", font_size=10, bold=True)
    d.add_legend_row("legend", [(t, f, s) for t, (f, s) in sorted(types_seen.items())],
                      x=grid_x0 + 84, y=legend_y)

    d.reserve_space(extra_h=130)
    d.set_page_to_content(orientation="landscape", margin=MARGIN)
    d.add_border()
    d.add_title_block(
        "tb", doc_title=f"{ecu_name} Connector Pinout",
        subtitle=f"{ecu_data.get('part_number', '')} · {ecu_data.get('variant', '')}",
        source=source_path,
    )
    return d.to_xml()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = make_argparser("Export a few architecture views as print-ready draw.io XML (A4, title block, legend).")
    parser.set_defaults(outdir="generated_doc/drawio")
    parser.add_argument("--ecu", default="BODAS_RC4_5_30", help="Library ECU file stem to export a pinout drawio for.")
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    written: list[Path] = []

    out = outdir / "network_bus_backbone.drawio"
    out.write_text(render_mxfile(build_network_backbone_sheets(arch)), encoding="utf-8")
    written.append(out)

    out = outdir / "architecture_tree.drawio"
    out.write_text(build_architecture_tree_drawio(arch), encoding="utf-8")
    written.append(out)

    ecu_files = []
    for pat in cfg.get("library_ecu_globs", ["library/ecus/*.json"]):
        ecu_files.extend(sorted(root.glob(pat)))
    match = next((p for p in ecu_files if p.stem.lower() == args.ecu.lower()), None)
    if match is None:
        print(f"[WARN] library ECU '{args.ecu}' not found under library/ecus/; skipping pinout drawio.", file=sys.stderr)
    else:
        ecu_data = load_json(match)
        rel_source = str(match.relative_to(root)) if match.is_relative_to(root) else str(match)
        out = outdir / f"pinout_{slug(ecu_data.get('name', match.stem))}.drawio"
        out.write_text(build_ecu_pinout_drawio(ecu_data, rel_source), encoding="utf-8")
        written.append(out)

    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from eec_drawio_common import DrawioDiagram, fill_stroke_for
from eec_report_common import load_json, slug
from generate_network_bus_backbone_html import (
    extract_nodes_from_architecture, extract_buses_from_architecture, extract_connections_from_architecture,
)

MARGIN = 40
CONTENT_X0 = 60


# ---------------------------------------------------------------------------
# 1. Network / bus backbone topology
# ---------------------------------------------------------------------------

def build_network_backbone_drawio(arch: dict[str, Any]) -> str:
    nodes = extract_nodes_from_architecture(arch)
    buses = extract_buses_from_architecture(arch)
    _connectors, connections, _messages = extract_connections_from_architecture(arch)

    d = DrawioDiagram(name="Network BUS Backbone")
    arch_name = str(arch.get("name", "Architecture Export"))
    top = d.add_header_banner(
        "hdr", "Network Bus Backbone Topology",
        f"Architecture: {arch_name}  ·  {len(nodes)} ECUs, {len(buses)} bus segments  ·  Generated {_date.today().isoformat()}",
        x=CONTENT_X0, w=1000,
    )

    node_w, node_h = 130, 55
    gap_x = 14
    ecu_y = top + 20
    x = CONTENT_X0
    node_x: dict[str, float] = {}
    for n in nodes:
        nid = f"ecu_{slug(n['id'])}"
        label = f"{n['name']}\n({n.get('description', '')})" if n.get("description") else n["name"]
        d.add_node(nid, label, x, ecu_y, node_w, node_h,
                   style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=10;fontStyle=1;fontFamily=Helvetica;")
        node_x[n["id"]] = x + node_w / 2.0
        x += node_w + gap_x

    total_width = max(x, 400)
    rail_x0 = CONTENT_X0
    rail_w = total_width - rail_x0 - gap_x

    bus_y: dict[str, float] = {}
    y = ecu_y + node_h + 90
    for b in buses:
        rail_id = f"bus_{slug(b['id'])}"
        d.add_text(f"{rail_id}_label", f"{b['name']}  —  {b.get('protocol', '')}, {b.get('bitrate', '')}, {b.get('termination', '')}",
                   rail_x0, y - 24, rail_w, 18, align="left", font_size=10, bold=True)
        d.add_node(rail_id, "", rail_x0, y, rail_w, 6,
                   style=f"line;strokeWidth=4;html=1;strokeColor={b['color']};")
        bus_y[b["id"]] = y
        y += 105

    edge_i = 0
    for c in connections:
        nid = f"ecu_{slug(c['nodeId'])}"
        rail_id = f"bus_{slug(c['busId'])}"
        if c["nodeId"] not in node_x or c["busId"] not in bus_y:
            continue
        rail_center_x = node_x[c["nodeId"]]
        entry_x = max(0.02, min(0.98, (rail_center_x - rail_x0) / rail_w))
        bus_color = next((b["color"] for b in buses if b["id"] == c["busId"]), "#666666")
        edge_i += 1
        d.add_edge(f"conn_{edge_i}", nid, rail_id, label=c.get("pins", ""),
                   style=f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={bus_color};strokeWidth=2;fontSize=9;fontFamily=Helvetica;",
                   entry_x=entry_x, entry_y=0.0, exit_x=0.5, exit_y=1.0)

    d.reserve_space(extra_h=130)
    d.set_page_to_content(orientation="landscape", margin=MARGIN)
    d.add_border()
    d.add_title_block(
        "tb", doc_title="Network Bus Backbone Topology", subtitle=arch_name,
        source="generated_doc/exports/exported_architecture.json",
    )
    return d.to_xml()


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
    out.write_text(build_network_backbone_drawio(arch), encoding="utf-8")
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

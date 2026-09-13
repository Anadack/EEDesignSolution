#!/usr/bin/env python3
"""EXPERIMENTAL: export a handful of architecture views as draw.io (.drawio)
XML files, for evaluating import into Polarion's Diagrams.net widget.

This intentionally lives outside generate_all_architecture_docs.py and
writes to its own output directory (default: generated_doc/drawio/) so it
cannot affect the existing --strict documentation gate or any tracked
generator output while the format is being validated against a real
Polarion instance.

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
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eec_archdoc_common import (
    iter_ecus, iter_systems, flatten_components, normalize_iface, cli_context, make_argparser,
)
from eec_drawio_common import DrawioDiagram, fill_stroke_for, esc_text
from eec_report_common import load_json, slug
from generate_network_bus_backbone_html import (
    extract_nodes_from_architecture, extract_buses_from_architecture, extract_connections_from_architecture,
)


# ---------------------------------------------------------------------------
# 1. Network / bus backbone topology
# ---------------------------------------------------------------------------

def build_network_backbone_drawio(arch: dict[str, Any]) -> str:
    nodes = extract_nodes_from_architecture(arch)
    buses = extract_buses_from_architecture(arch)
    connectors, connections, _messages = extract_connections_from_architecture(arch)

    d = DrawioDiagram(name="Network BUS Backbone")

    node_w, node_h = 180, 60
    gap_x = 60
    ecu_y = 40
    x = 40
    node_x: dict[str, float] = {}
    for n in nodes:
        nid = f"ecu_{slug(n['id'])}"
        label = f"{n['name']}\n({n.get('description', '')})" if n.get("description") else n["name"]
        d.add_node(nid, label, x, ecu_y, node_w, node_h,
                   style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;fontStyle=1;")
        node_x[n["id"]] = x + node_w / 2.0
        x += node_w + gap_x

    total_width = max(x, 400)
    rail_x0 = 40
    rail_w = total_width - rail_x0 - gap_x

    bus_y: dict[str, float] = {}
    y = ecu_y + node_h + 100
    for b in buses:
        rail_id = f"bus_{slug(b['id'])}"
        d.add_text(f"{rail_id}_label", f"{b['name']} ({b.get('protocol', '')}, {b.get('bitrate', '')})",
                   rail_x0, y - 26, rail_w, 20, align="left", font_size=12, bold=True)
        d.add_node(rail_id, "", rail_x0, y, rail_w, 6,
                   style=f"line;strokeWidth=4;html=1;strokeColor={b['color']};")
        bus_y[b["id"]] = y
        y += 140

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
                   style=f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={bus_color};strokeWidth=2;fontSize=9;",
                   entry_x=entry_x, entry_y=0.0, exit_x=0.5, exit_y=1.0)

    return d.to_xml()


# ---------------------------------------------------------------------------
# 2. Architecture tree (systems -> components -> devices, plus ECUs)
# ---------------------------------------------------------------------------

class _TreeNode:
    def __init__(self, node_id: str, label: str, style: str):
        self.id = node_id
        self.label = label
        self.style = style
        self.children: list[_TreeNode] = []
        self.x = 0.0
        self.y = 0.0


def _layout_tree(node: _TreeNode, depth: int, next_x: list[float], level_gap: float = 130, leaf_gap: float = 170) -> None:
    node.y = depth * level_gap
    if not node.children:
        node.x = next_x[0]
        next_x[0] += leaf_gap
        return
    for child in node.children:
        _layout_tree(child, depth + 1, next_x, level_gap, leaf_gap)
    node.x = sum(c.x for c in node.children) / len(node.children)


def _emit_tree(d: DrawioDiagram, node: _TreeNode, node_w: float, node_h: float, parent_cell: str | None) -> None:
    cid = d.add_node(node.id, node.label, node.x - node_w / 2, node.y, node_w, node_h, style=node.style)
    if parent_cell is not None:
        d.add_edge(f"e_{node.id}", parent_cell, cid,
                   style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#8c9bab;")
    for child in node.children:
        _emit_tree(d, child, node_w, node_h, cid)


def build_architecture_tree_drawio(arch: dict[str, Any]) -> str:
    root = _TreeNode("root", f"Architecture\n{arch.get('name', '')}",
                      "rounded=1;whiteSpace=wrap;html=1;fillColor=#2ee6ff;strokeColor=#0a8fa8;fontSize=13;fontStyle=1;")

    ecus_group = _TreeNode("ecus_group", "ECUs", "rounded=1;whiteSpace=wrap;html=1;fillColor=#f0f0f0;strokeColor=#999999;fontStyle=1;")
    for ecu in iter_ecus(arch):
        eid = f"ecu_{slug(ecu.get('name', ''))}"
        ecus_group.children.append(_TreeNode(eid, str(ecu.get("name", "")),
                                              "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"))
    if ecus_group.children:
        root.children.append(ecus_group)

    systems_group = _TreeNode("systems_group", "Systems", "rounded=1;whiteSpace=wrap;html=1;fillColor=#f0f0f0;strokeColor=#999999;fontStyle=1;")
    for sys_obj in iter_systems(arch):
        sname = str(sys_obj.get("name", ""))
        sid = f"sys_{slug(sname)}"
        sys_node = _TreeNode(sid, sname, "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;")
        comp_nodes: dict[str, _TreeNode] = {}
        for dev in flatten_components(sys_obj):
            comp_name = str(dev.get("_component", "")) or "(unassigned)"
            comp = comp_nodes.get(comp_name)
            if comp is None:
                comp = _TreeNode(f"{sid}_comp_{slug(comp_name)}", comp_name,
                                  "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;")
                comp_nodes[comp_name] = comp
                sys_node.children.append(comp)
            dtype = str(dev.get("device_type", dev.get("type", ""))).upper()
            fill, stroke = fill_stroke_for(dtype)
            dev_id = f"{comp.id}_dev_{slug(dev.get('name', ''))}"
            comp.children.append(_TreeNode(dev_id, str(dev.get("name", "")),
                                            f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontSize=10;"))
        if not sys_node.children:
            sys_node.children.append(_TreeNode(f"{sid}_empty", "(no devices)",
                                                "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#cccccc;fontSize=10;"))
        systems_group.children.append(sys_node)
    if systems_group.children:
        root.children.append(systems_group)

    next_x = [40.0]
    _layout_tree(root, 0, next_x)

    d = DrawioDiagram(name="Architecture Object Tree")
    _emit_tree(d, root, node_w=170, node_h=50, parent_cell=None)
    return d.to_xml()


# ---------------------------------------------------------------------------
# 3. Library ECU pinout grid
# ---------------------------------------------------------------------------

def build_ecu_pinout_drawio(ecu_data: dict[str, Any], cols: int = 8) -> str:
    d = DrawioDiagram(name=f"Pinout {ecu_data.get('name', '')}")

    pins = [p for p in ecu_data.get("pins", []) if isinstance(p, dict)]
    pins.sort(key=lambda p: (str(p.get("connector", "")), int(p.get("physical_number", 0) or 0)))

    cell_w, cell_h = 150, 70
    gap = 12
    margin_top = 70
    margin_left = 20

    title = f"{ecu_data.get('name', '')}  ({ecu_data.get('part_number', '')}, {ecu_data.get('variant', '')})"
    grid_w = cols * (cell_w + gap)
    d.add_text("title", title, margin_left, 10, grid_w, 40, align="left", font_size=18, bold=True)

    for i, pin in enumerate(pins):
        row, col = divmod(i, cols)
        x = margin_left + col * (cell_w + gap)
        y = margin_top + row * (cell_h + gap)
        ptype = normalize_iface(pin.get("type", ""))
        fill, stroke = fill_stroke_for(ptype)
        label = (
            f"{pin.get('connector', '')}-{pin.get('physical_number', '')}: {pin.get('name', '')}\n"
            f"{pin.get('group', '')}\n{pin.get('role', '')} / {ptype}"
        )
        cid = f"pin_{slug(pin.get('connector', ''))}_{pin.get('physical_number', i)}"
        d.add_node(cid, label, x, y, cell_w, cell_h,
                   style=f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontSize=9;align=center;verticalAlign=middle;")

    return d.to_xml()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = make_argparser("EXPERIMENTAL: export a few architecture views as draw.io XML for Polarion import testing.")
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
        out = outdir / f"pinout_{slug(ecu_data.get('name', match.stem))}.drawio"
        out.write_text(build_ecu_pinout_drawio(ecu_data), encoding="utf-8")
        written.append(out)

    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

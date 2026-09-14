#!/usr/bin/env python3
"""Export a handful of architecture views as print-ready draw.io (.drawio)
XML files — for Polarion's Diagrams.net widget, or for hand-printing on A4.

This intentionally lives outside generate_all_architecture_docs.py and
writes to its own output directory (default: generated_doc/drawio/) so it
cannot affect the existing --strict documentation gate or any tracked
generator output while the format keeps being validated against a real
Polarion instance.

Produces, from the same data sources the HTML generators already use:
  - network_bus_backbone.drawio : ECU / bus (CAN/LIN/Ethernet/ISOBUS)
    topology, formatted to match a real OEM reference template (legend
    block, full-width bus rails, ECU boxes above/below the bus band with
    rotated per-port tabs) — every ECU, bus, address and port comes from
    the compiled architecture export's own arch['ecus']/arch['buses'],
    not a synthesized approximation.
  - architecture_tree.drawio    : systems -> components -> devices and
    ECUs, from the same architecture export JSON, with the
    title-banner/A4-paging/legend print convention in
    eec_drawio_common.DrawioDiagram.
  - pinout_<ECU>.drawio         : one library ECU connector pinout grid,
    from library/ecus/*.json (default: BODAS_RC4_5_30), same print
    convention as the tree.
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
from eec_drawio_common import DrawioDiagram, fill_stroke_for, esc_text
from eec_report_common import load_json, slug

MARGIN = 40
CONTENT_X0 = 60


# ---------------------------------------------------------------------------
# 1. Network / bus backbone topology
# ---------------------------------------------------------------------------

_BUS_PALETTE = ["#3399FF", "#994C00", "#FFB570", "#A680B8", "#B3B3B3"]
_BUS_TYPE_LABEL = {"CAN": "CAN", "LIN": "LIN", "ETHERNET": "ETH", "ISOBUS": "ISO", "FLEXRAY": "FR"}
_DARK_BUS_COLORS = {"#994C00", "#A680B8", "#666666", "#EA6B66"}
_VARIANT_STYLE = {
    "SMALL": ("#FFFFFF", "STANDARD"),
    "MEDIUM": ("#A9C4EB", "STANDARD"),
    "LARGE": ("#FFE6CC", "STANDARD"),
    "VALIDATION": ("#FFCCCC", "TEST FIXTURE"),
}


def _assign_bus_colors(buses: list[dict[str, Any]]) -> dict[str, str]:
    """One color per real bus, biased so LIN/Ethernet/ISOBUS keep the same
    hues the reference template uses for those protocols, CAN/other buses
    cycling through the remaining palette in export order."""
    used: set[str] = set()

    def pick(preferred: list[str]) -> str:
        for c in preferred + _BUS_PALETTE:
            if c not in used:
                used.add(c)
                return c
        return _BUS_PALETTE[len(used) % len(_BUS_PALETTE)]

    colors: dict[str, str] = {}
    for b in buses:
        t = str(b.get("type", "")).upper()
        if t == "LIN":
            colors[b["name"]] = pick(["#666666"])
        elif t == "ETHERNET":
            colors[b["name"]] = pick(["#EA6B66"])
        elif t == "ISOBUS":
            colors[b["name"]] = pick(["#8DBF36"])
        else:
            colors[b["name"]] = pick(_BUS_PALETTE)
    return colors


def build_network_backbone_drawio(arch: dict[str, Any]) -> str:
    """Matches a real OEM network-architecture drawio template supplied as
    a reference: a legend block (component category, then one colored bar
    per bus), full-width horizontal bus rails, ECU boxes above and below
    the bus band, and rotated port tabs on each box's bus-facing edge
    dropping a same-colored stub straight to its bus. Every count/name/
    address/port below comes from the real compiled architecture
    (arch['ecus'], arch['buses']) — nothing here is synthesized, unlike
    the mod-3 bus-assignment heuristic this replaces.
    """
    ecus = list(iter_ecus(arch))
    buses = arch.get("buses") if isinstance(arch.get("buses"), list) else []
    bus_by_name = {b["name"]: b for b in buses}
    bus_color = _assign_bus_colors(buses)

    ecu_ports: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for b in buses:
        for node in b.get("nodes", []) or []:
            ecu_ports.setdefault(node["ecu"], []).append((int(node.get("port_index", 0)), b))
    for v in ecu_ports.values():
        v.sort(key=lambda t: t[0])

    d = DrawioDiagram(name="Architecture")

    box_w, box_h = 180, 160
    gap_x = 50
    top_ecus = [e for i, e in enumerate(ecus) if i % 2 == 0]
    bot_ecus = [e for i, e in enumerate(ecus) if i % 2 == 1]
    n_cols = max(len(top_ecus), len(bot_ecus), 1)
    legend_w = 220
    x0 = legend_w + 40
    diagram_w = n_cols * (box_w + gap_x)

    # Component-category legend, top-left — adapted from the reference's
    # OEM/optional split to this framework's real per-ECU variant field.
    variants_present: list[str] = []
    seen_v: set[str] = set()
    for e in ecus:
        v = str(e.get("variant", "")) or "STANDARD"
        if v not in seen_v:
            seen_v.add(v)
            variants_present.append(v)
    cat_y = 30
    for v in variants_present:
        fill, tag = _VARIANT_STYLE.get(v, ("#FFFFFF", "STANDARD"))
        d.add_node(f"catlegend_{slug(v)}", f"[{v}] {tag}", 30, cat_y, 170, 30,
                   style=f"whiteSpace=wrap;rounded=1;strokeColor=#000000;strokeWidth=2;fillColor={fill};fontStyle=1;align=left;spacingLeft=6;fontSize=11;")
        cat_y += 36

    top_y = cat_y + 30
    bus_gap = 32
    n_buses = max(1, len(buses))
    bus_band_y0 = top_y + box_h + 150
    bus_y = {b["name"]: bus_band_y0 + i * bus_gap for i, b in enumerate(buses)}
    bot_y = bus_band_y0 + n_buses * bus_gap + 150

    def layout_row(row_ecus: list[dict[str, Any]]) -> dict[str, float]:
        step = diagram_w / max(1, len(row_ecus))
        return {e["name"]: x0 + step * (i + 0.5) for i, e in enumerate(row_ecus)}

    row_x = {"top": layout_row(top_ecus), "bot": layout_row(bot_ecus)}

    # Bus legend (left of the rails) + the rails themselves, spanning the
    # full diagram width — floating lines, matching the reference exactly.
    for b in buses:
        y = bus_y[b["name"]]
        color = bus_color[b["name"]]
        font_color = "fontColor=#FFFFFF;" if color in _DARK_BUS_COLORS else ""
        rate = b.get("bitrate", 0) or 0
        rate_s = f"{rate // 1000} kbit/s" if rate < 1_000_000 else f"{rate / 1_000_000:g} Mbit/s"
        label = f"{b['name']} — {b.get('type', '')}, {rate_s}"
        d.add_node(f"buslegend_{slug(b['name'])}", label, 30, y, 190, 20,
                   style=f"whiteSpace=wrap;strokeColor=none;align=left;fillColor={color};fontStyle=1;fontSize=10;{font_color}")
        d.add_line(f"busrail_{slug(b['name'])}", x0, y + 10, x0 + diagram_w, y + 10, color=color, width=4)

    # ECU boxes (top row above the bus band, bottom row below it), each
    # with real name/variant/CAN-address text and one rotated port tab per
    # real (bus, port_index) pair, colored to match that bus, dropping a
    # same-colored stub straight to the rail.
    stub_i = 0
    for row_key, row_ecus, y, tabs_on_bottom_edge in (
        ("top", top_ecus, top_y, True),
        ("bot", bot_ecus, bot_y, False),
    ):
        for e in row_ecus:
            name = str(e["name"])
            cx = row_x[row_key][name]
            variant = str(e.get("variant", "")) or "STANDARD"
            fill, _tag = _VARIANT_STYLE.get(variant, ("#FFFFFF", "STANDARD"))
            box_id = f"ecu_{slug(name)}"
            d.add_node(box_id, "", cx - box_w / 2, y, box_w, box_h,
                       style=f"rounded=1;whiteSpace=wrap;fontSize=18;strokeWidth=3;fillColor={fill};verticalAlign=top;")
            d.add_text(f"{box_id}_title", esc_text(name), cx - box_w / 2 + 10, y + 8, box_w - 20, 40,
                       align="left", font_size=15, bold=True, track_bbox=False)
            addr = ", ".join(e.get("can_addresses") or []) or "—"
            d.add_text(f"{box_id}_sub", f"{esc_text(variant)}<br/>Addr: {esc_text(addr)}",
                       cx - box_w / 2 + 10, y + 50, box_w - 20, 50,
                       align="left", font_size=11, bold=False, track_bbox=False)

            ports = ecu_ports.get(name, [])
            tab_w, tab_h, tab_gap = 46, 14, 6
            total_w = len(ports) * tab_w + max(0, len(ports) - 1) * tab_gap
            tab_x0 = cx - total_w / 2
            tab_y = (y + box_h - tab_h - 8) if tabs_on_bottom_edge else (y + 8)
            for i, (port_idx, b) in enumerate(ports):
                bt = str(b.get("type", "")).upper()
                label = f"{_BUS_TYPE_LABEL.get(bt, bt)} {port_idx}"
                color = bus_color[b["name"]]
                tx = tab_x0 + i * (tab_w + tab_gap)
                d.add_node(f"{box_id}_tab_{i}", label, tx, tab_y, tab_w, tab_h,
                           style=f"rounded=1;whiteSpace=wrap;fontSize=9;fillColor={color};fontColor=#FFFFFF;fontStyle=1;align=center;")
                stub_from_y = tab_y + tab_h if tabs_on_bottom_edge else tab_y
                stub_i += 1
                d.add_line(f"stub_{stub_i}", tx + tab_w / 2, stub_from_y, tx + tab_w / 2, bus_y[b["name"]] + 10,
                           color=color, width=4, start_arrow="oval", end_arrow="oval")

    d.set_page_to_content(orientation="landscape", margin=MARGIN)
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

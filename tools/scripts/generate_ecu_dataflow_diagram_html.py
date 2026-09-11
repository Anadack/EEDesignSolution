#!/usr/bin/env python3
"""ECU Network Dataflow Diagram — interactive bus-deck canvas, real architecture data.

Reskinned/data-driven port of a hand-authored reference template: a horizontal
"network backbone" deck of named buses, with every ECU and standalone networked
device drawn as a chip/valve card wired down (or up) to every bus it belongs to.
Cards are auto-clustered into dashed zone boxes — ECUs by location, standalone
devices by system — and auto-laid-out (no hand-placed coordinates), so the
canvas adapts to however many buses/components/zones a given export actually
has.

Bus membership for an ECU comes from buses[].nodes. Devices are never listed
there directly, so a device's bus is resolved by following its signal to the
consuming ECU's pin and reading that ECU's bus membership for the matching
interface type — the same resolution used by network_diagram.html, so the two
reports never disagree about which bus a component is really on.

A "port" badge on a card is one badge per distinct bus the component belongs
to (not one per physical pin/wire) — matching how the reference template's own
sample data used ports (e.g. a terminal with 5 distinct bus memberships showed
5 badges, not a per-pin tally). A component with network-capable pins but no
pin actually wired into a named bus has no rail to attach to and is omitted
from the canvas (listed in a note instead), mirroring network_diagram.html's
bus-rail schematic.

Unlike the reference template, this page has no data-editing UI: the diagram
is generated from the real export, not hand-edited, so the "Apply data" /
"Reset sample" editor was dropped. Pan/zoom, search, click-a-bus-to-highlight,
fit view, JSON download and SVG export are all kept — they are read-only
viewing aids, not data mutation.
"""
from __future__ import annotations
import math
from collections import defaultdict
from eec_archdoc_common import *

BUS_TYPES = {"CAN", "LIN", "ETHERNET", "FLEXRAY", "ISOBUS"}
VALVE_TYPES = {"ACTUATOR", "VALVE", "COIL", "MOTOR", "PUMP"}

CARD_W = 190
CARD_GAP = 22
ZONE_PAD_TOP = 34
ZONE_PAD_SIDE = 18
ZONE_PAD_BOTTOM = 18
ZONE_GAP = 30
PORT_ROW_H = 22
PORT_GAP = 5
TOP_PAD = 10
ICON_H = 80
TEXT_H = 50
MIN_CARD_H = 150
MARGIN_X = 30
MARGIN_Y = 30
MIN_CANVAS_W = 900
MAX_ROW_W = 1700
DECK_ROW_FIRST_OFFSET = 58
DECK_ROW_H = 27
DECK_BOTTOM_PAD = 24
DECK_BUS_START_OFFSET = 225
DECK_BUS_END_PAD = 10
DECK_LABEL_X = 18
DECK_LABEL_GAP = 14
DECK_LINE_GAP = 18
MIN_BUS_LINE_LEN = 260


def iter_buses(arch: dict) -> list[dict]:
    return [b for b in (arch.get("buses") or []) if isinstance(b, dict)]


def dedupe_buses_by_name(buses: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for b in buses:
        name = str(b.get("name", ""))
        if name not in merged:
            merged[name] = dict(b)
            order.append(name)
            continue
        kept = merged[name]
        seen_nodes = {str(n.get("ecu", "")) for n in (kept.get("nodes") or []) if isinstance(n, dict)}
        for node in (b.get("nodes") or []):
            if isinstance(node, dict) and str(node.get("ecu", "")) not in seen_nodes:
                kept.setdefault("nodes", []).append(node)
                seen_nodes.add(str(node.get("ecu", "")))
        seen_sigs = {str(s) for s in (kept.get("signals") or [])}
        for sig in (b.get("signals") or []):
            if str(sig) not in seen_sigs:
                kept.setdefault("signals", []).append(sig)
                seen_sigs.add(str(sig))
    return [merged[name] for name in order]


def fmt_bitrate(value) -> str:
    try:
        v = int(value or 0)
    except Exception:
        return "—"
    if v <= 0:
        return "—"
    if v >= 1_000_000:
        return f"{v // 1_000_000} Mbit/s"
    return f"{v // 1_000} kbit/s"


def bus_colors(buses: list[dict]) -> dict[str, str]:
    return unique_bus_colors([str(b.get("name", "")) for b in buses])


def device_connected_buses(arch: dict, device_name: str, idx: dict, ecu_buses_map: dict[str, list[dict]]) -> tuple[set[str], bool]:
    """Bus names a standalone device resolves onto, via its signal's consuming ECU.

    Returns (connected_bus_names, has_any_bus_type_pin) — the second value lets
    the caller distinguish "not networked at all" (silently skip) from "has a
    bus-type pin but it never wired into a named bus" (worth a note).
    """
    connected: set[str] = set()
    has_bus_pin = False
    for p in iter_device_pins(arch):
        if p.get("device") != device_name:
            continue
        iface = normalize_iface(p.get("interface") or "")
        if iface not in BUS_TYPES:
            continue
        has_bus_pin = True
        sn = p.get("signal_name")
        if not sn:
            continue
        for ep in idx.get(sn, {}).get("ecu_pins", []):
            for b in ecu_buses_map.get(ep.get("ecu"), []):
                if normalize_iface(b.get("type", "")) == iface and sn in (b.get("signals") or []):
                    connected.add(str(b.get("name", "")))
    return connected, has_bus_pin


def gather_components(arch: dict, buses: list[dict]) -> tuple[list[dict], list[str]]:
    """Every ECU/device with at least one pin wired into a named bus, zoned and
    deduped. Returns (components, omitted_names) — omitted are components with
    a bus-type pin that never resolved to a named bus (no rail to attach to)."""
    ecus = list(iter_ecus(arch))
    ecu_buses: dict[str, list[dict]] = defaultdict(list)
    for b in buses:
        for node in (b.get("nodes") or []):
            if isinstance(node, dict) and node.get("ecu"):
                ecu_buses[str(node["ecu"])].append(b)

    idx = build_signal_index(arch)
    components: list[dict] = []
    omitted: list[str] = []

    for e in ecus:
        ename = str(e.get("name", ""))
        connected = {str(b.get("name", "")) for b in ecu_buses.get(ename, [])}
        if not connected:
            has_bus_pin = any(
                normalize_iface(p.get("type", p.get("interface", ""))) in BUS_TYPES
                for p in (e.get("pins") or []) if isinstance(p, dict)
            )
            if has_bus_pin:
                omitted.append(ename)
            continue
        components.append({
            "name": ename, "kind": "ECU", "device_type": "ECU",
            "subtitle": str(e.get("variant", "")),
            "zone": str(e.get("location", "") or "").strip() or "Unspecified location",
            "buses": sorted(connected), "valve": False,
        })

    device_order: list[str] = []
    device_meta: dict[str, dict] = {}
    for p in iter_device_pins(arch):
        dn = p.get("device")
        if dn and dn not in device_meta:
            device_order.append(dn)
            device_meta[dn] = {"system": p.get("system", ""), "device_type": p.get("device_type", "")}

    for dn in device_order:
        connected, has_bus_pin = device_connected_buses(arch, dn, idx, ecu_buses)
        if not connected:
            if has_bus_pin:
                omitted.append(dn)
            continue
        meta = device_meta[dn]
        components.append({
            "name": dn, "kind": "Device", "device_type": meta["device_type"],
            "subtitle": meta["device_type"],
            "zone": meta["system"] or "Unassigned system",
            "buses": sorted(connected),
            "valve": str(meta["device_type"]).upper() in VALVE_TYPES,
        })

    components.sort(key=lambda c: (0 if c["kind"] == "ECU" else 1, c["zone"], c["name"]))
    return components, omitted


def build_networks(buses: list[dict], colors: dict[str, str]) -> list[dict]:
    nets = []
    for b in buses:
        name = str(b.get("name", ""))
        btype = normalize_iface(b.get("type", ""))
        desc = f'{btype} · {fmt_bitrate(b.get("bitrate"))}'
        prio = b.get("priority")
        if prio:
            desc += f" · priority {prio}"
        nets.append({"id": name, "label": name, "color": colors.get(name, "#5aa6ff"), "description": desc})
    return nets


def bus_deck_height(network_count: int) -> int:
    n = max(network_count, 1)
    return DECK_ROW_FIRST_OFFSET + (n - 1) * DECK_ROW_H + DECK_BOTTOM_PAD


def _bus_label_width(label: str) -> float:
    return max(74.0, len(label) * 7.2 + 28)


def bus_start_offset(networks: list[dict]) -> float:
    """Minimum x-offset (from the deck's left edge) where the bus line can
    safely start — wide enough that no bus name pill or description text
    overflows into the line, no matter how long the real bus names are.
    Mirrored exactly by the JS renderer's pill/description placement in
    drawBusDeck() so the two never disagree."""
    widest = float(DECK_BUS_START_OFFSET)
    for net in networks:
        label_w = _bus_label_width(net.get("label", ""))
        desc_w = len(net.get("description") or "") * 6.8 + 14
        needed = DECK_LABEL_X + label_w + DECK_LABEL_GAP + desc_w + DECK_LINE_GAP
        widest = max(widest, needed)
    return widest


def _count_port_rows(bus_names: list[str], card_w: float) -> int:
    """Mirror the client-side port-wrapping algorithm exactly (same per-label
    width formula, same wrap condition) so the server-computed card height
    always matches what the browser actually renders — see getPortPositions()
    in the embedded JS. A mismatch here is what causes cards to overlap their
    own icon/title."""
    max_width = max(80, card_w - 18)
    x = 0.0
    row = 0
    for i, name in enumerate(bus_names):
        width = max(38, min(82, len(name) * 7 + 18))
        if x + width > max_width and i > 0:
            row += 1
            x = 0.0
        x += width + PORT_GAP
    return row + 1


def _card_size(bus_names: list[str]) -> tuple[int, int, int]:
    rows = _count_port_rows(bus_names, CARD_W) if bus_names else 1
    ports_block_h = TOP_PAD + rows * PORT_ROW_H
    h = ports_block_h + ICON_H + TEXT_H
    return CARD_W, max(MIN_CARD_H, h), ports_block_h


def _zone_grid_height(heights: list[int], cols: int) -> int:
    y = 0
    for i in range(0, len(heights), cols):
        y += max(heights[i:i + cols]) + CARD_GAP
    return y - CARD_GAP if heights else 0


def _layout_zone(devices: list[dict], origin_x: float, origin_y: float, cols: int) -> None:
    y = origin_y
    for i in range(0, len(devices), cols):
        row = devices[i:i + cols]
        row_h = max(d["h"] for d in row)
        for j, d in enumerate(row):
            d["x"] = origin_x + j * (CARD_W + CARD_GAP)
            d["y"] = y
        y += row_h + CARD_GAP


def _bucket_zones(zone_order: list[str], zones: dict[str, list[dict]]) -> tuple[list[str], list[str]]:
    """Split zones across the top and bottom of the bus deck, greedily
    balancing total card footprint between the two sides (not ECU/device
    kind — a zone is a meaningful cluster and stays whole). A single zone
    splits its own device list in half rather than leaving one side empty."""
    if len(zone_order) <= 1:
        zname = zone_order[0] if zone_order else None
        if zname is None:
            return [], []
        devices = sorted(zones[zname], key=lambda d: d["name"])
        half = math.ceil(len(devices) / 2)
        top_devices, bottom_devices = devices[:half], devices[half:]
        if not bottom_devices:
            return [zname], []
        top_name, bottom_name = f"{zname} — Top", f"{zname} — Bottom"
        zones[top_name] = top_devices
        zones[bottom_name] = bottom_devices
        del zones[zname]
        return [top_name], [bottom_name]

    weight = {z: sum(d["w"] * d["h"] for d in zones[z]) for z in zone_order}
    ordered = sorted(zone_order, key=lambda z: weight[z], reverse=True)
    top: list[str] = []
    bottom: list[str] = []
    top_w = bottom_w = 0.0
    for z in ordered:
        if top_w <= bottom_w:
            top.append(z)
            top_w += weight[z]
        else:
            bottom.append(z)
            bottom_w += weight[z]
    top_set = set(top)
    return [z for z in zone_order if z in top_set], [z for z in zone_order if z not in top_set]


def _pack_zone_row(zone_names: list[str], zones: dict[str, list[dict]]) -> tuple[float, float, list[dict]]:
    """Shelf-pack the given zones left-to-right (wrapping at MAX_ROW_W),
    grid-pack cards inside each zone, all relative to a local (0, 0) origin.
    Mutates each component with local x/y. Returns (content_w, content_h,
    groups) where groups is the zone-box list (also local-relative)."""
    shelf_x = 0.0
    shelf_y = 0.0
    shelf_h = 0.0
    max_x = 0.0
    groups: list[dict] = []

    for zname in zone_names:
        devices = zones[zname]
        cols = len(devices)  # one horizontal line per zone — no internal wrap
        content_h = _zone_grid_height([d["h"] for d in devices], cols)
        zone_w = cols * CARD_W + (cols - 1) * CARD_GAP + 2 * ZONE_PAD_SIDE
        zone_h = ZONE_PAD_TOP + content_h + ZONE_PAD_BOTTOM

        if shelf_x > 0 and shelf_x + zone_w > MAX_ROW_W:
            shelf_y += shelf_h + ZONE_GAP
            shelf_x = 0.0
            shelf_h = 0.0

        _layout_zone(devices, shelf_x + ZONE_PAD_SIDE, shelf_y + ZONE_PAD_TOP, cols)
        groups.append({"id": slug(zname), "label": zname, "x": shelf_x, "y": shelf_y, "w": zone_w, "h": zone_h})

        shelf_x += zone_w + ZONE_GAP
        shelf_h = max(shelf_h, zone_h)
        max_x = max(max_x, shelf_x - ZONE_GAP)

    return max_x, shelf_y + shelf_h, groups


def layout_canvas(components: list[dict], deck_h: float, bus_offset: float = 0.0) -> tuple[float, float, float, float, list[dict]]:
    """Mirrored bus-trunk topology: zones are balanced across the top and
    bottom of a horizontally-centered bus deck, each side independently
    shelf/grid-packed then centered over the deck's CLEAR zone only — never
    the legend gutter (width bus_offset, see bus_start_offset()) that holds
    each bus's name/description text. Cards — and the straight vertical
    connector lines dropping from their ports down to the deck — are
    confined to x >= busStart so they can never be drawn on top of that
    text, regardless of whether the card content is wider or narrower than
    the legend itself. Mutates each component with x/y/w/h/side/
    ports_block_h. Returns (canvas_w, canvas_h, deck_y, deck_w, groups),
    each group tagged with its side."""
    zone_order: list[str] = []
    zones: dict[str, list[dict]] = defaultdict(list)
    for c in components:
        if c["zone"] not in zones:
            zone_order.append(c["zone"])
        zones[c["zone"]].append(c)

    for c in components:
        c["w"], c["h"], c["ports_block_h"] = _card_size(c["buses"])

    top_names, bottom_names = _bucket_zones(zone_order, zones)
    top_w, top_h, top_groups = _pack_zone_row(top_names, zones)
    bottom_w, bottom_h, bottom_groups = _pack_zone_row(bottom_names, zones)

    line_zone_w = max(top_w, bottom_w, MIN_BUS_LINE_LEN)
    deck_w = bus_offset + line_zone_w + DECK_BUS_END_PAD
    canvas_w = deck_w + 2 * MARGIN_X
    if canvas_w < MIN_CANVAS_W:
        grow = MIN_CANVAS_W - canvas_w
        line_zone_w += grow
        deck_w += grow
        canvas_w = MIN_CANVAS_W

    card_zone_x0 = MARGIN_X + bus_offset
    top_dx = card_zone_x0 + (line_zone_w - top_w) / 2
    bottom_dx = card_zone_x0 + (line_zone_w - bottom_w) / 2
    top_dy = MARGIN_Y
    deck_y = MARGIN_Y + top_h + ZONE_GAP
    bottom_dy = deck_y + deck_h + ZONE_GAP

    groups: list[dict] = []
    for grp in top_groups:
        grp["x"] += top_dx
        grp["y"] += top_dy
        grp["side"] = "top"
        groups.append(grp)
    for grp in bottom_groups:
        grp["x"] += bottom_dx
        grp["y"] += bottom_dy
        grp["side"] = "bottom"
        groups.append(grp)

    for name in top_names:
        for c in zones[name]:
            c["x"] += top_dx
            c["y"] += top_dy
            c["side"] = "top"
    for name in bottom_names:
        for c in zones[name]:
            c["x"] += bottom_dx
            c["y"] += bottom_dy
            c["side"] = "bottom"

    canvas_h = bottom_dy + bottom_h + MARGIN_Y
    return canvas_w, canvas_h, deck_y, deck_w, groups


_ECDF_CSS = """
.eddash{height:80vh;min-height:560px;max-height:880px;border:1px solid var(--dark-border1,rgba(255,255,255,.1));border-radius:var(--radius-lg,12px);overflow:hidden;background:var(--dark-surface1,#0d1420)}
.eddash .app{height:100%;display:grid;grid-template-columns:340px 1fr;gap:0}
.eddash aside{border-right:1px solid var(--dark-border1,rgba(255,255,255,.1));background:var(--dark-surface2,#131a27);overflow:hidden;display:flex;flex-direction:column;min-width:0}
.eddash .brand{padding:18px 18px 15px;background:linear-gradient(135deg,#123b46 0%,#0d2c35 55%,#081a20 100%);color:#fff}
.eddash .brand h1{margin:0 0 6px;font-size:18px;letter-spacing:.2px;line-height:1.15;color:#fff}
.eddash .brand p{margin:0;opacity:.85;font-size:12px;line-height:1.4}
.eddash .panel-body{padding:14px;overflow:auto}
.eddash .pbsec{border:1px solid var(--dark-border1,rgba(255,255,255,.1));border-radius:12px;background:var(--dark-surface3,#1a2333);margin-bottom:12px}
.eddash .pbsec-head{padding:11px 12px 8px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.eddash .pbsec-head h2{margin:0;font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--text-fade,#677289)}
.eddash .pbsec-body{padding:0 12px 12px}
.eddash .edstats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
.eddash .edstat{background:var(--dark-surface2,#131a27);border:1px solid var(--dark-border1,rgba(255,255,255,.1));border-radius:10px;padding:9px 6px;text-align:center}
.eddash .edstat strong{display:block;font-size:18px;line-height:1;color:var(--text-primary,#e8ecf4)}
.eddash .edstat span{display:block;color:var(--text-fade,#677289);font-size:10px;margin-top:4px}
.eddash .network-list{display:grid;gap:6px}
.eddash .network-item{display:grid;grid-template-columns:10px 84px 1fr;align-items:center;gap:8px;padding:7px 8px;border-radius:10px;cursor:pointer;border:1px solid transparent;transition:.15s ease}
.eddash .network-item:hover,.eddash .network-item.active{background:rgba(46,230,255,.08);border-color:rgba(46,230,255,.35)}
.eddash .dot{width:10px;height:10px;border-radius:999px;box-shadow:inset 0 0 0 2px rgba(255,255,255,.25),0 0 0 1px rgba(0,0,0,.3)}
.eddash .net-name{font-weight:800;font-size:11px;letter-spacing:.02em;color:var(--text-primary,#e8ecf4);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.eddash .net-desc{color:var(--text-fade,#677289);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.eddash input[type="search"]{width:100%;padding:9px 10px;border:1px solid var(--dark-border1,rgba(255,255,255,.1));border-radius:10px;background:var(--dark-surface2,#131a27);color:var(--text-primary,#e8ecf4);outline:none;font:inherit;font-size:12px}
.eddash input[type="search"]:focus{border-color:var(--accent-cyan,#2ee6ff)}
.eddash .edbtn{border:0;border-radius:10px;padding:8px 10px;font:inherit;font-size:11px;font-weight:800;cursor:pointer;color:var(--text-primary,#e8ecf4);background:var(--dark-surface2,#131a27);border:1px solid var(--dark-border1,rgba(255,255,255,.1));transition:.15s ease;white-space:nowrap}
.eddash .edbtn:hover{filter:brightness(1.15)}
.eddash .edbtn.primary{background:var(--accent-cyan,#2ee6ff);color:#04141a;border-color:var(--accent-cyan,#2ee6ff)}
.eddash .edbtn.dark{background:#0a0f18;color:var(--text-primary,#e8ecf4)}
.eddash .button-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.eddash .edhint{margin:8px 0 0;color:var(--text-fade,#677289);font-size:11px;line-height:1.4}
.eddash main{background:var(--dark-bg,#070b14);overflow:hidden;display:grid;grid-template-rows:auto 1fr;min-width:0}
.eddash .toolbar{position:relative;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;border-bottom:1px solid var(--dark-border1,rgba(255,255,255,.1));background:var(--dark-surface2,#131a27)}
.eddash .toolbar-title strong{display:block;font-size:14px;line-height:1.2;color:var(--text-primary,#e8ecf4);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.eddash .toolbar-title span{display:block;color:var(--text-fade,#677289);font-size:11px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:46vw}
.eddash .toolbar-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}
.eddash .canvas-wrap{position:relative;min-height:0;overflow:hidden;background:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px),var(--dark-bg,#070b14);background-size:26px 26px}
.eddash svg{width:100%;height:100%;display:block;cursor:grab;user-select:none}
.eddash svg.dragging{cursor:grabbing}
.eddash .bus-line{stroke-width:5;stroke-linecap:round;opacity:.95}
.eddash .bus-label-bg{fill:var(--dark-surface3,#1a2333);stroke-width:1.2}
.eddash .bus-label-text{font-size:14px;font-weight:850;dominant-baseline:central;text-anchor:middle}
.eddash .bus-desc{font-size:11.5px;fill:var(--text-fade,#677289);dominant-baseline:central}
.eddash .connection{fill:none;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;opacity:.72}
.eddash .connection-glow{fill:none;stroke:rgba(7,11,20,.7);stroke-width:6.5;stroke-linecap:round;stroke-linejoin:round;opacity:.8}
.eddash .junction{stroke:var(--dark-bg,#070b14);stroke-width:2.2}
.eddash .zone rect.zone-bg{fill:rgba(255,255,255,.035);stroke:var(--dark-border2,rgba(255,255,255,.24));stroke-width:1.4;stroke-dasharray:9 7}
.eddash .zone .zone-tab{fill:var(--dark-surface3,#1a2333);stroke:var(--accent-cyan,#2ee6ff);stroke-width:1.3}
.eddash .zone .zone-text{fill:var(--text-secondary,#aeb9cc);font-size:12.5px;font-weight:850;letter-spacing:.08em;text-transform:uppercase;dominant-baseline:central}
.eddash .device-card{filter:drop-shadow(0 10px 16px rgba(0,0,0,.35))}
.eddash .device-box{fill:var(--dark-surface3,#1a2333);stroke:var(--dark-border2,rgba(255,255,255,.24));stroke-width:1.2}
.eddash .device-title{font-size:15px;font-weight:900;text-anchor:middle;fill:var(--text-primary,#e8ecf4)}
.eddash .device-subtitle{font-size:11px;fill:var(--text-fade,#677289);text-anchor:middle}
.eddash .port-badge rect{stroke-width:1.2}
.eddash .port-badge text{font-size:10px;font-weight:900;letter-spacing:.02em;dominant-baseline:central;text-anchor:middle}
.eddash .chip-pin{stroke:var(--accent-green,#2ee6a0);stroke-width:4;stroke-linecap:square}
.eddash .icon-green{stroke:var(--accent-green,#2ee6a0);fill:none;stroke-width:4;stroke-linejoin:round}
.eddash .icon-green-fill{fill:var(--accent-green,#2ee6a0);stroke:none}
.eddash .icon-screen{fill:#3a4452;stroke:var(--accent-green,#2ee6a0);stroke-width:4}
.eddash .dimmed{opacity:.1!important}
.eddash .highlighted{opacity:1!important;filter:drop-shadow(0 0 7px rgba(46,230,255,.6))}
.eddash .toast{position:absolute;right:18px;bottom:18px;padding:11px 13px;background:var(--dark-surface3,#1a2333);color:var(--text-primary,#e8ecf4);border:1px solid var(--dark-border2,rgba(255,255,255,.22));border-radius:12px;opacity:0;transform:translateY(10px);pointer-events:none;transition:.2s ease;font-size:12px;z-index:4}
.eddash .toast.show{opacity:1;transform:translateY(0)}
@media (max-width:980px){.eddash{height:auto;min-height:0}.eddash .app{grid-template-columns:1fr;height:auto}.eddash aside{max-height:48vh}.eddash main{min-height:60vh}}
@media print{.eddash{height:auto;max-height:none;border:0}.eddash aside,.eddash .toolbar{display:none}.eddash main{height:90vh}}
"""


_ECDF_JS = r"""
(function(){
const data = __DATA_JSON__;
let highlightNetwork = null;
let searchTerm = "";
let viewBox = {x:0, y:0, w:data.canvas.width, h:data.canvas.height};
const svg = document.getElementById('eddiagram');
const root = document.getElementById('edroot');
const ns = 'http://www.w3.org/2000/svg';

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(ns, name);
  for (const [key, val] of Object.entries(attrs)) {
    if (val !== undefined && val !== null) node.setAttribute(key, val);
  }
  if (parent) parent.appendChild(node);
  return node;
}

function textNode(parent, txt, attrs = {}) {
  const t = el('text', attrs, parent);
  t.textContent = txt;
  return t;
}

function roundedRect(parent, x, y, w, h, r, attrs = {}) {
  return el('rect', { x, y, width: w, height: h, rx: r, ry: r, ...attrs }, parent);
}

function netMap() {
  const deck = data.busDeck;
  return Object.fromEntries(data.networks.map((n, i) => [n.id, {...n, y: deck.y + deck.rowFirstOffset + i * deck.rowSpacing}]));
}

function portLabel(port) {
  return port.label || port.network || port.interface || 'PORT';
}

function cardBlocks(device) {
  const portsH = device.portsBlockH || 32;
  const iconH = 80, textH = 50;
  const slack = Math.max(0, device.h - (portsH + iconH + textH));
  if (device.side === 'top') {
    // bus deck sits below a top-side card, so its ports must be the
    // bottom-most block (nearest the deck); slack absorbed at the top.
    return { textY: slack, iconY: slack + textH, portsY: slack + textH + iconH, iconH, textH, portsH };
  }
  // bus deck sits above a bottom-side card, so its ports stay the
  // top-most block (nearest the deck), same as the original layout.
  return { portsY: 0, iconY: portsH, textY: portsH + iconH, iconH, textH, portsH };
}

function getPortPositions(device) {
  const ports = device.ports || [];
  const positions = [];
  const rowH = 22;
  const gap = 5;
  const maxWidth = Math.max(80, device.w - 18);
  const blocks = cardBlocks(device);
  let x = device.x + 9;
  let y = device.y + blocks.portsY + 10;
  let row = 0;
  ports.forEach((port, i) => {
    const label = portLabel(port);
    const width = Math.max(38, Math.min(82, label.length * 7 + 18));
    if (x + width > device.x + 9 + maxWidth && i > 0) {
      row += 1;
      x = device.x + 9;
      y = device.y + blocks.portsY + 10 + row * rowH;
    }
    // Badges wrap onto multiple rows on narrow cards, and each row restarts
    // x from the card's left edge — so a port directly below another one
    // (different row, near-identical x) would draw a connector line right
    // on top of it. laneX fans every port on the card out across its full
    // width by port index alone (row-independent), so N ports always exit
    // as N clearly separated lines regardless of how badges wrapped.
    const laneX = device.x + (i + 0.5) * device.w / ports.length;
    positions.push({ port, label, x, y, w: width, h: 17, cx: x + width/2, cy: y + 8.5, row, laneX });
    x += width + gap;
  });
  return positions;
}

function matchesSearch(device) {
  if (!searchTerm) return true;
  const haystack = [
    device.name,
    device.subtitle,
    device.zone,
    ...(device.ports || []).flatMap(p => [p.network, p.interface, p.label])
  ].filter(Boolean).join(' ').toLowerCase();
  return haystack.includes(searchTerm.toLowerCase());
}

function isDeviceLinked(device, netId) {
  return (device.ports || []).some(p => p.network === netId);
}

function setViewBox(vb) {
  viewBox = vb;
  svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
}

function render() {
  root.replaceChildren();
  const networks = netMap();

  document.getElementById('eddiagramTitle').textContent = data.title || 'ECU Network Dataflow Diagram';
  document.getElementById('eddiagramSubtitle').textContent = data.subtitle || 'Port-to-bus connectivity';
  document.getElementById('edstatDevices').textContent = data.devices.length;
  document.getElementById('edstatPorts').textContent = data.devices.reduce((a,d) => a + (d.ports || []).length, 0);
  document.getElementById('edstatBuses').textContent = data.networks.length;

  drawBusDeck(networks);
  drawZones();
  drawConnections(networks);
  drawDevices(networks);
  renderNetworkList();
}

function busLabelWidth(label) {
  return Math.max(74, (label || '').length * 7.2 + 28);
}

function drawBusDeck(networks) {
  const deck = data.busDeck;
  const g = el('g', { id: 'edbusDeck' }, root);
  roundedRect(g, deck.x, deck.y, deck.w, deck.h, 26, { class: 'bus-label-bg' });
  textNode(g, 'NETWORK BACKBONE', { x: deck.x + 26, y: deck.y + 21, 'font-size': 13, 'font-weight': 900, fill: 'var(--text-secondary,#aeb9cc)', 'letter-spacing': '.12em' });
  textNode(g, 'Horizontal buses come from the real buses[] export. Every component port sharing a bus id is routed automatically.', { x: deck.x + 26, y: deck.y + 39, 'font-size': 11, fill: 'var(--text-fade,#677289)' });

  data.networks.forEach((net) => {
    const y = networks[net.id].y;
    const labelW = busLabelWidth(net.label);
    const bus = el('g', { class: `bus-group ${highlightNetwork && highlightNetwork !== net.id ? 'dimmed' : ''}`, 'data-net': net.id }, g);
    roundedRect(bus, deck.x + 18, y - 10, labelW, 20, 9, { class: 'bus-label-bg', stroke: net.color });
    textNode(bus, net.label, { class: 'bus-label-text', x: deck.x + 18 + labelW / 2, y, fill: net.color });
    textNode(bus, net.description || '', { class: 'bus-desc', x: deck.x + 18 + labelW + 14, y });
    el('line', { class: 'bus-line', x1: deck.busStart, y1: y, x2: deck.busEnd, y2: y, stroke: net.color }, bus);
  });
}

function drawZones() {
  const zones = el('g', { id: 'edzones' }, root);
  (data.groups || []).forEach(zone => {
    const g = el('g', { class: `zone zone-${zone.side || 'bottom'}`, 'data-zone': zone.id }, zones);
    roundedRect(g, zone.x, zone.y, zone.w, zone.h, 20, { class: 'zone-bg' });
    const labelW = Math.max(170, zone.label.length * 8 + 34);
    // Tab sits on the outer edge (away from the bus deck) on both sides, so
    // the connection lines running between the deck and the cards never
    // cross it.
    const tabY = zone.side === 'bottom' ? zone.y + zone.h - 15 : zone.y - 15;
    roundedRect(g, zone.x + 16, tabY, labelW, 30, 14, { class: 'zone-tab' });
    textNode(g, zone.label, { class: 'zone-text', x: zone.x + 32, y: tabY + 15 });
  });
}

function drawConnections(networks) {
  const layer = el('g', { id: 'edconnections' }, root);
  data.devices.forEach(device => {
    const portPositions = getPortPositions(device);
    const deviceMatch = matchesSearch(device);
    const edgeY = device.side === 'top' ? device.y + device.h : device.y;
    portPositions.forEach(pos => {
      if (!pos.port.network || !networks[pos.port.network]) return;
      const net = networks[pos.port.network];
      const dim = (highlightNetwork && highlightNetwork !== pos.port.network) || !deviceMatch;
      const isHi = highlightNetwork && highlightNetwork === pos.port.network;
      // Stub straight down/up from the badge to the card's own edge (stays
      // under the badge), jog to this port's dedicated lane, then a clean
      // parallel run to the bus row — so every port's line is distinct even
      // when its badge shares a near-identical x with one on another row.
      const pathD = `M ${pos.cx} ${pos.cy} V ${edgeY} H ${pos.laneX} V ${net.y}`;
      const group = el('g', { class: `${dim ? 'dimmed' : ''} ${isHi ? 'highlighted' : ''}`, 'data-net': pos.port.network, 'data-device': device.id }, layer);
      el('path', { d: pathD, class: 'connection-glow' }, group);
      el('path', { d: pathD, class: 'connection', stroke: net.color }, group);
      el('circle', { class: 'junction', cx: pos.laneX, cy: net.y, r: 4.6, fill: net.color }, group);
    });
  });
}

function drawDevices(networks) {
  const layer = el('g', { id: 'eddevices' }, root);
  data.devices.forEach(device => {
    const linked = highlightNetwork ? isDeviceLinked(device, highlightNetwork) : true;
    const matched = matchesSearch(device);
    const cls = `device-card ${(!linked || !matched) ? 'dimmed' : ''} ${(highlightNetwork && linked) ? 'highlighted' : ''}`;
    const g = el('g', { class: cls, transform: `translate(${device.x},${device.y})`, 'data-device': device.id }, layer);
    roundedRect(g, 0, 0, device.w, device.h, 14, { class: 'device-box' });
    const blocks = cardBlocks(device);
    drawPorts(g, device, networks);
    drawIcon(g, device, blocks.iconY + blocks.iconH / 2);
    textNode(g, device.name, { class: 'device-title', x: device.w/2, y: blocks.textY + 12 });
    wrapSubtitle(g, device.subtitle || '', device.w/2, blocks.textY + 29, device.w - 24);
  });
}

function drawPorts(g, device, networks) {
  getPortPositions(device).forEach(pos => {
    const net = pos.port.network && networks[pos.port.network];
    const fill = net ? net.color : '#3a4452';
    const stroke = net ? shadeColor(net.color, -18) : 'var(--dark-border2,rgba(255,255,255,.22))';
    const textColor = needsDarkText(fill) ? '#0b0f17' : '#fff';
    const pg = el('g', { class: 'port-badge', transform: `translate(${pos.x - device.x},${pos.y - device.y})`, 'data-net': pos.port.network || '', 'data-interface': pos.port.interface || '' }, g);
    roundedRect(pg, 0, 0, pos.w, pos.h, 4, { fill, stroke });
    textNode(pg, pos.label, { x: pos.w/2, y: pos.h/2 + .4, fill: textColor });
  });
}

function drawIcon(g, device, cy) {
  const cx = device.w / 2;
  if (device.type === 'valve') {
    el('polygon', { points: `${cx-38},${cy-26} ${cx},${cy} ${cx-38},${cy+26}`, class: 'icon-green-fill' }, g);
    el('polygon', { points: `${cx+38},${cy-26} ${cx},${cy} ${cx+38},${cy+26}`, class: 'icon-green-fill' }, g);
    el('line', { x1: cx - 42, y1: cy - 30, x2: cx + 42, y2: cy + 30, stroke: 'var(--accent-orange,#ffb43d)', 'stroke-width': 2, opacity: .85 }, g);
    return;
  }
  if (device.type === 'screen' || device.type === 'terminal') {
    roundedRect(g, cx - 48, cy - 32, 96, 58, 6, { class: 'icon-screen' });
    roundedRect(g, cx - 15, cy + 28, 30, 8, 3, { class: 'icon-green-fill' });
    roundedRect(g, cx - 32, cy + 37, 64, 8, 4, { class: 'icon-green-fill' });
    if (device.type === 'terminal') {
      roundedRect(g, cx - 32, cy - 18, 64, 30, 4, { fill: '#5a6a78', stroke: 'none', opacity: .75 });
    }
    return;
  }
  if (device.type === 'keyboard') {
    roundedRect(g, cx - 50, cy - 28, 100, 28, 5, { class: 'icon-green' });
    for (let i = 0; i < 5; i++) roundedRect(g, cx - 41 + i*18, cy - 22, 10, 7, 2, { class: 'icon-green-fill' });
    el('path', { d: `M ${cx-18} ${cy+5} C ${cx-25} ${cy-15}, ${cx-8} ${cy-15}, ${cx-4} ${cy+2} L ${cx+10} ${cy+38} C ${cx+15} ${cy+50}, ${cx-7} ${cy+57}, ${cx-14} ${cy+42} Z`, fill: 'none', stroke: 'var(--accent-green,#2ee6a0)', 'stroke-width': 4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
    return;
  }
  if (device.type === 'converter') {
    drawChipIcon(g, cx - 28, cy - 25, 56, 56);
    el('path', { d: `M ${cx+42} ${cy-12} L ${cx+72} ${cy-12} L ${cx+72} ${cy-25} L ${cx+100} ${cy} L ${cx+72} ${cy+25} L ${cx+72} ${cy+12} L ${cx+42} ${cy+12}`, fill: 'var(--accent-orange,#ffb43d)', opacity: .9 }, g);
    return;
  }
  drawChipIcon(g, cx - 31, cy - 31, 62, 62);
}

function drawChipIcon(parent, x, y, w, h) {
  for (let i=0; i<5; i++) {
    const yy = y + 8 + i * (h - 16) / 4;
    el('line', { x1: x - 13, y1: yy, x2: x - 3, y2: yy, class: 'chip-pin' }, parent);
    el('line', { x1: x + w + 3, y1: yy, x2: x + w + 13, y2: yy, class: 'chip-pin' }, parent);
  }
  for (let i=0; i<5; i++) {
    const xx = x + 8 + i * (w - 16) / 4;
    el('line', { x1: xx, y1: y - 13, x2: xx, y2: y - 3, class: 'chip-pin' }, parent);
    el('line', { x1: xx, y1: y + h + 3, x2: xx, y2: y + h + 13, class: 'chip-pin' }, parent);
  }
  roundedRect(parent, x, y, w, h, 4, { class: 'icon-green' });
}

function wrapSubtitle(parent, text, x, y, maxWidth) {
  const words = String(text).split(/\s+/);
  let line = '';
  let lines = [];
  const maxChars = Math.max(18, Math.floor(maxWidth / 6.2));
  words.forEach(word => {
    if ((line + ' ' + word).trim().length > maxChars) {
      lines.push(line.trim());
      line = word;
    } else {
      line = (line + ' ' + word).trim();
    }
  });
  if (line) lines.push(line);
  lines.slice(0,2).forEach((ln, idx) => textNode(parent, ln, { class: 'device-subtitle', x, y: y + idx * 13 }));
}

function renderNetworkList() {
  const list = document.getElementById('ednetworkList');
  list.innerHTML = '';
  data.networks.forEach(net => {
    const item = document.createElement('div');
    item.className = 'network-item' + (highlightNetwork === net.id ? ' active' : '');
    item.innerHTML = `<span class="dot" style="background:${net.color}"></span><span class="net-name">${escapeHtml(net.label)}</span><span class="net-desc">${escapeHtml(net.description || '')}</span>`;
    item.addEventListener('click', () => {
      highlightNetwork = highlightNetwork === net.id ? null : net.id;
      render();
    });
    list.appendChild(item);
  });
}

function shadeColor(hex, percent) {
  if (!hex || hex[0] !== '#') return hex;
  const f = parseInt(hex.slice(1),16), t = percent < 0 ? 0 : 255, p = Math.abs(percent)/100;
  const R = f >> 16, G = f >> 8 & 0x00FF, B = f & 0x0000FF;
  return '#' + (0x1000000 + (Math.round((t-R)*p)+R)*0x10000 + (Math.round((t-G)*p)+G)*0x100 + (Math.round((t-B)*p)+B)).toString(16).slice(1);
}

function needsDarkText(hex) {
  if (!hex || hex[0] !== '#') return true;
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return (r*299 + g*587 + b*114) / 1000 > 152;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>'"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[s]));
}

function showToast(message) {
  const toast = document.getElementById('edtoast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1700);
}

function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 500);
}

function exportSvgFile() {
  const clone = svg.cloneNode(true);
  clone.setAttribute('xmlns', ns);
  const css = Array.from(document.styleSheets)
    .map(sheet => {
      try { return Array.from(sheet.cssRules).map(r => r.cssText).join('\n'); }
      catch { return ''; }
    }).join('\n');
  const style = document.createElementNS(ns, 'style');
  style.textContent = css;
  clone.insertBefore(style, clone.firstChild);
  download('ecu-network-dataflow.svg', new XMLSerializer().serializeToString(clone), 'image/svg+xml');
  showToast('SVG exported');
}

function fit() {
  setViewBox({x:0, y:0, w:data.canvas.width, h:data.canvas.height});
}

function zoom(scale) {
  const cx = viewBox.x + viewBox.w / 2;
  const cy = viewBox.y + viewBox.h / 2;
  const nw = viewBox.w * scale;
  const nh = viewBox.h * scale;
  setViewBox({x: cx - nw/2, y: cy - nh/2, w: nw, h: nh});
}

function pointerToSvg(evt) {
  const pt = svg.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}

let drag = null;
svg.addEventListener('pointerdown', evt => {
  drag = {start: pointerToSvg(evt), vb: {...viewBox}};
  svg.setPointerCapture(evt.pointerId);
  svg.classList.add('dragging');
});
svg.addEventListener('pointermove', evt => {
  if (!drag) return;
  const now = pointerToSvg(evt);
  const dx = drag.start.x - now.x;
  const dy = drag.start.y - now.y;
  setViewBox({ ...drag.vb, x: drag.vb.x + dx, y: drag.vb.y + dy });
});
svg.addEventListener('pointerup', evt => {
  drag = null;
  svg.classList.remove('dragging');
  try { svg.releasePointerCapture(evt.pointerId); } catch {}
});
svg.addEventListener('wheel', evt => {
  evt.preventDefault();
  const mouse = pointerToSvg(evt);
  const scale = evt.deltaY > 0 ? 1.08 : .92;
  const nw = viewBox.w * scale;
  const nh = viewBox.h * scale;
  const x = mouse.x - (mouse.x - viewBox.x) * scale;
  const y = mouse.y - (mouse.y - viewBox.y) * scale;
  setViewBox({x, y, w: nw, h: nh});
}, { passive: false });

document.getElementById('eddownloadJson').addEventListener('click', () => {
  download('ecu-network-dataflow-data.json', JSON.stringify(data, null, 2), 'application/json');
  showToast('JSON downloaded');
});
document.getElementById('edexportSvg').addEventListener('click', exportSvgFile);
document.getElementById('edclearHighlight').addEventListener('click', () => { highlightNetwork = null; render(); });
document.getElementById('edclearSearch').addEventListener('click', () => { searchTerm = ''; document.getElementById('edsearch').value = ''; render(); });
document.getElementById('edsearch').addEventListener('input', e => { searchTerm = e.target.value.trim(); render(); });
document.getElementById('edzoomIn').addEventListener('click', () => zoom(.86));
document.getElementById('edzoomOut').addEventListener('click', () => zoom(1.16));
document.getElementById('edfitView').addEventListener('click', fit);
document.getElementById('edprint').addEventListener('click', () => window.print());

render();
})();
"""


def json_for_html(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def main() -> int:
    parser = make_argparser("Generate ECU Network Dataflow Diagram HTML — interactive bus-deck canvas built from the real architecture export.")
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    allowed_bus_types = {str(x).upper() for x in cfg.get("bus_interfaces", [])} or BUS_TYPES

    def bus_ok(b: dict) -> bool:
        t = normalize_iface(b.get("type", b.get("bus_type", "")))
        return bool(t) and t in allowed_bus_types

    buses = dedupe_buses_by_name([b for b in iter_buses(arch) if bus_ok(b)])
    colors = bus_colors(buses)
    components, omitted = gather_components(arch, buses)

    body = kpi_row([
        ("Buses", len(buses), "Named bus topology entries"),
        ("Components", len(components), "ECUs + networked devices drawn on the canvas"),
        ("ECUs", sum(1 for c in components if c["kind"] == "ECU"), "Controllers on a named bus"),
        ("Networked devices", sum(1 for c in components if c["kind"] == "Device"), "Smart sensors/actuators on a named bus"),
        ("Zones", len({c["zone"] for c in components}), "Location/system clusters"),
        ("Omitted", len(omitted), "Network-capable but never wired into a named bus"),
    ])

    if not buses or not components:
        body += '<section class="section"><h2>ECU Network Dataflow Diagram</h2><p class="small">No buses[] topology or no component resolves onto a named bus in this export — nothing to draw.</p></section>'
        out = outdir / "ecu_dataflow_diagram.html"
        out.write_text(html_page(
            "ECU Network Dataflow Diagram", body, cfg,
            "Interactive bus-deck canvas — every ECU and networked device wired to its real bus, drawn from the architecture export."
        ), encoding="utf-8")
        print(out)
        return 0

    networks = build_networks(buses, colors)
    deck_h = bus_deck_height(len(buses))
    bus_offset = bus_start_offset(networks)
    canvas_w, canvas_h, deck_y, deck_w, groups = layout_canvas(components, deck_h, bus_offset)

    devices_json = []
    for c in components:
        devices_json.append({
            "id": slug(c["name"]), "name": c["name"], "subtitle": c["subtitle"],
            "type": "valve" if c["valve"] else "chip", "zone": slug(c["zone"]), "side": c["side"],
            "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"], "portsBlockH": c["ports_block_h"],
            "ports": [{"network": b} for b in c["buses"]],
        })

    arch_name = arch.get("name", "Architecture")
    data = {
        "title": f"{arch_name} — ECU Network Dataflow",
        "subtitle": "Every ECU and standalone networked device with a pin wired into a named bus, drawn against the real network backbone.",
        "canvas": {"width": canvas_w, "height": canvas_h},
        "busDeck": {
            "x": MARGIN_X, "y": deck_y, "w": deck_w, "h": deck_h,
            "rowFirstOffset": DECK_ROW_FIRST_OFFSET, "rowSpacing": DECK_ROW_H,
            "busStart": MARGIN_X + bus_offset, "busEnd": MARGIN_X + deck_w - DECK_BUS_END_PAD,
        },
        "networks": networks,
        "groups": groups,
        "devices": devices_json,
    }

    body += '<section class="section"><h2>ECU Network Dataflow Diagram</h2>'
    body += ('<p class="small">Pan by dragging the canvas, zoom with the wheel or the toolbar buttons, and click a bus in '
              'the left list to highlight every component wired to it. Cards are auto-clustered into dashed zones — ECUs by '
              'location, standalone devices by system — and auto-laid-out from the real export, not hand-placed.</p>')
    if omitted:
        body += (f'<p class="small">{len(omitted)} component(s) have a network-capable pin that never resolved onto a named '
                  f'bus, so they have no rail to attach to and are omitted from the canvas: {esc(", ".join(omitted))}.</p>')

    body += f'<style>{_ECDF_CSS}</style>'
    body += f'''<div class="eddash"><div class="app">
      <aside>
        <div class="brand">
          <h1>ECU Network Dataflow</h1>
          <p>Auto-generated from the architecture export — every ECU and networked device with a real, resolved bus connection.</p>
        </div>
        <div class="panel-body">
          <div class="pbsec">
            <div class="pbsec-head"><h2>Overview</h2></div>
            <div class="pbsec-body">
              <div class="edstats">
                <div class="edstat"><strong id="edstatDevices">—</strong><span>Components</span></div>
                <div class="edstat"><strong id="edstatPorts">—</strong><span>Bus links</span></div>
                <div class="edstat"><strong id="edstatBuses">—</strong><span>Buses</span></div>
              </div>
            </div>
          </div>
          <div class="pbsec">
            <div class="pbsec-head"><h2>Search</h2><button class="edbtn" id="edclearSearch">Clear</button></div>
            <div class="pbsec-body">
              <input id="edsearch" type="search" placeholder="Find ECU, device, bus, or zone…" />
              <p class="edhint">Click a network below to highlight every connected component and route.</p>
            </div>
          </div>
          <div class="pbsec">
            <div class="pbsec-head"><h2>Network buses</h2><button class="edbtn" id="edclearHighlight">Show all</button></div>
            <div class="pbsec-body"><div class="network-list" id="ednetworkList"></div></div>
          </div>
          <div class="pbsec">
            <div class="pbsec-head"><h2>Export</h2></div>
            <div class="pbsec-body">
              <div class="button-grid">
                <button class="edbtn" id="eddownloadJson">Download JSON</button>
                <button class="edbtn" id="edexportSvg">Export SVG</button>
              </div>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <div class="toolbar">
          <div class="toolbar-title">
            <strong id="eddiagramTitle">ECU Network Dataflow Diagram</strong>
            <span id="eddiagramSubtitle">Port-to-bus connectivity</span>
          </div>
          <div class="toolbar-actions">
            <button class="edbtn" id="edzoomIn">Zoom +</button>
            <button class="edbtn" id="edzoomOut">Zoom −</button>
            <button class="edbtn" id="edfitView">Fit view</button>
            <button class="edbtn dark" id="edprint">Print / PDF</button>
          </div>
        </div>
        <div class="canvas-wrap">
          <svg id="eddiagram" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}" role="img" aria-label="ECU network dataflow diagram">
            <g id="edroot"></g>
          </svg>
          <div class="toast" id="edtoast">Saved</div>
        </div>
      </main>
    </div></div>'''
    body += '</section>'
    body += f'<script>{_ECDF_JS.replace("__DATA_JSON__", json_for_html(data))}</script>'

    out = outdir / "ecu_dataflow_diagram.html"
    out.write_text(html_page(
        "ECU Network Dataflow Diagram", body, cfg,
        "Interactive bus-deck canvas — every ECU and networked device wired to its real bus, drawn from the architecture export."
    ), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

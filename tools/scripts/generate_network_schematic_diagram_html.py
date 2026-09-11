#!/usr/bin/env python3
"""Network Schematic Diagram — freeform IC-chip canvas in the style of hand-drawn DFD posters.

Unlike network_diagram.html (a bus-lane dashboard), this report draws ECUs
and standalone networked devices (smart CAN/LIN/etc. sensors or actuators
that carry their own bus interface, as opposed to plain analog/digital pins
wired into an ECU) as IC-chip / valve-glyph nodes, auto-clustered into dashed
boxes by ECU location and device system.

A device qualifies as a standalone networked node when at least one of its
pins has a bus-type interface (CAN/LIN/ETHERNET/FLEXRAY/ISOBUS); its actual
bus membership is resolved by following its signal to the consuming ECU's
pin and reading that ECU's buses[] membership — devices are never listed in
buses[].nodes directly (only ECUs are), so this chain is the only way to
answer "what bus is this sensor really on."

Variant-scope box coloring activates automatically once a system carries
platforms/brands metadata (currently empty in both the real export and the
example fixture, so clusters render in a neutral style until that data
exists — nothing is fabricated to fill the gap).

Optional manual annotations: create network_diagram_notes.json next to this
script with the shape:
  {"notes": [{"anchor": "<ECU or device name>", "text": "...", "severity": "info"|"warning"}]}
Each note becomes a numbered flag on its anchor node plus an entry in the
"Engineering notes" list at the bottom. This is the one piece of the
reference poster (hand-written wiring caveats) that cannot be derived from
the architecture JSON — if the file is absent, the section is omitted.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from eec_archdoc_common import *

NOTES_FILENAME = "network_diagram_notes.json"
BUS_TYPES = {"CAN", "LIN", "ETHERNET", "FLEXRAY", "ISOBUS"}
VALVE_TYPES = {"ACTUATOR", "VALVE", "COIL", "MOTOR", "PUMP"}


def iter_buses(arch: dict) -> list[dict]:
    return [b for b in (arch.get("buses") or []) if isinstance(b, dict)]


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


def load_notes(script_dir: Path) -> list[dict]:
    path = script_dir / NOTES_FILENAME
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    notes = data.get("notes", []) if isinstance(data, dict) else []
    return [n for n in notes if isinstance(n, dict) and n.get("anchor") and n.get("text")]


def device_network_nodes(arch: dict, idx: dict, ecu_buses_map: dict[str, list[dict]]) -> dict[str, dict]:
    """Standalone networked devices: name -> {system, device_type, targets: {iface: {bus_names}}}."""
    nodes: dict[str, dict] = {}
    for row in iter_device_pins(arch):
        ifc = normalize_iface(row.get("interface", ""))
        if ifc not in BUS_TYPES:
            continue
        dname = row["device"]
        rec = nodes.setdefault(dname, {"system": row["system"], "device_type": row["device_type"], "targets": defaultdict(set)})
        entry = idx.get(row["signal_name"], {})
        ecu_names = {ep["ecu"] for ep in entry.get("ecu_pins", []) if ep.get("ecu")}
        bus_names = set()
        for en in ecu_names:
            for b in ecu_buses_map.get(en, []):
                if normalize_iface(b.get("type", "")) == ifc:
                    bus_names.add(str(b.get("name", "")))
        if not bus_names:
            bus_names = {f"Direct to {', '.join(sorted(ecu_names))}"} if ecu_names else {"Unresolved"}
        rec["targets"][ifc].update(bus_names)
    return nodes


def render_badges(pairs: list[tuple[str, str]]) -> str:
    return "".join(pill(t, c) for t, c in pairs) or '<span class="schem-badge-empty">—</span>'


def chip_html(name: str, subtitle: str, badge_pairs: list[tuple[str, str]], flag: str = "", valve: bool = False) -> str:
    badges = render_badges(badge_pairs)
    sub_html = f'<div class="schem-sub">{esc(subtitle)}</div>' if subtitle else ""
    if valve:
        body = (f'<div class="schem-valve"><div class="schem-valve-shape"></div></div>'
                f'<div class="schem-badges" style="margin-top:6px">{badges}</div>'
                f'<div class="schem-name">{esc(name)}</div>')
    else:
        body = f'<div class="schem-chip"><div class="schem-badges">{badges}</div><div class="schem-name">{esc(name)}</div></div>'
    return f'<div class="schem-node">{flag}{body}{sub_html}</div>'


_SCHEM_CSS = """
.schem-wrap{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}
.schem-side{width:300px;flex-shrink:0;display:flex;flex-direction:column;gap:16px}
.schem-side-box{background:var(--dark-surface2,#131a27);border:1px solid var(--dark-border1,rgba(255,255,255,.1));border-radius:var(--radius-lg,12px);padding:14px}
.schem-side-box h3{margin:0 0 10px;font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-fade,#677289)}
.schem-netname{font-size:.74rem;margin-bottom:7px;color:var(--text-secondary,#aeb9cc);font-family:monospace;line-height:1.4}
.schem-netname b{color:var(--text-primary,#e8ecf4)}
.schem-canvas{flex:1;min-width:320px}
.schem-canvas-h2{font-size:.85rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-fade,#677289);margin:18px 0 10px}
.schem-canvas-h2:first-child{margin-top:0}
.netdiag-legend{display:flex;flex-wrap:wrap;gap:8px}
.netdiag-swatch{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:var(--radius-md,8px);background:var(--dark-surface3,#1a2333);border:1px solid var(--dark-border1,rgba(255,255,255,.1));font-size:.72rem}
.netdiag-swatch .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.netdiag-swatch .label{font-weight:700;color:var(--text-secondary,#aeb9cc)}
.netdiag-swatch .count{color:var(--text-fade,#677289)}
.schem-cluster{border:1.5px dashed var(--dark-border2,rgba(255,255,255,.18));border-radius:var(--radius-lg,12px);padding:24px 16px 16px;margin-bottom:20px;position:relative;display:flex;flex-wrap:wrap;gap:18px 16px}
.schem-cluster-label{position:absolute;top:-10px;left:14px;font-size:.64rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;background:var(--dark-bg,#070b14);padding:0 6px;color:var(--text-fade,#677289)}
.schem-node{width:150px;display:flex;flex-direction:column;align-items:center;position:relative}
.schem-chip{width:100%;background:var(--dark-surface3,#1a2333);border:1.5px solid var(--dark-border2,rgba(255,255,255,.18));border-radius:6px;padding:12px 8px 9px;position:relative;min-height:50px;box-sizing:border-box}
.schem-chip::before,.schem-chip::after{content:'';position:absolute;left:16px;right:16px;height:6px;background:repeating-linear-gradient(90deg,var(--dark-border2,rgba(255,255,255,.18)) 0 3px,transparent 3px 9px)}
.schem-chip::before{top:-6px}
.schem-chip::after{bottom:-6px}
.schem-badges{display:flex;flex-wrap:wrap;gap:3px;justify-content:center;margin-bottom:5px}
.schem-badge-empty{font-size:.68rem;color:var(--text-fade,#677289)}
.schem-name{font-size:.74rem;font-weight:800;text-align:center;color:var(--text-primary,#e8ecf4);word-break:break-word;line-height:1.25}
.schem-valve{width:60px;height:60px;margin:4px auto 0}
.schem-valve-shape{width:100%;height:100%;background:var(--dark-surface3,#1a2333);border:1.5px solid var(--dark-border2,rgba(255,255,255,.18));clip-path:polygon(0 0,100% 0,0 100%,100% 100%)}
.schem-sub{font-size:.64rem;color:var(--text-fade,#677289);text-align:center;margin-top:4px}
.schem-flag{position:absolute;top:-6px;right:6px;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.62rem;font-weight:800;color:#070b14;z-index:2}
.schem-note{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md,8px);background:var(--dark-surface2,#131a27);border:1px solid var(--dark-border1,rgba(255,255,255,.1));margin-bottom:8px;font-size:.78rem;align-items:baseline}
.schem-note .tag{font-weight:800;flex-shrink:0;white-space:nowrap}
"""


def main() -> int:
    parser = make_argparser("Generate Network Schematic Diagram HTML — freeform IC-chip canvas with ECUs, networked devices, variant clustering and optional manual annotations.")
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    allowed_bus_types = {str(x).upper() for x in cfg.get("bus_interfaces", [])} or BUS_TYPES

    def bus_ok(b: dict) -> bool:
        t = normalize_iface(b.get("type", b.get("bus_type", "")))
        return bool(t) and t in allowed_bus_types

    buses = [b for b in iter_buses(arch) if bus_ok(b)]
    ecus = list(iter_ecus(arch))

    ecu_buses: dict[str, list[dict]] = defaultdict(list)
    for b in buses:
        for node in (b.get("nodes") or []):
            if isinstance(node, dict) and node.get("ecu"):
                ecu_buses[str(node["ecu"])].append(b)

    idx = build_signal_index(arch)
    iface_set = {normalize_iface(b.get("type", "")) for b in buses if b.get("type")}
    iface_signal_counts: Counter = Counter()
    for sig in idx.values():
        ifc = normalize_iface(sig.get("interface", ""))
        if ifc:
            iface_set.add(ifc)
            iface_signal_counts[ifc] += 1

    sys_meta = {str(s.get("name", "")): s for s in iter_systems(arch)}
    device_nodes = device_network_nodes(arch, idx, ecu_buses)
    notes = load_notes(Path(__file__).resolve().parent)
    flag_index = {n["anchor"]: i + 1 for i, n in enumerate(notes)}

    def flag_html_for(anchor: str) -> str:
        i = flag_index.get(anchor)
        if not i:
            return ""
        sev = next((n.get("severity", "info") for n in notes if n["anchor"] == anchor), "info")
        color = "#f59e0b" if sev == "warning" else "#2ee6ff"
        return f'<div class="schem-flag" style="background:{color}" title="See engineering note {i}">{i}</div>'

    ecu_zone_order: list[str] = []
    ecu_zones: dict[str, list[dict]] = defaultdict(list)
    for e in ecus:
        loc = str(e.get("location", "") or "").strip() or "Unspecified location"
        if loc not in ecu_zones:
            ecu_zone_order.append(loc)
        ecu_zones[loc].append(e)

    ecu_cluster_html = []
    for loc in ecu_zone_order:
        nodes_html = []
        for e in ecu_zones[loc]:
            ename = str(e.get("name", ""))
            variant = str(e.get("variant", ""))
            badge_pairs = [(str(b.get("name", "")), iface_color(normalize_iface(b.get("type", "")))) for b in ecu_buses.get(ename, [])]
            nodes_html.append(chip_html(ename, variant, badge_pairs, flag_html_for(ename)))
        ecu_cluster_html.append(f'<div class="schem-cluster"><span class="schem-cluster-label">{esc(loc)}</span>{"".join(nodes_html)}</div>')

    dev_zone_order: list[str] = []
    dev_zones: dict[str, list[str]] = defaultdict(list)
    for dname, rec in device_nodes.items():
        sysname = rec["system"] or "Unassigned system"
        if sysname not in dev_zones:
            dev_zone_order.append(sysname)
        dev_zones[sysname].append(dname)

    device_cluster_html = []
    for sysname in dev_zone_order:
        sys_obj = sys_meta.get(sysname, {})
        platforms = sys_obj.get("platforms") or []
        if not isinstance(platforms, list):
            platforms = [platforms]
        platforms = [str(p) for p in platforms if p]
        accent = iface_color(sysname) if platforms else None  # reuse the hash-based palette fallback purely for a stable per-system color
        label = f"{sysname} · {', '.join(platforms)}" if platforms else sysname
        nodes_html = []
        for dname in sorted(dev_zones[sysname]):
            rec = device_nodes[dname]
            badge_pairs = [(t, iface_color(ifc)) for ifc, targets in rec["targets"].items() for t in sorted(targets)]
            is_valve = str(rec["device_type"]).upper() in VALVE_TYPES
            nodes_html.append(chip_html(dname, str(rec["device_type"]), badge_pairs, flag_html_for(dname), valve=is_valve))
        border_style = f"border-color:{accent}" if accent else ""
        label_style = f"color:{accent}" if accent else ""
        device_cluster_html.append(
            f'<div class="schem-cluster" style="{border_style}"><span class="schem-cluster-label" style="{label_style}">{esc(label)}</span>{"".join(nodes_html)}</div>'
        )

    netname_lines = "".join(
        f'<div class="schem-netname"><b>{esc(b.get("name",""))}</b> = "{esc(normalize_iface(b.get("type","")))}, '
        f'{fmt_bitrate(b.get("bitrate"))}, priority {esc(b.get("priority","") or "—")}"</div>'
        for b in buses
    ) or '<span class="small">No named buses.</span>'

    legend_items = "".join(
        f'<div class="netdiag-swatch"><span class="dot" style="background:{iface_color(ifc)}"></span>'
        f'{iface_icon(ifc)}<span class="label">{esc(ifc)}</span><span class="count">{iface_signal_counts.get(ifc, 0)}</span></div>'
        for ifc in sorted(iface_set)
    ) or '<span class="small">No interfaces discovered.</span>'

    notes_html = ""
    if notes:
        rows = []
        for i, n in enumerate(notes, start=1):
            sev = n.get("severity", "info")
            color = "#f59e0b" if sev == "warning" else "#2ee6ff"
            rows.append(f'<div class="schem-note"><span class="tag" style="color:{color}">#{i} · {esc(n["anchor"])}</span><span>{esc(n["text"])}</span></div>')
        notes_html = f'<section class="section schem-notes"><h2>Engineering notes</h2>{"".join(rows)}</section>'

    body = kpi_row([
        ("ECUs", len(ecus), "Controllers on canvas"),
        ("Networked devices", len(device_nodes), "Smart sensors/actuators with their own bus interface"),
        ("Buses", len(buses), "Named bus topology entries"),
        ("Notes", len(notes), "Manual engineering annotations" if notes else "None authored yet — see script docstring"),
    ])

    body += (
        f'<section class="section"><style>{_SCHEM_CSS}</style><div class="schem-wrap">'
        '<div class="schem-side">'
        f'<div class="schem-side-box"><h3>Network names</h3>{netname_lines}</div>'
        f'<div class="schem-side-box"><h3>Connection library</h3><div class="netdiag-legend">{legend_items}</div></div>'
        '</div>'
        '<div class="schem-canvas">'
        '<div class="schem-canvas-h2">ECU nodes by location</div>'
        + ("".join(ecu_cluster_html) or '<p class="small">No ECUs found.</p>')
        + '<div class="schem-canvas-h2">Networked devices by system</div>'
        + ("".join(device_cluster_html) or '<p class="small">No standalone networked devices found — every field device in this export is wired through ECU analog/digital pins rather than carrying its own bus interface.</p>')
        + '</div></div></section>'
    )
    body += notes_html

    out = outdir / "network_schematic_diagram.html"
    out.write_text(html_page(
        "Network Schematic Diagram", body, cfg,
        "Freeform IC-chip canvas — ECUs and standalone networked devices auto-clustered by location/system, with connection legends and optional manual engineering notes."
    ), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Advanced UI components for professional data visualization.

Generates KPI tiles, I/O grids, flow diagrams, detail panels, and semantic
color-coded elements for rich, interactive reports.
"""
from __future__ import annotations

import json
from typing import Any, Sequence


def esc(value: Any) -> str:
    """HTML escape."""
    import html
    return html.escape(str("" if value is None else value), quote=True)


class IOColorMap:
    """Semantic colors for I/O types."""

    DEFAULT_MAP = {
        "AI": "#60a5fa",        # Analog input - blue
        "DI": "#34d399",        # Digital input - green
        "FI": "#f59e0b",        # Frequency input - amber
        "SENT": "#818cf8",      # SENT input - indigo
        "CURR": "#2dd4bf",      # Current input - cyan
        "RES": "#facc15",       # Resistance - yellow
        "PWM_HS": "#c084fc",    # PWM high-side - purple
        "PWM_LS": "#d8b4fe",    # PWM low-side - light purple
        "DO_HS": "#4ade80",     # Digital output high - light green
        "DO_LS": "#86efac",     # Digital output low - lighter green
        "CAN": "#fb7185",       # CAN - rose
        "LIN": "#fb923c",       # LIN - orange
        "ETH": "#06b6d4",       # Ethernet - cyan
        "FLEX": "#f472b6",      # FlexRay - pink
        "SUP": "#f97316",       # Supply - orange
        "GND": "#94a3b8",       # Ground - slate
    }

    def __init__(self, custom_map: dict[str, str] | None = None):
        self.map = {**self.DEFAULT_MAP}
        if custom_map:
            self.map.update(custom_map)

    def get(self, io_type: str) -> str:
        """Get color for I/O type."""
        return self.map.get(io_type.upper(), "#94a3b8")


# Global color map
_COLOR_MAP = IOColorMap()


def kpi_tile(label: str, value: int | str, subtitle: str = "") -> str:
    """Generate a KPI tile."""
    return f"""<div class="kpi-tile">
  <div class="kpi-label">{esc(label)}</div>
  <div class="kpi-value">{esc(str(value))}</div>
  {f'<div class="kpi-sub">{esc(subtitle)}</div>' if subtitle else ''}
</div>"""


def kpi_row(tiles: Sequence[tuple[str, int | str, str]]) -> str:
    """Generate a row of KPI tiles."""
    tile_html = "".join(kpi_tile(l, v, s) for l, v, s in tiles)
    return f'<div class="kpi-row">{tile_html}</div>'


def io_tile(code: str, name: str, count: int) -> str:
    """Generate an I/O tile with count."""
    color = _COLOR_MAP.get(code)
    return f"""<div class="io-tile" style="--io-color:{color}">
  <div class="io-code">{esc(code)}</div>
  <div class="io-name">{esc(name)}</div>
  <div class="io-count">{count}</div>
</div>"""


def io_grid(io_demand: dict[str, int], io_names: dict[str, str] | None = None) -> str:
    """Generate a grid of I/O tiles from demand dict."""
    if not io_demand:
        return '<div class="io-empty">Aucun I/O</div>'

    tiles = []
    for code, count in sorted(io_demand.items(), key=lambda x: -x[1]):
        name = (io_names or {}).get(code, code) if io_names else code
        tiles.append(io_tile(code, name, count))

    return f'<div class="io-grid">{"".join(tiles)}</div>'


def bar_chart(data: dict[str, int], labels: dict[str, str] | None = None) -> str:
    """Generate a bar chart from data."""
    if not data:
        return '<div class="bar-empty">Pas de données</div>'

    max_val = max(data.values()) if data.values() else 1
    bars = []

    for code, val in sorted(data.items(), key=lambda x: -x[1]):
        pct = (val / max_val * 100) if max_val > 0 else 0
        label = (labels or {}).get(code, code) if labels else code
        color = _COLOR_MAP.get(code)

        bars.append(f"""<div class="bar-row">
  <div class="bar-label">{esc(label)}</div>
  <div class="bar-track" style="--bar-color:{color}">
    <div class="bar-fill" style="width:{pct:.1f}%"></div>
  </div>
  <div class="bar-value">{val}</div>
</div>""")

    return f'<div class="bar-chart">{"".join(bars)}</div>'


def flow_diagram(title: str, inputs: Sequence[str], system: str,
                 outputs: Sequence[str], description: str = "") -> str:
    """Generate a Sensors → System → Actuators flow diagram."""
    input_list = "<br>".join(f"• {esc(s)}" for s in inputs) if inputs else "—"
    output_list = "<br>".join(f"• {esc(s)}" for s in outputs) if outputs else "—"

    return f"""<div class="flow-diagram">
  <div class="flow-box flow-inputs">
    <div class="flow-title">Inputs</div>
    <div class="flow-content">{input_list}</div>
  </div>
  <div class="flow-arrow">→</div>
  <div class="flow-box flow-system">
    <div class="flow-title">{esc(system)}</div>
    <div class="flow-content">{esc(description)}</div>
  </div>
  <div class="flow-arrow">→</div>
  <div class="flow-box flow-outputs">
    <div class="flow-title">Outputs</div>
    <div class="flow-content">{output_list}</div>
  </div>
</div>"""


def detail_panel(title: str, kind: str = "Object",
                 fields: dict[str, str] | None = None,
                 json_data: dict[str, Any] | None = None) -> str:
    """Generate a detail panel with key-value pairs and JSON."""
    fields = fields or {}

    kv_rows = []
    for key, val in fields.items():
        if val:
            kv_rows.append(f"""<div class="detail-kv">
  <div class="detail-key">{esc(key)}</div>
  <div class="detail-val">{esc(str(val))}</div>
</div>""")

    json_str = ""
    if json_data:
        json_str = f"""<div class="detail-json">
  <pre>{esc(json.dumps(json_data, indent=2, ensure_ascii=False))}</pre>
</div>"""

    return f"""<div class="detail-panel">
  <div class="detail-header">
    <h3>{esc(title)}</h3>
    <span class="detail-kind">{esc(kind)}</span>
  </div>
  <div class="detail-content">
    {"".join(kv_rows) if kv_rows else '<div class="detail-empty">Pas de détails</div>'}
    {json_str}
  </div>
</div>"""


def semantic_badge(text: str, io_type: str = "", size: str = "sm") -> str:
    """Generate a semantic color-coded badge."""
    color = _COLOR_MAP.get(io_type) if io_type else "#94a3b8"
    size_class = f"badge-{size}"
    return f'<span class="badge {size_class}" style="--badge-color:{color}">{esc(text)}</span>'


def legend(io_types: Sequence[str], io_names: dict[str, str] | None = None) -> str:
    """Generate a legend of I/O types."""
    if not io_types:
        return '<div class="legend-empty">Aucun type I/O</div>'

    items = []
    for io_type in sorted(io_types):
        color = _COLOR_MAP.get(io_type)
        name = (io_names or {}).get(io_type, io_type) if io_names else io_type
        items.append(f'<span class="legend-item" style="--legend-color:{color}">{esc(io_type)}</span>')

    return f'<div class="legend">{"".join(items)}</div>'


def sidebar_section(title: str, content: str, id: str = "") -> str:
    """Generate a sidebar section."""
    id_attr = f' id="{esc(id)}"' if id else ""
    return f"""<section class="sidebar-section"{id_attr}>
  <h3 class="sidebar-title">{esc(title)}</h3>
  <div class="sidebar-content">{content}</div>
</section>"""


def system_card(name: str, level: str = "", priority: str = "",
                safety: str = "", active: bool = False) -> str:
    """Generate a system selection card."""
    active_class = " active" if active else ""
    meta = f"{level} · {priority} · {safety}".replace(" · ", " · ").strip(" · ")

    return f"""<div class="system-card{active_class}">
  <div class="system-name">{esc(name)}</div>
  <div class="system-meta">{esc(meta)}</div>
</div>"""


def page_header(title: str, subtitle: str = "", badges: Sequence[str] | None = None) -> str:
    """Generate a full-width page header."""
    badge_html = ""
    if badges:
        badge_html = '<div class="header-badges">' + "".join(
            semantic_badge(b) for b in badges
        ) + "</div>"

    return f"""<header class="page-header">
  <div class="header-content">
    <div class="header-text">
      <h1>{esc(title)}</h1>
      {f'<p class="header-subtitle">{esc(subtitle)}</p>' if subtitle else ''}
    </div>
    {badge_html}
  </div>
</header>"""


def main_layout(sidebar: str, main: str, details: str = "") -> str:
    """Generate a 3-column main layout (sidebar | main | details)."""
    details_html = f'<aside class="panel-details">{details}</aside>' if details else ""
    layout_class = "main-layout with-details" if details else "main-layout"

    return f"""<div class="{layout_class}">
  <aside class="panel-sidebar">{sidebar}</aside>
  <main class="panel-main">{main}</main>
  {details_html}
</div>"""


def advanced_css() -> str:
    """Generate CSS for advanced components."""
    return r"""
/* KPI Tiles */
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }
.kpi-tile { background: var(--dark-surface3); border: 1px solid var(--dark-border1); border-radius: 16px; padding: 14px; text-align: center; position: relative; overflow: hidden; transition: all 0.2s; }
.kpi-tile::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple)); }
.kpi-tile:hover { border-color: var(--accent-cyan); transform: translateY(-2px); }
.kpi-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-dim); font-weight: 700; margin-bottom: 4px; }
.kpi-value { font-size: 28px; font-weight: 900; color: var(--accent-cyan); letter-spacing: -0.04em; }
.kpi-sub { font-size: 0.8rem; color: var(--text-fade); margin-top: 4px; }

/* I/O Grid & Tiles */
.io-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; }
.io-tile { border: 1px solid var(--dark-border1); border-radius: 12px; padding: 12px; background: rgba(23, 32, 51, 0.5); position: relative; overflow: hidden; transition: all 0.15s; cursor: pointer; }
.io-tile::after { content: ""; position: absolute; top: -20px; right: -20px; width: 60px; height: 60px; border-radius: 50%; background: var(--io-color); opacity: 0.08; }
.io-tile:hover { border-color: var(--io-color); background: rgba(23, 32, 51, 0.8); transform: translateY(-1px); }
.io-code { font-size: 13px; font-weight: 800; color: var(--io-color); }
.io-name { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.io-count { font-size: 24px; font-weight: 900; color: var(--io-color); margin-top: 6px; letter-spacing: -0.04em; }
.io-empty { padding: 20px; text-align: center; color: var(--text-fade); }

/* Bar Chart */
.bar-chart { display: grid; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 60px 1fr 40px; gap: 8px; align-items: center; }
.bar-label { font-size: 0.85rem; font-weight: 700; color: var(--text-secondary); }
.bar-track { height: 8px; background: var(--dark-border0); border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--bar-color); border-radius: 999px; transition: width 0.3s ease; }
.bar-value { font-size: 0.85rem; font-weight: 800; text-align: right; color: var(--text-primary); }
.bar-empty { padding: 20px; text-align: center; color: var(--text-fade); }

/* Flow Diagram */
.flow-diagram { display: grid; grid-template-columns: 1fr 50px 1fr 50px 1fr; gap: 8px; align-items: center; }
.flow-box { background: var(--dark-surface3); border: 1px solid var(--dark-border1); border-radius: 12px; padding: 12px; min-height: 60px; display: flex; flex-direction: column; justify-content: center; }
.flow-title { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-dim); font-weight: 800; margin-bottom: 6px; }
.flow-content { font-size: 0.85rem; line-height: 1.4; color: var(--text-secondary); }
.flow-inputs { border-left: 3px solid var(--accent-cyan); }
.flow-system { border: 1px solid var(--accent-cyan); }
.flow-outputs { border-right: 3px solid var(--accent-purple); }
.flow-arrow { text-align: center; color: var(--text-dim); font-size: 20px; font-weight: 900; }
@media(max-width: 1000px) { .flow-diagram { grid-template-columns: 1fr; } .flow-arrow { display: none; } }

/* Detail Panel */
.detail-panel { background: var(--dark-surface2); border: 1px solid var(--dark-border1); border-radius: 12px; padding: 16px; }
.detail-header { margin-bottom: 12px; }
.detail-header h3 { margin: 0; font-size: 1.1rem; font-weight: 800; color: var(--text-primary); }
.detail-kind { display: inline-block; margin-top: 4px; padding: 2px 8px; background: var(--dark-surface3); border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: var(--text-secondary); }
.detail-content { font-size: 0.85rem; }
.detail-kv { display: grid; grid-template-columns: 120px 1fr; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--dark-border0); }
.detail-kv:last-child { border-bottom: none; }
.detail-key { color: var(--text-dim); font-weight: 600; }
.detail-val { color: var(--text-primary); word-break: break-word; }
.detail-json { margin-top: 12px; background: rgba(0, 0, 0, 0.3); border-radius: 8px; padding: 10px; overflow-x: auto; }
.detail-json pre { margin: 0; font-family: 'Fira Code', monospace; font-size: 0.75rem; color: var(--accent-cyan); line-height: 1.3; }
.detail-empty { padding: 12px; text-align: center; color: var(--text-fade); }

/* Legend */
.legend { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.legend-item { display: inline-flex; align-items: center; padding: 4px 8px; background: rgba(148, 163, 184, 0.08); border: 1px solid var(--legend-color); border-radius: 6px; font-size: 0.75rem; font-weight: 700; color: var(--legend-color); }
.legend-empty { padding: 12px; text-align: center; color: var(--text-fade); }

/* Badges */
.badge { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; background: rgba(var(--badge-color-rgb), 0.12); color: var(--badge-color); border: 1px solid var(--badge-color); }
.badge-sm { padding: 3px 6px; font-size: 0.7rem; }
.badge-lg { padding: 6px 12px; font-size: 0.85rem; }

/* Sidebar & Main Layout */
.main-layout { display: grid; grid-template-columns: 320px 1fr; gap: 18px; padding: 18px; min-height: calc(100vh - 100px); }
.main-layout.with-details { grid-template-columns: 320px 1fr 350px; }
.panel-sidebar { background: linear-gradient(180deg, rgba(17, 24, 39, 0.94), rgba(15, 23, 42, 0.92)); border: 1px solid var(--dark-border1); border-radius: 16px; padding: 16px; overflow-y: auto; position: sticky; top: 18px; max-height: calc(100vh - 36px); align-self: start; }
.panel-main { background: linear-gradient(180deg, rgba(15, 23, 42, 0.68), rgba(13, 21, 36, 0.64)); border: 1px solid var(--dark-border1); border-radius: 16px; padding: 18px; overflow-y: auto; }
.panel-details { background: linear-gradient(180deg, rgba(17, 24, 39, 0.94), rgba(15, 23, 42, 0.92)); border: 1px solid var(--dark-border1); border-radius: 16px; padding: 16px; overflow-y: auto; position: sticky; top: 18px; max-height: calc(100vh - 36px); align-self: start; }

.sidebar-section { margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--dark-border0); }
.sidebar-section:last-child { border-bottom: none; margin-bottom: 0; }
.sidebar-title { margin: 0 0 10px; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); font-weight: 800; }
.sidebar-content { font-size: 0.9rem; }

.system-card { border: 1px solid var(--dark-border1); background: rgba(23, 32, 51, 0.5); border-radius: 10px; padding: 10px; margin-bottom: 8px; cursor: pointer; transition: all 0.15s; }
.system-card:hover { border-color: var(--accent-cyan); transform: translateY(-1px); }
.system-card.active { border-color: var(--accent-cyan); background: rgba(56, 189, 248, 0.1); }
.system-name { font-weight: 700; font-size: 0.9rem; color: var(--text-primary); }
.system-meta { font-size: 0.75rem; color: var(--text-dim); margin-top: 4px; }

/* Header */
.page-header { background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(13, 21, 36, 0.88)); border-bottom: 1px solid var(--dark-border1); padding: 24px 28px; position: sticky; top: 0; z-index: 20; backdrop-filter: blur(15px); }
.header-content { max-width: 1600px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; gap: 20px; }
.header-text h1 { margin: 0; font-size: 28px; letter-spacing: -0.03em; color: var(--text-primary); }
.header-subtitle { margin: 6px 0 0; color: var(--text-secondary); font-size: 0.9rem; }
.header-badges { display: flex; gap: 8px; flex-wrap: wrap; }

@media(max-width: 1200px) {
  .main-layout { grid-template-columns: 1fr; }
  .main-layout.with-details { grid-template-columns: 1fr; }
  .panel-sidebar { order: 2; position: static; max-height: none; }
  .panel-main { order: 1; }
  .panel-details { order: 3; position: static; max-height: none; }
}

@media(max-width: 900px) {
  .main-layout { grid-template-columns: 1fr; padding: 12px; }
  .io-grid { grid-template-columns: repeat(2, 1fr); }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .page-header { padding: 16px; }
  .header-content { flex-direction: column; }
}

@media(max-width: 640px) {
  .io-grid { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 50px 1fr 35px; }
  .flow-diagram { grid-template-columns: 1fr; }
}

/* Connector View — component picker */
.component-list { display: flex; flex-direction: column; gap: 6px; }
.component-item { border: 1px solid var(--dark-border1); background: rgba(23, 32, 51, 0.5); border-radius: 10px; padding: 10px 12px; cursor: pointer; transition: all 0.15s; }
.component-item:hover { border-color: var(--accent-cyan); transform: translateY(-1px); }
.component-item.active { border-color: var(--accent-cyan); background: rgba(56, 189, 248, 0.1); }
.component-item .name { font-weight: 700; font-size: 0.88rem; color: var(--text-primary); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.component-item .meta { font-size: 0.72rem; color: var(--text-dim); margin-top: 4px; }
.component-kind { display: inline-block; font-size: 0.62rem; font-weight: 800; letter-spacing: 0.05em; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }
.component-kind.ecu { background: rgba(46, 230, 255, 0.14); color: var(--accent-cyan); }
.component-kind.device { background: rgba(179, 136, 255, 0.14); color: var(--accent-purple); }
.component-empty { padding: 16px; text-align: center; color: var(--text-fade); font-size: 0.85rem; }

/* Connector View — connector cards & pin grid */
.connector-card { background: var(--dark-surface2); border: 1px solid var(--dark-border1); border-radius: 16px; padding: 18px; margin-bottom: 18px; }
.connector-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.connector-header h2 { margin: 0; font-size: 1.1rem; color: var(--text-primary); }
.connector-stats { font-size: 0.78rem; color: var(--text-dim); font-weight: 600; white-space: nowrap; }
.connector-meta { font-size: 0.78rem; color: var(--text-secondary); margin-top: 4px; }

.pin-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(88px, 1fr)); gap: 10px; }
.pin { border: 1px solid var(--dark-border1); border-radius: 10px; padding: 10px 8px; background: var(--dark-surface3); cursor: pointer; min-height: 74px; transition: all 0.15s; display: flex; flex-direction: column; gap: 4px; }
.pin:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); border-color: var(--accent-cyan); }
.pin.active { outline: 2px solid var(--accent-cyan); outline-offset: 1px; }
.pin.valid { border-color: var(--pin-status-valid); }
.pin.warning { border-color: var(--pin-status-warning); }
.pin.error { border-color: var(--pin-status-error); }
.pin.free { border-color: var(--pin-status-free); opacity: 0.55; }
.pin .pin-num { font-size: 0.68rem; font-weight: 800; color: var(--text-dim); }
.pin .pin-name { font-size: 0.72rem; font-weight: 700; color: var(--text-primary); line-height: 1.25; word-break: break-word; }
.pin .pin-tag { align-self: flex-start; font-size: 0.6rem; font-weight: 800; padding: 1px 5px; border-radius: 4px; margin-top: auto; }

.legend-pinstatus { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; font-size: 0.78rem; }
.legend-pinstatus span { display: inline-flex; align-items: center; gap: 6px; color: var(--text-dim); }
.legend-pinstatus i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }

@media(max-width: 900px) {
  .pin-grid { grid-template-columns: repeat(auto-fill, minmax(72px, 1fr)); }
}
"""

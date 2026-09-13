#!/usr/bin/env python3
"""Minimal mxGraph/draw.io XML (.drawio) builder shared by the experimental
drawio exporters (generate_drawio_exports.py).

This is intentionally independent from the HTML generators: it only needs
to produce valid <mxfile> XML that draw.io / diagrams.net (and therefore the
Polarion "Diagrams.net" widget) can open and re-edit. It does not reuse any
HTML/CSS rendering helpers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from xml.sax.saxutils import escape, quoteattr


def esc_attr(value: object) -> str:
    """Escape a value for use inside a double-quoted XML attribute."""
    return quoteattr(str("" if value is None else value))[1:-1]


def esc_text(value: object) -> str:
    return escape(str("" if value is None else value))


@dataclass
class DrawioDiagram:
    """Accumulates mxCell nodes/edges for a single diagram page and renders
    the full <mxfile> document. IDs 0 and 1 are reserved by mxGraph for the
    root layer, per the format's own convention."""

    name: str = "Page-1"
    _cells: list[str] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set)

    def _register(self, cell_id: str) -> str:
        cell_id = str(cell_id)
        if cell_id in self._ids:
            raise ValueError(f"duplicate mxCell id: {cell_id}")
        self._ids.add(cell_id)
        return cell_id

    def add_node(
        self,
        cell_id: str,
        label: str,
        x: float,
        y: float,
        w: float,
        h: float,
        style: str = "rounded=0;whiteSpace=wrap;html=1;",
        parent: str = "1",
    ) -> str:
        cid = self._register(cell_id)
        self._cells.append(
            f'<mxCell id="{esc_attr(cid)}" value="{esc_attr(label)}" '
            f'style="{esc_attr(style)}" vertex="1" parent="{esc_attr(parent)}">'
            f'<mxGeometry x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" as="geometry"/>'
            f'</mxCell>'
        )
        return cid

    def add_edge(
        self,
        cell_id: str,
        source: str,
        target: str,
        label: str = "",
        style: str = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;",
        parent: str = "1",
        entry_x: Optional[float] = None,
        entry_y: Optional[float] = None,
        exit_x: Optional[float] = None,
        exit_y: Optional[float] = None,
    ) -> str:
        cid = self._register(cell_id)
        extra = []
        if entry_x is not None:
            extra.append(f"entryX={entry_x:g};entryY={entry_y if entry_y is not None else 0:g};entryDx=0;entryDy=0;")
        if exit_x is not None:
            extra.append(f"exitX={exit_x:g};exitY={exit_y if exit_y is not None else 1:g};exitDx=0;exitDy=0;")
        full_style = style + "".join(extra)
        self._cells.append(
            f'<mxCell id="{esc_attr(cid)}" value="{esc_attr(label)}" '
            f'style="{esc_attr(full_style)}" edge="1" parent="{esc_attr(parent)}" '
            f'source="{esc_attr(source)}" target="{esc_attr(target)}">'
            f'<mxGeometry relative="1" as="geometry"/>'
            f'</mxCell>'
        )
        return cid

    def add_text(self, cell_id: str, label: str, x: float, y: float, w: float, h: float,
                 align: str = "center", font_size: int = 14, bold: bool = True, parent: str = "1") -> str:
        style = f"text;html=1;align={align};verticalAlign=middle;fontSize={font_size};" + ("fontStyle=1;" if bold else "")
        return self.add_node(cell_id, label, x, y, w, h, style=style, parent=parent)

    def to_xml(self) -> str:
        body = "".join(self._cells)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<mxfile host="EEDesignSolution" agent="generate_drawio_exports.py" version="24.0.0">\n'
            f'  <diagram id="{esc_attr(self.name)}" name="{esc_attr(self.name)}">\n'
            '    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" '
            'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1200" math="0" shadow="0">\n'
            '      <root>\n'
            '        <mxCell id="0"/>\n'
            '        <mxCell id="1" parent="0"/>\n'
            f'        {body}\n'
            '      </root>\n'
            '    </mxGraphModel>\n'
            '  </diagram>\n'
            '</mxfile>\n'
        )


# Fill/stroke pairs keyed by a normalized pin/bus interface type, reused
# across the drawio exporters so colors stay consistent with the HTML docs'
# KNOWN_IFACE_COLORS palette (kept as a separate literal copy here so this
# module has no import-time dependency on the HTML/report toolchain).
IFACE_FILL = {
    "CAN": ("#ffe6e6", "#ff5a78"),
    "LIN": ("#fff1e6", "#ff9e6e"),
    "ETHERNET": ("#e6fbf8", "#19d6c0"),
    "FLEXRAY": ("#efe6ff", "#b388ff"),
    "ISOBUS": ("#e9fff5", "#2ee6a0"),
    "ANALOG": ("#eaf3ff", "#5aa6ff"),
    "PWM": ("#fff6e6", "#ffb43d"),
    "DIGITAL": ("#e9fff5", "#2ee6a0"),
    "RESISTANCE": ("#e9fff5", "#2ee6a0"),
    "FREQUENCY": ("#fff6e6", "#ffb43d"),
    "POWER": ("#eef1f6", "#6c83a2"),
    "GROUND": ("#eceff3", "#46566e"),
    "SENSOR_SUPPLY": ("#e6fbff", "#2ee6ff"),
    "RESERVED": ("#f2f2f2", "#b3b3b3"),
}
DEFAULT_FILL = ("#f5f5f5", "#666666")


def fill_stroke_for(iface: str) -> tuple[str, str]:
    return IFACE_FILL.get(str(iface or "").upper(), DEFAULT_FILL)

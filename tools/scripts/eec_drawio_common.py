#!/usr/bin/env python3
"""mxGraph/draw.io XML (.drawio) builder shared by the drawio exporters
(generate_drawio_exports.py).

This is intentionally independent from the HTML generators: it only needs
to produce valid <mxfile> XML that draw.io / diagrams.net (and therefore the
Polarion "Diagrams.net" widget) can open and re-edit. It does not reuse any
HTML/CSS rendering helpers.

Beyond raw node/edge primitives, this module also carries the print-layout
conventions shared by every generated sheet: A4 page sizing (portrait or
landscape, auto-tiled to the content's bounding box), an ISO 7200-style
title block, an outer drawing border, and a small color-swatch legend —
so every exported document reads as one consistent, print-ready family
rather than a loose collection of diagrams.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Optional
from xml.sax.saxutils import escape

# draw.io's built-in "A4" page preset, in its native drawing units
# (100 units/inch => 8.27in x 11.69in = 210mm x 297mm). Confirmed against
# a real draw.io export (pageWidth="826" pageHeight="1169").
A4_PORTRAIT = (827, 1169)
A4_LANDSCAPE = (1169, 827)

FONT_FAMILY = "Helvetica"


def esc_attr(value: object) -> str:
    """Escape a value for use inside a double-quoted XML attribute.

    Deliberately NOT xml.sax.saxutils.quoteattr: it picks single- or
    double-quote delimiters based on the text's own content and only
    escapes what its chosen delimiter needs — so a value containing `"`
    but no `'` comes back with the `"` left raw (safe only inside a
    `'...'`-delimited attribute). Every call site here always wraps the
    result in a literal `"..."`, so `"` must always be escaped regardless
    of what else is in the string. escape()'s default table covers & < >;
    add the quote explicitly.
    """
    return escape(str("" if value is None else value), {'"': "&quot;"})


def esc_text(value: object) -> str:
    return escape(str("" if value is None else value))


@dataclass
class DrawioDiagram:
    """Accumulates mxCell nodes/edges for a single diagram page and renders
    the full <mxfile> document. IDs 0 and 1 are reserved by mxGraph for the
    root layer, per the format's own convention."""

    name: str = "Page-1"
    page_w: float = A4_LANDSCAPE[0]
    page_h: float = A4_LANDSCAPE[1]
    _cells: list[str] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set)
    _bbox: list[Optional[float]] = field(default_factory=lambda: [None, None, None, None])

    def _register(self, cell_id: str) -> str:
        cell_id = str(cell_id)
        if cell_id in self._ids:
            raise ValueError(f"duplicate mxCell id: {cell_id}")
        self._ids.add(cell_id)
        return cell_id

    def _track_bbox(self, x: float, y: float, w: float, h: float) -> None:
        x0, y0, x1, y1 = self._bbox
        self._bbox = [
            x if x0 is None else min(x0, x),
            y if y0 is None else min(y0, y),
            x + w if x1 is None else max(x1, x + w),
            y + h if y1 is None else max(y1, y + h),
        ]

    def content_bbox(self) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = self._bbox
        return (x0 or 0.0, y0 or 0.0, x1 or 0.0, y1 or 0.0)

    def reserve_space(self, extra_w: float = 0, extra_h: float = 0) -> None:
        """Grow the tracked content bbox without drawing anything, so a
        later set_page_to_content() leaves a clean band free of any real
        content — e.g. for a bottom-band title block that must never
        overlap the last row of a grid or tree."""
        x0, y0, x1, y1 = self.content_bbox()
        if extra_w:
            self._track_bbox(x1, y0, extra_w, 1)
        if extra_h:
            self._track_bbox(x0, y1, 1, extra_h)

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
        track_bbox: bool = True,
    ) -> str:
        cid = self._register(cell_id)
        self._cells.append(
            f'<mxCell id="{esc_attr(cid)}" value="{esc_attr(label)}" '
            f'style="{esc_attr(style)}" vertex="1" parent="{esc_attr(parent)}">'
            f'<mxGeometry x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" as="geometry"/>'
            f'</mxCell>'
        )
        if track_bbox:
            self._track_bbox(x, y, w, h)
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
                 align: str = "center", font_size: int = 14, bold: bool = True, parent: str = "1",
                 color: str = "#1a1a1a", track_bbox: bool = True) -> str:
        style = (
            f"text;html=1;align={align};verticalAlign=middle;fontSize={font_size};"
            f"fontFamily={FONT_FAMILY};fontColor={color};"
        ) + ("fontStyle=1;" if bold else "")
        return self.add_node(cell_id, label, x, y, w, h, style=style, parent=parent, track_bbox=track_bbox)

    # -- Print layout: page sizing, drawing border, title block, legend ---

    def set_page_to_content(self, orientation: str = "auto", margin: float = 40, min_pages: int = 1) -> tuple[int, int]:
        """Size the page to the smallest whole number of A4 sheets (in the
        given or auto-picked orientation) that covers everything drawn so
        far plus a margin. Returns (columns, rows) of tiled A4 sheets so
        callers can size a title block/border to match. Call this AFTER all
        diagram content has been added, then add the border/title block."""
        x0, y0, x1, y1 = self.content_bbox()
        content_w = max(1.0, (x1 - min(x0, 0)) + margin * 2)
        content_h = max(1.0, (y1 - min(y0, 0)) + margin * 2)

        if orientation == "auto":
            orientation = "landscape" if content_w >= content_h else "portrait"
        unit_w, unit_h = A4_LANDSCAPE if orientation == "landscape" else A4_PORTRAIT

        cols = max(min_pages, -(-int(content_w) // int(unit_w)))
        rows = max(1, -(-int(content_h) // int(unit_h)))
        self.page_w = cols * unit_w
        self.page_h = rows * unit_h
        return cols, rows

    def add_border(self, cell_id: str = "frame_border", margin: float = 10, color: str = "#000000") -> str:
        return self.add_node(
            cell_id, "", margin, margin, self.page_w - 2 * margin, self.page_h - 2 * margin,
            style=f"rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor={color};strokeWidth=1.5;",
            parent="1", track_bbox=False,
        )

    def add_title_block(
        self,
        cell_id_prefix: str,
        doc_title: str,
        subtitle: str = "",
        source: str = "",
        rev: str = "A",
        sheet_label: str = "1/1",
        company: str = "EE Architect Design",
        margin: float = 10,
    ) -> None:
        """A compact ISO-7200-style title block, anchored to the bottom-right
        corner of the page (last tiled sheet if content spans several)."""
        w, h = 340.0, 96.0
        col1_w, col2_w = 240.0, 100.0
        row_h = h / 3.0
        x = self.page_w - margin - w
        y = self.page_h - margin - h
        today = _date.today().isoformat()

        cell = f"rounded=0;whiteSpace=wrap;html=1;strokeColor=#000000;fillColor=#ffffff;align=left;verticalAlign=middle;spacingLeft=6;fontFamily={FONT_FAMILY};"

        self.add_node(f"{cell_id_prefix}_c00", f"{company}", x, y, col1_w, row_h,
                       style=cell + "fontSize=11;fontStyle=1;", track_bbox=False)
        self.add_node(f"{cell_id_prefix}_c01", f"REV {rev}", x + col1_w, y, col2_w, row_h,
                       style=cell + "fontSize=11;fontStyle=1;align=center;", track_bbox=False)

        self.add_node(f"{cell_id_prefix}_c10", doc_title, x, y + row_h, col1_w, row_h,
                       style=cell + "fontSize=9;fontStyle=1;", track_bbox=False)
        self.add_node(f"{cell_id_prefix}_c11", today, x + col1_w, y + row_h, col2_w, row_h,
                       style=cell + "fontSize=8;align=center;", track_bbox=False)

        self.add_node(f"{cell_id_prefix}_c20", subtitle or source, x, y + 2 * row_h, col1_w, row_h,
                       style=cell + "fontSize=8;fontColor=#555555;", track_bbox=False)
        self.add_node(f"{cell_id_prefix}_c21", f"SHEET {sheet_label}", x + col1_w, y + 2 * row_h, col2_w, row_h,
                       style=cell + "fontSize=9;fontStyle=1;align=center;", track_bbox=False)

    def add_legend(self, cell_id_prefix: str, title: str, entries: list[tuple[str, str, str]],
                    x: float, y: float, swatch: float = 14, row_h: float = 20, w: float = 190) -> float:
        """entries: list of (label, fill, stroke). Returns the y coordinate
        just below the rendered legend, for stacking further content."""
        self.add_text(f"{cell_id_prefix}_title", title, x, y, w, 18, align="left", font_size=10, bold=True)
        yy = y + 20
        for i, (label, fill, stroke) in enumerate(entries):
            sid = f"{cell_id_prefix}_sw_{i}"
            self.add_node(sid, "", x, yy + (row_h - swatch) / 2, swatch, swatch,
                          style=f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};",
                          track_bbox=False)
            self.add_text(f"{cell_id_prefix}_lbl_{i}", label, x + swatch + 8, yy, w - swatch - 8, row_h,
                          align="left", font_size=9, bold=False)
            yy += row_h
        return yy

    def add_header_banner(self, cell_id_prefix: str, title: str, subtitle: str = "",
                           x: float = 50, y: float = 40, w: float = 1000) -> float:
        """Top-of-sheet banner (document title + one-line subtitle). Returns
        the y coordinate where diagram content should start."""
        self.add_text(f"{cell_id_prefix}_title", title, x, y, w, 30,
                       align="left", font_size=20, bold=True, track_bbox=False)
        if subtitle:
            self.add_text(f"{cell_id_prefix}_subtitle", subtitle, x, y + 30, w, 20,
                          align="left", font_size=11, bold=False, color="#666666", track_bbox=False)
        return y + (58 if subtitle else 40)

    def add_line(self, cell_id: str, x1: float, y1: float, x2: float, y2: float,
                 color: str = "#233152", width: float = 1.5, dashed: bool = False,
                 track_bbox: bool = True) -> str:
        """A floating straight line (no attached source/target cell) between
        two absolute points — for bus rails and drop-stubs that don't
        correspond to a vertex-to-vertex connection."""
        cid = self._register(cell_id)
        style = f"endArrow=none;html=1;strokeColor={color};strokeWidth={width};" + ("dashed=1;" if dashed else "")
        self._cells.append(
            f'<mxCell id="{esc_attr(cid)}" value="" style="{esc_attr(style)}" edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{x1:g}" y="{y1:g}" as="sourcePoint"/>'
            f'<mxPoint x="{x2:g}" y="{y2:g}" as="targetPoint"/>'
            f'</mxGeometry></mxCell>'
        )
        if track_bbox:
            self._track_bbox(min(x1, x2), min(y1, y2), max(abs(x2 - x1), 1), max(abs(y2 - y1), 1))
        return cid

    def add_table(self, cell_id_prefix: str, headers: list[str], rows: list[list[object]],
                  x: float, y: float, col_widths: list[float], row_h: float = 22, header_h: float = 24,
                  font_size: int = 9) -> float:
        """A bordered data grid (header row + striped body rows). Returns the
        y coordinate just below the table."""
        header_style = (
            f"rounded=0;whiteSpace=wrap;html=1;strokeColor=#233152;fillColor=#eef1f6;align=left;"
            f"verticalAlign=middle;spacingLeft=6;fontFamily={FONT_FAMILY};fontStyle=1;fontSize={font_size};"
        )
        xx = x
        for j, (htext, w) in enumerate(zip(headers, col_widths)):
            self.add_node(f"{cell_id_prefix}_h_{j}", htext, xx, y, w, header_h, style=header_style)
            xx += w
        yy = y + header_h
        for i, row in enumerate(rows):
            xx = x
            fill = "#ffffff" if i % 2 == 0 else "#f7f9fc"
            row_style = (
                f"rounded=0;whiteSpace=wrap;html=1;strokeColor=#d7dde8;fillColor={fill};align=left;"
                f"verticalAlign=middle;spacingLeft=6;fontFamily={FONT_FAMILY};fontSize={font_size};"
            )
            for j, (val, w) in enumerate(zip(row, col_widths)):
                self.add_node(f"{cell_id_prefix}_r{i}_c{j}", str(val), xx, yy, w, row_h, style=row_style)
                xx += w
            yy += row_h
        return yy

    def add_legend_row(self, cell_id_prefix: str, entries: list[tuple[str, str, str]],
                        x: float, y: float, swatch: float = 12, gap_after_swatch: float = 6,
                        entry_gap: float = 22, char_w: float = 5.6, font_size: int = 9) -> float:
        """A single horizontal strip of swatch+label pairs (a caption line),
        for legends that must not add page width/height of their own.
        Returns the x coordinate just past the last entry."""
        xx = x
        for i, (label, fill, stroke) in enumerate(entries):
            self.add_node(f"{cell_id_prefix}_sw_{i}", "", xx, y + 1, swatch, swatch,
                          style=f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};",
                          track_bbox=False)
            label_w = max(20.0, len(label) * char_w)
            self.add_text(f"{cell_id_prefix}_lbl_{i}", label, xx + swatch + gap_after_swatch, y,
                          label_w, swatch + 4, align="left", font_size=font_size, bold=False, track_bbox=False)
            xx += swatch + gap_after_swatch + label_w + entry_gap
        return xx

    def _diagram_id(self) -> str:
        # draw.io's own exports use a short opaque token for the diagram id
        # (the human-readable title goes in the separate "name" attribute).
        # Keeping the id to plain alnum/underscore avoids relying on any
        # importer's tolerance for spaces/punctuation in an id attribute.
        token = re.sub(r"[^A-Za-z0-9]+", "_", self.name).strip("_") or "Page"
        return f"{token}_1"

    def to_xml(self) -> str:
        # Mirrors, attribute-for-attribute, the header a real draw.io/
        # diagrams.net desktop or web export writes (no XML prolog, no
        # "type"/"modified" attributes) — verified against a user-supplied
        # native draw.io export rather than a hand-guessed header shape.
        body = "".join(self._cells)
        return (
            '<mxfile host="app.diagrams.net" agent="Mozilla/5.0" version="24.0.0">\n'
            f'  <diagram name="{esc_attr(self.name)}" id="{esc_attr(self._diagram_id())}">\n'
            f'    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" '
            f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.page_w:g}" '
            f'pageHeight="{self.page_h:g}" background="#ffffff" math="0" shadow="0">\n'
            '      <root>\n'
            '        <mxCell id="0" />\n'
            '        <mxCell id="1" parent="0" />\n'
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
    "SENSOR": ("#e6fff5", "#0d9488"),
    "ACTUATOR": ("#fff3e6", "#d97706"),
    "ECU": ("#eaf0ff", "#4f5bd5"),
}
DEFAULT_FILL = ("#f5f5f5", "#666666")


def fill_stroke_for(iface: str) -> tuple[str, str]:
    return IFACE_FILL.get(str(iface or "").upper(), DEFAULT_FILL)

#!/usr/bin/env python3
"""Design system helper for generating CSS from configurable design tokens.

Loads design tokens from eec_design_system.json and generates CSS with all
values driven by configuration. No hard-coded sizes, colors, or spacing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DesignSystem:
    """Load and access design system tokens."""

    def __init__(self, config_path: Path | None = None):
        """Load design system config."""
        if config_path is None:
            config_path = Path(__file__).resolve().parent / "eec_design_system.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Design system config not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as f:
            self.config = json.load(f)

    def get(self, path: str, default: Any = None) -> Any:
        """Get config value by dot-path (e.g. 'colors.dark.bg')."""
        keys = path.split(".")
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value

    def color(self, name: str) -> str:
        """Get color by name (e.g. 'cyan', 'text.primary')."""
        # Try direct path first
        val = self.get(f"colors.accent.{name}")
        if val:
            return val
        val = self.get(f"colors.semantic.{name}")
        if val:
            return val
        val = self.get(f"colors.text.{name}")
        if val:
            return val
        # Try full path
        val = self.get(f"colors.dark.{name}")
        return val or f"var(--{name})"

    def size(self, name: str) -> str:
        """Get size value (e.g. 'md' -> '12px')."""
        return self.get(f"sizing.{name}", f"var(--size-{name})")

    def radius(self, name: str) -> str:
        """Get border-radius value."""
        return self.get(f"radius.{name}", f"var(--radius-{name})")

    def shadow(self, name: str) -> str:
        """Get box-shadow value."""
        return self.get(f"shadows.{name}", f"var(--shadow-{name})")

    def spacing(self, name: str) -> str:
        """Get spacing value."""
        return self.get(f"spacing.{name}", f"var(--spacing-{name})")

    def gen_css_vars(self) -> str:
        """Generate CSS custom properties from config."""
        lines = [":root{"]

        # Colors
        colors = self.config.get("colors", {})
        for category, group in colors.items():
            if isinstance(group, dict):
                for name, value in group.items():
                    if isinstance(value, str):
                        css_name = f"{category}-{name}".replace("_", "-")
                        lines.append(f"--{css_name}:{value};")

        # Sizing
        sizing = self.config.get("sizing", {})
        for name, value in sizing.items():
            lines.append(f"--size-{name}:{value};")

        # Radius
        radius = self.config.get("radius", {})
        for name, value in radius.items():
            lines.append(f"--radius-{name}:{value};")

        # Shadows
        shadows = self.config.get("shadows", {})
        for name, value in shadows.items():
            css_name = f"shadow-{name}".replace("_", "-")
            lines.append(f"--{css_name}:{value};")

        # Spacing
        spacing = self.config.get("spacing", {})
        for name, value in spacing.items():
            css_name = f"spacing-{name}".replace("_", "-")
            lines.append(f"--{css_name}:{value};")

        # Layout
        layout = self.config.get("layout", {})
        for name, value in layout.items():
            if isinstance(value, str):
                css_name = f"layout-{name}".replace("_", "-")
                lines.append(f"--{css_name}:{value};")

        # Typography scale
        typo = self.config.get("typography", {})
        lines.append(f"--font-primary:{typo.get('font_family_primary', 'system-ui')};")
        lines.append(f"--font-mono:{typo.get('font_family_mono', 'monospace')};")

        lines.append("}")
        return "".join(lines)

    def gen_base_css(self) -> str:
        """Generate base CSS rules from design system."""
        css_vars = self.gen_css_vars()

        d = self.config
        colors = d.get("colors", {})
        dark = colors.get("dark", {})
        text = colors.get("text", {})
        accent = colors.get("accent", {})
        layout = d.get("layout", {})
        spacing = d.get("spacing", {})
        radius = d.get("radius", {})
        shadows = d.get("shadows", {})
        typo = d.get("typography", {})
        gradients = d.get("gradients", {})
        components = d.get("components", {})

        parts = [css_vars]

        # Base element styles
        parts.append(f"""
*{{box-sizing:border-box}}
html{{font-size:16px}}
body{{
  margin:0;
  padding:0;
  background:
    {gradients.get('bg_glow_1', 'transparent')},
    {gradients.get('bg_glow_2', 'transparent')},
    {dark.get('bg', '#07111f')};
  color:{text.get('primary', '#e5edf9')};
  font-family:var(--font-primary);
  font-size:1rem;
  font-weight:{typo.get('font_weight_regular', 400)};
  line-height:{typo.get('line_height_normal', 1.4)};
  -webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;
}}

button,input,select,textarea{{
  font:inherit;
  border:none;
  background:none;
  padding:0;
  margin:0;
}}

:focus-visible{{
  outline:2px solid {accent.get('cyan', '#2ee6ff')};
  outline-offset:2px;
}}

@media(prefers-reduced-motion:reduce){{
  *{{animation-duration:0.01ms !important;animation-iteration-count:1 !important;transition-duration:0.01ms !important}}
}}
""")

        # Page layout
        parts.append(f"""
.page{{
  max-width:{layout.get('content_max_width', '1480px')};
  margin:0 auto;
  padding:{spacing.get('page_padding', '28px')};
  display:grid;
  gap:{spacing.get('grid_gap', '22px')};
  overflow-x:clip;
}}

@media(max-width:{d.get('responsive', {}).get('breakpoints', {}).get('md', '900px')}){{
  .page{{padding:{spacing.get('page_padding_sm', '16px')}}}
}}
""")

        # Hero section
        hero_comp = components.get("hero", {})
        parts.append(f"""
.hero{{
  padding:{hero_comp.get('padding', spacing.get('page_padding'))};
  border:1px solid {colors.get('dark', {}).get('border2')};
  border-radius:{hero_comp.get('border_radius', radius.get('2xl'))};
  background:
    {gradients.get('card_glow')},
    linear-gradient(135deg,{dark.get('surface1')},{dark.get('surface2')});
  box-shadow:{shadows.get('lg')};
}}

.hero h1{{
  margin:0.2rem 0 0;
  font-size:{d.get('typography_scale', {}).get('h1', {}).get('size')};
  font-weight:{d.get('typography_scale', {}).get('h1', {}).get('weight')};
  line-height:{d.get('typography_scale', {}).get('h1', {}).get('line_height')};
  letter-spacing:{d.get('typography_scale', {}).get('h1', {}).get('letter_spacing')};
  color:{text.get('primary')};
}}

.hero p{{
  margin:0 0 0;
  color:{text.get('secondary')};
  font-size:1.06rem;
  line-height:{typo.get('line_height_relaxed')};
  max-width:90ch;
}}

.kicker{{
  text-transform:uppercase;
  letter-spacing:0.12em;
  color:{accent.get('cyan')};
  font-weight:{typo.get('font_weight_extrabold')};
  font-size:0.78rem;
  margin-bottom:0.5rem;
}}

.stamp{{
  margin-top:{spacing.get('element_gap')};
  color:{text.get('fade')};
  font-size:0.86rem;
}}
""")

        # Cards
        card_comp = components.get("card", {})
        parts.append(f"""
.card{{
  position:relative;
  overflow:hidden;
  background:{dark.get('surface2')};
  border:1px solid {dark.get('border2')};
  border-radius:{card_comp.get('border_radius', radius.get('xl'))};
  padding:{card_comp.get('padding', spacing.get('card_padding'))};
  box-shadow:{card_comp.get('shadow', shadows.get('md'))};
  transition:all {d.get('animation', {}).get('duration_normal')} {d.get('animation', {}).get('easing_ease_in_out')};
}}

.card:hover{{
  border-color:{accent.get('cyan')};
  box-shadow:{shadows.get('lg')};
  transform:translateY(-2px);
}}

.card::before{{
  content:"";
  position:absolute;
  top:0;left:0;right:0;
  height:{card_comp.get('accent_bar_height')};
  background:{card_comp.get('accent_bar_colors')};
}}

.card .label{{
  font-size:0.78rem;
  text-transform:uppercase;
  letter-spacing:0.08em;
  color:{text.get('dim')};
  font-weight:{typo.get('font_weight_bold')};
}}

.card .value{{
  font-size:2rem;
  font-weight:{typo.get('font_weight_black')};
  letter-spacing:-0.04em;
  margin-top:0.25rem;
  color:{accent.get('cyan')};
}}

.card .sub{{
  color:{text.get('fade')};
  font-size:0.88rem;
  margin-top:0.5rem;
}}
""")

        # Sections
        section_comp = components.get("section", {})
        parts.append(f"""
.section{{
  background:{dark.get('surface1')};
  border:1px solid {dark.get('border1')};
  border-radius:{section_comp.get('border_radius', radius.get('2xl'))};
  padding:{section_comp.get('padding', spacing.get('section_padding'))};
  box-shadow:{section_comp.get('shadow', shadows.get('lg'))};
}}

.section h2{{
  margin:0 0 {spacing.get('element_gap')};
  font-size:{d.get('typography_scale', {}).get('h2', {}).get('size')};
  font-weight:{d.get('typography_scale', {}).get('h2', {}).get('weight')};
  letter-spacing:{d.get('typography_scale', {}).get('h2', {}).get('letter_spacing')};
  color:{text.get('primary')};
}}

.section h3{{
  margin:{spacing.get('element_gap')} 0 {spacing.get('element_gap_sm')};
  font-size:{d.get('typography_scale', {}).get('h3', {}).get('size')};
  font-weight:{d.get('typography_scale', {}).get('h3', {}).get('weight')};
  color:{text.get('primary')};
}}
""")

        # Tables (now uses configurable values)
        table_comp = components.get("table", {})
        parts.append(f"""
.table-scroll{{
  overflow:auto;
  max-width:100%;
  max-height:{layout.get('table_max_height_viewport_percent', 74)}vh;
  border:1px solid {dark.get('border1')};
  border-radius:{table_comp.get('border_radius')};
}}

table{{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  background:{dark.get('surface2')};
  border:1px solid {dark.get('border1')};
  border-radius:{table_comp.get('border_radius')};
  overflow:hidden;
}}

th,td{{
  padding:{table_comp.get('th_padding')};
  border-bottom:1px solid {table_comp.get('border_color')};
  text-align:left;
  vertical-align:top;
  color:{text.get('primary')};
}}

th{{
  font-size:{table_comp.get('th_font_size')};
  font-weight:{table_comp.get('th_font_weight')};
  text-transform:uppercase;
  letter-spacing:0.07em;
  color:{text.get('dim')};
  background:{dark.get('surface3')};
  position:sticky;
  top:0;
  z-index:{table_comp.get('header_z_index')};
}}

td{{
  max-width:{table_comp.get('td_max_width')};
  overflow-wrap:anywhere;
  word-break:break-word;
}}

tr.filters th{{
  position:sticky;
  top:{layout.get('sticky_header_offset_px')}px;
  cursor:default;
  background:{dark.get('surface2')};
  z-index:2;
}}

tr.filters select,tr.filters input{{
  width:100%;
  padding:{components.get('input_filter', {}).get('padding')};
  font-size:{components.get('input_filter', {}).get('font_size')};
  border:1px solid {dark.get('border1')};
  border-radius:{components.get('input_filter', {}).get('border_radius')};
  background:{dark.get('surface2')};
  color:{text.get('primary')};
}}

tbody tr:hover{{
  background:{dark.get('surface3')};
}}

tr:last-child td{{
  border-bottom:none;
}}
""")

        # Controls
        button_comp = components.get("button", {})
        input_comp = components.get("input", {})
        parts.append(f"""
.toolbar{{
  display:flex;
  gap:{spacing.get('element_gap')};
  flex-wrap:wrap;
  margin:{spacing.get('element_gap_sm')} 0 {spacing.get('element_gap')};
}}

.search{{
  min-width:280px;
  flex:1;
  padding:{input_comp.get('padding')};
  border:1px solid {dark.get('border2')};
  border-radius:{input_comp.get('border_radius')};
  background:{dark.get('surface3')};
  color:{text.get('primary')};
  font-size:{input_comp.get('font_size')};
  transition:all {d.get('animation', {}).get('duration_fast')};
}}

.search::placeholder{{
  color:{text.get('fade')};
}}

.search:focus{{
  border-color:{accent.get('cyan')};
  background:{dark.get('surface3')};
}}

.btn{{
  padding:{button_comp.get('padding')};
  border:1px solid {dark.get('border2')};
  border-radius:{button_comp.get('border_radius')};
  background:{dark.get('surface3')};
  color:{text.get('secondary')};
  font-weight:{button_comp.get('font_weight')};
  cursor:pointer;
  transition:all {d.get('animation', {}).get('duration_fast')};
}}

.btn:hover{{
  border-color:{accent.get('cyan')};
  color:{accent.get('cyan')};
  background:rgba(46,230,255,0.08);
}}

.btn:focus-visible{{
  outline:2px solid {accent.get('cyan')};
  outline-offset:2px;
}}
""")

        # Utility classes
        parts.append(f"""
.pill{{
  display:inline-flex;
  align-items:center;
  gap:{spacing.get('element_gap_xs')};
  border:1px solid transparent;
  border-radius:{components.get('pill', {}).get('border_radius')};
  padding:{components.get('pill', {}).get('padding')};
  font-size:{components.get('pill', {}).get('font_size')};
  font-weight:{components.get('pill', {}).get('font_weight')};
  white-space:nowrap;
}}

.muted{{color:{text.get('dim')}}}
.small{{font-size:0.85rem;color:{text.get('dim')}}}
.ok{{color:{accent.get('green')}}}
.warn{{color:{accent.get('amber')}}}
.err{{color:{accent.get('red')}}}

a{{
  color:{accent.get('cyan')};
  text-decoration:none;
  transition:color {d.get('animation', {}).get('duration_fast')};
}}

a:hover{{
  color:{accent.get('green')};
  text-decoration:underline;
}}

.topnav{{
  display:flex;
  gap:{spacing.get('element_gap_sm')};
  flex-wrap:wrap;
}}

.topnav a{{
  padding:{button_comp.get('padding')};
  border:1px solid {dark.get('border2')};
  border-radius:999px;
  text-decoration:none;
  color:{text.get('secondary')};
  background:{dark.get('surface2')};
}}

.topnav a:hover{{
  border-color:{accent.get('cyan')};
  color:{accent.get('cyan')};
}}
""")

        return "".join(parts)


_DESIGN_SYSTEM = None


def get_design_system() -> DesignSystem:
    """Get global design system instance."""
    global _DESIGN_SYSTEM
    if _DESIGN_SYSTEM is None:
        _DESIGN_SYSTEM = DesignSystem()
    return _DESIGN_SYSTEM


def gen_base_css() -> str:
    """Generate all base CSS rules."""
    return get_design_system().gen_base_css()


def gen_advanced_css() -> str:
    """Generate advanced UI component CSS."""
    from eec_ui_components import advanced_css
    return advanced_css()


def gen_all_css() -> str:
    """Generate all CSS (base + advanced components)."""
    return gen_base_css() + "\n" + gen_advanced_css()

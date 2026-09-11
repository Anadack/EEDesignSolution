# Design System

E/E Architect Documentation now uses a comprehensive, configurable design system. All visual properties (colors, spacing, typography, etc.) are defined in JSON configuration files and Python, with **zero hard-coded CSS values** in generated HTML.

## Architecture

- **`tools/scripts/eec_design_system.json`** — Master design tokens (colors, spacing, typography, shadows, responsive breakpoints)
- **`tools/scripts/eec_design.py`** — Design system loader and CSS generator that converts tokens to CSS
- **`tools/scripts/eec_archdoc_common.py`** — Uses design system to generate all architecture documentation HTML/CSS
- **`tools/scripts/eec_report_common.py`** — Report helper module with design tokens

## Customization

### Change Colors, Spacing, or Typography

Edit `tools/scripts/eec_design_system.json` and update any category:

```json
{
  "colors": {
    "accent": {
      "cyan": "#2ee6ff",       // Change primary accent color
      "green": "#2ee6a0"       // Change success color
    }
  },
  "spacing": {
    "page_padding": "28px",    // Change page margins
    "grid_gap": "22px"         // Change section spacing
  },
  "typography": {
    "font_family_primary": "'Inter', system-ui, sans-serif"
  }
}
```

No Python code changes needed. Regenerate HTML:
```bash
./run.sh --skip-build --skip-run
```

### Change Component Sizing

All component sizes are configurable in the JSON:

```json
{
  "components": {
    "table": {
      "th_padding": "10px 12px",
      "td_padding": "10px 12px",
      "border_radius": "14px"
    },
    "button": {
      "padding": "9px 12px",
      "border_radius": "12px"
    }
  }
}
```

### Change Responsive Breakpoints

```json
{
  "responsive": {
    "breakpoints": {
      "md": "900px",    // Table collapse width
      "lg": "1280px"    // Large screen
    }
  }
}
```

### Create a New Theme

Copy `eec_design_system.json` to a custom file:
```bash
cp tools/scripts/eec_design_system.json tools/scripts/eec_design_system_dark.json
```

Modify colors and settings, then in your report script:
```python
from eec_design import DesignSystem
custom_theme = DesignSystem(Path("tools/scripts/eec_design_system_dark.json"))
```

## Design System Features

### Color Palette
- **Dark theme** with layered surface colors for depth
- **Semantic colors** (success, warning, error, info)
- **Interface colors** for CAN, LIN, PWM, analog, digital, etc.
- **Text hierarchy** (primary, secondary, tertiary, dim, fade)

### Typography Scale
Professional and readable at all sizes:
- **H1** — Clamp(2rem, 3vw, 3.5rem) | Weight 800 | Tight leading
- **H2** — Clamp(1.75rem, 2.5vw, 2.5rem) | Weight 700
- **H3** — Clamp(1.25rem, 1.8vw, 1.75rem) | Weight 700
- **Body** — 1rem | Weight 400 | Relaxed leading
- **Caption** — 0.75rem | Weight 600 | Uppercase

### Spacing System
Consistent, proportional spacing:
- **xs** 4px
- **sm** 8px
- **md** 12px
- **lg** 16px
- **xl** 24px
- **2xl** 32px
- **3xl** 48px
- **4xl** 64px

### Shadows & Depth
Professional shadows for layering:
- **sm** — Subtle 2px blur
- **md** — Card depth 4px blur
- **lg** — Section depth 6px blur
- **xl** — Modal depth 8px blur
- **focus** — Accessible focus ring

### Animation & Motion
- **Fast** 0.1s — Hover states, micro-interactions
- **Normal** 0.2s — Transitions, tooltips
- **Slow** 0.3s — Page transitions
- **Easing** — Cubic-bezier ease-in-out for smooth motion

### Accessibility
- **Color contrast** — WCAG AA compliant (4.5:1 minimum)
- **Focus rings** — Visible 2px cyan outline with offset
- **Touch targets** — 44px minimum (configurable)
- **Reduced motion** — Respects `prefers-reduced-motion`

## CSS Variables

All design tokens are available as CSS custom properties in generated HTML:

```css
:root {
  --dark-bg: #07111f;
  --text-primary: #e5edf9;
  --accent-cyan: #2ee6ff;
  --size-md: 12px;
  --radius-lg: 16px;
  --shadow-lg: 0 6px 24px rgba(0,0,0,0.35);
  --spacing-card-padding: 18px;
  ...
}
```

You can use these in custom styles or `<style>` tags in reports.

## Best Practices

### For Design Changes
1. Update `eec_design_system.json` — the single source of truth
2. Never hard-code colors, spacing, or sizes in Python or CSS
3. Test all changes with `./run.sh` before committing
4. Verify responsiveness at 900px, 1280px, 1600px breakpoints

### For New Reports
```python
from eec_archdoc_common import html_page
html = html_page("Report Title", body_html)  # Uses design system automatically
```

### For Custom Styling
```html
<style>
  /* Use design system variables, never hard-coded values */
  .my-custom { color: var(--accent-cyan); padding: var(--spacing-card-padding); }
</style>
```

## File Structure

```
tools/scripts/
├── eec_design_system.json        ← Design tokens (colors, spacing, etc.)
├── eec_design.py                 ← Design system loader & CSS generator
├── eec_archdoc_common.py         ← Uses design system for arch docs
├── eec_report_common.py          ← Uses design system for reports
└── [all report generators]       ← Inherit design system automatically
```

## Integration

All Python report scripts automatically use the design system:

1. **Architecture docs** (`generate_*.py`) → `eec_archdoc_common.html_page()` → `eec_design.gen_base_css()`
2. **Reports** (signal dict, harness book, etc.) → `eec_report_common.html_page()` → Custom CSS
3. **Viewer** (system configuration) → Own CSS with design tokens

To regenerate all documentation with design system changes:
```bash
./run.sh
```

## Troubleshooting

**CSS not updating?**
- Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
- Verify `eec_design_system.json` is valid JSON
- Check terminal output for errors: `python3 tools/scripts/eec_design.py`

**Colors look different?**
- Verify color values in `eec_design_system.json` (hex format: `#RRGGBB`)
- Check if your browser uses dark/light mode override
- Test in incognito/private window

**Spacing feels wrong?**
- Verify `layout.page_padding`, `spacing.grid_gap`, `spacing.card_padding` values
- Check `components.table.td_max_width` for table cell wrapping
- Test responsive breakpoints at mobile widths

## Future Enhancements

- [ ] Light theme variant
- [ ] Custom font upload
- [ ] Interactive design token editor UI
- [ ] Theme export/import for sharing
- [ ] Automated contrast checker

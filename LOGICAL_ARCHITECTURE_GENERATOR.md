# Logical Architecture HTML Generator

**File:** `tools/scripts/generate_logical_architecture_html.py`  
**Output:** `generated_doc/architecture_html/logical_architecture.html`  
**Status:** ✅ Active and uses clean signal names

---

## Overview

The Logical Architecture generator produces an interactive three-column system view showing the relationships between sensors, system controllers, and actuators. Each system is displayed with collapsible device cards listing all connected signals with their properties (interface type, safety level, priority, value range).

**Key Features:**
- 📊 System-by-system breakdown with sensor/system/actuator columns
- 🎯 Collapsible device cards with expandable signal lists
- 🔍 Real-time filtering by interface type, safety level, and priority
- 🎨 Color-coded interface types, safety classifications, and priority levels
- 📋 Signal properties including role, range, safety, and priority
- 🖥️ Dark theme, responsive design (mobile-friendly)
- ⌚ Sticky filter bar for easy navigation
- 🏷️ Clean signal names (SYSTEM_Function_[POSITION_]TYPE format)

---

## Architecture

### Three-Column Layout

For each system, signals are organized in three columns:

**LEFT COLUMN — Sensors**
- Input devices feeding the system
- Examples: Position sensors, pressure sensors, temperature sensors
- Displays all sensor outputs and their properties

**CENTER COLUMN — System Block**
- System name and metadata
- System safety level and priority
- Counts of connected sensors and actuators

**RIGHT COLUMN — Actuators**
- Output devices controlled by the system
- Examples: Hydraulic coils, proportional valves, solenoids
- Displays all actuator control inputs and their properties

### Interactive Elements

1. **Filter Bar (Sticky Top)**
   - Filter by Interface Type (POWER, GROUND, ANALOG, DIGITAL, CAN, PWM, etc.)
   - Filter by Safety Level (QM, AgPL_A, AgPL_B, AgPL_C, AgPL_D)
   - Filter by Priority (LOW, MEDIUM, HIGH, CRITICAL)
   - Reset button to clear all filters

2. **Device Cards (Collapsible)**
   - Device name with pin count
   - Click to expand/collapse
   - Lists all signals connected to device
   - Shows only signals matching active filters

3. **Signal Rows**
   - Interface type pill (colored badge)
   - Signal name (using clean standardized name)
   - Role badge (INPUT, OUTPUT, SUPPLY, GROUND, INOUT)
   - Value range badge (e.g., "9 - 36 VOLT")
   - Safety level badge (color-coded)
   - Priority badge (color-coded)

---

## Data Structure

The generator embeds a JSON data structure containing:

```javascript
{
  "arch_name": "EE_Architecture",
  "systems": [
    {
      "name": "HYDAC_Selected_Sensor_Examples",
      "safety": "QM",
      "priority": "MEDIUM",
      "sl": "SL1",
      "take_rate": 0.0,
      "mandatory": false,
      "location": "",
      "pn": "",
      "sensors": [
        {
          "name": "HYDAC_HAT1200_Angle_Analogue_4_20mA_3Pin_MappingReady",
          "signals": [
            {
              "name": "HAT1200_SUPPLY_9_36V",
              "iface": "POWER",
              "role": "SUPPLY",
              "safety": "AGPL_B",
              "priority": "MEDIUM",
              "range": "9 - 36 VOLT"
            },
            // ... more signals
          ],
          "count": 3
        }
        // ... more devices
      ],
      "actuators": [
        // ... actuator devices
      ]
    }
    // ... more systems
  ],
  "iface_list": ["ANALOG", "CAN", "CURRENT", "DIGITAL", "GROUND", "POWER", "PWM"],
  "safety_list": ["QM", "AGPL_B"],
  "prio_list": ["MEDIUM", "HIGH"],
  "iface_colors": { /* color map */ },
  "safety_colors": { /* color map */ },
  "priority_colors": { /* color map */ },
  "kpi": {
    "systems": 4,
    "devices": 21,
    "signals": 74,
    "ifaces": 7
  }
}
```

---

## Signal Names

The generator now uses **clean standardized signal names** when available.

**Format:** `SYSTEM_Function_[POSITION_]TYPE`

**Example Transformations:**
| Original Name | Clean Name | System | Function | Position | Type |
|---|---|---|---|---|---|
| HAT1200_Angle_4_20mA | HYDD_Angle_AI | HYDD | Angle | — | AI |
| EDS410_OUT1_PNP | HYDD_Switch01_SWT | HYDD | Switch | 01 | SWT |
| DirCoilCmd_HS | BRK_CoilDir_CMD | BRK | CoilDir | — | CMD |
| elobau_424C_CAN_H | ELB_Inclination_CAN | ELB | Inclination | — | CAN |

**Benefits:**
- ✅ Consistent naming across all documentation
- ✅ Clear system, function, and type identification
- ✅ Graceful fallback to original names when clean name unavailable
- ✅ Full traceability with original names in JSON exports

---

## Python Script Details

### Module: `generate_logical_architecture_html.py`

**Dependencies:**
```python
from eec_report_common import (
    collect_allocation_rows,
    esc,
    get_output_file,
    iter_device_pin_records,
    iter_devices,
    load_architecture_from_args,
    load_config,
    normalize_token,
    resolve_root,
    signal_name,           # <-- Uses updated version with clean_name support
    standard_arg_parser,
    write_text,
)
```

**Key Functions:**

#### `_build_data(arch: dict, cfg: dict) -> dict`
Extracts architecture data and builds the JSON payload for the embedded JavaScript renderer.

**Process:**
1. Iterate through all systems
2. For each system, collect sensors and actuators
3. For each device, collect signals with properties
4. Aggregate interface types, safety levels, and priorities
5. Build color maps and index lists
6. Return complete JSON structure

#### `_signal_range(sig: object) -> str`
Formats signal min/max/unit into a readable range string.

**Examples:**
- `{"min_value": 9, "max_value": 36, "unit": "VOLT"}` → `"9 - 36 VOLT"`
- `{"min": 0, "max": 100, "unit": "PERCENT"}` → `"0 - 100 PERCENT"`

#### `_fmt_number(v: object) -> str`
Formats numeric values compactly, removing unnecessary decimals.

#### Color Functions
- `IFACE_COLORS` – Maps interface types to colors
- `SAFETY_COLORS` – Maps safety levels to colors
- `PRIORITY_COLORS` – Maps priority levels to colors

**Color Scheme:**
- **Interfaces:** POWER=red, GROUND=gray, ANALOG=amber, DIGITAL=blue, CAN=cyan, PWM=violet
- **Safety:** QM=green, AgPL_A=lime, AgPL_B=yellow, AgPL_C=orange, AgPL_D=red
- **Priority:** LOW=slate, MEDIUM=blue, HIGH=amber, CRITICAL=red

### HTML Output Structure

**Head Section:**
- Meta tags (charset, viewport)
- Embedded CSS (28KB, includes design system)
- Google Fonts import (JetBrains Mono, Inter)

**Body Sections:**
1. **Site Header**
   - Architecture name and title
   - Eyebrow (product tagline)
   - Generation timestamp
   - KPI strip (4 key metrics)

2. **Filter Bar (Sticky)**
   - Interface type buttons
   - Safety level buttons
   - Priority level buttons
   - Reset button

3. **Main Content**
   - System sections (one per system)
   - Each with 3-column layout
   - Collapsible device cards
   - Signal rows with badges

4. **Footer**
   - Generation info and timestamp

### JavaScript Runtime

The embedded JavaScript handles:
- **DOM Construction** – Creates filter buttons, device cards, signal rows from data
- **Filtering** – Real-time filtering on interface, safety, priority
- **Interactivity** – Device card expand/collapse, filter button clicks
- **Styling** – Dynamic color application based on properties

---

## Usage

### Generate Single Report
```bash
python3 tools/scripts/generate_logical_architecture_html.py --root /path/to/project
```

### Generate All Reports (Including This One)
```bash
python3 tools/scripts/generate_all_reports.py --root /path/to/project
```

### With Custom Input
```bash
python3 tools/scripts/generate_logical_architecture_html.py \
  --root /path/to/project \
  --input /path/to/architecture.json \
  --outdir /custom/output/dir
```

---

## CSS Design System

The HTML includes a complete embedded CSS design system:

**Color Palette:**
- Background: `#0d0f14` (deep navy)
- Card: `#131720` (dark navy)
- Border: `rgba(255,255,255,.10)` (subtle light border)
- Text: `#e8ecf4` (light blue-gray)
- Muted: `#8993a8` (medium gray)

**Layout Variables:**
- Border radius: `14px` (cards), `8px` (small elements)
- Transition timing: `180ms cubic-bezier(.4,0,.2,1)` (smooth easing)
- Shadow: `0 4px 24px rgba(0,0,0,.4)` (depth)

**Responsive Breakpoints:**
- **Above 900px:** 3-column grid (sensors | system | actuators)
- **Below 900px:** Single-column stack for mobile viewing

---

## Filters

### Interface Types
- POWER / SUPPLY – Power distribution
- GROUND – Return paths and grounds
- ANALOG – Analog voltage inputs
- CURRENT – 4-20mA loop signals
- DIGITAL – Binary I/O
- PWM – Pulse-width modulation
- CAN – CAN bus network signals
- FREQUENCY – Frequency inputs
- RESISTANCE – Resistance inputs

### Safety Levels
- QM – Quality Management (not safety-critical)
- AGPL_A – Highest ASIL level
- AGPL_B – Medium-high ASIL
- AGPL_C – Medium ASIL
- AGPL_D – Lowest ASIL

### Priority Levels
- LOW – Non-critical, can be delayed
- MEDIUM – Standard priority
- HIGH – Urgent, time-sensitive
- CRITICAL – Essential, real-time required

---

## Integration with Framework

### JSON Export Integration
The generator reads the architecture JSON export:
- **Source:** `generated_doc/exports/example_architecture.json`
- **Format:** EE_Architect Design architecture export format
- **Content:** Systems, components, sensors, actuators, signals

### Signal Name Preference
The `signal_name()` function in `eec_report_common.py` now:
1. Checks for `clean_name` field first (standardized SYSTEM_Function_[POSITION_]TYPE)
2. Falls back to original `name` field if clean_name unavailable
3. Gracefully handles missing/null values

### Automatic Updates
When any signal in the architecture is imported:
1. C framework auto-generates clean signal name
2. JSON export includes both original and clean names
3. HTML generators automatically use clean names
4. No manual configuration needed

---

## Performance Characteristics

- **Generation Time:** ~1-2 seconds
- **HTML File Size:** ~500KB-1MB (depends on signal count)
- **Rendering Time:** <1 second in modern browser
- **Interactive Performance:** Smooth filtering with 100+ signals
- **Mobile Performance:** Responsive layout adapts to small screens

---

## Browser Compatibility

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile browsers (iOS Safari, Chrome Android)

**Requirements:**
- CSS Grid support
- Modern flexbox
- CSS custom properties (variables)
- ES6+ JavaScript (const, arrow functions, Set, Map)

---

## Recent Updates (v2024.06)

✅ **Clean Signal Names**
- Updated `signal_name()` function to prefer clean names
- All signals now display in SYSTEM_Function_[POSITION_]TYPE format
- Automatic fallback for signals without clean names

✅ **Improved Signal Display**
- Clean names make signals immediately recognizable
- System codes identify source domain
- Function names clarify purpose
- Type codes indicate signal classification

---

## Troubleshooting

### Missing Signals
- **Cause:** Signals not exported in architecture JSON
- **Fix:** Verify signals have interface type and role assigned

### Blank Report
- **Cause:** No systems in architecture export
- **Fix:** Load architecture with systems defined

### Filters Not Working
- **Cause:** JavaScript disabled or old browser
- **Fix:** Enable JavaScript, update browser

### Wrong Signal Names
- **Cause:** Clean names not generated during import
- **Fix:** Rebuild framework: `./run.sh`

---

## Examples

### Example 1: HYDAC Sensor System
```
SYSTEM: HYDAC_Selected_Sensor_Examples
├─ SENSORS
│  ├─ HYDAC_HAT1200_Angle (3 pins)
│  │  ├─ HAT1200_SUPPLY_9_36V (POWER)
│  │  ├─ HAT1200_0V (GROUND)
│  │  └─ HAT1200_Angle_4_20mA → HYDD_Angle_AI (CURRENT, OUTPUT)
│  └─ HYDAC_HAT3800_Angle_CANopen (5 pins)
│     ├─ CAN_VPLUS_9_36V (POWER)
│     ├─ CAN_GND (GROUND)
│     ├─ CAN_H (CAN, INOUT)
│     └─ CAN_L (CAN, INOUT)
├─ [SYSTEM BLOCK]
│  └─ 10 sensors, 0 actuators
└─ ACTUATORS
   └─ (none)
```

### Example 2: Rexroth Coil System
```
SYSTEM: Example_System_with_Bosch_Rexroth_Coil_Actuators
├─ SENSORS
│  └─ (none)
├─ [SYSTEM BLOCK]
│  └─ 0 sensors, 4 actuators
└─ ACTUATORS
   ├─ Rexroth_D36_CLASS_H_20W (2 pins)
   │  ├─ DirCoilCmd_HS → BRK_CoilDir_CMD (DIGITAL, INPUT)
   │  └─ POWER_GND (GROUND)
   └─ Rexroth_GP37_PROPORTIONAL (2 pins)
      ├─ PropCoilCurrentCmd_HS (PWM, INPUT)
      └─ POWER_GND (GROUND)
```

---

## See Also

- 📄 [Signal Naming Convention](NAMING_CONVENTION_IMPLEMENTATION_SUMMARY.md)
- 🔧 [Python Generator Infrastructure](README.md#documentation-suite)
- 📊 [Architecture HTML Reports](tools/scripts/generate_all_reports.py)
- 📋 [Architecture Export Format](generated_doc/exports/example_architecture.json)

---

**Last Updated:** 2026-06-29  
**Version:** 2.0 (with clean signal name support)  
**Status:** ✅ Active and fully integrated

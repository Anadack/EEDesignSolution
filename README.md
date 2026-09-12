# E/E Architect Design

> **A data-driven Electrical/Electronic Architecture framework for automotive and agricultural equipment.**  
> Define systems once in JSON, auto-map to ECU hardware, validate 23 architecture rules plus zone-integrity and DBC-level checks, estimate sizing, generate a full documentation suite — all from a single build command.

---

## Table of Contents

1. [What is E/E Architect Design?](#1-what-is-ee-architect-design)
2. [Architecture Overview](#2-architecture-overview)
3. [Getting Started](#3-getting-started)
4. [Component Library & Reusability](#4-component-library--reusability)
5. [Traceability](#5-traceability)
6. [Pre-Validation Engine — 23 Checks](#6-pre-validation-engine--23-checks)
7. [IO Needs & ECU Estimation](#7-io-needs--ecu-estimation)
8. [Architecture Comparison & Change Impact](#8-architecture-comparison--change-impact)
9. [Release Management](#9-release-management)
10. [Documentation & Report Suite](#10-documentation--report-suite)
11. [Versioning](#11-versioning)
12. [Bug Tracking & Issue Detection](#12-bug-tracking--issue-detection)
13. [Team Collaboration & Requirements Traceability](#13-team-collaboration--requirements-traceability)
14. [Why Solution Architects Should Use This](#14-why-solution-architects-should-use-this)
15. [Framework Directory Map](#15-framework-directory-map)
16. [Next Possible Improvements](#next-possible-improvements)

---

## 1. What is E/E Architect Design?

**E/E Architect Design** is a compiled, data-driven framework that replaces spreadsheet-based electrical architecture work with a rigorous, version-controlled, automatically validated design flow.

It spans the full architecture lifecycle:

```
System JSON library  →  C compilation  →  Verification  →  Export  →  HTML documentation
      (library/)           (src/ + inc/)      (23 rules)    (generated_doc/exports/)    (tools/scripts/)
```

At the centre is a **C11 application** that:
- Loads reusable **system** and **ECU** definitions from a JSON component library
- Runs **smart auto-mapping** — assigns device signals to physical ECU pins based on interface type, role, electrical requirements, and safety class
- Executes **23 architectural verification rules** (V1–V13, B1–B9, P1), plus zone integrity (Z1–Z3) and DBC-level checks (D1–D8) and produces a PASS/WARN/FAIL report
- Exports **architecture JSON** snapshots (logical + physical), estimation results, and text reports
- Feeds a **Python documentation pipeline** of 44 HTML generators covering bus diagrams, signal dictionaries, IO needs matrices, DFD data-flow diagrams, harness books, safety traces, change impact reports, and more

Every output is **generated from data** — no manual HTML editing. Change a system definition, rebuild, and all documents update automatically.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         JSON Source Library                         │
│  library/platform.json  ·  library/systems/*.json                   │
│  (ECU variants, sensors, actuators, coils, buses, signals)          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ loaded by
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        C11 Core Application                         │
│  src/main.c          — orchestration, platform loading              │
│  src/EEC_library.c   — JSON library import/export, batch signals    │
│  src/EEC_architecture.c — auto-mapping engine, pin assignment       │
│  src/EEC_verify.c    — 23 verification rules (V1–V13, B1–B9, P1)   │
│  src/EEC_estimation.c — 7-step ECU sizing pipeline (R1–R6 rules)   │
│  src/EEC_export.c    — JSON/text export                             │
│  src/EEC_connect.c   — bus topology management                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │ writes to
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        generated_doc/exports/                        │
│  exported_architecture.json          (full logical architecture)     │
│  exported_physical_architecture.json (pin-level physical view)       │
│  estimation_result.json              (ECU sizing recommendation)     │
│  pin_allocation_report.txt           (per-ECU utilisation summary)  │
│  verify_report.txt                   (23-rule verification result)  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ consumed by
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│             Python Documentation Suite (tools/scripts/)             │
│  44 generators sharing a common dark-theme CSS + SVG icon system   │
│  bus diagram · signal dictionary · IO needs matrix · DFD L0/L1 ·   │
│  harness connector book · safety trace · change impact · wiring …  │
└─────────────────────────────────────────────────────────────────────┘
```

### Technology choices

| Layer | Technology | Rationale |
|---|---|---|
| Core engine | C11, no external deps | Deterministic, zero-install, embeddable in CI |
| Library format | JSON | Human-readable, diff-friendly, tool-agnostic |
| Documentation | Python 3.11 + HTML | Single-file outputs; run in any browser, no server |
| CSS theme | CSS custom properties | One `base_css()` call propagates to all 44 documents |
| Icons | Inline SVG | ECU, sensor, actuator, CAN, LIN, ETH icons at any DPI |
| Bus topology | `arch["buses"]` array | Named buses + ECU node lists are the authoritative source; pin counts are never used to infer bus connectivity |

---

## 3. Getting Started

### Prerequisites

```bash
gcc >= 9    # or any C11-compatible compiler
python 3.11
```

### Build and run

```bash
# compile the framework
gcc -std=c11 -Wall -Wextra -pedantic -O2 -Iinc src/*.c -o app -lm

# run: imports library, runs auto-mapping, verifies, exports
./app
```

`./app` produces:

```
generated_doc/exports/exported_architecture.json
generated_doc/exports/exported_physical_architecture.json
generated_doc/exports/estimation_result.json
generated_doc/exports/pin_allocation_report.txt
generated_doc/exports/verify_report.txt
```

### Run the test suite

```bash
./qa/run_tests.sh
```

Builds and runs every hermetic test in `qa/` against the real engine (no mocks): naming convention, library import/export round-trips, DBC import/export round-trip, the ES3 generic-ECU pinout import, B9 busload, the DBC validator, J1939 PGN derivation (against known real SAE J1939 frame/PGN pairs), and the P1 power-budget rule. Each test links against the full `src/EEC_*.c` set and uses only `tmpfile()` / a portable temp directory, so it runs unmodified on any machine and from CI. Naming-convention-specific tests can also be run standalone with `./qa/run_naming_tests.sh`.

### Generate documentation

```bash
# all architecture HTML documents (44 files)
python tools/scripts/generate_all_architecture_docs.py --root .

# or a single document
python tools/scripts/generate_system_overview_html.py --root . --outdir generated_doc/architecture_html
```

### Create a release package

```bash
python tools/scripts/package_release.py --tag v1.0.0
# → releases/EE_Architect_Design_release_v1.0.0.zip
```

---

## 4. Component Library & Reusability

### Philosophy

Every component — sensor, actuator, coil, ECU variant — is defined **once** in JSON and referenced by a `Ref-2X` identifier. The same HYDAC pressure sensor used across 12 machine variants lives in one file. Update its electrical specs, and every architecture that references it reflects the change on next build.

### Library structure

```
library/
  platform.json              ← lists which systems belong to this platform
  systems/
    HYDAC_Example_Sensors.eec-system-1.4.json    (36 sensor signals)
    Elobau_Example_Angle_Sensors.eec-system-1.4.json  (26 signals)
    HYDAC_Example_Coils.eec-system-1.4.json      (4 coil signals)
    Bosch_Rexroth_Example_Coils.eec-system-1.4.json   (8 signals)
    BRAKE_SYSTEM.json                             (8 signals)
  ecus/
    AEC_LARGE.json    ← large controller variant  (192+ pins)
    AEC_MEDIUM.json   ← medium controller variant
    AEC_SMALL.json    ← compact controller variant
```

### System JSON anatomy

A system JSON is the atomic unit of reusability. It encodes every signal with full metadata:

```json
{
  "name": "HYDAC_Example_Sensors",
  "Ref-2X": "SYS-HYDAC-SENSOR-LIB",
  "components": [
    {
      "name": "Pressure_Sensors",
      "sensors": [
        {
          "name": "HDA4300_Pressure_4bar",
          "pins": [
            {
              "name": "OUT",
              "signal": {
                "name": "HDA4300_PRESSURE",
                "interface_type": "ANALOG",
                "unit": "BAR",
                "min": 0.0, "max": 4.0,
                "safety": "QM",
                "priority": "HIGH"
              },
              "electrical_requirement": 64
            }
          ]
        }
      ]
    }
  ]
}
```

Each signal carries:

| Field | Values | Used for |
|---|---|---|
| `interface_type` | ANALOG, DIGITAL, PWM, CAN, LIN, ETHERNET, ISOBUS, SENT, CURRENT… | Auto-mapping to compatible ECU pin |
| `electrical_requirement` | bitmask (PULLUP, PULLDOWN, HIGH_SIDE, LOW_SIDE, PUSH_PULL, CURRENT_SENSE, DIFFERENTIAL…) | Rule V8: electrical capability matching |
| `safety` | QM, AgPL_A–E | Rule V13: safety-relevant diagnostic coverage |
| `priority` | LOW, MEDIUM, HIGH, CRITICAL | Estimation R2: priority-based headroom |
| `min` / `max` / `unit` | numeric + string | Signal dictionary, range checks |
| `diagnostic_flags` | bitmask (OPEN_LOAD, SHORT_GND, SHORT_BAT, RANGE_CHECK…) | Rules V10, V13 |

### ECU library

ECU variants define physical pin matrices with:
- Connector layouts (X1, X2…) with cavity numbering
- Per-pin interface capability and electrical capability bitmask
- Pull resistor presence, voltage range, current limits
- CAN node address pools

### Reuse in `main.c`

```c
// Declare which systems belong to this architecture
EEC_platform_add_system(&platform, "SYS-HYDAC-SENSOR-LIB");
EEC_platform_add_system(&platform, "ELOBAU-ANGLE-SENSOR-CATALOG");
EEC_platform_add_system(&platform, "BRAKE_SYSTEM");

// The framework resolves Ref-2X → JSON → auto-maps all signals to ECU pins
```

### UI tools for library authoring

The `uibuilder/` directory contains browser-based GUI tools for teams who prefer a visual editor:

- **`system json generator/`** — visual system JSON authoring with live validation (`generator_v6_7_strict_c_adapter.html`)
- **`main.c generator/`** — drag-and-drop platform builder that generates `main.c` source

---

## 5. Traceability

Traceability is built into the data model at every level. A continuous chain links system requirement to physical ECU pin:

```
System definition (library JSON)
  └── Component (pressure sensors group)
        └── Device (HDA4300_Pressure_4bar)
              └── Device pin (OUT)
                    └── Signal (HDA4300_PRESSURE · ANALOG · 0–4 BAR · QM)
                          └── ECU pin (AEC_LARGE_01 · X1/23)
                                └── Bus node (Vehicle_CAN · port 1)   ← if bus-type signal
```

### Signal Dictionary

The **Signal Dictionary** (`generated_doc/architecture_html/signal_dictionary.html`) provides the complete cross-reference:

| Signal | System | Device | Interface | Unit | Min | Max | Safety | ECU | ECU Pin |
|---|---|---|---|---|---|---|---|---|---|
| HDA4300_PRESSURE | HYDAC_Sensors | HDA4300_4bar | ANALOG | BAR | 0.0 | 4.0 | QM | AEC_LARGE_01 | X1/23 |
| CAN_H | Vehicle_CAN | — | CAN | — | — | — | QM | AEC_LARGE_01 | X2/37 |

### Exported architecture JSON as trace record

`exported_architecture.json` is the canonical trace artefact. It contains every ECU, every pin, every signal, and every bus with full metadata. It is:
- **Version-controlled** in git — diff it between commits to see exactly what changed
- **Machine-readable** — feed it to DOORS, Polarion, JIRA, or any downstream tool
- **Self-contained** — a complete snapshot of the architecture at one point in time

### Safety traceability

`generate_safety_concept_trace_html.py` produces a dedicated safety trace:
- All signals classified AgPL_A–E (ISO 25119 agricultural machinery safety levels)
- Diagnostic coverage per safety-relevant signal
- Signals that are safety-relevant but lack diagnostics (V13 violations flagged)
- Ground class isolation evidence (V12)

### Requirements traceability

Structured requirement files (`REQ-ID: description`) can be pushed directly to Polarion — see [Section 13](#13-team-collaboration--requirements-traceability).

---

## 6. Pre-Validation Engine — 23 Checks

Every build executes 23 architectural rules before exporting (13 signal-level + 9 bus-level + 1 power-budget), plus two independent rule families that run at export time: zone integrity (Z1–Z3, ZONAL mode only) and DBC-level validation (D1–D8, CAN/ISOBUS buses only). This prevents design errors from reaching CAD tools, wiring harness design, or hardware procurement.

### Signal-level rules (V1–V13)

| Rule | Name | What it catches |
|---|---|---|
| V1 | Global duplicate CAN address | Two ECUs claiming the same CAN node ID across the entire architecture |
| V2 | Pin occupied / signal consistency | Pin marked occupied but no signal, or signal assigned to unoccupied pin |
| V3 | Pin identity uniqueness | Same connector + pin number used twice on the same ECU |
| V4 | Differential pair validation | CAN / ETH / LIN pin missing its H/L or P/N complement |
| V5 | Signal mapping completeness | Device signal declared but not assigned to any ECU pin |
| V6 | Duplicate signal assignment | Same signal routed to more than one ECU pin |
| V7 | Role compatibility | Device OUTPUT connected to ECU INPUT (or vice-versa) |
| V8 | Electrical capability matching | ECU pin lacks required capability (e.g. device needs HIGH_SIDE driver, ECU pin is simple GPIO) |
| V9 | Pull resistor requirement | Device needs pull-up/pull-down but no integrated pull on the assigned ECU pin |
| V10 | Diagnostics requirement coverage | Signal requires monitoring but ECU pin has no diagnostic capability flag |
| V11 | Current overload detection | Nominal + inrush current exceeds ECU pin rating |
| V12 | Ground class mixing | Signal GND and chassis GND mixed on the same pin group |
| V13 | Safety signal diagnostic | AgPL_A–E rated signal has no diagnostic monitoring configured |

### Bus-level rules (B1–B9)

| Rule | Name | What it catches |
|---|---|---|
| B1 | Bus port within ECU capacity | ECU assigned to more CAN ports than it physically has |
| B2 | ECU port not shared across buses | Same physical CAN port used on two different bus objects |
| B3 | Signal interface matches bus type | ANALOG signal assigned to a CAN bus object |
| B4 | No duplicate ECU port on same bus | Same ECU appears twice on the same bus with the same port index |
| B5 | CAN / ISOBUS node count ≤ 32 | More than 32 nodes on one segment (ISO 11898 limit) |
| B6 | Unique CAN addresses per bus | Two ECUs sharing a CAN address on the same bus |
| B7 | Bus-type signals assigned to a bus | CAN signal declared but not assigned to any bus object |
| B8 | Bus bitrate > 0 when nodes connected | Bus has connected ECUs but bitrate remains at 0 |
| B9 | CAN busload within safe utilization | Worst-case periodic traffic (ISO 11898-1 stuffed-bit estimate, summed over all messages with a non-zero cycle time) exceeds a safe fraction of the bus bitrate — `WARNING` at ≥50%, `ERROR` above 80% (the practical classic-CAN ceiling). Event-driven frames (cycle time 0) are reported separately, not summed into the load |

### Zone-level rules (Z1–Z3)

Only evaluated when the architecture uses **ZONAL** distribution mode (`arch->mode == EEC_ARCH_MODE_ZONAL`, populated from `library/zones.json` — see `EEC_ZONES` below). Run by `EEC_Verify_zones()` after buses are configured, so the connectivity check (Z3) sees real topology.

| Rule | Name | What it catches |
|---|---|---|
| Z1 | ECU in at most one zone | Same ECU assigned to two or more zones |
| Z2 | Every ECU is zoned | An ECU exists in the architecture but was never assigned to any zone |
| Z3 | Inter-zone backbone connectivity | With more than one zone, a zone has no ECU sitting on a bus shared with another zone — an **islanded zone** whose cross-zone signals cannot be routed |

To exercise ZONAL mode: `EEC_ZONES=library/zones.json ./app`.

### DBC-level validation (D1–D8)

Runs after CAN database (`.dbc`) export, once per CAN/ISOBUS bus, via `EEC_Dbc_Validate_all()`. These catch defects that Vector CANdb+ / `cantools` would reject or that silently corrupt decoding — independent of the V/B rules above, which validate the *architecture model*, not the *exported file*.

| Rule | Name | What it catches |
|---|---|---|
| D1 | Frame overflow | Signal bit range exceeds the message's DLC-derived frame width |
| D2 | Signal overlap | Two signals in the same message claim overlapping bits |
| D3 | Duplicate frame ID | Two messages on the same bus share a CAN identifier |
| D4 | Duplicate signal name | Two signals in the same message share a name |
| D5 | DLC out of range | Message DLC is 0 or greater than 8 (classic CAN) |
| D6 | Zero-length signal | A signal placement has length 0 |
| D7 | Min greater than max | Signal's engineering range has min > max |
| D8 | Node not in `BU_` | A message's transmitter or a signal's receiver ECU is not actually a node on that bus |

Output is `[DBC:<bus name>] N error(s)` per bus, printed by `./app` right after DBC export.

### Power budget (P1)

| Rule | Name | What it catches |
|---|---|---|
| P1 | Per-connector power budget | Sum of declared `nominal_current` across every device mapped onto one ECU connector exceeds that connector's aggregate current-carrying capacity, approximated as `rated_current` (A per contact) × `total_cavities` — `WARNING` at ≥80%, `ERROR` above 100% |

This is a documented simplification, not a full harness power-budget analysis: a real connector's aggregate rating is usually lower than contacts × per-contact rating (thermal derating from adjacent loaded contacts), and the check has no wire-gauge, fuse, or supply-rail-topology data (one connector can carry several independent supply rails). It still catches the concrete, common defect of piling many high-current loads (coils, lamps, motors) onto one small connector. A full per-rail/fuse budget needs wire gauge and fuse-rating fields the data model does not yet have (see `README.md` → *Next Possible Improvements*).

### Verification output

```
========================================================================
  E/E Architect Design — Architecture Verification Report
========================================================================
Name:     Imported Architecture
ECUs:     4    Systems:  5    Signals:  82    Buses:  1

  [PASS] V1  No duplicate CAN addresses across ECUs
  [PASS] V2  All occupied pins have signals, all signals on occupied pins
  WARNING:   electrical mismatch for signal X on AEC_LARGE_01 X1/83 …
  [PASS] V5-V9  All signal mappings valid (role, electrical, pull resistor)
  [PASS] B1-B9  All bus rules passed

SUMMARY:  4 check group(s) passed, 0 failed, 0 error(s)
STATUS: OK
========================================================================
[DBC:Tractor_Bus] 0 error(s).
[OK] DBC validation: no errors
```

`STATUS: OK` / `STATUS: FAIL` can be used as a CI gate.

---

## 6.5 Auto-Mapping Engine & IO Mapping Rules

### How signals are matched to ECU pins

The auto-mapping engine is the heart of the framework. Every system's device signals (from sensors, actuators, coils) must find a compatible free ECU pin. This happens in three phases: **role matching**, **interface compatibility**, and **electrical capability checking**. Only pins that pass all three gates can accept a signal.

#### Core mapping principle: role inversion

Signals are routed from a *logical device perspective* to a *physical ECU perspective*, with roles inverted:

| Device pin (logical) | Means | ECU pin (physical) | Maps to |
|---|---|---|---|
| `OUTPUT` | Sensor produces a signal | `INPUT` | ECU reads it |
| `INPUT` | Actuator receives a command | `OUTPUT` | ECU drives it |
| `INOUT` | Bus (CAN/LIN/ETH/FlexRay) | `INOUT` | Bus controller pin |
| `SUPPLY` | Power requirement | `SUPPLY` | Supply rail pin |
| `GROUND` | Return/reference | `GROUND` | Ground pin (accepts multiple connections in star topology) |
| `UNASSIGNED` | No-connect or catalogue placeholder | Any role | Ignored for mapping |

Source code: `EEC_connect.c:72-93` (`roles_are_compatible` function).

#### Interface & capability matching

Every signal carries an `interface_type` (ANALOG, DIGITAL, PWM, CAN, LIN, SENT, ETHERNET, RESISTANCE, FREQUENCY, CURRENT, FLEXRAY, POWER, GROUND). The auto-mapper converts this to a bitmask and verifies that the candidate ECU pin's `supported_capability_mask` includes that bit.

Example: A SENT sensor signal requires the pin to support SENT. If the candidate ECU pin lists its capability as `DIGITAL | SENT`, the match succeeds.

Source code: `EEC_types.c:159-177` (`EEC_Signal_InterfaceToCapability` function) and `EEC_architecture.c:791-803` (`EEC_Ecu_IsPinCompatible` function).

#### Electrical capability matching

In addition to role and interface, device pins may have `electrical_requirement` bitmasks (PULLUP, PULLDOWN, HIGH_SIDE, LOW_SIDE, PUSH_PULL, CURRENT_SENSE, VOLTAGE_IN, DIFFERENTIAL). The ECU pin must provide all required capabilities:

```
device.electrical_requirement & ~pin.electrical_capability == 0  ← valid match
```

The auto-mapper has two modes for this check:

- **Relaxed mode** (`EEC_System_connect_to_ecus`): Two-pass search — first try pins that fully satisfy the requirement, then fall back to any interface-compatible pin even if some electrical bits are missing. Non-blocking electrical mismatches are logged as `[AUTO-WARN]`.
  
- **Strict mode** (`EEC_System_connect_to_ecus_strict`): Electrical requirements are scored, not gates. A pin that fully satisfies the requirement gets `+80` points, and for each missing bit, `-25` points are applied. The highest-scoring pin wins.

Source code: `EEC_connect.c:95-164` (relaxed) and `EEC_connect.c:166-327` (strict).

#### Safety-level gates

Every signal derives a required **AgPL level** from its metadata:

- Base: `AgPL_A` (QM — quality managed)
- If `safety > QM`: `AgPL_C` (agricultural functional safety)
- If `safety > QM` AND `priority == CRITICAL`: `AgPL_D` (highest safety integrity)

The candidate ECU pin's `max_agpl` must meet or exceed the required level. In relaxed mode, under-rated pins produce a warning; in strict mode, they are skipped as incompatible.

Source code: `EEC_connect.c:132-146` (relaxed safety check) and `EEC_connect.c:195-206` (strict safety check).

#### Pin occupancy & GROUND star topology

A free ECU pin (where `is_occupied == false`) can accept a new signal. Exception: **GROUND pins** are marked occupied but remain open for multiple connections to support star grounding topology. This is enforced in `EEC_Ecu_ConnectSignalToPin` (`EEC_architecture.c:805-825`).

#### Strict mode: rule-based scoring

Strict mode adds three optional constraints via `EEC_StrictConnectPolicy_t`:

- **Preferred connector**: Filter pins to only a named connector (e.g. `required: "X1"`) — other pins are skipped.
- **Required pin function**: Filter to pins that advertise a function string (e.g. `required: "CAN_H"`).
- **Required diagnostic flags**: Filter to pins with specific diagnostic bits set (e.g. open-load detection).

Once filters pass, pins are scored on:

1. Preferred ECU bonus (+1000 if `prefer_same_ecu` is active and this is the first successful ECU)
2. Preferred connector bonus (+300 if the rule matches)
3. Pin function bonus (+200 if specified in the rule)
4. Priority bonus (CRITICAL: +100, HIGH: +60, MEDIUM: +30)
5. Safety bonus (+50 if signal is safety-related, +40 extra if pin has diagnostics)
6. Electrical fit (+80 if all requirements are met, -25 per missing capability bit)
7. Pin position bonus (+10 if physical pin number ≤ 16)

The highest-scoring pin is chosen. This makes strict mode ideal for designs with specific connector or diagnostic requirements.

Source code: `EEC_connect.c:218-300` (scoring algorithm).

#### Three mapping entry points

The framework offers three mapping functions to suit different use cases:

| Function | Entry point | Behavior |
|---|---|---|
| `EEC_System_MapToEcu()` | One system → one target ECU | Force all signals onto a specific ECU; fail if no compatible pin exists. |
| `EEC_System_connect_to_ecus()` | One system → ECU list (relaxed) | Iterate through ECUs in order; take first compatible free pin; fallback to next ECU naturally. |
| `EEC_System_connect_to_ecus_strict()` | One system → ECU list (strict) | Iterate with rule-based scoring; highest-scoring pin across all ECUs wins; skip if rules are too strict. |
| `EEC_Architecture_AutoMapAll()` | All systems → ECU list | Map each system in document order using relaxed mode. |
| `EEC_Architecture_AutoMapSmart()` | All systems → ECU list (prioritized) | Sort systems by: mandatory > take_rate > priority > AgPL > system_level > interface_diversity > pin_count. Then map in that order to ensure critical/hard systems place before easy ones. |

### Detailed documentation

A comprehensive **HTML reference** (`docs/doc_mapping_EE_ArchitectDesign.html`) documents all rules with examples, trace interpretation, and practical guidance. It includes:

- Complete role compatibility table
- Interface-to-capability mapping
- Electrical bitmask reference (8 bits: PULLUP, PULLDOWN, HIGH_SIDE, LOW_SIDE, PUSH_PULL, CURRENT_SENSE, VOLTAGE_IN, DIFFERENTIAL)
- All five mapping functions with use cases
- Strict mode policy examples (zone-aware ECU targeting, preferred connectors)
- Trace log interpretation (how to read `[AUTO]`, `[STRICT]`, `[AUTO-WARN]` outputs)
- AutoMapSmart priority scoring formula
- Practical examples: mapping a hydraulic system to a specific ECU, preferring one ECU with fallback, zone-aware multi-ECU allocation

---

## 7. IO Needs & ECU Estimation

### IO Needs Matrix

`system_overview.html` provides an **IO Needs Matrix** showing exact resource consumption per ECU:

| ECU | Variant | ANALOG | DIGITAL | PWM | SENT | CAN | LIN | ISOBUS |
|---|---|---|---|---|---|---|---|---|
| AEC_LARGE_01 | LARGE | 24 pins | 18 pins | 12 pins | 6 pins | 2 buses | 1 bus | 1 bus |
| AEC_SMALL_01 | SMALL | 8 pins | 6 pins | 4 pins | — | 1 bus | — | — |

**IO columns** = occupied pin count (each pin = one independent channel).  
**Bus columns** = number of named bus connections from `buses[]` — one connection per bus regardless of how many differential pin pairs (CAN_H / CAN_L) it uses. **No double-counting.**

### 7-step ECU Estimation Engine

When you have a system list but no ECU assignment yet, the estimation engine sizes the required hardware:

```
Step 1  Parse platform.json → resolve system Ref-2X identifiers
Step 2  Load all referenced system JSON files
Step 3  Aggregate IO demand per interface type (ANALOG_IN, DIGITAL_OUT, PWM, CAN…)
Step 4  Compute ECU variant capacities from the ECU library
Step 5  Generate homogeneous estimates (all LARGE / all MEDIUM / all SMALL)
Step 6  Apply 6 design rules for the optimised mixed-variant proposal:
           R1  Safety isolation — AgPL signals on a dedicated ECU
           R2  Priority headroom — HIGH/CRITICAL signals get 30% spare
           R3  Consolidate low-IO functions onto SMALL variant
           R4  Target 40–70% utilisation per ECU
           R5  Respect bus node count limit (≤ 32 per CAN segment)
           R6  Avoid splitting a single device across two ECUs
Step 7  Export estimation_result.json + architecture_estimation.html
```

The estimation HTML shows the recommended ECU mix with per-interface utilisation bars and a BOM cost comparison across scenarios.

By default, the engine keeps the historical SMALL/MEDIUM/LARGE comparison. To
evaluate a specific ECU from the JSON library against the same IO needs, select
it at runtime without recompiling:

```bash
EEC_ESTIMATION_ECU=library/ecus/BODAS_RC5_6_40.json ./app
```

The selected ECU identity, pin capacity per interface, required ECU count, and
utilisation are written to `estimation_result.json` under `selected_ecu`. Any
ECU using the standard library JSON schema can be selected, including BODAS and
ES3 definitions. An invalid path makes the estimation fail explicitly.

---

## 8. Architecture Comparison & Change Impact

`generate_change_impact_report_html.py` compares two architecture JSON exports — typically the baseline vs. the feature branch — and produces a structured HTML diff:

```bash
python tools/scripts/generate_change_impact_report_html.py \
  --baseline generated_doc/exports/baseline_v2_0.json \
  --input    generated_doc/exports/exported_architecture.json \
  --outdir   generated_doc/architecture_html
```

The report shows:

| Category | What is flagged |
|---|---|
| **Systems** | Added / removed functional domains |
| **ECUs** | Added / removed controllers |
| **Signals** | New sensors, removed actuators, renamed signals |
| **Allocations** | Signal moved from AEC_LARGE to AEC_MEDIUM |
| **Interface changes** | Signal changed from ANALOG to CAN |
| **Safety level changes** | QM → AgPL_B (triggers re-verification requirement) |
| **Bus topology** | New bus added, node removed, bitrate changed |

This makes iterative architecture refinement safe: commit the baseline, run the change, compare. The diff is a formal record for peer review and design approval.

---

## 9. Release Management

### Release package

```bash
python tools/scripts/package_release.py --tag v2.1.0
```

Creates `releases/EE_Architect_Design_release_v2.1.0.zip` containing all HTML documentation, JSON exports, text reports, and a `manifest.json` (file list, sizes, timestamp, tag).

### CI gate

```bash
# 1. strict build (warnings are errors)
gcc -std=c11 -Wall -Wextra -pedantic -Werror -O2 -Iinc src/*.c -o app -lm

# 2. hermetic unit tests (library/DBC round-trip, B9, DBC validator, …)
./qa/run_tests.sh

# 3. run (generates all exports + prints [DBC:*] validation lines)
./app

# 4. gate on verification status
grep "STATUS: OK" generated_doc/exports/verify_report.txt || exit 1

# 5. generate documentation (all 44 generators; --strict fails the build on
#    any skip too)
python tools/scripts/generate_all_architecture_docs.py --root . --strict

# 6. package release
python tools/scripts/package_release.py --tag ${GIT_TAG}
```

A GitHub Actions workflow enforcing all of this — strict build, `qa/run_tests.sh`, an ASan/UBSan sanitizer run in both CENTRAL and ZONAL mode, DBC round-trip validation with `cantools`, the full documentation suite in `--strict` mode, and an export-reproducibility check — runs automatically on every push/PR via `.github/workflows/ci.yml`.

### Architecture naming in exports

```c
// src/main.c — embed the version in every export
strncpy(arch.name, "My_Platform_v2_1_RC1", EEC_MAX_NAME);
```

This name propagates into every HTML document's hero section, the JSON header, the verification report, and the release package filename — making every artefact self-identifying.

---

## 10. Documentation & Report Suite

All 44 documents share the same dark design theme, CSS token system (`--bg`, `--surface0–4`, `--border0–2`, `--cyan`, `--green`, `--amber`, `--red`), SVG icon set (ECU chip, sensor, actuator, CAN, LIN, Ethernet, ISOBUS), and sortable/filterable table component.

### System-level views

| Document | What it shows |
|---|---|
| **System Overview** | ECU catalogue with icons, IO needs matrix, bus network (from `buses[]`), device catalogue, signal distribution — all in one page |
| **Bus Diagram** | Named buses from `buses[]` with ECU nodes, bitrate, signal count; never inferred from pin counts |
| **Bus Backbone** | Visual backbone with ECU cards connected to named bus lanes; JS-drawn connection lines |
| **Architecture Topology** | ECU-to-ECU connectivity graph |
| **Architecture Tree** | Full hierarchical object tree (system → device → pin → signal) |
| **Logical Architecture** | Functional domain groupings |
| **Allocation Matrix** | Signal × ECU-pin allocation grid |
| **Wiring Diagram** | Pin-level wiring connections |

### Signal & data flow views

| Document | What it shows |
|---|---|
| **Signal Flow** | Signal paths from device pin to ECU pin |
| **Signal Flow v2** | Enhanced with interface-type filtering |
| **Signal Dictionary** | Complete catalogue: signal, system, device, interface, unit, range, safety, ECU, pin |
| **DFD Level 0** | Tractor context diagram — external entities ↔ E/E architecture ↔ ECUs with sensor/actuator icons |
| **DFD Level 1** | Per-system: sensors (with icons) → system logic → ECUs (with icons) → actuators (with icons) |
| **Communication Matrix** | Which ECUs exchange which signals over which bus |

### Hardware & harness views

| Document | What it shows |
|---|---|
| **ECU Pinout (per ECU)** | Full connector pinout for each controller |
| **Library ECU Pinouts** | Pinout reference for all library ECU variants |
| **Architecture Pinouts** | All ECU pinouts stacked in one view |
| **Harness Connector Book** | Connector-by-connector harness documentation |
| **Wiring Netlist** | Net-level from/to list per signal |
| **Power Distribution** | Supply rail architecture and current budgets |
| **Grounding Architecture** | Ground class topology and isolation |

### Quality & safety views

| Document | What it shows |
|---|---|
| **Safety Concept Trace** | AgPL signal coverage, diagnostic mapping, V13 violations (ISO 25119 agricultural machinery safety) |
| **Diagnostics Matrix** | OBD/DTC coverage per signal and ECU pin |
| **Completeness Report** | Unmapped signals, incomplete pins, quality gaps |
| **Verification Report** | 23-rule pass/fail/warn (text file + embedded in overview) |

### Project & change views

| Document | What it shows |
|---|---|
| **Change Impact Report** | Diff between two architecture snapshots |
| **Architecture Estimation** | ECU sizing recommendations and BOM comparison |
| **Variant Option Matrix** | Feature/option combinations vs. ECU fit |
| **Documentation Index** | Master index linking all generated documents |

---

## 11. Versioning

### Git as architecture history

Every architecture is version-controlled through standard git workflows:

```
main              → released, validated architecture
feature/brake-sys → new system addition in progress
hotfix/can-addr   → CAN address conflict fix
```

The exported JSON files are committed alongside source code. Because the JSON is structured and deterministic, diffs are human-readable:

```bash
git diff main..HEAD -- generated_doc/exports/exported_architecture.json
# → shows exactly which signals moved, which ECU addresses changed, which buses were added
```

### Baseline / delta workflow

```bash
# 1. Save a baseline before starting a change
cp generated_doc/exports/exported_architecture.json generated_doc/exports/baseline_v2_0.json

# 2. Make changes in main.c / library JSONs, rebuild
./app

# 3. Generate change impact report
python tools/scripts/generate_change_impact_report_html.py \
  --baseline generated_doc/exports/baseline_v2_0.json --root . --outdir generated_doc/architecture_html

# 4. Review change_impact_report.html before merging
```

---

## 12. Bug Tracking & Issue Detection

### Built-in issue detection

The framework detects architectural bugs at build time, not at hardware bench or field commissioning:

| Issue type | Detected by | Output |
|---|---|---|
| Wrong pin electrical type | V8 electrical mismatch | `WARNING: electrical mismatch … device requires 0x04, ECU provides 0x43` |
| Missing signal mapping | V5 completeness | `ERROR: signal X declared but not mapped to any ECU pin` |
| CAN address conflict | V1, V6 | `ERROR: duplicate CAN address 0x71 on ECUs A and B` |
| Bus overload (>32 nodes) | B5 | `ERROR: CAN bus Vehicle_CAN has 35 nodes — exceeds ISO 11898 limit` |
| Safety signal without monitoring | V13 | `ERROR: AgPL_B signal X has no diagnostic coverage on AEC_LARGE_01 X1/23` |
| Ground class mixing | V12 | `ERROR: signal GND mixed with chassis GND on connector X1` |

### Verification as a non-regression gate

```bash
./app
grep "STATUS: OK" generated_doc/exports/verify_report.txt || exit 1
```

Every commit that touches `main.c` or any library JSON runs this gate. A previously-passing architecture that now fails means a regression was introduced — the report identifies exactly which rule failed and on which signal/ECU/pin.

### Architecture-level change tracking

The **Change Impact Report** serves as a permanent record of what changed between any two builds. Combined with git commit history, it provides a full audit trail:

- *Who* changed the architecture (git author)
- *When* (git timestamp)
- *What* changed (change_impact_report.html diff)
- *Why it's valid* (verify_report.txt STATUS: OK)

---

## 13. Team Collaboration & Requirements Traceability

### Document distribution

Every generated HTML is a **self-contained single file** — open in any browser, no server required:

| Audience | Documents |
|---|---|
| Wiring / harness engineers | `harness_connector_book.html` · `wiring_netlist.html` · `architecture_wiring_diagram.html` |
| Safety engineers | `safety_concept_trace.html` · `diagnostics_matrix.html` · `verify_report.txt` |
| System / SW engineers | `signal_dictionary.html` · `communication_matrix.html` · `dataflow_*.html` |
| ECU software teams | `allocation_matrix.html` · `architecture_bus_diagram.html` · pinout HTML files |
| Procurement | `architecture_estimation.html` (BOM sizing) |
| Project leads / reviews | `system_overview.html` · `change_impact_report.html` |

### Polarion integration

Requirements written in a lightweight structured format can be pushed directly to Polarion:

```
REQ-EE-001: All CAN buses shall operate at ≥ 250 kbit/s
Example: Vehicle CAN at 250 kbps
Why: Complies with ISO 11898-1 timing requirements for safety messages

REQ-EE-002: AgPL_B signals shall have diagnostic monitoring
Why: Required by ISO 25119 Part 4 for hardware element monitoring in agricultural machinery
```

```bash
# Push to Polarion (requires POLARION_PAT environment variable)
python tools/scripts/push_requirements_to_polarion.py \
  --file requirements/architecture_requirements.txt \
  --config .polarion_config.json \
  --project MY_PROJECT --document ArchRequirements

# Dry run — generates a standalone HTML without a Polarion connection
python tools/scripts/push_requirements_to_polarion.py \
  --file requirements/architecture_requirements.txt \
  --dry-run --out generated_doc/exports/requirements_preview.html
```

### Team configuration via JSON

All generator behaviour is controlled through `tools/scripts/eec_archdoc_config.v4.json` — no script editing needed:

```json
{
  "project_title": "My Platform Architecture",
  "bus_interfaces": ["CAN", "LIN", "ETHERNET", "ISOBUS", "FLEXRAY"],
  "excluded_bus_interfaces": ["POWER", "GROUND", "ANALOG", "PWM", "DIGITAL"],
  "default_output_dir": "generated_doc/architecture_html"
}
```

---

## 14. Why Solution Architects Should Use This

### The problem with today's E/E architecture tools

Traditional E/E architecture work is done in spreadsheets, PowerPoint, and proprietary CAD tools. The result:

- Signal lists in Excel, ECU pinouts in Visio, requirements in Word — manually kept in sync
- A change to one sensor requires updates across 6 different documents
- "Verification" means someone manually checking a spreadsheet
- No traceable path from system requirement to physical pin
- Architecture comparison between releases requires hours of manual diff work
- Hand-off to harness engineers is error-prone; wrong pin numbers cause expensive late-stage rework

### What this framework guarantees

| Capability | How it is guaranteed |
|---|---|
| **Single source of truth** | All information lives in JSON; HTML is generated, never edited manually |
| **Full traceability** | Continuous chain from system JSON → device → signal → ECU pin → bus node |
| **Pre-validation before hardware** | 23 rules catch electrical mismatches, missing diagnostics, ground mixing, bus errors at compile time |
| **Reusability** | A sensor defined once reuses across all variants; update once, all architectures update |
| **Accurate IO needs** | Bus connections from `buses[]` (not pin counts); IO channels per physical pin — no double-counting |
| **ECU estimation** | 7-step sizing engine with 6 design rules produces hardware recommendations in seconds |
| **Change management** | Architecture comparison report documents exactly what changed for design reviews |
| **Release packaging** | One command creates a dated zip with all documents and a manifest |
| **Requirements integration** | Structured requirements pushed to Polarion with a single script |
| **Version history** | Git diffs on deterministic JSON exports give exact, auditable architecture history |
| **Bug tracking** | 23 rules as a non-regression CI gate; failures identify the exact rule, signal, ECU, and pin |
| **Documentation at no cost** | 44 HTML documents auto-generated on every build — no manual authoring, no stale docs |

### Architecture maturity levels this framework supports

| Level | Description | Framework support |
|---|---|---|
| **Concept** | System list, IO demand sizing | `generate_estimation_html.py`, IO needs matrix |
| **Preliminary** | ECU assignment, bus topology | Auto-mapping, bus diagram, allocation matrix |
| **Detailed** | Pin-level harness design | Connector book, wiring netlist, pinout HTML |
| **Validated** | Compliance check | 23 verification rules, safety trace, diagnostics matrix |
| **Released** | Formal deliverable | Release package, Polarion push, change impact record |

### How a Solution Architect uses it day to day

```
1. Start a new feature (e.g. add a brake system):
   → Add BRAKE_SYSTEM.json to library/systems/
   → Reference it in main.c with EEC_platform_add_system()

2. Build and verify:
   → gcc … -o app -lm && ./app
   → grep "STATUS: OK" generated_doc/exports/verify_report.txt

3. Review impact:
   → python tools/scripts/generate_change_impact_report_html.py --baseline …
   → Open system_overview.html — IO needs changed? Bus load increased?

4. Generate full documentation:
   → python tools/scripts/generate_all_architecture_docs.py --root .

5. Distribute:
   → harness_connector_book.html → wiring team
   → signal_dictionary.html → SW teams
   → safety_concept_trace.html → safety engineer

6. Release:
   → python tools/scripts/package_release.py --tag v2.1.0
   → Attach zip to engineering change order
   → python tools/scripts/push_requirements_to_polarion.py … (optional)
```

---

## 15. Framework Directory Map

```
EE_Architect_Design/
├── src/                         C11 core application
│   ├── main.c                   Platform setup, ECU/system loading, orchestration
│   ├── EEC_architecture.c       Auto-mapping engine, pin assignment logic
│   ├── EEC_verify.c             23 verification rules (V1–V13, B1–B9, P1)
│   ├── EEC_estimation.c         7-step ECU sizing pipeline (R1–R6 rules)
│   ├── EEC_library.c            JSON library import, batch signals, connector metadata
│   ├── EEC_export.c             Architecture + estimation JSON export
│   ├── EEC_connect.c            Bus topology management
│   ├── EEC_agco.c               OEM-specific bus / connector extensions
│   └── EEC_log.c                Structured logging
│
├── inc/                         C headers (types, constants, public API)
│
├── library/                     Reusable JSON component library
│   ├── platform.json            Platform definition (Ref-2X system list)
│   └── systems/                 System JSON files (one per functional domain)
│
├── tools/
│   └── scripts/                 All Python tooling — 60+ scripts sharing common modules
│       ├── eec_archdoc_common.py  CSS theme, SVG icons, bus helpers, table/pill utilities
│       ├── eec_report_common.py   Shared helpers for the architecture-report suite
│       ├── eec_json_common.py     Shared JSON contract / workspace discovery helpers
│       ├── generate_system_overview_html.py       All-in-one overview
│       ├── generate_architecture_bus_diagram_html.py  Bus topology from buses[]
│       ├── generate_signal_dictionary_html.py     Signal catalogue + CSV
│       ├── generate_dataflow_context_diagram_html.py  DFD Level 0
│       ├── generate_dataflow_system_diagram_html.py   DFD Level 1
│       ├── generate_change_impact_report_html.py  Architecture diff
│       ├── generate_safety_concept_trace_html.py  Safety traceability
│       ├── generate_communication_matrix_html.py  Bus signal matrix
│       ├── generate_harness_connector_book_html.py  Connector-level harness docs
│       ├── generate_system_configuration_viewer_html.py  Standalone config/IO viewer
│       ├── generate_all_architecture_docs.py      Master orchestrator (doc suite)
│       ├── generate_all_reports.py                Master orchestrator (report suite)
│       ├── validate_signal_naming.py, validate_ecu_json.py, …  Validators
│       ├── push_requirements_to_polarion.py       Polarion requirements push
│       ├── package_release.py                     Release zip packager
│       ├── polarion_config.json, polarion_config.agco.json   Polarion connection configs
│       ├── legacy/                                Superseded standalone generators, kept for reference
│       └── … 40+ more generators, validators and config files
│
├── generated_doc/               All generated outputs, in one place (committed as architecture snapshot)
│   ├── exports/                 C app exports + architecture-report suite HTML
│   │   ├── exported_architecture.json
│   │   ├── exported_physical_architecture.json
│   │   ├── estimation_result.json
│   │   ├── verify_report.txt
│   │   ├── pin_allocation_report.txt
│   │   └── *.html               Allocation matrix, bus diagrams, pinouts, signal flow…
│   ├── architecture_html/       Documentation-suite HTML
│   │   ├── system_overview.html
│   │   ├── signal_dictionary.html
│   │   └── *.html               DFD, safety trace, harness book, change impact…
│   └── system_viewer/           Standalone system configuration viewer
│       ├── index.html
│       ├── system_io_matrix.csv
│       └── system_viewer_summary.json
│
├── examples/                    Reference architecture JSONs
├── templates/                   ECU pinout HTML templates
├── uibuilder/                   Browser-based GUI tools for JSON authoring
│   ├── main.c generator/        Drag-and-drop main.c code generator
│   └── system json generator/   Visual system JSON editor with live validation
├── spec/                        Architecture specification documents
├── releases/                    Release packages (gitignored)
└── .gitignore
```

---

## Next Possible Improvements

### **CAN Database & Protocol Support**

✅ **Shipped:** DBC (Vector CAN Database) export and import (`EEC_Export_dbc_bus/_all`, `EEC_Import_dbc`), CAN message packing (message ID, DLC, cycle time, per-signal start-bit/length/byte-order via `EEC_Swc_CreateMessage`/`EEC_Message_AddSignal`/`EEC_Message_AddTxPort`), Vector attribute fidelity (`GenMsgCycleTime`, `VFrameFormat=J1939PG`), and a DBC-level validator (rules D1–D8, see [Section 6](#6-pre-validation-engine--23-checks)). All exported DBCs are round-trip validated with `cantools`.

| Feature | Scope | Impact |
|---------|-------|--------|
| **J1939 PGN Assignment** | Auto-assign PGN (Parameter Group Numbers), validate PS/PF structure — the `pgn` field exists on `EEC_Message_t` but is not yet populated or checked | Full J1939 protocol support for agricultural equipment |
| **CANopen Object Dictionary** | Generate ODX / ODX.diag files, map signals to COB-IDs | Support CANopen protocol-specific message definitions |
| **ARXML (Autosar) Export** | Export system description to Autosar XML format | Standardized integration with OEM Autosar tools |

### **Signal & Interface Enhancements**

| Feature | Scope | Impact |
|---------|-------|--------|
| **LIN Scheduling** | Auto-generate LIN schedules, frame IDs, slot assignments | Complete LIN frame scheduling (currently signal-level only) |
| **Ethernet Frame Definitions** | Generate Ethernet frame headers, payload structures | Support modern high-speed communication protocols |
| **SENT Signal Validation** | Track fast/slow channels, nibble counts, CRC validation | Robust SENT protocol support |
| **FlexRay Configuration** | Generate FlexRay cycle / static / dynamic slot assignments | Safety-critical real-time communication support |
| **Signal Multiplexing** | Support multiplexed signals on same physical interface | Reduce pin/bus count for high-signal-count architectures |
| **Signal Variant Tables** | Platform/region-specific signal subsets | Support multi-variant platforms (e.g., NA vs. EU spec) |

### **Advanced Verification & Analysis**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Bandwidth Analysis (LIN / Ethernet)** | Calculate bus load per LIN/ETH message, warn on overload — CAN/ISOBUS busload is shipped as rule B9 (ISO 11898-1 worst-case estimate, see [Section 6](#6-pre-validation-engine--23-checks)) | Prevent runtime communication failures |
| **Latency & Timing Constraints** | Track signal deadlines, end-to-end latency budgets | Support real-time and safety-critical validation |
| **Power Budget Analysis (per-rail/fuse)** | Sum current per supply rail against fuse/breaker rating, harness voltage drop (needs wire gauge/length, fuse ratings, rail topology) — per-connector budget vs. contact rating × cavity count is shipped as rule P1 (see [Section 6](#6-pre-validation-engine--23-checks)) | Prevent power-delivery bottlenecks |
| **Thermal Analysis** | Estimate ECU/component dissipation, validate against limits | Prevent thermal runaway in harsh environments |
| **EMC / EMI Analysis** | Validate shielding, grounding, differential pair routing | Support compliance with automotive EMC standards |
| **Functional Safety (SOTIF)** | Track diagnostic coverage per safety level, validate fault reaction | ISO 26262 / ISO 21448 compliance traceability |
| **Cybersecurity Threat Model** | Auto-detect high-risk ECU/bus combinations, suggest mitigations | Support WP.29 / ISO 21434 security assessment |

### **Hardware & Pinout Enhancements**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Flexible Pin Numbering Schemes** | Support non-sequential/OEM-specific pin layouts | Simplify ECU pinouts with custom naming |
| **Connector Compatibility Checking** | Validate mating/keying between male/female connectors | Prevent assembly errors |
| **High-Current Power Distribution** | Model multiple power rails, return paths, current limits | Support high-power actuators / motors |
| **Ground Star Point Analysis** | Validate all returns meet at single point, calculate voltage drop | Prevent ground loops and noise coupling |
| **Cable Routing Constraints** | Track cable lengths, bend radii, environmental routing zones | Reduce design-to-production rework |
| **Splitter / Junction Box Support** | Model multi-pin harness splitters and distribution boxes | Support complex harness architectures |

### **Documentation & Reporting**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Bill of Materials (BoM)** | Auto-generate ECU / sensor / connector / cable BoM with part numbers | Direct procurement integration |
| **Harness Assembly Instructions** | Generate printable connector pin-out diagrams + assembly guides | Reduce assembly errors and support technician training |
| **Schematic Integration** | Embed auto-layout electrical schematics with live pin-to-pin traceability | One-click verification that schematic matches architecture |
| **3D Wiring Visualization** | Show ECU physical placement + harness routing in 3D | Spatial planning and interference detection |
| **Requirement Traceability Matrix (RTM)** | Link architecture → requirements → test cases → change impact | ISO 26262 / automotive compliance evidence |
| **Multilingual Reporting** | Generate documentation in English, German, French, Chinese, Japanese | Global vehicle platform support |
| **PDF Batch Export** | Generate all HTML reports as single consolidated PDF | Print-friendly documentation for OEM handbooks |

### **Testing & Quality**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Unit Test Coverage Expansion** | `qa/run_tests.sh` covers library import/export, DBC round-trip, ES3 ECU import, B9 busload, and DBC validation; extend to cover every V/B/Z/D rule individually, not just the ones with dedicated fixtures | Production-grade code stability |
| **Property-Based Testing** | Generate randomized architecture scenarios, validate rules systematically | Discover corner cases automatically |
| **Performance Benchmarking** | Track compile time, export speed, memory usage, rule evaluation time | Identify bottlenecks for 1000+ ECU architectures |
| **Regression Test Suite** | Pre-commit checks for unintended changes to verification logic | Catch breaking changes before release |
| **Integration Tests** | End-to-end tests: JSON → C compilation → export → HTML generation | Validate full pipeline for each release |

### **Integrations & Workflows**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Git Hooks & CI/CD** | Pre-commit validation, GitHub Actions / GitLab CI pipeline templates | Continuous validation on every commit |
| **IDE Plugins** | VS Code / JetBrains JSON schema validation, inline error highlighting | Faster library JSON authoring with real-time feedback |
| **Web UI for Authoring** | Browser-based architecture editor with live preview | Non-technical stakeholder access without CLI |
| **Polarion / Jira Integration** | Bi-directional sync of requirements and traceability | Integrated requirements management workflow |
| **CANoe Integration** | Auto-launch CANoe with generated .dbc, simulation configs | Streamlined CAN testing workflow |
| **MathWorks / Simulink Export** | Generate Simulink bus objects, message structures from architecture | Model-based development pipeline |
| **PSCR (Predictive Safety & Change Request)** | AI-assisted anomaly detection in architecture diffs | Highlight risky changes before review |

### **Performance & Scalability**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Multi-Architecture Workspace** | Load/compare 5–10 architecture variants in parallel | Support platform derivative analysis |
| **Incremental Build** | Only regenerate changed signals/systems, skip unchanged exports | Faster iteration on large architectures |
| **Streaming JSON Parser** | Handle 100K+ signal architectures without full memory load | Support massive platform architectures (e.g., heavy-duty trucks) |
| **Parallel Report Generation** | Run 44 generators concurrently on multi-core systems | Reduce full-build time from 30s to 5s |
| **Database Backend Option** | Replace JSON file storage with SQLite / PostgreSQL | Support cloud / SaaS deployment and concurrent team access |

### **User Experience & Accessibility**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Quick-Start Templates** | Pre-built example architectures for tractor / combine / telehandler | Reduce onboarding time for new users |
| **Interactive Tutorials** | Step-by-step guided walk-through of common workflows (add system, estimate ECU, verify rules) | Improve adoption and user satisfaction |
| **Dark/Light Theme Toggle** | User preference for HTML report styling | Accessibility for low-vision users, reduce eye strain |
| **Accessibility (WCAG 2.1 AA)** | Screen reader support, keyboard navigation, color contrast validation | Include visually impaired users and compliance audits |
| **Mobile-Responsive Reports** | Adapt HTML tables/diagrams to mobile browsers | On-site architecture review on tablets / phones |
| **Search & Filter UX** | Full-text search across all signals, systems, ECUs in reports | Faster navigation of large architectures |

### **Data & Reusability**

| Feature | Scope | Impact |
|---------|-------|--------|
| **Library Versioning & Tags** | Mark stable component versions, enforce compatibility ranges | Prevent breaking library updates on released platforms |
| **Sensor / ECU Catalog Export** | Generate public-facing product selector (like mouser.com) | Reduce barrier for non-architects to explore options |
| **Component Genealogy Tracking** | Record lineage of sensor variants, ECU generations, firmware versions | Support long-term after-sales service and part substitution |
| **Cross-Platform Part Reuse Metrics** | Analytics: which sensors appear in 50+ architectures, which are rarely used | Guide future library investments and deprecations |
| **Open Library Contribution** | Community-contributed sensors / ECUs, peer review before merge | Crowdsource library completeness |

### **Compliance & Standards**

| Feature | Scope | Impact |
|---------|-------|--------|
| **ISO 26262 Functional Safety** | Automated evidence generation (traceability, diagnostic coverage, ASIL decomposition) | Direct FMEA / FTA export for certification |
| **ISO 21434 Cybersecurity** | Threat enumeration, attack path visualization, security controls mapping | OEM cyber risk management |
| **ASPICE Process Compliance** | Automated work product evidence collection (requirements, design, verification) | Simplify automotive process assessments |
| **SOTIF (Safety of Intended Functionality)** | Scenario analysis, safe fallback state validation | ISO 21448 compliance support |
| **IP.Rights Protection** | Encrypt sensitive architectures, access control / audit logging | Protect proprietary designs in multi-supplier networks |

---

*E/E Architect Design — Precision, traceability, and speed for Solution Architects.*

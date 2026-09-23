# System Composer → E/E Architect Design bridge

Exports the **physical architecture** layer of a MathWorks System Composer
model to this repository's `library/systems/*.eec-system-1.4.json` format —
one JSON file per **physical variant** of the system, containing only the
components that are electronic or electronically-driven.

This is the tool referenced as "MathWorks / Simulink Export" in the root
`README.md`'s *Next Possible Improvements* table.

## What this does and does not do

- **Tagging**: a System Composer *Profile* (`EEDesignSolutionProfile`) with
  three stereotypes lets you mark, directly in the Property Inspector,
  which components are electronic/electronically-driven and which ports
  are their electrical nets. Everything untagged (valve bodies, brackets,
  hoses, structural parts…) is ignored by the exporter.
- **Variants**: each physical variant is one saved architecture model.
  The exporter takes a list of `(model, variant label)` pairs and writes
  one independent system JSON per variant, each with its own `name` and
  `Ref-2X` — this matches how the framework already models variants (see
  root `README.md` §4 and `inc/EEC_architecture.h`, where `variant_id` is
  reserved for System/Sensor/Actuator/ECU objects).
- **Output**: files matching the exact schema this repo's C engine and
  Python validator expect (`type:"system"`, `schema_version:"eec-system-1.4"`,
  explicit `pins[]`/`connectors[]`/`signals[]` per device — the *v4*, non
  "legacy-compact" shape). It does **not** touch `library/platform.json`
  or `src/main.c` for you — the console output tells you exactly what to
  add (see "Wiring the output into a build" below).
- It does **not** attempt ECU pin auto-mapping or run the 23 verification
  rules — that happens when you rebuild `./app` with the new system
  referenced, same as any other library file.

## Files

| File | Role |
|---|---|
| `eecEnums.m` | Enum value lists, mirrored 1:1 from `tools/scripts/eec_json_contract.v4.json`. No System Composer dependency. |
| `defineEECProfile.m` | Creates/saves `EEDesignSolutionProfile.sysml` (3 stereotypes). Run once. |
| `collectTaggedElements.m` | **The only file that calls System Composer's model API.** Walks one model, returns plain MATLAB structs. If a MATLAB-release API difference bites, this is the one file to patch. |
| `buildEECSystemStruct.m` | Pure mapping logic: plain structs → the exact JSON struct (enum validation, `electrical_requirement` bitmask, cavity/pin numbering, Ref-2X sanitizing). No System Composer dependency — can be exercised standalone. |
| `exportEECSystemJSON.m` | Orchestrator: loops variants, calls the two above, writes the files, prints a summary + the `platform.json`/`main.c` snippet to add. |

## Prerequisites

- MATLAB + System Composer (the profile/stereotype and model-traversal
  APIs used here have been stable since System Composer's introduction in
  R2019b, but exact method names have moved slightly across releases —
  see the note in `collectTaggedElements.m`).
- A physical architecture model already built (this tool tags and reads
  an existing model; it does not create component diagrams for you).

## Workflow

### 1. Define and attach the profile (once per project)

```matlab
cd('matlab/system_composer_export')
defineEECProfile('OutputFolder', pwd)
```

In each physical-architecture model: **Modeling tab → Profiles → Add to
Model**, pick `EEDesignSolutionProfile`.

### 2. Tag the model

For **every physical variant**, in that variant's model:

1. Select the **root architecture** → Property Inspector → apply
   `EEDesignSolutionProfile.ElectricalSystem` → fill in `RefIdBase`
   (e.g. `SYS-STEERING-ASSIST`, **without** a variant suffix — the
   exporter appends it), `SystemLevel`, `Priority`, `Safety`, etc.
2. For **every component that is electronic, or is the
   electronically-driven part of a mechanical/hydraulic/pneumatic
   assembly** (a sensor, an ECU, or e.g. the solenoid coil of a valve —
   tag the coil, not the valve body): apply
   `EEDesignSolutionProfile.ElectricalComponent`, set `Kind` to `SENSOR`
   or `ACTUATOR`, and fill in the part/connector properties.
3. For **every port of that component that is an electrical net**
   (supply, ground, signal, bus line): apply
   `EEDesignSolutionProfile.ElectricalSignal` and set at minimum
   `CavityNumber`, `Role`, `InterfaceType`, `Unit`. `CavityNumber` across
   a component's tagged ports must be exactly `1..N` (one connector
   cavity = one pin = one signal — the same rule this repo's own library
   files follow).
4. Leave non-electrical ports (hydraulic, mechanical, thermal) untagged —
   they are skipped.
5. Save the model.

Repeat per variant model. Components/ports common to all variants need
tagging in each model that contains them (there is currently no shared
"tag once, reuse across variant models" step — see *Limitations* below).

### 3. Export

```matlab
variants(1) = struct('ModelName', 'SteeringAssist_BASE', 'Label', "BASE");
variants(2) = struct('ModelName', 'SteeringAssist_HD',   'Label', "HD");
summary = exportEECSystemJSON(variants, "Steering_Assist", "library/systems");
```

This writes `library/systems/Steering_Assist__BASE.eec-system-1.4.json`
and `..._HD.eec-system-1.4.json`, and prints the `Ref-2X` of each for the
next step. `summary` is a table you can inspect programmatically (one row
per variant, with `OK`/`Message` columns — a bad tag on one variant does
not stop the others from exporting).

### 4. Validate (optional but recommended)

```bash
python3 tools/scripts/validate_system_json_code_aligned.py library/systems/Steering_Assist__*.json
```

### 5. Wiring the output into a build

Add each new `Ref-2X` to `library/platform.json`:

```json
{ "systems": ["...", "SYS-STEERING-ASSIST-BASE"] }
```

and reference the variant(s) you want in this build from `src/main.c`:

```c
EEC_platform_add_system(&platform, "SYS-STEERING-ASSIST-BASE");
/* or, for the HD build configuration: */
EEC_platform_add_system(&platform, "SYS-STEERING-ASSIST-HD");
```

Then `./app` auto-maps the new system's signals onto real ECU pins and
runs the 23-rule verification pass as usual.

## Field mapping

### `ElectricalSystem` (root architecture) → JSON `system` object

| Stereotype property | JSON field |
|---|---|
| `RefIdBase` + variant label | `Ref-2X` (sanitized, ≤25 chars — `inc/EEC_architecture.h` `ref_2x[26]`) |
| `SystemLevel`, `Priority`, `Safety`, `Location`, `TakeRate`, `IsMandatory`, `AutoMappingEnabled`, `PartNumber`, `Version`, `Description` | same-named / obvious JSON field |

### `ElectricalComponent` (component) → JSON device object

| Stereotype property | JSON field |
|---|---|
| `Kind` | `device_type`, and lower-cased into `type` / `schema_version` |
| `PartNumber`, `SupplierPartNumber`, `Manufacturer`, `Priority`, `Safety`, `Location`, `IsMandatory`→`is_mandatory`, `MappingEnabled`→`mapping_enabled`, `Description` | same |
| `DriveTopology` | `drive_topology` (actuators only, omitted if blank) |
| `Connector*` properties | the device's single `connectors[0]` entry; `total_cavities`/`used_cavities`/`max_pin_number` are **derived** from the number of tagged ports, not tagged separately |

### `ElectricalSignal` (port) → one `pins[]` entry + one `signals[]` entry

| Stereotype property | JSON field(s) |
|---|---|
| Port name | `pins[].name`/`signal`, `signals[].prefix`/`name` (sanitized to `A-Z0-9_`) |
| `CavityNumber` | `pins[].number`/`cavity` |
| `Role`, `InterfaceType`→`interface_type`/`interface`, `Unit`, `SignalType`→`type`, `Min`, `Max`, `Resolution`, `Scaling`, `Priority`, `Safety` | same |
| `PullUp`,`PullDown`,`HighSide`,`LowSide`,`PushPull`,`CurrentSense`,`VoltageIn`,`Differential` | combined into the `electrical_requirement` bitmask (bit values match `EEC_ElectricalFlag_e` in `inc/EEC_types.h` exactly) |
| `NominalCurrent`, `InrushCurrent`, `MaxVoltage`, `SafetyRelevant`→`safety_relevant`, `GroundClass`→`ground_class`, `RequiredResetState`→`required_reset_state`, `RequiredSensorSupply`, `RequiredSensorGround`, `RequiredSupplyVoltage` | `pins[]` fields |
| `DiagnosticsRequired` | `pins[].diagnostics_required` as `0`/`1` (see *Limitations*) |

## Variant patterns

**Primary pattern (what this tool implements): one saved model per
physical variant.** Reliable and version-agnostic — `exportEECSystemJSON`
just opens each model in turn. This is the recommended approach.

**Alternative: native Simulink/System Composer Variant blocks inside one
model** (`Simulink.VariantManager`, Variant Components/Variant Choices).
This is not implemented here, on purpose: the exact API for enumerating
and activating variant configurations has changed across MATLAB releases,
and getting it subtly wrong would silently export the wrong configuration
rather than fail loudly. If you use this mechanism, the integration point
is `collectTaggedElements.m` — before the traversal, activate the variant
configuration you want (e.g. `Simulink.VariantManager.setActiveVariant`
or your project's own variant-control mechanism), then call
`rootArch.getComponents()` as usual; everything downstream
(`buildEECSystemStruct.m`) is unaffected either way since it only sees
plain structs.

## Limitations / simplifications (by design, to keep this maintainable)

- **One connector per tagged component.** A component needing more than
  one physical connector needs either two System Composer components (one
  per connector) or a manual edit of the exported JSON's `connectors[]`/
  `pins[].connector`.
- **`DiagnosticsRequired` is a single boolean**, mapped to `0`/`1`, not
  the full 8-bit `EEC_DiagFlags_e` bitmask (`OPEN_LOAD`, `SHORT_GND`, …).
  Real library files mostly use it this way too (see e.g.
  `library/sensors/pushbutton/*.json`); if you need per-bit diagnostic
  coverage, extend `ElectricalSignal` with the 8 booleans (mirroring how
  `electrical_requirement` is built — see `eecEnums().diag_flag_bits`)
  and update `buildPinAndSignal` in `buildEECSystemStruct.m` accordingly.
- **Enums are plain strings, validated centrally**, not native System
  Composer `enum` properties — see the comment above the local-helpers
  section in `defineEECProfile.m` for why. A typo is caught at export
  time with a clear error naming the exact element and property, not
  silently accepted.
- **Shared components across variants must be tagged in each variant's
  model.** There is no "tag once in a base model, reuse in derived
  variant models" step; if your variants are built from a common
  reference sub-model, tag the stereotypes on that shared sub-model once
  and it will be picked up in every variant model that includes it (this
  falls out naturally from `collectTaggedElements.m` recursing into
  referenced components — it does not need special-casing).

## Verification performed while building this

`buildEECSystemStruct.m`'s output shape (device/connector/pin/signal
field set and types) was checked, outside MATLAB, by hand-constructing
the equivalent JSON for a 2-variant example (a steering-assist system:
angle sensor + proportional coil in a `BASE` variant, plus an extra
load-pressure sensor in an `HD` variant) and running it through:

1. `tools/scripts/validate_system_json_code_aligned.py` (strict v4, no
   `--legacy-compact`) — **0 errors** on both variants.
2. The real C engine (`EEC_Library_ImportSystem` → `EEC_System_connect_to_ecus`
   against the real `AEC_SMALL`/`MEDIUM`/`LARGE` ECU presets →
   `EEC_Verify_architecture`) — both variants imported with **zero
   structural errors** (all devices, connectors, pins, cavities and
   signals registered correctly); auto-mapping and the 23-rule
   verification pass then ran exactly as they would for any other
   library file.

What was **not** verified end-to-end is the System Composer side itself
(`collectTaggedElements.m`) against a live model, since this environment
has no MATLAB/System Composer installation. That function is kept
deliberately short and isolated so it is the one place to fix if your
release's traversal API differs — see the comments inside it.

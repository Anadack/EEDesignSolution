# Signal Naming Convention Implementation Plan

## Objective
Automatically rename all sensor/actuator signals in the architecture to follow the **SYSTEM_Function_[POSITION_]TYPE** convention.

---

## Phase 1: C Framework Extensions (EEC_architecture.h)

### Add to EEC_Signal_t structure:
```c
typedef struct EEC_Signal_s {
    // ... existing fields ...
    
    // Naming convention fields
    char system_code[8];           // "HYDD", "BRK", "RHIT", etc.
    char function_name[32];        // "AnglPosn", "PressMonit", etc. (CamelCase)
    char position_index[8];        // "01", "02", "" (optional)
    char type_code[8];             // "SNSR", "PWR", "GND", "CAN", etc.
    char clean_signal_name[64];    // Full generated name: SYSTEM_Function_[POSITION_]TYPE
    bool is_auto_named;            // True if name was auto-generated
} EEC_Signal_t;
```

### New Enums (EEC_types.h):
```c
// System codes mapping device systems to abbreviated codes
typedef enum {
    SYSTEM_CODE_HYDD = 0,  // Hydraulics Distribution
    SYSTEM_CODE_BRK,       // Brake System
    SYSTEM_CODE_RHIT,      // Rear Hitch
    SYSTEM_CODE_BREX,      // Rexroth Coils
    SYSTEM_CODE_COIL,      // Hydraulic Coils
    SYSTEM_CODE_ELB,       // Elobau Sensors
    SYSTEM_CODE_UNKNOWN
} EEC_SystemCode_t;

// Type codes for last segment
typedef enum {
    TYPE_CODE_SNSR = 0,    // Sensor
    TYPE_CODE_SWT,         // Switch
    TYPE_CODE_PWR,         // Power
    TYPE_CODE_GND,         // Ground
    TYPE_CODE_CAN,         // CAN Bus
    TYPE_CODE_CMD,         // Command
    TYPE_CODE_AI,          // Current Input
    TYPE_CODE_UNKNOWN
} EEC_TypeCode_t;
```

---

## Phase 2: C Implementation (New file: src/EEC_naming.c)

### Core Functions:

#### 1. **Get System Code from System Name**
```c
EEC_SystemCode_t EEC_GetSystemCode(const char *system_name);
// Maps "Rear_Hydraulic_Hitch_System" → SYSTEM_CODE_RHIT
```

#### 2. **Extract Type Code from Interface**
```c
EEC_TypeCode_t EEC_GetTypeCode(EEC_SignalInterface_t interface, EEC_PinRole_t role);
// Maps INTERFACE_ANALOG + ROLE_INPUT → TYPE_CODE_SNSR
// Maps INTERFACE_POWER + ROLE_SUPPLY → TYPE_CODE_PWR
```

#### 3. **Generate Clean Function Name**
```c
int EEC_GenerateFunctionName(
    const char *original_signal,
    const char *device_name,
    char *function_name_out,
    size_t max_len);
// Extract meaningful function from original signal: 
// "HAT1200_Angle_4_20mA" → "AnglPosn"
```

#### 4. **Extract Position Index**
```c
int EEC_ExtractPositionIndex(
    const char *original_signal,
    char *position_out,
    size_t max_len);
// "HAT1200_01" or "HAT1200" → "01" or ""
```

#### 5. **Generate Full Clean Signal Name**
```c
int EEC_GenerateCleanSignalName(EEC_Signal_t *signal);
// Combines: system_code + "_" + function_name + ("_" + position if present) + "_" + type_code
// Result: "HYDD_AnglPosn01_SNSR"
```

#### 6. **Validate Signal Name Compliance**
```c
int EEC_ValidateSignalNaming(const EEC_Signal_t *signal, char *reason_out, size_t max_len);
// Returns: 0 (OK), -1 (non-compliant)
// Sets reason_out with explanation
```

---

## Phase 3: Automatic Naming in Architecture Loading

### Update in src/EEC_library.c:
When importing sensor/actuator from JSON:
1. Auto-detect system code from system name
2. Parse original signal name
3. Extract function name using pattern matching
4. Extract position index (if present)
5. Map interface → type code
6. Generate clean_signal_name
7. Set is_auto_named = true

### Pattern Matching Rules:
```
Original: "HAT1200_Angle_4_20mA"
├─ Device: HYDAC_HAT1200 → System: Hydraulics → HYDD
├─ Extract: "Angle" → "AnglPosn" (function)
├─ Interface: CURRENT → TYPE_CODE_AI? No, it's a sensor → SNSR
└─ Result: "HYDD_AnglPosn_AI" or apply smarter logic
```

---

## Phase 4: Update Signal Export (src/EEC_export.c)

### JSON Export Format:
```json
{
  "id": 1,
  "name": "HAT1200_Angle_4_20mA",
  "system": "Rear_Hydraulic_Hitch_System",
  "device": "Rear_Hitch_Position_Sensor",
  "interface_type": "CURRENT",
  "original_name": "HAT1200_Angle_4_20mA",
  "clean_name": "HYDD_AnglPosn_AI",
  "naming_convention": {
    "system_code": "HYDD",
    "function": "AnglPosn",
    "position": "",
    "type_code": "AI",
    "is_auto_named": true,
    "validation_status": "OK"
  },
  "safety": "AgPL_B",
  "priority": "MEDIUM"
}
```

---

## Phase 5: Python Generator Updates

### Update all generators to use clean_name:
```python
# Before:
signal_name = signal.get('name', '')  # "HAT1200_Angle_4_20mA"

# After:
signal_name = signal.get('clean_name', signal.get('name', ''))
# Uses "HYDD_AnglPosn_AI" if available, falls back to original
```

### Update generated HTML reports:
- Show both original name (muted/red) and clean name (highlighted/green)
- Display naming convention metadata
- Show compliance status

---

## Phase 6: Verification & Testing

### New C Unit Tests (qa/test_naming_convention.c):
```c
// Test cases:
test_system_code_mapping();
test_type_code_from_interface();
test_function_name_extraction();
test_position_index_extraction();
test_clean_name_generation();
test_naming_compliance_validation();
```

### Integration Tests:
1. Load example architecture
2. Verify all signals have clean_name populated
3. Export to JSON
4. Verify clean_name appears in JSON
5. Generate HTML reports with clean names

---

## Phase 7: Configuration & Customization

### Add to eec_config.json:
```json
{
  "naming_convention": {
    "enabled": true,
    "auto_generate": true,
    "system_codes": {
      "Rear_Hydraulic_Hitch_System": "RHIT",
      "BRAKE_SYSTEM": "BRK",
      "HYDAC_Selected_Sensor_Examples": "HYDD"
    },
    "type_code_mapping": {
      "POWER+SUPPLY": "PWR",
      "GROUND": "GND",
      "ANALOG+INPUT": "SNSR",
      "CAN+INOUT": "CAN"
    },
    "function_name_rules": [
      { "pattern": "Angle.*", "function": "AnglPosn" },
      { "pattern": "Pressure.*", "function": "PressMonit" },
      { "pattern": ".*Position.*", "function": "PosMonit" }
    ]
  }
}
```

---

## Implementation Order

1. **Week 1**: Add C struct fields & enums
2. **Week 2**: Implement EEC_naming.c core functions
3. **Week 3**: Integration in library loading & export
4. **Week 4**: Python generator updates
5. **Week 5**: Unit tests & validation
6. **Week 6**: Documentation & examples

---

## Benefits

✅ **Consistency**: All signals follow same naming standard  
✅ **Traceability**: Original names preserved for reference  
✅ **Validation**: Framework auto-checks naming compliance  
✅ **Documentation**: Clean names in all exports/reports  
✅ **Integration**: Ready for downstream tools/CANoe  
✅ **Flexibility**: Config-driven mappings  

---

## Example Output

**Before**:
```
Signal: HAT1200_Angle_4_20mA (system: Rear_Hydraulic_Hitch_System)
Signal: EDS410_OUT1_PNP (system: HYDAC_Selected_Sensor_Examples)
Signal: DirCoilCmd_HS (system: BRAKE_SYSTEM)
```

**After**:
```
Signal: HYDD_AnglPosn_AI (original: HAT1200_Angle_4_20mA) [Status: OK]
Signal: HYDD_PressSwitch01_SWT (original: EDS410_OUT1_PNP) [Status: OK]
Signal: BRK_CoilDir_CMD (original: DirCoilCmd_HS) [Status: OK]
```

---

## Files to Create/Modify

**New Files**:
- `inc/EEC_naming.h` — Header with naming convention API
- `src/EEC_naming.c` — Implementation
- `qa/test_naming_convention.c` — Unit tests

**Modified Files**:
- `inc/EEC_architecture.h` — Add struct fields
- `inc/EEC_types.h` — Add enums
- `src/EEC_library.c` — Auto-naming on import
- `src/EEC_export.c` — Export clean names
- All Python generators — Use clean_name
- `eec_config.json` — Naming config section

---

**Status**: Ready for implementation  
**Effort**: ~5 weeks (2–3 devs working in parallel)  
**Priority**: HIGH (improves traceability & standardization)

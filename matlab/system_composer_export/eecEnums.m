function enums = eecEnums()
%EECENUMS Enumerated value lists for the E/E Architect Design JSON contract.
%   Mirrors tools/scripts/eec_json_contract.v4.json ("enums" section) 1:1 so
%   that MATLAB-side tagging/export uses exactly the same vocabulary as the
%   C importer and the Python validator. If the contract file changes,
%   update this function to match — it is intentionally a plain data
%   function with no System Composer dependency so it can be unit-tested
%   on its own.
%
%   enums = eecEnums() returns a struct with one field per enum category,
%   each holding a string array of the allowed values.

enums = struct();

enums.device_types = ["SENSOR", "ACTUATOR"];

enums.roles = ["INPUT", "OUTPUT", "INOUT", "SUPPLY", "GROUND", "UNASSIGNED"];

enums.signal_types = ["U1", "U8", "S8", "U16", "S16", "U32", "S32", "U64", "S64", "F32", "F64"];

enums.interfaces = ["DIGITAL", "ANALOG", "PWM", "CAN", "LIN", "SENT", "ETHERNET", ...
    "RESISTANCE", "FREQUENCY", "CURRENT", "FLEXRAY", "POWER", "GROUND"];

enums.units = ["NONE", "BOOLEAN", "VOLT", "AMPERE", "HERTZ", "PERCENT", "RPM", ...
    "CELSIUS", "BAR", "DEGREE", "OHM", "MILLIMETER"];

enums.priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

enums.safety_classes = ["QM", "AgPL_A", "AgPL_B", "AgPL_C", "AgPL_D"];

enums.system_levels = ["SL0", "SL1", "SL2", "SL3", "SL4"];

% Matches EEC_Brand_e in inc/EEC_types.h exactly (FENDT=0,
% MASSEY_FERGUSON=1, VALTRA=2) — the JSON contract lists "brands" as a
% known system-level key but (unlike interfaces/roles/units/...) does not
% itself constrain its values, so this list is this exporter's own
% enforcement, kept in sync with the C enum by hand.
enums.brands = ["FENDT", "MASSEY_FERGUSON", "VALTRA"];

enums.connector_families = ["DEUTSCH", "DEUTSCH_DT04_2P", "AMP_SUPERSEAL", ...
    "AMP_JUNIOR_TIMER", "MOLEX", "TE_CONNECTIVITY", "YAZAKI", "JAE", "AMPSEAL", ...
    "CUSTOM", "DIN_EN_175301_803", "BINDER", "M12", "ISO_4400", "KOSTAL"];

enums.connector_genders = ["MALE", "FEMALE", "HYBRID"];

enums.ground_classes = ["UNCLASSIFIED", "POWER", "LOGIC"];

enums.reset_states = ["OFF", "ON", "HIGH_Z"];

enums.drive_topologies = ["HIGH_SIDE_GROUND_RETURN", "HIGH_SIDE_LOW_SIDE", ...
    "LOW_SIDE_SWITCHED", "HIGH_SIDE_SWITCHED", "NOT_APPLICABLE"];

% Electrical flag bit values — must match EEC_ElectricalFlag_e in
% inc/EEC_types.h exactly (bitmask stored in "electrical_requirement").
enums.electrical_flag_bits = struct( ...
    "PULLUP",        uint32(1),   ...
    "PULLDOWN",      uint32(2),   ...
    "HIGH_SIDE",     uint32(4),   ...
    "LOW_SIDE",      uint32(8),   ...
    "PUSH_PULL",     uint32(16),  ...
    "CURRENT_SENSE", uint32(32),  ...
    "VOLTAGE_IN",    uint32(64),  ...
    "DIFFERENTIAL",  uint32(128));

% Diagnostic flag bit values — must match EEC_DiagFlags_e in inc/EEC_types.h.
enums.diag_flag_bits = struct( ...
    "OPEN_LOAD",    uint32(1),  ...
    "SHORT_GND",    uint32(2),  ...
    "SHORT_BAT",    uint32(4),  ...
    "RANGE_CHECK",  uint32(8),  ...
    "OVERCURRENT",  uint32(16), ...
    "THERMAL_WARN", uint32(32), ...
    "LINE_BREAK",   uint32(64), ...
    "PLAUSIBILITY", uint32(128));

end

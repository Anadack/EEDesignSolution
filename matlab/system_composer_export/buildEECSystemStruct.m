function sysStruct = buildEECSystemStruct(systemMeta, elements, variantLabel, nameBase, sourceModelFile, exportedAt)
%BUILDEECSYSTEMSTRUCT Turn plain tagged-element structs (from
%   collectTaggedElements) into a MATLAB struct ready for jsonencode,
%   matching the EEDesignSolution "system" JSON contract exactly
%   (schema_version "eec-system-1.4" / device schema "eec-sensor-1.5" /
%   "eec-actuator-1.5", as validated by
%   tools/scripts/eec_json_contract.v4.json and by the real C importer,
%   EEC_Library_ImportSystem).
%
%   sysStruct = buildEECSystemStruct(systemMeta, elements, variantLabel, nameBase, sourceModelFile, exportedAt)
%
%   systemMeta, elements  Outputs of collectTaggedElements(modelName).
%   variantLabel          Short variant tag, e.g. "BASE", "HD", "SMALL".
%                          Appended to nameBase and to the system's Ref-2X
%                          so every physical variant gets its own unique
%                          system name and Ref-2X (this framework's
%                          reuse/auto-mapping model keys everything off
%                          Ref-2X — see README.md section 4).
%   nameBase               Logical system name shared by all variants,
%                          e.g. "Steering_Assist". The emitted "name" is
%                          "<nameBase>__<variantLabel>".
%   sourceModelFile        Optional. The 3rd output of
%                          collectTaggedElements(modelName) — the model's
%                          .slx basename, or "" if unknown. Stamped into
%                          "metadata.source_model" for traceability.
%   exportedAt             Optional. ISO-8601 UTC timestamp string (e.g.
%                          from exportEECSystemJSON.m, computed right
%                          before writing the file) — stamped into
%                          "metadata.exported_at". Defaults to "now" if
%                          omitted, so calling this function directly
%                          still produces a valid, useful stamp.
%
%   This function has NO System Composer dependency — it only touches
%   plain MATLAB structs/strings/numbers, so it can be exercised and
%   sanity-checked (e.g. against tools/scripts/validate_system_json_code_aligned.py
%   after jsonencode) independently of having a live model open.
%
%   Every enum-like value is validated here against eecEnums() and raises
%   a clear error naming the offending element if it does not match —
%   this is where "only validate at real boundaries" happens for this
%   pipeline: System Composer property values are free-text strings, so
%   THIS is the boundary.
%
%   See also: collectTaggedElements, exportEECSystemJSON, eecEnums.

enums = eecEnums();
variantLabel = string(variantLabel);
nameBase = string(nameBase);
if nargin < 5 || isempty(sourceModelFile), sourceModelFile = ""; end
if nargin < 6 || isempty(exportedAt)
    % Millisecond precision matters here, not just cosmetically: when
    % installAutoExportOnSave.m fires, the export can run within the same
    % whole second as the model's own save — a whole-second-truncated
    % timestamp would then make the export look OLDER than the save it
    % followed, and checkJsonFreshness.py would wrongly call a
    % just-written JSON "stale". See its STALE_TOLERANCE_SECONDS too.
    exportedAt = string(datetime("now", "TimeZone", "UTC"), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");
end
sourceModelFile = string(sourceModelFile);
exportedAt = string(exportedAt);

sysStruct = struct();
sysStruct.type = "system";
sysStruct.schema_version = "eec-system-1.4";
sysStruct.name = nameBase + "__" + variantLabel;
sysStruct.part_number = charOrEmpty(systemMeta.PartNumber);
sysStruct.version = charOrEmpty(systemMeta.Version, "1.0");
sysStruct.system_level = checkEnum(systemMeta.SystemLevel, enums.system_levels, "system.SystemLevel");
% MATLAB struct field names must be valid identifiers, so "Ref-2X" (a
% hyphen is not legal in a field name, even via dynamic s.('Ref-2X')
% assignment) cannot be a struct field directly. REF2X_JSON_KEY is a
% placeholder field that exportEECSystemJSON.m rewrites to the literal
% "Ref-2X" JSON key after jsonencode — see the comment there.
sysStruct.REF2X_JSON_KEY = sanitizeRef2x(string(systemMeta.RefIdBase) + "-" + variantLabel);
sysStruct.priority = checkEnum(systemMeta.Priority, enums.priorities, "system.Priority");
sysStruct.safety = checkEnum(systemMeta.Safety, enums.safety_classes, "system.Safety");
sysStruct.location = charOrEmpty(systemMeta.Location);
sysStruct.take_rate = double(systemMeta.TakeRate);
sysStruct.is_mandatory = logical(systemMeta.IsMandatory);
sysStruct.auto_mapping_enabled = logical(systemMeta.AutoMappingEnabled);
sysStruct.mapping_enabled = true;
sysStruct.description = charOrEmpty(systemMeta.Description, ...
    "Physical variant " + variantLabel + " exported from MathWorks System Composer physical architecture.");
sysStruct.brands = parseBrandList(systemMeta.Brands, enums.brands, "system.Brands");

% Traceability stamp: which model produced this file and when, so a
% freshness check (checkJsonFreshness.py) or a human can tell whether
% this JSON still reflects the current state of the model. This JSON is
% a GENERATED artifact — treat it as disposable/re-creatable, never
% hand-edit it, or the stamp becomes a lie.
if sourceModelFile == ""
    warning("buildEECSystemStruct:UnknownSourceModel", ...
        "Could not determine the source .slx file name for variant '%s' " + ...
        "(model never saved to disk?) — 'metadata.source_model' will be " + ...
        "empty and checkJsonFreshness.py will not be able to verify this file.", variantLabel);
end
sysStruct.metadata = struct( ...
    "source_model", char(sourceModelFile), ...
    "exported_at", char(exportedAt), ...
    "exporter", "matlab/system_composer_export");

devices = {};
for i = 1:numel(elements)
    el = elements(i);
    if isempty(el.Ports)
        warning("buildEECSystemStruct:EmptyComponent", ...
            "Component '%s' is tagged ElectricalComponent but has no tagged " + ...
            "ElectricalSignal ports — skipped (tag at least one port, or " + ...
            "remove the ElectricalComponent tag).", el.Path);
        continue
    end
    devices{end+1} = buildDevice(el, enums); %#ok<AGROW>
end
if isempty(devices)
    error("buildEECSystemStruct:NoDevices", ...
        "No usable tagged component found for variant '%s' (nameBase '%s'). " + ...
        "Tag at least one Component with ElectricalComponent and at least " + ...
        "one of its Ports with ElectricalSignal.", variantLabel, nameBase);
end
sysStruct.devices = devices;

end

% =========================================================================
function device = buildDevice(el, enums)
kind = checkEnum(el.Props.Kind, enums.device_types, el.Path + ".Kind");
isActuator = strcmp(kind, "ACTUATOR");

device = struct();
device.type = lower(kind); % "sensor" | "actuator"
device.schema_version = "eec-" + lower(kind) + "-1.5";
device.name = el.Name;
device.device_type = kind;
device.part_number = charOrEmpty(el.Props.PartNumber);
device.supplier_pn = charOrEmpty(el.Props.SupplierPartNumber);
device.priority = checkEnum(el.Props.Priority, enums.priorities, el.Path + ".Priority");
device.safety = checkEnum(el.Props.Safety, enums.safety_classes, el.Path + ".Safety");
device.manufacturer = charOrEmpty(el.Props.Manufacturer);
device.description = charOrEmpty(el.Props.Description);
device.notes = "Exported from MathWorks System Composer component '" + el.Path + "'.";
device.owner_system = "";
device.owner_architecture = "EE_Architecture";
device.location = charOrEmpty(el.Props.Location);
device.is_mandatory = logical(el.Props.IsMandatory);
device.mapping_enabled = logical(el.Props.MappingEnabled);

driveTopo = strtrim(string(el.Props.DriveTopology));
if isActuator && driveTopo ~= ""
    device.drive_topology = checkEnum(driveTopo, enums.drive_topologies, el.Path + ".DriveTopology");
end

nPorts = numel(el.Ports);
cavities = zeros(1, nPorts);
for p = 1:nPorts
    cavities(p) = round(double(el.Ports(p).Props.CavityNumber));
end
if ~isequal(sort(cavities), 1:nPorts)
    error("buildEECSystemStruct:BadCavityNumbering", ...
        "Component '%s': CavityNumber across its %d tagged port(s) must be " + ...
        "exactly the integers 1..%d (one connector cavity = one pin = one " + ...
        "signal), got [%s]. Fix each port's CavityNumber property.", ...
        el.Path, nPorts, nPorts, strjoin(string(cavities), ","));
end

connName = charOrEmpty(el.Props.ConnectorName, "X1");
device.connectors = { struct( ...
    "id", "con_" + lower(sanitizeToken(el.Name)) + "_" + lower(sanitizeToken(connName)), ...
    "name", connName, ...
    "part_number", "", ...
    "family", checkEnum(el.Props.ConnectorFamily, enums.connector_families, el.Path + ".ConnectorFamily"), ...
    "gender", checkEnum(el.Props.ConnectorGender, enums.connector_genders, el.Path + ".ConnectorGender"), ...
    "total_cavities", int32(nPorts), ...
    "used_cavities", int32(nPorts), ...
    "max_pin_number", int32(nPorts), ...
    "sealed", logical(el.Props.ConnectorSealed), ...
    "color", "", ...
    "mounting", "", ...
    "ip_rating", charOrEmpty(el.Props.ConnectorIPRating), ...
    "rated_voltage", double(el.Props.ConnectorRatedVoltage), ...
    "rated_current", double(el.Props.ConnectorRatedCurrent), ...
    "temperature_min", int32(round(double(el.Props.ConnectorTempMin))), ...
    "temperature_max", int32(round(double(el.Props.ConnectorTempMax)))) };

pins = {};
signals = {};
[~, order] = sort(cavities); % emit pins/signals in cavity order — cosmetic, not required
for idx = 1:nPorts
    p = order(idx);
    port = el.Ports(p);
    [pin, signal] = buildPinAndSignal(el, port, connName, cavities(p), isActuator, driveTopo, enums);
    pins{end+1} = pin; %#ok<AGROW>
    signals{end+1} = signal; %#ok<AGROW>
end
device.pins = pins;
device.signals = signals;
end

function [pin, signal] = buildPinAndSignal(el, port, connName, cavity, isActuator, driveTopo, enums)
sp = port.Props;
sigName = sanitizeToken(port.Name);
role = checkEnum(sp.Role, enums.roles, el.Path + "/" + port.Name + ".Role");
iface = checkEnum(sp.InterfaceType, enums.interfaces, el.Path + "/" + port.Name + ".InterfaceType");
unit = checkEnum(sp.Unit, enums.units, el.Path + "/" + port.Name + ".Unit");
sigType = checkEnum(sp.SignalType, enums.signal_types, el.Path + "/" + port.Name + ".SignalType");
priority = checkEnum(sp.Priority, enums.priorities, el.Path + "/" + port.Name + ".Priority");
safety = checkEnum(sp.Safety, enums.safety_classes, el.Path + "/" + port.Name + ".Safety");
groundClass = checkEnum(sp.GroundClass, enums.ground_classes, el.Path + "/" + port.Name + ".GroundClass");
resetState = checkEnum(sp.RequiredResetState, enums.reset_states, el.Path + "/" + port.Name + ".RequiredResetState");

elecReq = electricalRequirementMask(sp, enums);
diagRequired = int32(logical(sp.DiagnosticsRequired));

pin = struct( ...
    "id", "pin_" + lower(sigName), ...
    "number", int32(cavity), ...
    "name", sigName, ...
    "connector", connName, ...
    "cavity", int32(cavity), ...
    "role", role, ...
    "interface_type", iface, ...
    "electrical_requirement", elecReq, ...
    "signal", sigName, ...
    "nominal_current", double(sp.NominalCurrent), ...
    "inrush_current", double(sp.InrushCurrent), ...
    "max_voltage", double(sp.MaxVoltage), ...
    "diagnostics_required", diagRequired, ...
    "safety_relevant", logical(sp.SafetyRelevant), ...
    "ground_class", groundClass, ...
    "required_reset_state", resetState, ...
    "required_sensor_supply", charOrEmpty(sp.RequiredSensorSupply, "UNKNOWN"), ...
    "required_sensor_ground", charOrEmpty(sp.RequiredSensorGround, "UNKNOWN"), ...
    "required_supply_voltage", double(sp.RequiredSupplyVoltage));

signal = struct( ...
    "id", "sig_" + lower(sigName), ...
    "prefix", sigName, ...
    "name", sigName, ...
    "count", int32(1), ...
    "type", sigType, ...
    "interface", iface, ...
    "unit", unit, ...
    "min", double(sp.Min), ...
    "max", double(sp.Max), ...
    "resolution", double(sp.Resolution), ...
    "scaling", double(sp.Scaling), ...
    "priority", priority, ...
    "safety", safety, ...
    "part_number", "", ...
    "digital_structure", "UNSPECIFIED", ...
    "electrical_requirement", elecReq, ...
    "role", role, ...
    "description", charOrEmpty(sp.Description), ...
    "notes", "", ...
    "is_mapped", false);

if isActuator && driveTopo ~= ""
    signal.drive_topology = driveTopo;
end
end

function mask = electricalRequirementMask(signalProps, enums)
bits = enums.electrical_flag_bits;
mask = uint32(0);
if logical(signalProps.PullUp),       mask = mask + bits.PULLUP;        end
if logical(signalProps.PullDown),     mask = mask + bits.PULLDOWN;      end
if logical(signalProps.HighSide),     mask = mask + bits.HIGH_SIDE;     end
if logical(signalProps.LowSide),      mask = mask + bits.LOW_SIDE;      end
if logical(signalProps.PushPull),     mask = mask + bits.PUSH_PULL;     end
if logical(signalProps.CurrentSense), mask = mask + bits.CURRENT_SENSE; end
if logical(signalProps.VoltageIn),    mask = mask + bits.VOLTAGE_IN;    end
if logical(signalProps.Differential), mask = mask + bits.DIFFERENTIAL;  end
mask = int32(mask);
end

function out = parseBrandList(value, allowed, fieldDescription)
% "FENDT,MASSEY_FERGUSON" -> {"FENDT","MASSEY_FERGUSON"}; "" -> {} (an
% empty cell array jsonencodes as "[]", not omitted — brands is optional
% but always present for a consistent, predictable file shape).
raw = strtrim(split(string(value), ","));
raw = raw(raw ~= "");
out = {};
for i = 1:numel(raw)
    out{end+1} = checkEnum(raw(i), allowed, fieldDescription); %#ok<AGROW>
end
end

function out = checkEnum(value, allowed, fieldDescription)
out = strtrim(string(value));
if ~any(out == string(allowed))
    error("buildEECSystemStruct:InvalidEnumValue", ...
        "%s = '%s' is not one of the allowed values: %s", ...
        fieldDescription, out, strjoin(string(allowed), ", "));
end
out = char(out);
end

function out = charOrEmpty(value, fallback)
if nargin < 2, fallback = ""; end
s = strtrim(string(value));
if s == ""
    s = string(fallback);
end
out = char(s);
end

function out = sanitizeToken(value)
% Upper-case identifier-safe token: keeps A-Z, 0-9, underscore; everything
% else (spaces, System Composer port-name punctuation, …) becomes "_".
s = upper(strtrim(string(value)));
s = regexprep(s, "[^A-Z0-9_]", "_");
s = regexprep(s, "_+", "_");
out = char(regexprep(s, "^_|_$", ""));
end

function out = sanitizeRef2x(value)
% Ref-2X is stored as char[26] (25 usable chars) in EEC_architecture.h —
% see inc/EEC_architecture.h "ref_2x[26]". Keep it upper-case,
% hyphen/alnum only, and truncate with a warning rather than fail, since
% a too-long id is a naming-convenience problem, not a data-loss one for
% THIS function (the caller sees the final id it wrote to disk).
s = upper(strtrim(string(value)));
s = regexprep(s, "[^A-Z0-9-]", "-");
s = regexprep(s, "-+", "-");
s = regexprep(s, "^-|-$", "");
if strlength(s) > 25
    warning("buildEECSystemStruct:Ref2xTruncated", ...
        "Ref-2X '%s' is longer than the 25-char limit (EEC_architecture.h " + ...
        "ref_2x[26]) — truncated to '%s'. Shorten RefIdBase or the variant label.", ...
        s, extractBefore(s, 26));
    s = extractBefore(s, 26);
end
out = char(s);
end

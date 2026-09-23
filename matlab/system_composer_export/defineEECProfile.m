function profile = defineEECProfile(varargin)
%DEFINEEECPROFILE Create/update the System Composer profile used to tag
%   electronic / electronically-driven elements of a physical architecture
%   for export to EEDesignSolution "system" JSON (schema eec-system-1.4).
%
%   profile = defineEECProfile() creates (or overwrites) a profile named
%   "EEDesignSolutionProfile.sysml" in the current folder and returns the
%   systemcomposer.profile.Profile object.
%
%   profile = defineEECProfile('OutputFolder', folder) writes the profile
%   file into FOLDER instead of the current folder.
%
%   Run this once (or whenever the stereotype set below changes), then in
%   System Composer: Modeling tab > Profiles > Add to Model, and pick
%   "EEDesignSolutionProfile" for every physical architecture model that
%   represents one variant of the system.
%
%   Three stereotypes are defined:
%
%     EEDesignSolutionProfile.ElectricalSystem   (AppliesTo: Architecture)
%       Tag the ROOT of the physical architecture model with this one.
%       Carries the JSON "system"-level metadata (one per model/variant).
%
%     EEDesignSolutionProfile.ElectricalComponent (AppliesTo: Component)
%       Tag every component that IS an electronic part (ECU, sensor) OR
%       that IS the electrical/electronically-driven sub-element of an
%       otherwise mechanical/hydraulic/pneumatic assembly (e.g. the
%       solenoid coil of a hydraulic valve — tag the coil, not the valve
%       body). Untagged components are skipped by the exporter: this is
%       the "tag all electronic or electronically-driven components" step.
%
%     EEDesignSolutionProfile.ElectricalSignal   (AppliesTo: Port)
%       Tag every port of a tagged component that is itself an electrical
%       net (supply, ground, signal, bus). A component can keep untagged
%       ports for its non-electrical interfaces (hydraulic, mechanical,
%       thermal) — those are skipped too.
%
%   See also: collectTaggedElements, buildEECSystemStruct, exportEECSystemJSON.

p = inputParser;
p.addParameter('OutputFolder', pwd, @(x) ischar(x) || isstring(x));
p.parse(varargin{:});
outputFolder = char(p.Results.OutputFolder);

enums = eecEnums();
profileName = "EEDesignSolutionProfile";

profile = systemcomposer.profile.Profile.createProfile(profileName);

% ---------------------------------------------------------------------
% ElectricalSystem — one per physical-architecture model (= one variant)
% ---------------------------------------------------------------------
sysType = profile.addStereotype("ElectricalSystem", "AppliesTo", "Architecture");
addStringProp(sysType, "RefIdBase",     "SYS-CHANGE-ME");   % Ref-2X, WITHOUT variant suffix
addStringProp(sysType, "Version",       "1.0");
addEnumStringProp(sysType, "SystemLevel", enums.system_levels, "SL1");
addEnumStringProp(sysType, "Priority",    enums.priorities,    "MEDIUM");
addEnumStringProp(sysType, "Safety",      enums.safety_classes,"QM");
addStringProp(sysType, "Location",      "");
addDoubleProp(sysType, "TakeRate",      100);
addBoolProp(sysType,   "IsMandatory",   true);
addBoolProp(sysType,   "AutoMappingEnabled", true);
addStringProp(sysType, "PartNumber",    "");
addStringProp(sysType, "Description",   "");
addStringProp(sysType, "Brands",        "");   % comma-separated, e.g. "MASSEY_FERGUSON" or "FENDT,MASSEY_FERGUSON" — see eecEnums().brands for the allowed names

% ---------------------------------------------------------------------
% ElectricalComponent — one per tagged sensor/actuator/ECU component
% ---------------------------------------------------------------------
compType = profile.addStereotype("ElectricalComponent", "AppliesTo", "Component");
addEnumStringProp(compType, "Kind", enums.device_types, "SENSOR"); % SENSOR | ACTUATOR
addStringProp(compType, "PartNumber",       "");
addStringProp(compType, "SupplierPartNumber","");
addStringProp(compType, "Manufacturer",     "");
addEnumStringProp(compType, "Priority", enums.priorities,     "MEDIUM");
addEnumStringProp(compType, "Safety",   enums.safety_classes, "QM");
addStringProp(compType, "Location",         "");
addBoolProp(compType,   "IsMandatory",      true);
addBoolProp(compType,   "MappingEnabled",   true);
addStringProp(compType, "DriveTopology",    "");   % actuators only; one of enums.drive_topologies, or ""
addStringProp(compType, "Description",      "");
% Single logical connector per tagged component (extend the exporter if a
% component genuinely needs more than one physical connector).
addStringProp(compType,  "ConnectorName",        "X1");
addEnumStringProp(compType, "ConnectorFamily", enums.connector_families, "CUSTOM");
addEnumStringProp(compType, "ConnectorGender", enums.connector_genders, "MALE");
addStringProp(compType,  "ConnectorIPRating",    "");
addDoubleProp(compType,  "ConnectorRatedVoltage", 0);
addDoubleProp(compType,  "ConnectorRatedCurrent", 0);
addDoubleProp(compType,  "ConnectorTempMin",     -40);
addDoubleProp(compType,  "ConnectorTempMax",      105);
addBoolProp(compType,    "ConnectorSealed",       true);

% ---------------------------------------------------------------------
% ElectricalSignal — one per tagged electrical port of a tagged component
% ---------------------------------------------------------------------
sigType = profile.addStereotype("ElectricalSignal", "AppliesTo", "Port");
addDoubleProp(sigType, "CavityNumber", 1);   % 1-based cavity on the component's connector
addEnumStringProp(sigType, "Role",          enums.roles,      "OUTPUT");
addEnumStringProp(sigType, "InterfaceType", enums.interfaces, "DIGITAL");
addEnumStringProp(sigType, "Unit",          enums.units,      "NONE");
addEnumStringProp(sigType, "SignalType",    enums.signal_types, "U1");
addDoubleProp(sigType, "Min",        0);
addDoubleProp(sigType, "Max",        1);
addDoubleProp(sigType, "Resolution", 1);
addDoubleProp(sigType, "Scaling",    1);
addEnumStringProp(sigType, "Priority", enums.priorities,      "MEDIUM");
addEnumStringProp(sigType, "Safety",   enums.safety_classes,  "QM");
% Electrical requirement bitmask, exposed as individual booleans (see
% eecEnums().electrical_flag_bits for the bit assignment):
addBoolProp(sigType, "PullUp",        false);
addBoolProp(sigType, "PullDown",      false);
addBoolProp(sigType, "HighSide",      false);
addBoolProp(sigType, "LowSide",       false);
addBoolProp(sigType, "PushPull",      false);
addBoolProp(sigType, "CurrentSense",  false);
addBoolProp(sigType, "VoltageIn",     false);
addBoolProp(sigType, "Differential",  false);
addDoubleProp(sigType, "NominalCurrent", 0);
addDoubleProp(sigType, "InrushCurrent",  0);
addDoubleProp(sigType, "MaxVoltage",     0);
addBoolProp(sigType,   "DiagnosticsRequired", false);
addBoolProp(sigType,   "SafetyRelevant",      false);
addEnumStringProp(sigType, "GroundClass",        enums.ground_classes, "LOGIC");
addEnumStringProp(sigType, "RequiredResetState",  enums.reset_states,   "OFF");
addStringProp(sigType, "RequiredSensorSupply", "UNKNOWN");
addStringProp(sigType, "RequiredSensorGround", "UNKNOWN");
addDoubleProp(sigType, "RequiredSupplyVoltage", 0);
addStringProp(sigType, "Description", "");

if ~isfolder(outputFolder)
    mkdir(outputFolder);
end
save(profile, fullfile(outputFolder, profileName + ".sysml"));

fprintf("EEDesignSolutionProfile written to %s\n", ...
    fullfile(outputFolder, profileName + ".sysml"));
fprintf("Add it to your physical architecture model via: Modeling tab > Profiles > Add to Model.\n");

end

% =========================================================================
% Local helpers — kept tiny and boring on purpose: enum *values* are
% validated centrally in buildEECSystemStruct.m/eecEnums.m, not by the
% System Composer property type itself, to avoid depending on the
% systemcomposer.profile.Enumeration API (its exact call signature has
% changed across MATLAB releases; a plain "string" property has not).
% =========================================================================
function addStringProp(stereotype, name, defaultValue)
prop = stereotype.addProperty(name, "Type", "string");
prop.DefaultValue = string(defaultValue);
end

function addEnumStringProp(stereotype, name, allowedValues, defaultValue) %#ok<INUSD>
% Same as addStringProp; allowedValues is accepted purely for
% self-documentation at the call site (the authoritative list lives in
% eecEnums()) even though it is not wired into a native System Composer
% enum type — see the comment above the local-helpers section.
prop = stereotype.addProperty(name, "Type", "string");
prop.DefaultValue = string(defaultValue);
end

function addDoubleProp(stereotype, name, defaultValue)
prop = stereotype.addProperty(name, "Type", "double");
prop.DefaultValue = defaultValue;
end

function addBoolProp(stereotype, name, defaultValue)
prop = stereotype.addProperty(name, "Type", "boolean");
prop.DefaultValue = defaultValue;
end

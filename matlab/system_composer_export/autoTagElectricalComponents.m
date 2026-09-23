function report = autoTagElectricalComponents(modelName, varargin)
%AUTOTAGELECTRICALCOMPONENTS Bulk-apply EEDesignSolutionProfile stereotypes
%   across a physical architecture model using a name-keyword
%   classification table, instead of tagging every component and port by
%   hand in the Property Inspector.
%
%   report = autoTagElectricalComponents(modelName) walks every component
%   in MODELNAME (recursively) and matches its name against a
%   classification table (default: defaultComponentRules(), below) to
%   decide SENSOR / ACTUATOR / no match. A match gets
%   "EEDesignSolutionProfile.ElectricalComponent" applied with Kind set;
%   its ports are then matched against a second table
%   (defaultPortRules()) to decide Role/InterfaceType and get
%   "EEDesignSolutionProfile.ElectricalSignal" applied, with CavityNumber
%   assigned in port declaration order (1, 2, 3, ...).
%
%   report = autoTagElectricalComponents(___, Name, Value) with:
%     'ComponentRules'  override table (Pattern, Kind) — first matching
%                       row wins; Pattern is a case-insensitive regexp
%                       tested against the component name
%     'PortRules'       override table (Pattern, Role, InterfaceType) —
%                       Role/InterfaceType may be "" to mean "use the
%                       owning component's default role" (SENSOR->OUTPUT,
%                       ACTUATOR->INPUT — the same default this repo's
%                       own tools/scripts/eec_json_contract.v4.json uses:
%                       "sensor_default_signal_role"/"actuator_default_signal_role")
%     'Apply'           true (default) tags the model; false = dry run —
%                       report only, nothing written to the model
%
%   report  table: Path, Kind, MatchedBy, NumPortsTagged, NumPortsTotal,
%           Applied — one row per component VISITED, including ones that
%           matched no rule (Kind "", MatchedBy "(no component rule
%           matched)"), so you can review the whole classification in one
%           place before trusting it. Ports matching no PortRules row are
%           left untagged on purpose (see "What this cannot do" below);
%           NumPortsTagged < NumPortsTotal on a matched component is your
%           signal to either add a rule or tag those ports by hand.
%
%   Recommended flow: run once with 'Apply', false; inspect report (and
%   report(report.Kind=="" & report.Applied==false, :) in particular, to
%   catch anything the table missed); adjust ComponentRules/PortRules or
%   rename a handful of components/ports if that is faster; run again
%   with 'Apply', true (the default).
%
%   WHAT THIS CANNOT DO: invent part numbers, manufacturers, electrical
%   ratings, safety class, or an interface type a name genuinely does not
%   encode. Kind/Role/InterfaceType/CavityNumber get a defensible default
%   so the model becomes exportable, but every auto-tagged element still
%   needs a quick pass in the Property Inspector (or a script driven by
%   your own BOM/parts-list spreadsheet) to fill in Priority, Safety,
%   PartNumber, the electrical-requirement flags, Min/Max, etc. before
%   the export is production-accurate — see this folder's README.md.
%
%   Like collectTaggedElements.m, this is one of the two files in this
%   folder that calls System Composer's model API directly (addStereotype/
%   setProperty via the stable, function-based form) — if a method name
%   differs on your release, this is where to patch it.
%
%   See also: defineEECProfile, collectTaggedElements, exportEECSystemJSON.

p = inputParser;
p.addParameter('ComponentRules', defaultComponentRules());
p.addParameter('PortRules', defaultPortRules());
p.addParameter('Apply', true, @(x) islogical(x) && isscalar(x));
p.parse(varargin{:});
componentRules = p.Results.ComponentRules;
portRules = p.Results.PortRules;
doApply = p.Results.Apply;

PROFILE = "EEDesignSolutionProfile";
model = systemcomposer.loadModel(modelName);
rootArch = model.Architecture;

report = table(strings(0,1), strings(0,1), strings(0,1), zeros(0,1), zeros(0,1), false(0,1), ...
    'VariableNames', {'Path', 'Kind', 'MatchedBy', 'NumPortsTagged', 'NumPortsTotal', 'Applied'});

report = visitAndTag(rootArch.getComponents(), string(modelName), report, ...
    PROFILE, componentRules, portRules, doApply);

fprintf("autoTagElectricalComponents: %d component(s) visited, %d tagged%s.\n", ...
    height(report), sum(report.Applied), ternary(doApply, "", " (dry run — nothing written)"));

end

% =========================================================================
function report = visitAndTag(comps, parentPath, report, profileName, componentRules, portRules, doApply)
for i = 1:numel(comps)
    c = comps(i);
    thisPath = parentPath + "/" + string(c.Name);

    [kind, matchedBy] = matchFirst(string(c.Name), componentRules, "Kind");
    allPorts = c.getPorts();
    nTagged = 0;
    if kind ~= ""
        if doApply
            if ~hasStereotype(c, profileName + ".ElectricalComponent")
                addStereotype(c, profileName + ".ElectricalComponent");
            end
            setProperty(c, profileName + ".ElectricalComponent.Kind", kind);
        end
        for j = 1:numel(allPorts)
            if tagPortIfMatched(allPorts(j), j, kind, portRules, profileName, doApply)
                nTagged = nTagged + 1;
            end
        end
    end

    report(end+1, :) = {thisPath, kind, matchedBy, nTagged, numel(allPorts), kind ~= "" && doApply}; %#ok<AGROW>

    childComps = c.getComponents();
    if ~isempty(childComps)
        report = visitAndTag(childComps, thisPath, report, profileName, componentRules, portRules, doApply);
    end
end
end

function tagged = tagPortIfMatched(port, cavityNumber, componentKind, portRules, profileName, doApply)
[role, iface, matched] = matchPort(string(port.Name), portRules, componentKind);
tagged = matched;
if ~matched || ~doApply
    return
end
if ~hasStereotype(port, profileName + ".ElectricalSignal")
    addStereotype(port, profileName + ".ElectricalSignal");
end
setProperty(port, profileName + ".ElectricalSignal.CavityNumber", double(cavityNumber));
setProperty(port, profileName + ".ElectricalSignal.Role", role);
setProperty(port, profileName + ".ElectricalSignal.InterfaceType", iface);
end

function [role, iface, matched] = matchPort(portName, portRules, componentKind)
defaultRole = "INPUT";
if componentKind == "SENSOR"
    defaultRole = "OUTPUT"; % matches eec_json_contract.v4.json rules.sensor_default_signal_role
end
matched = false;
role = ""; iface = "";
for r = 1:height(portRules)
    if ~isempty(regexpi(portName, portRules.Pattern(r), 'once'))
        role = portRules.Role(r);
        iface = portRules.InterfaceType(r);
        if role == "", role = defaultRole; end
        matched = true;
        return
    end
end
end

function [value, matchedBy] = matchFirst(name, rules, valueColumn)
value = ""; matchedBy = "(no component rule matched)";
for r = 1:height(rules)
    if ~isempty(regexpi(name, rules.Pattern(r), 'once'))
        value = rules.(valueColumn)(r);
        matchedBy = "/" + rules.Pattern(r) + "/";
        return
    end
end
end

function out = ternary(cond, a, b)
if cond, out = a; else, out = b; end
end

% =========================================================================
function rules = defaultComponentRules()
% First match wins. Deliberately conservative: bare "Valve" does NOT
% match (most valve bodies in a physical architecture are the mechanical
% housing, not the electrical part — only the coil/solenoid/modulator
% sub-element is electronically driven and should be tagged).
%
% ECU-like components are deliberately NOT in this table: an ECU is not a
% SENSOR/ACTUATOR device inside a system's devices[] in this framework's
% JSON contract — it is its own top-level "ecu" JSON
% (library/ecus/*.json, loaded via EEC_Library_ImportEcu, not part of
% what ElectricalComponent/buildEECSystemStruct.m produces). If your
% physical architecture models an ECU as a component, leave it untagged
% here (this exporter is for the devices that get mapped ONTO an ECU's
% pins, not the ECU itself).
Pattern = [ ...
    "Sensor"; "Switch"; "Encoder"; "Transducer"; ...   % -> SENSOR
    "Solenoid"; "Coil"; "Modulator"];                  % -> ACTUATOR
Kind = [ ...
    "SENSOR"; "SENSOR"; "SENSOR"; "SENSOR"; ...
    "ACTUATOR"; "ACTUATOR"; "ACTUATOR"];
rules = table(Pattern, Kind);
end

function rules = defaultPortRules()
% Role "" means "use the owning component's Kind-based default" (see
% matchPort). First match wins.
Pattern = [ ...
    "SUPPLY|VBAT|VCC|PWR"; ...
    "GND|RET(URN)?"; ...
    "CAN_?H|CAN_?L"; ...
    "PWM"; ...
    "FREQ"; ...
    "4[_-]?20\s*MA|CURRENT"; ...
    "ANALOG|AOUT|VOUT"; ...
    "CMD|CTRL"; ...
    "OUT|SIG"];
Role = [ ...
    "SUPPLY"; "GROUND"; "INOUT"; ""; "OUTPUT"; "OUTPUT"; "OUTPUT"; "INPUT"; ""];
InterfaceType = [ ...
    "POWER"; "GROUND"; "CAN"; "PWM"; "FREQUENCY"; "CURRENT"; "ANALOG"; "DIGITAL"; "DIGITAL"];
rules = table(Pattern, Role, InterfaceType);
end

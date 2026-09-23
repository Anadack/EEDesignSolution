function [systemMeta, elements] = collectTaggedElements(modelName)
%COLLECTTAGGEDELEMENTS Walk one System Composer physical architecture model
%   and pull out everything tagged with the EEDesignSolutionProfile
%   stereotypes, as plain MATLAB structs (no System Composer objects).
%
%   [systemMeta, elements] = collectTaggedElements(modelName)
%
%   modelName   Name of an already-saved System Composer architecture
%               model (.slx) representing ONE physical variant of the
%               system. The model's root must carry the
%               "EEDesignSolutionProfile.ElectricalSystem" stereotype.
%
%   systemMeta  Struct with the ElectricalSystem stereotype property
%               values read off the model root (see defineEECProfile.m).
%
%   elements    Struct array, one entry per component tagged
%               "EEDesignSolutionProfile.ElectricalComponent" anywhere in
%               the model (recursively), each with fields:
%                 .Name   component name (string)
%                 .Path   "/" separated path from the root (for error
%                         messages only)
%                 .Props  struct of ElectricalComponent property values
%                 .Ports  struct array, one per port on that component
%                         tagged "EEDesignSolutionProfile.ElectricalSignal",
%                         each with fields .Name and .Props
%
%   This is the ONLY file in this folder that calls System Composer's
%   model-traversal API. It is kept short and isolated on purpose: the
%   exact method names for opening a model and walking its architecture
%   have moved slightly across MATLAB releases, so if this errors out on
%   your installation, this is the one function to patch — everything
%   downstream (buildEECSystemStruct.m) works off the plain structs
%   returned here and has no System Composer dependency at all.
%
%   Untagged components/ports are silently skipped (that IS the "tag only
%   the electronic / electronically-driven parts" mechanism). A component
%   that is tagged but whose required properties are left at obviously
%   unfilled defaults still exports — buildEECSystemStruct.m is where
%   completeness is actually checked, with one clear error per problem.
%
%   See also: defineEECProfile, buildEECSystemStruct, exportEECSystemJSON.

PROFILE = "EEDesignSolutionProfile";

model = systemcomposer.loadModel(modelName); % adjust to systemcomposer.openModel(...) if your release needs it
rootArch = model.Architecture;

systemMeta = readStereotypeProps(rootArch, PROFILE + ".ElectricalSystem", systemPropertyNames());
if isempty(fieldnames(systemMeta))
    error("collectTaggedElements:MissingSystemTag", ...
        "Model '%s' root does not carry the %s.ElectricalSystem stereotype. " + ...
        "Apply it once via the Property Inspector before exporting.", modelName, PROFILE);
end

elements = struct("Name", {}, "Path", {}, "Props", {}, "Ports", {});
elements = visitComponents(rootArch.getComponents(), string(modelName), PROFILE, elements);

end

% =========================================================================
function elements = visitComponents(comps, parentPath, profileName, elements)
% Recursively walks COMPS (a System Composer component array), collecting
% every tagged ElectricalComponent into the ELEMENTS accumulator (plain
% struct array, threaded through explicitly — no shared/nested-function
% workspace tricks, so behavior does not depend on MATLAB scoping edge
% cases across releases).
for i = 1:numel(comps)
    c = comps(i);
    thisPath = parentPath + "/" + string(c.Name);
    if hasStereotype(c, profileName + ".ElectricalComponent")
        entry.Name  = string(c.Name);
        entry.Path  = thisPath;
        entry.Props = readStereotypeProps(c, profileName + ".ElectricalComponent", componentPropertyNames());
        entry.Ports = visitPorts(c, profileName);
        elements(end+1) = entry; %#ok<AGROW>
    end
    % Recurse regardless of whether this level was tagged, so a tagged
    % leaf component nested under an untagged mechanical assembly (e.g. a
    % solenoid coil inside a hydraulic valve body) is still found.
    childComps = c.getComponents();
    if ~isempty(childComps)
        elements = visitComponents(childComps, thisPath, profileName, elements);
    end
end
end

function ports = visitPorts(comp, profileName)
ports = struct("Name", {}, "Props", {});
allPorts = comp.getPorts();
for j = 1:numel(allPorts)
    pt = allPorts(j);
    if hasStereotype(pt, profileName + ".ElectricalSignal")
        pentry.Name  = string(pt.Name);
        pentry.Props = readStereotypeProps(pt, profileName + ".ElectricalSignal", signalPropertyNames());
        ports(end+1) = pentry; %#ok<AGROW>
    end
end
end

function props = readStereotypeProps(element, fullStereotypeName, propNames)
% Reads every property in propNames off ELEMENT for the given stereotype,
% via the stable, function-based System Composer API (getProperty), and
% returns them as a plain struct. Returns an empty struct if the
% stereotype is not applied to this element.
props = struct();
if ~hasStereotype(element, fullStereotypeName)
    return
end
for k = 1:numel(propNames)
    name = propNames(k);
    try
        value = getProperty(element, fullStereotypeName + "." + name);
    catch err
        error("collectTaggedElements:PropertyReadFailed", ...
            "Could not read property '%s' on '%s' (stereotype %s): %s", ...
            name, element.Name, fullStereotypeName, err.message);
    end
    props.(name) = value;
end
end

function names = systemPropertyNames()
names = ["RefIdBase", "Version", "SystemLevel", "Priority", "Safety", ...
    "Location", "TakeRate", "IsMandatory", "AutoMappingEnabled", ...
    "PartNumber", "Description"];
end

function names = componentPropertyNames()
names = ["Kind", "PartNumber", "SupplierPartNumber", "Manufacturer", ...
    "Priority", "Safety", "Location", "IsMandatory", "MappingEnabled", ...
    "DriveTopology", "Description", "ConnectorName", "ConnectorFamily", ...
    "ConnectorGender", "ConnectorIPRating", "ConnectorRatedVoltage", ...
    "ConnectorRatedCurrent", "ConnectorTempMin", "ConnectorTempMax", ...
    "ConnectorSealed"];
end

function names = signalPropertyNames()
names = ["CavityNumber", "Role", "InterfaceType", "Unit", "SignalType", ...
    "Min", "Max", "Resolution", "Scaling", "Priority", "Safety", ...
    "PullUp", "PullDown", "HighSide", "LowSide", "PushPull", ...
    "CurrentSense", "VoltageIn", "Differential", "NominalCurrent", ...
    "InrushCurrent", "MaxVoltage", "DiagnosticsRequired", "SafetyRelevant", ...
    "GroundClass", "RequiredResetState", "RequiredSensorSupply", ...
    "RequiredSensorGround", "RequiredSupplyVoltage", "Description"];
end

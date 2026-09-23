function [componentBOM, signalChecklist] = exportDatasheetLookupBOM(variants, nameBase, outputDir)
%EXPORTDATASHEETLOOKUPBOM Build a datasheet-sourcing BOM from tagged
%   physical-architecture components — the step between "tag electronic
%   components" and "build the system JSON": a document listing every
%   distinct electronic/electronically-driven part with enough identity
%   info (manufacturer, part number, description) to go find its real
%   datasheet, plus a per-signal checklist of which electrical values
%   still need confirming from that datasheet before the JSON export
%   (buildEECSystemStruct.m / exportEECSystemJSON.m) is production-accurate.
%
%   [componentBOM, signalChecklist] = exportDatasheetLookupBOM(variants, nameBase, outputDir)
%
%   variants   Same struct array exportEECSystemJSON.m takes: one entry
%              per physical variant, each with .ModelName and .Label.
%              Run this AFTER tagging (defineEECProfile.m +
%              autoTagElectricalComponents.m and/or manual tagging), on
%              the same models you will later export.
%   nameBase   Logical system name, e.g. "Braking_System" — used to name
%              the output files.
%   outputDir  Where to write the CSVs. Defaults to "generated_doc/exports"
%              (this repo's convention for generated outputs — see root
%              README.md "Framework Directory Map").
%
%   Writes two files:
%
%     <outputDir>/<nameBase>_component_bom.csv
%       One row per DISTINCT electronic component — deduplicated across
%       variants by Manufacturer+PartNumber (falling back to component
%       Name when PartNumber is still blank), so the same physical part
%       used in 3 variants gets ONE row, not 3. This is the "go find
%       these datasheets" list. Columns include a ready-to-paste
%       `SearchHint`, a `Variants` column listing every physical variant
%       the part appears in, and a `Conflicts` column that flags when the
%       same identity key was tagged with different Manufacturer /
%       PartNumber / Description / Name text across variants (fix the
%       tagging before trusting the BOM). `DatasheetURL`,
%       `DatasheetConfirmed` and `ResearchNotes` are intentionally blank —
%       fill them in as datasheets are found.
%
%     <outputDir>/<nameBase>_signal_checklist.csv
%       One row per (variant, component, port) — NOT deduplicated, so you
%       can eyeball whether "the same" part was really tagged identically
%       across variants — with the currently-tagged electrical values
%       (Min/Max/currents/voltage/...) to confirm or correct once the
%       datasheet is in hand. A blank `DatasheetNotes` column is added
%       for per-signal notes (e.g. "confirmed p.4 of XYZ datasheet").
%
%   componentBOM, signalChecklist  The same data as MATLAB tables, for
%           scripting, e.g.:
%             componentBOM(componentBOM.PartNumber == "", :)   % no part number tagged yet
%             componentBOM(componentBOM.Conflicts ~= "", :)    % inconsistent tagging
%
%   This reuses collectTaggedElements.m, so the BOM always reflects
%   exactly what exportEECSystemJSON.m would export — one source of
%   truth, nothing to keep in sync by hand.
%
%   See also: collectTaggedElements, exportEECSystemJSON, defineEECProfile,
%   autoTagElectricalComponents.

if nargin < 3 || isempty(outputDir)
    outputDir = fullfile("generated_doc", "exports");
end
outputDir = string(outputDir);
if ~isfolder(outputDir)
    mkdir(outputDir);
end
nameBase = string(nameBase);

rawComp = table(strings(0,1), strings(0,1), strings(0,1), strings(0,1), strings(0,1), strings(0,1), ...
    strings(0,1), strings(0,1), strings(0,1), strings(0,1), strings(0,1), zeros(0,1), ...
    'VariableNames', {'Variant','Path','Name','Kind','Manufacturer','PartNumber', ...
    'SupplierPartNumber','Description','DriveTopology','ConnectorFamily','ConnectorName','NumPorts'});

rawSig = table(strings(0,1), strings(0,1), strings(0,1), strings(0,1), strings(0,1), strings(0,1), ...
    zeros(0,1), strings(0,1), strings(0,1), zeros(0,1), zeros(0,1), zeros(0,1), zeros(0,1), zeros(0,1), false(0,1), ...
    'VariableNames', {'Variant','ComponentPath','ComponentName','PartNumber','PortName','Role', ...
    'CavityNumber','InterfaceType','Unit','Min','Max','NominalCurrent','InrushCurrent','MaxVoltage','SafetyRelevant'});

for v = 1:numel(variants)
    label = string(variants(v).Label);
    [~, elements] = collectTaggedElements(string(variants(v).ModelName));
    for i = 1:numel(elements)
        el = elements(i);
        pn = strtrim(string(el.Props.PartNumber));
        rawComp(end+1, :) = { ...
            label, el.Path, el.Name, string(el.Props.Kind), ...
            strtrim(string(el.Props.Manufacturer)), pn, ...
            strtrim(string(el.Props.SupplierPartNumber)), ...
            strtrim(string(el.Props.Description)), ...
            strtrim(string(el.Props.DriveTopology)), ...
            strtrim(string(el.Props.ConnectorFamily)), ...
            strtrim(string(el.Props.ConnectorName)), ...
            numel(el.Ports) }; %#ok<AGROW>

        for j = 1:numel(el.Ports)
            port = el.Ports(j);
            sp = port.Props;
            rawSig(end+1, :) = { ...
                label, el.Path, el.Name, pn, string(port.Name), ...
                string(sp.Role), double(sp.CavityNumber), string(sp.InterfaceType), string(sp.Unit), ...
                double(sp.Min), double(sp.Max), double(sp.NominalCurrent), double(sp.InrushCurrent), ...
                double(sp.MaxVoltage), logical(sp.SafetyRelevant) }; %#ok<AGROW>
        end
    end
end

if isempty(rawComp)
    error("exportDatasheetLookupBOM:NoTaggedComponents", ...
        "No tagged ElectricalComponent found across %d variant(s) — nothing to write. " + ...
        "Run defineEECProfile.m / autoTagElectricalComponents.m first.", numel(variants));
end

% --- Component BOM: dedupe by identity key (Manufacturer|PartNumber, or Name if PartNumber is blank) ---
identityKey = strings(height(rawComp), 1);
for r = 1:height(rawComp)
    if rawComp.PartNumber(r) ~= ""
        identityKey(r) = rawComp.Manufacturer(r) + "|" + rawComp.PartNumber(r);
    else
        identityKey(r) = "NAME:" + rawComp.Name(r);
    end
end
[uniqueKeys, ~, groupIdx] = unique(identityKey);
n = numel(uniqueKeys);

Component = strings(n,1); Kind = strings(n,1); Manufacturer = strings(n,1); PartNumber = strings(n,1);
SupplierPartNumber = strings(n,1); Description = strings(n,1); SearchHint = strings(n,1);
DriveTopology = strings(n,1); ConnectorFamily = strings(n,1); Variants = strings(n,1);
NumPorts = zeros(n,1); Conflicts = strings(n,1);
DatasheetURL = strings(n,1); DatasheetConfirmed = strings(n,1); ResearchNotes = strings(n,1);

for k = 1:n
    rows = rawComp(groupIdx == k, :);
    Component(k) = rows.Name(1);
    Kind(k) = rows.Kind(1);
    Manufacturer(k) = rows.Manufacturer(1);
    PartNumber(k) = rows.PartNumber(1);
    SupplierPartNumber(k) = rows.SupplierPartNumber(1);
    Description(k) = rows.Description(1);
    DriveTopology(k) = rows.DriveTopology(1);
    ConnectorFamily(k) = rows.ConnectorFamily(1);
    Variants(k) = strjoin(unique(rows.Variant), ", ");
    NumPorts(k) = rows.NumPorts(1);

    if PartNumber(k) ~= ""
        SearchHint(k) = strtrim(Manufacturer(k) + " " + PartNumber(k) + " datasheet");
    else
        SearchHint(k) = strtrim(Manufacturer(k) + " " + Component(k) + " " + Description(k) + " datasheet");
    end

    conflictBits = strings(0,1);
    if numel(unique(rows.Name)) > 1,         conflictBits(end+1) = "Name differs";         end %#ok<AGROW>
    if numel(unique(rows.Manufacturer)) > 1, conflictBits(end+1) = "Manufacturer differs"; end %#ok<AGROW>
    if numel(unique(rows.PartNumber)) > 1,   conflictBits(end+1) = "PartNumber differs";   end %#ok<AGROW>
    if numel(unique(rows.Description)) > 1,  conflictBits(end+1) = "Description differs";  end %#ok<AGROW>
    if numel(unique(rows.NumPorts)) > 1,     conflictBits(end+1) = "Port count differs";   end %#ok<AGROW>
    Conflicts(k) = strjoin(conflictBits, "; ");
end

componentBOM = table(Component, Kind, Manufacturer, PartNumber, SupplierPartNumber, Description, ...
    SearchHint, DriveTopology, ConnectorFamily, Variants, NumPorts, Conflicts, ...
    DatasheetURL, DatasheetConfirmed, ResearchNotes);
componentBOM = sortrows(componentBOM, {'Kind','Manufacturer','Component'});

signalChecklist = sortrows(rawSig, {'ComponentName','Variant','CavityNumber'});
signalChecklist.DatasheetNotes = strings(height(signalChecklist), 1);

compPath = fullfile(outputDir, nameBase + "_component_bom.csv");
sigPath = fullfile(outputDir, nameBase + "_signal_checklist.csv");
writetable(componentBOM, compPath);
writetable(signalChecklist, sigPath);

fprintf("exportDatasheetLookupBOM: %d distinct component(s) (%d tagged instance(s) across %d variant(s)), %d signal row(s)\n", ...
    n, height(rawComp), numel(variants), height(signalChecklist));
nConflict = sum(Conflicts ~= "");
if nConflict > 0
    fprintf(2, "  [WARN] %d component(s) tagged inconsistently across variants — see Conflicts column in %s\n", nConflict, compPath);
end
nNoPartNumber = sum(PartNumber == "");
if nNoPartNumber > 0
    fprintf("  %d component(s) have no PartNumber yet — Name/Description is the only search hint until one is tagged.\n", nNoPartNumber);
end
fprintf("Wrote:\n  %s  (%d rows)\n  %s  (%d rows)\n", compPath, height(componentBOM), sigPath, height(signalChecklist));

end

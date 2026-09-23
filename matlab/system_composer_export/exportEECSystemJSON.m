function summary = exportEECSystemJSON(variants, nameBase, outputDir)
%EXPORTEECSYSTEMJSON Export one EEDesignSolution "system" JSON file per
%   physical variant of a System Composer physical architecture.
%
%   summary = exportEECSystemJSON(variants, nameBase, outputDir)
%
%   variants   Struct array, one entry per physical variant, each with:
%                .ModelName  Name of a saved System Composer architecture
%                            model (.slx) tagged with the
%                            EEDesignSolutionProfile stereotypes (see
%                            defineEECProfile.m and collectTaggedElements.m).
%                .Label      Short variant tag, e.g. "BASE", "HD",
%                            "SMALL" — must be unique across VARIANTS.
%              Each model is one physical variant (the reliable,
%              version-agnostic pattern — see README.md "Variant
%              patterns" for the alternative of using native Simulink/
%              System Composer Variant blocks inside a single model).
%
%   nameBase   Logical system name shared by all variants, e.g.
%              "Steering_Assist". Files are written as
%              "<nameBase>__<Label>.eec-system-1.4.json".
%
%   outputDir  Where to write the files. Defaults to "library/systems"
%              relative to the current folder (this repo's convention —
%              see README.md section 4, "Library structure").
%
%   summary    Table with one row per variant: ModelName, Label, File,
%              NumDevices, NumSignals, OK, Message. Inspect this after
%              running to see what happened (this function does not
%              throw on a single variant's failure — it records the
%              failure in the table and continues with the rest — but it
%              DOES throw immediately for programmer errors such as
%              duplicate labels, since those indicate a broken call
%              rather than a bad model).
%
%   After running, add the new Ref-2X id(s) to library/platform.json and
%   an EEC_platform_add_system(&platform, "...") call in src/main.c (see
%   this folder's README.md, "Wiring the output into a build").
%
%   Example:
%       variants(1) = struct('ModelName', 'SteeringAssist_BASE', 'Label', "BASE");
%       variants(2) = struct('ModelName', 'SteeringAssist_HD',   'Label', "HD");
%       summary = exportEECSystemJSON(variants, "Steering_Assist", "library/systems");
%
%   See also: defineEECProfile, collectTaggedElements, buildEECSystemStruct.

if nargin < 3 || isempty(outputDir)
    outputDir = fullfile("library", "systems");
end
outputDir = string(outputDir);

labels = arrayfun(@(v) string(v.Label), variants);
if numel(unique(labels)) ~= numel(labels)
    error("exportEECSystemJSON:DuplicateLabel", ...
        "Variant labels must be unique, got: %s", strjoin(labels, ", "));
end

if ~isfolder(outputDir)
    mkdir(outputDir);
end

nameBase = string(nameBase);
n = numel(variants);
ModelName  = strings(n, 1);
Label      = strings(n, 1);
File       = strings(n, 1);
Ref2X      = strings(n, 1);
NumDevices = zeros(n, 1);
NumSignals = zeros(n, 1);
OK         = false(n, 1);
Message    = strings(n, 1);

for i = 1:n
    ModelName(i) = string(variants(i).ModelName);
    Label(i) = string(variants(i).Label);
    try
        [systemMeta, elements, sourceModelFile] = collectTaggedElements(ModelName(i));
        % Millisecond precision — see the matching comment in
        % buildEECSystemStruct.m's default exportedAt for why.
        exportedAt = string(datetime("now", "TimeZone", "UTC"), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");
        sysStruct = buildEECSystemStruct(systemMeta, elements, Label(i), nameBase, sourceModelFile, exportedAt);
        Ref2X(i) = string(sysStruct.REF2X_JSON_KEY);

        jsonText = jsonencode(sysStruct, "PrettyPrint", true);
        % See the REF2X_JSON_KEY comment in buildEECSystemStruct.m: this is
        % the one place the placeholder becomes the real "Ref-2X" JSON key.
        jsonText = strrep(jsonText, '"REF2X_JSON_KEY":', '"Ref-2X":');

        fileName = nameBase + "__" + Label(i) + ".eec-system-1.4.json";
        filePath = fullfile(outputDir, fileName);
        fid = fopen(filePath, "w");
        if fid < 0
            error("exportEECSystemJSON:WriteFailed", "Could not open '%s' for writing.", filePath);
        end
        fwrite(fid, jsonText, "char");
        fclose(fid);

        File(i) = filePath;
        NumDevices(i) = numel(sysStruct.devices);
        NumSignals(i) = sum(cellfun(@(d) numel(d.signals), sysStruct.devices));
        OK(i) = true;
        Message(i) = "OK";
        fprintf("[OK] %-8s -> %s  (%d device(s), %d signal(s))\n", ...
            Label(i), filePath, NumDevices(i), NumSignals(i));
    catch err
        OK(i) = false;
        Message(i) = string(err.message);
        fprintf(2, "[FAIL] %-8s (%s): %s\n", Label(i), ModelName(i), err.message);
    end
end

summary = table(ModelName, Label, File, Ref2X, NumDevices, NumSignals, OK, Message);

nOK = sum(OK);
fprintf("\n%d/%d variant(s) exported to %s\n", nOK, n, outputDir);
okRows = find(OK);
if ~isempty(okRows)
    fprintf("Next: add each Ref-2X below to library/platform.json \"systems\": [...] and call\n");
    fprintf("EEC_platform_add_system(&platform, \"...\") for it in src/main.c\n");
    fprintf("(see this folder's README.md for the full wiring steps):\n");
    for k = okRows(:)'
        fprintf("  %-8s -> Ref-2X = \"%s\"\n", Label(k), Ref2X(k));
    end
end

end

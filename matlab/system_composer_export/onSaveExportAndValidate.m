function onSaveExportAndValidate(modelName, label, nameBase, outputDir)
%ONSAVEEXPORTANDVALIDATE Re-export and re-validate one variant's system
%   JSON. Meant to be wired up as a model's PostSaveFcn callback via
%   installAutoExportOnSave.m, so every save of a tagged physical
%   architecture model keeps its JSON current automatically — the
%   traceability goal this folder is built around: the JSON should never
%   silently drift out of sync with the model that produced it.
%
%   onSaveExportAndValidate(modelName, label, nameBase, outputDir)
%
%   Same arguments as one entry of exportEECSystemJSON.m's `variants` plus
%   `nameBase`/`outputDir` — see installAutoExportOnSave.m, which is what
%   actually wires this function to a model's save event; you do not
%   normally call this directly.
%
%   Never throws: a PostSaveFcn callback that errors can interrupt the
%   model save workflow itself, which would be a worse outcome than a
%   failed auto-export. Every failure path is a warning instead, so the
%   save always completes; check the MATLAB console (or re-run
%   exportEECSystemJSON.m by hand) if you see one.
%
%   Only re-exports the ONE variant that owns this model — a multi-variant
%   system's other variants are untouched by this model's save (each
%   variant model gets its own installAutoExportOnSave.m call).
%
%   Deliberately does NOT re-run exportDatasheetLookupBOM.m: that CSV is
%   meant to be hand-edited (DatasheetURL, ResearchNotes...) as datasheets
%   are found, and silently overwriting it on every save would destroy
%   that work. Regenerate the BOM explicitly when you want an updated one.
%
%   See also: installAutoExportOnSave, exportEECSystemJSON, checkJsonFreshness.py.

if nargin < 4 || isempty(outputDir)
    outputDir = fullfile("library", "systems");
end

try
    variant = struct("ModelName", char(modelName), "Label", string(label));
    summary = exportEECSystemJSON(variant, string(nameBase), string(outputDir));
catch err
    warning("onSaveExportAndValidate:ExportError", ...
        "Auto-export on save of '%s' errored: %s", modelName, err.message);
    return
end

if ~summary.OK(1)
    warning("onSaveExportAndValidate:ExportFailed", ...
        "Auto-export on save of '%s' failed: %s", modelName, summary.Message(1));
    return
end

jsonPath = summary.File(1);
validatorScript = fullfile("tools", "scripts", "validate_system_json_code_aligned.py");
if ~isfile(validatorScript)
    fprintf("[auto-export] %s -> %s (validator script not found at %s — skipped)\n", ...
        modelName, jsonPath, validatorScript);
    return
end

[rc, out] = system(sprintf('python3 "%s" "%s"', validatorScript, jsonPath));
if rc == 0
    fprintf("[auto-export] %s -> %s (validated OK)\n", modelName, jsonPath);
else
    warning("onSaveExportAndValidate:ValidationFailed", ...
        "Auto-exported '%s' but validation FAILED:\n%s", jsonPath, out);
end

end

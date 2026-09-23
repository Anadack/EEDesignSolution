function installAutoExportOnSave(modelName, label, nameBase, outputDir)
%INSTALLAUTOEXPORTONSAVE Make saving this model re-export and re-validate
%   its system JSON automatically — the "if something changes, the JSON
%   stays up to date" half of traceability. The other half is
%   checkJsonFreshness.py, which detects the case where this was never
%   installed, was skipped, or errored quietly.
%
%   installAutoExportOnSave(modelName, label, nameBase, outputDir)
%
%   Run ONCE per variant model (after Step 1/2 in the folder README —
%   the model must already carry the EEDesignSolutionProfile tags).
%   Every subsequent Ctrl+S / File > Save of THIS model then:
%     1. Re-runs exportEECSystemJSON.m for this one variant.
%     2. Runs tools/scripts/validate_system_json_code_aligned.py on the
%        result.
%     3. Prints [auto-export] ... on success, or a MATLAB warning (never
%        an error — see onSaveExportAndValidate.m) if either step fails,
%        so a bad save is never silent but also never blocks the save
%        itself.
%
%   modelName, label, nameBase, outputDir   Same meaning as one entry of
%       exportEECSystemJSON.m's `variants` plus its own nameBase/outputDir
%       arguments. outputDir defaults to "library/systems".
%
%   Uses set_param(model, 'PostSaveFcn', ...) — ordinary Simulink model
%   callback machinery, unrelated to System Composer's own traversal API
%   (the one part of this pipeline with real cross-release risk — see
%   collectTaggedElements.m). PostSaveFcn has been stable Simulink API for
%   a very long time, so this file carries much less version risk than
%   collectTaggedElements.m/autoTagElectricalComponents.m do.
%
%   To remove: set_param(modelName, 'PostSaveFcn', '').
%
%   Example:
%       installAutoExportOnSave('BrakingSystem_ABS', "ABS", "Braking_System");
%
%   See also: onSaveExportAndValidate, exportEECSystemJSON, checkJsonFreshness.py.

if nargin < 4 || isempty(outputDir)
    outputDir = fullfile("library", "systems");
end

modelName = char(modelName);
if ~bdIsLoaded(modelName)
    error("installAutoExportOnSave:ModelNotOpen", ...
        "'%s' is not open. Open the model first, then run this again.", modelName);
end

callback = sprintf("onSaveExportAndValidate('%s', '%s', '%s', '%s');", ...
    modelName, char(label), char(nameBase), char(outputDir));
set_param(modelName, "PostSaveFcn", callback);

fprintf("Auto-export-on-save installed for '%s' (variant '%s').\n", modelName, label);
fprintf("Every save now re-writes and re-validates %s/%s__%s.eec-system-1.4.json\n", ...
    outputDir, nameBase, label);
fprintf("Save the model now (Ctrl+S) to make this callback itself persist in the .slx.\n");

end

# =============================================================================
# run.ps1 - E/E Architect Design full build + report pipeline (Windows/PowerShell)
#
# PowerShell equivalent of run.sh for environments without bash (native Windows
# + VS Code). Executes the same steps, in the same order:
#   1. Compile   - build the C framework binary (app.exe)
#   2. Run       - execute app.exe, refresh generated_doc/exports/
#   3. Arch HTML - architecture views (allocation, bus, signal-flow, pinout...)
#   4. Doc suite - signal dictionary, dataflow, safety trace, harness book...
#   5. Extras    - estimation, system config viewer, connector view
#   6. Draw.io   - print-ready .drawio exports (Polarion / A4)
#
# Usage (PowerShell terminal, repo root):
#   .\run.ps1                      full pipeline
#   .\run.ps1 -SkipBuild            reuse existing app.exe (re-run + reports only)
#   .\run.ps1 -SkipRun              rebuild app.exe but skip execution
#   .\run.ps1 -SkipBuild -SkipRun   reports only (need generated_doc/exports/ already present)
#
# Requirements:
#   - gcc on PATH (MinGW-w64 - e.g. the toolchain installed by the VS Code
#     "C/C++" extension Windows tutorial, or MSYS2's mingw-w64-gcc)
#   - A Python 3 interpreter on PATH (python, py, or python3)
#
# If Windows blocks the script with an execution-policy error, run it as:
#   powershell -ExecutionPolicy Bypass -File .\run.ps1
#
# Release packaging is intentionally EXCLUDED from this pipeline.
# To package a release run separately:
#   python tools\scripts\package_release.py
# =============================================================================

[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipRun
)

$ErrorActionPreference = "Stop"

$Root   = $PSScriptRoot
$Tools  = Join-Path $Root "tools\scripts"
$GenDir = Join-Path $Root "generated_doc"
$App    = Join-Path $Root "app.exe"

$WarnCount  = 0
$TotalSteps = 8

# -----------------------------------------------------------------------------
function Find-Python {
    foreach ($cand in @("python", "py", "python3")) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) { return $cand }
    }
    throw "No Python interpreter found on PATH (tried python, py, python3)."
}
$Python = Find-Python

function Step {
    param([int]$Number, [string]$Title)
    Write-Host ""
    Write-Host ("=" * 66)
    Write-Host ("  STEP {0}/{1}  {2}" -f $Number, $TotalSteps, $Title)
    Write-Host ("=" * 66)
}

function Invoke-PyRun {
    param([string]$Script)
    Write-Host "[PY]  $Script"
    Push-Location $Tools
    try {
        & $Python $Script --root $Root
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "$Script exited with errors"
            $script:WarnCount++
        }
    } finally {
        Pop-Location
    }
}

# =============================================================================
# STEP 1 - Compile C framework
# =============================================================================
Step 1 "Compile C framework"

if (-not $SkipBuild) {
    if (-not (Get-Command gcc -ErrorAction SilentlyContinue)) {
        throw "gcc not found on PATH. Install MinGW-w64 (MSYS2, or the VS Code 'C/C++' extension Windows tutorial) and ensure gcc.exe is on PATH."
    }

    $srcFiles = @(
        "src/main.c",
        "src/EEC_main_helpers.c",
        "src/EEC_library.c",
        "src/EEC_architecture.c",
        "src/EEC_verify.c",
        "src/EEC_export.c",
        "src/EEC_connect.c",
        "src/EEC_types.c",
        "src/EEC_agco.c",
        "src/EEC_log.c",
        "src/EEC_pin_helpers.c",
        "src/EEC_estimation.c",
        "src/EEC_component_loader.c",
        "src/EEC_naming.c",
        "src/EEC_message.c",
        "src/EEC_dbc.c",
        "src/EEC_datadict.c",
        "src/EEC_swc_loader.c",
        "src/EEC_zone.c"
    )

    Push-Location $Root
    try {
        & gcc -Iinc -Wall -Wextra -O2 @srcFiles -lm -o app.exe
        if ($LASTEXITCODE -ne 0) { throw "gcc compilation failed (exit $LASTEXITCODE)" }
        Write-Host "[OK]  Compiled -> $App"
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[SKIP] -SkipBuild: reusing existing binary"
}

# =============================================================================
# STEP 2 - Run C framework (populates generated_doc/exports/)
# =============================================================================
Step 2 "Run C framework - refresh generated_doc/exports/"

if (-not $SkipRun) {
    if (-not (Test-Path $App)) {
        throw "app.exe not found at $App - run without -SkipBuild first."
    }
    Push-Location $Root
    try {
        & $App
        if ($LASTEXITCODE -ne 0) { throw "app.exe exited with code $LASTEXITCODE" }
        Write-Host "[OK]  Framework run complete - generated_doc/exports/ updated"
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[SKIP] -SkipRun: using existing generated_doc/exports/"
}

# =============================================================================
# STEP 3 - Signal naming convention validation
# =============================================================================
Step 3 "Signal naming convention validation (SYSTEM_Function_[POSITION_]TYPE)"

Push-Location $Tools
try {
    & $Python "validate_signal_naming.py" --root $Root
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[INFO]  Naming warnings emitted above - pipeline continues"
    }
} finally {
    Pop-Location
}

# =============================================================================
# STEP 4 - Architecture HTML reports
#
# Runs the architecture-level suite via generate_all_reports.py:
#   - Signal-to-ECU allocation matrix
#   - Bus backbone diagram
#   - Bus topology diagram
#   - ECU pin-out tables
#   - Signal flow (v1 and v2)
#   - Architecture tree
#   - Wiring overview
#   - Logical architecture view
#   - Library ECU pin-out
# =============================================================================
Step 4 "Architecture HTML reports (allocation, bus, signal-flow, topology, wiring...)"

Push-Location $Tools
try {
    & $Python "generate_all_reports.py" --root $Root --continue-on-error
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Some architecture reports failed"
        $WarnCount++
    }
} finally {
    Pop-Location
}

# =============================================================================
# STEP 5 - Documentation suite
#
# Runs the full v4 documentation suite via generate_all_architecture_docs.py:
#   - Signal dictionary, communication matrix, dataflow diagrams
#   - Power distribution, grounding architecture
#   - Harness & connector book, wiring netlist
#   - Diagnostics matrix, safety concept trace
#   - Variant/option matrix, change impact report
#   - Architecture completeness report, full documentation index
# =============================================================================
Step 5 "Documentation suite - signal dictionary, dataflow, safety, harness..."

Push-Location $Tools
try {
    & $Python "generate_all_architecture_docs.py" --root $Root
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Some documentation reports failed"
        $WarnCount++
    }
} finally {
    Pop-Location
}

# =============================================================================
# STEP 6 - Standalone reports not covered by the suites above
# =============================================================================
Step 6 "Standalone reports - estimation, config viewer, connector view"

Invoke-PyRun "generate_estimation_html.py"
Invoke-PyRun "generate_system_configuration_viewer_html.py"
Invoke-PyRun "generate_connector_view_html.py"

# =============================================================================
# STEP 7 - Single-file architecture console (bundles every report above)
# =============================================================================
Step 7 "Architecture console - single-file bundle of every report"

Invoke-PyRun "generate_architecture_console_html.py"

# =============================================================================
# STEP 8 - Print-ready draw.io exports (Polarion / A4)
#
# Kept as its own non-fatal step (like STEP 6/7 above, via Invoke-PyRun)
# rather than folded into generate_all_architecture_docs.py: this format is
# still being validated against a real Polarion instance, so a problem here
# must never be able to fail the --strict documentation gate CI runs
# separately - see generate_drawio_exports.py's own docstring.
# =============================================================================
Step 8 "Print-ready draw.io exports (Polarion / A4)"

Invoke-PyRun "generate_drawio_exports.py"

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host ("=" * 66)
if ($WarnCount -gt 0) {
    Write-Host "  DONE - $WarnCount step(s) reported warnings (see above)"
} else {
    Write-Host "  ALL DONE - pipeline completed without errors"
}
Write-Host ""
Write-Host "  Exports : $GenDir\exports\"
Write-Host "  Reports : $GenDir\architecture_html\"
Write-Host "  Console : $GenDir\architecture_console.html  (single-file, all reports embedded)"
Write-Host "  Draw.io : $GenDir\drawio\  (Polarion / A4 print-ready)"
Write-Host ""
Write-Host "  Release packaging (separate step):"
Write-Host "    python tools\scripts\package_release.py"
Write-Host ("=" * 66)

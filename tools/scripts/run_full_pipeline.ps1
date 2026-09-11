# run_full_pipeline.ps1 - Build, run, then execute all Python tools.
# Called by the VS Code Build+Run task (Ctrl+Shift+B).

param(
    [string]$Compiler = "",
    [string]$Python   = ""
)

# Resolve GCC: prefer MinGW default, fall back to PATH
if (-not $Compiler) {
    if (Test-Path "C:/mingw64/bin/gcc.exe") {
        $Compiler = "C:/mingw64/bin/gcc.exe"
    } elseif (Test-Path "C:/msys64/mingw64/bin/gcc.exe") {
        $Compiler = "C:/msys64/mingw64/bin/gcc.exe"
    } else {
        $Compiler = "gcc"
    }
}

# Resolve Python: prefer project venv, fall back to system python
if (-not $Python) {
    if (Test-Path ".venv/Scripts/python.exe") {
        $Python = ".venv/Scripts/python.exe"
    } elseif (Test-Path ".venv/bin/python") {
        $Python = ".venv/bin/python"
    } else {
        $Python = "python3"
    }
}

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot/../..

# -- 1. Compile --
Write-Host "`n[DIR] $(Get-Location)" -ForegroundColor Cyan
$cFiles = (Get-ChildItem -Path src -Filter *.c).FullName
Write-Host "[SRC] $($cFiles.Count) .c files" -ForegroundColor Cyan
$cFiles | ForEach-Object { Write-Host "   - $_" }

& $Compiler -std=c11 -Wall -Wextra -pedantic -O2 -Iinc @cFiles -o app.exe
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[FAIL] Compilation error" -ForegroundColor Red
    exit 1
}
Write-Host "`n[OK] COMPILATION OK !" -ForegroundColor Green

# -- 2. Run app.exe --
& .\app.exe
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[FAIL] Execution error" -ForegroundColor Red
    exit 1
}

# -- 3. Python tools (skip generate_main_* wrappers, they are redundant) --
Write-Host "`n[PY] Running Python tools from tools/scripts/ ..." -ForegroundColor Cyan
$scripts = Get-ChildItem -Path tools/scripts -Filter *.py |
    Where-Object { $_.Name -notlike 'generate_main_*' -and $_.Name -notlike 'push_document_to_polarion.py' }
$failed = 0

foreach ($s in $scripts) {
    Write-Host "  > $($s.Name)" -ForegroundColor Yellow
    & $Python $s.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] $($s.Name)" -ForegroundColor Red
        $failed++
    } else {
        Write-Host "  [OK]   $($s.Name)" -ForegroundColor Green
    }
}

if ($failed -gt 0) {
    Write-Host "`n[FAIL] $failed script(s) failed" -ForegroundColor Red
    exit 1
} else {
    Write-Host "`n[OK] Build + Run + Tools : all good !" -ForegroundColor Green
}

# -- 4. Optional: Push Common Safety Concept to Polarion (non-blocking)
Write-Host "`n[POLARION] Attempting Polarion push (non-blocking)..." -ForegroundColor Cyan
$pushScript = Join-Path $PSScriptRoot "push_document_to_polarion.py"
if (Test-Path $pushScript) {
    $pushArgs = @('--file','Requierements/Common_Safety_Concept.txt','--document','CEA3_Common_Safety_Concept')
    Write-Host "  > python $pushScript $($pushArgs -join ' ')" -ForegroundColor Yellow
    & $Python $pushScript $pushArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] Polarion push failed or skipped (non-fatal). See generated_doc/exports/*.html." -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] Polarion push script finished." -ForegroundColor Green
    }
} else {
    Write-Host "  [SKIP] push_document_to_polarion.py not found." -ForegroundColor Yellow
}

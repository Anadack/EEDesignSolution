param(
    [string]$Compiler = "C:/mingw64/bin/gcc.exe"
)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot/..

$cFiles = Get-ChildItem -Path src -Filter *.c
$failed = 0

foreach ($f in $cFiles) {
    Write-Host "Analyzing $($f.Name)" -ForegroundColor Cyan
    & $Compiler -std=c11 -Iinc -fanalyzer -fmax-errors=200 -c $f.FullName
    if ($LASTEXITCODE -ne 0) { $failed++ }
}

if ($failed -gt 0) {
    Write-Host "Analyzer reported issues in $failed file(s)" -ForegroundColor Red
    exit 1
} else {
    Write-Host "No analyzer errors reported." -ForegroundColor Green
    exit 0
}

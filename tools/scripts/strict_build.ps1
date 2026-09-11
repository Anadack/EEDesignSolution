param(
    [string]$Compiler = ""
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

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot/..

# Collect C sources
$cFiles = (Get-ChildItem -Path src -Filter *.c).FullName
Write-Host "[DIR] $(Get-Location)"
Write-Host "[SRC] $($cFiles.Count) .c files"
$cFiles | ForEach-Object { Write-Host "   - $_" }

# Strict compile flags: treat warnings as errors
$flags = @(
    '-std=c11',
    '-Wall',
    '-Wextra',
    '-Wpedantic',
    '-Werror',
    '-Wshadow',
    '-Wformat',
    '-Wformat-security',
    '-Wmissing-prototypes',
    '-Wmissing-declarations',
    '-Wconversion',
    '-O2'
)

& $Compiler @flags -Iinc @cFiles -o app_strict.exe
exit $LASTEXITCODE

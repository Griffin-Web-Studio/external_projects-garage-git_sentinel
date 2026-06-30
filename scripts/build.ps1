# git-sentinel build.ps1 - builds the PyInstaller binary into
# dist\git-sentinel.exe
# Run from the project root directory.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: uv is not installed."
    Write-Error "       Install it from: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
}

if (-not (Test-Path "$ProjectRoot\pyproject.toml")) {
    Write-Error "ERROR: pyproject.toml not found in $ProjectRoot"
    exit 1
}

Write-Host "Syncing build dependencies..."
Set-Location $ProjectRoot
uv sync --group dev

Write-Host "Generating icon..."
uv run python scripts\gen-ico.py

Write-Host "Building binary (this may take a minute)..."
uv run pyinstaller `
    --onefile `
    --name git-sentinel `
    --distpath dist `
    --workpath build `
    --specpath build `
    --icon "$ProjectRoot\build\git-sentinel.ico" `
    --collect-submodules src.migrations `
    git-sentinel

if (-not (Test-Path "$ProjectRoot\dist\git-sentinel.exe")) {
    Write-Error "ERROR: build failed - dist\git-sentinel.exe not found"
    exit 1
}

Write-Host "Build complete -> $ProjectRoot\dist\git-sentinel.exe"

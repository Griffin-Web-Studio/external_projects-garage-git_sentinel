# git-sentinel setup.ps1 - prepares the local dev environment. Run once after
# cloning, from the project root directory.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $PSScriptRoot

# ───────────────────────────────────────────────────────| Environment Setup |──

# Install uv via pipx if not already available
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
        Write-Error "ERROR: Neither 'uv' nor 'pipx' is installed or on PATH."
        Write-Error "       Install pipx: https://pipx.pypa.io/stable/installation/"
        Write-Error "       Or install uv directly: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
    pipx install uv
}

# Install all dependencies
uv sync --all-extras

# Activate virtual python environment
& (Join-Path $ScriptDir '.venv\Scripts\Activate.ps1')

# ────────────────────────────────────────────────────────| Pre-commit hooks |──

if (-not (Get-Command pre-commit -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: pre-commit is not installed."
    Write-Error "       Install it with: pip install pre-commit or look for errors"
    Write-Error "       above as UV should have been already installed and"
    Write-Error "       activated, which means there's another issue."
    exit 1
}

Write-Host "Installing pre-commit hooks..."
Push-Location $ScriptDir
try {
    pre-commit install
    pre-commit install --hook-type commit-msg
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Dev environment ready."

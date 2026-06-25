# local-run.ps1 - build, install, and force-launch git-sentinel locally.
# Run from any directory.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "==> Building..."
& "$ScriptDir\build.ps1"

Write-Host "==> Installing..."
& "$ProjectRoot\dist\git-sentinel.exe"

Write-Host "==> Running..."
& "$HOME\.local\bin\git-sentinel.exe" --force

# install.ps1 — Windows thin wrapper. Locates a Python interpreter and execs install.py.
# This file is a sibling of install.py under bootstrap\.
#
# Usage: powershell -ExecutionPolicy Bypass -File bootstrap\install.ps1 [install.py args...]
# (Script is not signed; ExecutionPolicy Bypass required on default Windows setups.)
$ErrorActionPreference = "Stop"

# $PSScriptRoot is robust against dot-sourcing (PS 3.0+, always present on Win 11).
$Script = Join-Path $PSScriptRoot "install.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $Script @args
  exit $LASTEXITCODE
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  & python $Script @args
  exit $LASTEXITCODE
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  & python3 $Script @args
  exit $LASTEXITCODE
} else {
  # Write-Error under ErrorActionPreference=Stop is a terminating throw — exit 127
  # would be unreachable. Use [Console]::Error.WriteLine to keep exit 127 reachable
  # and preserve the POSIX "command not found" sentinel.
  [Console]::Error.WriteLine("install.ps1: python3 is required (py / python / python3 not found on PATH)")
  exit 127
}

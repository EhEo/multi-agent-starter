# install.ps1 — Windows thin wrapper. Locates a Python interpreter and execs install.py.
# This file is a sibling of install.py under bootstrap\.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "install.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $Script @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  & python $Script @args
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  & python3 $Script @args
} else {
  Write-Error "python3 is required (py / python / python3 not found on PATH)"
  exit 127
}

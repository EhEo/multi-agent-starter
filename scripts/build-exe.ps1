# MultiAgentSetup.exe 빌드 스크립트 — PS2EXE 사용
#Requires -Version 5.1
<#
.SYNOPSIS
    install.ps1 → dist\MultiAgentSetup.exe 빌드
.DESCRIPTION
    PS2EXE 모듈이 없으면 자동 설치 후 컴파일합니다.
    출력: dist\MultiAgentSetup.exe (더블클릭 또는 터미널에서 실행 가능)
.EXAMPLE
    .\scripts\build-exe.ps1
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$src  = Join-Path $root "install.ps1"
$dist = Join-Path $root "dist"
$out  = Join-Path $dist "MultiAgentSetup.exe"

# PS2EXE 설치 확인
if (-not (Get-Module -ListAvailable PS2EXE)) {
    Write-Host "PS2EXE 모듈 설치 중..." -ForegroundColor Cyan
    Install-Module PS2EXE -Force -Scope CurrentUser -ErrorAction Stop
    Write-Host "PS2EXE 설치 완료" -ForegroundColor Green
}

# dist 폴더 생성
if (-not (Test-Path $dist)) {
    New-Item -ItemType Directory -Path $dist | Out-Null
}

# 빌드
Write-Host "빌드 중: $src → $out" -ForegroundColor Cyan

Invoke-PS2EXE `
    -InputFile  $src `
    -OutputFile $out `
    -Title       "MultiAgent Starter 설치 마법사" `
    -Description "multi-agent-starter Windows 설치 프로그램" `
    -Company     "multi-agent-starter" `
    -Version     "1.0.0.0" `
    -Copyright   "2025" `
    -RequireAdmin:$false

if (Test-Path $out) {
    $size = [math]::Round((Get-Item $out).Length / 1KB, 1)
    Write-Host ""
    Write-Host "빌드 완료: $out ($size KB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "사용법:" -ForegroundColor White
    Write-Host "  더블클릭     MultiAgentSetup.exe" -ForegroundColor Gray
    Write-Host "  점검만 실행  MultiAgentSetup.exe -CheckOnly" -ForegroundColor Gray
} else {
    Write-Error "빌드 실패 — 출력 파일이 없습니다."
}

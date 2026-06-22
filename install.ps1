# 윈도우 환경에서 multi-agent-starter 시스템을 자동 설치하는 스크립트
#Requires -Version 5.1
<#
.SYNOPSIS
    MultiAgent Starter — Windows 자동 설치 스크립트
.DESCRIPTION
    multi-agent-starter 실행에 필요한 모든 구성 요소를 자동 설치합니다.
    이미 설치된 항목은 건너뛰고, 수동 설치가 필요한 항목은 안내합니다.
.EXAMPLE
    PowerShell에서 repo 루트에서: .\install.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

# ════════════════════════════════════════════════════════════════════
#  출력 헬퍼
# ════════════════════════════════════════════════════════════════════
function Write-Banner {
    $w = [Math]::Max(50, $Host.UI.RawUI.WindowSize.Width - 4)
    $line = "═" * $w
    Write-Host ""
    Write-Host "  $line" -ForegroundColor Cyan
    Write-Host "   MultiAgent Starter — Windows 설치 스크립트" -ForegroundColor Cyan
    Write-Host "  $line" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step  { param([string]$Title) Write-Host "`n▶  $Title" -ForegroundColor White }
function Write-OK    { param([string]$Msg)   Write-Host "  [✓] $Msg" -ForegroundColor Green }
function Write-Skip  { param([string]$Msg)   Write-Host "  [~] $Msg" -ForegroundColor Cyan }
function Write-Warn  { param([string]$Msg)   Write-Host "  [!] $Msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$Msg)   Write-Host "  [✗] $Msg" -ForegroundColor Red }
function Write-Info  { param([string]$Msg)   Write-Host "      $Msg" -ForegroundColor Gray }

function Write-Guidance {
    param(
        [string]   $Tool,
        [string]   $Desc,
        [string]   $Url,
        [string[]] $Steps,
        [switch]   $Required
    )
    $label = if ($Required) { "필수" } else { "선택" }
    $color = if ($Required) { "Yellow" } else { "DarkYellow" }
    Write-Host ""
    Write-Host "  ┌─ $Tool 설치 안내 ($label) " -ForegroundColor $color -NoNewline
    Write-Host "─────────────────────" -ForegroundColor DarkGray
    Write-Host "  │  $Desc" -ForegroundColor Gray
    Write-Host "  │  $Url" -ForegroundColor Blue
    if ($Steps) {
        Write-Host "  │  설치 방법:" -ForegroundColor Gray
        foreach ($s in $Steps) { Write-Host "  │    $s" -ForegroundColor Gray }
    }
    Write-Host "  └──────────────────────────────────────────────" -ForegroundColor DarkGray
}

# ════════════════════════════════════════════════════════════════════
#  유틸리티
# ════════════════════════════════════════════════════════════════════
function Test-Cmd ([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-CmdPath ([string]$Name) {
    $c = Get-Command $Name -ErrorAction SilentlyContinue
    return if ($c) { $c.Source } else { $null }
}

function Add-UserPath ([string]$Dir) {
    if (-not (Test-Path $Dir)) { return $false }
    $cur = [Environment]::GetEnvironmentVariable("PATH", "User") ?? ""
    if ($cur -like "*$Dir*") { return $false }
    [Environment]::SetEnvironmentVariable("PATH", "$Dir;$cur", "User")
    if ($env:PATH -notlike "*$Dir*") { $env:PATH = "$Dir;$env:PATH" }
    return $true
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("PATH", "Machine") ?? ""
    $user    = [Environment]::GetEnvironmentVariable("PATH", "User")   ?? ""
    $env:PATH = "$machine;$user"
}

function Get-PythonUserScripts {
    try {
        $s = python -c "import sysconfig; print(sysconfig.get_path('scripts','nt_user'))" 2>$null
        return $s.Trim()
    } catch { return $null }
}

# ════════════════════════════════════════════════════════════════════
#  설치 상태 추적
# ════════════════════════════════════════════════════════════════════
$installed = @()
$manualNeeded = @()
$warnings = @()

# ════════════════════════════════════════════════════════════════════
#  실행 시작
# ════════════════════════════════════════════════════════════════════
Write-Banner

$repoRoot    = $PSScriptRoot
$pyProjectPath = Join-Path $repoRoot "pyproject.toml"
$hasPyProject  = Test-Path $pyProjectPath

if (-not $hasPyProject) {
    Write-Fail "pyproject.toml을 찾을 수 없습니다."
    Write-Info "이 스크립트는 multi-agent-starter repo 루트에서 실행해야 합니다."
    Write-Info "예: cd D:\GitRepos\multi-agent-starter && .\install.ps1"
    exit 1
}
Write-Info "Repo: $repoRoot"

# ════════════════════════════════════════════════════════════════════
#  STEP 1: winget 확인
# ════════════════════════════════════════════════════════════════════
Write-Step "1/7  winget 확인"
if (Test-Cmd "winget") {
    $wv = (winget --version 2>&1)
    Write-OK "winget $wv"
} else {
    Write-Warn "winget 미설치 — 일부 항목을 자동 설치할 수 없습니다."
    Write-Info "Microsoft Store에서 '앱 설치 관리자'를 설치하거나"
    Write-Info "https://aka.ms/getwinget 에서 직접 설치하세요."
    $warnings += "winget 없음 — 자동 설치 일부 제한"
}

# ════════════════════════════════════════════════════════════════════
#  STEP 2: Python 확인 / 설치
# ════════════════════════════════════════════════════════════════════
Write-Step "2/7  Python 확인"
if (Test-Cmd "python") {
    $pyVer  = (python --version 2>&1).ToString().Trim()
    $pyPath = Get-CmdPath "python"
    Write-Skip "이미 설치됨: $pyVer"
    Write-Info "경로: $pyPath"
} else {
    if (Test-Cmd "winget") {
        Write-Info "Python 3.12를 winget으로 설치합니다 (잠시 기다려 주세요)..."
        winget install --id Python.Python.3.12 --silent `
              --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
        Refresh-Path
        if (Test-Cmd "python") {
            $pyVer = (python --version 2>&1).ToString().Trim()
            Write-OK "Python 설치 완료: $pyVer"
            $installed += "Python 3.12"
        } else {
            Write-Warn "설치 후 PowerShell을 재시작하고 이 스크립트를 다시 실행하세요."
            $warnings += "Python 설치 후 재시작 필요"
        }
    } else {
        Write-Fail "Python 미설치"
        Write-Guidance "Python 3.12" "멀티에이전트 시스템의 핵심 런타임" `
            "https://www.python.org/downloads/" `
            @("1. 위 URL에서 Python 3.12 설치 파일 다운로드",
              "2. 설치 시 하단 'Add Python to PATH' 체크박스 반드시 선택",
              "3. 설치 완료 후 이 스크립트를 다시 실행") -Required
        $manualNeeded += "Python 3.12"
    }
}

# ════════════════════════════════════════════════════════════════════
#  STEP 3: pip 확인
# ════════════════════════════════════════════════════════════════════
Write-Step "3/7  pip 확인"
if (Test-Cmd "pip") {
    $pipVer = (pip --version 2>&1).ToString().Trim()
    Write-Skip "이미 설치됨: $pipVer"
} elseif (Test-Cmd "python") {
    Write-Info "pip 설치 중..."
    python -m ensurepip --upgrade 2>&1 | Out-Null
    python -m pip install --upgrade pip 2>&1 | Out-Null
    Refresh-Path
    if (Test-Cmd "pip") {
        Write-OK "pip 설치/업그레이드 완료"
        $installed += "pip"
    } else {
        Write-Warn "pip 설치 실패 — python -m pip 으로 대체 사용합니다."
        $warnings += "pip 명령 없음 (python -m pip 사용 필요)"
    }
} else {
    Write-Warn "Python이 없어 pip를 설치할 수 없습니다."
}

# ════════════════════════════════════════════════════════════════════
#  STEP 4: 구버전 충돌 파일 감지
# ════════════════════════════════════════════════════════════════════
Write-Step "4/7  충돌 파일 감지"
$staleScript = Join-Path $env:USERPROFILE ".local\bin\multiagent"
if (Test-Path $staleScript) {
    $content = Get-Content $staleScript -TotalCount 2 -ErrorAction SilentlyContinue
    $isBash  = ($content -join "") -match "#!/usr/bin/env bash"
    if ($isBash) {
        Write-Warn "구버전 bash 스크립트 발견: $staleScript"
        Write-Info "이 파일이 PowerShell에서 'multiagent' 실행 시 충돌을 일으킵니다."
        $answer = Read-Host "      제거하시겠습니까? [Y/N]"
        if ($answer -match "^[Yy]") {
            Remove-Item $staleScript -Force
            Write-OK "구버전 스크립트 제거 완료"
            $installed += "구버전 bash 스크립트 제거"
        } else {
            Write-Warn "건너뜀 — PowerShell에서 실행 시 충돌이 발생할 수 있습니다."
            $warnings += ".local\bin\multiagent 구버전 스크립트 충돌 가능"
        }
    } else {
        Write-Skip ".local\bin\multiagent 있지만 bash 스크립트 아님 — 유지"
    }
} else {
    Write-OK "충돌 파일 없음"
}

# ════════════════════════════════════════════════════════════════════
#  STEP 5: multiagent-cli 설치 + PATH 등록
# ════════════════════════════════════════════════════════════════════
Write-Step "5/7  multiagent-cli 설치"
if (Test-Cmd "python") {
    Write-Info "pip install -e . 실행 중..."
    $pipOut = pip install -e . --user 2>&1
    $errors = $pipOut | Where-Object { $_ -match "ERROR" }
    if ($errors) {
        Write-Fail "설치 오류:"
        $errors | ForEach-Object { Write-Info $_ }
    } else {
        Write-OK "multiagent-cli 설치 완료"
        $installed += "multiagent-cli"
    }

    # Python Scripts PATH 등록
    $scriptsDir = Get-PythonUserScripts
    if ($scriptsDir) {
        if (Add-UserPath $scriptsDir) {
            Write-OK "PATH 등록: $scriptsDir"
            $installed += "PATH 등록 ($scriptsDir)"
        } else {
            Write-Skip "이미 PATH에 있음: $scriptsDir"
        }
    }

    # 현재 세션 PATH 갱신 후 명령 확인
    Refresh-Path
    if (Test-Cmd "multiagent") {
        Write-OK "multiagent 명령 확인"
    } else {
        Write-Warn "multiagent 명령을 아직 찾을 수 없습니다."
        Write-Info "PowerShell을 재시작한 후 'multiagent --help'로 확인하세요."
        $warnings += "PowerShell 재시작 후 multiagent 명령 활성화"
    }
    if (Test-Cmd "mat") {
        Write-OK "mat 명령 확인"
    }
} else {
    Write-Warn "Python이 없어 multiagent-cli 설치를 건너뜁니다."
    $warnings += "Python 설치 후 이 스크립트를 다시 실행하세요"
}

# ════════════════════════════════════════════════════════════════════
#  STEP 6: Node.js 확인 (Claude Code 의존성)
# ════════════════════════════════════════════════════════════════════
Write-Step "6/7  Node.js 확인 (Claude Code 의존성)"
if (Test-Cmd "node") {
    $nodeVer = (node --version 2>&1).ToString().Trim()
    Write-Skip "이미 설치됨: Node.js $nodeVer"
} else {
    if (Test-Cmd "winget") {
        Write-Info "Node.js LTS를 winget으로 설치합니다..."
        winget install --id OpenJS.NodeJS.LTS --silent `
              --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
        Refresh-Path
        if (Test-Cmd "node") {
            $nodeVer = (node --version 2>&1).ToString().Trim()
            Write-OK "Node.js 설치 완료: $nodeVer"
            $installed += "Node.js LTS"
        } else {
            Write-Warn "Node.js 설치 후 PowerShell을 재시작하세요."
            $warnings += "Node.js 설치 후 재시작 필요"
        }
    } else {
        Write-Warn "Node.js 미설치 — Claude Code 설치에 필요합니다."
        Write-Info "https://nodejs.org 에서 LTS 버전을 설치하세요."
        $warnings += "Node.js 수동 설치 필요"
    }
}

# ════════════════════════════════════════════════════════════════════
#  STEP 7: AI CLI 도구 확인 및 안내
# ════════════════════════════════════════════════════════════════════
Write-Step "7/7  AI CLI 도구 확인"

# ── Claude Code ───────────────────────────────────────────────────
if (Test-Cmd "claude") {
    $cv = (claude --version 2>&1).ToString().Trim()
    Write-Skip "Claude Code 이미 설치됨: $cv"
} else {
    Write-Warn "Claude Code 미설치"
    Write-Guidance "Claude Code (필수)" `
        "멀티에이전트 오케스트레이터 기본 엔진 — Anthropic 계정 필요" `
        "https://claude.ai/code" `
        @("1. npm install -g @anthropic-ai/claude-code",
          "2. 터미널에서 claude 실행 → Anthropic 계정으로 로그인",
          "3. Claude Pro / Max 구독 필요 (또는 API 키 사용)") -Required
    $manualNeeded += "Claude Code"
}

# ── Codex CLI ─────────────────────────────────────────────────────
if (Test-Cmd "codex") {
    $cv = (codex --version 2>&1).ToString().Trim()
    Write-Skip "Codex CLI 이미 설치됨: $cv"
} else {
    Write-Warn "Codex CLI 미설치 (선택 사항)"
    Write-Guidance "OpenAI Codex CLI" `
        "codex-main / codex-critic 워커 사용 시 필요 — OpenAI 계정 필요" `
        "https://github.com/openai/codex" `
        @("1. npm install -g @openai/codex",
          "2. OPENAI_API_KEY 환경변수 설정",
          "   PowerShell: [Environment]::SetEnvironmentVariable('OPENAI_API_KEY','sk-...','User')")
    $manualNeeded += "Codex CLI (선택)"
}

# ── Antigravity CLI ───────────────────────────────────────────────
if (Test-Cmd "agy") {
    $av = (agy --version 2>&1).ToString().Trim()
    Write-Skip "Antigravity(agy) 이미 설치됨: $av"
} else {
    Write-Warn "Antigravity(agy) 미설치 (선택 사항)"
    Write-Guidance "Antigravity CLI (agy)" `
        "gemini 워커 / antigravity 오케스트레이터 사용 시 필요" `
        "https://antigravity.ai" `
        @("1. Antigravity 공식 사이트에서 Windows 설치 파일 다운로드",
          "2. 설치 후 agy install 실행하여 셸 경로 등록")
    $manualNeeded += "Antigravity CLI (선택)"
}

# ════════════════════════════════════════════════════════════════════
#  최종 요약
# ════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  ════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   설치 완료 요약" -ForegroundColor Cyan
Write-Host "  ════════════════════════════════════════════════" -ForegroundColor Cyan

if ($installed.Count -gt 0) {
    Write-Host ""
    Write-Host "  ✓ 이번에 설치/처리된 항목:" -ForegroundColor Green
    $installed | ForEach-Object { Write-Host "      · $_" -ForegroundColor Green }
}

if ($manualNeeded.Count -gt 0) {
    Write-Host ""
    Write-Host "  ! 수동 설치가 필요한 항목:" -ForegroundColor Yellow
    $manualNeeded | ForEach-Object { Write-Host "      · $_" -ForegroundColor Yellow }
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "  ~ 주의 사항:" -ForegroundColor Cyan
    $warnings | ForEach-Object { Write-Host "      · $_" -ForegroundColor Cyan }
}

Write-Host ""
Write-Host "  다음 명령으로 시작하세요 (PowerShell 재시작 후):" -ForegroundColor White
Write-Host "    multiagent              # 현재 폴더에 시스템 구성 후 claude 실행" -ForegroundColor Gray
Write-Host "    multiagent mat          # mat 모니터를 새 창에서 실행" -ForegroundColor Gray
Write-Host "    multiagent --help       # 전체 옵션 보기" -ForegroundColor Gray
Write-Host ""
Write-Host "  PATH 변경 반영을 위해 PowerShell을 새로 여세요." -ForegroundColor Yellow
Write-Host ""

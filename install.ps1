# 윈도우 환경에서 multi-agent-starter를 설치하는 단계별 설치 스크립트
#Requires -Version 5.1
<#
.SYNOPSIS
    MultiAgent Starter — Windows 설치 스크립트 (PowerShell 5.1 이상)
.DESCRIPTION
    1단계: 현재 PC 설치 상태를 전체 점검
    2단계: 누락/불일치 항목만 설치
    -CheckOnly 스위치로 점검만 실행할 수 있습니다.
.EXAMPLE
    .\install.ps1              # 점검 후 설치
    .\install.ps1 -CheckOnly   # 점검만 (설치 안 함)
#>
param(
    [switch]$CheckOnly
)

Set-StrictMode -Off
$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"
[Console]::OutputEncoding = [Console]::InputEncoding = [System.Text.Encoding]::UTF8

# ════════════════════════════════════════════════════════════════
#  출력 헬퍼
# ════════════════════════════════════════════════════════════════
function Write-Banner {
    $w = 54
    try { $w = [Math]::Max(54, $Host.UI.RawUI.WindowSize.Width - 4) } catch {}
    $line = "=" * $w
    Write-Host ""
    Write-Host "  $line" -ForegroundColor Cyan
    Write-Host "   MultiAgent Starter -- Windows 설치 마법사" -ForegroundColor Cyan
    Write-Host "  $line" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section { param([string]$Title)
    Write-Host ""
    Write-Host "  [ $Title ]" -ForegroundColor White
    Write-Host ("  " + ("─" * ([Math]::Max(40, $Title.Length + 4)))) -ForegroundColor DarkGray
}

function Write-OK    { param([string]$M) Write-Host ("  [OK]   " + $M) -ForegroundColor Green }
function Write-Skip  { param([string]$M) Write-Host ("  [SKIP] " + $M) -ForegroundColor Cyan }
function Write-Warn  { param([string]$M) Write-Host ("  [!]    " + $M) -ForegroundColor Yellow }
function Write-Fail  { param([string]$M) Write-Host ("  [X]    " + $M) -ForegroundColor Red }
function Write-Info  { param([string]$M) Write-Host ("         " + $M) -ForegroundColor Gray }
function Write-Guide { param([string]$M) Write-Host ("  >>     " + $M) -ForegroundColor Blue }

function Write-Guidance {
    param([string]$Tool, [string]$Desc, [string]$Url, [string[]]$Steps, [switch]$Required)
    $label = if ($Required) { "필수" } else { "선택" }
    Write-Host ""
    Write-Host ("  +-- " + $Tool + " 설치 안내 [" + $label + "] " + ("-" * 30)) -ForegroundColor Yellow
    Write-Host ("  |   " + $Desc) -ForegroundColor Gray
    Write-Host ("  |   " + $Url) -ForegroundColor Blue
    foreach ($s in $Steps) { Write-Host ("  |   " + $s) -ForegroundColor Gray }
    Write-Host ("  " + ("+" + "-" * 50)) -ForegroundColor DarkGray
}

function Prompt-Continue {
    param([string]$Msg = "계속하려면 Enter를 누르세요...")
    Write-Host ""
    Write-Host ("  " + $Msg) -ForegroundColor DarkYellow -NoNewline
    $null = Read-Host
}

# ════════════════════════════════════════════════════════════════
#  유틸리티 (PowerShell 5.1 호환 — ?? 연산자 미사용)
# ════════════════════════════════════════════════════════════════
function Test-Cmd ([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-CmdPath ([string]$Name) {
    $c = Get-Command $Name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source } else { return $null }
}

function Add-UserPath ([string]$Dir) {
    if (-not (Test-Path $Dir)) { return $false }
    $cur = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($null -eq $cur) { $cur = "" }
    if ($cur -like ("*" + $Dir + "*")) { return $false }
    [Environment]::SetEnvironmentVariable("PATH", ($Dir + ";" + $cur), "User")
    if ($env:PATH -notlike ("*" + $Dir + "*")) { $env:PATH = ($Dir + ";" + $env:PATH) }
    return $true
}

function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable("PATH", "Machine")
    $u = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($null -eq $m) { $m = "" }
    if ($null -eq $u) { $u = "" }
    $env:PATH = ($m + ";" + $u)
}

function Get-PythonUserScripts {
    if (-not (Test-Cmd "python")) { return $null }
    try {
        $s = python -c "import sysconfig; print(sysconfig.get_path('scripts','nt_user'))" 2>$null
        if ($s) { return $s.Trim() } else { return $null }
    } catch { return $null }
}

function Remove-StaleScript ([string]$Path) {
    if (-not (Test-Path $Path)) { return $false }
    try {
        $lines = Get-Content $Path -TotalCount 2 -ErrorAction SilentlyContinue
        $content = if ($lines) { $lines -join "" } else { "" }
        return ($content -match "#!/usr/bin/env bash")
    } catch { return $false }
}

# ════════════════════════════════════════════════════════════════
#  PHASE 1: 전체 사전 점검 (시스템 무변경)
# ════════════════════════════════════════════════════════════════
function Invoke-PreflightCheck {
    $result = @{
        winget        = $false; wingetVer    = ""
        python        = $false; pythonVer    = ""; pythonPath   = ""
        pip           = $false; pipVer       = ""
        nodejs        = $false; nodeVer      = ""
        git           = $false; gitVer       = ""
        multiagent    = $false
        mat           = $false
        claude        = $false; claudeVer    = ""
        codex         = $false; codexVer     = ""
        agy           = $false; agyVer       = ""
        staleScript   = $false; stalePath    = ""
        scriptsInPath = $false; scriptsDir   = ""
        inRepo        = $false; repoPath     = ""
    }

    # winget
    if (Test-Cmd "winget") {
        $result.winget = $true
        try { $result.wingetVer = (winget --version 2>&1).ToString().Trim() } catch {}
    }

    # Python
    $pyPath = Get-CmdPath "python"
    if ($pyPath) {
        $result.python = $true
        $result.pythonPath = $pyPath
        try { $result.pythonVer = (python --version 2>&1).ToString().Trim() } catch {}
    }

    # pip
    if (Test-Cmd "pip") {
        $result.pip = $true
        try {
            $pipOut = pip --version 2>&1
            $pipLine = if ($pipOut -is [array]) { $pipOut[0].ToString() } else { $pipOut.ToString() }
            $result.pipVer = ($pipLine -split "\s+")[1]
        } catch {}
    }

    # Node.js
    if (Test-Cmd "node") {
        $result.nodejs = $true
        try { $result.nodeVer = (node --version 2>&1).ToString().Trim() } catch {}
    }

    # Git
    if (Test-Cmd "git") {
        $result.git = $true
        try { $result.gitVer = (git --version 2>&1).ToString().Trim() } catch {}
    }

    # multiagent / mat
    $result.multiagent = (Test-Cmd "multiagent")
    $result.mat        = (Test-Cmd "mat")

    # Claude Code
    if (Test-Cmd "claude") {
        $result.claude = $true
        try { $result.claudeVer = (claude --version 2>&1).ToString().Trim() } catch {}
    }

    # Codex
    if (Test-Cmd "codex") {
        $result.codex = $true
        try { $result.codexVer = (codex --version 2>&1).ToString().Trim() } catch {}
    }

    # Antigravity
    if (Test-Cmd "agy") {
        $result.agy = $true
        try { $result.agyVer = (agy --version 2>&1).ToString().Trim() } catch {}
    }

    # 구버전 bash 스크립트
    $stalePath = Join-Path $env:USERPROFILE ".local\bin\multiagent"
    if (Remove-StaleScript $stalePath) {
        $result.staleScript = $true
        $result.stalePath   = $stalePath
    }

    # Python Scripts in PATH
    $sd = Get-PythonUserScripts
    if ($sd) {
        $result.scriptsDir   = $sd
        $curPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        if ($null -eq $curPath) { $curPath = "" }
        $result.scriptsInPath = ($curPath -like ("*" + $sd + "*"))
    }

    # Repo check — PS2EXE exe 실행 시 $PSScriptRoot가 빈 문자열일 수 있으므로 방어 처리
    $_root = $PSScriptRoot
    if (-not $_root -and $PSCommandPath) { $_root = Split-Path $PSCommandPath -Parent }
    if (-not $_root) { $_root = (Get-Location).Path }
    $result.inRepo = ($_root -and (Test-Path (Join-Path $_root "pyproject.toml")))
    if ($result.inRepo) { $result.repoPath = $_root }

    return $result
}

function Show-PreflightReport ([hashtable]$r) {
    Write-Section "현재 PC 설치 상태 점검"

    # 도구별 상태
    $items = @(
        @{ name = "winget";        ok = $r.winget;     ver = $r.wingetVer;   note = "패키지 관리자" }
        @{ name = "Python";        ok = $r.python;     ver = $r.pythonVer;   note = $r.pythonPath }
        @{ name = "pip";           ok = $r.pip;        ver = ("v" + $r.pipVer); note = "" }
        @{ name = "Node.js";       ok = $r.nodejs;     ver = $r.nodeVer;     note = "Claude Code 의존성" }
        @{ name = "Git";           ok = $r.git;        ver = $r.gitVer;      note = "" }
        @{ name = "multiagent";    ok = $r.multiagent; ver = "";             note = "" }
        @{ name = "mat";           ok = $r.mat;        ver = "";             note = "" }
        @{ name = "Claude Code";   ok = $r.claude;     ver = $r.claudeVer;   note = "[필수] Anthropic 계정 필요" }
        @{ name = "Codex CLI";     ok = $r.codex;      ver = $r.codexVer;    note = "[선택] OpenAI 계정 필요" }
        @{ name = "Antigravity";   ok = $r.agy;        ver = $r.agyVer;      note = "[선택]" }
    )

    foreach ($item in $items) {
        $ver  = if ($item.ver)  { "  " + $item.ver } else { "" }
        $note = if ($item.note) { "  (" + $item.note + ")" } else { "" }
        if ($item.ok) {
            Write-OK ($item.name + $ver + $note)
        } else {
            Write-Fail ($item.name + "  미설치" + $note)
        }
    }

    # 경고 항목
    if ($r.staleScript) {
        Write-Host ""
        Write-Warn ("구버전 bash 스크립트 발견: " + $r.stalePath)
        Write-Info "PowerShell에서 multiagent 실행 시 충돌을 일으킵니다."
    }

    if ($r.python -and -not $r.scriptsInPath) {
        Write-Host ""
        Write-Warn "Python Scripts 폴더가 PATH에 없습니다."
        Write-Info ("등록 필요: " + $r.scriptsDir)
    }

    if (-not $r.inRepo) {
        Write-Host ""
        if ($r.git) {
            Write-Info "repo 없음 — 설치 시 자동으로 git clone합니다."
        } else {
            Write-Warn "repo 없음 & git 미설치 — 설치 시 수동 다운로드가 필요합니다."
        }
    }
}

# ════════════════════════════════════════════════════════════════
#  PHASE 2: 단계별 설치
# ════════════════════════════════════════════════════════════════
function Install-Prerequisites ([hashtable]$r) {

    # ── STEP 1: winget ──────────────────────────────────────────
    Write-Section "STEP 1/6  winget"
    if ($r.winget) {
        Write-Skip ("winget " + $r.wingetVer + " — 이미 설치됨")
    } else {
        Write-Fail "winget 미설치"
        Write-Info "Microsoft Store에서 '앱 설치 관리자'를 설치하세요."
        Write-Guide "https://aka.ms/getwinget"
        Write-Info "설치 후 이 스크립트를 다시 실행하세요."
        Prompt-Continue "winget 설치 후 계속하려면 Enter..."
        Refresh-Path
        if (Test-Cmd "winget") {
            Write-OK "winget 확인 완료"
            $r.winget = $true
        }
    }

    # ── STEP 2: Python ──────────────────────────────────────────
    Write-Section "STEP 2/6  Python"
    if ($r.python) {
        Write-Skip ($r.pythonVer + " — 이미 설치됨")
        Write-Info ("경로: " + $r.pythonPath)
    } elseif ($r.winget) {
        Write-Info "Python 3.12 설치 중 (winget)..."
        winget install --id Python.Python.3.12 --silent `
              --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
        Refresh-Path
        if (Test-Cmd "python") {
            $r.python = $true
            $r.pythonPath = Get-CmdPath "python"
            $r.pythonVer  = (python --version 2>&1).ToString().Trim()
            Write-OK ("Python 설치 완료: " + $r.pythonVer)
        } else {
            Write-Warn "설치됐지만 PATH가 아직 반영 안 됨 — 스크립트 재시작 필요"
            Prompt-Continue
        }
    } else {
        Write-Fail "Python 미설치 (winget 없음 — 수동 설치 필요)"
        Write-Guidance "Python 3.12" "멀티에이전트 시스템 핵심 런타임" `
            "https://www.python.org/downloads/" `
            @("1. 위 URL에서 Python 3.12 Windows 설치 파일 다운로드",
              "2. 설치 시 하단 'Add Python to PATH' 체크박스 반드시 선택",
              "3. 설치 완료 후 이 스크립트를 다시 실행") -Required
    }

    # ── STEP 3: Node.js ─────────────────────────────────────────
    Write-Section "STEP 3/6  Node.js (Claude Code 의존성)"
    if ($r.nodejs) {
        Write-Skip ("Node.js " + $r.nodeVer + " — 이미 설치됨")
    } elseif ($r.winget) {
        Write-Info "Node.js LTS 설치 중 (winget)..."
        winget install --id OpenJS.NodeJS.LTS --silent `
              --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
        Refresh-Path
        if (Test-Cmd "node") {
            $r.nodejs  = $true
            $r.nodeVer = (node --version 2>&1).ToString().Trim()
            Write-OK ("Node.js 설치 완료: " + $r.nodeVer)
        } else {
            Write-Warn "설치 후 PowerShell 재시작이 필요할 수 있습니다."
        }
    } else {
        Write-Warn "Node.js 미설치 — Claude Code 설치에 필요합니다."
        Write-Guide "winget install OpenJS.NodeJS.LTS  또는  https://nodejs.org"
    }

    # ── STEP 4: 구버전 충돌 파일 제거 ───────────────────────────
    Write-Section "STEP 4/6  충돌 파일 확인"
    if ($r.staleScript) {
        Write-Warn ("구버전 bash 스크립트: " + $r.stalePath)
        $ans = Read-Host "         제거하시겠습니까? [Y/N]"
        if ($ans -match "^[Yy]") {
            Remove-Item $r.stalePath -Force -ErrorAction SilentlyContinue
            if (-not (Test-Path $r.stalePath)) {
                Write-OK "구버전 스크립트 제거 완료"
                $r.staleScript = $false
            }
        } else {
            Write-Warn "건너뜀 — PowerShell에서 multiagent 실행 시 충돌 가능"
        }
    } else {
        Write-OK "충돌 파일 없음"
    }

    # ── STEP 5: multiagent-cli 설치 ─────────────────────────────
    Write-Section "STEP 5/6  multiagent-cli 설치 및 PATH 등록"
    if (-not $r.inRepo) {
        if ($r.git) {
            Write-Warn "repo가 없습니다. git clone으로 가져옵니다."
            $defaultPath = Join-Path $env:USERPROFILE "multi-agent-starter"
            Write-Host ("         설치 경로 [기본: " + $defaultPath + "]: ") -NoNewline
            $clonePath = Read-Host
            if (-not $clonePath) { $clonePath = $defaultPath }
            Write-Info ("git clone 중 → " + $clonePath)
            git clone "https://github.com/EhEo/multi-agent-starter.git" "$clonePath" 2>&1 | Out-Null
            if (Test-Path (Join-Path $clonePath "pyproject.toml")) {
                Write-OK ("clone 완료: " + $clonePath)
                $r.inRepo    = $true
                $r.repoPath  = $clonePath
            } else {
                Write-Fail "git clone 실패 — 네트워크 또는 Git 오류를 확인하세요."
                return
            }
        } else {
            Write-Fail "repo 없음 & git 미설치 — 수동으로 repo를 내려받은 후 실행하세요."
            Write-Guide "https://github.com/EhEo/multi-agent-starter"
            return
        }
    }

    if ($r.python -and $r.inRepo) {
        Push-Location $r.repoPath
        Write-Info "pip install -e . 실행 중..."
        $out = pip install -e . --user 2>&1
        Pop-Location
        $errs = $out | Where-Object { $_ -match "^ERROR" }
        if ($errs) {
            Write-Fail "설치 오류:"
            $errs | ForEach-Object { Write-Info $_ }
        } else {
            Write-OK "multiagent-cli 설치 완료"
            $r.multiagent = $true
        }

        # PATH 등록
        $sd = Get-PythonUserScripts
        if ($sd) {
            if (Add-UserPath $sd) {
                Write-OK ("PATH 등록 완료: " + $sd)
            } else {
                Write-Skip ("이미 PATH에 있음: " + $sd)
            }
        }

        # 현재 세션 PATH 갱신 후 재확인
        Refresh-Path
        if (Test-Cmd "multiagent") {
            Write-OK "multiagent 명령 확인"
        } else {
            Write-Warn "PATH 반영을 위해 PowerShell을 재시작하세요."
        }
        if (Test-Cmd "mat") { Write-OK "mat 명령 확인" }
    } else {
        Write-Warn "Python이 없어 설치를 건너뜁니다."
    }

    # ── STEP 6: AI CLI 도구 안내 ────────────────────────────────
    Write-Section "STEP 6/6  AI CLI 도구 확인"

    if ($r.claude) {
        Write-Skip ("Claude Code " + $r.claudeVer + " — 이미 설치됨")
    } else {
        Write-Fail "Claude Code 미설치"
        Write-Guidance "Claude Code" `
            "멀티에이전트 기본 AI 엔진 (Anthropic 계정 필요)" `
            "https://claude.ai/code" `
            @("1. npm install -g @anthropic-ai/claude-code",
              "2. claude 실행 -> Anthropic 계정 로그인",
              "3. Pro / Max / API 키 중 하나 필요") -Required
    }

    if ($r.codex) {
        Write-Skip ("Codex CLI " + $r.codexVer + " — 이미 설치됨")
    } else {
        Write-Warn "Codex CLI 미설치 (선택 사항)"
        Write-Guidance "OpenAI Codex CLI" `
            "codex-main / codex-critic 워커 사용 시 필요" `
            "https://github.com/openai/codex" `
            @("npm install -g @openai/codex",
              "OPENAI_API_KEY 환경변수 설정 필요")
    }

    if ($r.agy) {
        Write-Skip ("Antigravity " + $r.agyVer + " — 이미 설치됨")
    } else {
        Write-Warn "Antigravity(agy) 미설치 (선택 사항)"
        Write-Guidance "Antigravity CLI" `
            "gemini 워커 사용 시 필요" `
            "https://antigravity.ai" `
            @("Antigravity 공식 사이트에서 Windows 설치 파일 다운로드",
              "설치 후: agy install")
    }
}

# ════════════════════════════════════════════════════════════════
#  최종 요약
# ════════════════════════════════════════════════════════════════
function Show-Summary ([hashtable]$r) {
    Write-Host ""
    Write-Host "  ================================================" -ForegroundColor Cyan
    Write-Host "   설치 완료 요약" -ForegroundColor Cyan
    Write-Host "  ================================================" -ForegroundColor Cyan
    Write-Host ""

    $ready = $r.python -and $r.multiagent
    $cliOk = $r.claude

    if ($ready -and $cliOk) {
        Write-OK "모든 필수 항목 설치 완료"
    } elseif ($ready -and -not $cliOk) {
        Write-Warn "multiagent-cli 설치 완료 — Claude Code 설치 후 사용 가능"
    } else {
        Write-Warn "일부 항목이 누락됐습니다. 위 안내를 참고하세요."
    }

    Write-Host ""
    Write-Host "  시작 방법 (PowerShell 재시작 후):" -ForegroundColor White
    Write-Host "    multiagent              # 현재 폴더에 시스템 구성 후 claude 실행" -ForegroundColor Gray
    Write-Host "    multiagent mat          # mat 모니터를 새 창에서 실행" -ForegroundColor Gray
    Write-Host "    multiagent --help       # 전체 옵션 보기" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  PATH 변경 반영을 위해 PowerShell을 새로 여세요." -ForegroundColor Yellow
    Write-Host ""
}

# ════════════════════════════════════════════════════════════════
#  진입점
# ════════════════════════════════════════════════════════════════
Write-Banner

# PHASE 1: 점검
Write-Host "  1단계: 현재 PC 설치 상태를 점검합니다..." -ForegroundColor DarkCyan
$status = Invoke-PreflightCheck
Show-PreflightReport $status

if ($CheckOnly) {
    Write-Host ""
    Write-Host "  -CheckOnly 모드: 점검만 실행했습니다. 설치는 생략합니다." -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

# PHASE 2: 설치 여부 확인
$missing = @()
if (-not $status.python)     { $missing += "Python" }
if (-not $status.nodejs)     { $missing += "Node.js" }
if (-not $status.multiagent) { $missing += "multiagent-cli" }
if ($status.staleScript)     { $missing += "구버전 스크립트 제거" }
if (-not $status.scriptsInPath -and $status.python) { $missing += "PATH 등록" }

if ($missing.Count -eq 0 -and $status.multiagent) {
    Write-Host ""
    Write-OK "모든 필수 항목이 이미 설치되어 있습니다."
    Show-Summary $status
    exit 0
}

Write-Host ""
if ($missing.Count -gt 0) {
    Write-Warn ("설치/처리가 필요한 항목: " + ($missing -join ", "))
}
Write-Host ""
$proceed = Read-Host "  2단계: 위 항목을 설치하시겠습니까? [Y/N]"
if ($proceed -notmatch "^[Yy]") {
    Write-Host ""
    Write-Info "설치를 취소했습니다."
    exit 0
}

# PHASE 3: 설치 실행
Write-Host ""
Write-Host "  3단계: 설치를 시작합니다..." -ForegroundColor DarkCyan
Install-Prerequisites $status

# 요약
Show-Summary $status

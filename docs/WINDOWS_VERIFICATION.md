# Windows Native 검증 체크리스트

Phase A+B 변경사항을 Windows 11에서 직접 검증하기 위한 단계별 체크리스트.
각 단계를 순서대로 실행하고 결과를 기록한다.

> Linux/macOS에서는 `bash tests/run.sh`로 자동 회귀 테스트가 가능하지만,
> Native Windows 경로(`conhost.exe` 래핑 · winget 설치 · PowerShell User PATH)는
> 실기기 검증이 필요하다. 이 문서는 그 검증 절차다.
>
> Phase A = 크로스플랫폼 디스패처 (`_shared/adapters/call_worker.py`).
> Phase B = 크로스플랫폼 부트스트랩 (`bootstrap/install.py` + `install.ps1`).

---

## 사전 준비

- Windows 11 (10.0.22000+) 기기. Windows 10 21H2 이상도 동작하지만 권장.
- 인터넷 연결 (winget 패키지 다운로드, agy 공식 설치 스크립트).
- 관리자 권한 PowerShell (대부분의 단계는 불필요. winget·Node.js 일부 경로 권한, 문제 해결 시 사용).
- Microsoft 계정 (Windows Store / winget 소스 동기화).

---

## 1단계: 사전 환경 점검

새 PowerShell 창을 열고 아래 명령을 실행한다.

```powershell
# PowerShell 버전 (5.1+ 필수, 7+ 권장)
$PSVersionTable.PSVersion

# winget — Windows 11 기본 탑재, Windows 10 21H2+ 는 "App Installer" 최신화 필요
winget --version

# Python launcher (부트스트랩 실행 전제조건 — 없으면 install.ps1 이 종료 127)
py -3 --version
```

체크:
- [ ] `$PSVersionTable.PSVersion` ≥ 5.1
- [ ] `winget --version` 출력 (예: `v1.7.x` 이상)
- [ ] `py -3 --version` → Python 3.8 이상

> **참고**: `py` launcher는 python.org 공식 installer 또는 Microsoft Store版 Python 설치 시 함께 들어온다.
> WindowsApps의 `python` stub(Store 연결)만 있는 환경에서는 `install.ps1`이 `py → python → python3`
> 순서로 검색하므로 `py` 확보를 권장한다.

---

## 2단계: 리포지토리 준비

```powershell
cd C:\
git clone https://github.com/netwaif/multi-agent-starter.git
cd multi-agent-starter

# 파일 존재 확인
Test-Path .\bootstrap\install.ps1
Test-Path .\bootstrap\install.py
Test-Path .\_shared\adapters\call_worker.py
```

체크:
- [ ] 세 명령 모두 `True`

> Git이 없다면 부트스트랩이 Git.Git 설치 단계를 포함하지만 clone이 먼저 필요하다.
> https://git-scm.com/download/win 에서 수동 설치하거나 `winget install --id Git.Git -e` 먼저 실행.

---

## 3단계: 부트스트랩 실행

> `install.ps1` 자체는 ExecutionPolicy를 우회하지 **않는다**.
> 서명된 스크립트가 아니므로 사용자가 `-ExecutionPolicy Bypass`로 호출해야 한다 (의도된 동작).

```powershell
powershell -ExecutionPolicy Bypass -File bootstrap\install.ps1 `
  --flavor claude `
  --target C:\multi-agent-test `
  --yes
```

**예상 stdout 마지막 줄**:
```
bootstrap complete. Open a new shell, then `multiagent` in any folder.
```

**예상 stderr 흐름** (각 step 은 `[bootstrap] step N: ...` 형식):
```
[bootstrap] platform: windows pkg=winget
[bootstrap] repo root: C:\multi-agent-starter
[bootstrap] target: C:\multi-agent-test
[bootstrap] step 3-4: system deps (python3, git, bash, tmux, jq)
  [OK]   python 3.11.x
  [OK]   git present: ...
  [WARN] bash check skipped on Windows
  [WARN] tmux unavailable on native Windows (use WSL)   ← 정상
  [WARN] jq missing ...    또는 [OK] jq present: ...
[bootstrap] step 5: Node.js + npm
  [OK]   node: ..., npm: ...
[bootstrap] step 6: CLI tools (claude, codex, agy)
  [OK]   claude: ...
  [OK]   codex: ...
  [OK]   agy: ...
[bootstrap] step 7: mat (multi-agent tracker)
[bootstrap] step 9: PATH registration
  [OK]   Windows User PATH updated (+N entries)
[bootstrap] step 10: generator (flavor=claude)
[bootstrap] step 11: verification
[bootstrap] step 13: writing marker
[bootstrap] marker written: C:\Users\<user>\AppData\Local\multiagent-bootstrap\bootstrap.done
```

체크:
- [ ] exit code 0: `echo $LASTEXITCODE` → `0`
- [ ] stderr에 `tmux unavailable on native Windows` WARN 노출 (정상)
- [ ] marker 파일 생성: `Test-Path "$env:LOCALAPPDATA\multiagent-bootstrap\bootstrap.done"` → `True`

> **알려진 한계**: `bin/multiagent`는 bash 스크립트라 Native Windows cmd/PowerShell에서 실행 불가.
> PATH에 등록되는 것 자체는 부트스트랩 정상 동작의 증거. 런처 사용은 WSL 경로 권장.

---

## 4단계: 각 도구 버전 확인

**새 PowerShell 창**을 연다 (User PATH 반영을 위해 현재 세션을 버림).

```powershell
python --version
py --version
git --version
node --version
npm --version
jq --version          # winget 으로 설치된 경우
claude --version      # npm 글로벌
codex --version       # npm 글로벌
agy --version         # 공식 installer
```

체크 (설치된 도구만):
- [ ] `python --version` → 3.8 이상
- [ ] `git --version` → 2.x
- [ ] `node --version` → 18 LTS 이상 권장
- [ ] `npm --version` → 버전 문자열
- [ ] `claude --version` → 버전 문자열
- [ ] `codex --version` → 버전 문자열
- [ ] `agy --version` → 버전 문자열
- [ ] `jq --version` (설치된 경우)
- [ ] `tmux -V` → Windows에서는 실패 **정상** (3단계 WARN과 일관)

---

## 5단계: PATH 등록 확인

```powershell
# User PATH 내용
[Environment]::GetEnvironmentVariable('Path', 'User') -split ';' |
  Select-String 'agy','multi-agent-starter'
```

체크:
- [ ] `%LOCALAPPDATA%\agy\bin` 포함
- [ ] `C:\multi-agent-starter\bin` (또는 clone 위치) 포함

> `bin\multiagent`는 bash 런처라 Windows cmd/PowerShell에서 직접 실행은 불가.
> PATH에 들어있는 것 자체가 부트스트랩 정상 동작의 증거다.

---

## 6단계: 디스패처 smoke test

```powershell
# 인자 없이 실행 → usage 에러
python _shared\adapters\call_worker.py
echo "exit: $LASTEXITCODE"
```

**예상 stderr**:
```
call_worker: usage: call_worker.py <role> <brief-file>
```

체크:
- [ ] exit code 64
- [ ] stderr에 usage 메시지

---

## 7단계: conhost.exe 래핑 검증 (agy가 설치된 경우)

> Phase A 의 핵심. Native Windows + agy 워커가 `conhost.exe --headless` 로 래핑되는지 확인.
> 래핑하지 않으면 agy 가 detached console 요청 시 프롬프트 루프로 무한정지하거나
> 빈 stdout 을 반환한다 (upstream [Issue #76](https://github.com/google-antigravity/antigravity-cli/issues/76)).

### 7-A. 소스 검사 (항상 실행 가능)

`_shared\adapters\call_worker.py` 두 영역 확인:

**150-156줄** — conhost 경로 해석:
```python
def _resolve_conhost_path() -> Optional[str]:
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(sysroot, "System32", "conhost.exe")
    if os.path.exists(candidate):
        return candidate
    return shutil.which("conhost.exe")
```

**260-310줄** — agy 호출 시 래핑 분기 (핵심):
```python
is_windows_agy = (
    is_windows
    and ctype == "cli"
    and (spec.get("cli") or {}).get("command") == "agy"
)
...
if is_windows_agy:
    agy_path = shutil.which("agy")
    conhost = _resolve_conhost_path() if agy_path is not None else None
    if agy_path is None or conhost is None:
        ...  # 명확한 에러 envelope 반환 (exit 127)
    cmd = [conhost, "--headless", agy_path, *cmd[1:]]
    stdin_input = brief_bytes if stdin_input is not None else b""
```

체크:
- [ ] `Test-Path "$env:SystemRoot\System32\conhost.exe"` → `True`

### 7-B. 가짜 agy stub 으로 라이브 검증 (권장, 더 강력)

**사전 조건**: `_shared\backends.json` 에 `gemini` role 의 primary backend command 가 `agy` 여야 한다.
(claude/codex flavor 기본 템플릿에 포함 — 50줄 `"command": "agy"`, 51줄 `"args_template": ["--print", "@brief_content"]`)

```powershell
# 1. fake agy.cmd 생성
$fakeDir = "$env:TEMP\fake-agy-test"
New-Item -ItemType Directory -Force -Path $fakeDir | Out-Null
@'
@echo off
echo FAKE_AGY_STDOUT_LINE
echo FAKE_AGY_STDERR_LINE 1>&2
exit /b 0
'@ | Set-Content -Path "$fakeDir\agy.cmd" -Encoding ascii

# 2. fake agy 를 이 세션 PATH 맨 앞으로
$env:PATH = "$fakeDir;$env:PATH"

# 3. brief 파일 작성
$briefPath = "$env:TEMP\test-brief.md"
@'
# test brief
This is a test brief for fake agy dispatch.
'@ | Set-Content -Path $briefPath -Encoding utf8

# 4. 디스패처 호출 (gemini role)
$env:MULTIAGENT_ROOT = (Get-Location).Path
python _shared\adapters\call_worker.py gemini $briefPath
echo "exit: $LASTEXITCODE"
```

**기대 stdout** (단일 라인 JSON envelope):
```json
{"status": "ok", "exit_code": 0, "backend": "cli", "model": "gemini-3.1-pro-high",
 "duration_s": N, "stdout": "FAKE_AGY_STDOUT_LINE\r\n",
 "stderr_sanitized": "...", "fallback_used": false}
```

체크:
- [ ] exit code 0
- [ ] envelope JSON 의 `stdout` 필드에 `FAKE_AGY_STDOUT_LINE` 포함
- [ ] 빈 stdout 이면 → Issue #76 회귀. `call_worker.py` 290-310줄의 `is_windows_agy` 분기 재점검.

**정리**:
```powershell
Remove-Item -Recurse -Force $fakeDir
Remove-Item -Force $briefPath
Remove-Item Env:\MULTIAGENT_ROOT
```

---

## 8단계: generator 실행 (부트스트랩 step 10 수동 재현)

```powershell
python plugins\multi-agent-starter\skills\configure-multiagent\generator\init.py `
  --flavor claude `
  --target C:\test-target `
  --yes
```

체크:
- [ ] `C:\test-target` 폴더 생성
- [ ] `C:\test-target\CLAUDE.md` 존재
- [ ] `C:\test-target\_shared\adapters\call_worker.py` 존재
- [ ] 종료 직전 validate 자동 실행 → 0 FAIL ("전부 PASS")

---

## 9단계: validate 실행

```powershell
python plugins\multi-agent-starter\skills\configure-multiagent\generator\validate.py `
  --flavor claude `
  --target C:\test-target
echo "exit: $LASTEXITCODE"
```

체크:
- [ ] exit code 0
- [ ] "전부 PASS" 또는 "0 FAIL" 메시지

---

## 10단계: mat Python 폴백 (선택)

부트스트랩이 native mat 바이너리 설치에 실패한 경우 pip 폴백이 동작하는지 확인.

```powershell
pip install -e .
mat --help
```

체크:
- [ ] `pip install -e .` 성공
- [ ] `mat --help` 사용법 출력
- [ ] `pip show multi-agent-starter` 로 entry point `mat = ...` 확인

> Native Windows `mat.exe` 는 별도 프로젝트에서 경로 처리·터미널 표시·UTF-8·파일 감시를
> 검증한 뒤 지원 예정. 여기서는 Python 폴백만 확인한다.

---

## 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `install.ps1` 실행 시 `running scripts is disabled on this system` | PowerShell ExecutionPolicy 기본 Restricted | `powershell -ExecutionPolicy Bypass -File bootstrap\install.ps1 ...` 로 호출 (의도된 우회 경로) |
| `winget : 'winget' is not recognized` | App Installer 미설치/구버전 | Microsoft Store 에서 "App Installer" 최신화. Windows 10 21H2 미만은 OS 업그레이드 권장 |
| `winget install` 실패: `0x80073cfd` 등 Store 서비스 오류 | Store 캐시/서비스 문제 | `wsreset.exe` 실행 후 재시도. Microsoft Store 로그인 확인 |
| `npm install -g` 시 `EACCES` / `EPERM` | npm 글로벌 prefix 권한 부족 | `npm config set prefix "$env:APPDATA\npm"` 후 해당 디렉토리를 User PATH 에 추가. 또는 `--no-install-cli` 로 npm 계통 스킵 |
| `irm https://antigravity.google/cli/install.ps1` 실패 | 방화벽/프록시, URL 차단 | 브라우저에서 해당 URL 접속 가능한지 확인. 기업 프록시 환경에서는 `$env:HTTPS_PROXY` 설정 |
| envelope JSON: `agy 실행파일을 찾을 수 없습니다` | agy 가 PATH 에 없거나 설치 실패 | `agy --version` 으로 확인. `Test-Path "$env:LOCALAPPDATA\agy\bin\agy.exe"` 확인. 없으면 공식 installer 재실행 |
| envelope JSON: `conhost.exe 를 찾을 수 없습니다` | Windows 버전 너무 오래됨 | `winver` 로 10.0.22000+ (Windows 11) 권장. `%SystemRoot%\System32\conhost.exe` 존재 확인 |
| agy 워컹 호출이 빈 stdout 반환 (Issue #76 회귀) | conhost 래핑 미동작 | 7단계 7-B 재실행. `call_worker.py` 290-310줄의 `is_windows_agy` 분기가 참인지, `conhost` 변수가 None 이 아닌지 확인 |
| `multiagent` 명령 인식 안 됨 | User PATH 가 현재 세션에 반영 안 됨 | **새 PowerShell/cmd 창을 연다**. 로그아웃/로그인 불필요. 단 `bin\multiagent` 자체는 bash 런처라 Native Windows 에서 실행 불가 (6단계 디스패처 smoke test 로 대체) |
| `py -3` 명령 인식 안 됨 | Python launcher 미설치 | python.org 공식 installer 로 재설치 (Customize → "py launcher" 체크) |
| 부트스트랩 성공 후에도 `tmux -V` 실패 | Windows 는 tmux 미지원 | 정상 동작. `mat` 사용 시 WSL 경로 권장 (README "모니터링" 절) |
| `marker already present` 메시지 | 이미 부트스트랩을 실행한 적이 있음 | 정상. `--force` 로 재실행, 또는 `Remove-Item "$env:LOCALAPPDATA\multiagent-bootstrap\bootstrap.done"` 후 재실행 |
| `install.ps1` 의 `py` 분기를 타는데도 설치 실패 | Microsoft Store stub `python` 이 `py` 보다 먼저 잡힘 | `Get-Command python, py | Format-Table Name, Source` 로 실제 경로 점검. python.org版 재설치 권장 |

---

## 버그 리포트

문제 발생 시 아래 정보를 수집해서 GitHub Issue 로 제보한다.

1. **Windows 버전**: `winver` (또는 `Get-ComputerInfo | Select-Object WindowsVersion, OsBuildNumber`)
2. **PowerShell 버전**: `$PSVersionTable.PSVersion`
3. **부트스트랩 전체 출력** (stdout + stderr):
   ```powershell
   powershell -ExecutionPolicy Bypass -File bootstrap\install.ps1 `
     --flavor claude --target C:\report-test --yes *> bootstrap-output.txt 2>&1
   Get-Content bootstrap-output.txt
   ```
4. **marker 파일 내용**:
   ```powershell
   Get-Content "$env:LOCALAPPDATA\multiagent-bootstrap\bootstrap.done"
   ```
5. **검증 체크리스트 결과**: 위 1~10단계 체크박스 상태 (스크린샷 또는 텍스트).
6. **관련 도구 버전**: `python --version`, `git --version`, `node --version`, `agy --version` 등.
7. **(agy 관련인 경우)** `call_worker.py` 가 출력한 envelope JSON 전체.
   `stderr_sanitized` 필드는 32자 이상 토큰이 `[REDACTED]` 로 마스킹되므로 민감정보 누출 우려 없음.

---

## 참조 (Windows 분기 구현 위치)

빠른 디버깅용. Phase A+B 의 Windows 분기가 어디 있는지.

| 관심 영역 | 파일 · 줄 |
|-----------|-----------|
| Windows 플랫폼 감지 | `bootstrap/lib/platform_info.py` 97-114줄 (`detect()`) |
| winget 매핑 | `bootstrap/lib/packages.py` 39줄 (`PKG_MANAGERS.winget`), 51-68줄 (`PACKAGE_NAMES`) |
| Windows PATH 영속화 | `bootstrap/lib/pathing.py` 121-171줄 (`register_path_windows`) |
| agy Windows 설치 | `bootstrap/lib/cli_tools.py` 124-154줄 (`ensure_agy` Windows 분기) |
| 마커 파일 (Windows 경로) | `bootstrap/install.py` 60줄 (`MARKER_REL_WINDOWS`), 109-114줄 (`_marker_path`) |
| PowerShell wrapper | `bootstrap/install.ps1` (17줄 전체) |
| `conhost.exe` 경로 해석 | `_shared/adapters/call_worker.py` 150-156줄 (`_resolve_conhost_path`) |
| agy 호출 래핑 분기 | `_shared/adapters/call_worker.py` 260-310줄 (`is_windows_agy` 분기) |
| ANSI 이스케이프 제거 | `_shared/adapters/call_worker.py` 32줄 (`_ANSI_RE`), 319-322줄 (`_strip_ansi`) |
| 프로세스 트리 종료 (Windows) | `_shared/adapters/call_worker.py` 56-84줄 (`_terminate_tree`, `CTRL_BREAK_EVENT` + `taskkill /T /F`) |
| `gemini` role (agy backend) | `_shared/backends.json` 45-67줄 |

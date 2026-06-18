# Phase Progress — Cross-platform Migration

이 문서는 multi-agent-starter를 Linux/macOS 전용 시스템에서 **Linux·macOS·WSL·Native Windows** 단일 코드 경로로 이주한 3-Phase 작업의 서술형 진행 기록이다. 커밋 히스토리(무엇이 바뀌었는지)와 complement로, **왜 그 결정을 했는지·무엇을 남겼는지·다음엔 무엇을 해야 하는지**를 차례로 서술한다.

- 시작: 2026-06-18
- 완료: 2026-06-18 (Linux/macOS 측)
- 남은: Native Windows 11 실증 검증 (체크리스트만 작성, 실행은 사용자가 직접)

---

## 배경: 왜 이 작업을 했는가

기존 multi-agent-starter는 bash 디스패처(`call_worker.sh`)·bash 런처(`bin/multiagent`)·POSIX 전용 CLI(jq/mktemp/timeout)에 의존했다. Native Windows에서는 동작하지 않았고(KI-3), WSL이나 Git Bash 우회가 필요했다.

사용자 요구사항:
1. 신규 PC에서 한 번 실행으로 multi-agent-starter에 필요한 모든 것을 설치
2. 이후에는 새 폴더에서 `multiagent` 명령 한 번이면 시스템 + 에이전트 실행
3. Linux + WSL + Native Windows 모두 지원
4. CLI 도구(claude/codex/agy)도 자동 설치, 사용자는 브라우저 로그인만 수동

이를 위해 3-Phase 로드맵을 수립하고 순차 진행했다.

---

## Phase A — Cross-platform Python Dispatcher (commit `6c0da1e`)

### 목적
bash 디스패처(`call_worker.sh`)를 Python으로 이식. Linux·macOS·WSL·Native Windows에서 동일한 코드 경로로 동작하게. Phase B(부트스트랩)의 선행 조건 — 디스패처가 Python이 아니면 Native Windows 경로가 완전히 동작하지 않는다.

### 핵심 결정과 근거

**1. 단일 파일 `call_worker.py` (408 LOC)로 이식**
- 근거: 3 flavor(claude/codex/antigravity) 템플릿에 각각 복사되는 파일이라, 분할하면 drift 위험이 큼. Phase A의 `init.py` rglob 복사 패턴과 일관.
- 대안이었던 `call_worker.py + _platform_windows.py + _platform_posix.py` 분할은 기각.

**2. `gemini` 역할 이름 유지, 폴백만 정리 (사용자 결정 B)**
- 후보 A: 역할 이름을 `gemini` → `agy`로 rename + 폴백 정리
- 후보 B: 역할 이름은 `gemini` 유지, `gemini_api.sh` 폴백만 제거 ← **채택**
- 후보 C: 둘 다
- 근거: 이미 백엔드는 agy CLI를 쓰고 있었고, 이름 변경은 routing.md·backends.json·문서 전체의 호환성 깨기. slot-only `gemini_api.sh`는 어차피 동작 안 했으므로 제거만으로 충분.

**3. Native Windows + agy 조합에서 `conhost.exe --headless` 자동 래핑**
- 문제: agy CLI 자체의 Native Windows 버그 [Issue #76](https://github.com/google-antigravity/antigravity-cli/issues/76) — `agy --print`가 non-TTY stdout 환경에서 stdout을 silently drop.
- 해결: 디스패처가 `os.name == "nt"` + `command == "agy"` 조합을 감지하면 `conhost.exe --headless <agy> <args>`로 래핑. ANSI escape 제거 + stdin PIPE 즉시 close.
- 참고: obsigravity 프로젝트의 검증된 패턴 사용.

**4. 안정적 per-project agy workspace**
- 문제: agy가 workspace trust prompt로 처음 보는 폴더에서 블록됨. `cwd_policy: isolated_tmp`는 매 호출마다 새 폴더를 만들어 trust 루프 발생.
- 해결: `<tmp>/multi-agent-starter/agy-workspaces/<sha256(root)[:16]>/` 디렉토리를 dispatcher가 생성. `trustedWorkspaces` 항목 추가는 `init.py`가 담당 (dispatcher는 settings.json에 손 안 됨, stateless 유지).

**5. fallback all-fail 시 마지막 시도 exit code 반환**
- 기존 bash: 모든 폴백 실패 시 무조건 exit 1로 collapse.
- 변경: 마지막 시도의 실제 exit code 반환 (124 timeout, 1 일반 에러 등). CI 자동화가 timeout과 일반 실패를 구분할 수 있게.

### 결과
- 4개 위치에 byte-identical `call_worker.py` (root + 3 flavor 템플릿)
- 레거시 삭제: `call_worker.sh` × 4, `_run.py` × 4, `gemini_api.sh` × 3
- backends.json (claude/codex)에 `--dangerously-skip-permissions` 추가
- 테스트: bash 5개를 Python 6개로 재작성. 23개 디스패처 단언 + 19개 기존 = **42개 PASS**
- KI-3 부분 해결 (POSIX 의존 해결, Issue #76이 진짜 블로커로 정정)

### 파일 통계
50 files changed, +2169/−1079

---

## Phase B — Cross-platform Bootstrap Installer (commit `5663fbf`)

### 목적
신규 PC 1회 실행으로 multi-agent-starter에 필요한 모든 것을 설치. 사용자는 브라우저 로그인만 수동.

### 핵심 결정과 근거

**1. Python 단일 진실원천 (bash + PowerShell 이중 유지 기각)**
- 이중 유지하면 모든 로직 2벌, KI-3 해결도 별도 작업, 테스트도 2벌.
- Python은 이미 Tier 1 필수 의존(`init.py` 실행용)이라 추가 비용 0.
- `install.sh`와 `install.ps1`은 Python을 찾아 `install.py`를 실행하는 ~15줄 래퍼.

**2. 모듈 구조: `install.py` + `lib/` 패키지 (6 모듈)**
- 단일 600-800 LOC 파일은 `bin/multiagent`의 "여러 관심사가 뒤섞인" 안티패턴 반복.
- Oracle 설계: `lib/{platform_info, packages, cli_tools, pathing, repo, verify}.py`로 관심사 분리.
- 각 모듈 100-200 LOC로 상한. `install.py` 본체는 state machine orchestration만 (220 LOC).

**3. 패키지 매니저 dispatch table (brew/apt/dnf/pacman/winget)**
- snap/choco는 v1에서 제외 (신뢰성·사용자 비율).
- 단일 `PKG_MANAGERS` 딕셔너리로 5개 매니저 추상화.
- 멱등: per-tool `have()` 체크 + marker 파일 (`~/.local/share/multiagent-bootstrap.done`).

**4. agy는 공식 installer만 사용**
- librarian 조사 결과: npm 패키지 없음, brew tap 없음. 공식 `curl|bash` (POSIX) / `irm|iex` (Windows)만 지원.
- `cli_tools.ensure_agy()`가 플랫폼별로 분기.

**5. CLI 도구 로그인 자동화 불가**
- claude/codex/agy 모두 브라우저 OAuth. API key 환경변수는 일부만 지원하고 불안정.
- 부트스트랩 종료 후 로그인 가이드를 stderr에 출력 (`--skip-login-guide`로 억제 가능).

**6. Native Windows는 tmux 스킵, 단일 창 모드**
- 사용자 결정: Windows에서 tmux 없이 메인 도구를 현재 터미널에서 실행. mat는 별도 터미널 창에서.
- `verify.run_all_checks()`에서 tmux는 Windows일 때 WARN (FAIL 아님).

**7. 기존 `bin/multiagent`의 install_mat() 재사용 (재구현 X)**
- 부트스트랩이 `bin/multiagent --install-mat`를 subprocess로 호출. 단일 진실원천 유지.
- 폴백: `pip install -e .` (pyproject.toml의 `mat = "mat_linux:main"` entry point 활용).

### 결과
- `bootstrap/install.py` (285 LOC) + `bootstrap/lib/` 6 모듈 (1056 LOC)
- `bootstrap/install.sh` (POSIX 래퍼, 16 LOC) + `bootstrap/install.ps1` (Windows 래퍼, 17 LOC)
- 13단계 state machine: detect → idempotency → tier 1-5 설치 → repo → PATH → verify → login guide → marker
- 테스트: 132개 신규 단언 (8 테스트 파일). **총 155개 PASS**
- 문서: README.md "빠른 시작 (부트스트랩)" 섹션, INSTALL.md "0. 부트스트랩 (권장)" 섹션

### 파일 통계
23 files changed, +2422/−14

---

## Phase C — Windows Verification (commit `869ca23`)

### 목적
Phase A+B의 Native Windows 경로 검증. 단, 이 세션은 Linux에서 돌고 있어 실증은 불가 → Linux에서 가능한 최대 검증 + 사용자가 Windows 11에서 직접 실행할 체크리스트로 대체.

### 핵심 결정과 근거

**1. Linux에서 Windows code path를 monkeypatching으로 단위 테스트**
- `_StubPath` helper: `os.name='nt'`로 patch하면 Python `Path()`가 `WindowsPath` instantiate를 시도하며 Linux에서 `NotImplementedError`. stub으로 회피.
- `subprocess.run`을 MagicMock으로 캡처하여 실제 PowerShell/curl 호출 없이 명령 조립 로직 검증.

**2. `docs/WINDOWS_VERIFICATION.md` 10단계 체크리스트**
- 7단계 7-B가 핵심: 가짜 `agy.cmd` stub 만들어 `gemini` role 디스패치 후 envelope JSON의 `stdout`에 `FAKE_AGY_STDOUT_LINE`이 들어있는지 확인 → Issue #76 회귀 검증.
- 문제 해결 표: ExecutionPolicy, winget 미설치, npm EACCES, Microsoft Store python stub 등 Windows 함정.

**3. `install.ps1` 사전 버그 수정**
- **B1 (dead code)**: `$ErrorActionPreference="Stop"` 하에서 `Write-Error`는 terminating throw → `exit 127` 도달 불가. `[Console]::Error.WriteLine`로 교체.
- **B2 (exit code 전파 누락)**: `py`/`python` 호출의 exit code가 wrapper에 전파되지 않음 → 각 분기에 `exit $LASTEXITCODE` 추가.
- **I1**: `$PSScriptRoot`로 교체 (dot-sourcing 강건, PS 3.0+ 공식 관용).
- **I3**: 헤더에 ExecutionPolicy Bypass 사용 안내 추가.

### 결과
- `tests/dispatcher/test_conhost_wrap.py` (17 단언): conhost.exe 경로 해석, Windows+agy 분기, _terminate_tree
- `tests/bootstrap/test_windows_paths.py` (39 단언): platform_info Windows/WSL 분기, PowerShell PATH 등록, agy Windows/POSIX 설치 분기
- `docs/WINDOWS_VERIFICATION.md` (392 lines)
- **총 211개 테스트 PASS**

### 파일 통계
5 files changed, +1099/−3

---

## 남은 작업

### 1. Native Windows 11 실증 검증 (사용자 직접 실행)
- `docs/WINDOWS_VERIFICATION.md`의 10단계 체크리스트를 Windows 11 기기에서 실행.
- 특히 7-B (가짜 agy stub으로 conhost 래핑 라이브 검증)가 핵심.
- 문제 발생 시 버그 리포트 템플릿대로 정보 수집해서 GitHub Issue로 제보.

### 2. `bin/multiagent` (bash)의 Windows 대응 (Phase D 이후)
- 현재 `bin/multiagent`는 bash 스크립트라 Native Windows cmd/PowerShell에서 직접 실행 불가.
- 부트스트랩은 `bin/multiagent --install-mat`를 subprocess로 부르지만, 사용자가 직접 `multiagent` 명령을 치는 건 Windows에서 안 됨.
- 해결 옵션:
  - (a) Python 재작성 (부트스트랩의 lib를 재사용)
  - (b) Windows용 `multiagent.cmd` 래퍼 작성
  - (c) WSL만 공식 지원, Native Windows는 "부트스트랩으로 설치만, 실행은 WSL에서"로 positioning

### 3. agy `--model` 플래그 활용 (agy 1.0.5+)
- 현재 backends.json의 `model` 필드는 metadata only (agy CLI가 받지 않음).
- agy 1.0.5+에서 `--model` 플래그가 추가됨. backends.json 수정으로 per-call model pin 가능.
- 우선순위 낮음 — 기본 모델(gemini-3.1-pro-high)로 충분.

### 4. Native Windows mat.exe 검증
- `mat` 프로젝트에서 Windows 경로 처리·터미널 표시·UTF-8·파일 감시 검증이 아직 안 끝남.
- 현재는 Python 폴백(`pip install -e .`)으로 동작. native binary는 추후.

---

## 커밋 히스토럼 요약

| Phase | Commit | Files | Lines | 테스트 |
|-------|--------|-------|-------|--------|
| Phase A (Dispatcher) | `6c0da1e` | 50 | +2169/−1079 | 42 PASS |
| Phase B (Bootstrap) | `5663fbf` | 23 | +2422/−14 | 155 PASS |
| Phase C (Windows verify) | `869ca23` | 5 | +1099/−3 | 211 PASS |

브랜치: `linux-version`

---

## 의사결정 기록 (아카이브)

이 작업을 진행하며 내린 주요 결정을 한눈에:

1. **Python 단일 진실원천** (bash + PowerShell 이중 유지 기각) — 유지보수 비용 절감
2. **`gemini` 역할 이름 유지 + 폴백만 정리** (사용자 결정 B) — 호환성 보존
3. **`--dangerously-skip-permissions` 자동 주입** — headless 자동화 필수
4. **conhost.exe --headless 래핑** — Issue #76 우회의 유일한 검증된 방법
5. **단일 파일 `call_worker.py`** — 템플릿 복사 패턴과 일관
6. **`install.py` + `lib/` 분할** — `bin/multiagent` 안티패턴 회피
7. **Native Windows tmux 스킵** — 사용자 결정, 단일 창 모드
8. **agy 공식 installer만** — npm/brew 대안 없음
9. **부트스트랩 marker 파일로 멱등 보장** — 재실행 = 상태 맞추기, 재설치 아님
10. **`_StubPath` helper로 Linux에서 Windows Path() instantiation 회피** — 단위 테스트 커버리지 확장

# multiagent CLI — 설치 및 사용 가이드

## 개요

### 멀티에이전트 시스템이란?

`multiagent`는 **하나의 AI(오케스트레이터)가 여러 AI 워커를 지휘해 복잡한 작업을 처리**하는
파일 기반 오케스트레이션 시스템을 설치하고 실행하는 CLI 도구다.

```text
사용자
  │
  ▼
오케스트레이터 (Claude / Codex / Antigravity)
  │  작업을 분석하고 어떤 워커가 필요한지 판단
  │  각 워커 호출 전 사용자 승인 요청
  │
  ├── claude-main   메인 코딩·디버깅·설계·아키텍처
  ├── codex-main    보조 구현·코드 분석·테스트·diff
  ├── codex-critic  결과물 리뷰·비평
  └── gemini        멀티모달·긴 문서·제3자 검토
```

**핵심 특징:**

- **파일이 메모리** — 모든 작업 지시(brief), 결과(result), 승인 기록, 로그가 파일로 저장된다.
  세션이 끊겨도 파일에서 정확히 어디까지 진행했는지 파악할 수 있다.
- **승인 게이트** — 오케스트레이터가 워커를 호출하기 전에 반드시 사용자 확인을 받는다.
  의도하지 않은 AI 작업이 일어나지 않는다.
- **결정적 생성** — 설치 시 번들된 템플릿을 그대로 복사한다. AI가 시스템 파일을 임의로 만들지 않는다.
- **벤더 독립** — `_shared/backends.json` 하나만 수정하면 모델·연결 방식(native/MCP/CLI/API)을 바꿀 수 있다.

### `multiagent` 명령 동작 흐름

```text
multiagent 실행
    │
    ├─ 신규 폴더 ──▶ 파일 복사(init.py)
    │                    │
    │               파일 검증(validate.py) ──▶ FAIL이면 중단
    │                    │
    └─ 기존 폴더 ──▶ 파일 검증(validate.py) ──▶ FAIL이면 중단
                         │
                         ▼
                  claude / codex / agy 실행
```

---

## 1. 설치

### 요구 사항

| 도구 | 용도 | 설치 확인 |
|------|------|-----------|
| **Python 3.8+** | CLI 실행 | `python --version` |
| **uv** (Windows 권장) | 패키지 관리·PATH 자동 등록 | `uv --version` |
| **git** | 이 저장소 클론 | `git --version` |
| **claude / codex** | 오케스트레이터 실행 | `claude --version` |

### uv 사용 (권장 — Windows)

`uv`는 Python 패키지 관리자로, `pip install -e .` 보다 빠르고 PATH 등록도 자동으로 처리한다.

```powershell
# uv 설치 (미설치 시)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 이 저장소 클론 후 설치
git clone https://github.com/netwaif/multi-agent-starter.git
cd multi-agent-starter
uv tool install --editable .
```

설치가 완료되면 `multiagent`와 `mat` 두 명령이 PATH에 자동 등록된다.

### pip 사용 (macOS / Linux)

```bash
git clone https://github.com/netwaif/multi-agent-starter.git
cd multi-agent-starter
pip install -e .
```

### 설치 확인

```powershell
multiagent --help
mat --help
```

> **Windows PATH 미등록 시**: `uv tool update-shell` 실행 후 PowerShell 재시작.
> 또는 `$env:PATH`에 `C:\Users\<이름>\.local\bin` 추가.

---

## 2. 시스템 설치 (오케스트레이션 폴더 생성)

### 기본 사용법

원하는 **작업 폴더로 이동 후** `multiagent`를 실행한다.
현재 폴더가 자동으로 설치 대상이 된다.

```powershell
# 예: D:\projects\my-agent 폴더에 멀티에이전트 시스템 설치
cd D:\projects\my-agent
multiagent
```

실행하면:
1. `claude` flavor로 시스템 파일 26개를 현재 폴더에 복사
2. `validate.py`가 자동으로 실행되어 설치 완전성 검증 (C1~C9 모두 PASS 확인)
3. 검증 통과 후 `claude` 실행

### Flavor 선택

**Flavor**란 어느 AI를 오케스트레이터로 쓸지 결정하는 설정이다.
사용하는 AI 도구에 맞게 선택한다.

| 명령어 | 오케스트레이터 | 워커 풀 | 적합한 경우 |
|--------|----------------|---------|------------|
| `multiagent` (기본) | Claude Code | claude-main · codex-main · codex-critic · gemini | Claude Code를 주로 사용할 때 |
| `multiagent --claude` | Claude Code | 위와 동일 | 명시적으로 claude 지정 |
| `multiagent --codex` | Codex | codex-main · claude-critic · gemini | Codex를 주로 사용할 때 |
| `multiagent --antigravity` | Antigravity (Gemini 3.1 Pro High) | claude-main · codex-main · codex-critic | Gemini를 오케스트레이터로 쓸 때 |

### 주요 옵션

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--target <폴더>` | 현재 폴더 대신 특정 폴더에 설치 | `multiagent --target D:\myproject` |
| `--yes` | 신규 설치 확인 프롬프트 생략 | 자동화 스크립트에서 사용 |
| `--dry-run` | 실제 파일을 쓰지 않고 복사될 파일 목록만 미리보기 | 설치 전 확인 용도 |
| `--no-validate` | 설치 후 validate.py 검증 건너뜀 | 빠른 재설치 시 |
| `--no-launch` | 설치/검증만 하고 claude/codex 자동 실행 안 함 | 수동으로 오케스트레이터를 실행하고 싶을 때 |

### 예시

```powershell
# 현재 폴더에 설치 (확인 없이 바로 진행)
multiagent --yes

# 특정 폴더에 codex 시스템 설치 전 미리보기
multiagent --codex --target D:\projects\my-agent --dry-run

# 실제 설치 (확인 포함)
multiagent --codex --target D:\projects\my-agent
```

---

## 3. 재사용 (이미 설치된 폴더)

설치가 완료된 폴더에서 `multiagent`를 다시 실행하면 **파일 복사 없이** 검증만 수행하고
오케스트레이터를 바로 실행한다. 매일 작업을 시작할 때 이 방식을 쓰면 된다.

```powershell
cd D:\projects\my-agent

# 어제 하다 멈춘 작업 이어서 진행 — claude 바로 실행
multiagent

# codex로 전환해서 실행
multiagent --codex
```

**설치 여부 감지 기준**: `_shared/backends.json` + `CLAUDE.md`(claude) 또는 `AGENTS.md`(codex·antigravity)가
동시에 존재하면 이미 설치된 것으로 판단한다.

---

## 4. 작업 진행 방식

설치 후 오케스트레이터(claude)가 열리면, 자연어로 작업을 요청한다.

```text
> 새 작업 만들어줘. 목표는 로그인 API 버그 수정이고 claude-main이 필요할 것 같아.
```

오케스트레이터가 하는 일:

1. `tasks/fix-login-bug/task.md` 파일 생성 (작업 정의)
2. 어떤 워커가 필요한지 판단 → **사용자에게 승인 요청**
3. 승인 후 각 워커에게 `brief.md` 작성 (작업 지시서)
4. 워커 호출 → 결과를 `result.md`에 저장
5. 결과 검증 → `log.md`에 기록
6. 완료

모든 과정이 `tasks/fix-login-bug/` 폴더 안에 파일로 남는다.
세션이 끊겨도 `multiagent` 를 다시 실행하면 파일에서 진행 상황을 파악해 이어서 진행한다.

---

## 5. 모니터링 — mat

`mat`(MultiAgent Tracker)은 작업 진행 상황을 **읽기 전용**으로 보여주는 터미널 모니터다.
워커가 무엇을 하고 있는지, 어디까지 완료됐는지, 로그는 어떤지 한 화면에서 2초마다 갱신해 표시한다.
켜두거나 꺼도 오케스트레이션 진행에 전혀 영향이 없다.

### 5-1. `mat` 명령 — 현재 터미널에서 바로 실행

```powershell
# 작업 폴더로 이동 후 모니터 실행
cd D:\projects\my-agent
mat

# 폴더를 직접 지정
mat D:\projects\my-agent

# 환경변수로 지정
$env:MAT_ROOT = "D:\projects\my-agent"
mat
```

`Ctrl+C`로 종료.

### 5-2. `multiagent mat` — 새 터미널 창에서 실행

오케스트레이터와 모니터를 **동시에** 보고 싶을 때 사용한다.
새 cmd 창(Windows) 또는 새 Terminal 탭(macOS)을 열고 자동으로 mat를 시작한다.

```powershell
# 현재 폴더 모니터링 (새 창)
multiagent mat

# 특정 폴더 모니터링 (새 창)
multiagent mat --target D:\projects\my-agent
```

### 화면 구성 설명

```text
mat-win  my-agent  14:32:01  Ctrl+C 종료
────────────────────────────────────────────────────────────
  작업: fix-login-bug  상태: in_progress  갱신: 2026-06-14  우선순위: high
  목표: 로그인 API 버그 수정

  Workers
  [✓] claude-main      complete    14:28  JWT 검증 로직 분석 완료
  [⏳] codex-main      running     14:31  테스트 케이스 작성 중
  [ ] codex-critic     waiting

  Log
  [2026-06-14 14:28] [WORKER] claude-main 호출
  [2026-06-14 14:28] [VERIFICATION] C1~C9 PASS
  [2026-06-14 14:31] [WORKER] codex-main 호출
────────────────────────────────────────────────────────────
  작업 목록: fix-login-bug | refactor-db | add-tests
  폴링 2s  Ctrl+C 종료
```

| 영역 | 설명 |
|------|------|
| **헤더** | 모니터링 중인 폴더명, 현재 시각 |
| **작업 정보** | 현재 활성 작업명, 상태, 마지막 갱신일, 우선순위 |
| **목표** | task.md에 정의된 작업 목표 한 줄 요약 |
| **Workers** | 각 워커의 현재 상태 (아이콘·이름·상태·시각·brief 요약) |
| **Log** | log.md 최근 8줄 (색상으로 태그 구분) |
| **푸터** | 전체 작업 목록, 폴링 주기 |

| 워커 아이콘 | 의미 | 조건 |
|-------------|------|------|
| `[✓]` | 완료 | result.md 파일이 존재하고 내용 있음 |
| `[⏳]` | 실행 중 | brief.md 있고 result.md 없음 |
| `[ ]` | 대기 | brief.md도 없음 |

| 로그 색상 | 태그 |
|-----------|------|
| 초록 | `[PASS]` `[DONE]` |
| 노랑 | `[WORKER]` `[ACTION]` |
| 청록 | `[APPROVAL]` `[VERIFICATION]` |
| 빨강 | `[ERROR]` `[FAIL]` |

### 5-3. native mat (macOS / Linux / WSL)

Go로 작성된 고기능 TUI. 키보드 조작(작업 전환·로그 페이징)을 지원한다.

```bash
brew install netwaif/tap/mat
MAT_ROOT=/path/to/project mat
```

Windows에서 WSL을 사용하는 경우 (`D:\projects\my-agent` → WSL 경로 변환):

```bash
MAT_ROOT=/mnt/d/projects/my-agent mat
```

`mat` 명령(Windows)과 native mat은 **동일한 파일을 읽으므로** 어느 쪽이든 같은 정보를 표시한다.
native mat이 설치돼 있으면 `multiagent mat`가 자동으로 native mat을 사용한다.

---

## 6. 파일 구조 (설치 후)

```text
<설치-폴더>/
│
├── CLAUDE.md              ← 오케스트레이션 운영 규칙 (claude flavor)
│                            워커 역할 정의, 승인 게이트 규칙, 검증 기준 등
│
├── _shared/               ← 시스템 공유 파일 (multiagent가 관리, 직접 수정 금지)
│   ├── backends.json      ← 워커 역할 → 모델 → 연결 방식 레지스트리
│   │                        여기만 수정하면 모델·벤더 교체 가능
│   ├── routing.md         ← 어떤 작업에 어떤 워커를 쓸지 판단 기준
│   ├── orchestrator-rules.md ← 재진입 프로토콜, 에러 복구 규칙
│   ├── learnings.md       ← 운영 중 축적된 교훈 (자동 누적)
│   └── adapters/
│       └── call_worker.sh ← 워커 호출 디스패처 (MCP/CLI/API 자동 선택)
│
├── _templates/            ← 작업 파일 템플릿
│   ├── task.md            ← 새 작업 생성 시 이 형식으로 만든다
│   └── log.md             ← 로그 파일 초기 형식
│
├── tasks/                 ← 실제 작업 폴더 (사용자 데이터 — 절대 덮어쓰지 않음)
│   └── <task-name>/
│       ├── task.md        ← 작업 정의 (status, goal, 승인 워커 목록)
│       ├── log.md         ← 모든 이벤트 기록 (append-only)
│       ├── context.md     ← 현재 작업 맥락 스냅샷 (≤1500자)
│       ├── sources/       ← 참고 자료 원본
│       ├── artifacts/     ← 워커 산출물 원본
│       └── workers/
│           └── <role>/    ← 역할별 디렉터리 (claude-main, codex-main 등)
│               ├── brief.md   ← 오케스트레이터가 작성한 작업 지시서
│               └── result.md  ← 워커가 반환한 결과
│
└── _local/                ← 로컬 전용 데이터 (git 미추적, 공유 안 함)
    └── learnings.md       ← 이 프로젝트 한정 교훈
```

**중요 규칙:**
- `tasks/`와 `_local/` 폴더는 `multiagent`가 **절대 덮어쓰거나 삭제하지 않는다.**
  재설치(`multiagent --yes`)를 해도 작업 데이터는 보존된다.
- `_shared/`, `_templates/`, `CLAUDE.md` 는 시스템 파일로 재설치 시 갱신된다.
  직접 수정한 내용이 있다면 재설치 전에 백업한다.

---

## 7. 업데이트

```powershell
# 이 저장소 폴더에서
cd C:\path\to\multi-agent-starter
git pull
```

`uv tool install --editable .` / `pip install -e .` 로 설치했으면 `git pull` 만으로
`multiagent`와 `mat` CLI가 자동으로 최신 버전을 참조한다. 재설치 불필요.

시스템 파일(템플릿)도 최신화하려면:

```powershell
cd D:\projects\my-agent
multiagent --yes    # 기존 tasks/·_local/ 보존 + 시스템 파일만 갱신
```

---

## 8. 문제 해결

| 증상 | 원인 | 해결 방법 |
|------|------|-----------|
| `multiagent` 명령 없음 | PATH 미등록 | `uv tool update-shell` 후 터미널 재시작 |
| `mat` 명령 없음 | mat.cmd 미생성 | `uv tool install --editable .` 재실행 |
| validate FAIL | 시스템 파일 손상·누락 | `multiagent --yes` 로 재설치 |
| `claude` 명령 없음 | Claude Code 미설치 | Claude Code 설치 후 재시도 |
| 한글 깨짐 (PowerShell) | 터미널 인코딩 문제 | `$env:PYTHONIOENCODING="utf-8"` 추가 |
| mat 창이 즉시 닫힘 | 구버전 CLI (cmd /k → /c 변경 전) | `uv tool install --editable .` 재설치 |
| 작업 폴더가 tasks/ 안에 없음 | 잘못된 MAT_ROOT | `mat D:\projects\my-agent` 처럼 경로 직접 지정 |

---

## 9. 참고

- [README.md](./README.md) — 프로젝트 전체 개요 및 시스템 구조 설명
- [mat 저장소](https://github.com/netwaif/mat) — native mat 설치·키 조작 안내
- 설치된 폴더의 `CLAUDE.md` (claude) / `AGENTS.md` (codex·antigravity) — 운영 규칙 전문

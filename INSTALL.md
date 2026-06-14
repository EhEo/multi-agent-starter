# multiagent CLI — 설치 및 사용 가이드

## 개요

`multiagent` 명령어는 어느 폴더에서나 실행해 **파일 기반 멀티에이전트 오케스트레이션 시스템**을 설치하고,
설치 후 자동으로 오케스트레이터(Claude / Codex / Antigravity)를 실행한다.

```
multiagent 실행
    ├─ 신규 폴더  →  파일 복사(init.py)  →  파일 검증(validate.py)  →  claude/codex 실행
    └─ 기존 폴더  →  파일 검증(validate.py)                          →  claude/codex 실행
```

---

## 1. 설치

### 요구 사항

- Python 3.8 이상
- `uv` 또는 `pip`

### uv 사용 (권장 — Windows)

```powershell
git clone https://github.com/netwaif/multi-agent-starter.git
cd multi-agent-starter
uv tool install --editable .
```

### pip 사용 (macOS / Linux)

```bash
git clone https://github.com/netwaif/multi-agent-starter.git
cd multi-agent-starter
pip install -e .
```

### 설치 확인

```powershell
multiagent --help
```

> **Windows PATH 등록**: `uv tool install`은 `~/.local/bin`에 `multiagent.exe`를 자동 등록한다.
> 인식이 안 되면 `uv tool update-shell` 을 실행하거나 PowerShell을 재시작한다.

---

## 2. 시스템 설치 (오케스트레이션 폴더 생성)

원하는 **작업 폴더로 이동 후** `multiagent`를 실행한다.

### 기본 (Claude Code 오케스트레이터)

```powershell
cd C:\Users\Michael\documents\github\my-project
multiagent
```

### Flavor 지정

| 명령어 | 오케스트레이터 | 워커 풀 |
|--------|----------------|---------|
| `multiagent` 또는 `multiagent --claude` | Claude Code | claude-main · codex-main · codex-critic · gemini |
| `multiagent --codex` | Codex | codex-main · claude-critic · gemini |
| `multiagent --antigravity` | Antigravity (Gemini 3.1 Pro High) | claude-main · codex-main · codex-critic |

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--target <폴더>` | 대상 폴더 지정 (기본: 현재 폴더) |
| `--yes` | 신규 설치 시 확인 프롬프트 생략 |
| `--dry-run` | 실제 파일을 쓰지 않고 복사 목록만 미리보기 |
| `--no-validate` | 설치 후 파일 검증(validate.py) 건너뜀 |
| `--no-launch` | 설치/검증만 하고 claude/codex 실행 안 함 |

### 예시

```powershell
# 현재 폴더에 claude 시스템 설치 + 확인 없이 진행
multiagent --yes

# 특정 폴더에 codex 시스템 설치 (미리보기)
multiagent --codex --target D:\projects\my-agent --dry-run

# 이미 설치된 폴더 — 파일 검증 후 claude 실행
cd D:\projects\my-agent
multiagent
```

---

## 3. 재사용 (이미 설치된 폴더)

설치된 폴더에서 `multiagent`를 다시 실행하면 **파일을 복사하지 않고** 검증만 수행한 뒤
오케스트레이터를 바로 실행한다.

```powershell
cd D:\projects\my-agent
multiagent          # → 파일 검증 → claude 실행
multiagent --codex  # → 파일 검증 → codex 실행
```

설치 여부 감지 기준: `_shared/backends.json` + `CLAUDE.md`(claude) / `AGENTS.md`(codex·antigravity) 동시 존재.

---

## 4. 모니터링 — mat / mat-win

작업 진행 상황(워커 상태·goal·로그)을 별도 터미널에서 실시간으로 확인한다.
시스템을 **읽기만** 하므로 켜두거나 꺼도 진행에 영향이 없다.

### 4-1. `multiagent mat` — 새 터미널에 자동 실행 (권장)

```powershell
# 현재 폴더 모니터링
multiagent mat

# 특정 폴더 모니터링
multiagent mat --target D:\projects\my-agent
```

- native `mat`(brew 설치)가 있으면 native mat 사용
- 없으면 **mat_win.py (Python 폴백)** 자동 사용
- **Windows**: 새 cmd 창이 열리고 모니터링 시작
- **macOS**: Terminal.app 새 탭에서 실행
- **Ctrl+C** 로 종료 → 창 자동 닫힘

### 4-2. native mat — macOS / Linux / WSL (고기능 TUI)

```bash
brew install netwaif/tap/mat
MAT_ROOT=/path/to/project mat
```

Windows에서 WSL을 사용하는 경우 (폴더가 `D:\projects\my-agent`라면):

```bash
MAT_ROOT=/mnt/d/projects/my-agent mat
```

### 4-3. mat_win.py — Python 내장 모니터 (Windows 네이티브)

native mat 없이도 동작하는 순수 Python 구현체. `multiagent mat`가 자동으로 사용하지만
직접 실행할 수도 있다.

```powershell
# MAT_ROOT 환경변수로 지정
$env:MAT_ROOT = "D:\projects\my-agent"
python mat_win.py

# 인수로 직접 전달
python mat_win.py D:\projects\my-agent
```

#### 화면 구성

```
mat-win  my-agent  14:32:01  Ctrl+C 종료
────────────────────────────────────────────────────
  작업: fix-auth-bug  상태: in_progress  갱신: 2026-06-14  우선순위: high
  목표: JWT 토큰 만료 처리 수정

  Workers
  [✓] claude-main      complete    14:28  JWT 검증 로직 분석 완료
  [⏳] codex-main      running     14:31  테스트 케이스 작성 중
  [ ] codex-critic     waiting

  Log
  [2026-06-14 14:28] [WORKER] claude-main 호출
  [2026-06-14 14:28] [VERIFICATION] C1~C9 PASS
  [2026-06-14 14:31] [WORKER] codex-main 호출
────────────────────────────────────────────────────
  작업 목록: fix-auth-bug | refactor-db | ...
  폴링 2s  Ctrl+C 종료
```

| 아이콘 | 의미 |
|--------|------|
| `[✓]` | 완료 (result.md 존재) |
| `[⏳]` | 실행 중 (brief.md 있음, result.md 없음) |
| `[ ]` | 대기 |

---

## 5. 파일 구조 (설치 후)

```
<설치-폴더>/
├── CLAUDE.md              # 오케스트레이션 운영 규칙 (claude flavor)
├── _shared/
│   ├── backends.json      # 워커 역할→모델→연결방식 레지스트리
│   ├── routing.md         # 워커 선택 가이드
│   ├── learnings.md       # 시스템 운영 교훈 (누적)
│   └── adapters/
│       └── call_worker.sh # 워커 디스패처
├── _templates/
│   ├── task.md            # 작업 템플릿
│   └── log.md             # 로그 템플릿
├── tasks/                 # 작업 폴더 (사용자 데이터 — 절대 덮어쓰지 않음)
│   └── <task-name>/
│       ├── task.md
│       ├── log.md
│       └── workers/
│           └── <role>/
│               ├── brief.md
│               └── result.md
└── _local/                # 로컬 전용 데이터 (git 미추적)
```

---

## 6. 업데이트

```powershell
cd multi-agent-starter  # 설치한 repo 폴더
git pull
```

`uv tool install --editable .` / `pip install -e .` 로 설치했으면 `git pull` 만으로 CLI가 자동 반영된다.

---

## 7. 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `multiagent` 명령 없음 | PATH 미등록 | `uv tool update-shell` 후 터미널 재시작 |
| validate FAIL | 시스템 파일 손상 | `multiagent --yes` 로 재설치 |
| `claude` 명령 없음 | Claude Code 미설치 | Claude Code 설치 후 재시도 |
| mat 창이 안 닫힘 | 구버전 CLI | `uv tool install --editable .` 재설치 |
| 한글 깨짐 | 터미널 인코딩 | `$env:PYTHONIOENCODING="utf-8"` 설정 |

---

자세한 내용은 [README.md](./README.md) 및 [mat 저장소](https://github.com/netwaif/mat) 참고.

# multiagent — Linux/macOS 설치 및 사용 가이드

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

### `multiagent` 명령 동작 흐름 (Linux/macOS)

```text
multiagent 실행
    │
    ├─ 신규 폴더 ──▶ 파일 복사(init.py) ──▶ 파일 검증(validate.py)
    │                                              │
    └─ 기존 폴더 ──▶ 파일 검증(validate.py) ──────┘
                         │
                         ▼
              tmux 세션 생성 (세션명: multiagent-<폴더명>)
                         │
              ┌──────────┴──────────┐
              │ 왼쪽 창             │ 오른쪽 창
              │ claude / codex 실행 │ mat 모니터 실행
              └─────────────────────┘
```

---

## 1. 설치

### 요구 사항

| 도구 | 용도 | 설치 확인 |
|------|------|-----------|
| **Python 3.8+** | CLI 실행 · 워커 디스패처(`call_worker.py`) | `python3 --version` |
| **tmux** | 멀티 창 레이아웃 | `tmux -V` |
| **git** | 이 저장소 클론 | `git --version` |
| **claude / codex** | 오케스트레이터 실행 | `claude --version` |

### 의존성 설치

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y tmux python3

# macOS
brew install tmux
```

### pip 설치 (`mat` Python 폴백 등록)

`mat` 네이티브 바이너리가 없을 때를 위한 Python 폴백을 PATH에 등록한다.
`pip install -e .` 한 줄로 처리된다.

```bash
git clone https://github.com/netwaif/multi-agent-starter.git
cd multi-agent-starter
pip install -e .      # 또는: uv tool install --editable .
```

설치가 완료되면 `mat` 명령이 PATH에 등록된다.
`bin/multiagent`는 별도로 PATH에 추가한다 (아래 참조).

### `multiagent` 명령 PATH 등록

```bash
# 이 저장소 bin/ 폴더를 PATH에 추가
export PATH="$PWD/bin:$PATH"

# 영구 등록 (~/.bashrc 또는 ~/.zshrc)
echo 'export PATH="/path/to/multi-agent-starter/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 설치 확인

```bash
multiagent --help
mat --help
tmux -V
python3 --version
```

---

## 2. 시스템 설치 (오케스트레이션 폴더 생성)

### 기본 사용법

원하는 **작업 폴더로 이동 후** `multiagent`를 실행한다.
현재 폴더가 자동으로 설치 대상이 된다.

```bash
# 예: ~/projects/my-agent 폴더에 시스템 파일을 생성하고 claude 실행
cd ~/projects/my-agent
multiagent
```

실행하면:

1. `claude` flavor로 시스템 파일을 현재 폴더에 복사
2. `validate.py`가 자동으로 실행되어 설치 완전성 검증
3. 검증 통과 후 `claude`를 **현재 터미널에서 바로** 실행 (tmux 없음)

tmux 레이아웃(왼쪽: claude, 오른쪽: mat)을 원하면 `tmux` 서브커맨드를 사용한다:

```bash
multiagent tmux
```

### Flavor 선택

| 명령어 | 오케스트레이터 | 워커 풀 |
|--------|----------------|---------|
| `multiagent` (기본) | Claude Code | claude-main · codex-main · codex-critic · gemini |
| `multiagent -claude` | Claude Code | 위와 동일 |
| `multiagent -codex` | Codex | codex-main · claude-critic · gemini |

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--target <폴더>` | 현재 폴더 대신 특정 폴더에 설치 |
| `--setup-only` | 파일 생성 후 tmux 실행 안 함 |
| `--install-mat` | mat 바이너리만 설치하고 종료 |
| `--no-mat` | mat 모니터 창 열지 않음 |
| `--no-install-mat` | mat 자동 설치 시도 안 함 |
| `--no-install-deps` | jq 자동 설치 시도 안 함 |

### 예시

```bash
# 현재 폴더에 claude 시스템 설치 후 tmux 실행
multiagent

# 특정 폴더에 codex 시스템 설치
multiagent -codex --target ~/work/my-project

# mat 없이 실행 (모니터 창 생략)
multiagent --no-mat

# mat 바이너리만 먼저 설치
multiagent --install-mat

# 파일만 생성하고 tmux는 실행 안 함
multiagent --setup-only
```

---

## 3. tmux 세션 레이아웃

`multiagent`가 열면 아래와 같은 tmux 레이아웃이 생성된다.

```text
┌──────────────────────────┬──────────────────────────┐
│                          │                          │
│   왼쪽 창               │   오른쪽 창              │
│                          │                          │
│   claude (오케스트레이터) │   mat (모니터)          │
│                          │                          │
│   > 여기서 작업 요청     │   워커 상태 실시간 표시  │
│                          │                          │
└──────────────────────────┴──────────────────────────┘
```

- **왼쪽**: `claude` 또는 `codex` 실행. 여기서 자연어로 작업을 요청한다.
- **오른쪽**: `mat` 모니터. 워커 진행 상황을 2초마다 갱신해 표시한다. 읽기 전용.

기존 세션이 있으면 새로 만들지 않고 **재접속**한다.

### 세션 관리

```bash
# 세션 목록 확인
tmux ls

# 세션 분리 (detach) — 백그라운드로 유지
Ctrl+B, D

# 세션 재접속
tmux attach-session -t multiagent-my-agent

# 세션 종료
tmux kill-session -t multiagent-my-agent
```

---

## 4. 재사용 (이미 설치된 폴더)

설치가 완료된 폴더에서 `multiagent`를 다시 실행하면 파일 복사 없이
검증만 수행하고 tmux 세션을 바로 연다.

```bash
cd ~/projects/my-agent

# 어제 하다 멈춘 작업 이어서 진행
multiagent

# codex로 전환
multiagent -codex
```

**설치 여부 감지 기준**: `_shared/backends.json` + `CLAUDE.md`(claude) 또는 `AGENTS.md`(codex)가
동시에 존재하면 이미 설치된 것으로 판단한다.

---

## 5. 작업 진행 방식

tmux 왼쪽 창(claude)에서 자연어로 작업을 요청한다.

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

---

## 6. 모니터링 — mat

`mat`(MultiAgent Tracker)은 작업 진행 상황을 **읽기 전용**으로 보여주는 터미널 모니터다.
워커가 무엇을 하고 있는지, 어디까지 완료됐는지, 로그는 어떤지 한 화면에서 2초마다 갱신해 표시한다.

### 6-1. native mat (권장)

Go로 작성된 고기능 TUI. 키보드 조작(작업 전환·로그 페이징)을 지원한다.
`multiagent`가 실행 시 자동으로 native mat을 사용한다.

```bash
# macOS / Linux
brew install netwaif/tap/mat

# go install (brew 없을 때)
GOBIN=$HOME/.local/bin go install github.com/netwaif/mat@latest
```

또는 `multiagent --install-mat`으로 자동 설치한다.

### 6-2. Python 폴백 (`mat` 명령)

native mat이 없을 때 `pip install -e .`로 등록된 Python 폴백을 사용한다.

```bash
# 작업 폴더에서 직접 실행
cd ~/projects/my-agent
mat

# 폴더를 직접 지정
mat ~/projects/my-agent

# 환경변수로 지정
MAT_ROOT=~/projects/my-agent mat
```

`Ctrl+C`로 종료.

### 화면 구성

```text
mat  my-agent  14:32:01  Ctrl+C 종료
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

| 워커 아이콘 | 의미 |
|-------------|------|
| `[✓]` | result.md 존재하고 내용 있음 |
| `[⏳]` | brief.md 있고 result.md 없음 |
| `[ ]` | brief.md도 없음 (대기) |

| 로그 색상 | 태그 |
|-----------|------|
| 초록 | `[PASS]` `[DONE]` |
| 노랑 | `[WORKER]` `[ACTION]` |
| 청록 | `[APPROVAL]` `[VERIFICATION]` |
| 빨강 | `[ERROR]` `[FAIL]` |

---

## 7. 파일 구조 (설치 후)

```text
<설치-폴더>/
│
├── CLAUDE.md              ← 오케스트레이션 운영 규칙 (claude flavor)
│
├── _shared/               ← 시스템 공유 파일
│   ├── backends.json      ← 워커 역할 → 모델 → 연결 방식 레지스트리
│   ├── routing.md         ← 어떤 작업에 어떤 워커를 쓸지 판단 기준
│   ├── orchestrator-rules.md
│   ├── learnings.md
│   └── adapters/
│       └── call_worker.py ← 워커 호출 디스패처
│
├── _templates/            ← 작업 파일 템플릿
│
├── tasks/                 ← 실제 작업 폴더 (사용자 데이터 — 절대 덮어쓰지 않음)
│   └── <task-name>/
│       ├── task.md
│       ├── log.md
│       ├── context.md
│       ├── sources/
│       ├── artifacts/
│       └── workers/
│           └── <role>/
│               ├── brief.md
│               └── result.md
│
└── _local/                ← 로컬 전용 데이터 (git 미추적)
    └── learnings.md
```

**중요**: `tasks/`와 `_local/`은 `multiagent`가 절대 덮어쓰지 않는다.
재설치해도 작업 데이터는 보존된다.

---

## 8. 업데이트

```bash
cd /path/to/multi-agent-starter
git pull
```

`pip install -e .`로 설치했으면 `git pull`만으로 CLI가 자동으로 최신 버전을 참조한다.

시스템 파일도 최신화하려면:

```bash
cd ~/projects/my-agent
multiagent     # 기존 tasks/·_local/ 보존 + 시스템 파일만 갱신
```

---

## 9. 문제 해결

| 증상 | 원인 | 해결 방법 |
|------|------|-----------|
| `multiagent` 명령 없음 | bin/ PATH 미등록 | `export PATH="$PWD/bin:$PATH"` 추가 |
| `mat` 명령 없음 | pip install 미실행 | `pip install -e .` 재실행 |
| validate FAIL | 시스템 파일 손상 | `multiagent` 재실행 (재설치) |
| `tmux` 없음 | tmux 미설치 | `sudo apt install tmux` |
| `claude` 없음 | Claude Code 미설치 | Claude Code 설치 후 재시도 |
| mat 화면 깨짐 | 터미널 ANSI 미지원 | `TERM=xterm-256color mat` 시도 |
| 기존 세션에 붙음 | 같은 폴더 세션 존재 | `tmux kill-session -t multiagent-<폴더명>` 후 재실행 |

---

## 10. 참고

- [README.md](./README.md) — 프로젝트 전체 개요 및 시스템 구조 설명
- [mat 저장소](https://github.com/netwaif/mat) — native mat 설치·키 조작 안내
- 설치된 폴더의 `CLAUDE.md` (claude) / `AGENTS.md` (codex·antigravity) — 운영 규칙 전문

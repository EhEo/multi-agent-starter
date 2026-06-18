# 알려진 이슈

해결되지 않은 알려진 결함을 추적한다. 고쳐지면 해당 항목을 닫고(✅) PR 링크를 단다.
시스템이 깨지는 크리티컬은 즉시 수정 대상, 표시·미관 한정은 보류 가능.

출처: `repo-consistency-audit` (2026-05-19, claude-main·codex-main 병렬 + Orchestrator 교차검증).
상세 근거표(`repo-consistency-audit`)는 공개 배포본에 미포함 — 유지보수자 전용.

---

## KI-1 (audit C3) — 표준 `worker-brief.md`를 쓰면 mat이 워커 목적을 ` ```yaml `로 표시

- **상태**: 열림 / **보류** (경미·표시 한정. 크리티컬 C1·C2는 PR #3·#5에서 해소됨)
- **심각도**: 낮음 — 시스템·워커 호출·데이터에 영향 없음. [mat](https://github.com/netwaif/mat) **모니터 화면 표시만** 오염. mat 미사용 시 영향 0.
- **재현**: 항상. `_templates/worker-brief.md` 표준 구조를 그대로 채운 brief를 쓰는 모든 작업. (이 audit의 codex-main brief에서도 실증됨.)

### 증상

mat의 핵심 화면 요소인 "워커 한 줄 목적"이 실제 Objective가 아니라 문자열 ` ```yaml `로 표시된다.

### 근본 원인

| repo | 파일·라인 | 내용 |
|------|-----------|------|
| starter | `_templates/worker-brief.md` | 1행 `# Brief`(heading), 2–4행 `<!-- -->`(comment), 6행 `## Execution Context`(heading), **8행 ` ```yaml ` fence** |
| mat | `internal/parser/task.go:280` | brief 존재 시 무조건 `w.Purpose = firstMeaningfulLine(brief 내용)` |
| mat | `internal/parser/task.go:499–515` | `firstMeaningfulLine`은 **빈 줄·`#`시작·`<!--`시작만 skip**, 그 다음 줄을 그대로 반환 |
| mat | `internal/parser/task.go:71–76` | `w.Purpose == ""`일 때만 `planned_workers.purpose`로 fallback |

표준 brief에서 heading·comment를 건너뛴 첫 "의미 있는" 줄은 `## Execution Context` 다음의 ` ```yaml ` fence다. 이 값이 비어있지 않으므로 `planned_workers.purpose` fallback도 발동하지 않는다.

### 수정 후보 (택1, 미결정)

- **(a) starter 템플릿** — `_templates/worker-brief.md`를 첫 의미 있는 줄이 실제 한 줄 목적이 되도록 재구성 (예: Execution Context yaml 위에 평문 목적 1줄, 또는 Objective를 평문으로 선두 배치).
  - 장점: starter 단독 수정, mat 재빌드 불필요, 자기완결.
  - 단점: 전 worker 공용 템플릿 변경. 1200자 한도·codex Execution Context yaml 요구와 양립해야.
- **(b) mat 파서** — `firstMeaningfulLine`이 코드펜스(` ``` `/` ```yaml `)도 skip하거나, 명시적 purpose 필드를 우선.
  - 장점: 임의 brief에 견고.
  - 단점: mat 재빌드·재배포 필요(`go build -o mat .` + 재실행). mat은 선택적 외부 도구라 비-mat 환경엔 무의미.

### 참고

- 공개 흔적: `_shared/learnings.md` [2026-05-19] (곁다리 언급), PR #5 본문.
- 크리티컬 해소 이력: PR #3 (C1 gemini 기본 모델), PR #5 (C2 gemini 단일 브리지).

---

## KI-2 — Antigravity 호스트 설치 경로 미확정 (루트 `plugin.json` 미동봉)

- **상태**: 열림 / **보류** (생성 코어엔 영향 없음. 머지 전 실설치 검증 대상)
- **심각도**: 중간 — `antigravity` flavor **생성·validate(12/12)·ZIP**은 호스트 독립으로 PASS. 영향 범위는 Antigravity를 **오케스트레이터 호스트로 두고 플러그인을 설치**하는 경로 한정.

### 증상

이 repo는 `.claude-plugin/`(Claude Code)·`.codex-plugin/`(Codex) 매니페스트만 동봉한다. 설계서(`design.md` Part A)가 Antigravity 호스트용으로 명시한 **루트 `plugin.json`은 repo에 없다**. 따라서 Antigravity 호스트의 로컬·마켓플레이스 설치 행은 매니페스트 없이 미검증 상태다.

### 실증된 것 / 미확정인 것

- **실증(2026-06-02, agy v1.0.4)**: agy로 플러그인을 로컬 사용 → "구성해줘" → 생성기 → validate PASS, end-to-end 동작. → agy가 플러그인+스킬을 **읽고 트리거**하는 것은 확인됨. (당시 antigravity flavor 추가 전이라 claude flavor로 실증.)
- **미확정**: agy/Antigravity IDE가 실제로 **어떤 매니페스트를 소비**하는지(skills/ 자동탐색 vs 루트 매니페스트 vs `.codex-plugin` 재사용). 루트 `plugin.json`의 정확한 스키마도 미확인.

### 다음 (머지 전)

- 사용자 Antigravity IDE 실설치로 (a)로컬 설치를 먼저 검증. (b)마켓플레이스 설치는 **PR 머지 전 검증 불가**(마켓플레이스는 main을 pull하므로) — 머지 후에만 가능.
- 실제 로딩 경로 확인 후, 필요하면 루트 `plugin.json`을 올바른 스키마로 추가하고 본 항목을 닫는다(✅).
- 그 전까지 매니페스트·README는 Antigravity를 **설치 호스트로 보장하지 않고**(생성 flavor로만 광고) 보수적으로 둔다.

---

## KI-3 — Windows 네이티브 지원 (부분 해결 / 검증 진행 중)

- **상태**: 부분적으로 해결됨 / **진행 중** (POSIX 디스패처 의존성은 해결, Windows 네이티브 경로는 실증 검증 중)
- **심각도**: 낮음 — POSIX(macOS·Linux·WSL)에서는 Python 디스패처로 완전 동작. Windows 네이티브는 `conhost.exe --headless` 우회로 동작하나, 실제 Windows 11 기기 검증이 아직 남음.

### 증상

- 과거: 네이티브 Windows(cmd/PowerShell)에서 gemini 워커 호출 시 bash 디스패처가 실행되지 않음.
- 현재: Python 디스패처 도입으로 크로스플랫폼 동작. 단 Windows에서 agy CLI 자체의 별도 이슈(Issue #76)가 새로운 제약으로 등장.

### 근본 원인

- 과거 원인(bash·jq·timeout·mktemp·`/dev/null` 등 POSIX 전용 요소)은 Python 이식으로 해결됨 (Phase A).
- 현재 남은 제약은 agy CLI 자체의 Windows 버그: `agy --print`가 non-TTY stdout 환경에서 stdout을 silently drop함 ([Issue #76](https://github.com/google-antigravity/antigravity-cli/issues/76)).
- native(claude)·mcp(codex)는 디스패처를 거치지 않아 영향 없음 — 과거와 동일.
- 참고 — agy 설치 옵션: `curl|bash`(POSIX), `irm|iex`(Windows PowerShell), `install.cmd`(Windows CMD). npm·brew tap은 없음. 최신 agy는 1.0.9(2026-06-17). 네이티브 Windows 바이너리는 `%LOCALAPPDATA%\agy\bin\agy.exe`에 설치됨(과거 KI-3의 "네이티브 Windows 빌드 미확인" 텍스트 정정).

### 우회

- Python 디스패처가 native Windows + agy 조합을 감지하면 자동으로 `conhost.exe --headless <agy> <args>`로 래핑하고 ANSI escape를 제거. 참고: obsigravity 프로젝트의 검증된 패턴.
- `conhost.exe`가 없는 환경에서는 exit 127 + 명확한 에러 메시지로 실패.

### 다음 (출시 후)

- Windows 11 실기기에서 `python3 call_worker.py gemini <brief>` 호출이 conhost 래핑 경로로 정상 동작하는지 검증.
- Issue #76이 upstream에서 해결되면 conhost 래핑 로직을 제거 검토.
- agy 1.0.5+의 `--model` 플래그 도입으로 backends.json `model` 필드가 실제로 전달되도록 추후 업데이트 검토.

### 변경 이력

- [2026-06-18] Phase A: bash 디스패처 → Python 이식 (`call_worker.sh` → `call_worker.py`, `_run.py`·`gemini_api.sh` 삭제). POSIX 디스패처 의존성 해결. agy 네이티브 Windows 빌드 존재 확인(과거 "미확인" 정정). 실제 블로커는 Issue #76로 이전. Python 디스패처에 `conhost.exe --headless` 우회 구현.

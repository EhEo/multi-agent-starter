# Changelog

이 파일은 multi-agent-starter **패키지/배포**의 버전 이력이다.
**설치된 시스템의 동작** 변경 이력은 생성된 폴더의 `CHANGELOG.md`
(정본: `generator/templates/{claude,codex}/CHANGELOG.md`)를 참조한다.
형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [Unreleased]

### Phase B — Cross-platform Bootstrap Installer

#### Added
- **Cross-platform Python bootstrap installer** `bootstrap/install.py` + `bootstrap/lib/`
  (`platform_info`, `packages`, `cli_tools`, `pathing`, `repo`, `verify`).
  한 번의 실행으로 신규 PC에 시스템 의존성(python3, git, tmux, jq, Node.js)과
  CLI 도구(claude, codex, agy)를 설치하고 PATH를 영속화한 뒤 워크스페이스를 scaffold한다.
  Linux(apt/dnf/pacman)·WSL·macOS(brew)·Native Windows(winget) 모두 지원.
- **`bootstrap/install.sh`** (POSIX wrapper)와 **`bootstrap/install.ps1`** (Windows wrapper).
  각각 환경에서 Python 3를 찾아 `install.py`를 실행하는 thin wrapper. Git for Windows bash에서
  `install.sh`도 동작하지만 Native Windows에서는 `install.ps1`이 1차 권장.
- **132개 부트스트랩 회귀 테스트** (`tests/bootstrap/`).
  플랫폼 감지, 패키지 디스패치, PATH 등록 dedup, 멱등성(marker), CLI smoke test 커버.
  총 테스트 수: **155** (Phase A 직후 42, Phase A 이전 19).
- **`docs/WINDOWS_VERIFICATION.md`** — Native Windows 11 기기에서 Phase A+B 검증용
  단계별 체크리스트 (10단계 + 문제 해결 + 버그 리포트 양식).
  `install.ps1` 실행, PATH 등록, 디스패처 smoke test, 가짜 agy stub 을 이용한
  `conhost.exe --headless` 래핑 라이브 검증(Issue #76 회귀 확인) 포함.

#### Changed
- **CLI 도구(claude, codex via npm; agy via 공식 installer)가 부트스트랩에 의해 자동 설치.**
  사용자가 직접 설치할 필요 없이, 부트스트랩 종료 후 브라우저 로그인만 하면 된다.
  agy는 npm 패키지가 없으므로 공식 installer(POSIX `curl|bash`, Windows `irm|iex`)만 사용한다.
- **README.md / INSTALL.md 갱신** — 부트스트랩을 신규 PC 셋업의 1차 권장 경로로 명시.
  기존 수동 설치법(plugin/ZIP/pip/직접)은 "고급/수동" 경로로 재프레이밍 (내용은 보존).
  INSTALL.md는 §0 부트스트랩을 맨 앞에 추가하고 기존 §1 이후를 수동 경로로 재정렬.

#### Known Issues
- **Native Windows에서 tmux 사용 불가** — 부트스트랩은 tmux 단계를 WARN으로 건너뛰고
  single-window 모드로 동작. `mat`는 별도 터미널에서 실행한다.
- **agy Issue #76 (non-TTY stdout drop)** — Phase A의 디스패처 `conhost.exe --headless`
  래핑으로 런타임에 우회. 부트스트랩은 agy 설치만 담당한다.

---

### Phase A — Cross-platform Python Dispatcher

#### Added
- **Cross-platform Python dispatcher** `_shared/adapters/call_worker.py` (replaces bash `call_worker.sh`).
  Native Windows 지원을 위해 agy 워커 호출 시 자동으로 `conhost.exe --headless`로 래핑하고
  ANSI escape를 제거 (upstream [Issue #76](https://github.com/google-antigravity/antigravity-cli/issues/76) 우회).

#### Changed
- **gemini 워커의 agy 호출에 `--dangerously-skip-permissions` 추가.** 헤드리스/자동화 환경에서
  권한 프롬프트로 멈추는 것을 방지. claude·codex flavor의 `_shared/backends.json` 정본을
  해당 옵션을 포함하도록 갱신.

#### Removed
- `call_worker.sh` — bash 기반 디스패처, Python 이식본으로 대체.
- `_run.py` — 타임아웃 헬퍼, `call_worker.py`에 통합.
- `gemini_api.sh` — 슬롯 전용 API 폰백, 실제 동작하지 않았으므로 삭제.

#### Deprecated
- 없음.

#### Fixed
- **KI-3 POSIX 디스패처 의존성 해결** — bash·jq·mktemp·timeout·`/dev/null` 등 POSIX 전용 요소가
  더 이상 디스패처에 필요하지 않음.

#### Security
- `--dangerously-skip-permissions`는 agy 워커에만 한정된 third-party 도구 우회다.
  MultiAgent의 **승인 게이트**가 여전히 agy가 언제 호출되는지 통제한다.

#### Known Issues
- **KI-3 부분 해결** — POSIX에서는 완전 동작. native Windows 전체 지원은 Windows 11 실기기에서
  `conhost.exe --headless` 우회 경로가 실제로 동작하는지 검증이 필요.

---

## [2.0.0] - 미배포 (PR 머지 시 태깅)

**Breaking**: 배포 방식을 "clone → 루트 파일 그대로 사용"에서 **생성기 + 플러그인**으로
전환. 이제 repo는 시스템 그 자체가 아니라 시스템을 만들어 주는 도구다.

### Changed
- **지침파일 Task Lifecycle에 워커 산출물 경로 명시 (claude/CLAUDE.md, codex·antigravity/AGENTS.md).**
  기존엔 "brief.md/result.md 작성"이라고만 해 경로가 모호 → 오케스트레이터(특히 Gemini)가
  `tasks/<task>/workers/<role>/` 대신 `<role>_brief.md`처럼 평탄화해서 모니터 도구(mat)가
  워커를 못 읽는 문제. 5·6단계를 `tasks/<task>/workers/<role>/{brief,result}.md`로 못박고,
  8단계에 완료 시 `task.md status → done` 갱신을 추가. (제미나이 자가진단으로 원인 확인.)
- **플러그인 레이아웃: 루트 → `plugins/multi-agent-starter/` 하위 폴더로 이동.**
  루트는 마켓 카탈로그(`.claude-plugin/marketplace.json` + 신규 `.agents/plugins/marketplace.json`)만
  둔다. Codex가 로컬 마켓에서 플러그인 source가 repo 루트(`"./"`)인 걸 거부하기 때문
  ([openai/codex#17066](https://github.com/openai/codex/issues/17066) — Claude는 허용, Codex는 거부).
  이 구조로 Claude·Codex 양쪽에서 마켓 등록·설치가 동작함을 검증(`codex plugin add` → installed/enabled).
- **generator를 `skills/configure-multiagent/generator/` 안으로 이동(스킬 자기완결).**
  Antigravity(`agy`)는 플러그인 설치 시 인식하는 컴포넌트(skills/agents/…)만 복사하고 임의 폴더
  (`generator/`)는 버린다 → 설치돼도 스킬이 부를 생성기가 없어 동작 불가였음. 스킬 폴더 안에 두면
  스킬과 함께 복사된다. **3호스트 검증 완료**: `agy plugin install <경로>` / `codex plugin add` 모두
  설치 위치에 skill+generator 동거 확인, `tests/run.sh`·`build_zip` 3-flavor 자가검증 PASS.

### Added
- `generator/init.py` — flavor·대상 지정 결정적 생성기 (tasks/·_local/ 보존, dry-run, `--yes`, guard).
- `generator/validate.py` — flavor별 불변식 자가점검 (claude 10 / codex 11 / antigravity 12), `init`이 설치 후 자동 호출.
- `generator/build_zip.py` — 플러그인 없이 쓰는 자립형 ZIP(run.command/run.bat + 한글 README), 재현가능 빌드.
- `generator/templates/{claude,codex,antigravity}/` — 세 flavor 정본 템플릿.
- **Antigravity flavor** — Antigravity(Gemini 3.1 Pro High)를 오케스트레이터로, claude-main·codex-main·codex-critic을 워커로. 멀티모달·긴 문서는 오케스트레이터가 직접(동일 벤더 gemini 워커 없음).
- **연결 어댑터 레이어** (vendor/model-free 하네스의 토대):
  - `_shared/backends.json` — 역할→모델→연결방식(native·mcp·cli·api) 레지스트리(머신 검증되는 단일 진실원).
  - `_shared/adapters/call_worker.sh` — cli/api 디스패처(allowlist·옵션인젝션 방어·결과 envelope JSON·폴백·타임아웃). native/mcp는 오케스트레이터 직접 호출.
  - `_shared/adapters/_run.py` — 결정적 타임아웃 러너(coreutils timeout 부재 시 폴백, 프로세스그룹 TERM→KILL, 초과 시 124).
- gemini 백엔드를 폐기된 프록시에서 **Antigravity CLI `agy`**(gemini-3.1-pro-high)로 이전. API 연결은 슬롯으로 예약.
- `tests/` — 외부·유료 모델 호출 없는 결정적 회귀 테스트(`run.sh`): 3 flavor 생성·update 보존·디스패처 폴백/타임아웃/가드.
- `docs/ACCEPTANCE.md` — 3호스트(claude·codex·antigravity) 수용 체크리스트 + 4층 신뢰모델 + 테스트 시나리오 S1~S10 + 사인오프 표.
- `generator/sync_claude_template.py` — 루트(Claude 정본)에서 `templates/claude` 재생성 + drift 가드.
- `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` — Claude Code·Codex 플러그인 매니페스트.
- `skills/configure-multiagent/` — "멀티 에이전트 시스템 구성해줘" front door.
- `LICENSE` — MIT.

### Changed
- 배포: clone → 플러그인(`/plugins` 마켓플레이스) / ZIP fallback.
- 루트 문서(README/CHANGELOG/KNOWN_ISSUES)를 repo front-page·패키지 이력으로 분리. 설치된 타깃용 동명 문서는 `templates/` 에 독립 정본으로 둔다.

### Fixed
- 디스패처 타임아웃이 자식 SIGTERM 사망코드(-15)를 반환해 timeout을 error로 오분류하던 버그 — 타임아웃 시 항상 124 반환(`_run.py`, root+템플릿 3벌).

### Note
- 이번 2.0.0은 *배포/패키징* 변경이지 시스템 규칙 변경이 아니다. 설치되는 시스템의 **동작** 버전은 flavor별로 다른 축을 잇는다:
  - `claude` flavor — **1.0.1 라인 계승** (기존 실사용 시스템의 연장; `generator/templates/claude/CHANGELOG.md`).
  - `codex` flavor — **0.1.0 신규 파생** (multi-agent-starter의 Codex orchestrator 버전; `generator/templates/codex/CHANGELOG.md`).
  - `antigravity` flavor — **0.1.0 신규 파생** (Antigravity orchestrator 버전; `generator/templates/antigravity/CHANGELOG.md`).

---

> 아래 1.0.x는 generator 전환 이전, **repo가 곧 시스템**이던 시기의 릴리스 이력이다.
> 설치 시스템 동작 이력은 이후 템플릿 CHANGELOG에서 이어진다.

## [1.0.1] - 2026-06-01

모델·추론 정책 표기 정리(문서 patch). 동작 변경 없음.

### Changed
- **모델 식별자 별칭화** (`_shared/routing.md`): claude-main을 버전 문자열(`claude-opus-4-7` 등) 대신 별칭 `opus`로 표기 — 모델이 올라가도 문서 갱신 불필요. codex 예시 일반화, gemini는 `gemini-3.1-pro-low` 핀 유지 + "프록시 업그레이드 시에만 갱신" 노트.
- **claude-main 추론 강도(effort) 명문화**: `effort` 핀 없음 → 세션 `/effort` 상속(현 기본). 고정하려면 frontmatter `effort:`.

### Added
- **design-basis D7**: 모델 식별자 표기 정책(별칭 원칙 / gemini 핀 예외·세부는 D4 정본 / effort 비대칭 근거).

### Verification
- codex-critic adversarial 검수: 치명 0, 권장 3 반영(잔존 핀 제거 포함). INV9/INV10/INV11 PASS, 회귀 없음.

## [1.0.0] - 2026-06-01

첫 버전 태깅. 기존 실사용 시스템을 1.0.0 기준선으로 고정하고, harness(revfactory) 참고 버전 업그레이드를 함께 반영한다.

### Added
- **작업 재진입 프로토콜** (`_shared/orchestrator-rules.md` §3): 콜드세션이 끝난 작업에 다시 들어갈 때 재정박(re-anchor) → 6분기 판단 → 에러 후 진행. `status↔log 불일치`는 다른 분기보다 먼저 적용하는 정규화 단계로 명시.
- **토폴로지 4패턴표** (`_shared/routing.md`): Pipeline / Fan-out·Fan-in / Expert Pool / Producer-Reviewer + Fan-in 규칙.
- **CLAUDE.md** Task Lifecycle에 재진입 프로토콜 포인터.
- **불변식 INV11** (`_shared/system-invariants.md`): 재진입·토폴로지 규정 자동 자가점검(11a/b/c).
- **design-basis D6**: 4패턴 채택 + Supervisor·Hierarchical Delegation 배제 근거.

### Excluded (설계 결정)
- Supervisor·Hierarchical Delegation 패턴: 단일 orchestrator·worker간 무통신·file-as-memory와 충돌하여 미채택 (근거 D6).

### Baseline (1.0.0 시점 핵심 구조)
- 고정 4-worker pool (claude-main / codex-main / codex-critic / gemini), Claude Code 세션 = orchestrator.
- file-as-memory (런타임 상태 0): task / context / log / brief / result.
- 승인 게이트(`workers_approved`), 외부 쓰기 4조건, progressive disclosure(게이트 로드), 권위 우선순위(CLAUDE.md > routing/approval/orchestrator-rules > 매뉴얼).

### Verification
- 배선(INV11a/b/c) PASS · 회귀 없음, 탁상 분기 커버리지, 실전 콜드세션 3/3 PASS, codex-critic adversarial 리뷰 5 ISSUE 반영.

[2.0.0]: https://github.com/netwaif/multi-agent-starter/releases/tag/v2.0.0
[1.0.1]: https://github.com/netwaif/multi-agent-starter/releases/tag/v1.0.1
[1.0.0]: https://github.com/netwaif/multi-agent-starter/releases/tag/v1.0.0

# Worker Routing Rules

## Decision Tree

```
작업 성격 파악
│
├── 현재 Antigravity Orchestrator(Gemini 3.1 Pro High)가 직접 처리 가능한 단일 작업?
│   └── worker 호출 없이 진행 (멀티모달·긴 문서·제3자 시각 검토도 오케스트레이터가 직접)
│
├── 메인 코딩 / 디버깅 / 설계 / 아키텍처 / 전략 수립?
│   └── claude-main
│
├── 보조 구현 / 코드 분석 / 테스트 / diff / 로컬 검증이 크고 분리 가능?
│   └── codex-main
│
├── 산출물의 독립 리뷰 / 비판적 검증?
│   └── codex-critic
│
└── 판단 어려움?
    └── Orchestrator가 먼저 범위를 좁히고, 필요한 worker만 사용자 승인 후 추가
```

## 복합 작업 우선순위

1. **Orchestrator 우선**: 별도 worker 호출 전에 현재 Antigravity 세션의 추론·멀티모달·로컬 도구로 해결 가능한지 판단한다.
2. **최소 worker set**: 필요한 worker만 고른다. 모든 worker를 기본 호출하지 않는다.
3. **선행 의존성 우선**: `codex-critic`은 리뷰 대상 산출물 경로가 먼저 있어야 한다.
4. **검증은 한 번만**: `codex-critic`은 작업당 1회 원칙. 재호출은 검증 실패나 입력 변경 시만.
5. **메인 코딩은 claude-main**: 큰 구현·설계는 claude-main, 보조·분석·테스트는 codex-main.

## 토폴로지 패턴

| 패턴 | 언제 | 이 시스템에서 |
|------|------|---------------|
| Pipeline (순차) | 앞 결과가 뒤 입력 | claude-main -> codex-critic -> Orchestrator 반영 |
| Fan-out/Fan-in (병렬→통합) | 서로 독립된 산출물 여럿을 통합 | claude-main(설계) ∥ codex-main(테스트). 통합은 Orchestrator |
| Expert Pool (전문가 선택) | 작업 성격에 맞는 worker만 | decision tree + 최소 worker set |
| Producer-Reviewer (생성+게이트) | 산출물 품질 검증 필요 | claude-main 또는 codex-main 생성 -> codex-critic |

**금지**: 같은 입력에 같은 종류 worker 동시 호출.
**배제**: 별도 long-lived supervisor worker나 worker가 worker를 부르는 재귀 위임 계층은 쓰지 않는다. 단일 Orchestrator, worker간 무통신, file-as-memory 원칙과 충돌한다.

### Fan-in 규칙

1. 각 worker 원문을 `result.md`에 그대로 보존한다.
2. 결과가 충돌하면 삭제하지 말고 양쪽 출처를 병기한 뒤, 권위 우선순위와 사실검증으로 해소한다.
3. 통합 결론 한 줄을 `context.md`에 기록하고, 근거를 `log.md` `[DECISION]`에 남긴다.

## Worker 호출 방식

모든 worker 호출은 `_shared/backends.json`이 정본이고, 디스패처를 거친다:
```
python3 _shared/adapters/call_worker.py <role> <brief-file>   # 결과 = JSON envelope
```
Orchestrator는 envelope의 stdout을 `result.md`에 기록한다. (claude-main=`claude` CLI, codex-main/codex-critic=`codex` CLI)

## Worker 역할 상세

### claude-main

- **용도**: 메인 코딩, 디버깅, 설계 문서, 아키텍처, 전략 수립.
- **결과물**: 코드, 설계·아키텍처 문서, 디버깅 분석, 전략.
- **호출 방식**: `backends.json`의 `claude-main`(백엔드 = `claude` CLI). 외부/유료 모델이므로 호출 전 승인.
- **brief 필수 필드**:

```yaml
target_repo: /absolute/path/to/repo
write_scope: none | tasks-only | "src/**, tests/**"
```

- **기본 쓰기**: `tasks/<task>/` 내부 산출물·diff.
- **외부 repo 쓰기**: `AGENTS.md`의 4조건을 모두 충족할 때만.
- **금지**: `_shared/`, `_templates/`, 다른 작업 폴더 수정.

### codex-main

- **용도**: 보조 구현, 코드베이스 분석, 리팩토링, 테스트 작성, diff 생성, 로컬 CLI 검증.
- **결과물**: 코드, diff, 테스트 결과, CLI 출력.
- **호출 방식**: `backends.json`의 `codex-main`(백엔드 = `codex` CLI). 호출 전 승인.
- **brief 필수 필드**: 위 claude-main과 동일(`target_repo`, `write_scope`).
- **기본 쓰기**: `tasks/<task>/` 내부. 외부 repo는 4조건 충족 시만. **금지**: `_shared/`, `_templates/`, 다른 작업 폴더.

### codex-critic

- **용도**: Antigravity Orchestrator·claude-main·codex-main 산출물의 독립 리뷰·비평. 실현 가능성, 테스트 커버리지, 사이드 이펙트, 누락 요구사항을 adversarial하게 점검한다. **Gemini 오케스트레이터와 다른 벤더(Codex)라 독립성 확보** — gemini 자기검수로 대체 금지.
- **선행 조건**: 리뷰 대상 산출물 경로가 존재해야 한다(`claude-main`/`codex-main result.md`, Orchestrator 문서, 기존 코드 등).
- **결과물**: 중요도별 비평 리스트, 수정 제안, 수락/보류 판단 근거.
- **호출 방식**: `backends.json`의 `codex-critic`(백엔드 = `codex` CLI). 호출 전 승인.
- **쓰기 권한**: 없음. Orchestrator가 응답을 `result.md`에 기록한다.
- **brief 필수 필드**: `target_repo` 또는 리뷰 대상 경로, `write_scope: none`, "비평 모드" 명시.

## 모델 정책

- **Antigravity Orchestrator**: agy/IDE의 현재 모델 = **Gemini 3.1 Pro High**(전역·계정단위 `/model`). 멀티모달·긴 문서도 오케스트레이터가 직접.
- **claude-main**: 승인된 `claude` CLI의 현재 기본/별칭 모델. 버전 문자열을 repo에 핀하지 않는다.
- **codex-main / codex-critic**: 현재 Codex 환경(`~/.codex/config.toml`) 기본값을 상속. repo에 버전 핀 금지.
- **gemini 워커 없음**: 오케스트레이터가 Gemini라 별도 gemini 워커는 두지 않는다(같은 벤더 독립성 무의미).

## 최소 Worker Set

| 작업 유형 | 권장 최소 set |
|-----------|---------------|
| 작고 명확한 구현/문서/멀티모달 | worker 없음, Orchestrator 직접 처리 |
| 메인 구현/설계 | claude-main |
| 보조 구현/분석/테스트 | codex-main |
| 구현 + 독립 비평 | claude-main(또는 codex-main) -> codex-critic |
| 전체 검토 | codex-critic |

## Worker 추가 조건

- 기존 결과로 해결 가능하면 추가 호출 금지.
- 이전 결과가 검증 미통과이거나 입력이 바뀐 경우에만 동일 worker 재호출.
- 모든 worker(claude-main·codex-main·codex-critic)는 외부/유료 모델이므로 매 호출 전 승인 경계를 분명히 한다.

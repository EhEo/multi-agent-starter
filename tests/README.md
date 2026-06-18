# tests/ — v2 자동화 테스트

`docs/ACCEPTANCE.md`의 검증 항목 중 **외부·유료 모델 호출 없이 결정적으로 돌릴 수 있는 것**만
자동화한다. 매 빌드/PR에서 회귀 검사로 안전하게 실행 가능.

## 실행

```bash
bash tests/run.sh                          # 전체
python3 tests/test_generate.py             # 개별
python3 tests/dispatcher/test_fallback.py  # 디스패처 단건
```

종료코드 0 = 전부 PASS, 비0 = 하나라도 FAIL.

## 의존성

`python3`, `bash`. 워커 CLI(`agy`/`claude`/`codex`)는 **설치 불필요** —
디스패처 테스트는 PATH에 가짜 바이너리를 주입해 동작만 검사한다.
v2.1부터 디스패처가 Python으로 이식되어 `jq`는 더 이상 필요 없다.

## 구성

| 파일 | 커버 | 비고 |
|------|------|------|
| `test_generate.py` | 3 flavor 생성 → validate 전부 PASS (L1/A2) | validate 체크 개수는 하드코딩 안 함(F4 등으로 늘어도 안 깨짐) |
| `test_update_preserve.py` | update 모드 `tasks/`·`_local/` 보존 (S9) | 순수 파일시스템 |
| `dispatcher/_lib.py` | 공용 assert·가짜 bin·디스패처 호출 헬퍼 | Python 테스트 헬퍼 (`_lib.sh` 대체) |
| `dispatcher/test_fallback.py` | primary 실패 → fallback (S5) | 가짜 `agy`(exit1)+`claude`(exit0) |
| `dispatcher/test_timeout.py` | timeout → 124 (S6) | 가짜 `agy` sleep |
| `dispatcher/test_guards.py` | usage/`..`/role/allowlist 차단 (A6) | |
| `dispatcher/test_codex_git.py` | codex git 정책 — 옵트아웃 시 `--skip-git-repo-check` 주입 | |
| `dispatcher/test_dispatcher_misc.py` | ANSI 제거·stderr redact·api 확장자 감지·CLI 조립 단위 테스트 | Python 디스패처 전용 (순수 함수) |

## 자동화되지 않는 것 (수동 — `docs/ACCEPTANCE.md` 참조)

오케스트레이터 행동(승인 게이트 S3, write_scope S4, 지침 준수), 실제 워커 호출(A4/S1/S2),
컨텍스트 운영(S7), 재진입(S8), antigravity 실설치. LLM 판단·실벤더가 필요해 결정적 단언 불가.

## 새 테스트 추가

- 파이썬: `tests/test_*.py`, 종료코드로 성패 보고.
- 디스패처 Python: `tests/dispatcher/test_*.py`, 첫 줄에서 `sys.path.insert(...)` 후 `import _lib`,
  `assert_eq`/`assert_contains` 사용, 마지막에 `finish()`.
- `run.sh`가 위 두 패턴을 자동 발견한다.

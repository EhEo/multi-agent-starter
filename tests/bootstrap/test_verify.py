#!/usr/bin/env python3
"""test_verify.py — bootstrap.lib.verify.run_all_checks() smoke 테스트.

검증:
- run_all_checks() 가 List[CheckResult] 를 반환
- 각 CheckResult 는 name/status/detail 필드 (status 는 OK|WARN|FAIL 중 하나)
- 적어도 한 항목은 python>=3.8 (항상 OK 여야 함)
- count_statuses 합이 총 결과 수와 일치
- print_summary 가 빈 출력을 내지 않는다
머신별 count 차이(mat 누락 등)는 하드코딩하지 않는다.
"""
from __future__ import annotations

import dataclasses
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402

sys.path.insert(0, str(_lib.REPO))
from bootstrap.lib import platform_info, verify  # noqa: E402

VALID_STATUSES = {"OK", "WARN", "FAIL"}


def main() -> int:
    print("bootstrap.lib.verify: run_all_checks smoke test")

    info = platform_info.detect()
    repo_root = _lib.REPO
    # target 도 repo 자체 (이미 initialized 상태)
    target = _lib.REPO

    results = verify.run_all_checks(
        repo_root=repo_root,
        target=target,
        info=info,
        install_cli_requested=True,
    )

    # List[CheckResult]
    _lib.assert_eq("returns a list", True, isinstance(results, list))
    _lib.assert_eq("list is non-empty", True, len(results) > 0)

    # 모든 항목 shape 검증
    for i, r in enumerate(results):
        _lib.assert_eq(
            f"result[{i}] is dataclass",
            True,
            dataclasses.is_dataclass(r),
        )
        _lib.assert_eq(
            f"result[{i}].status in {{OK,WARN,FAIL}}",
            True,
            r.status in VALID_STATUSES,
        )
        # name/detail 은 비어있지 않은 str
        _lib.assert_eq(
            f"result[{i}].name is non-empty str",
            True,
            isinstance(r.name, str) and r.name != "",
        )
        _lib.assert_eq(
            f"result[{i}].detail is str",
            True,
            isinstance(r.detail, str),
        )

    # python>=3.8 check 가 항상 OK 여야 한다 (이 스크립트가 3.8+ 로 돌고 있으므로)
    py_results = [r for r in results if r.name == "python>=3.8"]
    _lib.assert_eq("python check present", True, len(py_results) >= 1)
    if py_results:
        _lib.assert_eq("python>=3.8 status OK", "OK", py_results[0].status)

    # count_statuses 합 == len(results)
    ok, warn, fail = verify.count_statuses(results)
    _lib.assert_eq(
        "count_statuses sum == total",
        len(results),
        ok + warn + fail,
    )

    # has_hard_failure 와 fail 수 일치
    _lib.assert_eq(
        "has_hard_failure matches fail count > 0",
        fail > 0,
        verify.has_hard_failure(results),
    )

    # print_summary 가 stderr 기본값으로 비어있지 않은 출력을 만든다
    buf = io.StringIO()
    verify.print_summary(results, stream=buf)
    summary_text = buf.getvalue()
    _lib.assert_eq(
        "print_summary produces output",
        True,
        len(summary_text) > 0,
    )
    # 적어도 한 [OK]/[WARN]/[FAIL] 태그가 있어야
    has_tag = any(tag in summary_text for tag in ("[OK]", "[WARN]", "[FAIL]"))
    _lib.assert_eq("summary contains at least one status tag", True, has_tag)

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

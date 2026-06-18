#!/usr/bin/env python3
"""test_cli_smoke.py — bootstrap/install.py CLI smoke 테스트.

검증:
- `python3 bootstrap/install.py --check-only --skip-login-guide` 가 exit 0
- stderr 에 "platform:" / "repo root:" 진행 메시지
- stdout 에 "bootstrap check-only summary:" 최종 요약
- stdout 에 적어도 하나의 [OK] 태그 (stderr 의 print_summary)
- stdout 에 [FAIL] 없을 것 (머신이 healthy 할 때)
- `--help` exit 0, stdout 에 "usage:" 포함
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402


def main() -> int:
    print("bootstrap/install.py CLI smoke (--check-only + --help)")

    # ── --check-only --skip-login-guide ──
    rc, out, err = _lib.run_install_py(["--check-only", "--skip-login-guide"])
    _lib.assert_eq("--check-only exit 0", 0, rc)

    # 진행 메시지는 stderr 에
    _lib.assert_contains("stderr has 'platform:'", "platform:", err)
    _lib.assert_contains("stderr has 'repo root:'", "repo root:", err)

    # 최종 summary 라인은 stdout 에
    _lib.assert_contains(
        "stdout has 'bootstrap check-only summary:'",
        "bootstrap check-only summary:",
        out,
    )

    # print_summary 가 stderr 로 출력한 [OK]/[WARN]/[FAIL] 태그들
    _lib.assert_contains("stderr has at least one [OK]", "[OK]", err)

    # stdout(사용자용 최종 라인)에는 [FAIL] 이 없어야 — print_summary 는 stderr 로 감
    _lib.assert_eq(
        "stdout has NO [FAIL]",
        False,
        "[FAIL]" in out,
    )

    # ── --help ──
    rc2, out2, err2 = _lib.run_install_py(["--help"])
    _lib.assert_eq("--help exit 0", 0, rc2)
    _lib.assert_contains("--help stdout has 'usage:'", "usage:", out2)
    # --help 는 argparse 가 prog 이름으로 install.py 를 찍어야
    _lib.assert_contains(
        "--help stdout mentions bootstrap/install.py",
        "bootstrap/install.py",
        out2,
    )

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""test_idempotency.py — bootstrap/install.py --check-only 멱등성 검증.

두 번 연속 실행해 stdout 이 byte-identical 한지 확인한다.
(stderr 은 타임스탬프/순서가 달라질 수 있어 비교에서 제외)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402


def main() -> int:
    print("bootstrap/install.py --check-only idempotency (stdout identical x2)")

    args = ["--check-only", "--skip-login-guide"]

    rc1, out1, err1 = _lib.run_install_py(args)
    rc2, out2, err2 = _lib.run_install_py(args)

    _lib.assert_eq("first run exit 0", 0, rc1)
    _lib.assert_eq("second run exit 0", 0, rc2)

    _lib.assert_eq(
        "stdout byte-identical across runs",
        out1,
        out2,
    )

    # 둘 다 summary 라인이 있어야 (요지: 빈 출력이 아님)
    _lib.assert_contains(
        "first stdout has summary line",
        "bootstrap check-only summary:",
        out1,
    )
    _lib.assert_contains(
        "second stdout has summary line",
        "bootstrap check-only summary:",
        out2,
    )

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""bootstrap 테스트 공용 헬퍼 (tests/dispatcher/_lib.py 와 동일 스타일).

Python 3.8+ 표준 라이브러리 전용. 각 test_*.py에서:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _lib
형태로 임포트해 사용한다.

제공:
- REPO / BOOTSTRAP_DIR / INSTALL_PY 상수
- assert_eq / assert_contains / finish (dispatcher/_lib.py 호환)
- run_install_py: bootstrap/install.py 를 subprocess 로 호출
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# tests/bootstrap/_lib.py → parents[2] = <repo>
REPO = Path(__file__).resolve().parents[2]
BOOTSTRAP_DIR = REPO / "bootstrap"
INSTALL_PY = BOOTSTRAP_DIR / "install.py"

# 추적 카운터 (bash의 PASS=0; FAIL=0 과 동일)
PASS = 0
FAIL = 0


def assert_eq(desc: str, expected, actual) -> bool:
    """PASS/FAIL 라인 출력. 같으면 True."""
    global PASS, FAIL
    if expected == actual:
        print(f"  PASS: {desc}")
        PASS += 1
        return True
    print(f"  FAIL: {desc} (expected [{expected}] got [{actual}])")
    FAIL += 1
    return False


def assert_contains(desc: str, needle: str, haystack: str) -> bool:
    """PASS/FAIL 라인 출력. needle이 haystack에 있으면 True."""
    global PASS, FAIL
    if needle in haystack:
        print(f"  PASS: {desc}")
        PASS += 1
        return True
    print(f"  FAIL: {desc} (missing [{needle}])")
    FAIL += 1
    return False


def run_install_py(
    args: "list[str]",
    env_extra: "dict[str, str] | None" = None,
) -> "tuple[int, str, str]":
    """bootstrap/install.py 를 subprocess 로 실행.

    반환: (returncode, stdout, stderr). 캡처된 텍스트.
    env_extra 가 주어지면 기존 env 위에 overlay.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    cmd = [sys.executable, str(INSTALL_PY), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def finish() -> int:
    """요약 출력, 실패가 없으면 0, 있으면 1 반환."""
    global PASS, FAIL
    print(f"  ({PASS} pass / {FAIL} fail)")
    return 0 if FAIL == 0 else 1

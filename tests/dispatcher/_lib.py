#!/usr/bin/env python3
"""디스패처 Python 테스트 공용 헬퍼 (tests/dispatcher/_lib.sh 대체).

Python 3.8+ 표준 라이브러리 전용. 각 test_*.py에서:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _lib
형태로 임포트해 사용한다. _lib.sh와 동일한 역할 — new_root/fake_bin/dispatch/
assert_eq/assert_contains/finish, 모듈 수준 함수만(클래스 없음).

DISPATCHER는 <repo>/_shared/adapters/call_worker.py(루트 사본)를 가리킨다.
이 파일 자체가 라이브 테스트 픽스처로 사용된다.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# <repo>/_shared/adapters/call_worker.py (이 파일 기준 ../../_shared/adapters/)
REPO = Path(__file__).resolve().parents[2]
DISPATCHER = REPO / "_shared" / "adapters" / "call_worker.py"

# 추적 카운터 (bash의 PASS=0; FAIL=0 과 동일)
PASS = 0
FAIL = 0


def new_root(backends_json: str) -> Path:
    """_shared/bin/ 을 가진 임시 루트를 만들고 backends.json을 저장. 루트 경로 반환."""
    d = Path(tempfile.mkdtemp(prefix="madis_"))
    (d / "_shared" / "bin").mkdir(parents=True, exist_ok=True)
    (d / "_shared" / "backends.json").write_text(backends_json, encoding="utf-8")
    return d


def fake_bin(root: Path, name: str, exit_code: int, sleep_secs: float = 0,
             extra_lines: "list[str] | None" = None) -> Path:
    """root/_shared/bin/<name> 에 실행 가능한 가짜 바이너리 생성.

    동작: (선택) sleep → (선택) extra_lines 실행 → 'fake-<name>-out' 출력 → exit_code 종료.
    extra_lines는 bash 스크립트 라인 목록(예: ['echo "ARGS: $*"']).
    """
    p = root / "_shared" / "bin" / name
    lines = ["#!/usr/bin/env bash"]
    if sleep_secs > 0:
        lines.append(f"sleep {sleep_secs}")
    if extra_lines:
        lines.extend(extra_lines)
    lines.append(f"echo fake-{name}-out")
    lines.append(f"exit {exit_code}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mode = p.stat().st_mode
    p.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


def dispatch(root: Path, role: str, brief_path: "Path | str",
             env_override: "dict[str, str] | None" = None) -> "tuple[int, str, str]":
    """디스패처 호출 → (exit_code, stdout, stderr).

    MULTIAGENT_ROOT=root, PATH=root/_shared/bin:<기존 PATH> 환경으로
    `python3 <DISPATCHER> <role> <brief>` 실행. env_override가 있으면 추가 덮어쓰기.
    """
    env = {
        **os.environ,
        "MULTIAGENT_ROOT": str(root),
        "PATH": str(root / "_shared" / "bin") + os.pathsep + os.environ.get("PATH", ""),
    }
    if env_override:
        env.update(env_override)
    r = subprocess.run(
        [sys.executable, str(DISPATCHER), role, str(brief_path)],
        capture_output=True, text=True, env=env,
    )
    return r.returncode, r.stdout, r.stderr


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


def finish() -> int:
    """요약 출력, 실패가 없으면 0, 있으면 1 반환."""
    global PASS, FAIL
    print(f"  ({PASS} pass / {FAIL} fail)")
    return 0 if FAIL == 0 else 1

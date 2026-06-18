#!/usr/bin/env python3
"""test_conhost_wrap.py — Windows 전용 코드 경로 회귀 테스트 (Linux 에서 monkeypatching).

이 테스트는 Linux 머신에서 실행되지만, `_shared/adapters/call_worker.py` 의
Windows 분기(Native Windows + agy → conhost.exe --headless 래핑, Issue #76)를
monkeypatching 으로 직접 검증한다. 목표: Windows 개발자가 없어도 Windows 논리
회귀를 잡아내는 것.

커버 (모두 단위 테스트, 실제 서브프로세스 비실행):
1. _resolve_conhost_path() — %SystemRoot%\\System32\\conhost.exe 우선 분기
2. _resolve_conhost_path() — shutil.which 폴백
3. _resolve_conhost_path() — 둘 다 없으면 None
4. run_backend(is_windows_agy=True) — agy 실행파일이 없으면 127 + "conhost" 안내
5. _strip_ansi() — conhost 경로가 쓰는 헬퍼 직접 단언 (통합 테스트는 Linux 불가)
6. _terminate_tree() — POSIX 분기가 SIGTERM → SIGKILL 순서로 os.killpg 호출

한계 (주석):
- conhost.exe 로 감싼 실제 서브프로세스 실행(popen · 자식 트리 종료)은 Linux 에서
  재현할 수 없다. 대신 그 경로가 의존하는 순수 함수 + 조건 분기 + 시그널 헬퍼를
  직접 단언한다 — 회귀를 잡아내는 가장 좁은 결정적 지점들이다.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 디스패처 모듈 임포트 — <repo>/_shared/adapters/call_worker.py
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_shared" / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import call_worker  # noqa: E402
import _lib  # noqa: E402


class _StubPath:
    """Path-like stub: Linux 에서 os.name='nt' 로 강제해도 Path() 가 WindowsPath
    인스턴스화로 죽지 않도록 call_worker.Path 를 치환.

    run_backend 의 is_windows_agy 분기가 쓰는 최소 API(constructor, __truediv__,
    __str__, mkdir)만 흉내낸다 — 실제 파일시스템 접근 없음.
    """

    def __init__(self, *parts: object) -> None:
        self._parts = parts

    def __truediv__(self, other: object) -> "_StubPath":
        return _StubPath(*self._parts, other)

    def __str__(self) -> str:
        return "/".join(str(p) for p in self._parts if str(p))

    def mkdir(self, **_kwargs: object) -> None:  # no-op
        return None


# ── _resolve_conhost_path() ──────────────────────────────────────────────


def test_resolve_conhost_systemroot_present() -> None:
    """_resolve_conhost_path: %SystemRoot%\\System32\\conhost.exe 가 존재하면
    해당 경로를 반환한다."""
    fake_root = "/fake/windows"
    # patch.dict 으로 SystemRoot 주입 + os.path.exists True
    with patch.dict(os.environ, {"SystemRoot": fake_root}, clear=False):
        with patch("os.path.exists", return_value=True):
            got = call_worker._resolve_conhost_path()
    expected = os.path.join(fake_root, "System32", "conhost.exe")
    _lib.assert_eq("SystemRoot 경로 반환", expected, got)


def test_resolve_conhost_shutil_fallback() -> None:
    """_resolve_conhost_path: candidate 가 없으면 shutil.which 폴백."""
    fake_which = "/some/path/conhost.exe"
    with patch.dict(os.environ, {"SystemRoot": "/fake/windows"}, clear=False):
        with patch("os.path.exists", return_value=False):
            with patch("shutil.which", return_value=fake_which):
                got = call_worker._resolve_conhost_path()
    _lib.assert_eq("shutil.which 폴백 경로 반환", fake_which, got)


def test_resolve_conhost_returns_none() -> None:
    """_resolve_conhost_path: 어디에서도 찾지 못하면 None."""
    with patch.dict(os.environ, {"SystemRoot": "/fake/windows"}, clear=False):
        with patch("os.path.exists", return_value=False):
            with patch("shutil.which", return_value=None):
                got = call_worker._resolve_conhost_path()
    _lib.assert_eq("둘 다 없으면 None", None, got)


# ── run_backend: Windows + agy 가 없는 경로 ─────────────────────────────


def test_run_backend_windows_agy_missing_returns_127() -> None:
    """run_backend: os.name=='nt' + agy 명령 + shutil.which('agy')==None 인 경우
    127 envelope 를 반환하고 stderr 에 'conhost' 안내가 들어있어야 한다.

    이것은 run_backend 의 is_windows_agy 조건 분기 + 에러 envelope 조립을 검증한다.
    실제 서브프로세스는 호출되지 않는다 — 127 반환은 execute_subprocess 이전이다.
    """
    spec = {
        "call_type": "cli",
        "cli": {"command": "agy", "args_template": ["--print", "@brief_content"]},
        "model": "agy-test",
        "brief_mode": "content",
        "timeout": 30,
        "cwd_policy": "repo_root",
    }
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        brief = root / "brief.txt"
        brief.write_text("hello", encoding="utf-8")
        brief_bytes = b"hello"

        # os.name=='nt' 로 Windows 분기 강제 + agy 실행파일 없음.
        # Path 를 _StubPath 로 치환: WindowsPath 인스턴스화 에러 회피.
        with patch.object(os, "name", "nt"):
            with patch.object(call_worker, "Path", _StubPath):
                # _build_cli_cmd 안에서 agy 허용list 통과; shutil.which('agy') 는
                # is_windows_agy 블록에서만 호출되므로 단일 return_value=None 로 충분
                with patch("shutil.which", return_value=None):
                    rc, envelope = call_worker.run_backend(
                        spec, brief, brief_bytes, root
                    )

    _lib.assert_eq("agy 없으면 rc=127", 127, rc)
    _lib.assert_eq("envelope exit_code=127", 127, envelope["exit_code"])
    _lib.assert_eq("envelope status=error", "error", envelope["status"])
    _lib.assert_eq("envelope backend=cli", "cli", envelope["backend"])
    _lib.assert_contains(
        "stderr_sanitized 에 conhost 안내",
        "conhost",
        envelope["stderr_sanitized"],
    )


def test_run_backend_windows_agy_missing_envelope_shape() -> None:
    """run_backend: 같은 경로에서 반환된 envelope 가 필수 필드를 모두 가지는지."""
    spec = {
        "call_type": "cli",
        "cli": {"command": "agy", "args_template": ["--print", "@brief_content"]},
    }
    required_keys = {
        "status", "exit_code", "backend", "model",
        "duration_s", "stdout", "stderr_sanitized",
    }
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        brief = Path(d) / "brief.txt"
        brief.write_text("x", encoding="utf-8")
        with patch.object(os, "name", "nt"):
            with patch.object(call_worker, "Path", _StubPath):
                with patch("shutil.which", return_value=None):
                    _, envelope = call_worker.run_backend(
                        spec, brief, b"x", root
                    )
    _lib.assert_eq(
        "envelope has all required keys",
        True,
        required_keys.issubset(envelope.keys()),
    )
    _lib.assert_eq("stdout is empty string on missing", "", envelope["stdout"])
    _lib.assert_eq("duration_s is int >= 0", True, isinstance(envelope["duration_s"], int))


# ── _strip_ansi (conhost 경로가 사용하는 헬퍼) ────────────────────────────


def test_strip_ansi_conhost_relevant_sequences() -> None:
    """_strip_ansi: conhost.exe --headless 로 캡처한 agy 출력에서 흔한 ANSI 시퀀스
    (CSI 색상/리셋/클리어, OSC 윈도우 제목)을 제거하는지.

    LIMITATION: conhost 가 감싼 실제 stdout/stderr 에서 ANSI 가 제거되는지는
    Linux 에서 재현 불가 — run_backend 의 is_windows_agy 분기 자체가 os.name=='nt'
    에만 동작하고 execute_subprocess 를 거치기 때문. 따라서 헬퍼 자체를 다시
    단언한다 (test_dispatcher_misc.test_strip_ansi 와互补 — conhost 관련 시퀀스 특화).
    """
    raw = "\x1b[31magy\x1b[0m\x1b]0;Title\x07\x1b[2Jready"
    got = call_worker._strip_ansi(raw)
    _lib.assert_eq("conhost-style ANSI stripped", "agyready", got)


# ── _terminate_tree POSIX 분기 ────────────────────────────────────────────


def test_terminate_tree_posix_sigterm_first() -> None:
    """_terminate_tree: POSIX 분기에서 os.killpg 를 SIGTERM 으로 먼저 호출.

    Mock proc.wait 가 정상 종료(MagicMock 기본)하면 SIGKILL 경로는 생략되어야 한다.
    """
    proc = MagicMock()
    proc.pid = 99999
    fake_pgid = 88888
    killpg_calls = []

    def fake_killpg(pgid: int, sig: int) -> None:
        killpg_calls.append((pgid, sig))

    # os.name 은 Linux 기본 'posix' — 명시적으로 'posix' 로 고정
    with patch.object(os, "name", "posix"):
        with patch("os.killpg", side_effect=fake_killpg):
            with patch("os.getpgid", return_value=fake_pgid):
                call_worker._terminate_tree(proc)

    _lib.assert_eq(
        "killpg 호출 횟수 (SIGTERM 만, wait 성공으로 SIGKILL 생략)",
        1,
        len(killpg_calls),
    )
    _lib.assert_eq(
        "첫 killpg 가 SIGTERM",
        (fake_pgid, signal.SIGTERM),
        killpg_calls[0] if killpg_calls else None,
    )
    # proc.wait 는 timeout=5 로 호출되어야
    proc.wait.assert_called_once_with(timeout=5)


def test_terminate_tree_posix_sigkill_on_timeout() -> None:
    """_terminate_tree: proc.wait 가 TimeoutExpired 시 SIGKILL 이 추가 호출되어야."""
    proc = MagicMock()
    proc.pid = 99999
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=5)
    fake_pgid = 88888
    killpg_calls = []

    def fake_killpg(pgid: int, sig: int) -> None:
        killpg_calls.append((pgid, sig))

    with patch.object(os, "name", "posix"):
        with patch("os.killpg", side_effect=fake_killpg):
            with patch("os.getpgid", return_value=fake_pgid):
                call_worker._terminate_tree(proc)

    _lib.assert_eq(
        "timeout 시 killpg 2회 (SIGTERM + SIGKILL)",
        2,
        len(killpg_calls),
    )
    if len(killpg_calls) >= 2:
        _lib.assert_eq(
            "두 번째 killpg 가 SIGKILL",
            (fake_pgid, signal.SIGKILL),
            killpg_calls[1],
        )


def test_terminate_tree_posix_killpg_processlookup_swallowed() -> None:
    """_terminate_tree: os.killpg 가 ProcessLookupError 를 던져도 죽지 않아야."""
    proc = MagicMock()
    proc.pid = 99999
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=5)

    with patch.object(os, "name", "posix"):
        with patch("os.killpg", side_effect=ProcessLookupError("no such")):
            with patch("os.getpgid", return_value=12345):
                # 예외 미전파 확인
                call_worker._terminate_tree(proc)
    _lib.assert_eq(
        "ProcessLookupError 삼켜짐 (예외 미전파)", True, True
    )


def test_main() -> int:
    print("Windows 전용 경로 (Linux monkeypatching)")
    test_resolve_conhost_systemroot_present()
    test_resolve_conhost_shutil_fallback()
    test_resolve_conhost_returns_none()
    test_run_backend_windows_agy_missing_returns_127()
    test_run_backend_windows_agy_missing_envelope_shape()
    test_strip_ansi_conhost_relevant_sequences()
    test_terminate_tree_posix_sigterm_first()
    test_terminate_tree_posix_sigkill_on_timeout()
    test_terminate_tree_posix_killpg_processlookup_swallowed()
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(test_main())

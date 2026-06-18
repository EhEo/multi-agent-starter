#!/usr/bin/env python3
"""test_windows_paths.py — bootstrap Windows 코드 경로 회귀 테스트.

Linux 머신에서 실행되지만, `bootstrap/lib/{platform_info,pathing,cli_tools}.py` 의
Windows 분기를 monkeypatching 으로 검증한다. 목표: Windows 개발자가 없어도
Windows 논리 회귀를 잡아내는 것.

커버 (모두 단위 테스트, 실제 PowerShell · 웹 요청 비실행):
1. platform_info.detect() — os.name=='nt' 분기 (Windows)
2. platform_info.detect() — _is_wsl + _parse_os_release 조합 (WSL Linux)
3. pathing.register_path_windows() — PowerShell 스크립트 조립 + subprocess 호출
4. cli_tools.ensure_agy() — Windows native 분기 (irm | iex)
5. cli_tools.ensure_agy() — POSIX 분기 회귀 (curl | bash)

모킹 방침:
- os.name / sys.platform: unittest.mock.patch.object 로 임시 치환
- subprocess.run: 캡처 래퍼로 치환, CompletedProcess(rc=0) 반환
- 외부 도구 검사(shutil.which / have): 결정적 결과 반환
- 모든 monkeypatch 는 try/finally 또는 with 구문으로 원상복구 — 멱등 보장
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402

sys.path.insert(0, str(_lib.REPO))
from bootstrap.lib import cli_tools  # noqa: E402
from bootstrap.lib import pathing  # noqa: E402
from bootstrap.lib import platform_info  # noqa: E402
from bootstrap.lib.platform_info import PlatformInfo  # noqa: E402


# ── platform_info.detect() Windows 분기 ──────────────────────────────────


def test_detect_windows_branch() -> None:
    """detect(): os.name=='nt' 면 PlatformInfo(os_kind='windows') 반환.
    pkg_manager 는 테스트 머신의 which('winget') 결과에 따라 None 또는 'winget'.

    sys.platform='win32' 패치 시 shutil.which 가 _winapi 를 호출하려다 Linux 에서
    죽으므로 platform_info.which 도 함께 치환한다 (Windows pkg_manager 경로가
    실제로 which('winget') 을 부르는지 자체는 test_platform_info.py 가 담당)."""
    with patch.object(os, "name", "nt"):
        with patch.object(sys, "platform", "win32"):
            with patch.object(platform_info, "which", return_value=None):
                info = platform_info.detect()

    _lib.assert_eq("windows: os_kind", "windows", info.os_kind)
    _lib.assert_eq("windows: is_posix=False", False, info.is_posix)
    _lib.assert_eq("windows: is_wsl=False", False, info.is_wsl)
    _lib.assert_eq(
        "windows: pkg_manager in {None, winget}",
        True,
        info.pkg_manager in (None, "winget"),
    )
    _lib.assert_eq("windows: distro_id=None", None, info.distro_id)
    _lib.assert_eq("windows: distro_like=None", None, info.distro_like)


def test_detect_windows_branch_with_winget() -> None:
    """detect(): Windows + winget 감지 시 pkg_manager='winget'."""
    with patch.object(os, "name", "nt"):
        with patch.object(sys, "platform", "win32"):
            with patch.object(platform_info, "which", return_value="/fake/winget.exe"):
                info = platform_info.detect()

    _lib.assert_eq(
        "windows+winget: pkg_manager='winget'",
        "winget",
        info.pkg_manager,
    )


# ── platform_info.detect() WSL 분기 ──────────────────────────────────────


def test_detect_wsl_branch() -> None:
    """detect(): _is_wsl()==True + _parse_os_release()==('ubuntu','debian') 면
    PlatformInfo(os_kind='wsl_linux', is_wsl=True, is_posix=True).

    detect() 자체의 Linux/WSL 분기 로직을 검증 — _is_wsl/_parse_os_release 는
    private helper 이므로 detect() 와의 결합을 잡는 이 단위에서 치환한다.
    /proc/sys/kernel/osrelease · /etc/os-release 파일 자체를 쓰는 테스트는
    다른 테스트 파일(test_platform_info.py)에서 '현재 머신' 기반으로 검증된다.
    """
    with patch.object(os, "name", "posix"):
        with patch.object(sys, "platform", "linux"):
            with patch.object(platform_info, "_is_wsl", return_value=True):
                with patch.object(
                    platform_info,
                    "_parse_os_release",
                    return_value=("ubuntu", "debian"),
                ):
                    info = platform_info.detect()

    _lib.assert_eq("wsl: os_kind=wsl_linux", "wsl_linux", info.os_kind)
    _lib.assert_eq("wsl: is_wsl=True", True, info.is_wsl)
    _lib.assert_eq("wsl: is_posix=True", True, info.is_posix)
    _lib.assert_eq("wsl: distro_id=ubuntu", "ubuntu", info.distro_id)
    _lib.assert_eq("wsl: distro_like=debian", "debian", info.distro_like)


def test_detect_linux_non_wsl_branch() -> None:
    """detect(): _is_wsl()==False + _parse_os_release()==('fedora',None) 면
    os_kind='linux' (wsl_linux 아님)."""
    with patch.object(os, "name", "posix"):
        with patch.object(sys, "platform", "linux"):
            with patch.object(platform_info, "_is_wsl", return_value=False):
                with patch.object(
                    platform_info,
                    "_parse_os_release",
                    return_value=("fedora", None),
                ):
                    info = platform_info.detect()

    _lib.assert_eq("linux: os_kind=linux", "linux", info.os_kind)
    _lib.assert_eq("linux: is_wsl=False", False, info.is_wsl)
    _lib.assert_eq("linux: is_posix=True", True, info.is_posix)


# ── pathing.register_path_windows() ──────────────────────────────────────


def test_register_path_windows_powershell_invocation() -> None:
    """register_path_windows: 'powershell' 서브프로세스 호출 + User PATH SetEnvironmentVariable.

    subprocess.run 을 캡처 래퍼로 치환 — 실제 PowerShell 실행 없이 스크립트 문자열 검증.
    """
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="ok", stderr=""
        )

    extra_dirs = [Path("C:\\fake\\repo\\bin"), Path("C:\\Users\\fake\\agy\\bin")]
    orig_path = os.environ.get("PATH", "")
    try:
        with patch.object(pathing.subprocess, "run", side_effect=fake_run):
            results = pathing.register_path_windows(extra_dirs=extra_dirs)
    finally:
        os.environ["PATH"] = orig_path

    cmd = captured.get("cmd") or []
    _lib.assert_eq("cmd[0] is 'powershell'", "powershell", cmd[0] if cmd else None)
    _lib.assert_eq(
        "cmd contains '-Command' flag",
        True,
        "-Command" in cmd,
    )

    ps_script = cmd[-1] if cmd else ""
    _lib.assert_contains(
        "PS 스크립트: SetEnvironmentVariable 호출",
        "[Environment]::SetEnvironmentVariable",
        ps_script,
    )
    _lib.assert_contains(
        "PS 스크립트: User target",
        "'User'",
        ps_script,
    )
    _lib.assert_contains(
        "PS 스크립트: 첫 extra_dir 포함",
        "C:\\fake\\repo\\bin",
        ps_script,
    )
    _lib.assert_contains(
        "PS 스크립트: 둘째 extra_dir 포함",
        "C:\\Users\\fake\\agy\\bin",
        ps_script,
    )
    _lib.assert_eq(
        "StepResult OK (subprocess rc=0)",
        "OK",
        results[0].status if results else None,
    )


def test_register_path_windows_powershell_missing() -> None:
    """register_path_windows: powershell 없으면 FileNotFoundError → FAIL."""
    orig_path = os.environ.get("PATH", "")
    try:
        with patch.object(
            pathing.subprocess,
            "run",
            side_effect=FileNotFoundError("powershell not found"),
        ):
            results = pathing.register_path_windows(extra_dirs=[Path("C:\\x")])
    finally:
        os.environ["PATH"] = orig_path

    _lib.assert_eq(
        "powershell 없으면 FAIL",
        "FAIL",
        results[0].status if results else None,
    )


# ── cli_tools.ensure_agy() Windows 분기 ──────────────────────────────────


def test_ensure_agy_windows_branch() -> None:
    """ensure_agy: Windows info → PowerShell irm | iex 호출.

    have('agy')==False 로 설치 분기 진입 + _run 캡처로 cmd 검증.
    """
    captured: dict = {}

    def fake_run(cmd, *, shell=False):
        captured["cmd"] = list(cmd)
        return (0, "", "")

    windows_info = PlatformInfo(
        os_kind="windows",
        distro_id=None,
        distro_like=None,
        pkg_manager="winget",
        is_wsl=False,
        is_posix=False,
    )

    with patch.object(cli_tools, "have", return_value=False):
        with patch.object(cli_tools, "_run", side_effect=fake_run):
            result = cli_tools.ensure_agy(windows_info)

    cmd = captured.get("cmd") or []
    _lib.assert_eq(
        "windows: cmd[0] is 'powershell'",
        "powershell",
        cmd[0] if cmd else None,
    )
    _lib.assert_eq(
        "windows: '-ExecutionPolicy' present",
        True,
        "-ExecutionPolicy" in cmd,
    )
    _lib.assert_eq(
        "windows: 'Bypass' policy",
        True,
        "Bypass" in cmd,
    )
    _lib.assert_contains(
        "windows: irm install.ps1 호출",
        "irm https://antigravity.google/cli/install.ps1",
        " ".join(cmd),
    )
    _lib.assert_contains(
        "windows: iex 파이프",
        "iex",
        " ".join(cmd),
    )
    _lib.assert_eq(
        "windows: rc=0 → OK status",
        "OK",
        result.status,
    )


# ── cli_tools.ensure_agy() POSIX 회귀 ────────────────────────────────────


def test_ensure_agy_posix_branch() -> None:
    """ensure_agy: POSIX info → bash -c 'curl ... | bash' 호출 회귀."""
    captured: dict = {}

    def fake_run(cmd, *, shell=False):
        captured["cmd"] = list(cmd)
        return (0, "", "")

    linux_info = PlatformInfo(
        os_kind="linux",
        distro_id="ubuntu",
        distro_like="debian",
        pkg_manager="apt",
        is_wsl=False,
        is_posix=True,
    )

    have_map = {"agy": False, "bash": True, "curl": True}

    with patch.object(cli_tools, "have", side_effect=lambda n: have_map.get(n, False)):
        with patch.object(cli_tools, "_run", side_effect=fake_run):
            result = cli_tools.ensure_agy(linux_info)

    cmd = captured.get("cmd") or []
    _lib.assert_eq(
        "posix: cmd[0] is 'bash'",
        "bash",
        cmd[0] if cmd else None,
    )
    _lib.assert_eq(
        "posix: cmd[1] is '-c'",
        "-c",
        cmd[1] if len(cmd) > 1 else None,
    )
    inner = cmd[2] if len(cmd) > 2 else ""
    _lib.assert_contains(
        "posix: curl install.sh 호출",
        "curl -fsSL https://antigravity.google/cli/install.sh",
        inner,
    )
    _lib.assert_contains(
        "posix: | bash 파이프",
        "| bash",
        inner,
    )
    _lib.assert_eq(
        "posix: rc=0 → OK status",
        "OK",
        result.status,
    )


def test_ensure_agy_posix_missing_bash() -> None:
    """ensure_agy: POSIX 인데 bash 없으면 FAIL (PATH 이상 환경 회귀 방지)."""
    linux_info = PlatformInfo(
        os_kind="linux",
        distro_id="ubuntu",
        distro_like="debian",
        pkg_manager="apt",
        is_wsl=False,
        is_posix=True,
    )
    have_map = {"agy": False, "bash": False, "curl": True}
    with patch.object(cli_tools, "have", side_effect=lambda n: have_map.get(n, False)):
        result = cli_tools.ensure_agy(linux_info)
    _lib.assert_eq(
        "bash 없으면 FAIL",
        "FAIL",
        result.status,
    )
    _lib.assert_contains(
        "FAIL detail mentions bash",
        "bash",
        result.detail,
    )


def test_ensure_agy_skipped_when_present() -> None:
    """ensure_agy: have('agy')==True → 설치 시도 없이 OK 반환 (멱원성).

    _run 자체는 버전 조회(['agy', '--version'])로 호출될 수 있지만,
    PowerShell/curl 설치 명령은 불리지 않아야 한다."""
    captured: list = []

    def fake_run(cmd, *, shell=False):
        captured.append(list(cmd))
        return (0, "agy 1.0.0", "")

    linux_info = PlatformInfo(
        os_kind="linux",
        distro_id=None,
        distro_like=None,
        pkg_manager=None,
        is_wsl=False,
        is_posix=True,
    )
    with patch.object(cli_tools, "have", return_value=True):
        with patch.object(cli_tools, "_run", side_effect=fake_run):
            result = cli_tools.ensure_agy(linux_info)

    install_invoked = any(
        "powershell" in c or "curl" in " ".join(c) or "irm" in " ".join(c)
        for c in captured
    )
    _lib.assert_eq(
        "이미 있으면 설치 명령 미호출",
        False,
        install_invoked,
    )
    _lib.assert_eq(
        "이미 있으면 OK",
        "OK",
        result.status,
    )
    _lib.assert_contains(
        "OK detail mentions 'present'",
        "present",
        result.detail,
    )


def test_main() -> int:
    print("bootstrap Windows 경로 (Linux monkeypatching)")
    test_detect_windows_branch()
    test_detect_windows_branch_with_winget()
    test_detect_wsl_branch()
    test_detect_linux_non_wsl_branch()
    test_register_path_windows_powershell_invocation()
    test_register_path_windows_powershell_missing()
    test_ensure_agy_windows_branch()
    test_ensure_agy_posix_branch()
    test_ensure_agy_posix_missing_bash()
    test_ensure_agy_skipped_when_present()
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(test_main())

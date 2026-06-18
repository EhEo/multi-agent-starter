#!/usr/bin/env python3
"""platform_info.py — OS/WSL/distro/package-manager 정적 감지.

크로스플랫폼(Linux·macOS·WSL·Native Windows). Python 3.8+.
서드파티 의존 0 (distro 패키지 사용 금지 — /etc/os-release 직접 파싱).

모든 감지는 부작용 없이 read-only 이며, 실패해도 예외를 던지지 않고
None/빈값으로 폴백한다. 호출측(orchestrator)이 결과를 stderr에 출력한다.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Optional


@dataclass(frozen=True)
class PlatformInfo:
    """감지된 플랫폼 정보 스냅샷. 한 번 감지하면 불변."""

    os_kind: str
    """windows | macos | wsl_linux | linux"""

    distro_id: Optional[str]
    """Linux 배포 ID (예: ubuntu, fedora, arch). 비-Linux는 None."""

    distro_like: Optional[str]
    """ID_LIKE 값 (예: debian). 비-Linux는 None."""

    pkg_manager: Optional[str]
    """brew | apt | dnf | pacman | winget | None. 실제 설치 가능한 것만."""

    is_wsl: bool
    """WSL(Windows Subsystem for Linux) 내부 여부."""

    is_posix: bool
    """POSIX 계열(macOS·Linux·WSL) 여부. tmux/bash rc 파일 작성 분기용."""


def _is_wsl() -> bool:
    """/proc/sys/kernel/osrelease 에 'microsoft' 가 포함되면 WSL.
    읽기 실패 시 False (비-POSIX 환경 포함)."""
    try:
        text = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore")
        return "microsoft" in text.lower()
    except OSError:
        return False


def _parse_os_release() -> tuple[Optional[str], Optional[str]]:
    """/etc/os-release 에서 ID, ID_LIKE 추출. 없으면 (None, None)."""
    path = Path("/etc/os-release")
    if not path.is_file():
        return None, None
    distro_id: Optional[str] = None
    distro_like: Optional[str] = None
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("ID=") and distro_id is None:
                distro_id = _strip_quotes(line[3:].strip())
            elif line.startswith("ID_LIKE=") and distro_like is None:
                distro_like = _strip_quotes(line[8:].strip())
    except OSError:
        return None, None
    return distro_id or None, distro_like or None


def _strip_quotes(s: str) -> str:
    """os-release 값의 양끝 따옴표 제거."""
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    return s


def _detect_linux_pkg_manager() -> Optional[str]:
    """Linux용 패키지 매니저 우선순위 체인: brew → apt → dnf → pacman.
    PATH 에 있는 첫 번째 것을 반환 (없으면 None)."""
    for mgr in ("brew", "apt", "apt-get", "dnf", "yum", "pacman"):
        if which(mgr):
            # apt-get 은 호출측에서 단순화를 apt 로 정규화
            if mgr in ("apt-get",):
                return "apt"
            if mgr in ("yum",):
                return "dnf"
            return mgr
    return None


def _detect_windows_pkg_manager() -> Optional[str]:
    """Windows: winget 만 지원."""
    return "winget" if which("winget") else None


def detect() -> PlatformInfo:
    """현재 환경을 감지해 PlatformInfo 반환. 예외 없음.

    감지 순서:
    1. Windows (os.name == 'nt')
    2. macOS (sys.platform == 'darwin')
    3. WSL Linux (osrelease 含 microsoft)
    4. Linux (나머지 POSIX)
    """
    if os.name == "nt" or sys.platform == "win32":
        return PlatformInfo(
            os_kind="windows",
            distro_id=None,
            distro_like=None,
            pkg_manager=_detect_windows_pkg_manager(),
            is_wsl=False,
            is_posix=False,
        )

    if sys.platform == "darwin":
        return PlatformInfo(
            os_kind="macos",
            distro_id=None,
            distro_like=None,
            pkg_manager="brew" if which("brew") else None,
            is_wsl=False,
            is_posix=True,
        )

    # 여기부터 Linux 계열
    is_wsl = _is_wsl()
    distro_id, distro_like = _parse_os_release()
    return PlatformInfo(
        os_kind="wsl_linux" if is_wsl else "linux",
        distro_id=distro_id,
        distro_like=distro_like,
        pkg_manager=_detect_linux_pkg_manager(),
        is_wsl=is_wsl,
        is_posix=True,
    )


def describe(info: PlatformInfo) -> str:
    """로그 출력용 한 줄 요약."""
    parts = [info.os_kind]
    if info.is_wsl:
        parts.append("(WSL)")
    if info.distro_id:
        parts.append(f"[{info.distro_id}]")
    if info.distro_like:
        parts.append(f"like={info.distro_like}")
    if info.pkg_manager:
        parts.append(f"pkg={info.pkg_manager}")
    return " ".join(parts)

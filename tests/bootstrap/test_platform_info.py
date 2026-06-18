#!/usr/bin/env python3
"""test_platform_info.py — bootstrap.lib.platform_info.detect() 단위 테스트.

PlatformInfo dataclass shape + 현재 머신에서 detect() 결과가 sanely 나오는지 검증.
특정 distro 이름(linuxmint, ubuntu 등)을 하드코딩하지 않는다 — 범위 세트로 검증.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

# _lib 임포트 (tests/bootstrap 를 sys.path 에 추가)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402

# bootstrap 패키지 임포트 가능하도록 REPO 를 sys.path 에 추가
sys.path.insert(0, str(_lib.REPO))
from bootstrap.lib import platform_info  # noqa: E402

VALID_OS_KINDS = {"linux", "wsl_linux", "macos", "windows"}
VALID_PKG_MANAGERS = {"brew", "apt", "dnf", "pacman", "winget", None}

EXPECTED_FIELDS = {
    "os_kind",
    "distro_id",
    "distro_like",
    "pkg_manager",
    "is_wsl",
    "is_posix",
}


def main() -> int:
    print("bootstrap.lib.platform_info.detect() 구조/값 검증")

    info = platform_info.detect()

    # dataclass 인스턴스인지
    _lib.assert_eq(
        "PlatformInfo is a dataclass instance",
        True,
        dataclasses.is_dataclass(info),
    )

    # 모든 예상 필드 존재
    actual_fields = {f.name for f in dataclasses.fields(info)}
    _lib.assert_eq(
        "PlatformInfo has all expected fields",
        EXPECTED_FIELDS,
        actual_fields,
    )

    # os_kind 범위
    _lib.assert_eq(
        f"os_kind in valid set (got {info.os_kind!r})",
        True,
        info.os_kind in VALID_OS_KINDS,
    )

    # pkg_manager 범위 (None 포함)
    _lib.assert_eq(
        f"pkg_manager in valid set (got {info.pkg_manager!r})",
        True,
        info.pkg_manager in VALID_PKG_MANAGERS,
    )

    # is_wsl/is_posix는 bool
    _lib.assert_eq("is_wsl is bool", True, isinstance(info.is_wsl, bool))
    _lib.assert_eq("is_posix is bool", True, isinstance(info.is_posix, bool))

    # POSIX 머신(Linux/macOS/WSL)에서는 is_posix == True
    if info.os_kind in ("linux", "wsl_linux", "macos"):
        _lib.assert_eq(
            f"is_posix True on {info.os_kind}",
            True,
            info.is_posix,
        )
    if info.os_kind == "windows":
        _lib.assert_eq("is_posix False on windows", False, info.is_posix)

    # WSL 머신이면 os_kind == 'wsl_linux'
    if info.is_wsl:
        _lib.assert_eq(
            "WSL flagged → os_kind=wsl_linux",
            "wsl_linux",
            info.os_kind,
        )

    # describe() 문자열에 os_kind 가 포함되어야 한다
    desc = platform_info.describe(info)
    _lib.assert_contains("describe() contains os_kind", info.os_kind, desc)

    # frozen dataclass 여부 — 해시 가능해야 한다
    try:
        hash(info)
        frozen_ok = True
    except TypeError:
        frozen_ok = False
    _lib.assert_eq("PlatformInfo is frozen/hashable", True, frozen_ok)

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

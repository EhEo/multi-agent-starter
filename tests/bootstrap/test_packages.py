#!/usr/bin/env python3
"""test_packages.py — bootstrap.lib.packages 단위 테스트.

검증:
- PKG_MANAGERS dispatch table shape (5 keys, 각 key 의 tuple 형태)
- have() 가 PATH 상의 도구를 올바르게 감지
- install_package() 가 fake package manager 주입 시 올바르게 dispatch 되어 호출됨
- 실제 패키지 매니저(brew/apt/dnf/...)는 절대 호출하지 않는다
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402

sys.path.insert(0, str(_lib.REPO))
from bootstrap.lib import packages  # noqa: E402

EXPECTED_PKG_MGR_KEYS = {"brew", "apt", "dnf", "pacman", "winget"}


def main() -> int:
    print("bootstrap.lib.packages: PKG_MANAGERS / have / install_package")

    # ── PKG_MANAGERS shape 검증 ──
    keys = set(packages.PKG_MANAGERS.keys())
    for k in EXPECTED_PKG_MGR_KEYS:
        _lib.assert_eq(f"PKG_MANAGERS has {k}", True, k in keys)

    # 각 매니저 엔트리는 비어있지 않은 str tuple 이어야 한다
    for k, cmd in packages.PKG_MANAGERS.items():
        _lib.assert_eq(
            f"PKG_MANAGERS[{k}] is non-empty tuple of str",
            True,
            isinstance(cmd, tuple)
            and len(cmd) > 0
            and all(isinstance(p, str) for p in cmd),
        )

    # ── have() 검증 ──
    # python3 은 현재 이 스크립트를 돌리고 있으므로 반드시 존재
    _lib.assert_eq(
        "have('python3') returns True",
        True,
        packages.have("python3"),
    )
    # 절대 존재하지 않는 도구
    _lib.assert_eq(
        "have('definitely_not_a_tool_xyz') returns False",
        False,
        packages.have("definitely_not_a_tool_xyz"),
    )

    # ── install_package() with FAKE package manager ──
    # 원본 백업
    orig_pkg_mgrs = dict(packages.PKG_MANAGERS)
    orig_need_sudo = packages._need_sudo
    tmpdir = Path(tempfile.mkdtemp(prefix="mabtpkg_"))
    marker = tmpdir / "installed.txt"
    try:
        # fakemgr: sh -c 'echo "$0 installed" > <marker>' <pkgname>
        # 호출 시 cmd = ["sh", "-c", script, package_name] 이 되어
        # $0 == package_name 으로 치환된다.
        install_script = f'echo "$0 installed" > "{marker}"'
        packages.PKG_MANAGERS["fakemgr"] = ("sh", "-c", install_script)

        # fakemgr 는 sudo 체크 경로를 타지 않도록 항상 False 로 우회
        packages._need_sudo = lambda _mgr: False  # noqa: E731

        # 설치 전 마커 없음 확인
        _lib.assert_eq("marker absent before install", False, marker.exists())

        res = packages.install_package("fakemgr", "fakepkg")
        _lib.assert_eq("install_package status OK", "OK", res.status)
        _lib.assert_eq("marker file created", True, marker.exists())
        _lib.assert_contains(
            "marker contains package name",
            "fakepkg installed",
            marker.read_text(encoding="utf-8"),
        )

        # 지원하지 않는 매니저 → FAIL
        res_bad = packages.install_package("nonexistent_mgr_xyz", "whatever")
        _lib.assert_eq("unknown mgr status FAIL", "FAIL", res_bad.status)
    finally:
        # 복구
        packages.PKG_MANAGERS.clear()
        packages.PKG_MANAGERS.update(orig_pkg_mgrs)
        packages._need_sudo = orig_need_sudo
        shutil.rmtree(tmpdir, ignore_errors=True)

    # 복구 후 fakemgr 가 사라졌는지 확인 (오염 방지)
    _lib.assert_eq(
        "fakemgr cleaned from PKG_MANAGERS",
        False,
        "fakemgr" in packages.PKG_MANAGERS,
    )

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

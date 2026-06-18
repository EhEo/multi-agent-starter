#!/usr/bin/env python3
"""packages.py — 시스템 패키지 매니저 dispatch + 의존성 설치.

PKG_MANAGERS: 매니저별 install 명령 템플릿 (Oracle §5).
PACKAGE_NAMES: 논리 도구 이름 → 매니저별 실제 패키지 이름.
have() / install_package() / ensure_system_deps() — 단일 인터페이스.

실패해도 예외를 던지지 않고 (status, msg) 튜플을 반환한다.
install 단계는 호출측의 명시적 결정(check_only, no_install 등)에만 동작한다.
"""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
from dataclasses import dataclass
from shutil import which
from typing import Callable, Dict, List, Optional, Tuple

from bootstrap.lib.platform_info import PlatformInfo


@dataclass(frozen=True)
class StepResult:
    """단일 설치/확인 단계의 결과."""

    status: str  # OK | WARN | FAIL
    detail: str


# ── 매니저별 install 명령 prefix ──
# root 여부에 따라 sudo prepend 여부는 install_package() 내부에서 결정된다.
PKG_MANAGERS: Dict[str, Tuple[str, ...]] = {
    "brew":   ("brew", "install"),
    "apt":    ("apt-get", "install", "-y"),
    "dnf":    ("dnf", "install", "-y"),
    "pacman": ("pacman", "-S", "--noconfirm"),
    "winget": ("winget", "install", "--accept-source-agreements", "--accept-package-agreements"),
}

# 매니저별 apt-get update / dnf makecache 갱신 명령 (선택적)
PKG_REFRESH: Dict[str, Tuple[str, ...]] = {
    "apt":    ("apt-get", "update"),
    "dnf":    ("dnf", "check-refresh"),
}

# ── 패키지 이름 매트릭스 ──
# 논리 이름 → 매니저별 실제 패키지/아이디.
# 빈 값 또는 누락은 "이 매니저로는 설치 불가" 를 뜻한다.
PACKAGE_NAMES: Dict[str, Dict[str, str]] = {
    "git":   {"brew": "git", "apt": "git", "dnf": "git", "pacman": "git",
              "winget": "Git.Git"},
    "bash":  {"brew": "bash", "apt": "bash", "dnf": "bash", "pacman": "bash",
              "winget": ""},  # Windows 는 기본 제공
    "tmux":  {"brew": "tmux", "apt": "tmux", "dnf": "tmux", "pacman": "tmux",
              "winget": ""},  # Windows 미지원 — WARN 처리
    "jq":    {"brew": "jq", "apt": "jq", "dnf": "jq", "pacman": "jq",
              "winget": "jqlang.jq"},
    "node":  {"brew": "node", "apt": "nodejs", "dnf": "nodejs", "pacman": "nodejs",
              "winget": "OpenJS.NodeJS"},
    "npm":   {"brew": "", "apt": "npm", "dnf": "npm", "pacman": "npm",
              "winget": "OpenJS.NodeJS"},  # npm 은 node 에 같이 딸림 (winget)
    "go":    {"brew": "go", "apt": "golang-go", "dnf": "golang", "pacman": "go",
              "winget": "GoLang.Go"},
    "curl":  {"brew": "curl", "apt": "curl", "dnf": "curl", "pacman": "curl",
              "winget": ""},
}


def have(tool_name: str) -> bool:
    """PATH 상에 해당 tool 이 있는지 shutil.which 로 확인."""
    return which(tool_name) is not None


def _need_sudo(pkg_manager: str) -> bool:
    """POSIX 패키지 매니저가 root 권한을 요구하고 현재 root 가 아니면 sudo 필요.
    brew 와 Windows(winget)는 항상 False."""
    if pkg_manager in ("brew", "winget"):
        return False
    try:
        return os.geteuid() != 0
    except AttributeError:  # Windows
        return False


def _have_sudo() -> bool:
    """sudo 실행 가능 여부."""
    return which("sudo") is not None


def install_package(pkg_manager: str, package_name: str) -> StepResult:
    """단일 패키지 설치 시도. 성공/실패 StepResult 반환.

    매니저가 지원하지 않는 패키지(빈 문자열)면 FAIL 로 폴백.
    sudo 가 필요하지만 없으면 FAIL.
    """
    if pkg_manager not in PKG_MANAGERS:
        return StepResult("FAIL", f"unsupported pkg_manager: {pkg_manager}")
    base_cmd = list(PKG_MANAGERS[pkg_manager])

    if pkg_manager in PKG_REFRESH and _need_sudo(pkg_manager):
        refresh = list(PKG_REFRESH[pkg_manager])
        if _need_sudo(pkg_manager):
            if not _have_sudo():
                return StepResult("FAIL", "sudo required but unavailable for refresh")
            refresh = ["sudo"] + refresh
        subprocess.run(refresh, check=False, capture_output=True)

    cmd: List[str] = list(base_cmd)
    if pkg_manager == "winget":
        # winget 은 --id <ID> -e 형태가 더 정확하다
        cmd += ["--id", package_name, "-e"]
    else:
        cmd += [package_name]

    if _need_sudo(pkg_manager):
        if not _have_sudo():
            return StepResult("FAIL", f"sudo required for {pkg_manager} but unavailable")
        cmd = ["sudo"] + cmd

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return StepResult("FAIL", f"{pkg_manager} binary not found: {exc}")
    if proc.returncode == 0:
        return StepResult("OK", f"installed {package_name} via {pkg_manager}")
    stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or ["(no stderr)"]
    return StepResult("FAIL", f"{pkg_manager} install {package_name} failed: {stderr_tail[0]}")


def _ensure_one(
    logical: str,
    binary: Optional[str],
    info: PlatformInfo,
    on_missing: str,
) -> StepResult:
    """단일 논리 도구의 have→install 시도. binary 는 실제 실행파일 이름."""
    binary = binary or logical
    if have(binary):
        path = which(binary) or binary
        return StepResult("OK", f"{logical} present: {path}")

    if on_missing == "skip":
        return StepResult("WARN", f"{logical} missing — skip install")

    if info.pkg_manager is None:
        return StepResult("FAIL" if on_missing == "fail" else "WARN",
                          f"{logical} missing and no pkg_manager detected")

    matrix = PACKAGE_NAMES.get(logical, {})
    pkg = matrix.get(info.pkg_manager, "")
    if not pkg:
        return StepResult("FAIL" if on_missing == "fail" else "WARN",
                          f"{logical} missing and {info.pkg_manager} has no mapping")
    return install_package(info.pkg_manager, pkg)


def ensure_system_deps(info: PlatformInfo) -> List[StepResult]:
    """Tier 1+3+4: python3 sanity, git, bash(POSIX), tmux(POSIX), jq(WARN).

    - python3 는 이미 이 스크립트를 돌리고 있으므로 sanity 만 확인.
    - git 은 hard dependency.
    - bash 는 POSIX 만.
    - tmux 는 POSIX 는 WARN, Windows 는 WARN(bash 런처 비대상이라 정보성).
    - jq 는 Phase A 디스패처가 필요치 않으므로 항상 WARN.
    """
    results: List[StepResult] = []

    # Tier 1: python3 sanity (현재 프로세스의 python)
    py_ok = sys.version_info >= (3, 8)
    if py_ok:
        results.append(StepResult("OK", f"python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"))
    else:
        results.append(StepResult("FAIL", f"python >=3.8 required (got {sys.version_info.major}.{sys.version_info.minor})"))

    # git (hard)
    results.append(_ensure_one("git", "git", info, on_missing="fail"))

    # bash (POSIX only)
    if info.is_posix:
        results.append(_ensure_one("bash", "bash", info, on_missing="warn"))
    else:
        results.append(StepResult("WARN", "bash check skipped on Windows"))

    # tmux (POSIX WARN, Windows WARN)
    if info.is_posix:
        results.append(_ensure_one("tmux", "tmux", info, on_missing="warn"))
    else:
        results.append(StepResult("WARN", "tmux unavailable on native Windows (use WSL)"))

    # jq (always WARN — optional)
    jq_res = _ensure_one("jq", "jq", info, on_missing="warn")
    if jq_res.status == "FAIL":
        jq_res = StepResult("WARN", jq_res.detail)
    results.append(jq_res)

    return results

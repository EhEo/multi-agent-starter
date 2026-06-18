#!/usr/bin/env python3
"""cli_tools.py — claude/codex/agy/node 자동 설치.

모든 ensure_* 함수는 멱등원(idempotent) 이다:
1. have() 로 이미 있으면 OK 반환 (설치 스킵).
2. 없으면 매니저/플랫폼별 공식 설치 시도.
3. 실패 시 예외 대신 (status, msg) 튜플을 반환한다.

node 는 packages.ensure_system_deps 와 겹치지만 npm CLI install 후행 작업을
이 모듈에서 통제하기 위해 별도 보장 함수로 둔다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from bootstrap.lib.packages import PACKAGE_NAMES, StepResult, have, install_package
from bootstrap.lib.platform_info import PlatformInfo


# ── npm 패키지 이름 ──
CLAUDE_NPM = "@anthropic-ai/claude-code"
CODEX_NPM = "@openai/codex"

# agy 공식 설치 스크립트 URL
AGY_INSTALL_URL_POSIX = "https://antigravity.google/cli/install.sh"
AGY_INSTALL_URL_WINDOWS = "https://antigravity.google/cli/install.ps1"

# npm 글로벌 prefix 를 일반 사용자 공간으로 강제할지 (기본 False — 시스템 npm 신뢰)
# 사용자가 권한 문제를 겪으면 별도 안내만 출력.
USER_NPM_PREFIX_HINT = True


def _run(cmd: List[str], *, shell: bool = False) -> tuple[int, str, str]:
    """subprocess.run 래퍼. (returncode, stdout, stderr) 반환."""
    try:
        proc = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as exc:
        return 127, "", f"command not found: {exc}"


def _ok_or_fail(name: str, action: str, rc: int, stderr: str, detail: str = "") -> StepResult:
    """rc==0 → OK, 아니면 FAIL."""
    if rc == 0:
        return StepResult("OK", f"{name}: {action} succeeded{(' — ' + detail) if detail else ''}")
    tail = stderr.strip().splitlines()[-1:] or ["(no stderr)"]
    return StepResult("FAIL", f"{name}: {action} failed: {tail[0]}")


def _version_string(binary: str) -> Optional[str]:
    """도구의 --version 출력(첫 라인). 호출 불가 시 None."""
    if not have(binary):
        return None
    rc, out, _ = _run([binary, "--version"])
    if rc != 0:
        return None
    return out.strip().splitlines()[0] if out.strip() else None


def ensure_node(info: PlatformInfo) -> StepResult:
    """node (및 npm) 보장. 있으면 스킵, 없으면 패키지 매니저로 설치."""
    if have("node") and have("npm"):
        return StepResult("OK", f"node: {_version_string('node') or 'present'}, "
                                f"npm: {_version_string('npm') or 'present'}")
    if info.pkg_manager is None:
        return StepResult("FAIL", "node missing and no pkg_manager detected")
    matrix = PACKAGE_NAMES.get("node", {})
    pkg = matrix.get(info.pkg_manager, "")
    if not pkg:
        return StepResult("FAIL", f"node missing and {info.pkg_manager} has no mapping")
    res = install_package(info.pkg_manager, pkg)
    if res.status != "OK":
        return res
    # apt/dnf/pacman 은 npm 이 별도 패키지일 수 있음
    if info.pkg_manager in ("apt", "dnf", "pacman") and not have("npm"):
        npm_pkg = PACKAGE_NAMES["npm"].get(info.pkg_manager, "")
        if npm_pkg:
            install_package(info.pkg_manager, npm_pkg)
    if not have("node"):
        return StepResult("FAIL", "node install reported OK but binary still missing (PATH issue?)")
    return StepResult("OK", f"node installed: {_version_string('node') or 'present'}")


def _npm_install_global(npm_pkg: str, binary: str, label: str) -> StepResult:
    """npm install -g <pkg>; 설치 후 have(binary) 확인."""
    if have(binary):
        return StepResult("OK", f"{label}: already present ({_version_string(binary) or 'ok'})")
    if not have("npm"):
        return StepResult("FAIL", f"{label} install skipped — npm not on PATH")
    cmd = ["npm", "install", "-g", npm_pkg]
    rc, _, stderr = _run(cmd)
    if rc != 0:
        return _ok_or_fail(label, "npm install -g", rc, stderr)
    # 설치 직후 새 셸에 PATH 반영 전일 수 있으므로 로컬 npm bin 도 확인
    if not have(binary):
        npm_bin_rc, npm_bin_out, _ = _run(["npm", "bin", "-g"])
        if npm_bin_rc == 0:
            npm_bin = npm_bin_out.strip()
            if npm_bin and Path(npm_bin).is_dir():
                candidate = Path(npm_bin) / (binary + (".cmd" if os.name == "nt" else ""))
                if candidate.exists():
                    return StepResult("OK", f"{label}: installed at {candidate} (re-login may be needed for PATH)")
    if have(binary):
        return StepResult("OK", f"{label}: installed ({_version_string(binary) or 'ok'})")
    return StepResult("WARN", f"{label}: npm install reported OK but {binary} still not on PATH "
                              "(re-run after opening a new shell)")


def ensure_claude() -> StepResult:
    """@anthropic-ai/claude-code 글로벌 설치."""
    return _npm_install_global(CLAUDE_NPM, "claude", "claude")


def ensure_codex() -> StepResult:
    """@openai/codex 글로벌 설치."""
    return _npm_install_global(CODEX_NPM, "codex", "codex")


def ensure_agy(info: PlatformInfo) -> StepResult:
    """Antigravity CLI (agy) 공식 인스톨러로 설치.

    POSIX (macOS/Linux/WSL): curl -fsSL <url> | bash → ~/.local/bin/agy
    Windows: powershell irm <url> | iex → %LOCALAPPDATA%\\agy\\bin\\agy.exe
    """
    if have("agy"):
        return StepResult("OK", f"agy: present ({_version_string('agy') or 'ok'})")

    if info.is_posix:
        if not have("bash"):
            return StepResult("FAIL", "agy installer needs bash (not on PATH)")
        if not have("curl"):
            return StepResult("FAIL", "agy installer needs curl (not on PATH)")
        cmd = f"curl -fsSL {AGY_INSTALL_URL_POSIX} | bash"
        rc, _, stderr = _run(["bash", "-c", cmd])
        return _ok_or_fail("agy", "posix installer", rc, stderr)

    # Windows native
    home = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))).resolve()
    agy_path = home / "agy" / "bin" / "agy.exe"
    if agy_path.exists():
        return StepResult("OK", f"agy: present at {agy_path}")
    ps_cmd = (
        f"irm {AGY_INSTALL_URL_WINDOWS} | iex"
    )
    rc, _, stderr = _run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd]
    )
    return _ok_or_fail("agy", "windows installer", rc, stderr,
                       detail=str(agy_path) if agy_path.exists() else "")


def ensure_all_cli(info: PlatformInfo, *, install_cli: bool = True) -> List[StepResult]:
    """node + claude + codex + agy 순서로 보장.

    install_cli=False 면 have() 만 검사하고 설치 시도는 스킵한다.
    이 경우 결과는 OK(있음) / WARN(없음) 만 나온다.
    """
    results: List[StepResult] = []
    node_res = ensure_node(info) if install_cli else (
        StepResult("OK", f"node present ({_version_string('node') or 'ok'})")
        if have("node") else StepResult("WARN", "node missing (--no-install-cli: skip)")
    )
    results.append(node_res)
    if not have("node") or not have("npm"):
        # node 가 없으면 claude/codex(agy) 검사 자체가 의미없음
        for label, binary in (("claude", "claude"), ("codex", "codex")):
            if have(binary):
                results.append(StepResult("OK", f"{label}: present"))
            else:
                results.append(StepResult("WARN", f"{label}: cannot verify (node/npm missing)"))
        results.append(_agy_check_only(info))
        return results

    if install_cli:
        results.append(ensure_claude())
        results.append(ensure_codex())
        results.append(ensure_agy(info))
    else:
        for label, binary in (("claude", "claude"), ("codex", "codex")):
            results.append(
                StepResult("OK", f"{label}: present ({_version_string(binary) or 'ok'})")
                if have(binary) else
                StepResult("WARN", f"{label}: missing (--no-install-cli)")
            )
        results.append(_agy_check_only(info))
    return results


def _agy_check_only(info: PlatformInfo) -> StepResult:
    """install_cli=False 시 agy 검사만."""
    if have("agy"):
        return StepResult("OK", f"agy: present ({_version_string('agy') or 'ok'})")
    # Windows fallback: known install location
    if not info.is_posix:
        home = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))).resolve()
        agy_path = home / "agy" / "bin" / "agy.exe"
        if agy_path.exists():
            return StepResult("OK", f"agy: present at {agy_path}")
    return StepResult("WARN", "agy: missing (--no-install-cli)")

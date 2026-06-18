#!/usr/bin/env python3
"""verify.py — 최종 검증 체크리스트 + 요약 출력.

CheckResult: 단일 검증 항목의 결과.
run_all_checks: 모든 검증 항목 실행 후 List[CheckResult] 반환.
print_summary: stderr 에 [OK]/[WARN]/[FAIL] 태그로 정렬 출력.

Hard check(FAIL 시 전체 중단): python >=3.8, git, node, npm,
    call_worker.py 컴파일, generator 존재, target 검증.
Soft check(WARN/OK): tmux, jq, agy, mat, multiagent launcher.
"""
from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from bootstrap.lib.packages import have
from bootstrap.lib.platform_info import PlatformInfo
from bootstrap.lib import repo as repo_mod


@dataclass(frozen=True)
class CheckResult:
    """검증 항목 결과."""

    name: str
    status: str  # OK | WARN | FAIL
    detail: str


def _ok(name: str, detail: str = "") -> CheckResult:
    return CheckResult(name, "OK", detail)


def _warn(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "WARN", detail)


def _fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "FAIL", detail)


def _check_python_ge_38() -> CheckResult:
    if sys.version_info >= (3, 8):
        v = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return _ok("python>=3.8", v)
    v = f"{sys.version_info.major}.{sys.version_info.minor}"
    return _fail("python>=3.8", f"need >=3.8, got {v}")


def _check_have(name: str, *, required: bool) -> CheckResult:
    path = have(name)
    if path:
        from shutil import which
        return _ok(name, f"present at {which(name)}")
    if required:
        return _fail(name, "not on PATH (required)")
    return _warn(name, "not on PATH (optional)")


def _check_call_worker(repo_root: Path) -> CheckResult:
    """Phase A 디스패처 컴파일 가능 여부 (경로는 flavor 의 _shared/adapters/)."""
    # repo_root 자체에 _shared 가 있을 수도(루트 레이아웃 v1) 있고
    # flavor template 안에만 있을 수도 있다. 두 경로 모두 시도.
    candidates = [
        repo_root / "_shared" / "adapters" / "call_worker.py",
        repo_root / "plugins" / "multi-agent-starter" / "skills" /
        "configure-multiagent" / "generator" / "templates" /
        "claude" / "_shared" / "adapters" / "call_worker.py",
    ]
    for cand in candidates:
        if cand.is_file():
            try:
                py_compile.compile(str(cand), doraise=True)
                return _ok("call_worker.py", f"compiles: {cand}")
            except py_compile.PyCompileError as exc:
                return _fail("call_worker.py", f"compile failed: {exc.msg}")
    return _warn("call_worker.py", "not found at expected paths (post-init check)")


def _check_generator(repo_root: Path) -> CheckResult:
    gen = repo_mod.generator_path(repo_root)
    return _ok("generator init.py", str(gen)) if gen.is_file() else \
        _fail("generator init.py", f"missing: {gen}")


def _check_target(target: Path) -> CheckResult:
    """target 폴더가 존재 + generator 가 생성한 흔적(CLAUDE.md or AGENTS.md) 있는지."""
    if not target.exists():
        return _fail("target", f"does not exist: {target}")
    if not target.is_dir():
        return _fail("target", f"not a directory: {target}")
    markers = ("CLAUDE.md", "AGENTS.md", "_shared", "_templates")
    has_any = any((target / m).exists() for m in markers)
    if has_any:
        return _ok("target", f"initialized: {target}")
    return _warn("target", f"exists but no system files yet: {target}")


def _check_version(binary: str) -> Optional[str]:
    """도구 --version 첫 라인. 없으면 None."""
    if not have(binary):
        return None
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    out = (proc.stdout or proc.stderr or "").strip()
    return out.splitlines()[0] if out else None


def _check_cli_tool(name: str, *, install_requested: bool, info: PlatformInfo) -> CheckResult:
    """name 도구의 검증. install_requested 및 플랫폼별 FAIL/WARN 규칙 적용."""
    ver = _check_version(name)
    if ver is not None:
        return _ok(name, ver)
    if not install_requested:
        return _warn(name, "missing (--no-install-cli)")
    if not info.is_posix:
        return _warn(name, "missing on Windows (manual install required)")
    return _fail(name, "missing despite install request")


def _check_agy(install_requested: bool, info: PlatformInfo) -> CheckResult:
    ver = _check_version("agy")
    if ver is not None:
        return _ok("agy", ver)
    # Windows fallback: known install location
    if not info.is_posix:
        local_app = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))).resolve()
        agy_exe = local_app / "agy" / "bin" / "agy.exe"
        if agy_exe.exists():
            return _ok("agy", f"present at {agy_exe}")
    if not install_requested:
        return _warn("agy", "missing (--no-install-cli)")
    if not info.is_posix:
        return _warn("agy", "missing on Windows (manual install required)")
    return _fail("agy", "missing despite install request")


def _check_mat(target: Path) -> CheckResult:
    """mat --version OR target/_local/bin/mat-here 존재."""
    ver = _check_version("mat")
    if ver is not None:
        return _ok("mat", ver)
    mat_here = target / "_local" / "bin" / "mat-here"
    if mat_here.exists():
        return _ok("mat", f"present at {mat_here}")
    return _warn("mat", "neither `mat` on PATH nor _local/bin/mat-here; multiagent --install-mat suggested")


def _check_multiagent_launcher(info: PlatformInfo) -> CheckResult:
    """`multiagent` 런처가 PATH 에 있는지. POSIX=OK/FAIL, Windows=항상 WARN."""
    if info.is_posix:
        return _check_have("multiagent", required=False)
    return _warn("multiagent", "bash launcher on Windows (use WSL or invoke via bash)")


def run_all_checks(
    repo_root: Path,
    target: Path,
    info: PlatformInfo,
    *,
    install_cli_requested: bool,
) -> List[CheckResult]:
    """모든 검증 항목 실행. 결과는 출력 순서대로 List[CheckResult] 반환."""
    results: List[CheckResult] = []

    # ── Hard checks (FAIL aborts) ──
    results.append(_check_python_ge_38())
    results.append(_check_have("git", required=True))
    results.append(_check_have("node", required=True))
    results.append(_check_have("npm", required=True))
    results.append(_check_call_worker(repo_root))
    results.append(_check_generator(repo_root))
    results.append(_check_target(target))

    # ── Platform soft checks ──
    if info.is_posix:
        results.append(_check_have("tmux", required=False))
    else:
        results.append(_warn("tmux", "unavailable on native Windows (use WSL)"))
    results.append(_check_have("jq", required=False))

    # ── CLI checks ──
    results.append(_check_cli_tool("claude", install_requested=install_cli_requested, info=info))
    results.append(_check_cli_tool("codex", install_requested=install_cli_requested, info=info))
    results.append(_check_agy(install_requested=install_cli_requested, info=info))

    # ── mat ──
    results.append(_check_mat(target))

    # ── multiagent launcher ──
    results.append(_check_multiagent_launcher(info))

    return results


def print_summary(results: List[CheckResult], *, stream=None) -> None:
    """stderr(기본) 에 결과 요약을 [OK]/[WARN]/[FAIL] 태그로 출력."""
    stream = stream or sys.stderr
    for r in results:
        tag = {"OK": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[r.status]
        detail = f" — {r.detail}" if r.detail else ""
        stream.write(f"  {tag} {r.name}{detail}\n")
    stream.flush()


def has_hard_failure(results: List[CheckResult]) -> bool:
    """하드 체크 FAIL 여부. 어느 하나라도 FAIL 이면 True."""
    return any(r.status == "FAIL" for r in results)


def count_statuses(results: List[CheckResult]) -> tuple[int, int, int]:
    """(ok, warn, fail) 카운트."""
    ok = sum(1 for r in results if r.status == "OK")
    warn = sum(1 for r in results if r.status == "WARN")
    fail = sum(1 for r in results if r.status == "FAIL")
    return ok, warn, fail

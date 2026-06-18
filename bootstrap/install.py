#!/usr/bin/env python3
"""install.py — multi-agent-starter 크로스플랫폼 부트스트랩 오케스트레이터.

 한 번 실행하면 신규 PC 에서 `multiagent` 를 어느 폴더에서든 바로
 scaffold+실행 할 수 있는 상태로 만든다. Linux(apt/dnf/pacman) + WSL +
 Native Windows(PowerShell) 모두 지원.

 13-단계 상태머신(Oracle §3):
   1. 플랫폼 감지
   2. 멱등성 가드(marker 존재 시 verify 단계로 점프, --force 시 재실행)
   3. Tier 1: python3, git, bash(POSIX)
   4. Tier 3-4: tmux(POSIX), jq(WARN)
   5. Tier 5: Node.js
   6. Tier 2: claude/codex/agy (--no-install-cli 시 스킵)
   7. Tier 5: mat (bin/multiagent --install-mat 또는 pip install -e .)
   8. 저장소 루트 derive
   9. PATH 영속화 (rc files / User PATH)
   10. Generator 호출 (flavor + target)
   11. 검증 (lib.verify.run_all_checks)
   12. 로그인 가이드 (--skip-login-guide 시 스킵)
   13. 마커 파일 기록 (--check-only 시 스킵)

 CLI:
   python3 bootstrap/install.py [options]
   --flavor <claude|codex|antigravity>  (기본 claude)
   --target <dir>                       (기본 CWD)
   --check-only                         (감지+검증만, 설치/마커/PATH/-generator 스킵)
   --force                              (marker 무시하고 재실행)
   --no-install-cli                     (claude/codex/agy/node 자동 설치 스킵)
   --skip-login-guide                   (끝의 로그인 안내 생략)
   --yes                                (모든 프롬프트에 기본 yes)
   -h, --help                           (사용법 출력)

 진행은 stderr, 최종 요약은 stdout. exit 0=성공, 비0=하드 실패.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Sequence

# ── 부트스트래핑: repo root 를 sys.path 에 추가해 패키지 import 가능하게 ──
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if __package__ in (None, ""):
    __package__ = "bootstrap"

from bootstrap.lib import cli_tools, packages, pathing, platform_info, repo as repo_mod, verify
from bootstrap.lib.packages import StepResult


BOOTSTRAP_VERSION = "1.0.0"
MARKER_REL_POSIX = Path(".local/share/multiagent-bootstrap.done")
MARKER_REL_WINDOWS = Path("multiagent-bootstrap") / "bootstrap.done"


# ── 입출력 유틸 ─────────────────────────────────────────────────────────────
def _say(msg: str) -> None:
    """진행 메시지를 stderr 에 출력."""
    sys.stderr.write(f"[bootstrap] {msg}\n")
    sys.stderr.flush()


def _print_step_results(results: Sequence[StepResult], *, indent: str = "  ") -> None:
    for r in results:
        tag = {"OK": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[r.status]
        sys.stderr.write(f"{indent}{tag} {r.detail}\n")
    sys.stderr.flush()


def _die(msg: str, code: int = 1) -> None:
    sys.stderr.write(f"[bootstrap][error] {msg}\n")
    sys.exit(code)


# ── 인자 파싱 ─────────────────────────────────────────────────────────────────
def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bootstrap/install.py",
        description="multi-agent-starter cross-platform bootstrap installer.",
        add_help=False,
    )
    p.add_argument("--flavor", choices=("claude", "codex", "antigravity"), default="claude")
    p.add_argument("--target", default=str(Path.cwd()))
    p.add_argument("--check-only", action="store_true",
                   help="detect + verify only; never install, mutate PATH, invoke generator, or write marker")
    p.add_argument("--force", action="store_true",
                   help="ignore existing marker and re-run install attempts (per-tool have() still skips)")
    p.add_argument("--no-install-cli", action="store_true",
                   help="skip auto-install of claude/codex/agy/node")
    p.add_argument("--skip-login-guide", action="store_true",
                   help="skip login guide at end")
    p.add_argument("--yes", action="store_true", help="non-interactive; default yes to all prompts")
    p.add_argument("-h", "--help", action="store_true", help="show usage and exit 0")
    ns = p.parse_args(argv)
    if ns.help:
        p.print_help(sys.stdout)
        sys.exit(0)
    return ns


# ── 마커 관리 ─────────────────────────────────────────────────────────────────
def _marker_path(info: platform_info.PlatformInfo) -> Path:
    """플랫폼별 marker 파일 절대 경로. 부모 디렉토리는 만들지 않는다(check_only 안전)."""
    if info.is_posix:
        return Path.home() / MARKER_REL_POSIX
    local_app = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return local_app / MARKER_REL_WINDOWS


def _marker_exists(info: platform_info.PlatformInfo) -> bool:
    p = _marker_path(info)
    return p.is_file()


def _write_marker(info: platform_info.PlatformInfo, repo_root: Path,
                  target: Path, flavor: str) -> None:
    p = _marker_path(info)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _say(f"could not create marker parent dir {p.parent}: {exc}")
        return
    payload = {
        "version": BOOTSTRAP_VERSION,
        "repo": str(repo_root),
        "target": str(target),
        "flavor": flavor,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    try:
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _say(f"marker written: {p}")
    except OSError as exc:
        _say(f"could not write marker {p}: {exc}")


# ── 로그인 가이드 ────────────────────────────────────────────────────────────
def _print_login_guide(flavor: str) -> None:
    sys.stderr.write("\n")
    sys.stderr.write("[bootstrap] login guide:\n")
    if flavor in ("claude", "antigravity"):
        sys.stderr.write("  • claude:   run `claude` once; complete OAuth on first launch.\n")
    if flavor in ("codex", "antigravity"):
        sys.stderr.write("  • codex:    run `codex login` (ChatGPT account) or set OPENAI_API_KEY.\n")
    sys.stderr.write("  • agy:      run `agy auth login` to connect Antigravity/Gemini.\n")
    sys.stderr.write("\n")


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main(argv: List[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))

    # Step 1: 플랫폼 감지
    info = platform_info.detect()
    _say(f"platform: {platform_info.describe(info)}")

    # Step 2: 멱등성 가드
    marker_existed = _marker_exists(info)
    if marker_existed and not args.force and not args.check_only:
        _say(f"marker already present at {_marker_path(info)} — running verification only.")
        _say("(use --force to re-attempt installs; --check-only to suppress message.)")

    # Step 8 (early): repo root derive — 검증 단계에서 필요하므로 일찍 잡는다
    repo_root = repo_mod.find_repo_root()
    _say(f"repo root: {repo_root}")

    target = Path(args.target).expanduser().resolve()
    _say(f"target: {target}")

    # --check-only: 감지 + 검증만. 절대 설치/PATH/marker/generator 터치 금지.
    if args.check_only:
        _say("--check-only: skipping installs, PATH mutation, generator, marker.")
        checks = verify.run_all_checks(
            repo_root, target, info,
            install_cli_requested=not args.no_install_cli,
        )
        verify.print_summary(checks)
        ok, warn, fail = verify.count_statuses(checks)
        sys.stdout.write(
            f"\nbootstrap check-only summary: {ok} OK, {warn} WARN, {fail} FAIL\n"
        )
        return 0 if fail == 0 else 1

    # Step 3+4: Tier 1+3+4 시스템 deps
    _say("step 3-4: system deps (python3, git, bash, tmux, jq)")
    dep_results = packages.ensure_system_deps(info)
    _print_step_results(dep_results)
    # python/git FAIL 시 중단
    dep_failed = [r for r in dep_results if r.status == "FAIL"]
    if dep_failed:
        _die(f"hard dependency check failed: {dep_failed[0].detail}", code=2)

    # Step 5: Tier 5 Node.js — cli_tools 가 npm 과 통합 보장
    _say("step 5: Node.js + npm")
    if args.no_install_cli:
        node_res = (
            StepResult("OK", f"node present ({cli_tools._version_string('node') or 'ok'})")
            if packages.have("node") else
            StepResult("WARN", "node missing (--no-install-cli: skip)")
        )
    else:
        node_res = cli_tools.ensure_node(info)
    _print_step_results([node_res])

    # Step 6: Tier 2 CLI 도구 (claude/codex/agy)
    _say("step 6: CLI tools (claude, codex, agy)")
    cli_results = cli_tools.ensure_all_cli(info, install_cli=not args.no_install_cli)
    _print_step_results(cli_results)

    # Step 7: Tier 5 mat
    _say("step 7: mat (multi-agent tracker)")
    mat_results: List[StepResult] = []
    if packages.have("mat"):
        mat_results.append(StepResult("OK", f"mat already present ({cli_tools._version_string('mat') or 'ok'})"))
    else:
        res = repo_mod.run_install_mat(repo_root)
        if res.status != "OK" and info.is_posix:
            _say(f"bin/multiagent --install-mat failed; falling back to pip install -e .")
            res2 = repo_mod.run_pip_install_editable(repo_root)
            mat_results.append(res2 if res2.status == "OK" else res)
        else:
            mat_results.append(res)
    _print_step_results(mat_results)

    # Step 9: PATH 영속화
    _say("step 9: PATH registration")
    repo_bin = repo_root / "bin"
    path_results = pathing.register_path(repo_bin, extra_dirs=[], is_posix=info.is_posix)
    _print_step_results(path_results)

    # Step 10: Generator 호출
    _say(f"step 10: generator (flavor={args.flavor})")
    if marker_existed and not args.force:
        _say("  marker present + not --force → skipping generator (already initialized)")
        gen_result = StepResult("OK", "skipped (idempotency: marker present)")
    else:
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _die(f"could not create target {target}: {exc}", code=3)
        gen_result = repo_mod.run_generator(repo_root, args.flavor, target, yes=args.yes)
    _print_step_results([gen_result])
    if gen_result.status == "FAIL":
        _die(f"generator failed: {gen_result.detail}", code=4)

    # Step 11: 검증
    _say("step 11: verification")
    checks = verify.run_all_checks(
        repo_root, target, info,
        install_cli_requested=not args.no_install_cli,
    )
    verify.print_summary(checks)
    ok, warn, fail = verify.count_statuses(checks)
    sys.stdout.write(
        f"\nbootstrap verification summary: {ok} OK, {warn} WARN, {fail} FAIL\n"
    )
    if fail > 0:
        _die(f"{fail} hard check(s) failed — see summary above", code=5)

    # Step 12: 로그인 가이드
    if not args.skip_login_guide:
        _print_login_guide(args.flavor)

    # Step 13: 마커 기록
    if marker_existed and not args.force:
        _say("step 13: marker already present (not overwritten without --force)")
    else:
        _say("step 13: writing marker")
        _write_marker(info, repo_root, target, args.flavor)

    sys.stdout.write(
        "bootstrap complete. Open a new shell, then `multiagent` in any folder.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

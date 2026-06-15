#!/usr/bin/env python3
"""multiagent — multi-agent orchestration system CLI.

Thin wrapper around the bundled deterministic generator (init.py).

Flow:
  - 이미 설치된 폴더: 파일 검증(validate.py) 후 CLI 실행
  - 신규 폴더: 파일 복사(init.py) → 검증 → CLI 실행

Usage:
    multiagent                         # claude flavor, 현재 폴더
    multiagent --claude                # claude (기본값)
    multiagent --codex                 # Codex를 오케스트레이터로
    multiagent --antigravity           # Antigravity (Gemini 3.1 Pro High)
    multiagent --target <folder>       # 대상 폴더 지정
    multiagent --yes                   # 확인 생략 (신규 설치 시)
    multiagent --dry-run               # 미리보기 (파일 쓰지 않음)
    multiagent --no-validate           # 검증 건너뜀
    multiagent --no-launch             # CLI 자동 실행 안 함

    multiagent mat                     # mat 모니터를 새 터미널에 실행
    multiagent mat --target <folder>   # 특정 폴더 대상
"""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

_GENERATOR = (
    Path(__file__).resolve().parent
    / "plugins/multi-agent-starter/skills/configure-multiagent/generator/init.py"
)
_MAT_WIN = Path(__file__).resolve().parent / "mat_win.py"

# flavor별 오케스트레이터 파일 (설치 여부 감지용)
_MAIN_FILE = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "antigravity": "AGENTS.md",
}

# flavor별 실행 CLI
_CLI_CMD = {
    "claude": "claude",
    "codex": "codex",
    "antigravity": "agy",
}


def _find_generator() -> Path:
    if not _GENERATOR.is_file():
        sys.exit(
            f"[error] generator not found: {_GENERATOR}\n"
            "Make sure you installed from the multi-agent-starter repo root:\n"
            "  pip install -e .   or   uv tool install --editable ."
        )
    return _GENERATOR


def _is_setup(target: Path, flavor: str) -> bool:
    """backends.json과 오케스트레이터 파일이 모두 있으면 이미 설치된 것으로 판단."""
    return (
        (target / "_shared" / "backends.json").is_file()
        and (target / _MAIN_FILE[flavor]).is_file()
    )


def cmd_generate(args: argparse.Namespace) -> None:
    gen = _find_generator()
    validate_py = gen.parent / "validate.py"

    if args.codex:
        flavor = "codex"
    elif args.antigravity:
        flavor = "antigravity"
    else:
        flavor = "claude"

    target = Path(args.target or ".").expanduser().resolve()

    if _is_setup(target, flavor):
        print(f"\n  이미 설치됨: {target}")
        if not args.no_validate:
            print("  파일 검증 중...")
            rc = subprocess.run(
                [sys.executable, str(validate_py),
                 "--flavor", flavor, "--target", str(target)]
            ).returncode
            if rc != 0:
                sys.exit(f"\n[warn] validate 실패 (exit {rc}) — 재설치: multiagent --yes")
        else:
            print("  검증 건너뜀 (--no-validate)")
    else:
        # 신규 설치
        cmd = [sys.executable, str(gen),
               "--flavor", flavor, "--target", str(target)]
        if args.yes:
            cmd += ["--yes"]
        if args.dry_run:
            cmd += ["--dry-run"]
        if args.no_validate:
            cmd += ["--no-validate"]
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            sys.exit(rc)

    if args.dry_run or args.no_launch:
        return

    cli = _CLI_CMD[flavor]
    print(f"\n  {cli} 실행 중...\n")
    try:
        result = subprocess.run([cli], cwd=str(target))
        sys.exit(result.returncode)
    except FileNotFoundError:
        sys.exit(
            f"\n[error] '{cli}' 명령을 찾을 수 없습니다.\n"
            f"  {cli} 가 설치되어 PATH에 있는지 확인하세요."
        )


def _has_native_mat() -> bool:
    import shutil
    return shutil.which("mat") is not None


def _mat_command(target: str) -> str:
    """Return the shell command string that runs mat (native or fallback)."""
    if _has_native_mat():
        return f"set MAT_ROOT={target}&& mat" if platform.system() == "Windows" \
               else f"MAT_ROOT={target} mat"
    # Fallback: mat_win.py
    py = sys.executable
    mat_win = str(_MAT_WIN)
    if platform.system() == "Windows":
        return f"set PYTHONIOENCODING=utf-8&& \"{py}\" \"{mat_win}\" \"{target}\""
    return f"PYTHONIOENCODING=utf-8 '{py}' '{mat_win}' '{target}'"


def cmd_mat(args: argparse.Namespace) -> None:
    target = str(Path(args.target or ".").expanduser().resolve())
    system = platform.system()
    native = _has_native_mat()

    if not native and not _MAT_WIN.is_file():
        print(f"[error] mat 미설치, mat_win.py 도 없음: {_MAT_WIN}")
        print("  brew install netwaif/tap/mat  (macOS/Linux/WSL)")
        return

    mode = "native mat" if native else "mat_win.py (Python fallback)"

    try:
        if system == "Windows":
            cmd_str = _mat_command(target)
            subprocess.Popen(
                f'start "mat monitor" cmd /c "{cmd_str}"',
                shell=True,
            )
        elif system == "Darwin":
            cmd_str = _mat_command(target)
            script = f'tell application "Terminal" to do script "{cmd_str}"'
            subprocess.Popen(["osascript", "-e", script])
        else:
            cmd_str = _mat_command(target)
            env_cmd = f"{cmd_str}; exec bash"
            for term in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
                try:
                    if term == "gnome-terminal":
                        subprocess.Popen([term, "--", "bash", "-c", env_cmd])
                    else:
                        subprocess.Popen([term, "-e", f"bash -c '{env_cmd}'"])
                    break
                except FileNotFoundError:
                    continue
            else:
                print(f"No terminal found. Run manually:\n  {cmd_str}")
                return
    except Exception as e:
        print(f"[error] Could not launch terminal: {e}")
        return

    print(f"mat monitor launched  ({mode}, MAT_ROOT={target})")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="multiagent",
        description=(
            "파일 기반 멀티에이전트 오케스트레이션 시스템을 설정하고 실행한다.\n"
            "이미 설치된 폴더에서는 파일 검증 후 바로 claude/codex를 실행한다."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  multiagent                          # 현재 폴더, claude\n"
            "  multiagent --codex                  # 현재 폴더, codex\n"
            "  multiagent --target ~/myproject     # 특정 폴더\n"
            "  multiagent --yes                    # 신규 설치 시 확인 생략\n"
            "  multiagent --no-launch              # CLI 자동 실행 안 함\n"
            "  multiagent mat                      # mat 모니터 새 터미널에 실행"
        ),
    )

    sub = ap.add_subparsers(dest="command")

    mat_p = sub.add_parser("mat", help="mat 모니터를 새 터미널 창에서 실행")
    mat_p.add_argument("--target", help="모니터링 폴더 (기본: 현재 폴더)")

    flavor_g = ap.add_mutually_exclusive_group()
    flavor_g.add_argument("--claude", action="store_true",
                          help="Claude Code 오케스트레이터 (기본값)")
    flavor_g.add_argument("--codex", action="store_true",
                          help="Codex 오케스트레이터")
    flavor_g.add_argument("--antigravity", action="store_true",
                          help="Antigravity (Gemini 3.1 Pro High) 오케스트레이터")

    ap.add_argument("--target", help="대상 폴더 (기본: 현재 폴더)")
    ap.add_argument("--yes", action="store_true", help="신규 설치 시 확인 생략")
    ap.add_argument("--dry-run", action="store_true", help="미리보기 (파일 쓰지 않음)")
    ap.add_argument("--no-validate", action="store_true", help="파일 검증 건너뜀")
    ap.add_argument("--no-launch", action="store_true",
                    help="설정 후 claude/codex 자동 실행 안 함")

    args = ap.parse_args()

    if args.command == "mat":
        cmd_mat(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()

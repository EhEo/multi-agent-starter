#!/usr/bin/env python3
# Windows Git Bash용 multiagent 런처를 외부 호출 없이 검증하는 테스트
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "bin" / "multiagent"
BASH = os.environ.get("GIT_BASH", r"C:\Program Files\Git\bin\bash.exe")


def run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def bash_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[1]
    return f"/{drive}{rest}"


def write_exe(path: Path, body: str = "#!/usr/bin/env bash\nexit 0\n") -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    fails = 0
    checks: list[tuple[str, bool, str]] = []

    launcher = bash_path(LAUNCHER)

    syntax = run([BASH, "-n", launcher])
    checks.append(("bash syntax", syntax.returncode == 0, syntax.stderr))

    help_out = run([BASH, launcher, "--help"])
    checks.append(("help exits cleanly", help_out.returncode == 0, help_out.stderr))
    checks.append(("help mentions mat path", "--mat PATH" in help_out.stdout, help_out.stdout))

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        target = root / "workspace"

        fake_generator = root / "init.py"
        fake_generator.write_text("# fake generator placeholder\n", encoding="utf-8")

        write_exe(fake_bin / "uname", "#!/usr/bin/env bash\nprintf 'MINGW64_NT-10.0\\n'\n")
        write_exe(fake_bin / "tmux")
        write_exe(fake_bin / "claude")
        write_exe(fake_bin / "codex")
        write_exe(fake_bin / "mat.exe")
        write_exe(fake_bin / "cygpath", "#!/usr/bin/env bash\nif [ \"$1\" = \"-w\" ]; then printf 'C:\\\\tmp\\\\workspace\\n'; else printf '%s\\n' \"$1\"; fi\n")
        write_exe(
            fake_bin / "python",
            "#!/usr/bin/env bash\n"
            "target=''\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--target' ]; then target=\"$2\"; break; fi\n"
            "  shift\n"
            "done\n"
            "[ -n \"$target\" ] || exit 2\n"
            "mkdir -p \"$target\"\n",
        )

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env['PATH']}"
        env["MULTIAGENT_GENERATOR"] = bash_path(fake_generator)

        setup = run([BASH, launcher, "--setup-only", "--target", bash_path(target), "--mat", bash_path(fake_bin / "mat.exe")], env=env)
        mat_env = target / "_local" / "mat.env"
        mat_here = target / "_local" / "bin" / "mat-here"
        checks.append(("setup-only exits cleanly", setup.returncode == 0, setup.stderr))
        checks.append(("setup-only writes mat.env", mat_env.is_file(), str(mat_env)))
        checks.append(("setup-only writes mat-here", mat_here.is_file(), str(mat_here)))
        checks.append(("mat-here executable", os.access(mat_here, os.X_OK), str(mat_here)))
        if mat_env.is_file():
            text = mat_env.read_text(encoding="utf-8")
            checks.append(("mat.env contains Windows MAT_ROOT", "MAT_ROOT=" in text and "\\workspace" in text, text))
            checks.append(("mat.env contains MAT_EXE", "MAT_EXE=" in text, text))

        capture = root / "mat-args.txt"
        (fake_bin / "mat.exe").write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > {bash_path(capture)}\n", encoding="utf-8")
        (fake_bin / "mat.exe").chmod(0o755)
        newer = target / "tasks" / "newer-task"
        newer.mkdir(parents=True)
        (newer / "task.md").write_text("# newer\n", encoding="utf-8")
        mat_run = run([BASH, bash_path(mat_here)], env=env)
        checks.append(("mat-here exits through fake mat.exe", mat_run.returncode == 0, mat_run.stderr))
        checks.append(("mat-here captures fake mat.exe args", capture.is_file(), str(capture)))
        if capture.is_file():
            checks.append(("mat-here passes newest task", capture.read_text(encoding="utf-8").strip() == "newer-task", capture.read_text(encoding="utf-8")))

    for desc, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")
        if not ok and detail:
            print(detail)
        fails += not ok

    print(f"test_multiagent_windows_launcher: {'all pass' if not fails else f'{fails} fail'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

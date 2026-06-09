#!/usr/bin/env python3
"""multiagent launcher smoke tests.

No network, tmux attach, or real installer calls. The install path is checked
only for the already-installed case via a fake mat binary.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "bin" / "multiagent"


def run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, env=env)


def main() -> None:
    fails = 0

    checks: list[tuple[str, bool, str]] = []

    syntax = run(["bash", "-n", str(LAUNCHER)])
    checks.append(("bash syntax", syntax.returncode == 0, syntax.stderr))

    help_out = run([str(LAUNCHER), "--help"])
    checks.append(("help exits cleanly", help_out.returncode == 0, help_out.stderr))
    checks.append(("help mentions install-mat", "--install-mat" in help_out.stdout, help_out.stdout))

    with tempfile.TemporaryDirectory() as d:
        fake_bin = Path(d)
        fake_mat = fake_bin / "mat"
        fake_mat.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_mat.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env['PATH']}"
        installed = run([str(LAUNCHER), "--install-mat"], env=env)
        checks.append(("install-mat detects existing mat", installed.returncode == 0, installed.stderr))
        checks.append(("install-mat reports existing mat", "already installed" in installed.stderr, installed.stderr))

    with tempfile.TemporaryDirectory() as d:
        fake_home = Path(d)
        fake_local_bin = fake_home / ".local" / "bin"
        fake_local_bin.mkdir(parents=True)
        fake_mat = fake_local_bin / "mat"
        fake_mat.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_mat.chmod(0o755)
        env = os.environ.copy()
        env["HOME"] = str(fake_home)
        installed = run([str(LAUNCHER), "--install-mat"], env=env)
        checks.append(("install-mat detects ~/.local/bin/mat", installed.returncode == 0, installed.stderr))

    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "workspace"
        setup = run([str(LAUNCHER), "--setup-only", "--target", str(target), "--no-install-mat"])
        mat_env = target / "_local" / "mat.env"
        mat_here = target / "_local" / "bin" / "mat-here"
        checks.append(("setup-only exits cleanly", setup.returncode == 0, setup.stderr))
        checks.append(("setup-only writes mat.env", mat_env.is_file(), str(mat_env)))
        checks.append(("setup-only writes mat-here", mat_here.is_file(), str(mat_here)))
        checks.append(("mat-here executable", os.access(mat_here, os.X_OK), str(mat_here)))
        if mat_env.is_file():
            checks.append(("mat.env points at target", str(target) in mat_env.read_text(encoding="utf-8"), mat_env.read_text(encoding="utf-8")))

        fake_bin = Path(d) / "fake-bin"
        fake_bin.mkdir()
        capture = Path(d) / "mat-args.txt"
        fake_mat = fake_bin / "mat"
        fake_mat.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > {capture}\n", encoding="utf-8")
        fake_mat.chmod(0o755)

        older = target / "tasks" / "older-task"
        newer = target / "tasks" / "newer-task"
        older.mkdir()
        newer.mkdir()
        (older / "task.md").write_text("# older\n", encoding="utf-8")
        (newer / "task.md").write_text("# newer\n", encoding="utf-8")
        os.utime(older / "task.md", (1, 1))
        os.utime(newer / "task.md", (2, 2))

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env['PATH']}"
        mat_run = run([str(mat_here)], env=env)
        checks.append(("mat-here exits through fake mat", mat_run.returncode == 0, mat_run.stderr))
        if capture.is_file():
            checks.append(("mat-here passes newest task", capture.read_text(encoding="utf-8").strip() == "newer-task", capture.read_text(encoding="utf-8")))

    for desc, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")
        if not ok and detail:
            print(detail)
        fails += not ok

    print(f"test_multiagent_launcher: {'all pass' if not fails else f'{fails} fail'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""mat_linux.py — Linux/macOS mat monitor for multi-agent-starter.

Pure Python stdlib, no external dependencies.
Polls every 2 seconds and displays task/worker status in the terminal.

Usage:
    python mat_linux.py                    # MAT_ROOT env or CWD
    python mat_linux.py /path/to/root      # explicit root
    MAT_ROOT=/path/to/root python mat_linux.py
"""
from __future__ import annotations

import io
import os
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BRIGHT_GREEN  = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_CYAN   = "\033[96m"

# alternate screen: 진입 시 원래 화면을 보존, 종료 시 복원
_ALT_ENTER = "\033[?1049h"
_ALT_EXIT  = "\033[?1049l"

POLL = 2  # seconds


def _restore_screen(*_):
    sys.stdout.write(_ALT_EXIT)
    sys.stdout.flush()
    sys.exit(0)


def _width() -> int:
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 80


def _parse_yaml(text: str) -> dict:
    """Extract key: value pairs from the first ```yaml block."""
    m = re.search(r"```yaml\s*(.*?)```", text, re.DOTALL)
    if not m:
        return {}
    out: dict = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


def _goal(text: str) -> str:
    m = re.search(r"##\s+Goal\s*\n+(.*?)(?:\n#|\Z)", text, re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        line = line.strip()
        if line:
            return line[:80]
    return ""


def _worker_state(wdir: Path) -> str:
    brief = wdir / "brief.md"
    result = wdir / "result.md"
    has_result = result.exists() and result.stat().st_size > 10
    if not has_result:
        for v in ("result-fix.md", "result-fix2.md"):
            p = wdir / v
            if p.exists() and p.stat().st_size > 10:
                has_result = True
                break
    if has_result:
        return "complete"
    if brief.exists() and brief.stat().st_size > 0:
        return "running"
    return "waiting"


_WICON = {
    "complete": f"{BRIGHT_GREEN}[✓]{RESET}",
    "running":  f"{BRIGHT_YELLOW}[⏳]{RESET}",
    "waiting":  f"{DIM}[ ]{RESET}",
}

_SCOL = {
    "done":        BRIGHT_GREEN,
    "in_progress": BRIGHT_YELLOW,
    "reviewing":   YELLOW,
    "pending":     DIM,
}

_LOG_TAGS = {
    "[ERROR]": RED, "[FAIL]": RED,
    "[PASS]": BRIGHT_GREEN, "[DONE]": BRIGHT_GREEN,
    "[WORKER]": BRIGHT_YELLOW, "[ACTION]": BRIGHT_YELLOW,
    "[APPROVAL]": CYAN, "[VERIFICATION]": CYAN,
}


def _render(root: Path, pinned_task: str | None) -> None:
    # 출력 전체를 버퍼에 모은다 — 한 번의 write로 플래시 없이 갱신
    buf = io.StringIO()
    p = lambda *a, **kw: print(*a, **kw, file=buf)

    w = _width()
    now = datetime.now().strftime("%H:%M:%S")
    sep = "─" * w

    tasks_dir = root / "tasks"
    p(f"{BOLD}mat{RESET}  {CYAN}{root.name}{RESET}  {DIM}{now}{RESET}  Ctrl+C 종료")
    p(sep)

    if not tasks_dir.is_dir():
        p(f"\n  {DIM}tasks/ 없음 — multiagent 로 시스템을 먼저 설정하세요{RESET}")
        _flush(buf)
        return

    task_dirs = sorted(
        [d for d in tasks_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not task_dirs:
        p(f"\n  {DIM}아직 작업이 없습니다{RESET}")
        _flush(buf)
        return

    # Select active task
    active: Path | None = None
    if pinned_task:
        cand = tasks_dir / pinned_task
        if cand.is_dir():
            active = cand
    if not active:
        for td in task_dirs:
            pt = td / "task.md"
            if pt.exists():
                meta = _parse_yaml(pt.read_text(encoding="utf-8", errors="ignore"))
                if meta.get("status", "") in ("in_progress", "reviewing", "waiting"):
                    active = td
                    break
        if not active:
            active = task_dirs[0]

    # Read task.md
    task_md = active / "task.md"
    text = task_md.read_text(encoding="utf-8", errors="ignore") if task_md.exists() else ""
    meta = _parse_yaml(text)
    status   = meta.get("status", "?")
    updated  = meta.get("updated", "")
    priority = meta.get("priority", "")
    goal     = _goal(text)
    scol     = _SCOL.get(status, "")

    p(f"  작업: {BOLD}{active.name}{RESET}  상태: {scol}{status}{RESET}  "
      f"갱신: {DIM}{updated}{RESET}  우선순위: {priority}")
    if goal:
        p(f"  목표: {goal}")
    p()

    # Workers
    wdir = active / "workers"
    if wdir.is_dir():
        wdirs = sorted(d for d in wdir.iterdir() if d.is_dir())
        if wdirs:
            p(f"  {BOLD}Workers{RESET}")
            for wd in wdirs:
                state = _worker_state(wd)
                icon  = _WICON.get(state, "[ ]")
                brief_line = ""
                bp = wd / "brief.md"
                if bp.exists():
                    for ln in bp.read_text(encoding="utf-8", errors="ignore").splitlines():
                        ln = ln.strip()
                        if ln and not ln.startswith("#"):
                            brief_line = ln[:50]
                            break
                rp = wd / "result.md"
                mtime = ""
                ref = rp if rp.exists() else bp
                if ref.exists():
                    mtime = datetime.fromtimestamp(ref.stat().st_mtime).strftime("%H:%M")
                p(f"  {icon} {CYAN}{wd.name:<16}{RESET} {state:<10} "
                  f"{DIM}{mtime:<6}{RESET} {brief_line}")
            p()

    # Log tail
    log_p = active / "log.md"
    if log_p.exists():
        lines = [ln for ln in log_p.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
        tail  = lines[-8:]
        if tail:
            p(f"  {BOLD}Log{RESET}")
            for line in tail:
                col = ""
                for tag, c in _LOG_TAGS.items():
                    if tag in line:
                        col = c
                        break
                line_out = line[:w - 4]
                p(f"  {col}{line_out}{RESET}" if col else f"  {DIM}{line_out}{RESET}")
            p()

    # Footer: task list
    p(sep)
    names = [d.name for d in task_dirs[:6]]
    p(f"  {DIM}작업: {' | '.join(names)}{RESET}")
    p(f"  {DIM}폴링 {POLL}s  Ctrl+C 종료{RESET}")

    _flush(buf)


def _flush(buf: io.StringIO) -> None:
    # 커서 홈으로 이동 → 새 내용 → 이전 내용 잔상 제거 — 모두 한 write()
    sys.stdout.write("\033[H" + buf.getvalue() + "\033[J")
    sys.stdout.flush()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("usage: mat [root_dir]\n\n"
              "  root_dir  모니터링할 폴더 (기본: MAT_ROOT 환경변수 또는 현재 폴더)\n\n"
              "  Ctrl+C 로 종료\n")
        return

    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).expanduser().resolve()
    else:
        env = os.environ.get("MAT_ROOT", "")
        root = Path(env).expanduser().resolve() if env else Path.cwd()

    if not root.is_dir():
        sys.exit(f"[error] 폴더 없음: {root}")

    pinned = sys.argv[2] if len(sys.argv) > 2 else None

    # SIGTERM 처리 — alternate screen 복원 후 종료
    signal.signal(signal.SIGTERM, _restore_screen)

    # alternate screen 진입 (Ctrl+C, 종료 시 원래 화면 복원)
    sys.stdout.write(_ALT_ENTER)
    sys.stdout.flush()

    try:
        while True:
            try:
                _render(root, pinned)
            except Exception as e:
                sys.stdout.write("\033[H\033[J")
                print(f"[error] {e}", flush=True)
            time.sleep(POLL)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(_ALT_EXIT)
        sys.stdout.flush()
        print("mat 종료.")


if __name__ == "__main__":
    main()

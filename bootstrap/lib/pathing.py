#!/usr/bin/env python3
"""pathing.py — PATH 영속화 (POSIX rc files / Windows User PATH).

POSIX:
    - ~/.profile, ~/.bashrc, ~/.bash_profile, ~/.zshrc 중
      "이미 존재" 하거나 "현재 셸 rc" 인 파일에만 마커 블록 추가.
    - 마커 블록 포맷 (정확한 delimiter 로 dedup):
          # >>> multiagent-bootstrap >>>
          export PATH="/abs/path/to/bin:$HOME/.local/bin:$PATH"
          # <<< multiagent-bootstrap <<<
    - 이미 블록이 있으면 skip.
    - 현재 프로세스 PATH 도 같이 갱신(verification 가 즉시 통과하도록).

Windows:
    - PowerShell 로 [Environment]::SetEnvironmentVariable('Path', ..., 'User') 호출.
    - 실패 시 수동 안내를 stdout 으로 출력한다.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

from bootstrap.lib.packages import StepResult


# POSIX 마커 delimiter
MARKER_BEGIN = "# >>> multiagent-bootstrap >>>"
MARKER_END = "# <<< multiagent-bootstrap <<<"

# POSIX rc 파일 후보 (존재 또는 현재 셸 rc 면 작성 대상)
POSIX_RC_FILES = (".profile", ".bashrc", ".bash_profile", ".zshrc")


def _current_shell_rc() -> str | None:
    """$SHELL 기반으로 현재 셸 rc 파일명 추정 (없으면 None)."""
    shell = os.environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return ".zshrc"
    if shell.endswith("bash"):
        return ".bashrc"
    return None


def _build_block(path_entries: Sequence[str]) -> str:
    """path_entries 로부터 POSIX 마커 블록 문자열 생성."""
    joined = ":".join(list(path_entries) + ["$PATH"])
    return f"{MARKER_BEGIN}\nexport PATH=\"{joined}\"\n{MARKER_END}\n"


def _block_present(content: str) -> bool:
    """파일 내용에 마커 블록이 이미 있는지 확인."""
    return MARKER_BEGIN in content and MARKER_END in content


def register_path_posix(
    repo_bin: Path,
    extra_dirs: Sequence[Path] = (),
) -> List[StepResult]:
    """POSIX rc 파일들에 repo/bin + extra_dirs 를 PATH 로 추가.

    기본 extra: $HOME/.local/bin (mat/agy 공통 목적지).
    """
    home = Path.home()
    local_bin = home / ".local" / "bin"
    entries: List[str] = [str(repo_bin)]
    entries += [str(d) for d in extra_dirs]
    if str(local_bin) not in entries:
        entries.append(str(local_bin))

    block = _build_block(entries)
    written_to: List[str] = []
    skipped: List[str] = []

    current_rc = _current_shell_rc()
    for rc_name in POSIX_RC_FILES:
        rc_path = home / rc_name
        is_current = rc_name == current_rc
        if not rc_path.exists() and not is_current:
            continue
        try:
            content = rc_path.read_text(encoding="utf-8", errors="ignore") if rc_path.exists() else ""
        except OSError as exc:
            skipped.append(f"{rc_path}: read failed ({exc})")
            continue
        if _block_present(content):
            skipped.append(f"{rc_path}: marker already present")
            continue
        try:
            with rc_path.open("a", encoding="utf-8") as fp:
                if content and not content.endswith("\n"):
                    fp.write("\n")
                fp.write("\n")
                fp.write(block)
            written_to.append(str(rc_path))
        except OSError as exc:
            skipped.append(f"{rc_path}: write failed ({exc})")

    # 현재 프로세스 PATH 도 즉시 갱신
    new_paths = [str(repo_bin), str(local_bin)] + [str(d) for d in extra_dirs]
    existing = os.environ.get("PATH", "")
    parts = existing.split(os.pathsep) if existing else []
    merged: List[str] = []
    for np in new_paths:
        if np not in merged:
            merged.append(np)
    for p in parts:
        if p and p not in merged:
            merged.append(p)
    os.environ["PATH"] = os.pathsep.join(merged)

    detail = "rc files updated: " + (", ".join(written_to) if written_to else "(none)")
    if skipped:
        detail += " | skipped: " + "; ".join(skipped)
    return [StepResult("OK" if written_to or skipped else "FAIL", detail)]


def register_path_windows(
    extra_dirs: Sequence[Path] = (),
) -> List[StepResult]:
    """Windows User PATH 에 repo\\bin, %LOCALAPPDATA%\\agy\\bin 을 추가.

    PowerShell 로 [Environment]::Get/SetEnvironmentVariable('Path', ..., 'User') 사용.
    실패 시 수동 지시를 stderr 로 안내.
    """
    local_app = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))).resolve()
    agy_bin = local_app / "agy" / "bin"
    additions: List[str] = [str(d) for d in extra_dirs]
    if str(agy_bin) not in additions:
        additions.append(str(agy_bin))

    # 현재 프로세스 PATH 즉시 갱신
    existing = os.environ.get("PATH", "")
    parts = existing.split(os.pathsep) if existing else []
    merged: List[str] = []
    for np in additions:
        if np and np not in merged:
            merged.append(np)
    for p in parts:
        if p and p not in merged:
            merged.append(p)
    os.environ["PATH"] = os.pathsep.join(merged)

    # PowerShell 로 영속화
    additions_ps = ";".join(additions)
    ps_script = (
        "$additions = '" + additions_ps + "'.Split(';') | Where-Object { $_ -ne '' };\n"
        "$current = [Environment]::GetEnvironmentVariable('Path', 'User');\n"
        "$parts = if ($current) { $current.Split(';') } else { @() };\n"
        "foreach ($a in $additions) { if ($parts -notcontains $a) { $parts = @($a) + $parts } };\n"
        "$new = ($parts -join ';');\n"
        "[Environment]::SetEnvironmentVariable('Path', $new, 'User');\n"
        "Write-Output $new"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return [StepResult("FAIL", "powershell not found — manual PATH edit required")]
    if proc.returncode != 0:
        sys.stderr.write(
            "[manual] PowerShell PATH mutation failed. Add manually to User PATH:\n"
            + "\n".join(f"  {a}" for a in additions) + "\n"
        )
        return [StepResult("WARN", "PowerShell PATH mutation failed; manual instructions printed")]
    return [StepResult("OK", f"Windows User PATH updated (+{len(additions)} entries)")]


def register_path(
    repo_bin: Path,
    extra_dirs: Sequence[Path] = (),
    *,
    is_posix: bool,
) -> List[StepResult]:
    """플랫폼 분기. POSIX 면 rc-file 라인, Windows 면 User PATH."""
    if is_posix:
        return register_path_posix(repo_bin, extra_dirs)
    return register_path_windows(extra_dirs)

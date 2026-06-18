#!/usr/bin/env python3
"""call_worker.py — backends.json 디스패처 (cli/api 전용).
native/mcp는 오케스트레이터가 직접 호출(디스패처 비경유).
사용: call_worker.py <role> <brief-file>
반환: stdout에 result envelope(JSON). exit 0=성공, 비0=실패/거부.

크로스플랫폩(Linux·macOS·WSL·Native Windows). Python 3.8+.
표준 라이브러리 전용(서드파티 의존 0).
기존 bash(call_worker.sh) + Python timeout 러너(_run.py)를 단일 파일로 통합.

Native Windows + agy: conhost.exe --headless 래핑(Issue #76). 래핑하지 않으면
apy가 detached console 요청 시 프롬프트 루프로 인해 무한정지된다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 상수 ──
ALLOWLIST_CMDS = ("agy", "codex", "claude")
# ANSI 이스케이프 제거: CSI(ESC[...letter), OSC(ESC]...BEL/ST), 단일 ESC 문자
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.")
# 32자 이상의 연속된 [A-Za-z0-9_-] 문자열 → 토큰/시크릿으로 간주해 마스킹(stderr만)
_REDACT_RE = re.compile(r"[A-Za-z0-9_-]{32,}")


def die(msg: str, code: int) -> None:
    """stderr에 에러 메시지 출력 후 지정된 종료코드로 즉시 종료."""
    sys.stderr.write(f"call_worker: {msg}\n")
    sys.exit(code)


def emit_envelope(envelope: Dict[str, Any]) -> None:
    """stdout에 envelope(JSON, 단일 라인, newline 종료) 출력. stdout은 envelope ONLY."""
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False) + "\n")


def _redact_stderr(text: str) -> str:
    return _REDACT_RE.sub("[REDACTED]", text)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _terminate_tree(proc: subprocess.Popen) -> None:
    """크로스플랫폼 프로세스 트리 종료.
    POSIX: 프로세스그룹 SIGTERM → 5s 대기 → SIGKILL.
    Windows: CTRL_BREAK_EVENT → 5s 대기 → taskkill /T /F → proc.kill()."""
    if os.name == "nt":
        ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
        if ctrl_break is not None:
            try:
                proc.send_signal(ctrl_break)
            except (ValueError, OSError):
                pass
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
        # taskkill /T /F(자식까지 강제). 출력은 억제.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        try:
            proc.kill()
        except OSError:
            pass
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.kill()
        except OSError:
            pass


def execute_subprocess(
    cmd: List[str],
    cwd: str,
    timeout: int,
    stdin_input: Optional[bytes],
) -> Tuple[int, bytes, bytes]:
    """서브프로세스 실행(크로스플랫폼, 타임아웃 보장).
    stdin_input: None → DEVNULL, bytes → PIPE로 전달.
    반환: (exit_code, stdout_bytes, stderr_bytes).
    타임아웃 시 124 반환(coreutils timeout 의미와 일치). 출력은 종료 직전까지 버퍼링된 분."""
    env = {**os.environ, "CI": "1", "DEBIAN_FRONTEND": "noninteractive"}

    if os.name == "nt":
        popen_kwargs: Dict[str, Any] = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        popen_kwargs = {"start_new_session": True}

    stdin = subprocess.PIPE if stdin_input is not None else subprocess.DEVNULL

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **popen_kwargs,
        )
    except FileNotFoundError as exc:
        # 명령어가 PATH에 없음. coreutils timeout과 동일하게 127 반환.
        return 127, b"", str(exc).encode("utf-8", "replace")

    try:
        out, err = proc.communicate(input=stdin_input, timeout=timeout)
        return proc.returncode if proc.returncode is not None else 0, out, err
    except subprocess.TimeoutExpired:
        _terminate_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except (subprocess.TimeoutExpired, ValueError):
            out, err = b"", b""
        return 124, out or b"", err or b""


def _resolve_conhost_path() -> Optional[str]:
    """conhost.exe 경로 해석. %SystemRoot%\\System32\\conhost.exe 우선, 없으면 PATH 검색."""
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(sysroot, "System32", "conhost.exe")
    if os.path.exists(candidate):
        return candidate
    return shutil.which("conhost.exe")


def _build_cli_cmd(
    spec: Dict[str, Any],
    brief_path: Path,
    brief_bytes: bytes,
    bmode: str,
) -> Tuple[List[str], Optional[bytes]]:
    """cli 백엔드 명령어 조립. @brief(경로)/@brief_content(파일내용) 토큰 치환."""
    cli = spec.get("cli") or {}
    command_bin = cli.get("command", "")
    if command_bin not in ALLOWLIST_CMDS:
        die(f"command allowlist 위반: {command_bin}", 7)

    cmd: List[str] = [command_bin]
    for a in cli.get("args_template", []) or []:
        if a == "@brief":
            cmd.append(str(brief_path))
        elif a == "@brief_content":
            cmd.append(brief_bytes.decode("utf-8", errors="replace"))
        else:
            cmd.append(a)

    # codex 워커: 기본은 git 요구(안전망). git 없으면 명확히 실패.
    # 옵트아웃(MULTIAGENT_CODEX_SKIP_GIT=1) 시에만 --skip-git-repo-check 주입(exec 직후).
    if command_bin == "codex":
        if os.environ.get("MULTIAGENT_CODEX_SKIP_GIT", "0") == "1":
            new_cmd: List[str] = []
            injected = False
            for x in cmd:
                new_cmd.append(x)
                if not injected and x == "exec":
                    new_cmd.append("--skip-git-repo-check")
                    injected = True
            cmd = new_cmd
        elif shutil.which("git") is None:
            die(
                "codex 워커는 git이 필요합니다. git 설치 후 재시도하거나, "
                "위험을 감수하면 MULTIAGENT_CODEX_SKIP_GIT=1 로 우회하세요.",
                8,
            )

    # stdin_input 결정: bmode가 stdin일 때만 brief bytes를 PIPE로 전달. 나머지는 DEVNULL.
    stdin_input: Optional[bytes] = brief_bytes if bmode == "stdin" else None
    return cmd, stdin_input


def _build_api_cmd(
    spec: Dict[str, Any],
    brief_path: Path,
    brief_bytes: bytes,
    bmode: str,
    root: Path,
) -> Tuple[List[str], Optional[bytes]]:
    """api 백엔드 명령어 조립. 확장자별 인터프리터(.sh → bash, .py → python3, 기본 bash)."""
    api = spec.get("api") or {}
    ref = api.get("ref", "")
    if not ref.startswith("adapters/"):
        die(f"api.ref는 adapters/ 내부만: {ref}", 7)
    if ".." in ref:
        die(f"api.ref에 '..' 금지: {ref}", 7)
    script_path = root / "_shared" / ref
    if not script_path.is_file():
        die(f"api 스크립트 없음: {ref}", 4)

    for name in api.get("required_env", []) or []:
        if not os.environ.get(name):
            die(f"필수 env 없음: {name}", 4)

    # 확장자별 인터프리터
    if ref.endswith(".py"):
        cmd: List[str] = ["python3", str(script_path)]
    else:
        cmd = ["bash", str(script_path)]

    # brief_pass 정책(기본 arg1, stdin이면 bmode 강제 전환)
    brief_pass = api.get("brief_pass", "arg1")
    effective_bmode = "stdin" if brief_pass == "stdin" else bmode
    if brief_pass == "arg1":
        cmd.append(str(brief_path))

    stdin_input: Optional[bytes] = brief_bytes if effective_bmode == "stdin" else None
    return cmd, stdin_input


def run_backend(
    spec: Dict[str, Any],
    brief_path: Path,
    brief_bytes: bytes,
    root: Path,
) -> Tuple[int, Dict[str, Any]]:
    """단일 backend spec 실행 → (exit_code, envelope). envelope는 fallback_used 미포함(호출자가 추가)."""
    ctype = spec.get("call_type", "")
    if ctype in ("native", "mcp"):
        die("native/mcp는 오케스트레이터 직접 호출(디스패처 비경유)", 3)
    if ctype not in ("cli", "api"):
        die(f"잘못된 call_type: {ctype}", 7)

    model = spec.get("model", "?")
    bmode = spec.get("brief_mode", "content")
    tmo = int(spec.get("timeout", 300))
    cwdp = spec.get("cwd_policy", "repo_root")

    is_windows = os.name == "nt"
    is_windows_agy = (
        is_windows
        and ctype == "cli"
        and (spec.get("cli") or {}).get("command") == "agy"
    )

    # cwd 결정
    tmpdir_cleanup: Optional[str] = None
    if is_windows_agy:
        # Native Windows + agy: 안정적인 프로젝트별 워크스페이스(작업신뢰 프롬프트 루프 방지).
        # 디렉토리 자체는 디스패처가 생성. settings.json trustedWorkspaces는 init.py 소관(여기서 안 건드림).
        h = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
        cwd = str(Path(tempfile.gettempdir()) / "multi-agent-starter" / "agy-workspaces" / h)
        Path(cwd).mkdir(parents=True, exist_ok=True)
    elif cwdp == "isolated_tmp":
        cwd = tempfile.mkdtemp()
        tmpdir_cleanup = cwd
    elif cwdp == "target":
        cwd = os.environ.get("TARGET_REPO", str(root))
    else:
        cwd = str(root)

    try:
        if ctype == "cli":
            cmd, stdin_input = _build_cli_cmd(spec, brief_path, brief_bytes, bmode)
        else:
            cmd, stdin_input = _build_api_cmd(spec, brief_path, brief_bytes, bmode, root)

        # Native Windows + agy: conhost.exe --headless 래핑(Issue #76).
        if is_windows_agy:
            agy_path = shutil.which("agy")
            conhost = _resolve_conhost_path() if agy_path is not None else None
            if agy_path is None or conhost is None:
                missing = "agy 실행파일" if agy_path is None else "conhost.exe"
                err_msg = (
                    f"call_worker: Native Windows에서 agy 워커는 conhost.exe가 필요합니다 "
                    f"(Issue #76). {missing}을(를) 찾을 수 없습니다."
                )
                return 127, {
                    "status": "error",
                    "exit_code": 127,
                    "backend": "cli",
                    "model": model,
                    "duration_s": 0,
                    "stdout": "",
                    "stderr_sanitized": _redact_stderr(err_msg),
                }
            cmd = [conhost, "--headless", agy_path, *cmd[1:]]
            # conhost 경로는 항상 PIPE(즉시 닫힘). stdin 모드면 brief bytes, 나머지는 빈 입력.
            stdin_input = brief_bytes if stdin_input is not None else b""

        start = time.time()
        rc, out_b, err_b = execute_subprocess(cmd, cwd, tmo, stdin_input)
        duration = int(time.time() - start)

        out_s = out_b.decode("utf-8", errors="replace")
        err_s = err_b.decode("utf-8", errors="replace")

        # Native Windows + agy: ANSI 이스케이프 제거(stdout+stderr), 그 후 stderr redact
        if is_windows_agy:
            out_s = _strip_ansi(out_s)
            err_s = _strip_ansi(err_s)

        if rc == 124:
            status = "timeout"
        elif rc == 0:
            status = "ok"
        else:
            status = "error"

        envelope: Dict[str, Any] = {
            "status": status,
            "exit_code": rc,
            "backend": ctype,
            "model": model,
            "duration_s": duration,
            "stdout": out_s,
            "stderr_sanitized": _redact_stderr(err_s),
        }
        return rc, envelope
    finally:
        if tmpdir_cleanup:
            shutil.rmtree(tmpdir_cleanup, ignore_errors=True)


def main() -> int:
    # ── argv ──
    if len(sys.argv) != 3 or not sys.argv[1] or not sys.argv[2]:
        die("usage: call_worker.py <role> <brief-file>", 64)
    role = sys.argv[1]
    brief_arg = sys.argv[2]

    # ── root 해석(MULTIAGENT_ROOT env 우선, 없으면 스크립트 기준 parent³) ──
    root_env = os.environ.get("MULTIAGENT_ROOT")
    root = Path(root_env).resolve() if root_env else Path(__file__).resolve().parent.parent.parent
    backends_path = root / "_shared" / "backends.json"
    if not backends_path.is_file():
        die(f"backends.json 없음: {backends_path}", 5)

    # ── brief 검증(정규화 전 literal '..' 금지 → 파일존재 → 절대경로화) ──
    if ".." in brief_arg:
        die("brief 경로에 '..' 금지", 6)
    brief_path_raw = Path(brief_arg)
    if not brief_path_raw.is_file():
        die(f"brief 파일 없음: {brief_arg}", 6)
    brief_path = brief_path_raw.resolve()
    try:
        brief_bytes = brief_path.read_bytes()
    except OSError as exc:
        die(f"brief 읽기 실패: {exc}", 6)

    # ── backends.json 로드 ──
    try:
        with backends_path.open("r", encoding="utf-8") as f:
            backends = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        die(f"backends.json 파싱 실패: {exc}", 5)

    workers = backends.get("workers") or {}
    if role not in workers:
        die(f"role 미정의: {role}", 2)
    primary = workers[role]

    # ── primary 시도 ──
    prc, primary_env = run_backend(primary, brief_path, brief_bytes, root)
    if prc == 0:
        primary_env["fallback_used"] = False
        emit_envelope(primary_env)
        return 0

    # ── fallbacks 순차 시도. 하나라도 성공하면 즉시 반환. 전부 실패하면 마지막 시도의 코드 사용(bash 1-붕괴 개선). ──
    last_env: Dict[str, Any] = primary_env
    last_rc: int = prc
    for fb in primary.get("fallbacks", []) or []:
        frc, fb_env = run_backend(fb, brief_path, brief_bytes, root)
        last_env, last_rc = fb_env, frc
        if frc == 0:
            fb_env["fallback_used"] = True
            emit_envelope(fb_env)
            return 0

    last_env["fallback_used"] = True
    emit_envelope(last_env)
    return last_rc


if __name__ == "__main__":
    sys.exit(main())

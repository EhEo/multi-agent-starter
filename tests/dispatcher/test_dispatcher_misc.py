#!/usr/bin/env python3
"""디스패처 Python 전용 동작 — NEW (bash에 없었거나 Python 포팅으로 새로 생긴 경로).

순수 함수 단위 테스트(서브프로세스 비경유). conhost 래핑 등 복잡한 통합 경로 대신,
그 경로가 사용하는 순수 함수(strip_ansi / redact_stderr / _build_api_cmd /
_build_cli_cmd)를 직접 단언한다 — 더 빠르고 결정적이며 실제 로직을 검사한다.

커버:
1. ANSI 이스케이프 제거 (conhost 경로가 사용하는 _strip_ansi)
2. stderr redaction (32자+ 토큰 → [REDACTED], 짧은 토큰은 유지)
3. api call_type 확장자 감지 (.sh → bash, .py → python3)
4. CLI 명령 조립 (@brief_content 토큰 치환)
5. codex git 정책 주입 (MULTIAGENT_CODEX_SKIP_GIT=1 시 exec 뒤 --skip-git-repo-check)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# 디스패처 모듈 임포트 — <repo>/_shared/adapters/call_worker.py
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_shared" / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import call_worker  # noqa: E402
import _lib  # noqa: E402


def test_strip_ansi() -> None:
    """_strip_ansi: CSI 이스케이프(ESC[...letter) 제거."""
    raw = "\x1b[31mhello\x1b[0m \x1b[1mbold\x1b[0m"
    got = call_worker._strip_ansi(raw)
    _lib.assert_eq("strip_ansi removes CSI escapes", "hello bold", got)


def test_redact_stderr() -> None:
    """_redact_stderr: 32자+ 토큰 → [REDACTED], 짧은 토큰(< 32)은 유지."""
    token = "a" * 40      # 40자 → 마스킹 대상
    short = "b" * 10      # 10자 → 유지
    got = call_worker._redact_stderr(f"token={token} short={short}")
    _lib.assert_contains("redact 32+ 토큰", "[REDACTED]", got)
    _lib.assert_contains("짧은 토큰 유지", short, got)


def test_build_api_cmd_sh() -> None:
    """_build_api_cmd: .sh ref → bash 인터프리터."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "_shared" / "adapters").mkdir(parents=True)
        (root / "_shared" / "adapters" / "foo.sh").write_text(
            "#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
        spec = {"api": {"ref": "adapters/foo.sh"}}
        cmd, stdin = call_worker._build_api_cmd(
            spec, root / "brief.txt", b"content", "content", root)
        _lib.assert_eq(".sh → bash 인터프리터", "bash", cmd[0])
        _lib.assert_contains(".sh 스크립트 경로", "foo.sh", cmd[1])


def test_build_api_cmd_py() -> None:
    """_build_api_cmd: .py ref → python3 인터프리터 (gemini_api.sh 삭제 후 기본 템플릿이
    닿지 않는 경로지만 코드는 살아있어야 한다)."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "_shared" / "adapters").mkdir(parents=True)
        (root / "_shared" / "adapters" / "foo.py").write_text(
            "print('hi')\n", encoding="utf-8")
        spec = {"api": {"ref": "adapters/foo.py"}}
        cmd, stdin = call_worker._build_api_cmd(
            spec, root / "brief.txt", b"content", "content", root)
        _lib.assert_eq(".py → python3 인터프리터", "python3", cmd[0])
        _lib.assert_contains(".py 스크립트 경로", "foo.py", cmd[1])


def test_build_cli_cmd_brief_content() -> None:
    """_build_cli_cmd: @brief_content 토큰 → brief 파일 내용으로 치환."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        brief = root / "brief.txt"
        brief.write_text("hello", encoding="utf-8")
        spec = {"cli": {"command": "agy",
                        "args_template": ["--print", "@brief_content"]}}
        cmd, stdin = call_worker._build_cli_cmd(spec, brief, b"hello", "content")
        _lib.assert_eq("CLI cmd @brief_content 치환",
                       ["agy", "--print", "hello"], cmd)


def test_build_cli_cmd_codex_skip_git() -> None:
    """_build_cli_cmd: codex + MULTIAGENT_CODEX_SKIP_GIT=1 → exec 뒤
    --skip-git-repo-check 주입."""
    old = os.environ.pop("MULTIAGENT_CODEX_SKIP_GIT", None)
    try:
        os.environ["MULTIAGENT_CODEX_SKIP_GIT"] = "1"
        spec = {"cli": {"command": "codex",
                        "args_template": ["exec", "@brief_content"]}}
        cmd, stdin = call_worker._build_cli_cmd(
            spec, Path("/tmp/brief.txt"), b"hello", "content")
        _lib.assert_eq("codex skip-git 주입",
                       ["codex", "exec", "--skip-git-repo-check", "hello"], cmd)
    finally:
        os.environ.pop("MULTIAGENT_CODEX_SKIP_GIT", None)
        if old is not None:
            os.environ["MULTIAGENT_CODEX_SKIP_GIT"] = old


def main() -> int:
    print("디스패처 Python 전용 동작 (순수 함수 단위)")
    test_strip_ansi()
    test_redact_stderr()
    test_build_api_cmd_sh()
    test_build_api_cmd_py()
    test_build_cli_cmd_brief_content()
    test_build_cli_cmd_codex_skip_git()
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

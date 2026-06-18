#!/usr/bin/env python3
"""test_pathing.py — bootstrap.lib.pathing POSIX rc-file marker block 검증.

핵심: 반드시 tempdir HOME 으로 교체해 실제 ~/.bashrc 를 건드리지 않는다.
검증:
- register_path_posix 가 rc 파일에 marker block 을 추가
- export PATH 라인에 repo_bin, extra_dirs 포함
- 두 번째 호출은 멱등(idempotent) — marker 중복 불가
- HOME / PATH env var 원상복구
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402

sys.path.insert(0, str(_lib.REPO))
from bootstrap.lib import pathing  # noqa: E402


def _count_markers(text: str) -> int:
    """marker begin delimiter 발생 횟수."""
    return text.count(pathing.MARKER_BEGIN)


def main() -> int:
    print("bootstrap.lib.pathing: POSIX rc-file marker + dedup (tempdir HOME)")

    orig_home = os.environ.get("HOME")
    orig_path = os.environ.get("PATH", "")
    tmpdir = Path(tempfile.mkdtemp(prefix="mabpath_"))

    try:
        os.environ["HOME"] = str(tmpdir)

        # 현재 셸 rc 추정 영향을 받지 않도록 SHELL 도 bash 로 고정
        # (.bashrc 가 "현재 셸 rc" 로 인식되어 강제 작성 대상이 되게)
        orig_shell = os.environ.get("SHELL")
        os.environ["SHELL"] = "/bin/bash"

        # 미리 .bashrc 를 비어있는 상태로 둔다 (존재만 하도록)
        bashrc = tmpdir / ".bashrc"
        bashrc.write_text("# existing user bashrc\n", encoding="utf-8")

        repo_bin = Path("/fake/repo/bin")
        extra_dir = Path("/fake/extra")

        # ── 첫 번째 호출 ──
        results = pathing.register_path_posix(repo_bin=repo_bin, extra_dirs=[extra_dir])
        _lib.assert_eq(
            "first call returns list",
            True,
            isinstance(results, list) and len(results) >= 1,
        )
        # 적어도 하나의 step result 는 OK 여야 한다 (작성 또는 skip 모두 OK)
        _lib.assert_eq(
            "first call result status is OK",
            "OK",
            results[0].status,
        )

        content_after_first = bashrc.read_text(encoding="utf-8")
        _lib.assert_eq(
            "marker block present in .bashrc after first call",
            True,
            pathing.MARKER_BEGIN in content_after_first
            and pathing.MARKER_END in content_after_first,
        )
        _lib.assert_eq(
            "exactly one marker block after first call",
            1,
            _count_markers(content_after_first),
        )
        # export PATH 라인에 repo_bin 과 extra_dir 포함
        _lib.assert_contains(
            "export PATH line contains repo_bin",
            str(repo_bin),
            content_after_first,
        )
        _lib.assert_contains(
            "export PATH line contains extra_dir",
            str(extra_dir),
            content_after_first,
        )
        # export 키워드 자체도 있어야
        _lib.assert_contains(
            "block has 'export PATH=' line",
            "export PATH=\"",
            content_after_first,
        )

        # ── 두 번째 호출 (dedup 검증) ──
        results2 = pathing.register_path_posix(repo_bin=repo_bin, extra_dirs=[extra_dir])
        content_after_second = bashrc.read_text(encoding="utf-8")
        _lib.assert_eq(
            "still exactly one marker block after second call",
            1,
            _count_markers(content_after_second),
        )
        # 두 번째 호출 결과에 "already present" 의미의 skip 메시지가 있어야
        _lib.assert_contains(
            "second call result detail mentions skip/already",
            "already",
            results2[0].detail,
        )

        # ── marker 상수 포맷 일관성 ──
        _lib.assert_eq(
            "MARKER_BEGIN literal",
            "# >>> multiagent-bootstrap >>>",
            pathing.MARKER_BEGIN,
        )
        _lib.assert_eq(
            "MARKER_END literal",
            "# <<< multiagent-bootstrap <<<",
            pathing.MARKER_END,
        )
    finally:
        # HOME / SHELL / PATH 원상복구
        if orig_home is not None:
            os.environ["HOME"] = orig_home
        elif "HOME" in os.environ:
            del os.environ["HOME"]
        if orig_shell is not None:
            os.environ["SHELL"] = orig_shell
        elif "SHELL" in os.environ:
            del os.environ["SHELL"]
        # PATH 는 register_path_posix 가 mutate 했으므로 원본으로 되돌린다
        os.environ["PATH"] = orig_path
        shutil.rmtree(tmpdir, ignore_errors=True)

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

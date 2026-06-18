#!/usr/bin/env python3
"""codex git 정책 (test_codex_git.sh 대체).

기본은 git 요구(안전망). 옵트아웃(MULTIAGENT_CODEX_SKIP_GIT=1) 시에만
exec 직후에 --skip-git-repo-check 주입.

- A: 옵트아웃 ON → exec 바로 뒤에 --skip-git-repo-check 주입, exit 0
- B: 기본(옵트아웃 OFF) → 플래그 없음. 단 shutil.which("git") 통과를 위해
  가짜 git을 PATH에 주입한다(bash 버전은 실 git 의존; Python 포팅은 fake git으로
  기계 독립성 확보).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402


def main() -> int:
    print("codex git 정책 (A기본 + B옵트아웃)")
    backends = """{"schema_version":"1","flavor":"antigravity","workers":{"c":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
  "timeout":10,"brief_mode":"path","cli":{"command":"codex","args_template":["exec","@brief_content"]}}}}"""
    root = _lib.new_root(backends)
    try:
        (root / "brief.txt").write_text("BRIEF-TEXT\n", encoding="utf-8")
        # 받은 인자를 그대로 출력하는 가짜 codex (조사 가능)
        _lib.fake_bin(root, "codex", 0, extra_lines=['echo "ARGS: $*"'])

        # A. 옵트아웃 ON → exec 바로 뒤에 --skip-git-repo-check 주입
        rc, out, err = _lib.dispatch(root, "c", root / "brief.txt",
                                     env_override={"MULTIAGENT_CODEX_SKIP_GIT": "1"})
        env = json.loads(out)
        so = env.get("stdout", "")
        _lib.assert_eq("옵트아웃 exit 0", 0, rc)
        _lib.assert_contains("exec 뒤 --skip-git-repo-check 주입",
                             "exec --skip-git-repo-check", so)

        # B. 기본(옵트아웃 OFF) → 플래그 없음.
        #    디스패처가 shutil.which("git")을 검사하므로 가짜 git을 PATH에 추가.
        _lib.fake_bin(root, "git", 0)
        rc2, out2, err2 = _lib.dispatch(root, "c", root / "brief.txt")
        env2 = json.loads(out2)
        so2 = env2.get("stdout", "")
        if "--skip-git-repo-check" in so2:
            print("  FAIL: 기본인데 플래그 주입됨")
            _lib.FAIL += 1
        else:
            print("  PASS: 기본은 플래그 없음")
            _lib.PASS += 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

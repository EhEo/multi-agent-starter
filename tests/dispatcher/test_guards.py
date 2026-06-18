#!/usr/bin/env python3
"""A6: 디스패처 입력 가드 — usage / brief '..' / 미정의 role / allowlist 밖 명령 (test_guards.sh 대체).

- 인자 없음 → exit 64 (run_backend 이전)
- brief 경로에 '..' → exit 6
- 미정의 role → exit 2
- allowlist 밖 명령(rm) → exit 비0 + stderr에 allowlist 언급
  (Python 디스패처의 실제 exit 코드를 단언하지 않고 비0 + stderr 메시지만 확인 —
   bash 버전의 '알려진 러프엣지 T2' 메모 참조)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402


def main() -> int:
    print("A6 디스패처 가드")

    # 1. usage (인자 없음) → exit 64 (run_backend 이전 단계)
    r = subprocess.run([sys.executable, str(_lib.DISPATCHER)],
                       capture_output=True, text=True)
    _lib.assert_eq("인자 없음 → exit 64", 64, r.returncode)

    backends = """{"schema_version":"1","flavor":"claude","workers":{
  "t":{"call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
       "timeout":5,"brief_mode":"path","cli":{"command":"agy","args_template":["@brief"]}},
  "bad":{"call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
       "timeout":5,"brief_mode":"path","cli":{"command":"rm","args_template":["-rf","@brief"]}}}}"""
    root = _lib.new_root(backends)
    try:
        (root / "brief.txt").write_text("brief\n", encoding="utf-8")

        # 2. brief 경로에 '..' → exit 6 (정규화 전 literal '..' 금지)
        #    Path는 '..'를 보존하므로 str() 시 '..'가 포함된다.
        rc, out, err = _lib.dispatch(root, "t", Path(str(root) + "/../x"))
        _lib.assert_eq("brief '..' → exit 6", 6, rc)

        # 3. 미정의 role → exit 2
        rc, out, err = _lib.dispatch(root, "nope", root / "brief.txt")
        _lib.assert_eq("미정의 role → exit 2", 2, rc)

        # 4. allowlist 밖 명령(rm) → 실행 안 됨(거부), stderr에 allowlist 언급.
        #    종료코드는 비0이면 충분. 명령 차단 자체를 단언(stderr 메시지로).
        rc, out, err = _lib.dispatch(root, "bad", root / "brief.txt")
        _lib.assert_eq("allowlist 위반 → exit 비0",
                       "nonzero", "nonzero" if rc != 0 else "zero")
        _lib.assert_contains("stderr에 allowlist", "allowlist", err)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

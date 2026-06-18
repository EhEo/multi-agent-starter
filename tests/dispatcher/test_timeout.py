#!/usr/bin/env python3
"""S6: 워커가 timeout 초과 → envelope status=timeout, exit_code=124 (test_timeout.sh 대체).

bash 버전과 동일한 의도 — 가짜 agy가 3초 sleep, backends timeout=1이므로 1초에 124로 종료.
테스트 프로세스 자체는 멈추지 않는다 — 디스패처가 1초 타임아웃을 강제하고 sleep 3 서브프로세스를
프로세스 그룹 단위로 종료한다.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402


def main() -> int:
    print("S6 디스패처 timeout (초과 → 124)")
    backends = """{"schema_version":"1","flavor":"claude","workers":{"t":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
  "timeout":1,"brief_mode":"path","cli":{"command":"agy","args_template":["--print","@brief"]}}}}"""
    root = _lib.new_root(backends)
    try:
        (root / "brief.txt").write_text("brief\n", encoding="utf-8")
        _lib.fake_bin(root, "agy", 0, sleep_secs=3)  # 3초 sleep > timeout 1초

        rc, out, err = _lib.dispatch(root, "t", root / "brief.txt")
        env = json.loads(out)
        _lib.assert_eq("status=timeout", "timeout", env.get("status"))
        _lib.assert_eq("exit_code=124", 124, env.get("exit_code"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""S5: primary 백엔드 실패 → fallback 성공 (test_fallback.sh 대체).

bash 버전과 동일한 의도 — primary agy가 exit 1로 실패하면 fallback claude(exit 0)로
전환, 전체 exit 0 + envelope.fallback_used=true + model=fb + status=ok.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402


def main() -> int:
    print("S5 디스패처 폴백 (primary 실패 → fallback 성공)")
    backends = """{"schema_version":"1","flavor":"claude","workers":{"t":{
  "call_type":"cli","model":"primary","approval_class":"worker","result_capture":"stdout",
  "timeout":10,"brief_mode":"path","cli":{"command":"agy","args_template":["--print","@brief"]},
  "fallbacks":[{"call_type":"cli","model":"fb","approval_class":"worker","result_capture":"stdout",
    "timeout":10,"brief_mode":"path","cli":{"command":"claude","args_template":["-p","@brief"]}}]}}}"""
    root = _lib.new_root(backends)
    try:
        (root / "brief.txt").write_text("brief\n", encoding="utf-8")
        _lib.fake_bin(root, "agy", 1)       # primary 실패
        _lib.fake_bin(root, "claude", 0)    # fallback 성공

        rc, out, err = _lib.dispatch(root, "t", root / "brief.txt")
        env = json.loads(out)
        _lib.assert_eq("전체 exit 0", 0, rc)
        _lib.assert_eq("fallback_used=true", True, env.get("fallback_used"))
        _lib.assert_eq("fallback 모델=fb", "fb", env.get("model"))
        _lib.assert_eq("fallback status=ok", "ok", env.get("status"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

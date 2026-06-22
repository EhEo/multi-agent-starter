#!/usr/bin/env python3
"""L1/A2: 각 flavor를 임시폴더에 생성 → validate가 전부 PASS인지.

외부 호출 없음, 결정적. validate 체크 *개수*는 하드코딩하지 않는다
(F4 등으로 체크가 늘어도 안 깨지도록 — "전부 PASS"와 exit 0만 단언).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "plugins" / "multi-agent-starter" / "skills" / "configure-multiagent" / "generator"
FLAVORS = sorted(p.name for p in (GEN / "templates").iterdir() if p.is_dir())


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def main() -> None:
    fails = 0
    for f in FLAVORS:
        with tempfile.TemporaryDirectory() as d:
            tgt = Path(d) / f"sys-{f}"
            r = run([sys.executable, str(GEN / "init.py"),
                     "--flavor", f, "--target", str(tgt), "--yes", "--no-validate"])
            if r.returncode != 0:
                print(f"  FAIL [{f}] init exit {r.returncode}\n{r.stderr}")
                fails += 1
                continue
            v = run([sys.executable, str(GEN / "validate.py"),
                     "--flavor", f, "--target", str(tgt)])
            ok = v.returncode == 0 and "전부 PASS" in v.stdout
            print(f"  {'PASS' if ok else 'FAIL'} [{f}] validate exit {v.returncode}")
            if not ok:
                print(v.stdout)
                fails += 1
            if f == "claude":
                backends = tgt / "_shared" / "backends.json"
                data = json.loads(backends.read_text(encoding="utf-8"))
                critic_args = data["workers"]["codex-critic"]["mcp"]["args_template"]
                cwd_ok = critic_args.get("cwd") == "@target_repo"
                print(f"  {'PASS' if cwd_ok else 'FAIL'} [claude] codex-critic cwd contract")
                fails += not cwd_ok

                critic_args.pop("cwd", None)
                backends.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                missing_cwd = run([
                    sys.executable, str(GEN / "validate.py"),
                    "--flavor", f, "--target", str(tgt),
                ])
                rejects_missing = missing_cwd.returncode != 0 and "C10 codex-critic MCP cwd=@target_repo" in missing_cwd.stdout
                print(f"  {'PASS' if rejects_missing else 'FAIL'} [claude] missing critic cwd rejected")
                fails += not rejects_missing
    print(f"test_generate: {'all pass' if not fails else f'{fails} fail'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""test_repo.py — bootstrap.lib.repo 단위 테스트.

검증:
- find_repo_root() 가 실제 multi-agent-starter repo 루트를 가리킨다
- 반환된 Path 아래에 bootstrap/install.py, pyproject.toml, bin/multiagent 가 존재
- generator_path() / bin_multiagent_path() helper 가 repo_root 기준 절대경로 반환
- run_generator() / run_install_mat() / run_pip_install_editable() 호출 가능한지 signature 만 확인
  (실제 호출은 filesystem mutate 이므로 금지)
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib  # noqa: E402

sys.path.insert(0, str(_lib.REPO))
from bootstrap.lib import repo as repo_mod  # noqa: E402


def main() -> int:
    print("bootstrap.lib.repo: find_repo_root + helper signature 검증")

    repo_root = repo_mod.find_repo_root()

    # 반환값이 Path 인스턴스
    _lib.assert_eq("find_repo_root returns Path", True, isinstance(repo_root, Path))

    # 실제 REPO 와 동일 (절대경로 비교)
    _lib.assert_eq(
        "find_repo_root == tests/bootstrap/_lib.REPO",
        _lib.REPO.resolve(),
        repo_root.resolve(),
    )

    # repo_root 아래 핵심 마커 파일 존재
    _lib.assert_eq(
        "pyproject.toml exists under repo_root",
        True,
        (repo_root / "pyproject.toml").is_file(),
    )
    _lib.assert_eq(
        "bootstrap/install.py exists under repo_root",
        True,
        (repo_root / "bootstrap" / "install.py").is_file(),
    )
    _lib.assert_eq(
        "bin/multiagent exists under repo_root",
        True,
        (repo_root / "bin" / "multiagent").exists(),
    )

    # generator_path helper
    gen = repo_mod.generator_path(repo_root)
    _lib.assert_eq(
        "generator_path returns Path",
        True,
        isinstance(gen, Path),
    )
    _lib.assert_eq(
        "generator_path ends with generator/init.py",
        True,
        gen.parts[-2:] == ("generator", "init.py"),
    )
    _lib.assert_eq(
        "generator file actually exists",
        True,
        gen.is_file(),
    )

    # bin_multiagent_path helper
    bin_ma = repo_mod.bin_multiagent_path(repo_root)
    _lib.assert_eq(
        "bin_multiagent_path == repo_root/bin/multiagent",
        repo_root / "bin" / "multiagent",
        bin_ma,
    )

    # ── callable helpers signature 만 검증 (실제 호출 금지) ──
    for fname in ("run_generator", "run_install_mat", "run_pip_install_editable"):
        fn = getattr(repo_mod, fname, None)
        _lib.assert_eq(f"{fname} is callable", True, callable(fn))
        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())
        # run_generator 만 인자 구조를 더 엄격히 검증
        if fname == "run_generator":
            _lib.assert_eq(
                "run_generator has repo_root param",
                True,
                "repo_root" in param_names,
            )
            _lib.assert_eq(
                "run_generator has flavor param",
                True,
                "flavor" in param_names,
            )
            _lib.assert_eq(
                "run_generator has target param",
                True,
                "target" in param_names,
            )

    # REPO_MARKERS 상수에 pyproject.toml 이 있어야 (find_repo_root 검증에 쓰임)
    _lib.assert_contains(
        "REPO_MARKERS contains pyproject.toml",
        "pyproject.toml",
        ",".join(repo_mod.REPO_MARKERS),
    )

    return _lib.finish()


if __name__ == "__main__":
    sys.exit(main())

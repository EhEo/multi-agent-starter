#!/usr/bin/env python3
"""repo.py — 저장소 루트 감지 + generator 호출.

find_repo_root():
    bootstrap/install.py 의 __file__ 기준으로 repo root 추정.
    (bootstrap/install.py 의 parent.parent = repo root)
    호출측에서 이 모듈을 임포트하면 이 파일의 절대 위치가 곧 repo 구조를 드러낸다.

run_generator():
    <repo>/plugins/multi-agent-starter/skills/configure-multiagent/generator/init.py
    를 현재 python 으로 subprocess 호출. 결과를 스트리밍.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from bootstrap.lib.packages import StepResult


# Generator 상대 경로 (repo root 기준)
GENERATOR_REL = Path("plugins/multi-agent-starter/skills/configure-multiagent/generator/init.py")

# Repo 식별용 마커 파일들 (존재하면 repo root 로 인정)
REPO_MARKERS = (
    "pyproject.toml",
    "bin/multiagent",
    "mat_linux.py",
    GENERATOR_REL.as_posix(),
)


def find_repo_root() -> Path:
    """이 모듈(bootstrap/lib/repo.py) 위치에서 repo root 추정.

    bootstrap/lib/repo.py → parent×3 = repo root.
    마커 파일(pyproject.toml 등)로 검증. 검증 실패 시에도 추정값을 반환
    (호출측에서 추가 검사/메시지 처리).
    """
    here = Path(__file__).resolve().parent  # bootstrap/lib/
    candidate = here.parent.parent          # repo root
    if (candidate / "pyproject.toml").exists() or (candidate / "bin").is_dir():
        return candidate
    # 마커가 없으면 한 단계 더 위도 검사 (symbolic link 등 예외 대비)
    for parent in [candidate, candidate.parent]:
        for marker in REPO_MARKERS:
            if (parent / marker).exists():
                return parent
    return candidate


def generator_path(repo_root: Path) -> Path:
    """repo_root 기준 generator/init.py 절대 경로."""
    return repo_root / GENERATOR_REL


def bin_multiagent_path(repo_root: Path) -> Path:
    """repo_root 기준 bin/multiagent 절대 경로."""
    return repo_root / "bin" / "multiagent"


def run_generator(
    repo_root: Path,
    flavor: str,
    target: Path,
    yes: bool = True,
) -> StepResult:
    """generator/init.py 를 subprocess 로 실행.

    stdout/stderr 를 그대로 상속(stream) 하여 사용자가 진행 상황을 볼 수 있게 한다.
    exit 0 → OK. 비0 → FAIL (stderr 마지막 줄 포함).
    """
    gen = generator_path(repo_root)
    if not gen.is_file():
        return StepResult("FAIL", f"generator not found: {gen}")
    cmd = [sys.executable, str(gen), "--flavor", flavor, "--target", str(target)]
    if yes:
        cmd.append("--yes")
    try:
        proc = subprocess.run(cmd)
    except FileNotFoundError as exc:
        return StepResult("FAIL", f"python executable not found: {exc}")
    if proc.returncode == 0:
        return StepResult("OK", f"generator ran for flavor={flavor} target={target}")
    return StepResult("FAIL", f"generator exited {proc.returncode} for flavor={flavor}")


def run_install_mat(repo_root: Path) -> StepResult:
    """bin/multiagent --install-mat 를 호출해 mat 설치 시도.

    bash 런처를 그대로 불러 mat 설치 로직을 재사용한다(중복 구현 금지).
    bash 가 없거나 bin/multiagent 가 없으면 FAIL 반환 — 호출측은 pip install -e . 폴백.
    """
    launcher = bin_multiagent_path(repo_root)
    if not launcher.is_file():
        return StepResult("FAIL", f"bin/multiagent not found: {launcher}")
    bash = _which("bash")
    if bash is None:
        return StepResult("FAIL", "bash not on PATH (cannot invoke bin/multiagent)")
    try:
        proc = subprocess.run([bash, str(launcher), "--install-mat"])
    except FileNotFoundError as exc:
        return StepResult("FAIL", f"bash invocation failed: {exc}")
    if proc.returncode == 0:
        return StepResult("OK", "mat installed via bin/multiagent --install-mat")
    return StepResult("FAIL", f"bin/multiagent --install-mat exited {proc.returncode}")


def run_pip_install_editable(repo_root: Path) -> StepResult:
    """pip install -e <repo> 폴백 (mat Python 버전 등록).

    pyproject.toml 의 [project.scripts] mat = "mat_linux:main" 사용.
    """
    if not (repo_root / "pyproject.toml").is_file():
        return StepResult("FAIL", f"pyproject.toml not found at {repo_root}")
    cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_root)]
    try:
        proc = subprocess.run(cmd)
    except FileNotFoundError as exc:
        return StepResult("FAIL", f"pip invocation failed: {exc}")
    if proc.returncode == 0:
        return StepResult("OK", "mat registered via pip install -e <repo>")
    return StepResult("FAIL", f"pip install -e exited {proc.returncode}")


def _which(name: str) -> Optional[str]:
    """shutil.which 래퍼 — Optional 경로 반환."""
    from shutil import which
    return which(name)

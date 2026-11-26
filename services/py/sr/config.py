"""Loads versioned parameters from config/*.yaml (never hard-code decision-table values)."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    env = os.environ.get("SR_REPO_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "config" / "decisions.yaml").exists():
            return p
    raise FileNotFoundError("cannot locate repo root (config/decisions.yaml); set SR_REPO_ROOT")


def config_dir() -> Path:
    return repo_root() / "config"


@cache
def load(name: str) -> dict[str, Any]:
    """Load config/<name>.yaml (name may include a subdirectory, e.g. 'features/fs-0.2')."""
    path = config_dir() / f"{name}.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data

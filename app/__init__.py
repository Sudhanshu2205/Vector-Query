"""Application package bootstrap."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _candidate_site_packages() -> list[Path]:
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / ".venv" / "Lib" / "site-packages",
        project_root / ".conda-rag-env" / "Lib" / "site-packages",
        Path.home() / "anaconda3" / "envs" / "rag_env" / "Lib" / "site-packages",
        Path.home() / "miniconda3" / "envs" / "rag_env" / "Lib" / "site-packages",
    ]

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate).lower()
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(candidate)

    return unique_candidates


def _bootstrap_runtime_dependencies() -> None:
    required_modules = (
        "fastapi",
        "starlette",
        "slowapi",
        "multipart",
        "pypdf",
    )

    if all(_module_exists(module_name) for module_name in required_modules):
        return

    for candidate in _candidate_site_packages():
        if not candidate.exists():
            continue

        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.append(candidate_str)

        if all(_module_exists(module_name) for module_name in required_modules):
            return


_bootstrap_runtime_dependencies()

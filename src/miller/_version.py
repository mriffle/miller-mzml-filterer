"""Version resolution helpers for CLI and package metadata."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
import subprocess

DIST_NAME = "miller-mzml-filterer"
UNAVAILABLE_VERSION = "not available"


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the best available version string for this checkout/install."""
    installed_version = _get_installed_version()
    if installed_version is not None:
        return installed_version

    tagged_version = _get_exact_tag()
    if tagged_version is not None:
        return _normalize_tag(tagged_version)

    git_hash = _get_git_hash()
    if git_hash is not None:
        return f"git-{git_hash}"

    return UNAVAILABLE_VERSION


def _get_installed_version() -> str | None:
    try:
        return distribution_version(DIST_NAME)
    except PackageNotFoundError:
        return None


def _get_exact_tag() -> str | None:
    return _git_output(["describe", "--tags", "--exact-match"])


def _get_git_hash() -> str | None:
    return _git_output(["rev-parse", "--short", "HEAD"])


def _git_output(args: list[str]) -> str | None:
    repo_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            check=False,
            cwd=repo_root,
            text=True,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    output = result.stdout.strip()
    return output or None


def _normalize_tag(tag: str) -> str:
    if tag.startswith("v") and len(tag) > 1:
        return tag[1:]
    return tag

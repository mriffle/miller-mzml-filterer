from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def indexed_fixture(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_indexed.mzML"


@pytest.fixture(scope="session")
def nonindexed_fixture(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_nonindexed.mzML"

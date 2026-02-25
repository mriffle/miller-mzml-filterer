from __future__ import annotations

import pytest

from miller.errors import InputFileError
from miller.reader import MzMLSource


def test_reads_indexed(indexed_fixture) -> None:
    source = MzMLSource(indexed_fixture)
    assert source.is_indexed is True
    assert [s.scan_id for s in source.scan_infos[:6]] == [
        "scan=1001",
        "scan=1002",
        "scan=1003",
        "scan=1004",
        "scan=1005",
        "scan=1006",
    ]
    assert len(source.scan_infos) == 20


def test_reads_nonindexed(nonindexed_fixture) -> None:
    source = MzMLSource(nonindexed_fixture)
    assert source.is_indexed is False
    assert source.scan_infos[1].ms_level == 2
    assert source.scan_infos[1].precursor_ref == "scan=1001"
    assert source.scan_infos[2].precursor_ref is None


def test_invalid_file(tmp_path) -> None:
    bad = tmp_path / "bad.mzML"
    bad.write_text("not xml", encoding="utf-8")
    with pytest.raises(InputFileError):
        MzMLSource(bad)

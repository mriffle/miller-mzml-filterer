from __future__ import annotations

import numpy as np

from miller.codec import NS, decode_binary_data_array, is_zlib_array
from miller.reader import MzMLSource
from miller.writer import write_subset


def test_write_nonindexed_and_count(nonindexed_fixture, tmp_path) -> None:
    source = MzMLSource(nonindexed_fixture)
    out = tmp_path / "subset.mzML"
    write_subset(source, ["scan=1002", "scan=1003"], out, indexed=False, compression="source")

    subset = MzMLSource(out)
    assert subset.is_indexed is False
    assert len(subset.scan_infos) == 2


def test_write_indexed(indexed_fixture, tmp_path) -> None:
    source = MzMLSource(indexed_fixture)
    out = tmp_path / "subset_indexed.mzML"
    write_subset(source, ["scan=1001", "scan=1002"], out, indexed=True, compression="source")

    blob = out.read_text(encoding="utf-8")
    assert "<indexedmzML" in blob
    assert "<indexList" in blob


def test_compression_zlib(nonindexed_fixture, tmp_path) -> None:
    source = MzMLSource(nonindexed_fixture)
    out = tmp_path / "subset_zlib.mzML"
    write_subset(source, ["scan=1001"], out, indexed=False, compression="zlib")

    subset = MzMLSource(out)
    spec = subset.spectrum_by_id["scan=1001"]
    bdas = spec.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)
    assert all(is_zlib_array(bda) for bda in bdas)


def test_compression_none_data_roundtrip(nonindexed_fixture, tmp_path) -> None:
    source = MzMLSource(nonindexed_fixture)
    src_spec = source.spectrum_by_id["scan=1002"]
    src_intensity = decode_binary_data_array(src_spec.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)[1])

    out = tmp_path / "subset_none.mzML"
    write_subset(source, ["scan=1002"], out, indexed=False, compression="none")

    subset = MzMLSource(out)
    out_spec = subset.spectrum_by_id["scan=1002"]
    out_intensity = decode_binary_data_array(out_spec.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)[1])
    assert np.array_equal(src_intensity, out_intensity)

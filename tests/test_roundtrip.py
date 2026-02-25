from __future__ import annotations

import numpy as np

from miller.codec import NS, decode_binary_data_array
from miller.reader import MzMLSource
from miller.writer import write_subset


def _arrays(spec):
    bdas = spec.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)
    return decode_binary_data_array(bdas[0]), decode_binary_data_array(bdas[1])


def test_roundtrip_source_fidelity(nonindexed_fixture, tmp_path) -> None:
    source = MzMLSource(nonindexed_fixture)
    selected = ["scan=1001", "scan=1006"]

    out = tmp_path / "subset.mzML"
    write_subset(source, selected, out, indexed=False, compression="source")
    subset = MzMLSource(out)

    for sid in selected:
        src_mz, src_i = _arrays(source.spectrum_by_id[sid])
        out_mz, out_i = _arrays(subset.spectrum_by_id[sid])
        assert np.array_equal(src_mz, out_mz)
        assert np.array_equal(src_i, out_i)


def test_roundtrip_recalc_tic(nonindexed_fixture, tmp_path) -> None:
    source = MzMLSource(nonindexed_fixture)
    selected = ["scan=1002", "scan=1003"]

    out = tmp_path / "subset.mzML"
    write_subset(source, selected, out, indexed=False, compression="none")
    subset = MzMLSource(out)

    chrom_list = subset.run.find("mz:chromatogramList", NS)
    assert chrom_list is not None
    tic = chrom_list.find("mz:chromatogram[@id='TIC']", NS)
    assert tic is not None
    vals = decode_binary_data_array(tic.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)[1])
    assert np.array_equal(vals, np.array([40.0, 35.0]))


def test_roundtrip_source_binary_base64_identical(nonindexed_fixture, tmp_path) -> None:
    source = MzMLSource(nonindexed_fixture)
    out = tmp_path / "subset_source.mzML"
    write_subset(source, ["scan=1002"], out, indexed=False, compression="source")
    subset = MzMLSource(out)

    source_bdas = source.spectrum_by_id["scan=1002"].findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)
    output_bdas = subset.spectrum_by_id["scan=1002"].findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)
    for source_bda, output_bda in zip(source_bdas, output_bdas, strict=True):
        source_binary = source_bda.find("mz:binary", NS)
        output_binary = output_bda.find("mz:binary", NS)
        assert source_binary is not None and output_binary is not None
        assert source_binary.text == output_binary.text

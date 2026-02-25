from __future__ import annotations

import numpy as np

from miller.chromatogram import recalculate_bpc, recalculate_tic
from miller.codec import NS, decode_binary_data_array
from miller.reader import MzMLSource


def test_tic_bpc_recalculation(nonindexed_fixture) -> None:
    source = MzMLSource(nonindexed_fixture)
    spectra = [source.spectrum_by_id["scan=1002"], source.spectrum_by_id["scan=1003"]]
    times_tic, intens_tic = recalculate_tic(spectra)
    times_bpc, intens_bpc = recalculate_bpc(spectra)

    assert np.array_equal(times_tic, np.array([2.0, 3.0]))
    assert np.array_equal(times_bpc, np.array([2.0, 3.0]))
    assert np.array_equal(intens_tic, np.array([40.0, 35.0]))
    assert np.array_equal(intens_bpc, np.array([25.0, 30.0]))


def test_fixture_tic_matches_declared(nonindexed_fixture) -> None:
    source = MzMLSource(nonindexed_fixture)
    run = source.run
    chrom_list = run.find("mz:chromatogramList", NS)
    assert chrom_list is not None
    tic = chrom_list.find("mz:chromatogram[@id='TIC']", NS)
    assert tic is not None
    intensity_bda = tic.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)[1]
    values = decode_binary_data_array(intensity_bda)
    assert np.array_equal(
        values,
        np.array(
            [
                30.0,
                40.0,
                35.0,
                33.0,
                39.0,
                21.0,
                30.0,
                30.0,
                22.0,
                15.0,
                14.0,
                15.0,
                8.0,
                22.0,
                15.0,
                20.0,
                22.0,
                22.0,
                20.0,
                25.0,
            ]
        ),
    )

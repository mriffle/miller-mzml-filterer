from __future__ import annotations

import numpy as np
from lxml import etree

from miller.chromatogram import recalculate_bpc, recalculate_tic
from miller.codec import NS


MZ_NS = "http://psi.hupo.org/ms/mzml"


def _spectrum_no_scan() -> etree._Element:
    return etree.Element(f"{{{MZ_NS}}}spectrum")


def _spectrum_with_bad_time_and_no_intensity() -> etree._Element:
    spectrum = etree.Element(f"{{{MZ_NS}}}spectrum")
    scan_list = etree.SubElement(spectrum, f"{{{MZ_NS}}}scanList")
    scan = etree.SubElement(scan_list, f"{{{MZ_NS}}}scan")
    cv = etree.SubElement(scan, f"{{{MZ_NS}}}cvParam")
    cv.set("accession", "MS:1000016")
    cv.set("value", "not-a-number")
    bdal = etree.SubElement(spectrum, f"{{{MZ_NS}}}binaryDataArrayList")
    bdal.set("count", "0")
    return spectrum


def test_recalculate_handles_missing_scan_and_intensity() -> None:
    no_scan = _spectrum_no_scan()
    bad_scan = _spectrum_with_bad_time_and_no_intensity()

    times_tic, intens_tic = recalculate_tic([no_scan, bad_scan])
    times_bpc, intens_bpc = recalculate_bpc([no_scan, bad_scan])

    assert np.array_equal(times_tic, np.array([0.0, 0.0]))
    assert np.array_equal(times_bpc, np.array([0.0, 0.0]))
    assert np.array_equal(intens_tic, np.array([0.0, 0.0]))
    assert np.array_equal(intens_bpc, np.array([0.0, 0.0]))


def test_recalculate_retention_time_missing_value() -> None:
    spectrum = etree.Element(f"{{{MZ_NS}}}spectrum")
    scan_list = etree.SubElement(spectrum, f"{{{MZ_NS}}}scanList")
    scan = etree.SubElement(scan_list, f"{{{MZ_NS}}}scan")
    cv = etree.SubElement(scan, f"{{{MZ_NS}}}cvParam")
    cv.set("accession", "MS:1000016")

    times, intensities = recalculate_tic([spectrum])
    assert np.array_equal(times, np.array([0.0]))
    assert np.array_equal(intensities, np.array([0.0]))


def test_no_namespace_lookup_failure_guard(nonindexed_fixture) -> None:
    # Ensure namespace map works in edge tests too.
    tree = etree.parse(str(nonindexed_fixture))
    assert tree.getroot().find("mz:run", NS) is not None

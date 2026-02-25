from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from miller.errors import InputFileError
from miller.reader import (
    _extract_ms_level,
    _extract_ms_level_pyteomics,
    _extract_precursor_ref,
    _extract_precursor_ref_pyteomics,
    _local_name,
    MzMLSource,
)


MZ_NS = "http://psi.hupo.org/ms/mzml"


def test_local_name_plain_and_namespaced() -> None:
    assert _local_name("plain") == "plain"
    assert _local_name(f"{{{MZ_NS}}}mzML") == "mzML"


def test_extract_ms_level_edge_cases() -> None:
    spectrum = etree.Element(f"{{{MZ_NS}}}spectrum")
    cv = etree.SubElement(spectrum, f"{{{MZ_NS}}}cvParam")
    cv.set("accession", "MS:1000511")
    cv.set("value", "not-an-int")
    assert _extract_ms_level(spectrum) is None

    cv.attrib.pop("value")
    assert _extract_ms_level(spectrum) is None


def test_extract_precursor_ref_edge_cases() -> None:
    spectrum = etree.Element(f"{{{MZ_NS}}}spectrum")
    assert _extract_precursor_ref(spectrum) is None


def test_pyteomics_extract_helpers() -> None:
    assert _extract_ms_level_pyteomics({"ms level": "2"}) == 2
    assert _extract_ms_level_pyteomics({"ms level": "bad"}) is None
    assert _extract_precursor_ref_pyteomics({"precursorList": {"precursor": [{"spectrumRef": "scan=1"}]}}) == "scan=1"
    assert _extract_precursor_ref_pyteomics({"precursorList": {"precursor": [{}]}}) is None


def test_reader_invalid_root(tmp_path: Path) -> None:
    bad = tmp_path / "badroot.mzML"
    bad.write_text("<root></root>", encoding="utf-8")
    with pytest.raises(InputFileError, match="Root element"):
        MzMLSource(bad)


def test_reader_indexed_fallback_find_descendant(tmp_path: Path) -> None:
    path = tmp_path / "indexed_nested.mzML"
    path.write_text(
        """
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<indexedmzML xmlns=\"http://psi.hupo.org/ms/mzml\">
  <wrapper>
    <mzML>
      <run>
        <spectrumList count=\"0\" />
      </run>
    </mzML>
  </wrapper>
</indexedmzML>
""".strip(),
        encoding="utf-8",
    )
    source = MzMLSource(path)
    assert source.is_indexed is True
    assert source.scan_infos == []


def test_reader_indexed_missing_mzml_child(tmp_path: Path) -> None:
    path = tmp_path / "indexed_missing.mzML"
    path.write_text(
        """
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<indexedmzML xmlns=\"http://psi.hupo.org/ms/mzml\">
</indexedmzML>
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(InputFileError, match="no mzML child"):
        MzMLSource(path)


def test_reader_pyteomics_empty_infos_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "noid.mzML"
    path.write_text(
        """
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<mzML xmlns=\"http://psi.hupo.org/ms/mzml\">
  <run>
    <spectrumList count=\"1\">
      <spectrum index=\"0\" defaultArrayLength=\"0\" />
    </spectrumList>
  </run>
</mzML>
""".strip(),
        encoding="utf-8",
    )
    source = MzMLSource(path)
    assert source.scan_infos == []

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from miller.codec import NS
from miller.errors import OutputWriteError
from miller.reader import MzMLSource
from miller.writer import _extract_ids_in_order, write_subset


def test_write_subset_missing_run_raises(nonindexed_fixture, tmp_path: Path) -> None:
    source = MzMLSource(nonindexed_fixture)
    run = source.mzml_root.find("mz:run", NS)
    assert run is not None
    source.mzml_root.remove(run)

    with pytest.raises(OutputWriteError, match="<run>"):
        write_subset(source, ["scan=1001"], tmp_path / "out.mzML", indexed=False, compression="source")


def test_write_subset_missing_spectrum_list_raises(nonindexed_fixture, tmp_path: Path) -> None:
    source = MzMLSource(nonindexed_fixture)
    run = source.mzml_root.find("mz:run", NS)
    assert run is not None
    spectrum_list = run.find("mz:spectrumList", NS)
    assert spectrum_list is not None
    run.remove(spectrum_list)

    with pytest.raises(OutputWriteError, match="<spectrumList>"):
        write_subset(source, ["scan=1001"], tmp_path / "out.mzML", indexed=False, compression="source")


def test_write_subset_write_error_wrapped(nonindexed_fixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = MzMLSource(nonindexed_fixture)
    out = tmp_path / "out.mzML"

    def _boom(self, data):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_bytes", _boom)
    with pytest.raises(OutputWriteError, match="Cannot write output file"):
        write_subset(source, ["scan=1001"], out, indexed=False, compression="source")


def test_index_list_count_omits_chromatogram_section_when_absent(tmp_path: Path) -> None:
    path = tmp_path / "nochrom.mzML"
    path.write_text(
        """
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<mzML xmlns=\"http://psi.hupo.org/ms/mzml\">
  <run>
    <spectrumList count=\"1\">
      <spectrum id=\"scan=1\" index=\"0\" defaultArrayLength=\"0\">
        <cvParam accession=\"MS:1000511\" value=\"1\"/>
        <binaryDataArrayList count=\"0\" />
      </spectrum>
    </spectrumList>
  </run>
</mzML>
""".strip(),
        encoding="utf-8",
    )
    source = MzMLSource(path)
    out = tmp_path / "out_indexed.mzML"
    write_subset(source, ["scan=1"], out, indexed=True, compression="source")

    text = out.read_text(encoding="utf-8")
    assert '<indexList count="1">' in text
    assert '<index name="chromatogram">' not in text


def test_extract_ids_in_order_break_paths() -> None:
    assert _extract_ids_in_order(b"<spectrum >", b"<spectrum ") == []
    assert _extract_ids_in_order(b"<spectrum id=\"abc", b"<spectrum ") == []


def test_write_subset_no_chromatogram_list_passthrough(tmp_path: Path) -> None:
    path = tmp_path / "nochrom.mzML"
    path.write_text(
        """
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<mzML xmlns=\"http://psi.hupo.org/ms/mzml\">
  <run>
    <spectrumList count=\"1\">
      <spectrum id=\"scan=1\" index=\"0\" defaultArrayLength=\"0\">
        <cvParam accession=\"MS:1000511\" value=\"1\"/>
        <binaryDataArrayList count=\"0\" />
      </spectrum>
    </spectrumList>
  </run>
</mzML>
""".strip(),
        encoding="utf-8",
    )
    source = MzMLSource(path)
    out = tmp_path / "out_nonindexed.mzML"
    write_subset(source, ["scan=1"], out, indexed=False, compression="source")

    root = etree.parse(str(out)).getroot()
    assert root.find("mz:run/mz:chromatogramList", NS) is None

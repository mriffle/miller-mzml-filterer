"""Regression tests for spectrum/chromatogram index renumbering in output.

Subset files must declare zero-based, consecutive ``index`` attributes so that
random-access mzML consumers (e.g. MSFTBX / umich.ms) can map a spectrum's
``index`` to its position in the (smaller) spectrum list. The committed
``test_data/test_data.mzML`` corpus is itself a subset whose spectra carry the
original, non-consecutive indices, which is exactly what makes it a useful
regression fixture here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from miller.cli import main
from miller.codec import NS
from miller.reader import MzMLSource
from miller.writer import write_subset

SMOKE_INPUT = Path("test_data/test_data.mzML")


def _spectrum_index_attrs(source: MzMLSource) -> list[int]:
    return [int(spec.get("index")) for spec in source.spectra]


def _chromatogram_index_attrs(source: MzMLSource) -> list[int]:
    chrom_list = source.run.find("mz:chromatogramList", NS)
    if chrom_list is None:
        return []
    return [
        int(value)
        for chrom in chrom_list.findall("mz:chromatogram", NS)
        if (value := chrom.get("index")) is not None
    ]


def _read_spectrum_offsets(path: Path) -> list[tuple[str, int]]:
    """Return (idRef, absolute byte offset) pairs from the spectrum <index>."""
    text = path.read_text(encoding="utf-8")
    start = text.index('<index name="spectrum">')
    end = text.index("</index>", start)
    section = text[start:end]
    return [
        (m.group(1), int(m.group(2)))
        for m in re.finditer(r'<offset idRef="([^"]+)">(\d+)</offset>', section)
    ]


def test_smoke_corpus_has_nonconsecutive_indices() -> None:
    # Guards the regression: if the corpus were ever cleaned, the tests below
    # would pass even with the bug present.
    source = MzMLSource(SMOKE_INPUT)
    indices = _spectrum_index_attrs(source)
    assert indices != list(range(len(indices)))


@pytest.mark.parametrize(
    ("extra_args", "expect_indexed"),
    [
        ([], True),  # follows the (indexed) source
        (["--no-index"], False),
        (["--indexed"], True),
    ],
)
def test_output_spectrum_indices_are_consecutive(
    extra_args: list[str], expect_indexed: bool, tmp_path: Path
) -> None:
    out = tmp_path / "subset.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-count",
            "6",
            "--seed",
            "3",
            "--no-include-precursors",
            *extra_args,
            str(SMOKE_INPUT),
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output

    output = MzMLSource(out)
    assert output.is_indexed is expect_indexed

    count = int(output.spectrum_list.get("count"))
    assert _spectrum_index_attrs(output) == list(range(count))
    assert len(output.spectra) == count

    chrom_indices = _chromatogram_index_attrs(output)
    assert chrom_indices == list(range(len(chrom_indices)))


def test_indexed_offsets_point_at_consecutively_indexed_spectra(tmp_path: Path) -> None:
    """Reproduce the random-access consumer path: each <indexList> offset must
    land on a <spectrum> whose index attribute equals its ordinal position."""
    out = tmp_path / "subset.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-count",
            "5",
            "--seed",
            "1",
            "--indexed",
            "--no-include-precursors",
            str(SMOKE_INPUT),
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output

    blob = out.read_bytes()
    offsets = _read_spectrum_offsets(out)
    assert offsets, "expected spectrum offsets in indexList"

    for ordinal, (id_ref, byte_off) in enumerate(offsets):
        start_tag = blob[byte_off:].split(b">", 1)[0].decode("utf-8")
        assert start_tag.startswith("<spectrum "), start_tag
        assert f'index="{ordinal}"' in start_tag
        assert f'id="{id_ref}"' in start_tag


def test_synthetic_subset_renumbers_indices_and_preserves_ids(
    nonindexed_fixture: Path, tmp_path: Path
) -> None:
    source = MzMLSource(nonindexed_fixture)
    # scan=1003 / scan=1007 have original indices 2 and 6 in the fixture.
    out = tmp_path / "subset.mzML"
    write_subset(source, ["scan=1003", "scan=1007"], out, indexed=False, compression="source")

    output = MzMLSource(out)
    assert _spectrum_index_attrs(output) == [0, 1]
    assert [spec.get("id") for spec in output.spectra] == ["scan=1003", "scan=1007"]

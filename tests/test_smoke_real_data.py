from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from click.testing import CliRunner

from miller.cli import main
from miller.codec import NS, decode_binary_data_array
from miller.reader import MzMLSource

CV_MZ_ARRAY = "MS:1000514"
CV_INTENSITY_ARRAY = "MS:1000515"


@dataclass(frozen=True)
class SourceStats:
    input_path: Path
    is_indexed: bool
    ordered_scan_ids: list[str]
    ms_level_by_id: dict[str, int | None]
    precursor_by_id: dict[str, str | None]
    ms1_ids: list[str]
    ms2_ids: list[str]
    ms2_with_parent_ids: list[str]


@pytest.fixture(scope="session")
def smoke_input_path() -> Path:
    path = Path("test_data/test_data.mzML")
    assert path.exists(), "Expected smoke input file at test_data/test_data.mzML"
    return path


@pytest.fixture(scope="session")
def smoke_stats(smoke_input_path: Path) -> SourceStats:
    source = MzMLSource(smoke_input_path)
    ordered_scan_ids = [scan.scan_id for scan in source.scan_infos]
    ms_level_by_id = {scan.scan_id: scan.ms_level for scan in source.scan_infos}
    precursor_by_id = {scan.scan_id: scan.precursor_ref for scan in source.scan_infos}

    ms1_ids = [scan.scan_id for scan in source.scan_infos if scan.ms_level == 1]
    ms2_ids = [scan.scan_id for scan in source.scan_infos if scan.ms_level == 2]
    ms2_with_parent_ids = [
        scan.scan_id
        for scan in source.scan_infos
        if scan.ms_level == 2
        and scan.precursor_ref is not None
        and scan.precursor_ref != scan.scan_id
        and scan.precursor_ref in ms_level_by_id
    ]

    # Keep these checks explicit because this file is our intended smoke-test corpus.
    assert len(ms1_ids) == 10, f"Expected 10 MS1 scans, found {len(ms1_ids)}"
    assert len(ms2_ids) == 10, f"Expected 10 MS2 scans, found {len(ms2_ids)}"
    assert len(ms2_with_parent_ids) > 0, "Expected MS2 scans with valid parent refs in smoke input"

    return SourceStats(
        input_path=smoke_input_path,
        is_indexed=source.is_indexed,
        ordered_scan_ids=ordered_scan_ids,
        ms_level_by_id=ms_level_by_id,
        precursor_by_id=precursor_by_id,
        ms1_ids=ms1_ids,
        ms2_ids=ms2_ids,
        ms2_with_parent_ids=ms2_with_parent_ids,
    )


def _spectrum_arrays(source: MzMLSource, scan_id: str) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    spectrum = source.spectrum_by_id[scan_id]
    mz_array: np.ndarray[Any, Any] | None = None
    intensity_array: np.ndarray[Any, Any] | None = None
    for bda in spectrum.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS):
        accessions = {cv.get("accession") for cv in bda.findall("mz:cvParam", NS)}
        if CV_MZ_ARRAY in accessions:
            mz_array = decode_binary_data_array(bda)
        elif CV_INTENSITY_ARRAY in accessions:
            intensity_array = decode_binary_data_array(bda)
    assert mz_array is not None
    assert intensity_array is not None
    return mz_array, intensity_array


def _resolve_precursors_locally(
    selected_ids: list[str],
    precursor_by_id: dict[str, str | None],
    source_order: list[str],
) -> list[str]:
    selected_set = set(selected_ids)
    for scan_id in list(selected_ids):
        current = scan_id
        seen: set[str] = set()
        while True:
            precursor = precursor_by_id.get(current)
            if precursor is None or precursor == current or precursor in seen:
                break
            seen.add(precursor)
            if precursor not in precursor_by_id:
                break
            if precursor in selected_set:
                current = precursor
                continue
            selected_set.add(precursor)
            current = precursor
    return [scan_id for scan_id in source_order if scan_id in selected_set]


def _expected_ids(
    stats: SourceStats,
    *,
    scan_count: int | None = None,
    scan_percent: float | None = None,
    include_ids: list[str] | None = None,
    exclude_ids: list[str] | None = None,
    ms_levels: set[int] | None = None,
    include_precursors: bool = True,
    seed: int = 42,
) -> list[str]:
    excluded_set = set(exclude_ids or [])

    def _eligible_ids() -> list[str]:
        return [
            scan_id
            for scan_id in stats.ordered_scan_ids
            if (ms_levels is None or stats.ms_level_by_id[scan_id] in ms_levels)
            and scan_id not in excluded_set
        ]

    if scan_count is not None:
        eligible = _eligible_ids()
        picked = set(random.Random(seed).sample(eligible, scan_count))
        selected = [scan_id for scan_id in stats.ordered_scan_ids if scan_id in picked]
    elif scan_percent is not None:
        eligible = _eligible_ids()
        count = math.ceil((scan_percent / 100.0) * len(eligible))
        picked = set(random.Random(seed).sample(eligible, count))
        selected = [scan_id for scan_id in stats.ordered_scan_ids if scan_id in picked]
    else:
        if include_ids is None:
            selected = [scan_id for scan_id in stats.ordered_scan_ids if scan_id not in excluded_set]
        else:
            include_set = set(include_ids)
            selected = [scan_id for scan_id in stats.ordered_scan_ids if scan_id in include_set]
            selected = [scan_id for scan_id in selected if scan_id not in excluded_set]

    if include_precursors:
        selected = _resolve_precursors_locally(selected, stats.precursor_by_id, stats.ordered_scan_ids)

    return [scan_id for scan_id in selected if scan_id not in excluded_set]


def _write_scan_file(path: Path, scan_ids: list[str]) -> Path:
    path.write_text("\n".join(scan_ids) + "\n", encoding="utf-8")
    return path


def _count_by_ms_level(source: MzMLSource) -> dict[int, int]:
    counts: dict[int, int] = {}
    for scan in source.scan_infos:
        if scan.ms_level is None:
            continue
        counts[scan.ms_level] = counts.get(scan.ms_level, 0) + 1
    return counts


def _assert_ms1_precursors_match_output_ms2(
    output_source: MzMLSource,
    stats: SourceStats,
) -> None:
    output_ids = {scan.scan_id for scan in output_source.scan_infos}
    output_ms2_ids = [scan.scan_id for scan in output_source.scan_infos if scan.ms_level == 2]
    output_ms1_ids = {scan.scan_id for scan in output_source.scan_infos if scan.ms_level == 1}

    expected_parent_ms1_ids = {
        precursor
        for scan_id in output_ms2_ids
        for precursor in [stats.precursor_by_id.get(scan_id)]
        if precursor is not None
        and precursor != scan_id
        and stats.ms_level_by_id.get(precursor) == 1
    }

    assert expected_parent_ms1_ids
    assert expected_parent_ms1_ids.issubset(output_ids)
    assert output_ms1_ids == expected_parent_ms1_ids


@pytest.mark.parametrize(
    ("name", "args_builder", "expected_builder", "expect_indexed", "expect_compression"),
    [
        (
            "count_no_precursors",
            lambda stats, tmp: ["--scan-count", "4", "--seed", "13", "--no-include-precursors"],
            lambda stats, tmp: _expected_ids(stats, scan_count=4, seed=13, include_precursors=False),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "count_ms2_with_precursors",
            lambda stats, tmp: ["--scan-count", "4", "--ms-level", "2", "--seed", "7"],
            lambda stats, tmp: _expected_ids(
                stats,
                scan_count=4,
                ms_levels={2},
                seed=7,
                include_precursors=True,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "percent_ms1_no_precursors",
            lambda stats, tmp: ["--scan-percent", "50", "--ms-level", "1", "--seed", "5", "--no-include-precursors"],
            lambda stats, tmp: _expected_ids(
                stats,
                scan_percent=50.0,
                ms_levels={1},
                seed=5,
                include_precursors=False,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "include_file_no_precursors",
            lambda stats, tmp: [
                "--scan-include-file",
                str(_write_scan_file(tmp / "include.txt", stats.ms2_with_parent_ids[:3])),
                "--no-include-precursors",
            ],
            lambda stats, tmp: _expected_ids(
                stats,
                include_ids=stats.ms2_with_parent_ids[:3],
                include_precursors=False,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "include_file_with_precursors",
            lambda stats, tmp: [
                "--scan-include-file",
                str(_write_scan_file(tmp / "include.txt", stats.ms2_with_parent_ids[:3])),
            ],
            lambda stats, tmp: _expected_ids(
                stats,
                include_ids=stats.ms2_with_parent_ids[:3],
                include_precursors=True,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "count_with_exclude",
            lambda stats, tmp: [
                "--scan-count",
                "5",
                "--seed",
                "23",
                "--scan-exclude-file",
                str(_write_scan_file(tmp / "exclude.txt", stats.ms1_ids[:2] + stats.ms2_ids[:2])),
                "--no-include-precursors",
            ],
            lambda stats, tmp: _expected_ids(
                stats,
                scan_count=5,
                seed=23,
                exclude_ids=stats.ms1_ids[:2] + stats.ms2_ids[:2],
                include_precursors=False,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "exclude_only_all_minus_excluded",
            lambda stats, tmp: [
                "--scan-exclude-file",
                str(_write_scan_file(tmp / "exclude.txt", stats.ordered_scan_ids[:3])),
            ],
            lambda stats, tmp: _expected_ids(
                stats,
                exclude_ids=stats.ordered_scan_ids[:3],
                include_precursors=True,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "include_and_exclude_disjoint",
            lambda stats, tmp: [
                "--scan-include-file",
                str(_write_scan_file(tmp / "include.txt", stats.ordered_scan_ids[:6])),
                "--scan-exclude-file",
                str(_write_scan_file(tmp / "exclude.txt", stats.ordered_scan_ids[10:12])),
                "--no-include-precursors",
            ],
            lambda stats, tmp: _expected_ids(
                stats,
                include_ids=stats.ordered_scan_ids[:6],
                exclude_ids=stats.ordered_scan_ids[10:12],
                include_precursors=False,
            ),
            lambda stats: stats.is_indexed,
            "source",
        ),
        (
            "forced_no_index",
            lambda stats, tmp: ["--scan-count", "3", "--seed", "9", "--no-index", "--no-include-precursors"],
            lambda stats, tmp: _expected_ids(stats, scan_count=3, seed=9, include_precursors=False),
            lambda stats: False,
            "source",
        ),
        (
            "forced_index_and_zlib",
            lambda stats, tmp: ["--scan-count", "3", "--seed", "9", "--indexed", "--compression", "zlib"],
            lambda stats, tmp: _expected_ids(stats, scan_count=3, seed=9, include_precursors=True),
            lambda stats: True,
            "zlib",
        ),
        (
            "forced_none_compression",
            lambda stats, tmp: ["--scan-count", "3", "--seed", "3", "--compression", "none"],
            lambda stats, tmp: _expected_ids(stats, scan_count=3, seed=3, include_precursors=True),
            lambda stats: stats.is_indexed,
            "none",
        ),
    ],
)
def test_smoke_miller_option_matrix(
    name: str,
    args_builder: Any,
    expected_builder: Any,
    expect_indexed: Any,
    expect_compression: str,
    smoke_stats: SourceStats,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / f"{name}.mzML"
    runner = CliRunner()

    args = [*args_builder(smoke_stats, tmp_path), str(smoke_stats.input_path), str(output_path)]
    result = runner.invoke(main, args)
    assert result.exit_code == 0, result.output

    output_source = MzMLSource(output_path)
    source = MzMLSource(smoke_stats.input_path)

    expected_ids = expected_builder(smoke_stats, tmp_path)
    actual_ids = [scan.scan_id for scan in output_source.scan_infos]
    assert actual_ids == expected_ids
    assert len(output_source.scan_infos) == len(expected_ids)
    assert output_source.is_indexed is expect_indexed(smoke_stats)

    for scan_id in expected_ids:
        source_mz, source_i = _spectrum_arrays(source, scan_id)
        output_mz, output_i = _spectrum_arrays(output_source, scan_id)
        assert np.array_equal(source_mz, output_mz)
        assert np.array_equal(source_i, output_i)

    if expect_compression in {"zlib", "none"}:
        accession = "MS:1000574" if expect_compression == "zlib" else "MS:1000576"
        for scan_id in expected_ids:
            spectrum = output_source.spectrum_by_id[scan_id]
            for bda in spectrum.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS):
                accessions = {cv.get("accession") for cv in bda.findall("mz:cvParam", NS)}
                assert accession in accessions


def test_smoke_include_exclude_overlap_errors(smoke_stats: SourceStats, tmp_path: Path) -> None:
    include_file = _write_scan_file(tmp_path / "include.txt", smoke_stats.ordered_scan_ids[:3])
    exclude_file = _write_scan_file(tmp_path / "exclude.txt", [smoke_stats.ordered_scan_ids[1]])

    runner = CliRunner()
    output_path = tmp_path / "overlap.mzML"
    result = runner.invoke(
        main,
        [
            "--scan-include-file",
            str(include_file),
            "--scan-exclude-file",
            str(exclude_file),
            str(smoke_stats.input_path),
            str(output_path),
        ],
    )
    assert result.exit_code == 2
    assert "overlap" in result.output


def test_smoke_percent_ms2_with_precursors_counts(smoke_stats: SourceStats, tmp_path: Path) -> None:
    output_path = tmp_path / "pct_ms2_with_precursors.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-percent",
            "50",
            "--ms-level",
            "2",
            "--seed",
            "11",
            str(smoke_stats.input_path),
            str(output_path),
        ],
    )
    assert result.exit_code == 0, result.output
    output_source = MzMLSource(output_path)
    counts = _count_by_ms_level(output_source)
    assert counts.get(2, 0) == 5
    assert counts.get(1, 0) == 5
    assert len(output_source.scan_infos) == 10
    _assert_ms1_precursors_match_output_ms2(output_source, smoke_stats)


def test_smoke_percent_ms2_no_precursors_counts(smoke_stats: SourceStats, tmp_path: Path) -> None:
    output_path = tmp_path / "pct_ms2_no_precursors.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-percent",
            "50",
            "--ms-level",
            "2",
            "--seed",
            "11",
            "--no-include-precursors",
            str(smoke_stats.input_path),
            str(output_path),
        ],
    )
    assert result.exit_code == 0, result.output
    output_source = MzMLSource(output_path)
    counts = _count_by_ms_level(output_source)
    assert counts.get(2, 0) == 5
    assert counts.get(1, 0) == 0
    assert len(output_source.scan_infos) == 5


def test_smoke_percent_ms1_only_counts(smoke_stats: SourceStats, tmp_path: Path) -> None:
    output_path = tmp_path / "pct_ms1_only.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-percent",
            "50",
            "--ms-level",
            "1",
            "--seed",
            "11",
            str(smoke_stats.input_path),
            str(output_path),
        ],
    )
    assert result.exit_code == 0, result.output
    output_source = MzMLSource(output_path)
    counts = _count_by_ms_level(output_source)
    assert counts.get(1, 0) == 5
    assert counts.get(2, 0) == 0
    assert len(output_source.scan_infos) == 5

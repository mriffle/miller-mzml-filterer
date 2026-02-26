from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from miller.cli import main
from miller.reader import MzMLSource


def _write_scan_file(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_cli_scan_count(nonindexed_fixture: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, ["--scan-count", "2", str(nonindexed_fixture), str(out)])
    assert result.exit_code == 0, result.output
    subset = MzMLSource(out)
    assert len(subset.scan_infos) >= 2


def test_cli_scan_include_file(nonindexed_fixture: Path, tmp_path: Path) -> None:
    include_file = tmp_path / "include.txt"
    _write_scan_file(include_file, ["1001", "1006"])

    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-include-file",
            str(include_file),
            "--no-include-precursors",
            str(nonindexed_fixture),
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    subset = MzMLSource(out)
    assert [s.scan_id for s in subset.scan_infos] == ["scan=1001", "scan=1006"]


def test_cli_reject_random_plus_include(nonindexed_fixture: Path, tmp_path: Path) -> None:
    include_file = tmp_path / "include.txt"
    _write_scan_file(include_file, ["1001"])

    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-count",
            "1",
            "--scan-include-file",
            str(include_file),
            str(nonindexed_fixture),
            str(out),
        ],
    )
    assert result.exit_code == 2


def test_cli_missing_scan(nonindexed_fixture: Path, tmp_path: Path) -> None:
    include_file = tmp_path / "include.txt"
    _write_scan_file(include_file, ["9999"])

    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, ["--scan-include-file", str(include_file), str(nonindexed_fixture), str(out)])
    assert result.exit_code == 3
    assert "not found" in result.output


def test_cli_ms_level_with_include_file_error(nonindexed_fixture: Path, tmp_path: Path) -> None:
    include_file = tmp_path / "include.txt"
    _write_scan_file(include_file, ["1001"])

    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-include-file",
            str(include_file),
            "--ms-level",
            "2",
            str(nonindexed_fixture),
            str(out),
        ],
    )
    assert result.exit_code == 2


def test_cli_count_exceeds_filtered_pool(nonindexed_fixture: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--scan-count", "1000", "--ms-level", "3", str(nonindexed_fixture), str(out)],
    )
    assert result.exit_code == 4


def test_cli_percent_mode(nonindexed_fixture: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--scan-percent", "25", "--no-include-precursors", str(nonindexed_fixture), str(out)],
    )
    assert result.exit_code == 0, result.output
    subset = MzMLSource(out)
    assert len(subset.scan_infos) == 5


def test_cli_neither_selection_option(nonindexed_fixture: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, [str(nonindexed_fixture), str(out)])
    assert result.exit_code == 2


def test_cli_invalid_input(tmp_path: Path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, ["--scan-count", "1", str(tmp_path / "missing.mzML"), str(out)])
    assert result.exit_code == 1


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Generate a subset mzML file for testing." in result.output


def test_cli_seed_deterministic(nonindexed_fixture: Path, tmp_path: Path) -> None:
    out1 = tmp_path / "a.mzML"
    out2 = tmp_path / "b.mzML"
    runner = CliRunner()
    args = ["--scan-count", "5", "--seed", "99", str(nonindexed_fixture)]
    result1 = runner.invoke(main, [*args, str(out1)])
    result2 = runner.invoke(main, [*args, str(out2)])
    assert result1.exit_code == 0, result1.output
    assert result2.exit_code == 0, result2.output
    assert out1.read_bytes() == out2.read_bytes()


def test_cli_index_override_and_compression(nonindexed_fixture: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--indexed",
            "--compression",
            "zlib",
            "--scan-count",
            "3",
            str(nonindexed_fixture),
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "<indexedmzML" in text


def test_cli_include_exclude_overlap_errors(nonindexed_fixture: Path, tmp_path: Path) -> None:
    include_file = tmp_path / "include.txt"
    exclude_file = tmp_path / "exclude.txt"
    _write_scan_file(include_file, ["1001", "1002"])
    _write_scan_file(exclude_file, ["1002"])

    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-include-file",
            str(include_file),
            "--scan-exclude-file",
            str(exclude_file),
            str(nonindexed_fixture),
            str(out),
        ],
    )
    assert result.exit_code == 2
    assert "overlap" in result.output


def test_cli_scan_count_with_exclusion_applies_before_random(nonindexed_fixture: Path, tmp_path: Path) -> None:
    exclude_file = tmp_path / "exclude.txt"
    _write_scan_file(exclude_file, ["1001", "1002", "1003", "1004", "1005", "1006"])

    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--scan-count",
            "2",
            "--scan-exclude-file",
            str(exclude_file),
            "--no-include-precursors",
            str(nonindexed_fixture),
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    subset = MzMLSource(out)
    assert all(s.scan_id not in {"scan=1001", "scan=1002", "scan=1003", "scan=1004", "scan=1005", "scan=1006"} for s in subset.scan_infos)

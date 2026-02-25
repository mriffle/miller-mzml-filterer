from __future__ import annotations

from click.testing import CliRunner

from miller.cli import main
from miller.reader import MzMLSource


def test_cli_scan_count(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, ["--scan-count", "2", str(nonindexed_fixture), str(out)])
    assert result.exit_code == 0, result.output
    subset = MzMLSource(out)
    assert len(subset.scan_infos) >= 2


def test_cli_scan_list(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--scan-list", "1001,1006", "--no-include-precursors", str(nonindexed_fixture), str(out)],
    )
    assert result.exit_code == 0, result.output
    subset = MzMLSource(out)
    assert [s.scan_id for s in subset.scan_infos] == ["scan=1001", "scan=1006"]


def test_cli_reject_both(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--scan-count", "1", "--scan-list", "1001", str(nonindexed_fixture), str(out)],
    )
    assert result.exit_code == 2


def test_cli_missing_scan(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, ["--scan-list", "9999", str(nonindexed_fixture), str(out)])
    assert result.exit_code == 3
    assert "not found" in result.output


def test_cli_ms_level_with_scan_list_error(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--scan-list", "1001", "--ms-level", "2", str(nonindexed_fixture), str(out)],
    )
    assert result.exit_code == 2


def test_cli_count_exceeds_filtered_pool(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--scan-count", "10", "--ms-level", "3", str(nonindexed_fixture), str(out)],
    )
    assert result.exit_code == 4


def test_cli_neither_selection_option(nonindexed_fixture, tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, [str(nonindexed_fixture), str(out)])
    assert result.exit_code == 2


def test_cli_invalid_input(tmp_path) -> None:
    out = tmp_path / "out.mzML"
    runner = CliRunner()
    result = runner.invoke(main, ["--scan-count", "1", str(tmp_path / "missing.mzML"), str(out)])
    assert result.exit_code == 1


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Generate a subset mzML file for testing." in result.output


def test_cli_seed_deterministic(nonindexed_fixture, tmp_path) -> None:
    out1 = tmp_path / "a.mzML"
    out2 = tmp_path / "b.mzML"
    runner = CliRunner()
    args = ["--scan-count", "5", "--seed", "99", str(nonindexed_fixture)]
    result1 = runner.invoke(main, [*args, str(out1)])
    result2 = runner.invoke(main, [*args, str(out2)])
    assert result1.exit_code == 0, result1.output
    assert result2.exit_code == 0, result2.output
    assert out1.read_bytes() == out2.read_bytes()


def test_cli_index_override_and_compression(nonindexed_fixture, tmp_path) -> None:
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

from __future__ import annotations

from pathlib import Path

import pytest

from miller.errors import UsageError
from miller.validation import (
    ensure_readable_input,
    ensure_writable_output,
    normalize_scan_id,
    parse_ms_levels,
    parse_rt_bound,
    parse_rt_window_percent,
    parse_scan_file,
    parse_scan_percent,
    validate_include_exclude_disjoint,
    validate_rt_range,
    validate_selection_mode,
)


def test_validate_selection_mode_requires_exactly_one() -> None:
    with pytest.raises(UsageError):
        validate_selection_mode(None, None, None, None, None, None, None, None)
    with pytest.raises(UsageError):
        validate_selection_mode(1, 10.0, None, None, None, None, None, None)
    with pytest.raises(UsageError):
        validate_selection_mode(1, None, Path("x.txt"), None, None, None, None, None)


def test_validate_selection_mode_rejects_ms_level_with_include_file() -> None:
    with pytest.raises(UsageError):
        validate_selection_mode(None, None, Path("in.txt"), None, None, None, None, "2")


def test_validate_selection_mode_accepts_valid_modes() -> None:
    validate_selection_mode(1, None, None, None, None, None, None, None)
    validate_selection_mode(None, 25.0, None, None, None, None, None, "2")
    validate_selection_mode(None, None, Path("in.txt"), None, None, None, None, None)
    validate_selection_mode(None, None, None, Path("exclude.txt"), None, None, None, None)
    validate_selection_mode(None, None, None, None, 5.0, None, None, None)
    validate_selection_mode(None, None, None, None, None, 25.0, None, None)


def test_validate_selection_mode_rejects_ms_level_with_exclude_only() -> None:
    with pytest.raises(UsageError):
        validate_selection_mode(None, None, None, Path("exclude.txt"), None, None, None, "2")


def test_ensure_writable_output_parent_missing(tmp_path: Path) -> None:
    with pytest.raises(PermissionError):
        ensure_writable_output(tmp_path / "missing" / "out.mzML")


def test_ensure_readable_input_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ensure_readable_input(tmp_path / "missing.mzML")


def test_ensure_writable_output_rejects_non_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    with pytest.raises(PermissionError):
        ensure_writable_output(out_dir)


def test_ensure_writable_output_create_and_existing(tmp_path: Path) -> None:
    new_path = tmp_path / "new.mzML"
    ensure_writable_output(new_path)

    existing = tmp_path / "existing.mzML"
    existing.write_text("x", encoding="utf-8")
    ensure_writable_output(existing)


def test_ensure_writable_output_raises_on_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "cantwrite.mzML"

    def _raise(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("denied")

    monkeypatch.setattr(Path, "open", _raise)
    with pytest.raises(PermissionError):
        ensure_writable_output(target)


def test_parse_scan_file_and_dedupe(tmp_path: Path) -> None:
    f = tmp_path / "include.txt"
    f.write_text("1001\nscan=1001\n1002\n\n", encoding="utf-8")
    assert parse_scan_file(f, "--scan-include-file") == ["scan=1001", "scan=1002"]


def test_parse_scan_file_invalid(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(UsageError):
        parse_scan_file(missing, "--scan-include-file")

    empty = tmp_path / "empty.txt"
    empty.write_text("\n\n", encoding="utf-8")
    with pytest.raises(UsageError):
        parse_scan_file(empty, "--scan-include-file")


def test_validate_include_exclude_disjoint() -> None:
    validate_include_exclude_disjoint(["scan=1"], ["scan=2"])
    with pytest.raises(UsageError):
        validate_include_exclude_disjoint(["scan=1"], ["scan=1", "scan=2"])


def test_normalize_scan_id_passthrough() -> None:
    assert normalize_scan_id("scan=1001") == "scan=1001"
    assert normalize_scan_id("1001") == "scan=1001"
    assert normalize_scan_id("controllerType=0 controllerNumber=1 scan=5") == "controllerType=0 controllerNumber=1 scan=5"


def test_parse_ms_levels_variants() -> None:
    assert parse_ms_levels(None) is None
    assert parse_ms_levels("1,2") == {1, 2}
    assert parse_ms_levels(" 1 , 3 ") == {1, 3}


def test_parse_ms_levels_invalid() -> None:
    with pytest.raises(UsageError):
        parse_ms_levels(" , ")
    with pytest.raises(UsageError):
        parse_ms_levels("abc")
    with pytest.raises(UsageError):
        parse_ms_levels("0")


def test_parse_scan_percent() -> None:
    assert parse_scan_percent(None) is None
    assert parse_scan_percent(10.0) == 10.0
    with pytest.raises(UsageError):
        parse_scan_percent(0.0)
    with pytest.raises(UsageError):
        parse_scan_percent(100.1)
    with pytest.raises(UsageError):
        parse_scan_percent(float("inf"))


def test_parse_rt_bound_and_range() -> None:
    assert parse_rt_bound(None, "--rt-range-start") is None
    assert parse_rt_bound(10.0, "--rt-range-start") == 10.0
    with pytest.raises(UsageError):
        parse_rt_bound(float("nan"), "--rt-range-start")
    validate_rt_range(1.0, 2.0)
    with pytest.raises(UsageError):
        validate_rt_range(3.0, 2.0)
    assert parse_rt_window_percent(25.0) == 25.0
    with pytest.raises(UsageError):
        parse_rt_window_percent(0.0)

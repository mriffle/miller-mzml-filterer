from __future__ import annotations

from pathlib import Path

import pytest

from miller.errors import UsageError
from miller.validation import (
    ensure_readable_input,
    ensure_writable_output,
    normalize_scan_id,
    parse_ms_levels,
    parse_scan_list,
    validate_selection_mode,
)


def test_validate_selection_mode_requires_exactly_one() -> None:
    with pytest.raises(UsageError):
        validate_selection_mode(None, None, None)
    with pytest.raises(UsageError):
        validate_selection_mode(1, "1001", None)


def test_validate_selection_mode_rejects_ms_level_with_scan_list() -> None:
    with pytest.raises(UsageError):
        validate_selection_mode(None, "1001", "2")


def test_validate_selection_mode_accepts_valid_modes() -> None:
    validate_selection_mode(1, None, None)
    validate_selection_mode(None, "1001", None)


def test_ensure_readable_input_missing() -> None:
    with pytest.raises(FileNotFoundError):
        ensure_readable_input(Path("/definitely/missing/file.mzML"))


def test_ensure_writable_output_parent_missing(tmp_path) -> None:
    with pytest.raises(PermissionError):
        ensure_writable_output(tmp_path / "missing" / "out.mzML")


def test_ensure_writable_output_rejects_non_file(tmp_path) -> None:
    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    with pytest.raises(PermissionError):
        ensure_writable_output(out_dir)


def test_ensure_writable_output_create_and_existing(tmp_path) -> None:
    new_path = tmp_path / "new.mzML"
    ensure_writable_output(new_path)

    existing = tmp_path / "existing.mzML"
    existing.write_text("x", encoding="utf-8")
    ensure_writable_output(existing)


def test_ensure_writable_output_raises_on_oserror(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "cantwrite.mzML"

    def _raise(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("denied")

    monkeypatch.setattr(Path, "open", _raise)
    with pytest.raises(PermissionError):
        ensure_writable_output(target)


def test_parse_scan_list_empty_and_dedupe() -> None:
    with pytest.raises(UsageError):
        parse_scan_list(" , ")
    assert parse_scan_list("1001,scan=1001,1002") == ["scan=1001", "scan=1002"]


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

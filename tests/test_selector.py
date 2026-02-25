from __future__ import annotations

import pytest

from miller.errors import MissingScanError, ScanCountError, UsageError
from miller.models import ScanInfo
from miller.selector import (
    filter_by_ms_level,
    resolve_precursors,
    select_explicit,
    select_random,
    select_scan_ids,
)


def _infos() -> list[ScanInfo]:
    return [
        ScanInfo("scan=1001", 0, 1, None),
        ScanInfo("scan=1002", 1, 2, "scan=1001"),
        ScanInfo("scan=1003", 2, 2, None),
        ScanInfo("scan=1004", 3, 1, None),
        ScanInfo("scan=1005", 4, 2, "scan=9999"),
        ScanInfo("scan=1006", 5, 3, "scan=1002"),
    ]


def test_random_deterministic() -> None:
    scan_ids = [s.scan_id for s in _infos()]
    a = select_random(scan_ids, 3, 42)
    b = select_random(scan_ids, 3, 42)
    assert a == b


def test_random_count_error() -> None:
    with pytest.raises(ScanCountError):
        select_random(["scan=1"], 2, 42)


def test_random_zero_error() -> None:
    with pytest.raises(UsageError):
        select_random(["scan=1"], 0, 42)


def test_random_returns_all_when_count_matches() -> None:
    scan_ids = ["scan=1", "scan=2"]
    assert select_random(scan_ids, 2, 42) == scan_ids


def test_explicit_missing() -> None:
    with pytest.raises(MissingScanError):
        select_explicit(["scan=1001"], ["scan=1002"])


def test_explicit_bare_numbers() -> None:
    result = select_explicit(["scan=1001", "scan=1002"], ["1002", "1001"])
    assert result == ["scan=1001", "scan=1002"]


def test_filter_by_ms_level() -> None:
    filtered = filter_by_ms_level(_infos(), {2})
    assert [x.scan_id for x in filtered] == ["scan=1002", "scan=1003", "scan=1005"]


def test_resolve_precursors_chain_and_sort(capsys: pytest.CaptureFixture[str]) -> None:
    infos = _infos()
    precursor_map = {s.scan_id: s.precursor_ref for s in infos}
    source_order = [s.scan_id for s in infos]
    result = resolve_precursors(["scan=1006", "scan=1005"], precursor_map, source_order)
    assert result == ["scan=1001", "scan=1002", "scan=1005", "scan=1006"]
    err = capsys.readouterr().err
    assert "scan=9999" in err


def test_resolve_precursors_self_ref_warns_dia(capsys: pytest.CaptureFixture[str]) -> None:
    source_order = ["scan=1001", "scan=1002"]
    precursor_map = {
        "scan=1001": None,
        "scan=1002": "scan=1002",
    }
    result = resolve_precursors(["scan=1002"], precursor_map, source_order)
    assert result == ["scan=1002"]
    err = capsys.readouterr().err
    assert "self-referential" in err
    assert "likely due to DIA data" in err


def test_resolve_precursors_handles_cycle_and_already_selected() -> None:
    precursor_map: dict[str, str | None] = {
        "scan=1": "scan=2",
        "scan=2": "scan=1",
        "scan=3": "scan=1",
    }
    result = resolve_precursors(["scan=3", "scan=1"], precursor_map, ["scan=1", "scan=2", "scan=3"])
    assert result == ["scan=1", "scan=2", "scan=3"]


def test_select_scan_ids_random_with_and_without_precursors() -> None:
    infos = _infos()
    selected_with = select_scan_ids(
        infos,
        scan_count=1,
        requested_scan_ids=None,
        ms_levels={3},
        include_precursors=True,
        seed=42,
    )
    assert selected_with == ["scan=1001", "scan=1002", "scan=1006"]

    selected_without = select_scan_ids(
        infos,
        scan_count=1,
        requested_scan_ids=None,
        ms_levels={3},
        include_precursors=False,
        seed=42,
    )
    assert selected_without == ["scan=1006"]


def test_select_scan_ids_explicit_mode() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        requested_scan_ids=["1002", "1001"],
        ms_levels=None,
        include_precursors=True,
        seed=42,
    )
    assert selected == ["scan=1001", "scan=1002"]


def test_select_scan_ids_count_exceeds_messages() -> None:
    infos = _infos()
    with pytest.raises(ScanCountError, match="exceeds available scans"):
        select_scan_ids(
            infos,
            scan_count=99,
            requested_scan_ids=None,
            ms_levels=None,
            include_precursors=True,
            seed=42,
        )
    with pytest.raises(ScanCountError, match="after --ms-level filtering"):
        select_scan_ids(
            infos,
            scan_count=99,
            requested_scan_ids=None,
            ms_levels={2},
            include_precursors=True,
            seed=42,
        )

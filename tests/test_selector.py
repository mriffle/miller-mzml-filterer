from __future__ import annotations

import pytest

from miller.errors import MissingScanError, ScanCountError, UsageError
from miller.models import ScanInfo
from miller.selector import (
    _describe_filtering,
    _no_eligible_message,
    _no_scans_selected_message,
    filter_by_ms_level,
    filter_by_random_rt_window,
    filter_by_retention_time,
    resolve_precursors,
    select_explicit,
    select_random,
    select_random_percent,
    select_scan_ids,
)


def _infos() -> list[ScanInfo]:
    return [
        ScanInfo("scan=1001", 0, 1, None, 1.0),
        ScanInfo("scan=1002", 1, 2, "scan=1001", 2.0),
        ScanInfo("scan=1003", 2, 2, None, 3.0),
        ScanInfo("scan=1004", 3, 1, None, 4.0),
        ScanInfo("scan=1005", 4, 2, "scan=9999", 5.0),
        ScanInfo("scan=1006", 5, 3, "scan=1002", 6.0),
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


def test_random_percent() -> None:
    scan_ids = [f"scan={i}" for i in range(1, 11)]
    result = select_random_percent(scan_ids, 10.0, 42)
    assert len(result) == 1
    result2 = select_random_percent(scan_ids, 100.0, 42)
    assert len(result2) == 10


def test_explicit_missing() -> None:
    with pytest.raises(MissingScanError):
        select_explicit(["scan=1001"], ["scan=1002"])


def test_explicit_bare_numbers() -> None:
    result = select_explicit(["scan=1001", "scan=1002"], ["1002", "1001"])
    assert result == ["scan=1001", "scan=1002"]


def test_filter_by_ms_level() -> None:
    filtered = filter_by_ms_level(_infos(), {2})
    assert [x.scan_id for x in filtered] == ["scan=1002", "scan=1003", "scan=1005"]


def test_filter_by_retention_time() -> None:
    filtered = filter_by_retention_time(_infos(), 2.5, 5.0)
    assert [x.scan_id for x in filtered] == ["scan=1003", "scan=1004", "scan=1005"]


def test_filter_by_retention_time_skips_missing_retention_time() -> None:
    infos = _infos() + [ScanInfo("scan=9999", 6, 1, None, None)]
    filtered = filter_by_retention_time(infos, 1.0, 10.0)
    assert [x.scan_id for x in filtered] == [info.scan_id for info in _infos()]


def test_filter_by_random_rt_window_deterministic() -> None:
    filtered = filter_by_random_rt_window(_infos(), 50.0, 42)
    assert [x.scan_id for x in filtered] == ["scan=1003", "scan=1004", "scan=1005"]


def test_filter_by_random_rt_window_invalid_percent() -> None:
    with pytest.raises(UsageError):
        filter_by_random_rt_window(_infos(), 0.0, 42)


def test_filter_by_random_rt_window_no_eligible_scans() -> None:
    infos = [ScanInfo("scan=1", 0, 1, None, None)]
    assert filter_by_random_rt_window(infos, 25.0, 42) == []


def test_filter_by_random_rt_window_all_when_span_zero() -> None:
    infos = [
        ScanInfo("scan=1", 0, 1, None, 5.0),
        ScanInfo("scan=2", 1, 1, None, 5.0),
    ]
    filtered = filter_by_random_rt_window(infos, 10.0, 42)
    assert [x.scan_id for x in filtered] == ["scan=1", "scan=2"]


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
        scan_percent=None,
        requested_scan_ids=None,
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=None,
        ms_levels={3},
        excluded_scan_ids=None,
        include_precursors=True,
        seed=42,
    )
    assert selected_with == ["scan=1001", "scan=1002", "scan=1006"]

    selected_without = select_scan_ids(
        infos,
        scan_count=1,
        scan_percent=None,
        requested_scan_ids=None,
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=None,
        ms_levels={3},
        excluded_scan_ids=None,
        include_precursors=False,
        seed=42,
    )
    assert selected_without == ["scan=1006"]


def test_select_scan_ids_explicit_mode() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        scan_percent=None,
        requested_scan_ids=["1002", "1001"],
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=None,
        ms_levels=None,
        excluded_scan_ids=None,
        include_precursors=True,
        seed=42,
    )
    assert selected == ["scan=1001", "scan=1002"]


def test_select_scan_ids_percent_with_exclude() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        scan_percent=50.0,
        requested_scan_ids=None,
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=None,
        ms_levels=None,
        excluded_scan_ids=["scan=1001", "scan=1002", "scan=1003"],
        include_precursors=False,
        seed=42,
    )
    assert all(scan_id not in {"scan=1001", "scan=1002", "scan=1003"} for scan_id in selected)


def test_select_scan_ids_explicit_respects_exclude() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        scan_percent=None,
        requested_scan_ids=["scan=1001", "scan=1002"],
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=None,
        ms_levels=None,
        excluded_scan_ids=["scan=1002"],
        include_precursors=False,
        seed=42,
    )
    assert selected == ["scan=1001"]


def test_select_scan_ids_exclude_only_mode() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        scan_percent=None,
        requested_scan_ids=None,
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=None,
        ms_levels=None,
        excluded_scan_ids=["scan=1002", "scan=1004"],
        include_precursors=False,
        seed=42,
    )
    assert selected == ["scan=1001", "scan=1003", "scan=1005", "scan=1006"]


def test_select_scan_ids_random_no_eligible_after_exclude() -> None:
    infos = _infos()
    with pytest.raises(ScanCountError, match="No eligible scans available"):
        select_scan_ids(
            infos,
            scan_count=1,
            scan_percent=None,
            requested_scan_ids=None,
            rt_range_start=None,
            rt_range_end=None,
            rt_window_percent=None,
            ms_levels=None,
            excluded_scan_ids=[s.scan_id for s in infos],
            include_precursors=False,
            seed=42,
        )


def test_select_scan_ids_random_no_eligible_after_ms_and_exclude() -> None:
    infos = _infos()
    with pytest.raises(ScanCountError, match="--ms-level filtering and exclusions"):
        select_scan_ids(
            infos,
            scan_count=1,
            scan_percent=None,
            requested_scan_ids=None,
            rt_range_start=None,
            rt_range_end=None,
            rt_window_percent=None,
            ms_levels={3},
            excluded_scan_ids=["scan=1006"],
            include_precursors=False,
            seed=42,
        )


def test_select_scan_ids_count_exceeds_messages() -> None:
    infos = _infos()
    with pytest.raises(ScanCountError, match="exceeds available scans"):
        select_scan_ids(
            infos,
            scan_count=99,
            scan_percent=None,
            requested_scan_ids=None,
            rt_range_start=None,
            rt_range_end=None,
            rt_window_percent=None,
            ms_levels=None,
            excluded_scan_ids=None,
            include_precursors=True,
            seed=42,
        )
    with pytest.raises(ScanCountError, match="after applying --ms-level filtering"):
        select_scan_ids(
            infos,
            scan_count=99,
            scan_percent=None,
            requested_scan_ids=None,
            rt_range_start=None,
            rt_range_end=None,
            rt_window_percent=None,
            ms_levels={2},
            excluded_scan_ids=None,
            include_precursors=True,
            seed=42,
        )


def test_select_scan_ids_rt_range_with_precursor_outside_range() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        scan_percent=None,
        requested_scan_ids=["scan=1002"],
        rt_range_start=2.0,
        rt_range_end=2.0,
        rt_window_percent=None,
        ms_levels=None,
        excluded_scan_ids=None,
        include_precursors=True,
        seed=42,
    )
    assert selected == ["scan=1001", "scan=1002"]


def test_select_scan_ids_rt_only_mode() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=None,
        scan_percent=None,
        requested_scan_ids=None,
        rt_range_start=2.0,
        rt_range_end=4.0,
        rt_window_percent=None,
        ms_levels=None,
        excluded_scan_ids=None,
        include_precursors=False,
        seed=42,
    )
    assert selected == ["scan=1002", "scan=1003", "scan=1004"]


def test_select_scan_ids_include_file_empty_after_rt_filter() -> None:
    infos = _infos()
    with pytest.raises(ScanCountError, match="retention-time filtering"):
        select_scan_ids(
            infos,
            scan_count=None,
            scan_percent=None,
            requested_scan_ids=["scan=1001"],
            rt_range_start=2.0,
            rt_range_end=6.0,
            rt_window_percent=None,
            ms_levels=None,
            excluded_scan_ids=None,
            include_precursors=False,
            seed=42,
        )


def test_select_scan_ids_rt_window_then_scan_count() -> None:
    infos = _infos()
    selected = select_scan_ids(
        infos,
        scan_count=2,
        scan_percent=None,
        requested_scan_ids=None,
        rt_range_start=None,
        rt_range_end=None,
        rt_window_percent=50.0,
        ms_levels=None,
        excluded_scan_ids=None,
        include_precursors=False,
        seed=42,
    )
    assert selected == ["scan=1003", "scan=1005"]


def test_select_scan_ids_no_eligible_without_filters() -> None:
    with pytest.raises(ScanCountError, match="No eligible scans available\\."):
        select_scan_ids(
            [],
            scan_count=1,
            scan_percent=None,
            requested_scan_ids=None,
            rt_range_start=None,
            rt_range_end=None,
            rt_window_percent=None,
            ms_levels=None,
            excluded_scan_ids=None,
            include_precursors=False,
            seed=42,
        )


def test_select_scan_ids_empty_explicit_without_filters() -> None:
    infos = _infos()
    with pytest.raises(ScanCountError, match="No scans selected\\."):
        select_scan_ids(
            infos,
            scan_count=None,
            scan_percent=None,
            requested_scan_ids=[],
            rt_range_start=None,
            rt_range_end=None,
            rt_window_percent=None,
            ms_levels=None,
            excluded_scan_ids=None,
            include_precursors=False,
            seed=42,
        )


def test_selector_message_helpers_cover_descriptions() -> None:
    assert (
        _describe_filtering(
            rt_range_start=1.0,
            rt_range_end=2.0,
            rt_window_percent=25.0,
            ms_levels={2},
            excluded_set={"scan=1"},
        )
        == "retention-time filtering, random retention-time window filtering, --ms-level filtering, and exclusions"
    )
    assert _no_eligible_message(None) == "No eligible scans available."
    assert _no_scans_selected_message(None) == "No scans selected."

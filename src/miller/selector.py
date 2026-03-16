"""Scan selection and precursor expansion logic."""

from __future__ import annotations

import math
import random
import sys
from collections.abc import Iterable

from .errors import MissingScanError, ScanCountError, UsageError
from .models import ScanInfo
from .validation import normalize_scan_id


def filter_by_ms_level(scan_metadata: list[ScanInfo], levels: set[int]) -> list[ScanInfo]:
    return [info for info in scan_metadata if info.ms_level in levels]


def filter_by_retention_time(
    scan_metadata: list[ScanInfo],
    start: float | None,
    end: float | None,
) -> list[ScanInfo]:
    filtered: list[ScanInfo] = []
    for info in scan_metadata:
        if info.retention_time is None:
            continue
        if start is not None and info.retention_time < start:
            continue
        if end is not None and info.retention_time > end:
            continue
        filtered.append(info)
    return filtered


def filter_by_random_rt_window(
    scan_metadata: list[ScanInfo],
    percent: float,
    seed: int,
) -> list[ScanInfo]:
    if percent <= 0 or percent > 100:
        raise UsageError("--rt-window-percent must be greater than 0 and at most 100.")
    eligible = [info for info in scan_metadata if info.retention_time is not None]
    if not eligible:
        return []

    retention_times = [info.retention_time for info in eligible if info.retention_time is not None]
    min_rt = min(retention_times)
    max_rt = max(retention_times)
    span = max_rt - min_rt
    if span <= 0 or percent == 100:
        return eligible

    width = (percent / 100.0) * span
    latest_start = max_rt - width
    rng = random.Random(seed)
    window_start = rng.uniform(min_rt, latest_start)
    window_end = window_start + width
    return [
        info
        for info in eligible
        if info.retention_time is not None and window_start <= info.retention_time <= window_end
    ]


def select_random(scan_ids: list[str], count: int, seed: int) -> list[str]:
    if count <= 0:
        raise UsageError("--scan-count must be greater than zero.")
    available = len(scan_ids)
    if count > available:
        raise ScanCountError(f"Requested scan count {count} exceeds available scans {available}.")
    if count == available:
        return list(scan_ids)
    rng = random.Random(seed)
    selected = set(rng.sample(scan_ids, count))
    return [scan_id for scan_id in scan_ids if scan_id in selected]


def select_explicit(scan_ids: list[str], requested: list[str]) -> list[str]:
    requested_set = {normalize_scan_id(s) for s in requested}
    scan_set = set(scan_ids)
    missing = sorted(requested_set - scan_set)
    if missing:
        raise MissingScanError(missing)
    return [scan_id for scan_id in scan_ids if scan_id in requested_set]


def select_random_percent(scan_ids: list[str], percent: float, seed: int) -> list[str]:
    count = math.ceil((percent / 100.0) * len(scan_ids))
    return select_random(scan_ids, count, seed)


def resolve_precursors(
    selected: list[str],
    precursor_map: dict[str, str | None],
    source_order: list[str],
) -> list[str]:
    selected_set = set(selected)
    added_precursors = 0
    self_ref_count = 0
    for scan_id in list(selected):
        current = scan_id
        seen: set[str] = set()
        while True:
            precursor = precursor_map.get(current)
            if precursor is None:
                break
            if precursor == current:
                self_ref_count += 1
                break
            if precursor in seen:
                break
            seen.add(precursor)
            if precursor not in precursor_map:
                print(
                    f"Warning: precursor reference '{precursor}' for scan '{current}' not found in source file.",
                    file=sys.stderr,
                )
                break
            if precursor in selected_set:
                current = precursor
                continue
            selected_set.add(precursor)
            added_precursors += 1
            current = precursor
    if self_ref_count > 0 and added_precursors == 0:
        print(
            "Warning: precursor spectrumRef values are self-referential, so no precursor scans were added. "
            "This is likely due to DIA data.",
            file=sys.stderr,
        )
    return [scan_id for scan_id in source_order if scan_id in selected_set]


def select_scan_ids(
    scan_infos: list[ScanInfo],
    *,
    scan_count: int | None,
    scan_percent: float | None,
    requested_scan_ids: Iterable[str] | None,
    rt_range_start: float | None,
    rt_range_end: float | None,
    rt_window_percent: float | None,
    ms_levels: set[int] | None,
    excluded_scan_ids: Iterable[str] | None,
    include_precursors: bool,
    seed: int,
) -> list[str]:
    source_order = [s.scan_id for s in scan_infos]
    excluded_set = {normalize_scan_id(s) for s in excluded_scan_ids} if excluded_scan_ids else set()
    eligible_infos = scan_infos
    if rt_range_start is not None or rt_range_end is not None:
        eligible_infos = filter_by_retention_time(eligible_infos, rt_range_start, rt_range_end)
    if rt_window_percent is not None:
        eligible_infos = filter_by_random_rt_window(eligible_infos, rt_window_percent, seed)
    if ms_levels is not None:
        eligible_infos = filter_by_ms_level(eligible_infos, ms_levels)
    eligible_ids = [s.scan_id for s in eligible_infos if s.scan_id not in excluded_set]
    filter_description = _describe_filtering(
        rt_range_start=rt_range_start,
        rt_range_end=rt_range_end,
        rt_window_percent=rt_window_percent,
        ms_levels=ms_levels,
        excluded_set=excluded_set,
    )
    if (scan_count is not None or scan_percent is not None) and not eligible_ids:
        raise ScanCountError(_no_eligible_message(filter_description))

    if scan_count is not None:
        if scan_count > len(eligible_ids):
            raise ScanCountError(
                _count_exceeds_message(scan_count, len(eligible_ids), filter_description)
            )
        selected = select_random(eligible_ids, scan_count, seed)
    elif scan_percent is not None:
        selected = select_random_percent(eligible_ids, scan_percent, seed)
    else:
        if requested_scan_ids is not None:
            existing_selected = select_explicit(source_order, list(requested_scan_ids))
            eligible_set = set(eligible_ids)
            selected = [scan_id for scan_id in existing_selected if scan_id in eligible_set]
        else:
            selected = list(eligible_ids)

    if not selected:
        raise ScanCountError(_no_scans_selected_message(filter_description))

    if not include_precursors:
        return [scan_id for scan_id in selected if scan_id not in excluded_set]

    precursor_map = {s.scan_id: s.precursor_ref for s in scan_infos}
    resolved = resolve_precursors(selected, precursor_map, source_order)
    return [scan_id for scan_id in resolved if scan_id not in excluded_set]


def _describe_filtering(
    *,
    rt_range_start: float | None,
    rt_range_end: float | None,
    rt_window_percent: float | None,
    ms_levels: set[int] | None,
    excluded_set: set[str],
) -> str | None:
    parts: list[str] = []
    if rt_range_start is not None or rt_range_end is not None:
        parts.append("retention-time filtering")
    if rt_window_percent is not None:
        parts.append("random retention-time window filtering")
    if ms_levels is not None:
        parts.append("--ms-level filtering")
    if excluded_set:
        parts.append("exclusions")
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _no_eligible_message(filter_description: str | None) -> str:
    if filter_description is None:
        return "No eligible scans available."
    return f"No eligible scans available after applying {filter_description}."


def _no_scans_selected_message(filter_description: str | None) -> str:
    if filter_description is None:
        return "No scans selected."
    return f"No scans selected after applying {filter_description}."


def _count_exceeds_message(count: int, available: int, filter_description: str | None) -> str:
    if filter_description is None:
        return f"Requested scan count {count} exceeds available scans {available}."
    return (
        f"Requested scan count {count} exceeds available scans {available} "
        f"after applying {filter_description}."
    )

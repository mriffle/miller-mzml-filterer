"""Scan selection and precursor expansion logic."""

from __future__ import annotations

import random
import sys
from collections.abc import Iterable

from .errors import MissingScanError, ScanCountError, UsageError
from .models import ScanInfo
from .validation import normalize_scan_id


def filter_by_ms_level(scan_metadata: list[ScanInfo], levels: set[int]) -> list[ScanInfo]:
    return [info for info in scan_metadata if info.ms_level in levels]


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
    requested_scan_ids: Iterable[str] | None,
    ms_levels: set[int] | None,
    include_precursors: bool,
    seed: int,
) -> list[str]:
    source_order = [s.scan_id for s in scan_infos]
    eligible_infos = scan_infos
    if ms_levels is not None:
        eligible_infos = filter_by_ms_level(scan_infos, ms_levels)
    eligible_ids = [s.scan_id for s in eligible_infos]

    if scan_count is not None:
        if scan_count > len(eligible_ids):
            if ms_levels is None:
                raise ScanCountError(
                    f"Requested scan count {scan_count} exceeds available scans {len(eligible_ids)}."
                )
            raise ScanCountError(
                f"Requested scan count {scan_count} exceeds available scans {len(eligible_ids)} after --ms-level filtering."
            )
        selected = select_random(eligible_ids, scan_count, seed)
    else:
        assert requested_scan_ids is not None
        selected = select_explicit(source_order, list(requested_scan_ids))

    if not include_precursors:
        return selected

    precursor_map = {s.scan_id: s.precursor_ref for s in scan_infos}
    return resolve_precursors(selected, precursor_map, source_order)

"""Validation helpers."""

from __future__ import annotations

from pathlib import Path
import math

from .errors import UsageError


def validate_selection_mode(
    scan_count: int | None,
    scan_percent: float | None,
    scan_include_file: Path | None,
    scan_exclude_file: Path | None,
    rt_range_start: float | None,
    rt_range_end: float | None,
    rt_window_percent: float | None,
    ms_level: str | None,
) -> None:
    has_count = scan_count is not None
    has_percent = scan_percent is not None
    has_include_file = scan_include_file is not None
    has_exclude_file = scan_exclude_file is not None
    has_rt_filter = (
        rt_range_start is not None or rt_range_end is not None or rt_window_percent is not None
    )
    selected_modes = sum([has_count, has_percent, has_include_file])
    if selected_modes > 1:
        raise UsageError(
            "Exactly one of --scan-count, --scan-percent, or --scan-include-file must be provided."
        )
    if selected_modes == 0 and not has_exclude_file and not has_rt_filter:
        raise UsageError(
            "Provide one of --scan-count, --scan-percent, --scan-include-file, "
            "--rt-range-start/--rt-range-end, --rt-window-percent, or use --scan-exclude-file alone."
        )
    if has_include_file and ms_level:
        raise UsageError(
            "--ms-level is only valid with random selection (--scan-count or --scan-percent) "
            "and cannot be used with --scan-include-file."
        )
    if ms_level and not (has_count or has_percent):
        raise UsageError(
            "--ms-level is only valid with random selection (--scan-count or --scan-percent)."
        )


def ensure_readable_input(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Input file does not exist or is not a file: {path}")


def ensure_writable_output(path: Path) -> None:
    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        raise PermissionError(f"Output directory does not exist: {parent}")
    if path.exists() and not path.is_file():
        raise PermissionError(f"Output path is not a file: {path}")
    try:
        if path.exists():
            with path.open("ab"):
                pass
        else:
            with path.open("wb"):
                pass
            path.unlink()
    except OSError as exc:
        raise PermissionError(f"Output path is not writable: {path}") from exc


def parse_scan_file(scan_file: Path, option_name: str) -> list[str]:
    try:
        text = scan_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"{option_name} file is not readable: {scan_file}") from exc

    values = [v.strip() for v in text.splitlines() if v.strip()]
    if not values:
        raise UsageError(f"{option_name} must contain at least one scan identifier per line.")
    canonical = []
    seen: set[str] = set()
    for value in values:
        scan_id = normalize_scan_id(value)
        if scan_id not in seen:
            seen.add(scan_id)
            canonical.append(scan_id)
    return canonical


def normalize_scan_id(value: str) -> str:
    val = value.strip()
    if val.startswith("scan="):
        return val
    if val.isdigit():
        return f"scan={val}"
    return val


def parse_ms_levels(ms_level: str | None) -> set[int] | None:
    if not ms_level:
        return None
    parts = [p.strip() for p in ms_level.split(",") if p.strip()]
    if not parts:
        raise UsageError("--ms-level must contain one or more integers, e.g. 1 or 1,2")
    levels: set[int] = set()
    for part in parts:
        if not part.isdigit():
            raise UsageError(f"Invalid MS level '{part}'. Expected integer values like 1,2.")
        level = int(part)
        if level <= 0:
            raise UsageError("MS levels must be positive integers.")
        levels.add(level)
    return levels


def parse_rt_window_percent(rt_window_percent: float | None) -> float | None:
    return parse_percent(rt_window_percent, "--rt-window-percent")


def parse_percent(value: float | None, option_name: str) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        raise UsageError(f"{option_name} must be a finite number between 0 and 100.")
    if value <= 0 or value > 100:
        raise UsageError(f"{option_name} must be greater than 0 and at most 100.")
    return value


def parse_scan_percent(scan_percent: float | None) -> float | None:
    return parse_percent(scan_percent, "--scan-percent")


def parse_rt_bound(value: float | None, option_name: str) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        raise UsageError(f"{option_name} must be a finite number.")
    return value


def validate_rt_range(start: float | None, end: float | None) -> None:
    if start is not None and end is not None and start > end:
        raise UsageError("--rt-range-start must be less than or equal to --rt-range-end.")


def validate_include_exclude_disjoint(included: list[str], excluded: list[str]) -> None:
    overlap = sorted(set(included).intersection(excluded))
    if overlap:
        joined = ", ".join(overlap)
        raise UsageError(
            f"Include and exclude scan files overlap. Remove duplicates from one file: {joined}"
        )

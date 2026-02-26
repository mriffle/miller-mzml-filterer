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
    ms_level: str | None,
) -> None:
    has_count = scan_count is not None
    has_percent = scan_percent is not None
    has_include_file = scan_include_file is not None
    has_exclude_file = scan_exclude_file is not None
    selected_modes = sum([has_count, has_percent, has_include_file])
    if selected_modes > 1:
        raise UsageError(
            "Exactly one of --scan-count, --scan-percent, or --scan-include-file must be provided."
        )
    if selected_modes == 0 and not has_exclude_file:
        raise UsageError(
            "Provide one of --scan-count, --scan-percent, --scan-include-file, "
            "or use --scan-exclude-file alone."
        )
    if has_include_file and ms_level:
        raise UsageError(
            "--ms-level is only valid with random selection (--scan-count or --scan-percent) "
            "and cannot be used with --scan-include-file."
        )
    if selected_modes == 0 and has_exclude_file and ms_level:
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


def parse_scan_percent(scan_percent: float | None) -> float | None:
    if scan_percent is None:
        return None
    if not math.isfinite(scan_percent):
        raise UsageError("--scan-percent must be a finite number between 0 and 100.")
    if scan_percent <= 0 or scan_percent > 100:
        raise UsageError("--scan-percent must be greater than 0 and at most 100.")
    return scan_percent


def validate_include_exclude_disjoint(included: list[str], excluded: list[str]) -> None:
    overlap = sorted(set(included).intersection(excluded))
    if overlap:
        joined = ", ".join(overlap)
        raise UsageError(
            f"Include and exclude scan files overlap. Remove duplicates from one file: {joined}"
        )

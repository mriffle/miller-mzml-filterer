"""Validation helpers."""

from __future__ import annotations

from pathlib import Path

from .errors import UsageError


def validate_selection_mode(scan_count: int | None, scan_list: str | None, ms_level: str | None) -> None:
    has_count = scan_count is not None
    has_list = scan_list is not None and scan_list.strip() != ""
    if has_count == has_list:
        raise UsageError("Exactly one of --scan-count or --scan-list must be provided.")
    if has_list and ms_level:
        raise UsageError("--ms-level is only valid with --scan-count and cannot be used with --scan-list.")


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


def parse_scan_list(scan_list: str) -> list[str]:
    values = [v.strip() for v in scan_list.split(",") if v.strip()]
    if not values:
        raise UsageError("--scan-list must contain at least one scan identifier.")
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

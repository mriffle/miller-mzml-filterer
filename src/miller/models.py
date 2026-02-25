from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanInfo:
    scan_id: str
    index: int
    ms_level: int | None
    precursor_ref: str | None

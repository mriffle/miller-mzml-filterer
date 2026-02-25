"""Custom exception hierarchy for CLI exit code mapping."""

from __future__ import annotations


class MillerError(Exception):
    """Base exception."""


class InputFileError(MillerError):
    """Input cannot be read as mzML."""


class UsageError(MillerError):
    """Invalid argument combination."""


class MissingScanError(MillerError):
    """One or more requested scans do not exist."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        joined = ", ".join(missing)
        super().__init__(f"Requested scans not found: {joined}")


class ScanCountError(MillerError):
    """Requested random count exceeds eligible pool."""


class OutputWriteError(MillerError):
    """Output path cannot be written."""

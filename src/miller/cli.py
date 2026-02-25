"""CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click

from .errors import InputFileError, MissingScanError, OutputWriteError, ScanCountError, UsageError
from .reader import MzMLSource
from .selector import select_scan_ids
from .validation import (
    ensure_readable_input,
    ensure_writable_output,
    parse_ms_levels,
    parse_scan_list,
    validate_selection_mode,
)
from .writer import write_subset


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.option("--scan-count", type=int, default=None, help="Number of random scans to select.")
@click.option("--scan-list", type=str, default=None, help="Comma-separated scan IDs to select.")
@click.option(
    "--ms-level",
    type=str,
    default=None,
    help='Comma-separated MS levels to include (e.g., "1" or "1,2"). Only valid with --scan-count.',
)
@click.option("--include-precursors/--no-include-precursors", default=True, show_default=True)
@click.option("--indexed/--no-index", default=None, help="Force indexed or non-indexed output.")
@click.option(
    "--compression",
    type=click.Choice(["source", "zlib", "none"], case_sensitive=True),
    default="source",
    show_default=True,
)
@click.option("--seed", type=int, default=42, show_default=True)
@click.argument("input_path", type=click.Path(path_type=Path, dir_okay=False))
@click.argument("output_path", type=click.Path(path_type=Path, dir_okay=False))
def main(
    scan_count: int | None,
    scan_list: str | None,
    ms_level: str | None,
    include_precursors: bool,
    indexed: bool | None,
    compression: str,
    seed: int,
    input_path: Path,
    output_path: Path,
) -> None:
    """Generate a subset mzML file for testing."""
    try:
        validate_selection_mode(scan_count, scan_list, ms_level)
        ensure_readable_input(input_path)
        ensure_writable_output(output_path)

        requested_scan_ids = parse_scan_list(scan_list) if scan_list else None
        ms_levels = parse_ms_levels(ms_level)

        source = MzMLSource(input_path)
        output_indexed = source.is_indexed if indexed is None else indexed

        selected_ids = select_scan_ids(
            source.scan_infos,
            scan_count=scan_count,
            requested_scan_ids=requested_scan_ids,
            ms_levels=ms_levels,
            include_precursors=include_precursors,
            seed=seed,
        )

        write_subset(
            source,
            selected_ids,
            output_path,
            indexed=output_indexed,
            compression=compression,
        )
    except FileNotFoundError as exc:
        _fail(1, str(exc))
    except InputFileError as exc:
        _fail(1, str(exc))
    except UsageError as exc:
        _fail(2, str(exc))
    except MissingScanError as exc:
        _fail(3, str(exc))
    except ScanCountError as exc:
        _fail(4, str(exc))
    except (PermissionError, OutputWriteError) as exc:
        _fail(5, str(exc))


def _fail(code: int, message: str) -> None:
    click.echo(message, err=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main(prog_name="miller")

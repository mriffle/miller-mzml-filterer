"""CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click

from ._version import get_version
from .errors import InputFileError, MissingScanError, OutputWriteError, ScanCountError, UsageError
from .reader import MzMLSource
from .selector import select_scan_ids
from .validation import (
    ensure_readable_input,
    ensure_writable_output,
    parse_rt_bound,
    parse_rt_window_percent,
    parse_scan_file,
    parse_scan_percent,
    parse_ms_levels,
    validate_include_exclude_disjoint,
    validate_rt_range,
    validate_selection_mode,
)
from .writer import write_subset


def _show_version(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return

    click.echo(get_version())
    ctx.exit()


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.option(
    "-v",
    "--version",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_show_version,
    help="Show the program version and exit.",
)
@click.option("--scan-count", type=int, default=None, help="Number of random scans to select.")
@click.option(
    "--scan-percent",
    type=float,
    default=None,
    help="Percent of eligible scans to select at random (0 < percent <= 100).",
)
@click.option(
    "--scan-include-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="File containing one scan identifier per line to include.",
)
@click.option(
    "--scan-exclude-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="File containing one scan identifier per line to exclude.",
)
@click.option("--rt-range-start", type=float, default=None, help="Minimum retention time to include.")
@click.option("--rt-range-end", type=float, default=None, help="Maximum retention time to include.")
@click.option(
    "--rt-window-percent",
    type=float,
    default=None,
    help="Percent of the eligible retention-time span to keep in a random contiguous window.",
)
@click.option(
    "--ms-level",
    type=str,
    default=None,
    help='Comma-separated MS levels to include (e.g., "1" or "1,2"). Only valid with random selection.',
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
    scan_percent: float | None,
    scan_include_file: Path | None,
    scan_exclude_file: Path | None,
    rt_range_start: float | None,
    rt_range_end: float | None,
    rt_window_percent: float | None,
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
        validate_selection_mode(
            scan_count,
            scan_percent,
            scan_include_file,
            scan_exclude_file,
            rt_range_start,
            rt_range_end,
            rt_window_percent,
            ms_level,
        )
        ensure_readable_input(input_path)
        ensure_writable_output(output_path)

        scan_percent = parse_scan_percent(scan_percent)
        rt_range_start = parse_rt_bound(rt_range_start, "--rt-range-start")
        rt_range_end = parse_rt_bound(rt_range_end, "--rt-range-end")
        rt_window_percent = parse_rt_window_percent(rt_window_percent)
        validate_rt_range(rt_range_start, rt_range_end)
        requested_scan_ids = (
            parse_scan_file(scan_include_file, "--scan-include-file")
            if scan_include_file is not None
            else None
        )
        excluded_scan_ids = (
            parse_scan_file(scan_exclude_file, "--scan-exclude-file")
            if scan_exclude_file is not None
            else []
        )
        if requested_scan_ids is not None:
            validate_include_exclude_disjoint(requested_scan_ids, excluded_scan_ids)
        ms_levels = parse_ms_levels(ms_level)

        source = MzMLSource(input_path)
        output_indexed = source.is_indexed if indexed is None else indexed

        selected_ids = select_scan_ids(
            source.scan_infos,
            scan_count=scan_count,
            scan_percent=scan_percent,
            requested_scan_ids=requested_scan_ids,
            rt_range_start=rt_range_start,
            rt_range_end=rt_range_end,
            rt_window_percent=rt_window_percent,
            ms_levels=ms_levels,
            excluded_scan_ids=excluded_scan_ids,
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

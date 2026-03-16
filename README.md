# Miller

`miller` creates small, representative mzML files from full-sized proteomics mzML datasets. The goal is realistic test fixtures for CI, integration tests, and local development without shipping multi-GB raw conversions.

## Key Properties

- Fidelity: preserves mzML structure and metadata; only the spectrum set is reduced.
- Determinism: random selection is reproducible via `--seed` (default `42`).
- Correctness-first: explicit validation and stable exit codes for automation.

## What It Does (High Level)

- Selects spectra by:
  - Random count: `--scan-count N`
  - Random percent: `--scan-percent PCT`
  - Include file: `--scan-include-file path/to/include.txt`
- Optional retention-time filtering: `--rt-range-start MIN_RT`, `--rt-range-end MAX_RT`
- Optional random retention-time window: `--rt-window-percent PCT`
- Optional exclusion file: `--scan-exclude-file path/to/exclude.txt`
- Optional MS-level pre-filtering for random mode: `--ms-level 1`, `--ms-level 2`, `--ms-level 1,2`.
- Precursor inclusion (default on): if an MSn scan references a precursor via `spectrumRef`, the full precursor chain is included.
- Preserves run-level sections and metadata, updates `spectrumList/@count`.
- Chromatograms:
  - Recalculates TIC (`MS:1000235`) and BPC (`MS:1000628`) from retained spectra when present.
  - Passes through all other chromatograms unmodified.
- Output format:
  - Indexed or non-indexed mzML output, defaulting to the source unless overridden.
  - Binary array compression control: `source`, `zlib`, or `none`.

## How To Run

Basic usage:

```bash
miller [OPTIONS] INPUT OUTPUT
```

### Local day-to-day usage

Typical workflow is: keep large source mzMLs somewhere on disk, generate small subsets into a separate folder, then point your CI/tests/tools at the subset files.

Example directory layout:

```text
project/
  data/
    input.mzML
  subsets/
```

Create a subset (random selection):

```bash
mkdir -p subsets
miller --scan-count 50 data/input.mzML subsets/input.subset_50.mzML
```

Create a subset from only MS2 scans (still includes precursor MS1 scans when referenced):

```bash
miller --ms-level 2 --scan-count 10 data/input.mzML subsets/input.ms2_10_plus_precursors.mzML
```

Create a subset with exact scan IDs using an include file (`one scan ID per line`, no header):

```bash
cat > subsets/include_scans.txt <<'EOF'
1001
1002
1050
EOF
miller --scan-include-file subsets/include_scans.txt data/input.mzML subsets/input.scans_1001_1002_1050.mzML
```

Create a random subset by percent:

```bash
miller --scan-percent 5 data/input.mzML subsets/input.subset_5pct.mzML
```

Create a subset from a chromatographic time window:

```bash
miller --rt-range-start 35.2 --rt-range-end 35.8 data/input.mzML subsets/input.rt_35p2_35p8.mzML
```

Use a retention-time filter before random selection:

```bash
miller --rt-range-start 35.2 --rt-range-end 35.8 --scan-count 50 data/input.mzML subsets/input.rt_window_random_50.mzML
```

Keep a random contiguous 10% retention-time window, then select 25 scans from within it:

```bash
miller --rt-window-percent 10 --scan-count 25 data/input.mzML subsets/input.rt_segment_10pct_count25.mzML
```

Exclude specific scans from random candidate pool (and final output):

```bash
cat > subsets/exclude_scans.txt <<'EOF'
1001
1002
EOF
miller --scan-count 50 --scan-exclude-file subsets/exclude_scans.txt data/input.mzML subsets/input.subset_50_excl.mzML
```

Exclude-only mode (all scans except excluded):

```bash
miller --scan-exclude-file subsets/exclude_scans.txt data/input.mzML subsets/input.all_minus_excluded.mzML
```

Disable precursor inclusion (output contains exactly the selected scans):

```bash
miller --no-include-precursors --scan-count 10 data/input.mzML subsets/input.subset_10_no_precursors.mzML
```

Force indexed/non-indexed output and compression:

```bash
miller --indexed --compression zlib --scan-count 10 data/input.mzML subsets/input.indexed.zlib.mzML
miller --no-index --compression none --scan-count 10 data/input.mzML subsets/input.noindex.none.mzML
```

### Notes on determinism

Random selection uses `--seed` (default `42`). If you want different subsets from the same file, vary the seed:

```bash
miller --scan-count 50 --seed 1 data/input.mzML subsets/input.subset_seed1.mzML
miller --scan-count 50 --seed 2 data/input.mzML subsets/input.subset_seed2.mzML
```

### Quick examples (minimal)

Randomly select 50 scans:

```bash
miller --scan-count 50 input.mzML output.mzML
```

Select specific scans via include file:

```bash
miller --scan-include-file include_scans.txt input.mzML output.mzML
```

Randomly select by percent:

```bash
miller --scan-percent 10 input.mzML output.mzML
```

Only draw from MS2 scans, but still include MS1 precursors if referenced:

```bash
miller --ms-level 2 --scan-count 10 input.mzML output.mzML
```

Disable precursor chain inclusion:

```bash
miller --no-include-precursors --scan-count 10 input.mzML output.mzML
```

Force output format and compression:

```bash
miller --indexed --compression zlib --scan-count 10 input.mzML output.mzML
miller --no-index --compression none --scan-count 10 input.mzML output.mzML
```

## CLI Parameters

Positional arguments:

- `INPUT` (required): path to the source mzML file (indexed or non-indexed).
- `OUTPUT` (required): path for the output mzML file.

Selection mode:

- `--scan-count INTEGER`: randomly select N scans uniformly from the eligible pool.
  - Output order is the original file order, not the random draw order.
  - If N exceeds the eligible pool size, the program exits non-zero (see Exit Codes).
- `--scan-percent FLOAT`: randomly select a percentage of eligible scans.
  - Must be `> 0` and `<= 100`.
  - Selection count is computed from the eligible pool after any exclusions.
- `--scan-include-file PATH`: file with one scan ID per line to include.
  - Accepts either bare numbers (`1001`) or prefixed IDs (`scan=1001`).
  - Output order follows source file order.
  - Incompatible with `--scan-count` and `--scan-percent`.
- `--scan-exclude-file PATH` can also be used alone (no include/count/percent), which means:
  - Start from all scans in input.
  - Apply any retention-time bounds.
  - Exclude listed scans.
  - Then apply precursor inclusion behavior and final exclusion.
- `--rt-range-start FLOAT` and `--rt-range-end FLOAT`:
  - Optional inclusive retention-time bounds applied before selection.
  - If only one bound is provided, the other side is left open.
  - Can be combined with random selection, include-file selection, or used by themselves to keep all scans within a time window.
  - Scans with missing retention time are treated as ineligible when any RT filter is present.
  - Precursor inclusion can still add scans outside the requested RT window.
- `--rt-window-percent FLOAT`:
  - Chooses a random contiguous retention-time window whose width is the given percentage of the eligible RT span.
  - Applied after fixed RT bounds and before non-RT filters or primary selection.
  - Can be combined with random selection, include-file selection, or used by itself.
  - The percentage refers to retention-time span, not percentage of scans.
  - Precursor inclusion can still add scans outside the chosen RT window.

Exclusion file:

- `--scan-exclude-file PATH`: file with one scan ID per line to exclude.
  - Excluded scans are removed from random candidate pools and from final output.
  - Can be combined with random selection or include-file selection.
  - Can be used by itself to produce \"all scans except excluded scans\" output.
  - If the same scan appears in both include and exclude files, the program exits with usage error.

MS-level filtering:

- `--ms-level TEXT`: comma-separated MS levels (e.g. `1`, `2`, `1,2`).
  - Valid only with random selection (`--scan-count` or `--scan-percent`).
  - Applies only to the initial random selection pool. Precursor inclusion can add MS levels not listed here.
  - Using `--ms-level` with `--scan-include-file` or exclude-only mode is a usage error.

Precursor inclusion:

- `--include-precursors / --no-include-precursors` (default: include)
  - When enabled, walks `precursor/@spectrumRef` chains and includes all referenced ancestors.
  - Broken `spectrumRef` values emit a warning to stderr and continue.
  - If no `spectrumRef` attributes exist in the file, this option has no effect.

Output format:

- `--indexed / --no-index`:
  - When omitted, the output format follows the source file.
  - `--indexed` adds an index (`indexList` and `indexListOffset`) to the end of the file.
  - `--no-index` omits those elements entirely.

Binary array compression:

- `--compression [source|zlib|none]` (default: `source`)
  - `source`: copies each spectrum's binary arrays without re-encoding.
  - `zlib`: decodes and re-encodes all spectrum arrays with zlib compression and updates CV terms.
  - `none`: decodes and re-encodes all spectrum arrays uncompressed and updates CV terms.
  - Recalculated TIC/BPC use this setting. Pass-through chromatograms retain their original encoding.

Reproducibility:

- `--seed INTEGER` (default: `42`): random seed used for `--scan-count` and `--scan-percent`.
  - Also used for `--rt-window-percent`.

Help:

- `--help` / `-h`: show usage and exit.
- `--version` / `-v`: show the installed release version, or a git-derived development version when available.

## Exit Codes

- `1`: invalid/unreadable input file.
- `2`: CLI usage/argument error (bad flag combinations).
- `3`: one or more explicit scans were not found.
- `4`: random selection request exceeds or has no eligible scans after filtering/exclusion.
  - Also used when any other filter/selection combination leaves zero scans selected.
- `5`: output path/write error.

## Installation

Install from PyPI:

```bash
python3 -m pip install miller-mzml-filterer
```

Verify the CLI is available:

```bash
miller --help
```

Example run after installing with `pip`:

```bash
miller --scan-count 50 input.mzML output.subset_50.mzML
```

### Installation (Local Dev)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Testing

```bash
.venv/bin/pytest --cov=miller --cov-report=term-missing tests/
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/
```

Smoke tests:

- `tests/test_smoke_real_data.py` uses `test_data/test_data.mzML`.
- These smoke tests run automatically with the rest of the suite in GitHub Actions because they live under `tests/`.
- Run only smoke tests locally:

```bash
.venv/bin/pytest tests/test_smoke_real_data.py
```

## Docker

Pull the published image for this GitHub project:

```bash
docker pull ghcr.io/mriffle/miller-mzml-filterer:latest
```

Run help:

```bash
docker run --rm ghcr.io/mriffle/miller-mzml-filterer:latest --help
```

Run the tool in the current directory, as your current user and group, with the current directory mounted at `/work`:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  -w /work \
  ghcr.io/mriffle/miller-mzml-filterer:latest \
  --scan-count 50 input.mzML output.subset_50.mzML
```

### Docker day-to-day usage (with mounts)

When running in Docker, you almost always want to mount a host directory containing mzML files into the container, and mount an output directory to receive the subset file.

Example host layout:

```text
/path/to/project/
  data/
    input.mzML
  subsets/
```

Run the tool against a mounted input file and write to a mounted output directory:

```bash
mkdir -p subsets
docker run --rm \
  -v "$PWD/data:/data:ro" \
  -v "$PWD/subsets:/out" \
  ghcr.io/mriffle/miller-mzml-filterer:latest \
  --scan-count 50 \
  /data/input.mzML /out/input.subset_50.mzML
```

If you want the output file to be owned by your host user (instead of root), run the container as you:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/data:/data:ro" \
  -v "$PWD/subsets:/out" \
  ghcr.io/mriffle/miller-mzml-filterer:latest \
  --ms-level 2 --scan-count 10 \
  /data/input.mzML /out/input.ms2_10_plus_precursors.mzML
```

Run tests inside the container:

```bash
docker run --rm --entrypoint pytest ghcr.io/mriffle/miller-mzml-filterer:latest \
  --cov=miller --cov-report=term-missing tests/
```

If you want to build the image locally during development instead of pulling it from GHCR:

```bash
docker build -t miller .
docker run --rm miller --help
```

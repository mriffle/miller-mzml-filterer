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

Exclude specific scans from random candidate pool (and final output):

```bash
cat > subsets/exclude_scans.txt <<'EOF'
1001
1002
EOF
miller --scan-count 50 --scan-exclude-file subsets/exclude_scans.txt data/input.mzML subsets/input.subset_50_excl.mzML
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

Selection mode (exactly one required):

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

Exclusion file:

- `--scan-exclude-file PATH`: file with one scan ID per line to exclude.
  - Excluded scans are removed from random candidate pools and from final output.
  - Can be combined with random selection or include-file selection.
  - If the same scan appears in both include and exclude files, the program exits with usage error.

MS-level filtering:

- `--ms-level TEXT`: comma-separated MS levels (e.g. `1`, `2`, `1,2`).
  - Valid only with random selection (`--scan-count` or `--scan-percent`).
  - Applies only to the initial random selection pool. Precursor inclusion can add MS levels not listed here.
  - Using `--ms-level` with `--scan-include-file` is a usage error.

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

Help:

- `--help` / `-h`: show usage and exit.

## Exit Codes

- `1`: invalid/unreadable input file.
- `2`: CLI usage/argument error (bad flag combinations).
- `3`: one or more explicit scans were not found.
- `4`: random selection request exceeds or has no eligible scans after filtering/exclusion.
- `5`: output path/write error.

## Installation (Local Dev)

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

Build:

```bash
docker build -t miller .
```

Run help:

```bash
docker run --rm miller --help
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
  miller \
  --scan-count 50 \
  /data/input.mzML /out/input.subset_50.mzML
```

If you want the output file to be owned by your host user (instead of root), run the container as you:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/data:/data:ro" \
  -v "$PWD/subsets:/out" \
  miller \
  --ms-level 2 --scan-count 10 \
  /data/input.mzML /out/input.ms2_10_plus_precursors.mzML
```

Run tests inside the container:

```bash
docker run --rm --entrypoint pytest miller \
  --cov=miller --cov-report=term-missing tests/
```

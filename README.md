# Miller

Miller generates small, representative mzML files from full-sized proteomics mzML datasets. Production mzML files are often hundreds of megabytes or several gigabytes — too large to bundle in repositories, share casually, or iterate on quickly. Miller solves this by extracting a configurable subset of spectra into a new, fully valid mzML file that preserves the structure and metadata of the original.

Miller works with both **DDA** and **DIA** data and is useful in a variety of scenarios:

- **Smoke-testing data analysis pipelines** — generate tiny mzML files to verify that a workflow runs end-to-end before committing to a full-scale run.
- **CI and integration tests** — ship realistic test fixtures without multi-GB raw data.
- **Filtering step in a larger workflow** — use Miller as a pre-processing stage, for example to trim mzML files in a cascade search or to focus on a retention-time window of interest.

### Highlights

- Include or exclude scans based on scan number or retention-time range.
- Operate on specific MS levels (e.g. MS1, MS2).
- **Precursor inclusion** (default on) — if an MSn scan references a precursor via `spectrumRef`, the full precursor chain is included automatically.
- Preserves run-level sections and metadata; updates `spectrumList/@count` and renumbers spectrum `index` attributes so the output is a valid, random-access-safe indexed mzML (works with index-based readers such as MSFTBX / PDV / FragPipe).
- Recalculates TIC (`MS:1000235`) and BPC (`MS:1000628`) from retained spectra when present.
- Indexed or non-indexed mzML output, defaulting to the source unless overridden.
- Binary array compression control: `source`, `zlib`, or `none`.

## Installation

### pip (recommended)

```bash
pip install miller-mzml-filterer
```

Verify:

```bash
miller --help
```

### Docker

```bash
docker pull ghcr.io/mriffle/miller-mzml-filterer:latest
```

Verify:

```bash
docker run --rm ghcr.io/mriffle/miller-mzml-filterer:latest --help
```

## Quick Start

### Using pip

Randomly select 50 scans:

```bash
miller --scan-count 50 input.mzML output.mzML
```

Randomly select 5% of scans:

```bash
miller --scan-percent 5 input.mzML output.mzML
```

Select 10 random MS2 scans (precursor MS1 scans are included automatically):

```bash
miller --ms-level 2 --scan-count 10 input.mzML output.mzML
```

Keep scans in a retention-time window:

```bash
miller --rt-range-start 35.2 --rt-range-end 35.8 input.mzML output.mzML
```

Select specific scans from an include file (one scan ID per line):

```bash
miller --scan-include-file scans.txt input.mzML output.mzML
```

### Using Docker

All Docker examples below mount the current directory into the container and run as your current user/group so output files have the correct ownership:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  -w /work \
  ghcr.io/mriffle/miller-mzml-filterer:latest \
  --scan-count 50 input.mzML output.mzML
```

Select 5% of scans:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  -w /work \
  ghcr.io/mriffle/miller-mzml-filterer:latest \
  --scan-percent 5 input.mzML output.mzML
```

Select 10 random MS2 scans:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  -w /work \
  ghcr.io/mriffle/miller-mzml-filterer:latest \
  --ms-level 2 --scan-count 10 input.mzML output.mzML
```

## More Examples

### Retention-time filtering

Combine an RT window with random selection:

```bash
miller --rt-range-start 35.2 --rt-range-end 35.8 --scan-count 50 input.mzML output.mzML
```

Pick a random contiguous 10% RT window, then select 25 scans from it:

```bash
miller --rt-window-percent 10 --scan-count 25 input.mzML output.mzML
```

### Excluding scans

Exclude specific scans by ID (one per line in the file):

```bash
miller --scan-count 50 --scan-exclude-file exclude.txt input.mzML output.mzML
```

Keep all scans *except* the excluded ones:

```bash
miller --scan-exclude-file exclude.txt input.mzML output.mzML
```

### Output format and compression

Force indexed output with zlib compression:

```bash
miller --indexed --compression zlib --scan-count 10 input.mzML output.mzML
```

Non-indexed, uncompressed:

```bash
miller --no-index --compression none --scan-count 10 input.mzML output.mzML
```

### Precursor inclusion

By default, Miller follows `spectrumRef` links to include precursor scans (e.g. MS1 parents of selected MS2 scans). Disable this with:

```bash
miller --no-include-precursors --scan-count 10 input.mzML output.mzML
```

### Determinism

Random selection is seeded (default `42`). Vary the seed for different subsets of the same file:

```bash
miller --scan-count 50 --seed 1 input.mzML output_seed1.mzML
miller --scan-count 50 --seed 2 input.mzML output_seed2.mzML
```

---

## CLI Reference

```text
miller [OPTIONS] INPUT OUTPUT
```

### Positional arguments

- **`INPUT`** — path to the source mzML file (indexed or non-indexed).
- **`OUTPUT`** — path for the output mzML file.

### Selection mode (mutually exclusive)

- **`--scan-count INTEGER`** — randomly select N scans from the eligible pool. Fails if N exceeds pool size.
- **`--scan-percent FLOAT`** — randomly select a percentage (> 0, ≤ 100) of eligible scans.
- **`--scan-include-file PATH`** — file with one scan ID per line. Accepts bare numbers (`1001`) or prefixed IDs (`scan=1001`).
- If none of the above are given and `--scan-exclude-file` is set, all scans minus exclusions are kept.

### Filtering

- **`--rt-range-start FLOAT`** / **`--rt-range-end FLOAT`** — inclusive RT bounds applied before selection. Either or both may be supplied.
- **`--rt-window-percent FLOAT`** — random contiguous RT window (percentage of eligible RT span), applied after fixed RT bounds.
- **`--scan-exclude-file PATH`** — one scan ID per line to exclude from selection and final output.
- **`--ms-level TEXT`** — comma-separated MS levels (e.g. `1`, `2`, `1,2`). Valid only with `--scan-count` or `--scan-percent`.

### Precursor inclusion

- **`--include-precursors / --no-include-precursors`** (default: include) — walk `spectrumRef` chains to include ancestor scans.

### Output format

- **`--indexed / --no-index`** — force indexed or non-indexed output. Default follows the source file.
- **`--compression [source|zlib|none]`** (default: `source`) — binary array compression mode.

### Other

- **`--seed INTEGER`** (default: `42`) — random seed for `--scan-count`, `--scan-percent`, and `--rt-window-percent`.
- **`--help / -h`** — show usage and exit.
- **`--version / -v`** — show version and exit.

### Exit codes

| Code | Meaning |
|------|---------|
| 1 | Invalid or unreadable input file |
| 2 | CLI usage / argument error |
| 3 | One or more explicit scan IDs not found |
| 4 | Selection produced zero eligible scans |
| 5 | Output path / write error |

---

## Development

### Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

### Running tests

```bash
.venv/bin/pytest --cov=miller --cov-report=term-missing tests/
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/
```

Smoke tests use `test_data/test_data.mzML` and run automatically with the full suite. To run only smoke tests:

```bash
.venv/bin/pytest tests/test_smoke_real_data.py
```

### Building the Docker image locally

```bash
docker build -t miller .
docker run --rm miller --help
```

### Running tests inside Docker

```bash
docker run --rm --entrypoint pytest ghcr.io/mriffle/miller-mzml-filterer:latest \
  --cov=miller --cov-report=term-missing tests/
```

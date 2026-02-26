# Miller — mzML Test Data Generator Specification

Version: 1.1  
Status: Draft  
Date: 2026-02-24

## 1. Overview

### 1.1 Purpose

Miller is a command-line tool to generate small, representative mzML files from full-sized proteomics datasets. The output files are intended as smoke-test fixtures for CI pipelines, integration tests, and development workflows.

### 1.2 Problem Statement

Production mzML files are often hundreds of MB to multiple GB. Automated workflows need realistic inputs without full production volume. Manually curated fixtures are brittle and expensive to maintain.

### 1.3 Design Goals

- Fidelity: preserve source mzML structure and metadata, changing only selected spectra/chromatograms as required.
- Determinism: identical input + flags produce identical output.
- Simplicity: one CLI entrypoint with clear options.
- Correctness over performance: prioritize robust behavior and testability.

## 2. Functional Requirements

### 2.1 Inputs

- Required positional args:
  - `input`: source mzML path.
  - `output`: output mzML path.
- Exactly one selection mode:
  - `--scan-count N`
  - `--scan-percent P`
  - `--scan-include-file PATH` (one scan ID per line, no header)
- Optional:
  - `--scan-exclude-file PATH` (one scan ID per line, no header)
  - `--ms-level L1,L2,...` (valid only with random mode: `--scan-count`/`--scan-percent`)
  - `--include-precursors / --no-include-precursors` (default enabled)
  - `--indexed / --no-index` (default follows source)
  - `--compression source|zlib|none` (default `source`)
  - `--seed` (default `42`)

### 2.2 Selection Rules

- Random mode:
  - If `--ms-level` is set, filter eligible pool first.
  - If `--scan-exclude-file` is set, remove excluded scans from eligible pool before selection.
  - Choose `N` uniformly at random from eligible scans.
  - Or choose `P%` from eligible scans when `--scan-percent` is used.
  - Output order always follows source order.
  - If requested random selection cannot be satisfied from eligible scans, fail with descriptive error.
- Explicit mode:
  - Read included scan IDs from include file (`--scan-include-file`).
  - Accept bare numbers (`1001`) or prefixed IDs (`scan=1001`) in file lines.
  - Fail with all missing IDs listed if any are absent.
  - Output order follows source order.
  - If both include and exclude files are provided, both are honored.
  - If any scan ID appears in both include and exclude files, fail with usage error.

### 2.3 Precursor Inclusion

When enabled:

1. Start from initially selected scans.
2. Follow precursor `spectrumRef` links to include parents.
3. Walk recursively (MS3 -> MS2 -> MS1 chains).
4. Deduplicate while preserving source order.
5. Warn (stderr) and continue for broken references.

When disabled:

- Include only directly selected scans.

### 2.4 Output Requirements

- Emit valid mzML parseable by compliant readers.
- Preserve metadata sections under `<mzML>` and `<run>` except for modified spectrum/chromatogram content.
- Update `spectrumList/@count` to final included spectrum count.
- Recalculate TIC/BPC if present; pass through other chromatograms.
- Support indexed and non-indexed output.
- Apply selected compression behavior.

### 2.5 Compression

- `source`: preserve original per-array encoding.
- `zlib`: re-encode all spectrum arrays to zlib and update CV terms.
- `none`: re-encode all spectrum arrays uncompressed and update CV terms.
- Recalculated TIC/BPC follow requested compression mode.
- Non-TIC/BPC pass-through chromatograms retain original encoding.

### 2.6 Chromatograms

- TIC (`MS:1000235`): intensity is sum of spectrum intensity array per retained spectrum.
- BPC (`MS:1000628`): intensity is max of spectrum intensity array per retained spectrum.
- Time array uses retained spectra retention times in source order.
- Update `defaultArrayLength` to number of retained spectra.
- Do not synthesize TIC/BPC if absent from source.
- Pass through non-TIC/BPC chromatograms unchanged.

### 2.7 Exit Codes and Errors

- `1`: invalid/unreadable input.
- `2`: CLI usage errors (flag incompatibility, missing mode, etc.).
- `3`: explicit scan IDs missing.
- `4`: random selection exceeds or has no eligible pool after filtering/exclusion.
- `5`: output not writable/write failure.

All errors go to stderr. Successful execution is silent.

## 3. Technical Design

### 3.1 Language and Dependencies

- Python >= 3.10
- Runtime deps:
  - `click`
  - `pyteomics`
  - `lxml`
  - `numpy`
- Dev deps:
  - `pytest`
  - `pytest-cov`
  - `ruff`
  - `mypy`

### 3.2 Module Structure

- `src/miller/cli.py`
- `src/miller/reader.py`
- `src/miller/selector.py`
- `src/miller/chromatogram.py`
- `src/miller/writer.py`
- `src/miller/validation.py`
- `src/miller/codec.py`
- `src/miller/errors.py`
- `src/miller/models.py`

### 3.3 CLI

Usage:

```text
miller [OPTIONS] INPUT OUTPUT
```

## 4. Testing Strategy

Required layers:

- Unit tests:
  - selection
  - validation
  - reader
  - codec/chromatogram
  - writer
- CLI integration tests for exit codes and feature combinations.
- Roundtrip/fidelity tests for retained spectra and chromatograms.
- Fixture generation script checked into repository.

Coverage goals:

- >= 90% total line coverage.
- 100% branch coverage for selector/validation logic.

## 5. Docker

Base image: `python:3.12-slim`  
Container entrypoint: `miller`

Expected usage:

```bash
docker build -t miller .
docker run --rm -v "$PWD/data:/data:ro" -v "$PWD/subsets:/out" miller --scan-count 50 /data/input.mzML /out/output.mzML
```

## 6. CI/CD

CI (`ci.yml`):

- Trigger: pushes + PRs.
- Matrix test across Python 3.10/3.11/3.12.
- Run lint, type-check, tests with coverage gates.
- Upload coverage artifacts.
- Validate Docker build and container test/help behavior.

Release (`release.yml`):

- Trigger: `v*.*.*` tags.
- Run same validation as CI.
- Build sdist/wheel.
- Build and push versioned Docker image to GHCR.
- Attach Python artifacts to GitHub release.

# Mouse Arena

Optimized Python port of the MATLAB Tariq et al. (2020) Mouse Arena reconstruction
pipeline, validated against golden fixtures captured from a MATLAB reference run.

## Layout

- `Optimized Python/` - the package, its test suite, and benchmarks:
  - `mouse_arena/` - the pipeline package (config, io, kernels, deconvolution,
    detection, tracking, lighting, metadata, figures, etc.)
  - `harness/` - the differential-test engine (fixture loader + tolerance comparator)
  - `tests/` - one pytest module per fixture stage
  - `benchmarks/` - performance benchmarks
- `Golden Fixtures/` - MATLAB-derived golden fixtures used to validate the Python
  port. Per-stage test cases live under a nested `fixtures/` subdirectory, e.g.
  `Golden Fixtures/fixtures/00_params/`, `01_loader/`, ... `09_sensor_char/`.
  Not tracked by Git (see below).

## Running the tests

From `Optimized Python/`:

    python -m pytest tests/ -q

The test harness auto-discovers the fixtures at `../Golden Fixtures/fixtures`
relative to the repo root, no environment variable is required. To point at a
fixtures tree in a different location, set MA_FIXTURES:

    MA_FIXTURES="/path/to/fixtures" python -m pytest tests/ -q

## Git / porting note

`Golden Fixtures/` is excluded from Git via `.gitignore`. The fixture files are
large binary MATLAB data (some individual files are 230-260 MB), which exceeds
GitHub's 100 MB per-file limit, so only the code in `Optimized Python/` is
pushed to the repository. When setting up this project on a new machine, copy
`Golden Fixtures/` over separately (zip, external drive, rsync, etc.) - see
Repos/Guides for the recommended process.

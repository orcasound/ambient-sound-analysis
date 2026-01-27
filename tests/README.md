## Tests

This directory contains the project’s automated tests and test fixtures.

### Quick start

From the repo root:

```bash
python -m pytest -q
```

If you only want the pipeline tests:

```bash
python -m pytest -q tests/test_pipeline.py
```

### Prerequisites

- **Python environment**: run tests inside the same environment that has the project dependencies installed.
- **pytest**: required to run tests.
- **librosa**: required for PSD/broadband computation tests.
- **ffmpeg**: required for `.ts -> .wav` conversion tests and for generating golden fixtures.

For a conda workflow (example):

```bash
conda activate orca_env
python -m pip install -r requirements.txt
python -m pip install pytest pytest-asyncio
python -m pytest -q
```

### `src/` layout and `conftest.py`

This repo uses a `src/` layout. `tests/conftest.py` adds `<repo>/src` to `sys.path` so imports like
`orcasound_noise...` work when running tests without requiring an editable install.

### Golden fixtures

We use **golden-file regression tests** to ensure that pipeline outputs remain stable across refactors
and dependency/Python upgrades.

- **Location**: `tests/golden/`
- **Naming**: `{stem}__{config}__psd.pkl` and `{stem}__{config}__bb.pkl`
  - Example: `live000__60s_100hz__psd.pkl`

Golden fixtures are generated from the local `.ts` samples in `test_files/` using `ffmpeg`, and then
processed via `NoiseAnalysisPipeline.process_wav_file(...)`.

#### Regenerate golden fixtures

From the repo root:

```bash
python -m tests.generate_test_data
```

If a test fails after an intentional algorithm change, regenerate and commit updated fixtures with a
clear explanation in the PR/commit message.

### Tests included

- **`test_pipeline.py`**
  - Pipeline initialization sanity checks
  - Local `.wav` processing smoke test
  - `.ts -> .wav -> PSD` golden regression tests (requires `ffmpeg`)
- **`test_FileConnector.py`**
  - Filename formatting/parsing for S3 parquet outputs


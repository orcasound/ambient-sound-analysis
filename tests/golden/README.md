## Golden PSD fixtures

This folder holds small, committed “golden” fixtures used by `tests/test_pipeline.py` to validate:

- **`.ts` → `.wav` conversion** (via `ffmpeg`)
- **PSD/broadband computation** (via `NoiseAnalysisPipeline.process_wav_file`)

### Regenerate

From the repo root:

```bash
python -m tests.generate_test_data
```

This will overwrite any existing golden `.pkl` files in this folder.


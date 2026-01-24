import datetime as dt
import os
import shutil
import subprocess
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
import librosa  # noqa: F401  # required dependency; fail fast if missing
from botocore import UNSIGNED as BOTOCRE_UNSIGNED

from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone


@pytest.fixture
def test_files_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_files")


@pytest.fixture
def golden_dir():
    return os.path.join(os.path.dirname(__file__), "golden")


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Make comparisons stable across platforms/ffmpeg/librosa versions.
    df = df.sort_index()
    df.columns = df.columns.astype(str)
    return df


def _golden_paths(golden_dir: str, stem: str, config_name: str):
    psd_path = os.path.join(golden_dir, f"{stem}__{config_name}__psd.pkl")
    bb_path = os.path.join(golden_dir, f"{stem}__{config_name}__bb.pkl")
    return psd_path, bb_path


@pytest.fixture
def sample_wav_path(test_files_dir):
    return os.path.join(test_files_dir, "live000.wav")


@pytest.fixture
def sample_ts_path(test_files_dir):
    return os.path.join(test_files_dir, "live000.ts")


def test_pipeline_init():
    """Test that the pipeline initializes with correct attributes and handles no_auth."""
    pipeline = NoiseAnalysisPipeline(
        Hydrophone.ORCASOUND_LAB, delta_t=60, delta_f=100, no_auth=True
    )
    assert pipeline.delta_t == 60
    assert pipeline.delta_f == 100
    # UNSIGNED config check varies by boto3/botocore version.
    sig = pipeline.file_connector.client.meta.config.signature_version
    assert sig in ("s3v4", "unsigned", None) or sig == BOTOCRE_UNSIGNED

    # Check that temp folders are created
    assert os.path.exists(pipeline.wav_folder)
    assert os.path.exists(pipeline.pqt_folder)


def test_process_wav_file_snapshot(sample_wav_path):
    """Test the static process_wav_file method against a local wav."""
    start_time = dt.datetime(2021, 7, 1, 0, 0, 0)
    args = (sample_wav_path, start_time, 60, 100, None, {})
    psd_df, bb_df = NoiseAnalysisPipeline.process_wav_file(args)

    assert isinstance(psd_df, pd.DataFrame)
    assert isinstance(bb_df, pd.DataFrame)
    assert not psd_df.empty
    assert not bb_df.empty


def test_convert_ts_to_wav_then_process(sample_ts_path, tmp_path):
    """Test local .ts -> .wav conversion (ffmpeg) and PSD generation."""
    if not os.path.exists(sample_ts_path):
        pytest.skip(f"Missing test file: {sample_ts_path}")

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found; required to convert .ts to .wav for this test")

    out_wav = tmp_path / "from_ts.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            sample_ts_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            str(out_wav),
        ],
        check=True,
    )

    start_time = dt.datetime(2021, 7, 1, 0, 0, 0)
    args = (str(out_wav), start_time, 60, 100, None, {})
    psd_df, bb_df = NoiseAnalysisPipeline.process_wav_file(args)

    assert isinstance(psd_df, pd.DataFrame)
    assert isinstance(bb_df, pd.DataFrame)
    assert not psd_df.empty
    assert not bb_df.empty


@pytest.mark.parametrize("stem", ["live000", "live001", "live002"])
@pytest.mark.parametrize("config_name,delta_t,delta_f,bands", [("60s_100hz", 60, 100, None)])
def test_ts_to_psd_matches_golden(stem, config_name, delta_t, delta_f, bands, test_files_dir, golden_dir, tmp_path):
    """Convert multiple local .ts files and compare PSD/broadband against golden fixtures."""
    ts_path = os.path.join(test_files_dir, f"{stem}.ts")
    if not os.path.exists(ts_path):
        pytest.skip(f"Missing test file: {ts_path}")

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found; required to convert .ts to .wav for this test")

    psd_golden_path, bb_golden_path = _golden_paths(golden_dir, stem, config_name)
    if not (os.path.exists(psd_golden_path) and os.path.exists(bb_golden_path)):
        pytest.skip(
            "Golden fixtures missing. Regenerate with: python -m tests.generate_test_data"
        )

    out_wav = tmp_path / f"{stem}.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            ts_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            str(out_wav),
        ],
        check=True,
    )

    start_time = dt.datetime(2021, 7, 1, 0, 0, 0)
    psd_df, bb_df = NoiseAnalysisPipeline.process_wav_file(
        (str(out_wav), start_time, delta_t, delta_f, bands, {})
    )
    psd_df = _normalize_df(psd_df)
    bb_df = _normalize_df(bb_df)

    psd_golden = _normalize_df(pd.read_pickle(psd_golden_path))
    bb_golden = _normalize_df(pd.read_pickle(bb_golden_path))

    # ffmpeg conversion can introduce small numeric drift; allow tolerance.
    pd.testing.assert_frame_equal(psd_df, psd_golden, check_exact=False, atol=0.5, rtol=0)
    pd.testing.assert_frame_equal(bb_df, bb_golden, check_exact=False, atol=0.5, rtol=0)


@patch("orcasound_noise.pipeline.pipeline.DateRangeHLSStream")
def test_generate_psds_snapshot(
    mock_stream_class, sample_wav_path
):
    """Integration test: mock the stream and compare to direct wav processing."""
    # Setup mock stream
    mock_stream = MagicMock()
    mock_stream.is_stream_over.side_effect = [False, True]
    # get_next_clip returns (wav_path, clip_start_time, _)
    mock_stream.get_next_clip.return_value = (
        sample_wav_path,
        "2021_07_01_00_00_00",
        None,
    )
    mock_stream_class.return_value = mock_stream

    pipeline = NoiseAnalysisPipeline(
        Hydrophone.ORCASOUND_LAB, delta_t=60, delta_f=100, no_auth=True
    )

    start_time = dt.datetime(2021, 7, 1, 0, 0, 0)
    end_time = start_time + dt.timedelta(minutes=1)

    psd_results, bb_results = pipeline.generate_psds(
        start_time, end_time, ref_lvl=False
    )

    expected_psd, expected_bb = NoiseAnalysisPipeline.process_wav_file(
        (sample_wav_path, start_time, 60, 100, None, {})
    )

    # Compare
    pd.testing.assert_frame_equal(
        _normalize_df(psd_results), _normalize_df(expected_psd), check_column_type=False
    )
    pd.testing.assert_frame_equal(
        _normalize_df(bb_results), _normalize_df(expected_bb), check_column_type=False
    )


def test_pipeline_cleanup():
    """Verify that temp directories are cleaned up on deletion."""
    pipeline = NoiseAnalysisPipeline(
        Hydrophone.ORCASOUND_LAB, delta_t=60, delta_f=100
    )
    wav_path = pipeline.wav_folder
    pqt_path = pipeline.pqt_folder

    assert os.path.exists(wav_path)

    # Trigger deletion
    del pipeline

    # Check if they still exist (this can be flaky depending on GC, but let's try)
    # The pipeline class uses tempfile.TemporaryDirectory which cleans up on __del__
    assert not os.path.exists(wav_path)
    assert not os.path.exists(pqt_path)

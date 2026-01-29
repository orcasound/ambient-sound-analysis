import datetime as dt
import os
import sys
import subprocess
import tempfile

# Allow running this script without installing the package.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

try:
    from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
except ModuleNotFoundError as e:
    print("ERROR: Failed to import project dependencies.")
    print(f"Details: {e}")
    print()
    print("Try one of:")
    print("- pip install -r requirements.txt")
    print("- pip install -e .")
    sys.exit(1)


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _normalize_df(df):
    df = df.sort_index()
    df.columns = df.columns.astype(str)
    return df


def _golden_paths(golden_dir, stem, config_name):
    psd_out = os.path.join(golden_dir, f"{stem}__{config_name}__psd.pkl")
    bb_out = os.path.join(golden_dir, f"{stem}__{config_name}__bb.pkl")
    return psd_out, bb_out


def generate():
    # Setup paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(current_dir)
    test_files_dir = os.path.join(repo_root, "test_files")
    golden_dir = os.path.join(current_dir, "golden")
    os.makedirs(golden_dir, exist_ok=True)

    print(f"Writing golden fixtures to: {golden_dir}")

    if not check_ffmpeg():
        print("ERROR: ffmpeg not found. It is required to generate golden fixtures from .ts.")
        print("Install it (e.g. conda install -c conda-forge ffmpeg) and retry.")
        sys.exit(1)

    start_time = dt.datetime(2021, 7, 1, 0, 0, 0)
    stems = ["live000", "live001", "live002"]
    configs = [
        # Matches the existing pipeline/tests: 60s samples, linear 100hz bins.
        {"name": "60s_100hz", "delta_t": 60, "delta_f": 100, "bands": None},
        # A second useful configuration: fractional octave bands (coarser, but common for acoustics).
        {"name": "60s_3oct", "delta_t": 60, "delta_f": 100, "bands": 3},
    ]

    try:
        with tempfile.TemporaryDirectory() as td:
            for stem in stems:
                ts_path = os.path.join(test_files_dir, f"{stem}.ts")
                if not os.path.exists(ts_path):
                    print(f"ERROR: missing test ts: {ts_path}")
                    sys.exit(1)

                wav_path = os.path.join(td, f"{stem}.wav")
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
                        wav_path,
                    ],
                    check=True,
                )

                for cfg in configs:
                    print(f"Generating {stem} ({cfg['name']}) from .ts ...")
                    args = (
                        wav_path,
                        start_time,
                        cfg["delta_t"],
                        cfg["delta_f"],
                        cfg["bands"],
                        {},
                    )
                    psd_df, bb_df = NoiseAnalysisPipeline.process_wav_file(args)
                    if psd_df is None or bb_df is None:
                        raise RuntimeError(
                            f"No PSD/broadband data generated from {ts_path} ({cfg['name']})."
                        )

                    psd_df = _normalize_df(psd_df)
                    bb_df = _normalize_df(bb_df)

                    psd_out, bb_out = _golden_paths(golden_dir, stem, cfg["name"])
                    psd_df.to_pickle(psd_out)
                    bb_df.to_pickle(bb_out)

                    print(f"Wrote golden: {os.path.basename(psd_out)}")
                    print(f"Wrote golden: {os.path.basename(bb_out)}")

        print("SUCCESS: Generated golden PSD fixtures from local .ts files.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    generate()

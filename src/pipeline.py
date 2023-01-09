# Native imports
import datetime as dt
import time

# Third part imports
import numpy as np
from scipy import signal
from scipy.io import wavfile

# Local imports
from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream


def ts_to_spectrogram(start_date: dt.date, end_date: dt.date, wav_folder, max_files=5):
    """
    Pull ts files from aws and create spectrograms of them by converting to wav files.

    * start_date: First date to pull files for
    * end_date: Last date to collect files for
    * wav_folder: folder path to store wav files in
    * max_files: Maximum number of wav files to generate. Use to help limit compute and egress whiel testing.

    # Return

    List of spectrograms, one per wav file generated

    """

    stream = DateRangeHLSStream(
        'https://s3-us-west-2.amazonaws.com/streaming-orcasound-net/rpi_orcasound_lab',
        60,
        time.mktime(start_date.timetuple()),
        time.mktime(end_date.timetuple()),
        wav_folder
    )

    result = []
    while len(result) <= max_files and not stream.is_stream_over():
        wav_file_path, clip_start_time, current_clip_name = stream.get_next_clip()
        print(clip_start_time)
        frequencies, times, spectrogram = create_spectogram(wav_file_path)
        result.append(spectrogram)

    return result


def create_spectogram(file, segs_per_sec=None):
    """
    Create a spectrogram from a wav file.

    * file: File handle or path of wav file
    * segs_per_sec: Number of bins per second to calculate. Leave None to create maximum granularity

    # Return

    Tuple of frequencies, times, spectrogram
    """
    wav_sample_rate, samples = wavfile.read(file)
    nperseg = None if not segs_per_sec else int(wav_sample_rate / segs_per_sec)

    # Average channels if more than 1
    if len(samples.shape) > 1 and samples.shape[1] > 1:
        samples = np.mean(samples, axis=1)

    frequencies, times, spectrogram = signal.spectrogram(samples, fs=wav_sample_rate, nperseg=nperseg)
    return frequencies, times, spectrogram




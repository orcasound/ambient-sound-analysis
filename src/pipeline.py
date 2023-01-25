# Native imports
import datetime as dt
import time

# Third part imports
import numpy as np
from scipy import signal
from scipy.io import wavfile

# Local imports
from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream
from util import wav_to_array

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
        frequencies, times, spectrogram = create_spectogram(wav_file_path)
        result.append(spectrogram)

    return result


def ts_to_array(start_date: dt.date, end_date: dt.date, wav_folder, max_files=6, overwrite_output=False, **kwargs):
    """
    Pull ts files from aws and create PSD arrays of them by converting to wav files.

    * start_date: First date to pull files for
    * end_date: Last date to collect files for
    * wav_folder: folder path to store wav files in
    * max_files: Maximum number of wav files to generate. Use to help limit compute and egress whiel testing.
    * overwrite_output: Automatically overwrite existing wav files. If False, will prompt before overwriting
    * kwargs: Other keyword args are passed to wav_to_array

    # Return

    List of PSDs, one per wav file generated

    """

    stream = DateRangeHLSStream(
        'https://s3-us-west-2.amazonaws.com/streaming-orcasound-net/rpi_orcasound_lab',
        60,
        time.mktime(start_date.timetuple()),
        time.mktime(end_date.timetuple()),
        wav_folder,
        overwrite_output
    )

    result = []
    while len(result) < max_files and not stream.is_stream_over():
        wav_file_path, clip_start_time, current_clip_name = stream.get_next_clip()
        if wav_file_path is not None:
            df = wav_to_array(wav_file_path, **kwargs)
            result.append(df)

    return result



def create_spectogram(file):
    """
    Create a spectrogram from a wav file.

    * file: File handle or path of wav file
    * sample_rate: Rate in samples per second. Leave as none to use the sample rate of the wav file

    # Return

    Tuple of frequencies, times, spectrogram
    """
    sample_rate, samples = wavfile.read(file)

    # Average channels if more than 1
    if len(samples.shape) > 1 and samples.shape[1] > 1:
        samples = np.mean(samples, axis=1)

    frequencies, times, spectrogram = signal.spectrogram(samples, sample_rate)
    return frequencies, times, spectrogram

# Native imports
import datetime as dt
import os
import tempfile
import time

# Third part imports
import numpy as np
import pandas as pd
from scipy import signal
from scipy.io import wavfile

# Local imports
from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream
from .acoustic_util import wav_to_array
from .hydrophone import Hydrophone
from .file_connector import S3FileConnector

class NoiseAnalysisPipeline:

    def __init__(self, hydrophone: Hydrophone, wav_folder=None, pqt_folder=None):
        """
        Pipeline object for generating rolled-up PDS parquet files. 

        * hydrophone: Hydrophone enum that contains all conenction info to S3 buccket.
        * wav_folder: Local folder to store wav files in. Defaults to Temporary Directory
        * pqt_folder: Local folder to store pqt files in. Defaults to Temporary Directory
        """

        # Conenctions
        self.hydrophone = hydrophone.value
        self.file_connector = S3FileConnector(hydrophone)

        # Local storage
        if wav_folder:
            self.wav_folder = wav_folder
            self.wav_folder_td = None
        else:
            self.wav_folder_td = tempfile.TemporaryDirectory()
            self.wav_folder = self.wav_folder_td.name
        
        if pqt_folder:
            self.pqt_folder = pqt_folder
            self.pqt_folder_td = None
        else:
            self.pqt_folder_td = tempfile.TemporaryDirectory()
            self.pqt_folder = self.pqt_folder_td.name

    def __del__(self):
        """"
        Remove Temp Dirs on delete
        """

        try:
            self.wav_folder_td.cleanup()
        except AttributeError:
            pass
        try:
            self.pqt_folder_td.cleanup()
        except AttributeError:
            pass

    # TODO
    def get_data(hydrophone: str, target_date: dt.date, sec_per_sample=60, frequency_bands='octet', check_archive=True, if_missing='raise'):
        """
        Gets a days worth of pds data from target hydrophone.

        * hydrophone: String name of hydrophone. Names include [rpi-orcasound-lab, bush-point...]
        * target_date. Date to pull data for
        * sec_per_sample: The number of seconds per row of data. Default is one minute per sample.
        * frequency_bands: The bands of frequency in the result. CHoose from premade bands such as 'octet', 'thirds', 'octet-log' or enter an integer to specify the number of hz per band
        * check_archive: Flag for whether to look in the archive before generating this data. Defaults to True.
        * if_missing: Behavior to take if no archive data is available. Set to 'raise' to raise a lookupError for missing data, 'generate' to create a new pds with the specifications 
            if none exists, or 'ignore' to return an empty dataframe. Has no effect if chack_archive is set to False.

        # Return
        Dataframe representing one days worth of psd data at desired specs. Rows are timestamps, columns are frequency bands.
        
        """

        # TODO

    def generate_psds(self, start: dt.datetime, end: dt.datetime, max_files=6, overwrite_output=False, **kwargs):
        """
        Pull ts files from aws and create PSD arrays of them by converting to wav files.

        * start_date: First date to pull files for
        * end_date: Last date to collect files for
        * max_files: Maximum number of wav files to generate. Use to help limit compute and egress whiel testing.
        * overwrite_output: Automatically overwrite existing wav files. If False, will prompt before overwriting
        * kwargs: Other keyword args are passed to wav_to_array

        # Return

        List of PSDs, one per wav file generated

        """

        stream = DateRangeHLSStream(
            'https://s3-us-west-2.amazonaws.com/' + self.hydrophone.bucket + '/' + self.hydrophone.ref_folder,
            60,
            time.mktime(start.timetuple()),
            time.mktime(end.timetuple()),
            self.wav_folder,
            overwrite_output
        )

        result = []
        while len(result) < max_files and not stream.is_stream_over():
            wav_file_path, clip_start_time, current_clip_name = stream.get_next_clip()
            if wav_file_path is not None:
                df = wav_to_array(wav_file_path, **kwargs)
                result.append(df)

        return result

    def generate_parquet_file(self, start: dt.datetime, end: dt.datetime, pqt_folder_override=None, upload_to_s3=False):
        """
        Create a parquet file of the psd at the given daterange.

        * Start: datetime, start of data to poll
        * end: datetime, end of data to poll
        * pqt_folder_override: Overide the object level settings for where to save pqt files.
        * upload_to_s3: Boolean, set to true to upload file to S3 after saving
        """

        # Create datafame
        psds = self.generate_psds(start, end, overwrite_output=True)
        pds_frame = pd.concat(list(zip(*psds))[0])

        # Save file
        save_folder = pqt_folder_override or self.pqt_folder
        os.makedirs(save_folder, exist_ok=True)
        fileName = self.file_connector.create_filename(start, end, 1, '3rd-octet')
        filePath = os.path.join(save_folder, fileName)
        pds_frame.to_parquet(filePath)

        # Upload
        if upload_to_s3:
            self.file_connector.upload_file(filePath, start, end, 1, '3rd-octet')

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

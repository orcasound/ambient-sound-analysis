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

    def __init__(self, hydrophone: Hydrophone, delta_t, delta_f, bands=None, wav_folder=None, pqt_folder=None):
        """
        Pipeline object for generating rolled-up PDS parquet files. 

        * hydrophone: Hydrophone enum that contains all conenction info to S3 buccket.
        * wav_folder: Local folder to store wav files in. Defaults to Temporary Directory
        * pqt_folder: Local folder to store pqt files in. Defaults to Temporary Directory
        * delta_t: The number of seconds per sample
        * delta_f: Int, The number of hertz per band.
        * bands: int. default=None. If not None this value selects how many octave subdivisions the frequency spectrum should 
          be divided into, where each frequency step is 1/Nth of an octave with N=bands. Based on the ISO R series.
          Accepts values 1, 3, 6, 12, or 24.
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

        # Config
        self.delta_f = delta_f
        self.delta_t = delta_t
        self.bands = bands

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

    def generate_psds(self, start: dt.datetime, end: dt.datetime, max_files=None, polling_interval=600, overwrite_output=True, **kwargs):
        """
        Pull ts files from aws and create PSD arrays of them by converting to wav files.

        * start_date: First date to pull files for
        * end_date: Last date to collect files for
        * max_files: Maximum number of wav files to generate. Use to help limit compute and egress whiel testing.
        * polling_interval: Int, size in secconds of intermediate wav files to generate.
        * overwrite_output: Automatically overwrite existing wav files. If False, will prompt before overwriting
        * kwargs: Other keyword args are passed to wav_to_array

        # Return

        Tuple of lists. First is psds and second is broadbands. Each list has one entry per wav_file generated

        """

        stream = DateRangeHLSStream(
            'https://s3-us-west-2.amazonaws.com/' + self.hydrophone.bucket + '/' + self.hydrophone.ref_folder,
            polling_interval,
            time.mktime(start.timetuple()),
            time.mktime(end.timetuple()),
            self.wav_folder,
            overwrite_output
        )

        psd_result = []
        broadband_result = []
        while (max_files is None or (len(psd_result) < max_files)) and not stream.is_stream_over():
            wav_file_path, clip_start_time, _ = stream.get_next_clip()
            if clip_start_time is None:
                continue
            start_time = [int(x) for x in clip_start_time.split('_')]
            start_time = dt.datetime(*start_time)
            if wav_file_path is not None:
                dfs = wav_to_array(wav_file_path, t0=start_time, delta_t=self.delta_t, delta_f=self.delta_f, transforms=[],
                                   bands=self.bands, **kwargs)
                psd_result.append(dfs[0])
                broadband_result.append(dfs[1])

        return pd.concat(psd_result), pd.concat(broadband_result)

    def generate_parquet_file(self, start: dt.datetime, end: dt.datetime, pqt_folder_override=None, upload_to_s3=False):
        """
        Create a parquet file of the psd at the given daterange.

        * Start: datetime, start of data to poll
        * end: datetime, end of data to poll
        * pqt_folder_override: Overide the object level settings for where to save pqt files.
        * upload_to_s3: Boolean, set to true to upload file to S3 after saving

        # Return
        Filepath of generated pqt file.
        """

        def generate_parquet_file(self, start: dt.datetime, end: dt.datetime, pqt_folder_override=None,
                                  upload_to_s3=False):
            """
            Create a parquet file of the psd at the given daterange.

            * Start: datetime, start of data to poll
            * end: datetime, end of data to poll
            * pqt_folder_override: Overide the object level settings for where to save pqt files.
            * upload_to_s3: Boolean, set to true to upload file to S3 after saving

            # Return
            Filepath of generated pqt file.
            """

            # Create datafame
            pds_frame, broadband_frame = self.generate_psds(start, end, overwrite_output=True)

            # Save file
            save_folder = pqt_folder_override or self.pqt_folder
            os.makedirs(save_folder, exist_ok=True)
            fileName = self.file_connector.create_filename(start, end, self.delta_t, self.delta_f,
                                                           octave_bands=self.bands)
            broadbandName = self.file_connector.create_filename(start, end, is_broadband=True)
            filePath = os.path.join(save_folder, fileName)
            broadbandFilePath = os.path.join(save_folder, broadbandName)
            pds_frame.columns = pds_frame.columns.astype(str)
            broadband_frame.columns = broadband_frame.columns.astype(str)
            pds_frame.to_parquet(filePath)
            broadband_frame.to_parquet(broadbandFilePath)

            # Upload
            if upload_to_s3:
                self.file_connector.upload_file(filePath, start, end, self.delta_t, self.delta_f,
                                                octave_bands=self.bands)
                self.file_connector.upload_file(broadbandFilePath, start, end, is_braodband=True)

            return filePath, broadbandFilePath

    def generate_parquet_file_batch(self, start: dt.datetime, num_files: int, file_length:dt.timedelta, **kwargs):
        """
            Generate a range of parquet files, starting at starttime with given length.

            Ex: To generate a weeks worth of data in 1-day sizes, call generate_parquet_file_batch(startDate, 7, timedelta(days=1))

            * start: Datetime, start of first file to generate
            * num_files: NUmber of files to generate
            * file_length: The length in time of each file.
            * kwargs: Other kwargs are passed to generate_parquet_file function

            # Return
            List of filepaths generated
        """

        file_paths = []
        for i in range(num_files):
            startTime = start + file_length*i
            endTime = startTime + file_length
            file_paths.append(self.generate_parquet_file(startTime, endTime, **kwargs))
        
        return file_paths

# Native imports
import datetime as dt
import os
import tempfile
import time
import logging
import random


# Third part imports
import numpy as np
import pandas as pd
from multiprocessing import Pool

# Local imports
#
# `orca_hls_utils` is an optional dependency when running purely local
# processing/tests. Import it lazily so importing this module does not fail
# in environments that haven't installed the git dependency yet.
try:
    from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream
except ModuleNotFoundError:  # pragma: no cover
    DateRangeHLSStream = None
from .acoustic_util import wav_to_array
from ..utils import Hydrophone
from ..utils.file_connector import S3FileConnector


class NoiseAnalysisPipeline:

    def __init__(self, hydrophone: Hydrophone, delta_t, delta_f, bands=None, wav_folder=None, pqt_folder=None,
                 no_auth=False, mode='safe'):
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
        * no_auth: Bool, default False. Set to True to allow anonymous downloads. Uploading is not available when True.
        """

        # Conenctions
        self.hydrophone = hydrophone.value
        self.file_connector = S3FileConnector(hydrophone, no_sign=no_auth)
        self.mode = mode

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
        # Calculate ref for hydrophone with generate_ref()
        self.ref = self.hydrophone.bb_ref

    def cleanup(self):
        """
        Cleanup any internally-created temporary directories.

        Note: If the caller provided `wav_folder`/`pqt_folder`, those directories
        are *not* owned by this class and will not be deleted.
        """
        # TemporaryDirectory.cleanup() is idempotent; guard for None/AttributeError.
        try:
            if self.wav_folder_td is not None:
                self.wav_folder_td.cleanup()
                self.wav_folder_td = None
        except AttributeError:
            pass
        try:
            if self.pqt_folder_td is not None:
                self.pqt_folder_td.cleanup()
                self.pqt_folder_td = None
        except AttributeError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        # Do not suppress exceptions.
        return False

    def __del__(self):
        """"
        Remove Temp Dirs on delete
        """
        self.cleanup()

    @staticmethod
    def process_wav_file(args):
        wav_file_path, start_time, delta_t, delta_f, bands, kwargs = args
        try:
            dfs = wav_to_array(wav_file_path, t0=start_time, delta_t=delta_t, delta_f=delta_f, transforms=[],
                               bands=bands, **kwargs)
            return dfs[0], dfs[1]
        except FileNotFoundError as fnf_error:
            logging.debug(f"{wav_file_path} clip failed to download: Error {fnf_error}")
            return None, None

    def generate_psds(self, start: dt.datetime, end: dt.datetime, max_files=None, polling_interval=600,
                      overwrite_output=True, ref_lvl=True, **kwargs):
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
        if DateRangeHLSStream is None:
            raise ModuleNotFoundError(
                "orca_hls_utils is required for HLS streaming (.ts -> .wav). "
                "Install project dependencies (e.g. `pip install -r requirements.txt`)."
            )
        # Set timezone, pipeline won't work on devices not set to PST
        os.environ['TZ'] = 'US/Pacific'
        time.tzset()

        # Creating the stream object
        stream = DateRangeHLSStream(
            'https://s3-us-west-2.amazonaws.com/' + self.hydrophone.bucket + '/' + self.hydrophone.ref_folder,
            polling_interval,
            time.mktime(start.timetuple()),
            time.mktime(end.timetuple()),
            self.wav_folder,
            overwrite_output
        )
        # Fast mode still in development, use safe mode for accurate results
        if self.mode == 'fast':
            tasks = []
            try:
                wav_file_paths_and_clip_start_times = stream.get_all_clips()
                print('#' * 5, "Finished Downloading .ts files", '#' * 5)

                wav_file_paths = wav_file_paths_and_clip_start_times[0]
                clip_start_time = wav_file_paths_and_clip_start_times[1]
                assert len(wav_file_paths) == len(clip_start_time)

                for i in range(len(wav_file_paths)):
                    start_time = [int(x) for x in clip_start_time[i].split('_')]
                    start_time = dt.datetime(*start_time)
                    tasks.append((wav_file_paths[i], start_time, self.delta_t, self.delta_f, self.bands, kwargs))

            except FileNotFoundError as fnf_error:
                logging.debug("%s clip failed to download: Error %s", clip_start_time, fnf_error)
                pass
            # Use a multiprocessing Pool
            print('#' * 5, "Using Multiprocessing for process_wav_file", '#' * 5)
            with Pool() as pool:
                results = pool.map(self.process_wav_file, tasks)
                # Filter out None results and concatenate
            psd_results = [r[0] for r in results if r[0] is not None]
            broadband_results = [r[1] for r in results if r[1] is not None]

            if len(psd_results) == 0:
                logging.warning(f"No data found for {start} to {end}")
                return None, None

            psd_results = pd.concat(psd_results).sort_index()
            broadband_results = pd.concat(broadband_results).sort_index()
            psd_results = psd_results[~psd_results.index.duplicated(keep='last')]
            broadband_results = broadband_results[~broadband_results.index.duplicated(keep='last')]

            if ref_lvl:
                broadband_results = broadband_results - self.ref

            return psd_results, broadband_results

        elif self.mode == 'safe':
            psd_results = []
            broadband_results = []
            while (max_files is None or (len(psd_results) < max_files)) and not stream.is_stream_over():
                try:
                    # Create .wav file with duration of polling_interval
                    wav_file_path, clip_start_time, _ = stream.get_next_clip()
                    if clip_start_time is None:
                        continue
                    start_time = [int(x) for x in clip_start_time.split('_')]
                    start_time = dt.datetime(*start_time)
                    if wav_file_path is not None:
                        # Convert the .wav file into PSD and broadband dataframes
                        dfs = wav_to_array(wav_file_path, t0=start_time, delta_t=self.delta_t, delta_f=self.delta_f,
                                           transforms=[], bands=self.bands, **kwargs)
                        # Add the PSD and broadband to list of dataframes
                        psd_results.append(dfs[0])
                        broadband_results.append(dfs[1])
                except FileNotFoundError as fnf_error:
                    logging.debug("%s clip failed to download: Error %s", clip_start_time, fnf_error)
                    pass

            if len(psd_results) == 0:
                logging.warning(f"No data found for {start} to {end}")
                return None, None

            # Concatenating the list of PSDs and broadband to get one PSD and one broadband
            psd_result = pd.concat(psd_results)
            del psd_results
            broadband_result = pd.concat(broadband_results)
            del broadband_results
            # Removing duplicates, occur sometimes at end of one dataframe and start of next
            psd_result = psd_result[~psd_result.index.duplicated(keep='last')]
            broadband_result = broadband_result[~broadband_result.index.duplicated(keep='last')]

            # Subtracting reference level from broadband
            if ref_lvl:
                broadband_result = broadband_result - self.ref

            return psd_result, broadband_result

        else:
            raise ValueError("Specify either 'safe' or 'fast' mode")

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

        # Create PSD and broadband Dataframes
        pds_frame, broadband_frame = self.generate_psds(start, end, overwrite_output=True)

        if pds_frame is None:
            return None, None

        # Save file locally
        save_folder = pqt_folder_override or self.pqt_folder
        os.makedirs(save_folder, exist_ok=True)
        fileName = self.file_connector.create_filename(start, end, self.delta_t, self.delta_f,
                                                       octave_bands=self.bands)
        broadbandName = self.file_connector.create_filename(start, end, self.delta_t, is_broadband=True)
        filePath = os.path.join(save_folder, fileName)
        broadbandFilePath = os.path.join(save_folder, broadbandName)
        pds_frame.columns = pds_frame.columns.astype(str)
        broadband_frame.columns = broadband_frame.columns.astype(str)
        pds_frame.to_parquet(filePath)
        broadband_frame.to_parquet(broadbandFilePath)

        # Upload to S3 bucket
        if upload_to_s3:
            self.file_connector.upload_file(filePath, start, end, self.delta_t, self.delta_f,
                                            octave_bands=self.bands)
            self.file_connector.upload_file(broadbandFilePath, start, end, self.delta_t, is_broadband=True)

        return filePath, broadbandFilePath

    def generate_parquet_file_batch(self, start: dt.datetime, num_files: int, file_length: dt.timedelta, **kwargs):
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
            startTime = start + file_length * i
            endTime = startTime + file_length
            file_paths.append(self.generate_parquet_file(startTime, endTime, **kwargs))

        return file_paths

    def process_ancient_ambient(self, ref_time: dt.datetime, dB=True):
        """
        Calculate the ancient ambient level for a given date and update the parquet file storing the
        ancient ambient values.  

        * ref_time: Datetime, date to use as the reference.
        * dB: Bool.  True if the data is already in decibel form. Default True. 
        
        """

        tmp_dir = tempfile.TemporaryDirectory()

        fc = self.file_connector
        start_time = ref_time - dt.timedelta(30)

        if dB:
            bb = False
            amb_band = self.bands
        else:
            bb = True
            amb_band = None
        files = fc.get_files(start=start_time, end=ref_time, secs_per_sample=self.delta_t,
                             hz_bands=amb_band, is_broadband=bb)

        pqs = []

        for file in files:
            tmp_file = tmp_dir.name + '/' + file.split('/')[-1]
            fc.download_file(file, tmp_file)
            pqs.append(pd.read_parquet(tmp_file, engine='pyarrow'))

        pq_out = pd.concat(pqs)

        mask = (pq_out.index >= start_time) & (pq_out.index < ref_time)
        df = pq_out.iloc[mask]

        aa = np.percentile(df, 5)

        out_df = pd.DataFrame(index=[ref_time], columns=['ancient_ambient'], data=[aa])

        if dB:
            filename = '/ancient_ambient_dB.parquet'
        else:
            filename = '/ancient_ambient.parquet'
        aa_filepath = tmp_dir.name + filename

        try:
            fc.download_file(self.hydrophone.save_folder + filename, aa_filepath)
            aa_df = pd.read_parquet(aa_filepath, engine='pyarrow')
            aa_df = pd.concat([aa_df, out_df])
        except:
            aa_df = out_df

        aa_pq = aa_df.to_parquet(aa_filepath, engine='pyarrow')

        file = open(aa_filepath, 'rb')
        fc.client.upload_fileobj(file, self.hydrophone.save_bucket, self.hydrophone.save_folder + filename)
        file.close()

    def get_ancient_ambient(self, date: dt.datetime, dB=True):
        """
        
        Return the ancient ambient level for a given date from the parquet file. 

        * date: Datetime, date of interest.
        * dB: Bool.  True if the data is already in decibel form. Default True. 

        """

        tmp_dir = tempfile.TemporaryDirectory()
        fc = self.file_connector

        if dB:
            filename = '/ancient_ambient_dB.parquet'
        else:
            filename = '/ancient_ambient.parquet'
        aa_filepath = tmp_dir.name + filename

        fc.download_file(self.hydrophone.save_folder + filename, aa_filepath)
        aa_df = pd.read_parquet(aa_filepath, engine='pyarrow')

        pos_df = aa_df.iloc[(date - aa_df.index).total_seconds() > 0]

        return pos_df.loc[min(pos_df.index, key=lambda sub: date - sub)].values[0]

    def generate_ref(self, year: dt.datetime, month: dt.datetime, samples=30):
        """
            Generate a 5th percentile broadband reference level for a give hydrophone, year, and month.

            * year: Datetime, year to use for generation
            * month: Datetime, month to use for generation
            * samples: Number of 10min-long samples to use

            # Return
            Float representing the reference level
        """

        bb = []
        count = 0
        while count < samples:
            # Randomly select a day, hour, and 10min start within a given year and month
            day = random.randint(1, 28)
            hour = random.randint(0, 22)
            minute = random.randint(0, 4) * 10
            try:
                # Calculating the broadband Dataframe for the sample
                pds_frame, broadband_frame = self.generate_psds(dt.datetime(year, month, day, hour, minute),
                                                                dt.datetime(year, month, day, hour, minute + 10),
                                                                overwrite_output=True, ref_lvl=False)
            except:
                continue
            # Appending all broadband readings to the list
            bb.extend(broadband_frame[0].tolist())
            count += 1
        # Setting reference level to 5th percentile of broadband list
        ref = np.percentile(bb, 5)

        return ref

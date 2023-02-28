

import datetime as dt
import os
from tempfile import TemporaryDirectory

import pandas as pd

from .file_connector import S3FileConnector
from .hydrophone import Hydrophone

class NoiseAcccessor:

    def __init__(self, hydrophone: Hydrophone):
        self.connector = S3FileConnector(hydrophone)


    def create_df(self, start, end, delta_t=10, delta_f="3oct", round_timestamps=False):
        """
        Creates a dataframe of one days worth of data.

        * start: datetime object representing start of range
        * end: datetime object representing end of range
        * delta_t: Int, Time frequency to find
        * delta_f: Str, Hz frequency to find. Use format '50hz' for linear hz bands or '3oct' for octave bands
        * round_timestamps: Bool, default False. Set to True to round timestamps to the delta_t frequency. Good for when grouping by time.

        # Return: Dataframe with request data in daterange. Index is datetime
        """

        # Setup
        dfs = []

        with TemporaryDirectory() as td:
            for filepath in self.connector.get_files(start, end, secs_per_sample=delta_t, hz_bands=delta_f):
                # Save file
                filename = filepath.split("/")[-1]
                save_location = os.path.join(td, filename)
                self.connector.download_file(filepath, save_location)

                # Load df
                this_start, this_end, _, _, _  = S3FileConnector.parse_filename(filename)
                this_df = pd.read_parquet(save_location)
                try:
                    dfs.append(this_df[this_start: this_end])
                except KeyError:
                    dfs.append(this_df)

        # Compile and clean
        df = pd.concat(dfs, axis=0)
        df = df[~df.index.duplicated(keep='first')]
        df = df[(df.index >= start) & (df.index <= end)]

        # Round
        if round_timestamps:
            df.index = pd.Series(df.index).apply(self._round_seconds, round_to=delta_t)
        return df
    
    @staticmethod
    def _round_seconds(target_dt, round_to=60):
        """
        Round the seconds datetime object. Can only round by even divisors of 60 for consistency 

        * target_dt : datetime object to round
        * round_to : Closest number of seconds to round to, default 1 minute. Must be a divisor of 60

        # Return
        Datetime object rounded to round_to secconds
        """

        # Validate
        if 60 % round_to != 0:
            raise ValueError("round_to must be a divisor of 60")
        
        # Round
        seconds = int(round(target_dt.second/round_to, 0) * round_to)
        diff = target_dt.second - seconds
        
        return target_dt.replace(microsecond=0) - dt.timedelta(seconds=diff)
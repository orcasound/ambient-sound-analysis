

import datetime as dt
import os
from tempfile import TemporaryDirectory

import pandas as pd

from ..utils.file_connector import S3FileConnector
from ..utils import Hydrophone

class NoiseAccessor:

    def __init__(self, hydrophone: Hydrophone):
        self.connector = S3FileConnector(hydrophone, no_sign=True)


    def create_df(self, start, end, delta_t=1, delta_f="3oct", round_timestamps=False, is_broadband=False):
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
            for filepath in self.connector.get_files(start, end, secs_per_sample=delta_t, hz_bands=delta_f, is_broadband=is_broadband):
                # Save file
                filename = filepath.split("/")[-1]
                save_location = os.path.join(td, filename)
                self.connector.download_file(filepath, save_location)

                # Load df
                this_start, this_end, _, _, _  = S3FileConnector.parse_filename(filename)
                this_df = pd.read_parquet(save_location)
                try:
                    this_df = this_df[(this_df.index >= this_start) & (this_df.index <= this_end)]
                except KeyError:
                    pass
                finally:
                    dfs.append(this_df)

        # Compile
        df = pd.concat(dfs, axis=0)
        df = df[~df.index.duplicated(keep='first')]

        # Round
        if round_timestamps:
            df.index = pd.Series(df.index).apply(self._round_seconds, round_to=delta_t)
            df = df.asfreq(str(delta_t) + 's')

        # Clean
        df = df[~df.index.duplicated(keep='first')]
        df = df[(df.index >= start) & (df.index <= end)]

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
    
    def get_options(self):
        """
        Get the time delta and frequency resolution options available already in S3. 

        # Return
        Tuple of lists.  Delta_t values, Delta_f values, frequency types. 
        """
        delta_fs = []
        delta_ts = []
        freq_types = []

        for item in self.connector.archive_resource.objects.filter(Prefix=self.connector.save_folder):
            filename = item.key.split("/")[-1]
            args = filename.replace(".parquet", "").split("_")

            if args[0] == 'ancient':
                continue
            else:
                _, _, secs, freq_value, freq_type = self.connector.parse_filename(filename)
                if freq_value != 0:
                    delta_fs.append(freq_value)
                delta_ts.append(secs)
                freq_types.append(freq_type)

        return list(set(delta_ts)), list(set(delta_fs)), list(set(freq_types))
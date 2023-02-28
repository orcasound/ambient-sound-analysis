

import os
from tempfile import TemporaryDirectory
import pandas as pd

from .file_connector import S3FileConnector
from .hydrophone import Hydrophone

class NoiseAcccessor:

    def __init__(self, hydrophone: Hydrophone):
        self.connector = S3FileConnector(hydrophone)


    def create_df(self, start, end, delta_t=10, delta_f="3oct"):
        """
        Creates a dataframe of one days worth of data.

        * start: datetime object representing start of range
        * end: datetime object representing end of range
        * delta_t: Int, Time frequency to find
        * delta_f: Str, Hz frequency to find. Use format '50hz' for linear hz bands or '3oct' for octave bands

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
        return df
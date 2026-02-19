import polars as pl
import numpy as np
import datetime as dt
from datetime import timedelta

from ..utils import Hydrophone

class PartitionedAccessor:
    def __init__(self, hydrophone: Hydrophone, start_time: dt.datetime, end_time: dt.datetime):
        self.hydrophone = hydrophone
        self.start_time = start_time
        self.end_time = end_time

        dates = []
        d = start_time.date()
        while d <= end_time.date():
            dates.append(d)
            d += timedelta(days=1)

        psd_paths = [
            f"s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/hydrophone={hydrophone.value.name}/year={d.year}/month={d.month:02d}/day={d.day:02d}/*.parquet"
            for d in dates
        ]

        bb_paths = [
            f"s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/broadband/hydrophone={hydrophone.value.name}/year={d.year}/month={d.month:02d}/day={d.day:02d}/*.parquet"
            for d in dates
        ]
        
        try:
            self.psd_df = (pl.scan_parquet(psd_paths,  storage_options={'aws_region': 'us-west-2'})
                           .filter(pl.col("__index_level_0__").is_between(start_time, end_time)))
            self.bb_df = (pl.scan_parquet(bb_paths,  storage_options={'aws_region': 'us-west-2'})
                          .filter(pl.col("__index_level_0__").is_between(start_time, end_time)))
        except FileNotFoundError as e:
            print(f"Error: File was not found. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    
    def get_dataframes(self):
        """
        Retrieves the PSD and broadband noise levels DataFrames for the specified time range.
        Returns:
            tuple: A tuple containing the PSD DataFrame and the broadband noise levels DataFrame for the specified time range.
        """
        return self.psd_df.collect(), self.bb_df.collect()
    
    def get_time_range_bb(self, start_time: dt.datetime, end_time: dt.datetime, df=None):
        """
        Retrieves data from the specified time range for the broadband noise levels.
        Args:
            start_time (dt.datetime): The start time of the desired time range.
            end_time (dt.datetime): The end time of the desired time range.
        Returns:
            pl.DataFrame: The filtered broadband noise levels DataFrame containing data within the specified time range
        """
        if df is None:
            df = self.bb_df
        df = df.filter(pl.col("__index_level_0__").is_between(start_time, end_time))
        return df
    
    # Currently assuming that data settings are delta_f = 1 and bands = 12 for calculating broadband noise levels, but this may need to be updated if data settings change
    def get_broadband(self, freq_low: int, freq_high: int, ref: float, name: str=None):
        """
        Retrieves data from the specified time range for the orca communication band (500-15000 Hz).
        Args:
            freq_low (int): The lower bound of the frequency range.
            freq_high (int): The upper bound of the frequency range.
            ref (float): The reference waveform
        Returns:
            pl.DataFrame: The filtered PSD DataFrame containing data within the specified time range and orca communication band (500-15000 Hz).
        """
        df = self.psd_df
        selected_cols = [
            col for col in df.collect_schema().names() 
            if col.isdigit() and freq_low <= int(col) <= freq_high
        ]

        broadband = (
            df  
            # convert from dB re ref Pa to Pa^2 linear scale
            .with_columns([(ref**2 * 10**(pl.col(colm)/10)).alias(colm) for colm in selected_cols])
            # given 1/12 octave bands, the delta f is approximately 0.5777 times the center frequency, so we can multiply by that to get the power in each band
            .with_columns([pl.col(col) * 0.577 * int(col) for col in selected_cols])
            # sum the power across the selected frequency bands and convert back to dB re ref Pa
            .with_columns((10 * np.log10(pl.sum_horizontal(selected_cols)/ref**2)).alias(f'{name}' if name else 'calc_bb'))
            .select(['__index_level_0__', f'{name}' if name else 'calc_bb'])
        )

        return broadband

    def get_quantile_range(self, start_time: dt.datetime, end_time: dt.datetime, df=None):
        """
        Retrieves quantiles for the broadband noise levels within the specified time range.
        Args:
            df (pl.DataFrame, optional): A DataFrame containing broadband noise levels. If None, the method will use the broadband noise levels DataFrame from the class instance. Default is None.
        Returns:
            pl.DataFrame: A DataFrame containing the broadband noise levels and their corresponding quantiles within the specified time range.
        """
        if df is None:
            df = self.bb_df
        df = self.get_time_range_bb(start_time, end_time, df=df)
        quant_df = df.with_columns(
            (pl.col("0")
                .rank(method="average")
                / pl.len()
            ).alias("quantile")
        ).filter(pl.col("0") > 0).select(["0", "quantile"])

        return quant_df.collect()
    
    def get_quantiles(self,  start_time: dt.datetime, end_time: dt.datetime, df: pl.DataFrame=None, name: str=None ):
        """
        Retrieves quantiles for the broadband noise levels within the specified time range.
        Args:
            df (pl.DataFrame, optional): A DataFrame containing broadband noise levels. If None, the method will use the broadband noise levels DataFrame from the class instance. Default is None.
        Returns:
            pl.Dataframe: A dataframe containing the 0.05, 0.25, 0.5, 0.75, and 0.95 quantiles for the broadband noise levels within the specified time range.
        """
        if df is None:
            df = self.bb_df
        df = self.get_time_range_bb(start_time, end_time, df=df)
        quantiles = df.select(
            pl.col('0').quantile(0.05).alias(f'{name}_q05' if name else 'q05'),
            pl.col('0').quantile(0.25).alias(f'{name}_q25' if name else 'q25'),
            pl.col('0').quantile(0.5).alias(f'{name}_q50' if name else 'q50'),
            pl.col('0').quantile(0.75).alias(f'{name}_q75' if name else 'q75'),
            pl.col('0').quantile(0.95).alias(f'{name}_q95' if name else 'q95')
        )

        return quantiles.collect()
    
    def get_percentage_over_threshold(self, threshold: float = 120.0):
        """
        Retrieves the percentage of time that broadband noise levels exceed a specified threshold within a given time range.
        Args:
            threshold (float): The noise level threshold in dB. Default is 120.0 dB.
            threshold (float): The noise level threshold in dB. Default is 120.0 dB.
        Returns:
            pl.DataFrame: A DataFrame containing the percentage of time that broadband noise levels exceed the specified threshold within the given time range.
        """
        df = self.bb_df
        percentage_df = (
            df
            .select(((pl.col('0') > threshold).sum() / pl.len()).alias(f"Percentage_of_time_over_{threshold}dB"))
        )

        return percentage_df.collect()

    def polars_to_pandas(self, pl_df: pl.DataFrame):
        """
        Converts a Polars DataFrame to a Pandas DataFrame, setting the index to the original Polars DataFrame index.
        Args:
            pl_df (pl.DataFrame): The Polars DataFrame to convert.
        Returns:
            pd.DataFrame: The converted Pandas DataFrame.
        """
        pd_df = pl_df.to_pandas()
        pd_df.set_index('__index_level_0__', inplace=True)
        return pd_df
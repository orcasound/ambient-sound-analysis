import polars as pl
import numpy as np
import datetime as dt

from ..utils import Hydrophone

class PartitionedAccessor:
    def __init__(self, hydrophone: Hydrophone):
        self.hydrophone = hydrophone
        self.s3_path_bb = f's3://{self.hydrophone.value.save_bucket}/{self.hydrophone.value.save_folder}/broadband/hydrophone={self.hydrophone.value.name}/'
        self.s3_path_psd = f's3://{self.hydrophone.value.save_bucket}/{self.hydrophone.value.save_folder}/psd/hydrophone={self.hydrophone.value.name}/'

        try:
            self.psd_df = pl.scan_parquet(self.s3_path_psd,  storage_options={'aws_region': 'us-west-2'})
            self.bb_df = pl.scan_parquet(self.s3_path_bb,  storage_options={'aws_region': 'us-west-2'})
        except FileNotFoundError as e:
            print(f"Error: File was not found. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    
    def get_time_range(self, start_time: dt.datetime, end_time: dt.datetime, psd: bool = True):
        """
        Retrieves data from the specified time range for either PSD or broadband.
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
            psd (bool): If True, retrieves PSD data; otherwise, retrieves broadband data.
        Returns:
            pl.DataFrame: The filtered DataFrame containing data within the specified time range.
        """
        if psd:
            df = self.psd_df
        else:
            df = self.bb_df
        filtered = df.filter(
            (pl.col('year') >= start_time.year) &
            (pl.col('year') <= end_time.year) &
            (pl.col('month') >= start_time.month) &
            (pl.col('month') <= end_time.month) &
            (pl.col('day') >= start_time.day) &
            (pl.col('day') <= end_time.day) &
            (pl.col('__index_level_0__') >= start_time) & 
            (pl.col('__index_level_0__') <= end_time)
        )
        return filtered.collect()
    
    # Currently assuming that data settings are delta_f = 1 and bands = 12 for calculating broadband noise levels, but this may need to be updated if data settings change
    def get_broadband(self, start_time: dt.datetime, end_time: dt.datetime, freq_low: int, freq_high: int, ref: float):
        """
        Retrieves data from the specified time range for the orca communication band (500-15000 Hz).
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
            ref (float): The reference waveform
        Returns:
            pl.DataFrame: The filtered PSD DataFrame containing data within the specified time range and orca communication band (500-15000 Hz).
        """
        df = self.get_time_range(start_time, end_time, psd=True)
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
            .with_columns((10 * np.log10(pl.sum_horizontal(selected_cols)/ref**2)).alias('sound_pressure_level_db'))
            .select(['__index_level_0__', 'hydrophone', 'year', 'month', 'day', 'sound_pressure_level_db'])
        )

        return broadband.collect()

    def get_quantile_range(self, start_time: dt.datetime, end_time: dt.datetime):
        """
        Retrieves quantiles for the broadband noise levels within the specified time range.
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
        Returns:
            pl.DataFrame: A DataFrame containing the broadband noise levels and their corresponding quantiles within the specified time range.
        """
        df = self.get_time_range(start_time, end_time, psd=False)
        quant_df = df.with_columns(
            (pl.col("0")
                .rank(method="average")
                / pl.len()
            ).alias("quantile")
        ).filter(pl.col("0") > 0).select(["0", "quantile"])

        return quant_df.collect()
    
    def get_quantiles(self, start_time: dt.datetime, end_time: dt.datetime):
        """
        Retrieves quantiles for the broadband noise levels within the specified time range.
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
        Returns:
            pl.Dataframe: A dataframe containing the 0.05, 0.25, 0.5, 0.75, and 0.95 quantiles for the broadband noise levels within the specified time range.
        """
        df = self.get_time_range(start_time, end_time, psd=False)
        quantiles = df.select(
            pl.col('0').quantile(0.05).alias('q05'),
            pl.col('0').quantile(0.25).alias('q25'),
            pl.col('0').quantile(0.5).alias('q50'),
            pl.col('0').quantile(0.75).alias('q75'),
            pl.col('0').quantile(0.95).alias('q95')
        )

        return quantiles.collect()
    
    def get_percentage_over_threshold(self, start_time: dt.datetime, end_time: dt.datetime, threshold: float = 120.0):
        """
        Retrieves the percentage of time that broadband noise levels exceed a specified threshold within a given time range.
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
            threshold (float): The noise level threshold in dB. Default is 120.0 dB.
        Returns:
            pl.DataFrame: A DataFrame containing the percentage of time that broadband noise levels exceed the specified threshold within the given time range.
        """
        df = self.get_time_range(start_time, end_time, psd=False)
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
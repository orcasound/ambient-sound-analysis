import polars as pl
import numpy as np
import datetime as dt
from datetime import timedelta

from ..utils import Hydrophone

class PartitionedAccessor:
    def __init__(self, hydrophone: Hydrophone, start_time: dt.datetime, end_time: dt.datetime, s3_folder: str = None):
        self.hydrophone = hydrophone
        self.start_time = start_time
        self.end_time = end_time
        if s3_folder:
            s3_loc = f"s3://{hydrophone.value.save_bucket}/{s3_folder}"
        else:
            s3_loc = f"s3://{hydrophone.value.save_bucket}/{hydrophone.value.save_folder}"
        psd_paths = []
        bb_paths = []
        d = start_time.date()
        while d <= end_time.date():
            psd_path = f"{s3_loc}/psd/hydrophone={hydrophone.value.name}/year={d.year}/month={d.month:02d}/day={d.day:02d}/*.parquet"
            bb_path = f"{s3_loc}/broadband/hydrophone={hydrophone.value.name}/year={d.year}/month={d.month:02d}/day={d.day:02d}/*.parquet"
            psd_paths.append(psd_path)
            bb_paths.append(bb_path)
            d += timedelta(days=1)
        
        self.psd_df = (pl.scan_parquet(psd_paths,  storage_options={'aws_region': 'us-west-2'})
                        .filter(pl.col("ind").is_between(start_time, end_time)).sort("ind"))
        self.bb_df = (pl.scan_parquet(bb_paths,  storage_options={'aws_region': 'us-west-2'})
                        .filter(pl.col("ind").is_between(start_time, end_time)).sort("ind"))
    
    def get_dataframes(self, lazy: bool = False):
        """
        Retrieves the PSD and broadband noise levels DataFrames for the specified time range.
        Returns:
            tuple: A tuple containing the PSD DataFrame and the broadband noise levels DataFrame for the specified time range.
        """
        if lazy:
            return self.psd_df, self.bb_df
        else:
            return self.psd_df.collect(), self.bb_df.collect()
    
    # Currently assuming that data settings are delta_f = 1 and bands = 12 for calculating broadband noise levels, but this may need to be updated if data settings change
    def get_broadband(self, freq_low: int, freq_high: int, ref: float, name: str=None):
        """
        Retrieves data from the specified time range for the orca communication band (500-15000 Hz).
        Args:
            freq_low (int): The lower bound of the frequency range.
            freq_high (int): The upper bound of the frequency range.
            ref (float): The reference waveform
        Returns:
            pl.LazyFrame: The filtered PSD LazyFrame containing data within the specified time range and orca communication band (500-15000 Hz).
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
            .select(['ind', f'{name}' if name else 'calc_bb'])
        )

        return broadband

def get_quantile_range(start_time: dt.datetime, end_time: dt.datetime, df: pl.LazyFrame, col_name: str = '0'):
    """
    Retrieves quantiles for the broadband noise levels within the specified time range.
    Args:
        start_time (dt.datetime): The start time of the time range for which to retrieve quantiles.
        end_time (dt.datetime): The end time of the time range for which to retrieve quantiles.
        df (pl.LazyFrame): A LazyFrame containing broadband noise levels matching the broadband schema.
        col_name (str): The name of the column containing broadband noise levels to calculate quantiles for. Default is '0'.
    Returns:
        pl.DataFrame: A DataFrame containing the broadband noise levels and their corresponding quantiles within the specified time range.
    """
    df = df.filter(pl.col("ind").is_between(start_time, end_time))
    quant_df = df.with_columns(
        (pl.col(col_name)
            .rank(method="average")
            / pl.len()
        ).alias("quantile")
    ).filter(pl.col(col_name) > 0).select([col_name, "quantile"])

    return quant_df.collect()
    
def get_quantiles(start_time: dt.datetime, end_time: dt.datetime, df: pl.LazyFrame, col_name: str = '0', name: str=None ):
    """
    Retrieves quantiles for the broadband noise levels within the specified time range.
    Args:
        start_time (dt.datetime): The start time of the time range for which to retrieve quantiles.
        end_time (dt.datetime): The end time of the time range for which to retrieve quantiles.
        df (pl.LazyFrame): A LazyFrame containing broadband noise levels matching the broadband schema.
        col_name (str): The name of the column containing broadband noise levels to calculate quantiles for. Default is '0'.
        name (str): An optional name to prefix the quantile columns. Default is None.
    Returns:
        pl.Dataframe: A dataframe containing the 0.05, 0.25, 0.5, 0.75, and 0.95 quantiles for the broadband noise levels within the specified time range.
    """
    df = df.filter(pl.col("ind").is_between(start_time, end_time))
    quantiles = df.select(
        pl.col(col_name).quantile(0.05).alias(f'{name}_q05' if name else 'q05'),
        pl.col(col_name).quantile(0.25).alias(f'{name}_q25' if name else 'q25'),
        pl.col(col_name).quantile(0.5).alias(f'{name}_q50' if name else 'q50'),
        pl.col(col_name).quantile(0.75).alias(f'{name}_q75' if name else 'q75'),
        pl.col(col_name).quantile(0.95).alias(f'{name}_q95' if name else 'q95')
    )

    return quantiles.collect()
    
def get_percentage_over_threshold(df: pl.LazyFrame, threshold: float = 120.0, col_name: str = '0'):
    """
    Retrieves the percentage of time that broadband noise levels exceed a specified threshold within a given time range.
    Args:
        df (pl.LazyFrame): A LazyFrame containing broadband noise levels matching the broadband schema.
        threshold (float): The noise level threshold in dB. Default is 120.0 dB.
        col_name (str): The name of the column containing broadband noise levels to calculate the percentage for. Default is '0'.
    Returns:
        pl.DataFrame: A DataFrame containing the percentage of time that broadband noise levels exceed the specified threshold within the given time range.
    """
    percentage_df = (
        df
        .select(((pl.col(col_name) > threshold).sum() / pl.len()).alias(f"Percentage_of_time_over_{threshold}dB"))
    )

    return percentage_df.collect()

def polars_to_pandas(pl_df: pl.DataFrame):
    """
    Converts a Polars DataFrame to a Pandas DataFrame, setting the index to the original Polars DataFrame index.
    Args:
        pl_df (pl.DataFrame): The Polars DataFrame to convert.
    Returns:
        pd.DataFrame: The converted Pandas DataFrame.
    """
    pd_df = pl_df.to_pandas()
    pd_df.set_index('ind', inplace=True)
    return pd_df
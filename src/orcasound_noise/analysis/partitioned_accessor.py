import polars as pl
import datetime as dt
import os

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
    
    def get_orca_communication_band(self, start_time: dt.datetime, end_time: dt.datetime):
        """
        Retrieves data from the specified time range for the orca communication band (500-15000 Hz).
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
        Returns:
            pl.DataFrame: The filtered PSD DataFrame containing data within the specified time range and orca communication band (500-15000 Hz).
        """
        df = self.get_time_range(start_time, end_time, psd=True)
        selected_cols = [
            col for col in df.collect_schema().names() 
            if col.isdigit() and 500 <= int(col) <= 15000
        ]
        comm_df = df.select(selected_cols)

        return comm_df
    
    def get_orca_echo_band(self, start_time: dt.datetime, end_time: dt.datetime):
        """
        Retrieves data from the specified time range for the orca echo band (>15000 Hz).
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
        Returns:
            pl.DataFrame: The filtered PSD DataFrame containing data within the specified time range and orca echo band (>15000 Hz).
        """
        df = self.get_time_range(start_time, end_time, psd=True)
        selected_cols = [
            col for col in df.collect_schema().names() 
            if col.isdigit() and int(col) > 15000
        ]
        echo_df = df.select(selected_cols)

        return echo_df
    
    def get_quantiles(self, start_time: dt.datetime, end_time: dt.datetime):
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
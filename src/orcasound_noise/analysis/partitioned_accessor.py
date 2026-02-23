import polars as pl
import numpy as np
import datetime as dt

from ..utils import Hydrophone

# ISO R40 (1/12 octave) center frequencies, 67 Hz to 22400 Hz
FREQ_BANDS_R40 = [
    67, 71, 75, 80, 85, 90, 95, 100, 106, 112, 118, 125,
    132, 140, 150, 160, 170, 180, 190, 200, 212, 224, 236, 250,
    265, 280, 300, 315, 335, 355, 375, 400, 425, 450, 475, 500,
    530, 560, 600, 630, 670, 710, 750, 800, 850, 900, 950, 1000,
    1060, 1120, 1180, 1250, 1320, 1400, 1500, 1600, 1700, 1800, 1900, 2000,
    2120, 2240, 2360, 2500, 2650, 2800, 3000, 3150, 3350, 3550, 3750, 4000,
    4250, 4500, 4750, 5000, 5300, 5600, 6000, 6300, 6700, 7100, 7500, 8000,
    8500, 9000, 9500, 10000, 10600, 11200, 11800, 12500, 13200, 14000, 15000, 16000,
    17000, 18000, 19000, 20000, 21200, 22400,
]

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
            (pl.col('__index_level_0__') >= start_time) &
            (pl.col('__index_level_0__') <= end_time)
        )
        result = filtered.collect()
        if psd:
            index_cols = [c for c in result.columns if c.isdigit()]
            rename_map = {str(i): str(FREQ_BANDS_R40[int(i)]) for i in range(len(FREQ_BANDS_R40)) if str(i) in index_cols}
            result = result.rename(rename_map)
        return result
    
    # Currently assuming that data settings are delta_f = 1 and bands = 12 for calculating broadband noise levels, but this may need to be updated if data settings change
    def get_broadband(self, start_time: dt.datetime, end_time: dt.datetime, freq_low: int, freq_high: int, ref: float):
        """
        Calculates broadband sound pressure level for a specified frequency range from PSD data.
        Args:
            start_time (dt.datetime): The start of the time range.
            end_time (dt.datetime): The end of the time range.
            freq_low (int): Lower bound of frequency range in Hz (e.g., 500 for orca communication band).
            freq_high (int): Upper bound of frequency range in Hz (e.g., 15000 for orca communication band).
            ref (float): Reference pressure value (use 1.0 for normalized; use hydrophone.bb_ref for calibrated).
        Returns:
            pl.DataFrame: DataFrame with columns including __index_level_0__, hydrophone, and sound_pressure_level_db.
        """
        df = self.get_time_range(start_time, end_time, psd=True)
        selected_cols = [
            col for col in df.columns
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

        return broadband

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

        return quant_df
    
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

        return quantiles
    
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

        return percentage_df

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
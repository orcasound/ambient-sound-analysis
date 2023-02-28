import datetime as dt
import os
from collections.abc import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from .accessor import NoiseAcccessor

class DailyNoiseAnalysis:

    def __init__(self, hydrophone) -> None:
        self.accessor = NoiseAcccessor(hydrophone)

    def get_daily_df(self, target_date):
        """
        Creates a dataframe of one days worth of data.

        * targetdate: date object of date to pull

        # Return: Dataframe with one day of data
        """

        return self.accessor.create_df(start=target_date, end=target_date + dt.timedelta(days=1), round_timestamps=True)

    def create_daily_noise_summary_df(self, start_date, num_days):
        # Compile
        start_date = dt.datetime.combine(start_date, dt.time.min)
        daily_dfs = [self.get_daily_df(start_date + dt.timedelta(days=i)) for i in range(num_days)]
        df = pd.concat(daily_dfs, axis=0)

        # Group
        df["time"] = df.index.time
        print(df["time"])
        time_group = df.groupby("time")
        mean_df = time_group.mean()
        min_df = time_group.min()
        max_df = time_group.max()

        return {
            "mean":mean_df, 
            "min": min_df,
            "max": max_df
        }

    @staticmethod
    def plot_daily_noise(df_dict, band=63, mean_smoothing=500, error_smoothing=100):
        mean_df = df_dict["mean"] 
        min_df = df_dict["min"] 
        max_df = df_dict["max"] 

        # Prepare Series
        if isinstance(band, Iterable):
            mean_series = mean_df.loc[:, band[0]:band[1]].mean(axis=1, skipna=True)
            min_series = min_df.loc[:, band[0]:band[1]].mean(axis=1, skipna=True)
            max_series = max_df.loc[:, band[0]:band[1]].mean(axis=1, skipna=True)
        else:
            mean_series, min_series, max_series = mean_df[band], min_df[band], max_df[band]
        
        # Smoothing
        def smooth(series, smooth_amount):
            looped_series = pd.concat([series[-smooth_amount:], series])
            smoothed = looped_series.rolling(smooth_amount).mean()
            return smoothed[smooth_amount: ]

        # PLot
        fig, ax = plt.subplots()
        ax.set_ylim([min_series.quantile(0.01), max_series.quantile(0.99)])
        smooth(mean_series, mean_smoothing).plot()
        ax.fill_between(mean_df.index, smooth(min_series, error_smoothing), smooth(max_series, error_smoothing), alpha=0.2, interpolate=True)
        plt.xticks([dt.time(i*6, 0) for i in range(4)])

        return fig





                




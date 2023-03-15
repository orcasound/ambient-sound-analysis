import datetime as dt
from collections.abc import Iterable

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from .accessor import NoiseAccessor

class DailyNoiseAnalysis:

    def __init__(self, hydrophone) -> None:
        self.accessor = NoiseAccessor(hydrophone)

    def get_daily_df(self, target_date, **kwargs):
        """
        Creates a dataframe of one days worth of data.

        * targetdate: date object of date to pull

        # Return: Dataframe with one day of data
        """

        return self.accessor.create_df(start=target_date, end=target_date + dt.timedelta(days=1), round_timestamps=True)

    def create_daily_noise_summary_df(self, start_date, num_days, **kwargs):
        # Compile
        start_date = dt.datetime.combine(start_date, dt.time.min)
        # daily_dfs = [self.get_daily_df(start_date + dt.timedelta(days=i)) for i in range(num_days)]
        # df = pd.concat(daily_dfs, axis=0)
        df = self.accessor.create_df(start=start_date, end=start_date + dt.timedelta(days=num_days), round_timestamps=True)

        # Group
        df["time"] = df.index.time
        time_group = df.groupby("time")
        mean_df = time_group.mean()
        min_df = time_group.min()
        max_df = time_group.max()
        count = time_group.count()

        return {
            "mean":mean_df, 
            "min": min_df,
            "max": max_df,
            "count": count
        }

    @staticmethod
    def plot_daily_noise(df_dict, band=[63, 8000], mean_smoothing=60, error_smoothing=60):
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
            smoothed = looped_series.rolling(smooth_amount, min_periods=1, center=True).mean()

            # Outlier removal
            smoothed = smoothed.clip(
                lower=smoothed.quantile(0.001),
                upper=smoothed.quantile(0.999)
                )
            return smoothed[smooth_amount: ]

        # Plot
        fig = go.Figure()
        x = pd.Series(mean_series.index)
        x_rev = x[::-1]
        fig.add_trace(go.Scatter(
            x=x,
            y=smooth(mean_series, mean_smoothing),
            name='Mean Noise',
        ))
        y = pd.concat([smooth(max_series, error_smoothing), smooth(min_series, error_smoothing)[::-1]])
        fig.add_trace(go.Scatter(
            x=pd.concat([x, x_rev]),
            y=y,
            fill='toself',
            showlegend=False,
            name='Mean Noise',
        ))
        # fig.add_trace(go.Scatter(
        #     x=x,
        #     y=smooth(mean_series, mean_smoothing*1000),
        #     name='Trend Line',
        #     line_color="#0000ff"
        # ))


        fig.update_traces(mode='lines')

        return fig

    def create_broadband_daily_noise(self, start_date, num_days):
        # Compile
        start_date = dt.datetime.combine(start_date, dt.time.min)
        df = self.accessor.create_df(start=start_date, end=start_date + dt.timedelta(days=num_days), delta_f="broadband")

        # Group
        df["date"] = df.index.date
        return df.groupby("date").mean()
    
    @staticmethod
    def plot_broadband_daily_noise(vals):
        # PLot
        return go.Figure([go.Bar(x=vals.index, y=vals["0"])])






                




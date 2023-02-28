import datetime as dt
import os
from collections.abc import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from .file_connector import S3FileConnector


def get_daily_df(target_date):
    """
    Creates a dataframe of one days worth of data.

    * targetdate: date object of date to pull

    # Return: Dataframe with one day of data
    """

    dfs = []

    directory = os.fsencode('pqt')
    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        start, end, secs, freq, typ = S3FileConnector.parse_filename(filename)

        if start.date() == target_date or end.date() == target_date:
            this_df = pd.read_parquet(os.path.join('pqt', filename))
            #this_df.columns = this_df.columns.astype(int)
            try:
                dfs.append(this_df[start: end])
            except KeyError:
                dfs.append(this_df)

    df = pd.concat(dfs, axis=0)
    df = df[~df.index.duplicated(keep='first')]
    df = df[df.index.date == target_date]
    return df

def create_daily_noise_summary_df(start_date, num_days):
    # Compile
    daily_dfs = [get_daily_df(start_date + dt.timedelta(days=i)) for i in range(num_days)]
    df = pd.concat(daily_dfs, axis=0)

    # Group
    df["time"] = df.index.time
    df["time"] = df["time"].apply(round_time, roundTo=10)
    time_group = df.groupby("time")
    mean_df = time_group.mean()
    min_df = time_group.min()
    max_df = time_group.max()

    return {
        "mean":mean_df, 
        "min": min_df,
        "max": max_df
    }

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
    # smooth(min_series, error_smoothing).plot()
    # smooth(max_series, error_smoothing).plot()
    ax.fill_between(mean_df.index, smooth(min_series, error_smoothing), smooth(max_series, error_smoothing), alpha=0.2, interpolate=True)
    plt.xticks([dt.time(i*6, 0) for i in range(4)])

    # ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

    return fig

def round_time(target, roundTo=60):
   """
   Round a datetime object to any time lapse in seconds

   * target : datetime.time object
   * roundTo : Closest number of seconds to round to, default 1 minute.
   """
   temp_dt = dt.datetime(2000, 1, 1, target.hour, target.minute, target.second)
   seconds = (temp_dt - temp_dt.min).seconds
   rounding = (seconds+roundTo/2) // roundTo * roundTo
   return (temp_dt + dt.timedelta(0,rounding-seconds)).time()




            




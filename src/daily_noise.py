import datetime as dt
import os
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
            try:
                dfs.append(this_df[start: end])
            except KeyError:
                dfs.append(this_df)

    df = pd.concat(dfs, axis=0)
    df = df[~df.index.duplicated(keep='first')]
    return df

def create_daily_noise_plot(start_date, num_days, band="63", mean_smoothing=500, error_smoothing=100):
    # Compile
    daily_dfs = [get_daily_df(start_date + dt.timedelta(days=i)) for i in range(num_days)]
    df = pd.concat(daily_dfs, axis=0)

    # Group
    df["time"] = df.index.time
    time_group = df.groupby("time")
    mean_df = time_group.mean()
    min_df = time_group.min()
    max_df = time_group.max()

    # PLot
    fig, ax = plt.subplots()
    mean_series, min_series, max_series = mean_df[band], min_df[band], max_df[band]
    ax.set_ylim([min_series.quantile(0.01), max_series.quantile(0.99)])
    mean_series.rolling(500).mean().plot()
    ax.fill_between(mean_df.index, min_series.rolling(100).mean(), max_series.rolling(100).mean(), alpha=0.2)

    return fig





            




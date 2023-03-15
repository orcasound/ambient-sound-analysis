import datetime as dt
from copy import deepcopy
import pickle

import streamlit as st
import pandas as pd

from src.orcasound_noise.analysis import DailyNoiseAnalysis
from src.orcasound_noise.utils import Hydrophone
from src.orcasound_noise.pipeline import pipeline
from src.orcasound_noise.pipeline import acoustic_util


# Title
st.write("# Daily Noise Levels")


col1, col2 = st.columns(2)
with col1:
    # Choose Hydrophone
    hydrophones = ["Orcasound Lab"]
    selected_hydrophone = st.selectbox(
        'Hydrophone',
        hydrophones
    )

with col2:
    # Choose Month
    months = [f"2021_{i}" for i in range(1,12)]
    selected_month = st.selectbox(
        'Month',
        months
    )

# Create analysis
@st.cache
def get_summary_dfs(hydrophone, month):
    with open(f'pages/demo_data/daily_summary_{month}.pkl', 'rb') as f:
        return pickle.load(f)
    return DailyNoiseAnalysis(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_daily_noise_summary_df(start_date, day_range)
summary_dfs = get_summary_dfs(selected_hydrophone, selected_month)


# Choose Band
bands = summary_dfs["mean"].columns
selected_band = st.select_slider(
    'Band',
    bands, 
    (bands[0], bands[-1])
)


# Display
st.write(f"Daily Noise in {selected_band[0]}hz to {selected_band[1]}hz band")
fig = DailyNoiseAnalysis.plot_daily_noise(summary_dfs, band=selected_band, mean_smoothing=100, error_smoothing=10)
st.plotly_chart(fig)

# Broadband
st.write("Average Daily Noise Levels")
year, month = selected_month.split("_")
start_date = dt.date(int(year), int(month), 1)
@st.cache
def get_broadband_df(hydrophone):
    return DailyNoiseAnalysis(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_broadband_daily_noise(start_date, 30)
broadband_df = get_broadband_df(selected_hydrophone)

fig = DailyNoiseAnalysis.plot_broadband_daily_noise(broadband_df)
st.plotly_chart(fig)
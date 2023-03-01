import datetime as dt
import pandas as pd
import os
from tempfile import TemporaryDirectory

import streamlit as st

# Local imports
from src.daily_noise import DailyNoiseAnalysis
from src.hydrophone import Hydrophone

# Title
st.write("# Daily Noise Levels")

# Choose Hydrophone
hydrophones = ["Orcasound Lab"]
selected_hydrophone = st.selectbox(
    'Hydrophone',
    hydrophones
)

# Create analysis
@st.cache
def get_summary_dfs(hydrophone):
    return DailyNoiseAnalysis(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_daily_noise_summary_df(dt.date(2023, 2, 1), 3)
summary_dfs = get_summary_dfs(selected_hydrophone)

# Choose Band
bands = summary_dfs["mean"].columns
selected_band = st.select_slider(
    'Band',
    bands, 
    (bands[0], bands[-1])
)

# Display
st.write(f"Daily Noise in {selected_band[0]}hz to {selected_band[1]}hz band")
fig = DailyNoiseAnalysis.plot_daily_noise(summary_dfs, band=selected_band)
fig.patch.set_facecolor(None)
fig.patch.set_alpha(0.0)
st.pyplot(fig)
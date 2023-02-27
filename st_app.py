import datetime as dt
import pandas as pd
import os
from tempfile import TemporaryDirectory

import streamlit as st

# Local imports
from src import daily_noise

# Title
st.write("# Daily Noise Levels")

# Choose Hydrophone
hydrophones = ["Orcasound Lab"]
selected_hydrophone = st.selectbox(
    'Hydrophone',
    hydrophones
)

# Get Dfs
@st.cache
def get_summary_dfs(hydrophone):
    return daily_noise.create_daily_noise_summary_df(dt.date(2023, 2, 1), 2)
summary_dfs = get_summary_dfs(selected_hydrophone)

# Choose Band
bands = summary_dfs["mean"].columns
selected_band = st.select_slider(
    'Band',
    bands
)

# Display
st.write(f"Daily Noise in {selected_band}hz band")
fig = daily_noise.plot_daily_noise(summary_dfs, band=selected_band)
fig.patch.set_facecolor(None)
fig.patch.set_alpha(0.0)
st.pyplot(fig)
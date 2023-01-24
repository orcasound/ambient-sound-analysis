import datetime as dt
import pandas as pd
import os
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import streamlit as st

# Local imports
from src import pipeline

# Title
st.write("# Example Spectrograms")

# Demo data
use_demo = st.checkbox("Use Demo Data", value=True)

# Date
as_of_date = st.date_input("Choose a day")

# Create spectrograms
@st.cache
def get_grams(as_of_date, use_demo=True):
    if use_demo:
        return [
                pd.read_csv(f'sample_psds/{file_name}').to_numpy()
                for file_name in os.listdir('sample_psds')
        ]
    else:
        with TemporaryDirectory() as tmp_path:
            return pipeline.ts_to_spectrogram(
                as_of_date,
                as_of_date + dt.timedelta(days=1),
                tmp_path
            )
grams = get_grams(as_of_date, use_demo)

# Choose spectrogram
gram_idx = st.selectbox(
    'Spectrogram #',
    range(len(grams))
)

# Display
st.write(f"Spectrogram {gram_idx}")
fig, ax = plt.subplots()
plt.pcolormesh(grams[gram_idx])
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time')
st.pyplot(fig)
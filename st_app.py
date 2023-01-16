import datetime as dt
import os
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import streamlit as st

# Local imports
from src import pipeline

# Title
st.write("# Example Spectrograms")

# Date
as_of_date = st.date_input("Choose a day")

# Create spectrograms
@st.cache
def get_grams(as_of_date):
    with TemporaryDirectory() as tmp_path:
        return pipeline.ts_to_spectrogram(
            as_of_date,
            as_of_date + dt.timedelta(days=1),
            tmp_path
        )
grams = get_grams(as_of_date)

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
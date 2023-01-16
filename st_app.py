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

grams = pipeline.ts_to_spectrogram(
    as_of_date,
    as_of_date + dt.timedelta(days=1),
    TemporaryDirectory
)

# grams = [
#     pipeline.create_spectogram('wav/' + file, 1)[2]
#     for file in os.listdir('wav')
# ]


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
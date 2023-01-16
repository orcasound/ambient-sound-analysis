import datetime as dt
import os

import matplotlib.pyplot as plt
import streamlit as st

# Local imports
from src import pipeline


# Create spectrograms
# grams = pipeline.ts_to_spectrogram(
#     dt.date(2022, 11, 5),
#     dt.date(2022, 11, 6),
#     'wav'
# )

grams = [
    pipeline.create_spectogram('wav/' + file, 1)[2]
    for file in os.listdir('wav')
]

# Title
st.write("# Example Spectrograms")

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
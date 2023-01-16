import datetime as dt

import matplotlib.pyplot as plt
import streamlit as st

# Local imports
from src import pipeline


# Create spectrograms
grams = pipeline.ts_to_spectrogram(
    dt.date(2022, 11, 5),
    dt.date(2022, 11, 6),
    'wav'
)

# Title
st.write("# Example Spectrograms")

# Add grams
for i, gram in enumerate(grams):
    st.write(f"Spectrogram {i}")

    fig, ax = plt.subplots()
    plt.pcolormesh(grams[0])
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time')

    st.pyplot(fig)
import streamlit as st

from src.orcasound_noise.dashboard import daily_dashboard, broadband_comparison, spectrogram

dailyTab, specTab, comparisonTab = st.tabs(["Daily Noise", "Spectrogram", "Broadband Comparison"])

with dailyTab:
    daily_dashboard.create_tab()

with specTab:
    spectrogram.create_tab()

with comparisonTab:
    broadband_comparison.create_tab()

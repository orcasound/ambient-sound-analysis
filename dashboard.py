import streamlit as st

from src.orcasound_noise.dashboard import daily_dashboard, dashboard_3, spectrogram

dailyTab, specTab, tab3 = st.tabs(["Daily Noise", "Spectrogram", "Tab3"])

with dailyTab:
    daily_dashboard.create_tab()

with specTab:
    spectrogram.create_tab()

with tab3:
    dashboard_3.create_tab()

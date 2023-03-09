import datetime as dt

import streamlit as st

from src.analysis import DailyNoiseAnalysis
from src.hydrophone import Hydrophone


def create_tab():
    # Title
    st.write("# Daily Noise Levels")

    # Choose Hydrophone
    hydrophones = ["Orcasound Lab"]
    selected_hydrophone = st.selectbox(
        'Hydrophone',
        hydrophones
    )

    # Choose dates
    col1, col2, col3 = st.columns(3)
    anchor_date = dt.date(2022, 1, 1)
    with col1:
        start_date = st.date_input(
            "Start Date", 
            anchor_date, 
            min_value=anchor_date, 
            max_value=dt.date.today()
        )
    with col2:
        end_date = st.date_input(
            "End Date", 
            start_date + dt.timedelta(days=30), 
            min_value=start_date, 
            max_value=dt.date.today()
        )
    day_range = (end_date - start_date).days

    # Create analysis
    @st.cache
    def get_summary_dfs(hydrophone):
        return DailyNoiseAnalysis(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_daily_noise_summary_df(start_date, day_range)
    summary_dfs = get_summary_dfs(selected_hydrophone)
    with col3:
        st.write(f"{summary_dfs['count'].max().max()} days of data found within range")

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
    @st.cache
    def get_broadband_df(hydrophone):
        return DailyNoiseAnalysis(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_broadband_daily_noise(start_date, day_range)
    broadband_df = get_broadband_df(selected_hydrophone)
    fig = DailyNoiseAnalysis.plot_broadband_daily_noise(broadband_df)
    st.plotly_chart(fig)
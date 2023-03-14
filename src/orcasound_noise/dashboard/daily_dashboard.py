import datetime as dt
from copy import deepcopy

import streamlit as st
import pandas as pd

from src.orcasound_noise.analysis import DailyNoiseAnalysis
from src.orcasound_noise.utils import Hydrophone
from src.orcasound_noise.pipeline import pipeline
from src.orcasound_noise.pipeline import acoustic_util


def create_tab():
    # Title
    st.write("# Daily Noise Levels")

    hydro_col, ref_col = st.columns([2,1])
    with hydro_col:
        # Choose Hydrophone
        hydrophones = ["Orcasound Lab"]
        selected_hydrophone = st.selectbox(
            'Hydrophone',
            hydrophones
        )

    with ref_col:
        reference = st.radio(
            'Reference Level',
            ('Full Scale', 'Ancient Ambient'),
            key='daily_ref'
        )

    if reference == 'Ancient Ambient':
        aa = True
    else:
        aa = False

    # Choose dates
    col1, col2, col3 = st.columns(3)
    anchor_date = dt.date(2021, 1, 1)
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
    summary_dfs = deepcopy(get_summary_dfs(selected_hydrophone))
    with col3:
        st.write(f"{summary_dfs['count'].max().max()} days of data found within range")

    # Choose Band
    bands = summary_dfs["mean"].columns
    selected_band = st.select_slider(
        'Band',
        bands, 
        (bands[0], bands[-1])
    )

    if aa:
        aa_df = summary_dfs
        ship = pipeline.NoiseAnalysisPipeline(Hydrophone[selected_hydrophone.upper().replace(" ", "_")], delta_f=1,delta_t = 1)

        aa = ship.get_ancient_ambient(dt.datetime.combine(end_date,dt.time(0,0,0)))
        aa_df['mean'] = acoustic_util.dBFS_to_aa(aa_df['mean'], aa)
        aa_df['min'] = acoustic_util.dBFS_to_aa(aa_df['min'], aa)
        aa_df['max'] = acoustic_util.dBFS_to_aa(aa_df['max'], aa)

        out_df = aa_df
    else:
        out_df = summary_dfs

    # Display
    st.write(f"Daily Noise in {selected_band[0]}hz to {selected_band[1]}hz band")
    fig = DailyNoiseAnalysis.plot_daily_noise(out_df, band=selected_band, mean_smoothing=100, error_smoothing=10)
    st.plotly_chart(fig)

    # Broadband
    st.write("Average Daily Noise Levels")
    @st.cache
    def get_broadband_df(hydrophone):
        return DailyNoiseAnalysis(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_broadband_daily_noise(start_date, day_range)
    broadband_df = deepcopy(get_broadband_df(selected_hydrophone))
    if aa:
        aa_bb = ship.get_ancient_ambient(dt.datetime.combine(end_date,dt.time(0,0,0)), dB=False)
        bb_df = acoustic_util.abs_to_dB(broadband_df, ref=aa_bb, columns=['Level'])
    else:
        bb_df = acoustic_util.abs_to_dB(broadband_df, columns=['Level'])
    
    fig = DailyNoiseAnalysis.plot_broadband_daily_noise(bb_df)
    st.plotly_chart(fig)
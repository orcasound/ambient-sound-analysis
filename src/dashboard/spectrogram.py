import datetime as dt

import streamlit as st
import plotly.graph_objects as go

from src.analysis import accessor
from src.hydrophone import Hydrophone


def create_tab():
    # Title
    st.write("Spectrogram")

    # Choose Hydrophone
    hydrophones = ["Orcasound Lab"]
    selected_hydrophone = st.selectbox(
        'Hydrophone',
        hydrophones,
        key='spec_hydro'
    )

    target_date = dt.datetime(2023,2,2)

    # Get data  
    @st.cache
    def get_summary_dfs(hydrophone):
        return accessor.NoiseAcccessor(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_df(start=target_date, end=target_date + dt.timedelta(days=1), delta_t=10)
    hydro_df = get_summary_dfs(selected_hydrophone)

    # Plot data
    fig = go.Figure(data=go.Heatmap(x=hydro_df.index, y=hydro_df.columns, z=hydro_df.values.transpose(),colorscale='Viridis',
                colorbar={"title": 'Magnitude'}))
    fig.update_layout(
        title="Hydrophone Power Spectral Density",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        legend_title="Magnitude"
        )
    st.plotly_chart(fig)
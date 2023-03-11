import datetime as dt

import streamlit as st
import plotly.graph_objects as go

from ..analysis import accessor
from ..utils import Hydrophone


def create_tab():
    # Title
    st.write("Spectrogram")

    col1, col2, col3 = st.columns(3)
    col4, col5, col6, col7 = st.columns(4)

    with col1:
        # Choose Hydrophone
        hydrophones = ["Orcasound Lab"]
        selected_hydrophone = st.selectbox(
            'Hydrophone',
            hydrophones,
            key='spec_hydro'
        )

    with col2:
        delta_t = st.selectbox(
            'Delta t',
            [0.1, 0.5, 1, 10],
            index=3
        )

    with col3:
        band = st.selectbox(
            'Octave Bands',
            ["1", "1/3", "1/6", "1/12", "1/24"], 
            index=1
        )

    band_ref = {"1": "1oct",
               "1/3": "3oct",
               "1/6": "6oct",
               "1/12": "12oct",
               "1/24": "24oct"
    }
    delta_f = band_ref[band]

    with col4:
        start_date = st.date_input("Start Date", value=dt.date(2023,2,2))

    with col5:
        start_time = st.time_input("Start Time", value=dt.time(0,0,0))

    with col6:
        end_date = st.date_input("End Date", value=dt.date(2023,2,3))

    with col7:
        end_time = st.time_input("End Time", value=dt.time(0,0,0))

    start = dt.datetime.combine(start_date, start_time)
    end = dt.datetime.combine(end_date, end_time)

    # Get data
    try:  
        @st.cache
        def get_summary_dfs(hydrophone):
            return accessor.NoiseAcccessor(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_df(start=start, end=end, 
                                                                                                       delta_t=delta_t, delta_f = delta_f)
        hydro_df = get_summary_dfs(selected_hydrophone)
        data_available = True
    except:
        data_available = False

    # Plot data
    if data_available:
        fig = go.Figure(data=go.Heatmap(x=hydro_df.index, y=hydro_df.columns, z=hydro_df.values.transpose(),colorscale='Viridis',
                    colorbar={"title": 'Magnitude'}))
        fig.update_layout(
            title="Hydrophone Power Spectral Density",
            xaxis_title="Time",
            yaxis_title="Frequency (Hz)",
            legend_title="Magnitude"
            )

    else:
        fig = go.Figure()
        fig.add_annotation(
            xref="x domain",
            yref="y domain",
            # The arrow head will be 25% along the x axis, starting from the left
            x=0.5,
            # The arrow head will be 40% along the y axis, starting from the bottom
            y=0.5,
            text="NO DATA",
            showarrow=False,
            font=dict(
                    family="Courier New, monospace",
                    size=48,
                    color="#FF0000"
                    ),
                align="center",
        )

    st.plotly_chart(fig)
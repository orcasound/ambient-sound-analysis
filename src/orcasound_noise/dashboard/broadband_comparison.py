import datetime as dt
from copy import deepcopy

import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


from src.orcasound_noise.analysis import accessor
from src.orcasound_noise.utils.hydrophone import Hydrophone


def create_tab():
    # Title
    st.write("Broadband Comparison")

    col1, col2, col3 = st.columns(3)
    col4, col5, col6, col7 = st.columns(4)

    with col1:
        # Choose Hydrophone
        hydrophones = ["Orcasound Lab"]
        selected_hydrophone = st.selectbox(
            'Hydrophone',
            hydrophones,
            key='broad_hydro'
        )

    with col2:
        delta_t = st.selectbox(
            'Delta t',
            [0.1, 0.5, 1, 10],
            index=2,
            key='broad_delt'
        )
    with col3:
        number_of_days_to_compare = st.selectbox(
            'Number of days to compare',
            [1, 2, 5, 7],
            index = 3
        )
    with col4:
        start_date_range = st.date_input("Start Date", value=dt.date(2020,2,2), key="broad_s_date")

    with col6:
        start_compare_date = st.date_input("Start of Compared Date", value=dt.date(2020,2,9), key="broad_e_date")

    start = dt.datetime.combine(start_date_range, dt.time(0,0,0))
    end = start+dt.timedelta(days=number_of_days_to_compare)
    start_compare = dt.datetime.combine(start_compare_date, dt.time(0,0,0))
    end_compare = start_compare+dt.timedelta(days=number_of_days_to_compare)

    # Get data
    def get_spec_dfs(selected_hydrophone, start, end):
        return accessor.NoiseAccessor(Hydrophone[selected_hydrophone.upper().replace(" ", "_")]).create_df(start=start,end=end, delta_t=delta_t, is_broadband=True)

    # Get data
    try:
        start_df = deepcopy(get_spec_dfs(selected_hydrophone, start, end))
        compare_df = deepcopy(get_spec_dfs(selected_hydrophone, start_compare, end_compare))
        data_available = True
    except:
        data_available = False
        st.write("Data not available.")



    if data_available:
        # hydro_df = get_summary_dfs(selected_hydrophone, start, end)
        # compare_df = get_summary_dfs(selected_hydrophone, start_compare, end_compare)
        fig = make_subplots(
            cols=1,
            rows=1,
            specs=[[{"secondary_y": True}]]
        )

        bar_trace = go.Scatter(
            x=start_df.index,
            y=start_df.iloc[:, 0],
            name="original broadband",
        )

        scatter_trace = go.Scatter(
            x=compare_df.index,
            y=compare_df.iloc[:, 0],
            name="compared broadband",
            line_color="#ee0000",
            opacity=0.5,

        )

        fig.add_trace(bar_trace, col=1, row=1)
        fig.add_trace(scatter_trace, col=1, row=1, secondary_y=True)

        # Copy 'anchor' and 'domain' of each subplot original xaxis
        fig.update_layout(
            xaxis3={**fig.layout.xaxis.to_plotly_json(), "side": "top", "overlaying": "x"},
        )

        # Re-assign scatter traces to axes created above
        fig.data[1].update(xaxis="x3")
        st.plotly_chart(fig)
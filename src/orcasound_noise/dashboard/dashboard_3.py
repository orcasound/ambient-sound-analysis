import datetime as dt

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.analysis import accessor
from src.hydrophone import Hydrophone


def create_tab():
    # Title
    st.write("# Broadband signal over time")

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
            index = 0
        )
    st.write("Timeframes less than a week are recommended.")
    with col4:
        start_date_range = st.date_input("Start Date", value=dt.date(2022,2,2), key="broad_s_date")

    with col6:
        start_compare_date = st.date_input("Start of Compared Date", value=dt.date(2022,2,3), key="broad_e_date")

    start = dt.datetime.combine(start_date_range, dt.time(0,0,0))
    end = start+dt.timedelta(days=number_of_days_to_compare)
    start_compare = dt.datetime.combine(start_compare_date, dt.time(0,0,0))
    end_compare = dt.datetime.combine(start_compare+dt.timedelta(days= number_of_days_to_compare),dt.time(0,0,0))

    # Get data
    try:
        @st.cache
        def get_summary_dfs(hydrophone, start, end):
            return accessor.NoiseAcccessor(Hydrophone[hydrophone.upper().replace(" ", "_")]).create_df(start=start, end=end,
                                                                                                       delta_t=delta_t, is_broadband=True)
        hydro_df = get_summary_dfs(selected_hydrophone, start, end)
        compare_df = get_summary_dfs(selected_hydrophone, start_compare, end_compare)
        data_available = True
    except:
        data_available = False
    if data_available:
        st.line_chart(hydro_df)
        st.line_chart(compare_df)
        import plotly.graph_objects as go

        # dict for the dataframes and their names
        dfs = {"df1": hydro_df, "df2": compare_df}
        # compare_df.reset_index(drop=True, inplace=True)
        # df = pd.concat([hydro_df, compare_df])
        # st.line_chart(df)
        # plot the data
        # fig = go.Figure()
        #
        # for i in dfs:
        #     fig = fig.add_trace(px.line(dfs[i]))
        # st.plotly_chart(fig)

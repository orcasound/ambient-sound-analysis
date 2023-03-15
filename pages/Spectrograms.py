import datetime as dt
from copy import deepcopy

import streamlit as st
import plotly.graph_objects as go

from src.orcasound_noise.analysis import accessor
from src.orcasound_noise.utils import Hydrophone
from src.orcasound_noise.pipeline import pipeline
from src.orcasound_noise.pipeline import acoustic_util



col1, col2, col3, radio = st.columns([3,1,1,2])
col4, col5, col6, col7 = st.columns(4)

aa = False

with col1:
    # Choose Hydrophone
    hydrophones = ["Orcasound Lab"]
    selected_hydrophone = st.selectbox(
        'Hydrophone',
        hydrophones,
        key='spec_hydro'
    )

delta_ts, delta_fs, _ = accessor.NoiseAccessor(Hydrophone[selected_hydrophone.upper().replace(" ", "_")]).get_options()

with col2:
    delta_t = st.selectbox(
        'Delta t',
        delta_ts
    )

with col3:
    band = st.selectbox(
        'Octave Bands',
        delta_fs
    )

with radio:
    reference = st.radio(
        'Reference Level',
        ('Full Scale', 'Ancient Ambient'),
        index=1
    )

if reference == 'Ancient Ambient':
    aa = True
elif reference == 'Full Scale':
    aa = False

band_ref = {1: "1oct",
            3: "3oct",
            6: "6oct",
            12: "12oct",
            24: "24oct"
}
delta_f = band_ref[band]

with col4:
    start_date = st.date_input("Start Date", value=dt.date(2020,2,2))

with col5:
    start_time = st.time_input("Start Time", value=dt.time(0,0,0))

with col6:
    end_date = st.date_input("End Date", value=dt.date(2020,2,3))

with col7:
    end_time = st.time_input("End Time", value=dt.time(0,0,0))

start = dt.datetime.combine(start_date, start_time)
end = dt.datetime.combine(end_date, end_time)

@st.cache
def get_spec_dfs(selected_hydrophone):
    return accessor.NoiseAccessor(Hydrophone[selected_hydrophone.upper().replace(" ", "_")]).create_df(start=start,end=end, delta_t=delta_t, delta_f=delta_f)

# Get data
try:                                                                    
    hydro_df = deepcopy(get_spec_dfs(selected_hydrophone))
    data_available = True
except:
    data_available = False

# Plot data
if data_available:
    if aa:
        aa_df = hydro_df
        ship = pipeline.NoiseAnalysisPipeline(Hydrophone[selected_hydrophone.upper().replace(" ", "_")], delta_f=1,
                                                delta_t = delta_t, bands=delta_f, no_auth=True)
        dates = [i.date() for i in aa_df.index]
        dates = list(set(dates))

        for date in dates:
            aa = ship.get_ancient_ambient(dt.datetime.combine(date,dt.time(0,0,0)))
            aa_df.loc[aa_df.index.date == date] = acoustic_util.dBFS_to_aa(aa_df.loc[aa_df.index.date == date], aa)
        out_df = aa_df
    else:
        out_df = hydro_df

    fig = go.Figure(data=go.Heatmap(x=out_df.index, y=out_df.columns, z=out_df.values.transpose(),colorscale='Viridis',
                colorbar={"title": 'Magnitude'}))
    fig.update_layout(
        title="Hydrophone Power Spectral Density",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        legend_title="Magnitude"
        )
    fig.update_yaxes(type="log")

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
import plotly.graph_objects as go
import numpy as np
import pandas as pd

def plot_spectrogram(df, title="Orcasound Ambient Sound Analysis", ship_df=None):
    # Return empty figure if data wasn't found
    if df is None or df.empty:
        return go.Figure()

    fig = go.Figure()

    TIME_DOWNSAMPLE_FACTOR = 30 
    FREQ_DOWNSAMPLE_FACTOR = 10

    df_small = df.iloc[::TIME_DOWNSAMPLE_FACTOR].copy()

    # Extract only frequency columns (they are numbers)
    valid_freq_cols = [c for c in df_small.columns if str(c).replace('.', '', 1).isdigit()]
    valid_freq_cols.sort(key=lambda x: float(str(x)))
    valid_freq_cols_small = valid_freq_cols[::FREQ_DOWNSAMPLE_FACTOR]
    
    # Transpose data for Plotly (x=time, y=frequency, z=PSD)
    z_data = df_small[valid_freq_cols_small].T.values 
    z_data = np.where(z_data == -100, np.nan, z_data)
    
    x_axis = df_small['__index_level_0__']
    y_axis = [float(c) for c in valid_freq_cols_small]
    
    min_freq = y_axis[0] if y_axis else 0
    max_freq = 16000 

    if np.isnan(z_data).all():
        zmin, zmax = -100, 0
    else:
        zmin = np.nanpercentile(z_data, 5)
        zmax = np.nanpercentile(z_data, 95)

    fig.add_trace(go.Heatmap(
        z=z_data,
        x=x_axis,
        y=y_axis,
        colorscale='Viridis',
        zmin=zmin,
        zmax=zmax,
        colorbar=dict(title='PSD (dB)'),
        hoverinfo='x+y+z',
        name='PSD Heatmap'
    ))

    start_view = x_axis.min() if not x_axis.empty else pd.Timestamp.min
    end_view = x_axis.max() if not x_axis.empty else pd.Timestamp.max

    # # --- 2. Ship Overlay Logic ---
    # if ship_df is not None and not ship_df.empty:
    #     relevant_ships = ship_df[
    #         (ship_df['entry_time'] <= end_view) & 
    #         (ship_df['exit_time'] >= start_view)
    #     ]

    #     for _, ship in relevant_ships.iterrows():
    #         entry = ship['entry_time']
    #         exit = ship['exit_time']
            
    #         fig.add_trace(go.Scatter(
    #             x=[entry, entry, exit, exit, entry],
    #             y=[min_freq, max_freq, max_freq, min_freq, min_freq],
    #             fill="toself",
    #             fillcolor="rgba(255, 0, 0, 0.2)",
    #             mode="lines",
    #             line=dict(width=0), 
    #             name="Ship Passage",
    #             hovertemplate=(
    #                 f"<b>SHIP PASSAGE</b><br>"
    #                 f"Type: {ship.get('type', ship.get('type_m2', 'Unknown'))}<br>"
    #                 f"ID: {ship.get('id_track', 'N/A')}<br>"
    #                 f"Closest Dist: {ship.get('closest_approach_km', 0):.2f} km<br>"
    #                 f"Duration: {exit - entry}<extra></extra>"
    #             ),
    #             showlegend=False
    #         ))

    #         fig.add_vline(x=entry, line_width=2, line_color="red", line_dash="dash")
    #         fig.add_vline(x=exit, line_width=2, line_color="red", line_dash="dash")

    fig.update_layout(
        title=title,
        yaxis_title="Frequency (Hz)",
        xaxis_title="Time (UTC)",
        height=650,
        hovermode="closest", 
        margin=dict(l=60, r=20, t=50, b=50),
        plot_bgcolor='white'
    )
    fig.update_yaxes(range=[min_freq, max_freq])

    return fig
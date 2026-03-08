import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd

def plot_spectrogram(df, title="Orcasound Ambient Sound Analysis", ship_df=None):
    
    # Return empty figure if data wasn't found
    if df is None or df.empty:
        return go.Figure()

    fig = go.Figure()

    TIME_DOWNSAMPLE_FACTOR = 1 
    FREQ_DOWNSAMPLE_FACTOR = 1

    df_small = df.iloc[::TIME_DOWNSAMPLE_FACTOR].copy()

    # Extract only frequency columns 
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

    # --- Base Spectrogram Trace ---
    fig.add_trace(go.Heatmap(
        z=z_data,
        x=x_axis,
        y=y_axis,
        colorscale='Viridis',
        zmin=zmin,
        zmax=zmax,
        colorbar=dict(
            title='', 
            tickmode='array',
            tickvals=[zmin, zmax], 
            ticktext=['Quiet', 'Loud'], 
            ticks='', 
        ),
        hoverinfo='x+y+z',
        name='PSD Heatmap'
    ))

    start_view = x_axis.min() if not x_axis.empty else pd.Timestamp.min
    end_view = x_axis.max() if not x_axis.empty else pd.Timestamp.max

    start_view = pd.to_datetime(start_view, utc=True)
    end_view = pd.to_datetime(end_view, utc=True)

    # --- Ship Overlay Logic  ---
    if ship_df is not None and not ship_df.empty:
        
        # Filter to ships that intersect the current spectrogram window
        relevant_ships = ship_df[
            (ship_df['s_timestamp'] <= end_view) & 
            (ship_df['l_timestamp'] >= start_view)
        ]

        for _, ship in relevant_ships.iterrows():
            actual_entry = ship['s_timestamp']
            actual_exit = ship['l_timestamp']
            
            # Clip the visual overlay polygon
            plot_entry = max(actual_entry, start_view)
            plot_exit = min(actual_exit, end_view)
            
            if plot_entry >= plot_exit:
                continue

            # --- Extract and Format Hover Data ---
            ship_type = str(ship.get('type', 'Unknown')).replace('_', ' ').title()
            ship_id = ship.get('id_track', 'N/A')
            
            # Safely get numeric values, falling back to 'N/A' if missing
            speed = round(ship.get('avg_speed', 0), 1) if pd.notna(ship.get('avg_speed')) else 'N/A'
            draft = round(ship.get('draft', 0), 1) if pd.notna(ship.get('draft')) else 'N/A'
            comm_bb_q50 = round(ship.get('comm_bb_q50', 0), 2) if pd.notna(ship.get('comm_bb_q50')) else 'N/A'
            
            # Format timestamps to look clean (e.g., "12:15:30 UTC")
            start_str = actual_entry.strftime('%H:%M:%S UTC')
            end_str = actual_exit.strftime('%H:%M:%S UTC')
            
            # Pack the HTML into the text variable
            hover_details = (
                f"<b>SHIP {ship_id}</b><br><br>"
                f"<b>Type:</b> {ship_type}<br>"
                f"<b>Passage:</b> {start_str} - {end_str}<br>"
                f"<b>Avg Speed:</b> {speed} knots<br>"
                f"<b>Draft:</b> {draft} m<br>"
                f"<b>Comm Band (q50):</b> {comm_bb_q50} dB"
            )
            
            fig.add_trace(go.Scatter(
                x=[plot_entry, plot_entry, plot_exit, plot_exit, plot_entry],
                y=[min_freq, max_freq, max_freq, min_freq, min_freq],
                fill="toself",
                fillcolor="rgba(255, 0, 0, 0.15)",
                mode="lines",
                line=dict(width=0), 
                name=f"Ship {ship_id}",
                text=hover_details,      
                hoverinfo="text",        
                hoveron="fills", 
                showlegend=False
            ))

    # --- Layout & Axis Configuration ---
    fig.update_layout(
        title=title,
        yaxis_title="Frequency (Hz)",
        yaxis_type="log",
        xaxis_title="Time (UTC)",
        height=650,
        hovermode="x", 
        margin=dict(l=60, r=20, t=50, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    safe_min_freq = max(10, min_freq) 
    fig.update_yaxes(range=[np.log10(safe_min_freq), np.log10(max_freq)])
    
    # Lock the X-axis strictly to the acoustic data boundaries
    fig.update_xaxes(range=[start_view, end_view])

    return fig




def create_ship_timeline_with_detections(ship_df, detections):
    """
    Generates a Gantt chart grouped by Ship Type and overlays whale bout detections.
    This is the chart that you see on opening the home page of the dashboard
    """
    # Plot Ship Tracks grouped by Vessel Type
    if ship_df is not None and not ship_df.empty:
        df_plot = ship_df.copy()
        
        # Ensure we have a 'type' column to group by on the Y-axis
        if 'type' not in df_plot.columns:
            df_plot['type'] = 'Not a Listed Type'
        else:
            df_plot['type'] = df_plot['type'].fillna('Not a Listed Type')

        df_plot = df_plot[~(df_plot['type'] == '-')]

        df_plot['s_timestamp'] = pd.to_datetime(df_plot['s_timestamp'])
        df_plot['l_timestamp'] = pd.to_datetime(df_plot['l_timestamp'])
        
        fig = px.timeline(
            df_plot, 
            x_start="s_timestamp", 
            x_end="l_timestamp", 
            y="type",
            color="type", 
            hover_name="id_track",
            hover_data={
                "type": False, 
                "s_timestamp": True,
                "l_timestamp": True,
                "duration": True,
                "avg_speed": ":.2f",
                "min_dist": ":.2f"
            }
        )
        
        fig.update_yaxes(autorange="reversed") 
        
        # Make thin bars visible when looking at a wide date range
        for trace in fig.data:
            if trace.type == "bar":
                trace.marker.line.width = 1.1
                trace.marker.line.color = trace.marker.color
    else:
        fig = go.Figure()
        fig.update_yaxes(autorange="reversed")

    # Add Whale Detections
    if detections:
        det_times = []
        det_texts = []
        
        for d in detections:
            dt_val = pd.to_datetime(d["timestamp"], utc=True)
            conf = round(d.get("confidence", 0), 2)
            loc = d.get("location", {}).get("name", "Unknown")
            comments = d.get("comments", "") or "No comments"
            
            det_times.append(dt_val)
            det_texts.append(
                f"<b>Whale Bout Detection</b><br>"
                f"<b>Time:</b> {dt_val.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"<b>Confidence:</b> {conf}%<br>"
                f"<b>Location:</b> {loc}<br>"
                f"<b>Comments:</b> {comments}<br>"
            )
            
        # Add the detections as a specific scatter line on a dedicated Y-category
        fig.add_trace(go.Scatter(
            x=det_times,
            y=["Whale Detections"] * len(det_times),
            mode='markers+lines',
            line=dict(color="#00E5FF", width=2, dash="dot"),
            marker=dict(symbol="diamond", size=12, color="#00E5FF", line=dict(color='white', width=1)),
            name="Whale Detections",
            text=det_texts,
            hoverinfo="text"
        ))


    fig.update_layout(
        title={
            "text":"Ship Passages & Whale Detections vs Time",
            'y': 1,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font':dict(
                family="Courier New, monospace",
                size=18,
                color="#F8FAFC"
                )
            },
        xaxis_title="Time (UTC)",
        yaxis_title="Vessel Type",
        xaxis=dict(type='date'),
        showlegend=True,
        legend_title_text="Vessel Category",
        hovermode="closest",
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=450,
        font=dict(
            family="Courier New, monospace",
            size=14,
            color="#F8FAFC"
        ),
        hoverlabel=dict(
        bgcolor="white",
        font_size=16,
        font_family="Rockwell"
        ),
        clickmode="event"
    )

    return fig






def plot_combined_broadband(df_full, df_srkw, df_ship, title="Combined Broadband Metrics"):
    """
    Plots Full Range, SRKW, and Ship Noise broadband metrics on a single graph.
    """
    fig = go.Figure()

    # Helper function to extract time/value and add trace
    def add_trace(df, name, color):
        if df is not None and not df.empty:
            df = df.copy()
            time_col = "__index_level_0__"
            
            # Ensure timestamp is a column
            if time_col not in df.columns:
                if df.index.name == time_col or isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()
            
            # Extract data and plot
            if time_col in df.columns:
                val_cols = [c for c in df.columns if c != time_col]
                if val_cols:
                    fig.add_trace(go.Scatter(
                        x=df[time_col], y=df[val_cols[0]],
                        mode='lines', name=name,
                        line=dict(color=color, width=1.5)
                    ))

    # Add the three lines with distinct colors
    add_trace(df_full, "Full Range (1-16000 Hz)", "#B0BEC5") # Light gray
    add_trace(df_srkw, "SRKW Band (1-6 kHz)", "#00E5FF")     # Cyan
    add_trace(df_ship, "Ship Noise (10-500 Hz)", "#FF5252")  # Red / Orange

    fig.update_layout(
        margin=dict(l=40, r=20, t=40, b=30),
        xaxis_title="Time (UTC)",
        yaxis_title="Power (dB)",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e0e0e0"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Optional: If all traces fail, add an annotation
    if not fig.data:
        fig.add_annotation(text="No broadband data available", showarrow=False)

    return fig
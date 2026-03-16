import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


from plotly.subplots import make_subplots




from dashboard_utils import (
    DISPLAY_TZ_NAME,
    localize_series_to_pacific,
    parse_source_timestamp,
)


def plot_spectrogram(df, title="Orcasound Ambient Sound Analysis", ship_df=None):
    if df is None or df.empty:
        return go.Figure()

    fig = go.Figure()
    df_small = df.copy()

    if "ind" not in df_small.columns:
        fig.add_annotation(text="No acoustic time column 'ind' found", showarrow=False)
        return fig

    valid_freq_cols = [c for c in df_small.columns if str(c).replace(".", "", 1).isdigit()]
    valid_freq_cols.sort(key=lambda x: float(str(x)))

    z_data = df_small[valid_freq_cols].T.values
    z_data = np.where(z_data == -100, np.nan, z_data)

    x_axis = localize_series_to_pacific(df_small["ind"])
    y_axis = [float(c) for c in valid_freq_cols]

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
        colorscale="Viridis",
        zmin=zmin,
        zmax=zmax,
        colorbar=dict(
            title="",
            tickmode="array",
            tickvals=[zmin, zmax],
            ticktext=["Quiet", "Loud"],
            ticks=""
        ),
        hoverinfo="skip",
        name="PSD Heatmap"
    ))

    start_view = x_axis.min() if len(x_axis) else pd.Timestamp.min.tz_localize("America/Los_Angeles")
    end_view = x_axis.max() if len(x_axis) else pd.Timestamp.max.tz_localize("America/Los_Angeles")

    fig.update_layout(
        title=title,
        yaxis_title="Frequency - Log Scale (Hz)",
        yaxis_type="log",
        xaxis_title=f"Time ({DISPLAY_TZ_NAME})",
        height=650,
        hovermode="closest", 
        margin=dict(l=60, r=20, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        
        font=dict(
            family="Garamond",
            color="#F8FAFC",
            size=13
        ),
        
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.95)", 
            font_size=13,
            font_family="Garamond",
            font_color="#F8FAFC",
            bordercolor="#FF5252" 
        )
    )
    if ship_df is not None and not ship_df.empty:
        relevant_ships = ship_df[
            (ship_df["s_timestamp"] <= end_view) &
            (ship_df["l_timestamp"] >= start_view)
        ].copy()

        relevant_ships = relevant_ships.sort_values("s_timestamp")
        lanes = [] 

        top_log = np.log10(max_freq)
        block_thickness = 0.04  
        gap_thickness = 0.015   

        for _, ship in relevant_ships.iterrows():
            actual_entry = ship["s_timestamp"]
            actual_exit = ship["l_timestamp"]

            plot_entry = max(actual_entry, start_view)
            plot_exit = min(actual_exit, end_view)

            if plot_entry >= plot_exit:
                continue

            assigned_lane = 0
            for i, lane_end in enumerate(lanes):
                if plot_entry > lane_end:
                    assigned_lane = i
                    lanes[i] = plot_exit
                    break
            else:
                assigned_lane = len(lanes)
                lanes.append(plot_exit)

            lane_top_log = top_log - (assigned_lane * (block_thickness + gap_thickness))
            lane_bottom_log = lane_top_log - block_thickness
            
            y_top = 10 ** lane_top_log
            y_bottom = 10 ** lane_bottom_log

            # 1. Clean Ship Type
            ship_type_raw = str(ship.get("type", "Unknown")).replace("_", " ").title()
            if ship_type_raw.lower() in ["none", "unknown", "nan", "-"]:
                ship_type = "Not a Listed Type of Ship"
            else:
                ship_type = ship_type_raw

            # 2. Format Times natively 
            start_str = actual_entry.strftime("%H:%M")
            end_str = actual_exit.strftime("%H:%M")
            
            # Platform-safe date formatting (e.g., "4 March")
            date_str = f"{actual_entry.day} {actual_entry.strftime('%B')}"

            # 3. Formatted Metrics with Placeholders
            speed_val = ship.get("avg_speed")
            speed_str = f"{round(speed_val, 1)} kts" if pd.notna(speed_val) else "Not available"

            draft_val = ship.get("draft")
            draft_str = f"{round(draft_val, 1)} m" if pd.notna(draft_val) else "Not available"

            comm_val = ship.get("comm_bb_q50")
            comm_str = f"{round(comm_val, 2)} dB" if pd.notna(comm_val) else "Not available"

            # Rebuilt Hover String for maximum privacy and readability
            hover_details = (
                f"<b>Passage:</b> {start_str} to {end_str} on {date_str} ({DISPLAY_TZ_NAME})<br>"
                f"<b>Type:</b> {ship_type}<br>"
                f"<b>Average Speed:</b> {speed_str} | <b>Draft:</b> {draft_str}<br>"
                f"<b>Comm Band Noise (q50):</b> {comm_str}"
            )

            # Draw the faint red column
            fig.add_vrect(
                x0=plot_entry, x1=plot_exit,
                fillcolor="rgba(255, 82, 82, 0.08)", 
                layer="above", 
                line_width=1, 
                line_dash="dash", 
                line_color="rgba(255, 82, 82, 0.3)"
            )

            # Draw the solid block and force the hover tooltip
            fig.add_trace(go.Scatter(
                x=[plot_entry, plot_entry, plot_exit, plot_exit, plot_entry],
                y=[y_bottom, y_top, y_top, y_bottom, y_bottom],
                fill="toself",
                fillcolor="rgba(255, 82, 82, 0.8)",
                mode="lines",
                line=dict(color="#FFFFFF", width=0.5),
                name=hover_details,
                hoverinfo="name",
                hoverlabel=dict(namelength=-1),
                hoveron="fills",
                showlegend=False
            ))

    safe_min_freq = max(10, min_freq)
    fig.update_yaxes(range=[np.log10(safe_min_freq), np.log10(max_freq)])
    fig.update_xaxes(range=[start_view, end_view])

    return fig


def create_ship_timeline_with_detections(ship_df, detections):
    """
    Generates a Gantt chart grouped by ship type and overlays whale detections.
    Everything is shown in Pacific time with custom, privacy-focused tooltips.
    """
    if ship_df is not None and not ship_df.empty:
        df_plot = ship_df.copy()

        if "type" not in df_plot.columns:
            df_plot["type"] = "Not a Listed Type"
        else:
            df_plot["type"] = df_plot["type"].fillna("Not a Listed Type")

        df_plot = df_plot[~(df_plot["type"] == "-")]

        df_plot["s_timestamp"] = localize_series_to_pacific(df_plot["s_timestamp"])
        df_plot["l_timestamp"] = localize_series_to_pacific(df_plot["l_timestamp"])

        # --- Custom Hover String Generator ---
        def format_gantt_hover(row):
            actual_entry = row["s_timestamp"]
            actual_exit = row["l_timestamp"]
            
            start_str = actual_entry.strftime("%H:%M")
            end_str = actual_exit.strftime("%H:%M")
            date_str = f"{actual_entry.day} {actual_entry.strftime('%B')}"
            
            speed_val = row.get("avg_speed")
            speed_str = f"{round(speed_val, 1)} kts" if pd.notna(speed_val) else "Not available"
            
            draft_val = row.get("draft")
            draft_str = f"{round(draft_val, 1)} m" if pd.notna(draft_val) else "Not available"
            
            dist_val = row.get("min_dist")
            dist_str = f"{round(dist_val, 1)} m" if pd.notna(dist_val) else "Not available"
            
            # Formats exactly to your specifications, omitting IDs/MMSIs
            return (
                f"<b>Type:</b> {row['type']}<br>"
                f"<b>Passage:</b> {start_str} to {end_str} on {date_str} ({DISPLAY_TZ_NAME})<br>"
                f"<b>Average Speed:</b> {speed_str}<br>"
                f"<b>Draft:</b> {draft_str}<br>"
                f"<b>Closest approach to hydrophone:</b> {dist_str}"
            )
        
        # Apply the formatter to create a new column specifically for tooltips
        df_plot["custom_hover"] = df_plot.apply(format_gantt_hover, axis=1)

        fig = px.timeline(
            df_plot,
            x_start="s_timestamp",
            x_end="l_timestamp",
            y="type",
            color="type",
            custom_data=["custom_hover"] # Tells Plotly Express to load our HTML column
        )

        fig.update_yaxes(autorange="reversed")

        # Force all ship blocks to ONLY use our custom HTML, dropping the default box
        fig.update_traces(
            hovertemplate="%{customdata[0]}<extra></extra>"
        )

        for trace in fig.data:
            if trace.type == "bar":
                trace.marker.line.width = 1.1
                trace.marker.line.color = trace.marker.color
    else:
        fig = go.Figure()
        fig.update_yaxes(autorange="reversed")

    if detections:
        det_times = []
        det_texts = []

        for d in detections:
            dt_val = parse_source_timestamp(d["timestamp"])
            conf = round(d.get("confidence", 0), 2)
            loc = d.get("location", {}).get("name", "Unknown")
            comments = d.get("comments", "") or "No comments"

            det_times.append(dt_val)
            det_texts.append(
                f"<b>Whale Bout Detection</b><br>"
                f"<b>Time:</b> {dt_val.strftime('%H:%M:%S')} on {dt_val.day} {dt_val.strftime('%B')} ({DISPLAY_TZ_NAME})<br>"
                f"<b>Confidence:</b> {conf}%<br>"
                f"<b>Location:</b> {loc}<br>"
                f"<b>Comments:</b> {comments}<br>"
            )

        fig.add_trace(go.Scatter(
            x=det_times,
            y=["Whale Detections"] * len(det_times),
            mode="markers+lines",
            line=dict(color="#00E5FF", width=2, dash="dot"),
            marker=dict(symbol="diamond", size=12, color="#00E5FF", line=dict(color="white", width=1)),
            name="Whale Detections",
            text=det_texts,
            hovertemplate="%{text}<extra></extra>", # Added this so whales also match the clean style!
            hoverinfo="text"
        ))

    fig.update_layout(
        title={
            "text": "Ship Passages & Whale Detections vs Time",
            "y": 1,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": dict(
                family="'Inter', -apple-system, sans-serif",
                size=18,
                color="#F8FAFC"
            )
        },
        xaxis_title=f"Time ({DISPLAY_TZ_NAME})",
        yaxis_title="Vessel Type",
        xaxis=dict(type="date"),
        showlegend=True,
        legend_title_text="Vessel Category",
        hovermode="closest",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=450,
        font=dict(
            family="'Inter', -apple-system, sans-serif",
            size=14,
            color="#F8FAFC"
        ),
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.95)",
            font_size=13,
            font_family="'Inter', -apple-system, sans-serif",
            bordercolor="#00E5FF"
        ),
        clickmode="event"
    )

    return fig

def plot_combined_broadband(df_bb, title="Combined Broadband Metrics"):

    fig = go.Figure()

    if df_bb is None or df_bb.empty:
        fig.add_annotation(
            text="No broadband data available", 
            showarrow=False,
            font=dict(family="'Inter', -apple-system, sans-serif", color="#F8FAFC")
        )
        return fig

    df_bb = df_bb.copy()

    if "ind" not in df_bb.columns:
        fig.add_annotation(
            text="No broadband time column ('ind') found", 
            showarrow=False,
            font=dict(family="'Inter', -apple-system, sans-serif", color="#F8FAFC")
        )
        return fig

    x_vals = localize_series_to_pacific(df_bb["ind"])

    series_map = [
        ("bb", "Full Range", "#B0BEC5"),
        ("comm_bb", "SRKW Band", "#00E5FF"),
        ("ship_bb", "Ship Noise", "#FF5252"),
    ]

    for col, label, color in series_map:
        if col in df_bb.columns:
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=df_bb[col],
                mode="lines",
                name=label,
                line=dict(color=color, width=1.5)
            ))

    fig.update_layout(
        title={
            "text": title,
            "font": dict(
                family="'Inter', -apple-system, sans-serif",
                size=18,
                color="#F8FAFC"
            )
        },
        margin=dict(l=40, r=20, t=40, b=30),
        xaxis_title=f"Time ({DISPLAY_TZ_NAME})",
        yaxis_title="Power (dB)",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",

        font=dict(
            family="'Inter', -apple-system, sans-serif", 
            size=14,
            color="#F8FAFC"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(family="'Inter', -apple-system, sans-serif")
        ),
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.95)",
            font_size=13,
            font_family="'Inter', -apple-system, sans-serif",
            bordercolor="#00E5FF"
        ),
    )

    if not fig.data:
        fig.add_annotation(
            text="No broadband data available", 
            showarrow=False,
            font=dict(family="'Inter', -apple-system, sans-serif", color="#F8FAFC")
        )

    return fig




# def create_poster_composite_fig(ship_df, detections, bb_df):
#     """
#     Generates a pristine, white-background composite graph for poster export.
#     Fonts, line weights, and markers are massively scaled up for high-visibility print.
#     """
#     fig = make_subplots(
#         rows=2, cols=1,
#         shared_xaxes=True,
#         vertical_spacing=0.04,
#         row_heights=[0.35, 0.65]
#     )

#     # --- 1. Top Row: Broadband (Floating, No Shadow) ---
#     if bb_df is not None and not bb_df.empty and "ind" in bb_df.columns:
#         x_vals = localize_series_to_pacific(bb_df["ind"])
#         y_vals = bb_df["bb"] if "bb" in bb_df.columns else bb_df.iloc[:, 1]
        
#         y_vals = y_vals.replace(0.0, np.nan)
#         y_vals = y_vals.where(y_vals >= -10, np.nan)

#         fig.add_trace(
#             go.Scatter(
#                 x=x_vals, y=y_vals,
#                 mode='lines',
#                 line=dict(color='#8B5CF6', width=4), # Doubled line width for print visibility
#                 name="Broadband",
#                 showlegend=False,
#                 hoverinfo="skip"
#             ),
#             row=1, col=1
#         )

#     # --- 2. Bottom Row: Ships ---
#     all_categories = []
#     if ship_df is not None and not ship_df.empty:
#         df_plot = ship_df.copy()
        
#         df_plot["type"] = df_plot.get("type", "Not a Listed Type").fillna("Not a Listed Type")
#         df_plot = df_plot[~(df_plot["type"] == "-")]
#         df_plot["type"] = df_plot["type"].astype(str).str.replace("_", " ").str.title()
        
#         df_plot["s_timestamp"] = localize_series_to_pacific(df_plot["s_timestamp"])
#         df_plot["l_timestamp"] = localize_series_to_pacific(df_plot["l_timestamp"])

#         color_map = {
#             "Not A Listed Type": "#6366f1",
#             "Cargo": "#10b981",
#             "Tanker": "#f59e0b",
#             "Passenger": "#ec4899",
#             "Tug": "#06b6d4"
#         }
#         fallback_palette = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#8b5cf6"]
#         types = sorted(df_plot["type"].unique())

#         for i, t in enumerate(types):
#             c = color_map.get(t, fallback_palette[i % len(fallback_palette)])
#             df_t = df_plot[df_plot["type"] == t]
            
#             for _, row in df_t.iterrows():
#                 fig.add_trace(
#                     go.Scatter(
#                         x=[row["s_timestamp"], row["l_timestamp"]],
#                         y=[t, t],
#                         mode='lines',
#                         line=dict(color=c, width=32), # Massively thickened the Gantt bars
#                         showlegend=False,
#                         hoverinfo="skip"
#                     ),
#                     row=2, col=1
#                 )
#             fig.add_trace(
#                 go.Scatter(
#                     x=[None], y=[None], mode='markers',
#                     marker=dict(color=c, symbol='square', size=22), # Scaled up legend markers
#                     name=t
#                 ),
#                 row=2, col=1
#             )
#             all_categories.append(t)

#     # --- 3. Bottom Row: Whale Detections ---
#     if detections:
#         all_categories.append("Whale Detections")
#         det_times = [parse_source_timestamp(d["timestamp"]) for d in detections]
#         fig.add_trace(
#             go.Scatter(
#                 x=det_times,
#                 y=["Whale Detections"] * len(det_times),
#                 mode='markers',
#                 marker=dict(symbol='diamond', size=26, color='#00E5FF', line=dict(color='black', width=2)), # Giant diamonds
#                 name="Whale Detections"
#             ),
#             row=2, col=1
#         )

#     # --- 4. Layout & Spacing (POSTER SCALE) ---
#     fig.update_layout(
#         template="none",
#         plot_bgcolor='#FFFFFF',
#         paper_bgcolor='#FFFFFF',
        
#         font=dict(family="'Inter', sans-serif", color="#1e293b", size=20), # Increased base font
        
#         title=dict(
#             text="<b>Composite View: Broadband, Ship Passages, Whale Detections</b>",
#             font=dict(family="'Montserrat', sans-serif", color="#0f172a", size=38), # Massive title font
#             x=0.5,
#             y=0.96
#         ),
        
#         height=850, # Increased total canvas height so thick bars and big text don't overlap
#         margin=dict(l=40, r=40, t=120, b=120), # Expanded margins
#         showlegend = False
#         # legend=dict(font=dict(family="'Inter', sans-serif", color="#1e293b", size=22), orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1)
#     )

#     # --- 5. Clean Axes Formatting ---
#     # TOP ROW: completely invisible
#     fig.update_xaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False, row=1, col=1)
#     fig.update_yaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False, title="", row=1, col=1)

#     # BOTTOM ROW: visible axes with dashed grid
#     fig.update_xaxes(
#         showgrid=True, gridcolor='rgba(148, 163, 184, 0.3)', griddash='dash',
#         zeroline=False, showline=True, linecolor='#334155', linewidth=3, 
#         tickfont=dict(family="'Inter', sans-serif", color='#334155', size=20), # Massive tick labels
#         title=dict(text=f"Time ({DISPLAY_TZ_NAME})", font=dict(family="'Inter', sans-serif", color="#0f172a", size=26), standoff=30), # Massive axis title
#         type='date', range=["2026-03-03 00:00:00", "2026-03-09 00:00:00"], 
#         row=2, col=1
#     )
    
#     if all_categories:
#         fig.update_yaxes(
#             showgrid=True, gridcolor='rgba(148, 163, 184, 0.15)', 
#             zeroline=False, showline=True, linecolor='#334155', linewidth=3, 
#             tickfont=dict(family="'Inter', sans-serif", color='#334155', size=20), # Massive tick labels
#             title=dict(text="Vessel Category", font=dict(family="'Inter', sans-serif", color="#0f172a", size=26), standoff=30), # Massive axis title
#             type='category', categoryorder='array', categoryarray=all_categories[::-1], 
#             automargin=True, 
#             row=2, col=1
#         )

#     return fig
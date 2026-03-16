from datetime import datetime, date, timedelta
import pandas as pd

import pandas as pd
import plotly.graph_objects as go

DISPLAY_TZ_NAME = "PST"

def get_true_date(val):

    if isinstance(val, datetime):
        return val.date()
    return val





def sanitize_taipy_date(dt_val):
    
    if isinstance(dt_val, datetime):
        return dt_val.date()
    return dt_val








def parse_source_timestamp(ts):

    ts = pd.Timestamp(ts)
    if pd.isna(ts):
        return pd.NaT
    
    # Strip any attached timezone info to keep it purely naive (PST)
    return ts.tz_localize(None)









def localize_series_to_pacific(values):

    parsed = pd.to_datetime(values, errors="coerce")
    
    if isinstance(parsed, pd.Series):
        return parsed.dt.tz_localize(None)
        
    idx = pd.DatetimeIndex(parsed)
    return idx.tz_localize(None)









def parse_detections_to_markdown(detections_list):
    """
    Takes raw OrcaHello detection JSON and formats it into markdown.
    """
    if not detections_list:
        return "_No confirmed whale calls found for this period._"

    md_content = f"**Confirmed Detections ({len(detections_list)})**\n\n"

    for i, d in enumerate(detections_list, 1):
        # Time is treated as PST natively
        d_time = parse_source_timestamp(d["timestamp"])
        d_time_str = f"{d_time.strftime('%H:%M:%S on %d %b')} {DISPLAY_TZ_NAME}"

        confidence = round(d.get("confidence", 0), 2)
        location = d.get("location", {}).get("name", "Unknown Location")

        audio_url = d.get("audioUri", "")
        spec_url = d.get("spectrogramUri", "")

        audio_link = f"[Listen to Audio]({audio_url})" if audio_url else ""
        spec_link = f"[Download Spectrogram]({spec_url})" if spec_url else ""
        media_links = " | ".join(filter(None, [audio_link, spec_link])) or "No media"

        md_content += f"* **Detection {i}** - {d_time_str}\n"
        md_content += f"  * **Location:** {location}\n"
        md_content += f"  * **AI Confidence:** {confidence}%\n"
        md_content += f"  * **Media:** {media_links}\n\n"
        md_content += "---\n\n"

    return md_content









def generate_ship_summary_df(ship_df):
    """
    Groups raw ship tracking data by vessel type and calculates summary metrics.
    """
    if ship_df is None or ship_df.empty:
        return pd.DataFrame(
            columns=["Type of Ship", "Number of Observations", "Avg Length of Passage", "Avg Speed"]
        )

    df = ship_df.copy()

    if "type" not in df.columns:
        df["type"] = "Not a Listed Type"
    else:
        df["type"] = df["type"].fillna("Not a Listed Type")
        df["type"] = df["type"].replace(["Unknown Vessel", "unknown"], "Not a Listed Type")

    df = df[~(df["type"] == "-")]

    summary = df.groupby("type").agg(
        count=("id_track", "count"),
        avg_duration=("duration", "mean"),
        avg_speed=("avg_speed", "mean")
    ).reset_index()

    summary = summary.sort_values(by="count", ascending=False)

    def format_type(t):
        if t == "Not a Listed Type":
            return t
        return str(t).replace("_", " ").title()

    summary["type"] = summary["type"].apply(format_type)
    summary["avg_duration"] = summary["avg_duration"].apply(
        lambda x: f"{round(x / 60, 1)} mins" if pd.notna(x) else "0 mins"
    )
    summary["avg_speed"] = summary["avg_speed"].apply(
        lambda x: f"{round(x, 2)} knots" if pd.notna(x) else "0 knots"
    )

    summary = summary.rename(columns={
        "type": "Type of Ship",
        "count": "Number of Observations",
        "avg_duration": "Avg Length of Passage",
        "avg_speed": "Avg Speed"
    })

    return summary










def make_empty_figure(message):

    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>{message}</b>",
        showarrow=False,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        font=dict(size=18, color="#94A3B8", family="'Inter', sans-serif")
    )
    fig.update_layout(
        height=650, 
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),

        paper_bgcolor="rgba(30, 41, 59, 0.4)", 
        plot_bgcolor="rgba(30, 41, 59, 0.4)",
        margin=dict(l=0, r=0, t=0, b=0)
    )
    return fig







def reset_acoustic_figures(state, message="No data available"):
    """
    Clears the spectrogram and broadband charts.
    """
    state.spectrogram_fig = make_empty_figure(message)
    state.combined_bb_fig = make_empty_figure(message)











def _normalize_local_timestamp(ts):
    """
    Normalize a single timestamp to Pacific-aware.
    """
    return parse_source_timestamp(ts)








def build_ship_psd_window(start_time, end_time):
    """
    Calculates top-of-hour boundaries for ship PSD fetches, in Pacific time.
    """
    start_ts = _normalize_local_timestamp(start_time)
    end_ts = _normalize_local_timestamp(end_time)

    window_start = start_ts.floor("h")
    window_end = end_ts.ceil("h")

    if window_end <= window_start:
        window_end = window_start + pd.Timedelta(hours=1)

    return window_start, window_end















def extract_ship_id_from_table_payload(state, payload):
    """
    Uses the Taipy table payload to get the clicked Track ID safely,
    accounting for column renaming.
    """
    payload = payload or {}

    for key in ("row", "data", "value"):
        row_obj = payload.get(key)
        if isinstance(row_obj, dict):
            if row_obj.get("Track ID") is not None:
                return str(row_obj["Track ID"])
            if row_obj.get("id_track") is not None:
                return str(row_obj["id_track"])

    row_index = payload.get("index")
    if row_index is not None and not state.display_leaderboard_df.empty:
        working_df = state.display_leaderboard_df.reset_index(drop=True)
        if 0 <= row_index < len(working_df):
            return str(working_df.iloc[row_index].get("Track ID", working_df.iloc[row_index].get("id_track")))

    return None









def calculate_masking_percentage(start_dt, end_dt, ship_df):
    """
    Computes the percentage of a given time window that is masked by overlapping ship passages.
    """
    if ship_df is None or ship_df.empty:
        return 0.0

    # Simplified: Direct subtraction of naive datetimes
    total_window_seconds = (end_dt - start_dt).total_seconds()
    
    if total_window_seconds <= 0:
        return 0.0

    df = ship_df.copy()
    df["s_timestamp"] = df["s_timestamp"].clip(lower=start_dt)
    df["l_timestamp"] = df["l_timestamp"].clip(upper=end_dt)

    df = df[df["s_timestamp"] < df["l_timestamp"]].copy()
    if df.empty:
        return 0.0

    df = df.sort_values("s_timestamp")

    merged_intervals = []
    current_start = df.iloc[0]["s_timestamp"]
    current_end = df.iloc[0]["l_timestamp"]

    for _, row in df.iloc[1:].iterrows():
        if row["s_timestamp"] <= current_end:
            current_end = max(current_end, row["l_timestamp"])
        else:
            merged_intervals.append((current_start, current_end))
            current_start = row["s_timestamp"]
            current_end = row["l_timestamp"]

    merged_intervals.append((current_start, current_end))

    total_masked_seconds = sum((end - start).total_seconds() for start, end in merged_intervals)
    return round((total_masked_seconds / total_window_seconds) * 100.0, 2)
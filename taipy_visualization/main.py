from datetime import datetime, timedelta, date, time
import time as time_lib

import pandas as pd
import taipy.gui.builder as tgb
from taipy.gui import Gui, navigate, Icon

from data_utils import (
    load_ship_data,
    get_available_hours_map,
    fetch_detections,
    fetch_psd_window,
    fetch_bb_window,
)

from plot_utils import plot_spectrogram, plot_combined_broadband, create_ship_timeline_with_detections

from orcasound_noise.utils.hydrophone import Hydrophone
from orcasound_noise.analysis.metrics.ship_metrics import get_ship_metrics_df

from dashboard_utils import (
    DISPLAY_TZ_NAME,
    get_true_date,
    parse_source_timestamp,
    parse_detections_to_markdown,
    generate_ship_summary_df,
    make_empty_figure,
    reset_acoustic_figures,
    build_ship_psd_window,
    extract_ship_id_from_table_payload,
    calculate_masking_percentage,
    localize_series_to_pacific,
)

class HydrophoneProxy:

    def __init__(self, base_enum, new_folder):
        class MockValue:
            def __init__(self, val):
                self.name = val.name
                self.save_bucket = val.save_bucket
                self.save_folder = new_folder
        
        self.value = MockValue(base_enum.value)

HYDROPHONE = HydrophoneProxy(Hydrophone.ORCASOUND_LAB, "ambient-sound-analysis/data_3.0")

from dotenv import load_dotenv
load_dotenv()

MIGRATION_START_DATE = date(2026, 3, 3)


# ---------------------------------------------------------------------------------------------------- #
# --------------------------------------- TAIPY CALLBACKS -------------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #

def on_init(state):
    """
    The initial setup callback, initializes tables, chart states, and default UI values.
    """
    rebuild_leaderboard_table(state)
    update_chart(state)




def on_menu(state, action, info):
    """
    Handles page routing when a user clicks a link in the dashboard's navigation menu.
    """
    page = info["args"][0]
    navigate(state, to=page)





def update_gantt_chart(state, var_name=None, var_value=None):
    """
    Refetch ship and whale data for the main timeline chart using PST natively.
    """
    true_start = get_true_date(state.gantt_start_date)
    true_end = get_true_date(state.gantt_end_date)

    state.gantt_start_date = true_start
    state.gantt_end_date = true_end

    # Use naive PST datetimes instead of tz_localize
    start_dt = pd.Timestamp(datetime.combine(true_start, time.min))
    end_dt = pd.Timestamp(datetime.combine(true_end, time.max))

    if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
        mask = (
            (GLOBAL_SHIP_DF["s_timestamp"] >= start_dt) &
            (GLOBAL_SHIP_DF["l_timestamp"] <= end_dt)
        )
        filtered_ships = GLOBAL_SHIP_DF[mask]
    else:
        filtered_ships = pd.DataFrame()

    api_start_dt = start_dt.date() - timedelta(days=1)
    api_end_dt = end_dt.date() + timedelta(days=1)

    raw_detections = fetch_detections(
        datetime.combine(api_start_dt, time.min),
        datetime.combine(api_end_dt, time.max)
    )

    valid_detections = []
    for d in raw_detections:
        d_time = parse_source_timestamp(d["timestamp"])
        if start_dt <= d_time <= end_dt:
            valid_detections.append(d)

    state.ship_and_detections = create_ship_timeline_with_detections(filtered_ships, valid_detections)
    state.detection_title = f"Bout Information ({true_start.strftime('%d %b %Y')} to {true_end.strftime('%d %b %Y')})"
    state.detection_partial.update_content(state, parse_detections_to_markdown(valid_detections))
    state.masking_percentage = calculate_masking_percentage(start_dt, end_dt, filtered_ships)
    state.ship_summary_df = generate_ship_summary_df(filtered_ships)
    
    
    state.detection_title = f"Bout Information ({true_start.strftime('%d %b %Y')} to {true_end.strftime('%d %b %Y')})"
    state.detection_partial.update_content(state, parse_detections_to_markdown(valid_detections))
    state.masking_percentage = calculate_masking_percentage(start_dt, end_dt, filtered_ships)
    state.ship_summary_df = generate_ship_summary_df(filtered_ships)






def update_date(state, var_name, var_value):
    """
    Triggered when the user picks a new date for sound analysis.
    """
    new_date = get_true_date(var_value)
    state.acoustic_date = new_date
    state.displayed_hour = None

    state.last_fetched_date = None
    state.last_fetched_hour = None
    state.pd_acoustic_data_cache = pd.DataFrame()

    if new_date < MIGRATION_START_DATE:
        state.hours_of_data = ["No migrated data for this date"]
        state.displayed_hour = "No migrated data for this date"
        state.spectrogram_title = f"PSD for **{new_date.strftime('%Y-%m-%d')}** *( No migrated data available )*"
        reset_acoustic_figures(state, "Migrated acoustic data starts on 2026-03-03")
        return

    new_hours = get_available_hours_map(new_date.month, new_date.day, HYDROPHONE, new_date.year)

    if not new_hours:
        state.hours_of_data = ["No data for this date"]
        state.displayed_hour = "No data for this date"
        state.spectrogram_title = f"PSD for **{new_date.strftime('%Y-%m-%d')}** *( No data available )*"
        reset_acoustic_figures(state, "No acoustic data available for selected date")
    else:
        state.hours_of_data = new_hours
        state.displayed_hour = new_hours[0]
        update_chart(state)








def on_gantt_click(state, id, payload):
    """
    Clicking a whale detection jumps the acoustic view to that local Pacific hour.
    Safely handles dates prior to the data migration or dates with missing acoustic files.
    """
    print(f"\n[CLICK EVENT] Payload received: {payload}")

    current_time = time_lib.time()
    if current_time - state.last_click_time < 1.5:
        return
    state.last_click_time = current_time

    try:
        if isinstance(payload, dict) and "x" in payload and "y" in payload:
            if payload.get("y") == "Whale Detections":
                clicked_time = parse_source_timestamp(payload.get("x"))
                print(f"[CLICK EVENT] Processing Whale Detection at {clicked_time}...")

                # Extract date safely
                clicked_date = clicked_time.date()
                state.acoustic_date = clicked_date

                # 1. Handle dates prior to the migration cutoff
                if clicked_date < MIGRATION_START_DATE:
                    state.hours_of_data = ["No migrated data for this date"]
                    state.displayed_hour = "No migrated data for this date"
                
                # 2. Fetch hours for valid dates
                else:
                    new_hours = get_available_hours_map(
                        clicked_time.month,
                        clicked_time.day,
                        HYDROPHONE,
                        clicked_time.year
                    )
                    
                    # 3. Handle dates that are valid, but have no S3 files
                    if not new_hours:
                        state.hours_of_data = ["No data for this date"]
                        state.displayed_hour = "No data for this date"
                    
                    # 4. Happy Path: Find the exact hour block for the detection
                    else:
                        state.hours_of_data = new_hours
                        target_hour_str = f"{clicked_time.hour:02d}:00"
                        matching_hour = next((h for h in new_hours if h.startswith(target_hour_str)), None)
                        
                        if matching_hour:
                            state.displayed_hour = matching_hour
                        else:
                            state.displayed_hour = new_hours[0]

                # Reset cache and trigger UI update
                state.last_fetched_date = None
                state.last_fetched_hour = None
                state.pd_acoustic_data_cache = pd.DataFrame()

                print(f"[CLICK EVENT] Triggering chart update for {state.acoustic_date} at {state.displayed_hour}")
                update_chart(state)
            else:
                print(f"[CLICK EVENT] Ignored - clicked on '{payload.get('y')}'")
        else:
            print("[CLICK EVENT] Payload missing x/y keys.")

    except Exception as e:
        print(f"[CLICK EVENT] Critical Error during processing: {e}")







def update_chart(state, var_name=None, var_value=None):
    """
    Updates acoustic visualizations using the new PartitionedAccessor schema.
    """
    if not state.displayed_hour or state.displayed_hour in ("No data for this date", "No migrated data for this date"):
        state.spectrogram_title = "PSD for <No time selected>"
        reset_acoustic_figures(state, "No time selected")
        return

    try:
        start_str = state.displayed_hour.split(" to ")[0]
        selected_time = datetime.strptime(start_str, "%H:%M").time()

        safe_date = state.acoustic_date.date() if isinstance(state.acoustic_date, datetime) else state.acoustic_date
        
        # Naive PST setup
        pst_start = datetime.combine(safe_date, selected_time)
        pst_end_exclusive = pst_start + timedelta(hours=1)

        print(
            f"[CHART] Selected PST hour: {safe_date} {state.displayed_hour} | "
            f"Accessor window: {pst_start} -> {pst_end_exclusive}"
        )

        state.spectrogram_title = (
            f"PSD for **{safe_date.strftime('%Y-%m-%d')}** "
            f"*( {state.displayed_hour} {DISPLAY_TZ_NAME} )*"
        )

        time_changed = (
            state.last_fetched_date != state.acoustic_date
            or state.last_fetched_hour != state.displayed_hour
        )

        if state.last_fetched_hour is None or time_changed:
            pl_psd = fetch_psd_window(HYDROPHONE, pst_start, pst_end_exclusive)
            pl_bb = fetch_bb_window(HYDROPHONE, pst_start, pst_end_exclusive)

            if pl_psd is None or pl_psd.is_empty():
                print("Warning: Accessor returned empty PSD data for this window.")
                state.pd_acoustic_data_cache = pd.DataFrame()
                state.last_fetched_date = state.acoustic_date
                state.last_fetched_hour = state.displayed_hour
                reset_acoustic_figures(state, "No acoustic data available for selected hour")
                return

            pd_psd = pl_psd.to_pandas()
            pd_bb = pl_bb.to_pandas() if pl_bb is not None and not pl_bb.is_empty() else pd.DataFrame()

            try:
                new_combined_fig = plot_combined_broadband(pd_bb)
            except Exception as e:
                print(f"Broadband error: {e}")
                new_combined_fig = make_empty_figure("Broadband plot error")

            if pd_psd.empty:
                new_spec_fig = make_empty_figure("No acoustic data available for selected hour")
            else:
                # Update these two lines:
                is_showing = (state.show_ship_overlay == "Show Ship Overlays")
                ship_data = GLOBAL_SHIP_DF if is_showing else None
                
                new_spec_fig = plot_spectrogram(
                    pd_psd,
                    "Spectrogram",
                    ship_df=ship_data
                )

            with state as s:
                s.pd_acoustic_data_cache = pd_psd
                s.combined_bb_fig = new_combined_fig
                s.spectrogram_fig = new_spec_fig
                s.last_fetched_date = s.acoustic_date
                s.last_fetched_hour = s.displayed_hour

    except Exception as e:
        print(f"Critical error in update_chart: {e}")
        reset_acoustic_figures(state, "Error loading data")
        state.spectrogram_title = "PSD for <Error>"






def on_ship_row_click(state, id, payload):
    """
    Captures clicks on the ship leaderboard table to fetch and display the detailed statistics and 
    acoustic signature for that specific vessel.
    """
    # First protect from too much clicking in the table causing the program to hang
    current_time = time_lib.time()
    if current_time - state.last_table_click_time < 1.5:
        print("[LEADERBOARD] Click ignored (debounced) to prevent UI freeze.")
        return
    state.last_table_click_time = current_time
    
    if state.display_leaderboard_df.empty:
        return

    ship_id = extract_ship_id_from_table_payload(state, payload)
    
    if ship_id is None:
        return

    print(f"[LEADERBOARD] Clicked ship id: {ship_id}")

    full_matches = GLOBAL_SHIP_DF[
        GLOBAL_SHIP_DF["id_track"].astype(str) == str(ship_id)
    ]

    if full_matches.empty:
        print(f"[LEADERBOARD] No full ship record found for id_track={ship_id}")
        return

    full_ship_data = full_matches.iloc[0]

    general_cols = ["avg_speed", "max_speed", "min_speed", "duration", "distance", "min_dist", "curviness", "draft", "confidence"]
    acoustic_cols = ["bb_avg", "bb_q50", "bb_q95", "comm_bb_avg", "comm_bb_q50", "comm_bb_q95", "ship_bb_avg", "ship_bb_q50", "ship_bb_q95"]


    def build_tab_df(cols, series):
        data = []
        for c in cols:
            if c in series and pd.notna(series[c]): 
                val = series[c]
                if isinstance(val, (float, int)):
                    val = round(val, 2)
                
                # Clean up the variable names for display
                name = c.replace("_", " ").title().replace("Bb", "BB").replace("Q", "Quantile ")
                data.append({"Metric": name, "Value": val})
        return pd.DataFrame(data, columns=["Metric", "Value"])


    stats_general_df = build_tab_df(general_cols, full_ship_data)
    stats_acoustic_df = build_tab_df(acoustic_cols, full_ship_data)

    start_time = parse_source_timestamp(full_ship_data["s_timestamp"])
    end_time = parse_source_timestamp(full_ship_data["l_timestamp"])

    window_start, window_end = build_ship_psd_window(start_time, end_time)

    print(
        f"[LEADERBOARD] Generating PSD for {ship_id} "
        f"from {window_start} to {window_end}"
    )

    try:
        pl_psd = fetch_psd_window(HYDROPHONE, window_start, window_end)

        if pl_psd is not None and not pl_psd.is_empty():
            new_psd_fig = plot_spectrogram(
                pl_psd.to_pandas()
            )
        else:
            print("[LEADERBOARD] No PSD rows found for this ship window.")
            new_psd_fig = make_empty_figure(
                "No acoustic data found for this ship passage window."
            )

    except Exception as e:
        print(f"[LEADERBOARD] Error loading PSD: {e}")
        new_psd_fig = make_empty_figure("Error loading acoustic data from S3.")

    # Safely extract and format Ship Type
    type_val = full_ship_data.get("type")
    if pd.isna(type_val) or type_val == "" or type_val == "-":
        type_str = "Not available"
    else:
        type_str = str(type_val).replace('_', ' ').title()

    # Format the exact passage times
    time_fmt = "%Y-%m-%d %H:%M:%S"
    passage_str = (
        f"{start_time.strftime(time_fmt)} to {end_time.strftime(time_fmt)} "
        f"({DISPLAY_TZ_NAME})"
    )

    formatted_title = (
        f"Visualizing Ship Track ID - {ship_id}\n\n"
        f"**Passage Duration** - {passage_str}  \n"
        f"**Type of Ship** - {type_str}"
    )

    with state as s:
        s.ship_details_title = formatted_title

        s.ship_stats_general_df = stats_general_df
        s.ship_stats_acoustic_df = stats_acoustic_df
        
        s.selected_ship_psd_fig = new_psd_fig
        s.ship_psd_chart_rebuild = not s.ship_psd_chart_rebuild
        s.psd_expanded = True
        s.stats_expanded = True






def toggle_ship_overlay(state, var_name, var_value):
    """
    Triggered when the user toggles the ship overlay switch. 
    Re-renders the spectrogram without hitting S3 to re-fetch the acoustic data.
    """
    if state.pd_acoustic_data_cache is None or state.pd_acoustic_data_cache.empty:
        return
        
    is_showing = (state.show_ship_overlay == "Show Ship Overlays")
    ship_data = GLOBAL_SHIP_DF if is_showing else None
    
    state.spectrogram_fig = plot_spectrogram(
        state.pd_acoustic_data_cache,
        "Spectrogram",
        ship_df=ship_data
    )


# ---------------------------------------------------------------------------------------------------- #
# ----------------------------------- Ship dataframe loading ----------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #


GLOBAL_SHIP_DF = None
try:
    GLOBAL_SHIP_DF = get_ship_metrics_df()
    if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
        GLOBAL_SHIP_DF["s_timestamp"] = localize_series_to_pacific(GLOBAL_SHIP_DF["s_timestamp"])
        GLOBAL_SHIP_DF["l_timestamp"] = localize_series_to_pacific(GLOBAL_SHIP_DF["l_timestamp"])
except Exception as e:
    print(f"Failed to load global ship data: {e}")
    GLOBAL_SHIP_DF = pd.DataFrame()

# --------------------------------------------------------------------------------------------------- #
# --------------------------------- Ship Leaderboard Setup ------------------------------------------ #
# --------------------------------------------------------------------------------------------------- #

LEADERBOARD_BASE_COLS = [
    "id_track", "s_timestamp", "l_timestamp", "type",
]

LEADERBOARD_METRIC_GROUPS = {
    "metric_speed": {"columns": ["avg_speed", "max_speed", "min_speed"]},
    "metric_duration_distance_path": {"columns": ["duration", "distance", "min_dist", "curviness", "draft"]},
    "metric_confidence": {"columns": ["confidence"]},
    "metric_comm_bb": {"columns": ["comm_bb_avg", "comm_bb_q05", "comm_bb_q25", "comm_bb_q50", "comm_bb_q75", "comm_bb_q95"]},
    "metric_overall_bb": {"columns": ["bb_avg", "bb_q05", "bb_q25", "bb_q50", "bb_q75", "bb_q95"]},
    "metric_ship_bb": {"columns": ["ship_bb_avg", "ship_bb_q05", "ship_bb_q25", "ship_bb_q50", "ship_bb_q75", "ship_bb_q95"]},
    "metric_isolated": {"columns": ["is_isolated"]},
}

leaderboard_metric_lov = [
    ("metric_speed", "Speed of vessels"),
    ("metric_duration_distance_path", "Duration, Distance, Draft, Path"),
    ("metric_confidence", "Confidence scores"),
    ("metric_comm_bb", "Communication broadband levels"),
    ("metric_overall_bb", "Overall broadband levels"),
    ("metric_ship_bb", "Ship broadband levels"),
    ("metric_isolated", "Isolated flag")
]

isolated_lov = [
    ("All", "All"), 
    ("Isolated", "Isolated Passages"), 
    ("Overlapping", "Overlapping Passages")
]

selected_leaderboard_metrics = []
selected_ship_type = "All"
selected_isolated = "All"
leaderboard_table_rebuild = False

if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty and "type" in GLOBAL_SHIP_DF.columns:
    unique_types = GLOBAL_SHIP_DF["type"].dropna().unique().tolist()
    clean_types = sorted(list(set([str(t).replace('_', ' ').title() for t in unique_types if t != '-'])))
    ship_type_lov = ["All"] + clean_types
else:
    ship_type_lov = ["All"]




def compute_visible_leaderboard_columns(active_metrics):
    if GLOBAL_SHIP_DF is None or GLOBAL_SHIP_DF.empty:
        return LEADERBOARD_BASE_COLS.copy()

    available_cols = set(GLOBAL_SHIP_DF.columns)
    final_cols = [col for col in LEADERBOARD_BASE_COLS if col in available_cols]

    if not isinstance(active_metrics, list):
        active_metrics = [active_metrics] if active_metrics else []

    for metric_item in active_metrics:
        metric_id = metric_item[0] if isinstance(metric_item, tuple) else metric_item
        if metric_id in LEADERBOARD_METRIC_GROUPS:
            for col in LEADERBOARD_METRIC_GROUPS[metric_id]["columns"]:
                if col in available_cols and col not in final_cols:
                    final_cols.append(col)
    
    return final_cols





def on_leaderboard_filter_change(state, var_name, var_value):

    if var_name == "selected_leaderboard_metrics":
        rebuild_leaderboard_table(state, active_metrics=var_value)

    elif var_name == "selected_ship_type":
        rebuild_leaderboard_table(state, active_type=var_value)
    
    elif var_name == "selected_isolated":
        rebuild_leaderboard_table(state, active_isolated=var_value)





def rebuild_leaderboard_table(state, active_metrics=None, active_type=None, active_isolated=None):
    metrics = active_metrics if active_metrics is not None else state.selected_leaderboard_metrics
    ship_type = active_type if active_type is not None else state.selected_ship_type
    isolated = active_isolated if active_isolated is not None else state.selected_isolated

    if GLOBAL_SHIP_DF is None or GLOBAL_SHIP_DF.empty:
        return

    visible_cols = compute_visible_leaderboard_columns(metrics)
    filtered_df = GLOBAL_SHIP_DF.copy()

    if ship_type != "All":
        formatted_series = filtered_df["type"].fillna("Not a Listed Type").astype(str).str.replace("_", " ").str.title()
        filtered_df = filtered_df[formatted_series == ship_type]

    if isolated == "Isolated":
        filtered_df = filtered_df[filtered_df["is_isolated"].astype(str).str.lower().isin(["true", "1", "1.0"])]
    elif isolated == "Overlapping":
        filtered_df = filtered_df[filtered_df["is_isolated"].astype(str).str.lower().isin(["false", "0", "0.0"])]

    display_df = filtered_df.copy().reset_index(drop=True)

    rename_map = {
        "id_track": "Track ID",
        "s_timestamp": "First Timestamp",
        "l_timestamp": "Last Timestamp",
        "type": "Ship Type"
    }
    display_df = display_df.rename(columns=rename_map)
    new_cols = [rename_map.get(c, c) for c in visible_cols]

    if "First Timestamp" in display_df.columns:
        display_df["First Timestamp"] = pd.to_datetime(display_df["First Timestamp"]).dt.strftime('%Y-%m-%d %H:%M:%S')
    if "Last Timestamp" in display_df.columns:
        display_df["Last Timestamp"] = pd.to_datetime(display_df["Last Timestamp"]).dt.strftime('%Y-%m-%d %H:%M:%S')

    numeric_cols = display_df.select_dtypes(include=['float', 'float64', 'float32']).columns
    for col in numeric_cols:
        display_df[col] = display_df[col].round(2)
    
    with state as s:
        s.selected_leaderboard_metrics = metrics
        s.selected_ship_type = ship_type
        s.selected_isolated = isolated
        
        s.display_leaderboard_df = display_df
        s.leaderboard_table_columns = new_cols







selected_leaderboard_metrics = []

metric_speed_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_duration_distance_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_confidence_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_comm_bb_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_overall_bb_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_ship_bb_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_isolated_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"

leaderboard_table_rebuild = False





if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
    display_leaderboard_df = GLOBAL_SHIP_DF.copy().reset_index(drop=True)

    rename_map = {
        "id_track": "Track ID",
        "s_timestamp": "First Timestamp",
        "l_timestamp": "Last Timestamp",
        "type": "Ship Type"
    }

    display_leaderboard_df = display_leaderboard_df.rename(columns=rename_map)
    numeric_cols = display_leaderboard_df.select_dtypes(include=['float', 'float64', 'float32']).columns
    for col in numeric_cols:
        display_leaderboard_df[col] = display_leaderboard_df[col].round(2)

    leaderboard_table_columns = ["Track ID", "First Timestamp", "Last Timestamp", "Ship Type"]

else:
    all_cols = ["Track ID", "First Timestamp", "Last Timestamp", "Ship Type"]
    for group in LEADERBOARD_METRIC_GROUPS.values():
        all_cols.extend(group["columns"])
        
    display_leaderboard_df = pd.DataFrame(columns=all_cols)
    leaderboard_table_columns = ["Track ID", "First Timestamp", "Last Timestamp", "Ship Type"]






selected_ship_psd_fig = make_empty_figure("Click a row in the table above to load acoustic signature")
selected_ship_stats_df = pd.DataFrame(columns=["Metric", "Value"])
ship_details_title = "Select a ship from the table"
psd_expanded = True
stats_expanded = True

ship_psd_chart_rebuild = False

selected_ship_tab = "Speed, Draft & Passage Info"
ship_tab_lov = ["Speed, Draft & Passage Info", "Acoustic Broadband"]

ship_stats_general_df = pd.DataFrame(columns=["Metric", "Value"])
ship_stats_acoustic_df = pd.DataFrame(columns=["Metric", "Value"])

data_dict_expanded = False

# --------------------------------------------------------------------------------------------------- #
# --------------------------- Ship Leaderboard Setup ends ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #






# --------------------------------------------------------------------------------------------------- #
# ---------------------------- Acoustic Chart Setup ------------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #


acoustic_date = date(2026, 3, 4)
gantt_start_date = date(2026, 3, 3)
gantt_end_date = date(2026, 3, 4)

hours_of_data = get_available_hours_map(
    acoustic_date.month,
    acoustic_date.day,
    HYDROPHONE,
    acoustic_date.year
)
displayed_hour = hours_of_data[0] if hours_of_data else None


start_dt_init = pd.Timestamp(datetime.combine(gantt_start_date, time.min))
end_dt_init = pd.Timestamp(datetime.combine(gantt_end_date, time.max))

if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
    mask = (
        (GLOBAL_SHIP_DF["s_timestamp"] >= start_dt_init) &
        (GLOBAL_SHIP_DF["l_timestamp"] <= end_dt_init)
    )
    init_ships = GLOBAL_SHIP_DF[mask]
else:
    init_ships = pd.DataFrame()

masking_percentage = calculate_masking_percentage(start_dt_init, end_dt_init, init_ships)

api_start_dt_init = start_dt_init.date() - timedelta(days=1)
api_end_dt_init = end_dt_init.date() + timedelta(days=1)

raw_dets_init = fetch_detections(
    datetime.combine(api_start_dt_init, time.min),
    datetime.combine(api_end_dt_init, time.max)
)

valid_dets_init = []
for d in raw_dets_init:
    d_time = parse_source_timestamp(d["timestamp"])
    if start_dt_init <= d_time <= end_dt_init:
        valid_dets_init.append(d)

ship_and_detections = create_ship_timeline_with_detections(init_ships, valid_dets_init)

initial_det_string = parse_detections_to_markdown(valid_dets_init)
ship_summary_df = generate_ship_summary_df(init_ships)
detection_title = f"Bout Information ({gantt_start_date.strftime('%d %b %Y')} to {gantt_end_date.strftime('%d %b %Y')})"

# Initializing Empty Plotly Figures and Cache Variables
spectrogram_fig = make_empty_figure("Select a date and time to load spectrogram")
combined_bb_fig = make_empty_figure("Select a date and time to load broadband data")

spectrogram_title = "PSD for <Select a date and time>"
pd_acoustic_data_cache = pd.DataFrame() 
last_fetched_date = None  
last_fetched_hour = None

last_click_time = 0.0
last_table_click_time = 0.0

show_ship_overlay = "Hide Ship Overlays"

menu_lov = [
    ("Dashboard", Icon("icon_images/home.png", "Home Page")),
    ("Ship-Leaderboard", Icon("icon_images/cargo-ship.png", "Ship Leaderboard"))
]


# ---------------------------------------------------------------------------------------------------- #
# ---------------------------------------- MAIN UI DEFINITION ---------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #

with tgb.Page() as root_page:
    tgb.menu(lov="{menu_lov}", on_action=on_menu)
    tgb.content()

with tgb.Page() as dashboard_page:
    with tgb.part(class_name="page-padding"):
        
        with tgb.part(class_name="hero-title center-align-text"):
            tgb.text("## **Orcasound** - Ambient Sound Analysis", mode="md")
            tgb.text("*Visualizing the ocean's soundscape: whales, ships, and ambient noise*", mode="md", class_name="secondary-text-color")
        
        with tgb.part(class_name="card-panel"):

            with tgb.layout(columns="1 2 10 2 1", class_name="align-columns-center bottom-padding"):

                tgb.part()

                tgb.part()
                
                with tgb.part(class_name="center-align-text"):
                    tgb.text("#### Select a time period to explore ship activity and whale detections", mode="md", class_name="inline-title")
                
                tgb.part()
                
                with tgb.part(class_name="right-align-text info-tooltip-container"):
                    tgb.image("taipy_visualization/icon_images/info.png", class_name="info-icon") 
                    
                    with tgb.part(class_name="info-tooltip-content"):
                        tgb.text("**Calculation**", mode="md", class_name="tooltip-heading")
                        tgb.text("Whales had interference for **{masking_percentage}%** of your chosen duration.", mode="md", class_name="tooltip-body")
                        
                        tgb.html("hr", class_name="tooltip-divider")
                        
                        tgb.text("**Info**", mode="md", class_name="tooltip-heading")
                        tgb.text("This is a low-end estimate based on the duration of ship passages. Acoustic masking lasts longer than the physical ship passage.", mode="md", class_name="tooltip-body")
            
            with tgb.layout(columns="2 1 1 2", class_name="center-align-text bottom-padding"):
                tgb.part()
                with tgb.part():
                    tgb.text("Start Date", class_name="form-label")
                    tgb.date("{gantt_start_date}", on_change=update_gantt_chart)
                with tgb.part():
                    tgb.text("End Date", class_name="form-label")
                    tgb.date("{gantt_end_date}", on_change=update_gantt_chart)
                with tgb.part():
                    tgb.text("") 

            tgb.chart(figure="{ship_and_detections}", on_click="on_gantt_click")
        
        with tgb.part(class_name="card-panel-secondary title-viz"):

            with tgb.layout(columns="1 2 10 2 1", class_name="align-columns-center bottom-padding"):
                tgb.part()
                tgb.part()
                
                with tgb.part(class_name="center-align-text"):
                    tgb.text("### Sound Visualization - Choose time and date", mode="md", class_name="inline-title")
                
                tgb.part()
                
                with tgb.part(class_name="right-align-text info-tooltip-container"):
                    tgb.image("taipy_visualization/icon_images/info.png", class_name="info-icon") 
                    
                    with tgb.part(class_name="info-tooltip-content"):
                        tgb.text("**Hydrophone Calibration**", mode="md", class_name="tooltip-heading")
                        tgb.text("The Orcasound Lab hydrophone data used here is currently uncalibrated. As a result, the acoustic visualizations display relative sound energy distributions rather than absolute decibel (dB) levels.", mode="md", class_name="tooltip-body")
                        
                        tgb.html("hr", class_name="tooltip-divider")
                        
                        tgb.text("**Frequency Range (1 - 16 kHz)**", mode="md", class_name="tooltip-heading")
                        tgb.text("This data pipeline processes frequencies up to 16 kHz. While this covers most SRKW pulsed calls and communication whistles, it completely excludes the high-frequency echolocation clicks (often reaching 80+ kHz) that they rely on for hunting salmon and navigating.", mode="md", class_name="tooltip-body")

            with tgb.layout(columns="1 1 1 1", class_name="center-align-text"):
                tgb.part()
                with tgb.part():
                    tgb.text("Choose a date", class_name="form-label")
                    tgb.date("{acoustic_date}", on_change=update_date)
                with tgb.part():
                    tgb.text("Choose a time", class_name="form-label")
                    tgb.selector("{displayed_hour}", lov="{hours_of_data}", dropdown=True, on_change=update_chart)
                tgb.part() 

            tgb.html("hr", style="border: 0; border-top: 1px solid rgba(255,255,255,0.2); margin: 30px 0;")


            tgb.text("### {spectrogram_title}", mode="md", class_name="bottom-padding")


            with tgb.layout(columns="1 5 3"):
                with tgb.part():
                    tgb.part()
                with tgb.part(class_name="center-align-text"):
                    tgb.toggle("{show_ship_overlay}", lov=["Hide Ship Overlays", "Show Ship Overlays"], on_change=toggle_ship_overlay, class_name="sleek-toggle")
                with tgb.part():
                    tgb.part()
            
            with tgb.layout(columns="3 1", gap="30px"):
                with tgb.part():
                    tgb.chart(figure="{spectrogram_fig}")
                with tgb.part(class_name="info-widget"):
                    tgb.text("### Understanding PSD Spectrograms", mode="md")
                    with tgb.html("ul"):
                        tgb.html("li", "A Power Spectral Density (PSD) spectrogram maps the distribution of acoustic energy across different frequencies over time, allowing researchers to isolate specific sound sources.")
                        tgb.html("li", "It visually separates low-frequency anthropogenic noise (like commercial shipping below 1,000 Hz) from the mid-to-high frequencies used by marine life.")
                        tgb.html("li", "SRKW vocalizations appear in specific bands: pulsed calls typically have fundamental frequencies between 1–6 kHz, while their whistles span 2–16 kHz.")
                        tgb.html("li", "By analyzing PSD, researchers can pinpoint exact 'masking bands' where vessel noise—such as high-frequency propeller cavitation—directly overlaps with and drowns out killer whale communication.")
            
            tgb.html("hr", style="border: 0; border-top: 1px solid rgba(255,255,255,0.2); margin: 30px 0;")

            tgb.text("### Combined Broadband Levels", mode="md", class_name="combined-broadband")
            with tgb.layout(columns="3 1", gap="30px"):
                with tgb.part():
                    tgb.chart(figure="{combined_bb_fig}")
                with tgb.part(class_name="info-widget scrollable-box", style="max-height: 450px; overflow-y: auto; padding-right: 15px;"):
                    tgb.text("### Broadband Insights", mode="md")
                    with tgb.html("ul"):
                        tgb.html("li", "<b>Full Range:</b> Calculates the total integrated sound energy, providing a baseline measure of the overall ocean soundscape.")
                        tgb.html("li", "<b>SRKW Band:</b> Pulsed calls are the most frequent vocalizations and range from 0.5 to 25 kHz, with energy concentrated between 1-6 kHz.")
                        tgb.html("li", "<b>Ship Band:</b> Large commercial vessels dominate the soundscape below 500 Hz through heavy machinery and propeller cavitation.")
                        tgb.html("li", "<b>The Lombard Effect:</b> For every 1 dB increase in background broadband noise, whales must exert more energy to increase their own vocal amplitude by 1 dB to be heard.")

        
        with tgb.part(class_name="card-panel"):
            tgb.text("### Detections & Ship Summaries", mode="md", class_name="bottom-padding underline-combined-graph-title")
            
            with tgb.layout(columns="1 3 1 3 1"):
                tgb.part()

                # LEFT: Whale Detections
                with tgb.part():
                    tgb.text("#### {detection_title}", mode="md", class_name="bottom-padding secondary-text-color")
                    with tgb.part(class_name="scrollable-box", style="max-height: 400px; overflow-y: auto; padding-right: 15px;"):
                        tgb.part(partial="{detection_partial}")

                tgb.part()

                # RIGHT: Ship Statistics Table
                with tgb.part():
                    tgb.text("#### Ships observed near Orcasound Lab in chosen timerange", mode="md", class_name="bottom-padding secondary-text-color underline-detections")
                    tgb.table("{ship_summary_df}", filter=False)
                
                tgb.part()

        with tgb.part(class_name="card-panel-secondary"):
            with tgb.expandable(title="Disclaimer and Additional Info", expanded=False, class_name="disclaimer-text"):
                with tgb.part(class_name="bottom-padding"):
                    tgb.text(
                        "This project is developed for **Orcasound**, an open-source community effort, with the primary goal of understanding how underwater noise may affect orcas in Puget Sound.", 
                        mode="md", 
                        class_name="secondary-text-color"
                    )
                    tgb.html("br")
                    tgb.text(
                        "The datasets, analyses, and code in this repository are intended for research, education, and conservation-oriented analysis. Ship passage data and derived ship sound metrics are included only to characterize the underwater acoustic environment and its potential effects on orcas.", 
                        mode="md", 
                        class_name="secondary-text-color"
                    )
                    tgb.html("br")
                    tgb.text(
                        "*Data quality, coverage, and processing assumptions may vary by source, location, and time period. Users should validate fitness for their own use case before drawing conclusions.*", 
                        mode="md", 
                        class_name="secondary-text-color"
                    )
                    


with tgb.Page() as leaderboard_page:
    with tgb.part(class_name="page-padding"):
        
        tgb.text("## Ship Leaderboard", mode="md", class_name="hero-title center-align-text")
        
        with tgb.part(class_name="card-panel center-align-text"):
            tgb.text("### Filter and Choose Metrics", mode="md", class_name="bottom-padding")
            
            with tgb.layout(columns="1 1 1", gap="30px"):
                with tgb.part():
                    tgb.text("Select Metrics", class_name="form-label")
                    tgb.selector(
                        "{selected_leaderboard_metrics}", 
                        lov="{leaderboard_metric_lov}", 
                        dropdown=True, 
                        multiple=True, 
                        value_by_id=True,
                        on_change=on_leaderboard_filter_change
                    )
                
                with tgb.part():
                    tgb.text("Select Ship Type", class_name="form-label")
                    tgb.selector(
                        "{selected_ship_type}", 
                        lov="{ship_type_lov}", 
                        dropdown=True, 
                        value_by_id=True,
                        on_change=on_leaderboard_filter_change
                    )
                    
                with tgb.part():
                    tgb.text("Isolated Status", class_name="form-label")
                    tgb.selector(
                        "{selected_isolated}", 
                        lov="{isolated_lov}", 
                        dropdown=True, 
                        value_by_id=True,
                        on_change=on_leaderboard_filter_change
                    )
            
            tgb.html("hr", style="border: 0; border-top: 1px solid rgba(255,255,255,0.2); margin: 30px 0;")
            
            tgb.text("### Ship Passages *( Click any row to inspect )*", mode="md", class_name="bottom-padding")
            tgb.table(
                "{display_leaderboard_df}",
                columns="{leaderboard_table_columns}",
                rebuild=True,
                on_action=on_ship_row_click,
                filter=True,
                page_size=20
            )

        with tgb.part(class_name="card-panel center-align-text"):
            tgb.text("### {ship_details_title}", mode="md", class_name="bottom-padding secondary-text-color")
            
            with tgb.expandable(title="PSD of Chosen Ship", expanded="{psd_expanded}"):
                tgb.chart(
                    figure="{selected_ship_psd_fig}",
                    rebuild="{ship_psd_chart_rebuild}"
                )
                
            with tgb.expandable(title="Detailed Ship Information", expanded="{stats_expanded}"):

                tgb.toggle("{selected_ship_tab}", lov="{ship_tab_lov}", class_name="sleek-toggle")
                
                with tgb.part(render="{selected_ship_tab == 'Speed, Draft & Passage Info'}"):
                    tgb.table("{ship_stats_general_df}")
                    
                with tgb.part(render="{selected_ship_tab == 'Acoustic Broadband'}"):
                    tgb.table("{ship_stats_acoustic_df}")
                    

        with tgb.part(class_name="card-panel-secondary"):
            with tgb.expandable(title="Data Dictionary", expanded="{data_dict_expanded}"):
                with tgb.layout(columns="1 1 1", gap="25px"):
                    
                    # Column 1: Identification & Timing
                    with tgb.part(class_name="info-widget"):
                        tgb.text("### Identity & Timing", mode="md")
                        with tgb.html("ul"):
                            tgb.html("li", "<b>id_track:</b> Unique tracking identifier for the radar passage.")
                            tgb.html("li", "<b>type:</b> Human-readable vessel category (e.g., Cargo, Tanker) mapped from raw AIS type codes.")
                            tgb.html("li", "<b>s_timestamp:</b> The time the ship was first detected entering the tracking zone.")
                            tgb.html("li", "<b>l_timestamp:</b> The time the ship exited the tracking zone.")
                            tgb.html("li", "<b>duration:</b> Total time duration of the observed passage.")

                    # Column 2: Spatial & Movement
                    with tgb.part(class_name="info-widget"):
                        tgb.text("### Spatial & Movement", mode="md")
                        with tgb.html("ul"):
                            tgb.html("li", "<b>avg_speed / max_speed:</b> Vessel speed over ground, measured in knots.")
                            tgb.html("li", "<b>distance:</b> Total distance covered by the vessel during the tracked passage.")
                            tgb.html("li", "<b>min_dist:</b> The closest point of approach (in meters) to the hydrophone coordinates.")
                            tgb.html("li", "<b>draft:</b> The vertical distance between the waterline and the bottom of the ship's hull.")
                            tgb.html("li", "<b>curviness:</b> A geometric metric representing how much the vessel's track deviates from a straight line.")

                    # Column 3: Acoustic & System Metrics
                    with tgb.part(class_name="info-widget"):
                        tgb.text("### Acoustics & System", mode="md")
                        with tgb.html("ul"):
                            tgb.html("li", "<b>is_isolated:</b> <i>True</i> if the ship passed alone. <i>False</i> if it temporally overlapped with other tracked vessels.")
                            tgb.html("li", "<b>confidence:</b> Machine learning confidence score (0 to 1) indicating the validity of the radar track.")
                            tgb.html("li", "<b>bb_q50 / bb_q95:</b> The median (50th) and 95th percentile broadband noise levels recorded during the passage.")
                            tgb.html("li", "<b>comm_bb / ship_bb:</b> Broadband noise levels isolated to the SRKW communication band and the low-frequency commercial shipping band, respectively.")
                            

pages = {
    "/": root_page,
    "Dashboard": dashboard_page,
    "Ship-Leaderboard": leaderboard_page
}

# ---------------------------------------------------------------------------------------------------- #
# --------------------------------------------- EXECUTION -------------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #

gui = Gui(pages=pages)
detection_partial = gui.add_partial(initial_det_string)

if __name__ == "__main__":
    gui.run(title="Orcasound Dashboard")
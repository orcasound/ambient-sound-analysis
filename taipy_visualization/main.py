from datetime import datetime, timedelta, date, time
import time as time_lib


import pandas as pd
import taipy.gui.builder as tgb
from taipy.gui import Gui, navigate, Icon


from data_utils import load_ship_data, get_available_hours_map, fetch_detections, fetch_psd_window
from plot_utils import plot_spectrogram, plot_combined_broadband, create_ship_timeline_with_detections
from orcasound_noise.analysis.partitioned_accessor import PartitionedAccessor
from orcasound_noise.utils.hydrophone import Hydrophone
from orcasound_noise.analysis.metrics.ship_metrics import get_ship_metrics_df

from dashboard_utils import (
    UTC_TZ,
    get_true_date,
    parse_detections_to_markdown,
    generate_ship_summary_df,
    make_empty_figure,
    reset_acoustic_figures,
    build_ship_psd_window,
    extract_ship_id_from_table_payload,
    calculate_masking_percentage
)


HYDROPHONE = Hydrophone.ORCASOUND_LAB


# ---------------------------------------------------------------------------------------------------- #
# --------------------------------------- TAIPY CALLBACKS -------------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #

def on_init(state):
    """
    The initial setup callback, initializes tables, chart states, and default UI values.
    """
    refresh_leaderboard_metric_button_classes(state)
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
    Triggered by date picker changes; refetches ship and whale data to redraw the main timeline Gantt chart.
    """
    true_start = get_true_date(state.gantt_start_date)
    true_end = get_true_date(state.gantt_end_date)
    
    state.gantt_start_date = true_start
    state.gantt_end_date = true_end

    start_dt = datetime.combine(true_start, time.min)
    end_dt = datetime.combine(true_end, time.max)
        
    aware_start_dt = start_dt.replace(tzinfo=UTC_TZ)
    aware_end_dt = end_dt.replace(tzinfo=UTC_TZ)
        
    if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
        mask = (GLOBAL_SHIP_DF['s_timestamp'] >= aware_start_dt) & (GLOBAL_SHIP_DF['l_timestamp'] <= aware_end_dt)
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
        d_time = pd.to_datetime(d["timestamp"], utc=True)
        if aware_start_dt <= d_time <= aware_end_dt:
            valid_detections.append(d)

    state.ship_and_detections = create_ship_timeline_with_detections(filtered_ships, valid_detections)
    state.detection_title = f"Bout Information ({start_dt.strftime('%d %b %Y')} to {end_dt.strftime('%d %b %Y')})"
    state.detection_partial.update_content(state, parse_detections_to_markdown(valid_detections))
    state.masking_percentage = calculate_masking_percentage(aware_start_dt, aware_end_dt, filtered_ships)
    state.ship_summary_df = generate_ship_summary_df(filtered_ships)




def update_date(state, var_name, var_value):
    """
    Triggered when the user picks a new date for sound analysis; fetches available data hours 
    for that specific day and resets the dropdowns.
    """
    new_date = get_true_date(var_value)
    state.acoustic_date = new_date
    state.displayed_hour = None 

    new_hours = get_available_hours_map(new_date.month, new_date.day, HYDROPHONE, new_date.year)

    state.last_fetched_date = None
    state.last_fetched_hour = None
    state.pd_acoustic_data_cache = pd.DataFrame()

    if not new_hours:
        # Provide a fallback string so the Taipy dropdown component doesn't break
        state.hours_of_data = ["No data for this date"]
        state.displayed_hour = "No data for this date"
        
        state.spectrogram_title = f"PSD for **{new_date.strftime('%Y-%m-%d')}** *( No data available )*"
        reset_acoustic_figures(state, "No acoustic data available for selected date")
    
    else:
        # Standard load for valid dates
        state.hours_of_data = new_hours
        state.displayed_hour = new_hours[0]
        update_chart(state)




def on_gantt_click(state, id, payload):
    """
    Captures clicks on the whale detection diamond markers in the Gantt chart and auto-navigates the acoustic UI to that specific hour.
    """
    print(f"\n[CLICK EVENT] Payload received: {payload}")

    current_time = time_lib.time()
    if current_time - state.last_click_time < 1.5:
        return
    state.last_click_time = current_time

    try:
        if isinstance(payload, dict) and 'x' in payload and 'y' in payload:
            if payload.get('y') == 'Whale Detections':
                clicked_time_str = payload.get('x')
                print(f"[CLICK EVENT] Processing Whale Detection at {clicked_time_str}...")
                
                dt = pd.to_datetime(clicked_time_str)
                state.acoustic_date = dt.date()
                
                new_hours = get_available_hours_map(dt.month, dt.day, HYDROPHONE, dt.year)
                state.hours_of_data = new_hours
                
                target_hour_str = f"{dt.hour:02d}:00"
                matching_hour = next((h for h in new_hours if h.startswith(target_hour_str)), None)
                
                state.displayed_hour = None 
                if matching_hour:
                    state.displayed_hour = matching_hour
                elif new_hours:
                    state.displayed_hour = new_hours[0]
                
                state.last_fetched_date = None
                state.last_fetched_hour = None
                state.pd_acoustic_data_cache = pd.DataFrame()
                
                print(f"[CLICK EVENT] Triggering chart update for {state.acoustic_date} at {state.displayed_hour}")
                update_chart(state)
            else:
                print(f"[CLICK EVENT] Ignored - Clicked on '{payload.get('y')}'")
        else:
            print("[CLICK EVENT] Payload missing x/y keys.")
            
    except Exception as e:
        print(f"[CLICK EVENT] Critical Error during processing: {e}")



def update_chart(state, var_name=None, var_value=None):
    """
    Updates all acoustic visualizations based on the selected UTC hour.
    """

    if not state.displayed_hour or state.displayed_hour == "No data for this date":
        state.spectrogram_title = "PSD for <No time selected>"
        reset_acoustic_figures(state, "No time selected")
        return

    try:
        start_str = state.displayed_hour.split(" to ")[0]
        selected_time = datetime.strptime(start_str, "%H:%M").time()

        safe_date = state.acoustic_date.date() if isinstance(state.acoustic_date, datetime) else state.acoustic_date
        utc_start = datetime.combine(safe_date, selected_time)
        utc_end = utc_start + timedelta(hours=1)

        print(
            f"[CHART] Selected UTC hour: {safe_date} {state.displayed_hour} | "
            f"Accessor window: {utc_start} -> {utc_end}"
        )

        state.spectrogram_title = (
            f"PSD for **{safe_date.strftime('%Y-%m-%d')}** "
            f"*( {state.displayed_hour} UTC )*"
        )

        time_changed = (
            state.last_fetched_date != state.acoustic_date
            or state.last_fetched_hour != state.displayed_hour
        )

        if state.last_fetched_hour is None or time_changed:
            accessor = PartitionedAccessor(HYDROPHONE, utc_start, utc_end)
            pl_psd, _ = accessor.get_dataframes(lazy=False)

            if pl_psd is None or pl_psd.is_empty():
                print("Warning: Accessor returned empty data for this window.")
                state.pd_acoustic_data_cache = pd.DataFrame()
                state.last_fetched_date = state.acoustic_date
                state.last_fetched_hour = state.displayed_hour
                reset_acoustic_figures(state, "No acoustic data available for selected hour")
                return

            state.pd_acoustic_data_cache = pl_psd.to_pandas()

            # ---  Generate Broadband Figures ---
            try:
                pl_full = accessor.get_broadband(1, 16000, 1e-6, "Full_Band").collect().to_pandas()
                pl_srkw = accessor.get_broadband(1000, 6000, 1e-6, "SRKW_Band").collect().to_pandas()
                pl_ships = accessor.get_broadband(10, 500, 1e-6, "Ship_Band").collect().to_pandas()
                
                new_combined_fig = plot_combined_broadband(pl_full, pl_srkw, pl_ships)
            except Exception as e:
                print(f"Broadband error: {e}")
                new_combined_fig = make_empty_figure("Broadband plot error")

            # ---  Generate Spectrogram Figure with Ship Overlay ---
            if state.pd_acoustic_data_cache is None or state.pd_acoustic_data_cache.empty:
                new_spec_fig = make_empty_figure("No acoustic data available for selected hour")
            else:
                # Pass GLOBAL_SHIP_DF here to activate the Use Case 1 overlays!
                new_spec_fig = plot_spectrogram(
                    state.pd_acoustic_data_cache, 
                    "Spectrogram",
                    ship_df=GLOBAL_SHIP_DF 
                )

            # ---  Batch Update UI State ---
            with state as s:
                s.pd_acoustic_data_cache = pl_psd.to_pandas()
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

    full_matches = state.GLOBAL_SHIP_DF[
        state.GLOBAL_SHIP_DF["id_track"].astype(str) == str(ship_id)
    ]

    if full_matches.empty:
        print(f"[LEADERBOARD] No full ship record found for id_track={ship_id}")
        return

    full_ship_data = full_matches.iloc[0]

    stats_df = full_ship_data.to_frame().reset_index()
    stats_df.columns = ["Metric", "Value"]

    start_time = pd.to_datetime(full_ship_data["s_timestamp"], utc=True)
    end_time = pd.to_datetime(full_ship_data["l_timestamp"], utc=True)

    window_start, window_end = build_ship_psd_window(start_time, end_time)

    print(
        f"[LEADERBOARD] Generating PSD for {ship_id} "
        f"from {window_start} to {window_end}"
    )

    try:
        pl_psd = fetch_psd_window(HYDROPHONE, window_start, window_end)

        if pl_psd is not None and not pl_psd.is_empty():
            new_psd_fig = plot_spectrogram(
                pl_psd.to_pandas(),
                f"PSD Profile: {ship_id}"
            )
        else:
            print("[LEADERBOARD] No PSD rows found for this ship window.")
            new_psd_fig = make_empty_figure(
                "No acoustic data found for this ship passage window."
            )

    except Exception as e:
        print(f"[LEADERBOARD] Error loading PSD: {e}")
        new_psd_fig = make_empty_figure("Error loading acoustic data from S3.")

    # Safely extract MMSI
    mmsi_val = full_ship_data.get("mmsi")
    if pd.isna(mmsi_val) or mmsi_val == "" or mmsi_val == 0:
        mmsi_str = "Not available"
    else:
        mmsi_str = str(int(mmsi_val)) # Convert float to int to remove decimals

    # Safely extract and format Ship Type
    type_val = full_ship_data.get("type")
    if pd.isna(type_val) or type_val == "" or type_val == "-":
        type_str = "Not available"
    else:
        type_str = str(type_val).replace('_', ' ').title()

    # Format the exact passage times
    time_fmt = "%Y-%m-%d %H:%M:%S"
    passage_str = f"{start_time.strftime(time_fmt)} to {end_time.strftime(time_fmt)}"

    # Build the multi-line markdown string (the two spaces before \n force a line break in Markdown)
    formatted_title = (
        f"Visualizing Ship Track ID - {ship_id}\n\n"
        f"**MMSI** - {mmsi_str}  \n"
        f"**Passage Duration** - {passage_str} (in UTC)  \n"
        f"**Type of Ship** - {type_str}"
    )

    with state as s:
        s.ship_details_title = formatted_title
        s.selected_ship_stats_df = stats_df
        s.selected_ship_psd_fig = new_psd_fig
        s.psd_expanded = True
        s.stats_expanded = True

# ---------------------------------------------------------------------------------------------------- #
# ----------------------------------- Ship dataframe loading ----------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #

# 1. Load Global Ship DataFrame
GLOBAL_SHIP_DF = None
try:
    GLOBAL_SHIP_DF = get_ship_metrics_df()
    if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
        GLOBAL_SHIP_DF['s_timestamp'] = pd.to_datetime(GLOBAL_SHIP_DF['s_timestamp'], utc=True)
        GLOBAL_SHIP_DF['l_timestamp'] = pd.to_datetime(GLOBAL_SHIP_DF['l_timestamp'], utc=True)
except Exception as e:
    print(f"Failed to load global ship data: {e}")
    GLOBAL_SHIP_DF = pd.DataFrame()

# --------------------------------------------------------------------------------------------------- #
# --------------------------------- Ship Leaderboard Setup ------------------------------------------ #
# --------------------------------------------------------------------------------------------------- #

LEADERBOARD_BASE_COLS = [
    "id_track", "s_timestamp", "l_timestamp", "mmsi", "name", "type",
]

LEADERBOARD_METRIC_GROUPS = {
    "metric_speed": {
        "label": "Speed of vessels",
        "columns": ["avg_speed", "max_speed", "min_speed"],
        "class_var": "metric_speed_class",
    },
    "metric_duration_distance": {
        "label": "Duration, Distance, Draft",
        "columns": ["duration", "distance", "min_dist", "curviness", "draft"],
        "class_var": "metric_duration_distance_class",
    },
    "metric_confidence": {
        "label": "Confidence scores",
        "columns": ["confidence"],
        "class_var": "metric_confidence_class",
    },
    "metric_comm_bb": {
        "label": "Communication broadband levels",
        "columns": ["comm_bb_avg", "comm_bb_q05", "comm_bb_q25", "comm_bb_q50", "comm_bb_q75", "comm_bb_q95"],
        "class_var": "metric_comm_bb_class",
    },
    "metric_overall_bb": {
        "label": "Overall broadband levels",
        "columns": ["bb_avg", "bb_q05", "bb_q25", "bb_q50", "bb_q75", "bb_q95"],
        "class_var": "metric_overall_bb_class",
    },
    "metric_ship_bb": {
        "label": "Ship broadband levels",
        "columns": ["ship_bb_avg", "ship_bb_q05", "ship_bb_q25", "ship_bb_q50", "ship_bb_q75", "ship_bb_q95"],
        "class_var": "metric_ship_bb_class",
    },
    "metric_lsr": {
        "label": "Listening space reduction",
        "columns": ["bb_lsr_q50", "bb_lsr_q95", "comm_bb_lsr_q50", "comm_bb_lsr_q95"],
        "class_var": "metric_lsr_class",
    },
    "metric_isolated": {
        "label": "Isolated flag",
        "columns": ["is_isolated"],
        "class_var": "metric_isolated_class",
    },
}




def refresh_leaderboard_metric_button_classes(state):
    """
    Toggles the CSS classes (selected vs. unselected visual states) for the metric filter buttons on the leaderboard page.
    """
    selected = set(state.selected_leaderboard_metrics)
    for metric_id, config in LEADERBOARD_METRIC_GROUPS.items():
        if metric_id in selected:
            class_value = "ship-leadboard-metric-buttons ship-leaderboard-metric-selected"
        else:
            class_value = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
        setattr(state, config["class_var"], class_value)




def compute_visible_leaderboard_columns(state):
    """
    Determines which data columns should actually be displayed in the leaderboard table 
    based on which metric buttons the user has toggled.
    """
    if GLOBAL_SHIP_DF is None or GLOBAL_SHIP_DF.empty:
        return LEADERBOARD_BASE_COLS.copy()

    available_cols = set(GLOBAL_SHIP_DF.columns)
    final_cols = [col for col in LEADERBOARD_BASE_COLS if col in available_cols]

    for metric_id in state.selected_leaderboard_metrics:
        for col in LEADERBOARD_METRIC_GROUPS[metric_id]["columns"]:
            if col in available_cols and col not in final_cols:
                final_cols.append(col)
    return final_cols




def rebuild_leaderboard_table(state):
    """
    Updates the underlying dataframe and schema for the leaderboard table so Taipy re-renders it with the correct newly selected columns.
    """

    if GLOBAL_SHIP_DF is None or GLOBAL_SHIP_DF.empty:
        
        # Batch empty state updates
        with state as s:
            s.display_leaderboard_df = pd.DataFrame(columns=LEADERBOARD_BASE_COLS)
            s.leaderboard_table_columns = LEADERBOARD_BASE_COLS.copy()
            s.leaderboard_table_rebuild = not s.leaderboard_table_rebuild
        return

    visible_cols = compute_visible_leaderboard_columns(state)
    
    # Batch data and column updates
    with state as s:
        s.display_leaderboard_df = (
            GLOBAL_SHIP_DF.loc[:, visible_cols]
            .copy()
            .reset_index(drop=True)
        )
        s.leaderboard_table_columns = visible_cols.copy()
        s.leaderboard_table_rebuild = not s.leaderboard_table_rebuild





def on_leaderboard_metric_click(state, id, payload):
    """
    Captures clicks on the metric filter buttons, updates the active selection state, and triggers the table rebuild.
    """
    current = list(state.selected_leaderboard_metrics)
    if id in current:
        current.remove(id)
    else:
        current.append(id)
    state.selected_leaderboard_metrics = current
    refresh_leaderboard_metric_button_classes(state)
    rebuild_leaderboard_table(state)





def render_leaderboard_metric_buttons():
    """
    A UI builder function that cleanly lays out all the toggleable metric buttons for the leaderboard.
    """
    tgb.button("Speed of vessels", id="metric_speed", on_action=on_leaderboard_metric_click, class_name="{metric_speed_class}")
    tgb.button("Duration, Distance, Draft", id="metric_duration_distance", on_action=on_leaderboard_metric_click, class_name="{metric_duration_distance_class}")
    tgb.button("Confidence scores", id="metric_confidence", on_action=on_leaderboard_metric_click, class_name="{metric_confidence_class}")
    tgb.button("Communication broadband levels", id="metric_comm_bb", on_action=on_leaderboard_metric_click, class_name="{metric_comm_bb_class}")
    tgb.button("Overall broadband levels", id="metric_overall_bb", on_action=on_leaderboard_metric_click, class_name="{metric_overall_bb_class}")
    tgb.button("Ship broadband levels", id="metric_ship_bb", on_action=on_leaderboard_metric_click, class_name="{metric_ship_bb_class}")
    tgb.button("Listening space reduction", id="metric_lsr", on_action=on_leaderboard_metric_click, class_name="{metric_lsr_class}")
    tgb.button("Isolated flag", id="metric_isolated", on_action=on_leaderboard_metric_click, class_name="{metric_isolated_class}")




selected_leaderboard_metrics = []

metric_speed_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_duration_distance_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_confidence_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_comm_bb_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_overall_bb_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_ship_bb_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_lsr_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"
metric_isolated_class = "ship-leadboard-metric-buttons ship-leaderboard-metric-unselected"

leaderboard_table_rebuild = False

if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
    temp_selected_state = type("TempState", (), {})()
    temp_selected_state.selected_leaderboard_metrics = selected_leaderboard_metrics
    leaderboard_table_columns = compute_visible_leaderboard_columns(temp_selected_state)

    display_leaderboard_df = (
        GLOBAL_SHIP_DF.loc[:, leaderboard_table_columns]
        .copy()
        .reset_index(drop=True)
    )
else:
    display_leaderboard_df = pd.DataFrame(columns=LEADERBOARD_BASE_COLS)
    leaderboard_table_columns = LEADERBOARD_BASE_COLS.copy()

selected_ship_psd_fig = make_empty_figure("Click a row in the table above to load acoustic signature")
selected_ship_stats_df = pd.DataFrame(columns=["Metric", "Value"])
ship_details_title = "Select a ship from the table"
psd_expanded = False
stats_expanded = False

# --------------------------------------------------------------------------------------------------- #
# --------------------------- Ship Leaderboard Setup ends ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #






# --------------------------------------------------------------------------------------------------- #
# ---------------------------- Acoustic Chart Setup ------------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #

acoustic_date = date(2026, 2, 7) #Default first date
hours_of_data = get_available_hours_map(
    acoustic_date.month, 
    acoustic_date.day, 
    HYDROPHONE, 
    acoustic_date.year
)
displayed_hour = hours_of_data[0] if hours_of_data else None

# Initializing Gantt Chart & Ship Summaries
gantt_start_date = datetime(2026, 2, 6)
gantt_end_date = datetime(2026, 2, 7)

start_dt_init = datetime.combine(gantt_start_date.date(), time.min)
end_dt_init = datetime.combine(gantt_end_date.date(), time.max)

aware_start_init = start_dt_init.replace(tzinfo=UTC_TZ)
aware_end_init = end_dt_init.replace(tzinfo=UTC_TZ)

if GLOBAL_SHIP_DF is not None and not GLOBAL_SHIP_DF.empty:
    mask = (GLOBAL_SHIP_DF['s_timestamp'] >= aware_start_init) & (GLOBAL_SHIP_DF['l_timestamp'] <= aware_end_init)
    init_ships = GLOBAL_SHIP_DF[mask]
else:
    init_ships = pd.DataFrame()

masking_percentage = calculate_masking_percentage(aware_start_init, aware_end_init, init_ships)

api_start_dt_init = start_dt_init.date() - timedelta(days=1)
api_end_dt_init = end_dt_init.date() + timedelta(days=1)

raw_dets_init = fetch_detections(
    datetime.combine(api_start_dt_init, time.min), 
    datetime.combine(api_end_dt_init, time.max)
)

valid_dets_init = []
for d in raw_dets_init:
    d_time = pd.to_datetime(d["timestamp"], utc=True)
    if aware_start_init <= d_time <= aware_end_init:
        valid_dets_init.append(d)

ship_and_detections = create_ship_timeline_with_detections(init_ships, valid_dets_init)
initial_det_string = parse_detections_to_markdown(valid_dets_init)
ship_summary_df = generate_ship_summary_df(init_ships)
detection_title = f"Bout Information ({start_dt_init.strftime('%d %b %Y')} to {end_dt_init.strftime('%d %b %Y')})"

# Initializing Empty Plotly Figures and Cache Variables
spectrogram_fig = make_empty_figure("Select a date and time to load spectrogram")
combined_bb_fig = make_empty_figure("Select a date and time to load broadband data")

spectrogram_title = "PSD for <Select a date and time>"
pd_acoustic_data_cache = pd.DataFrame() 
last_fetched_date = None  
last_fetched_hour = None

last_click_time = 0.0
last_table_click_time = 0.0

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
            tgb.text("## **Orcasound** - Ambient Sound Analysis", mode="md", class_name="bottom-padding")
            tgb.text("#### Visualizing the ocean's soundscape: whales, ships, and ambient noise", mode="md", class_name="secondary-text-color")
        
        with tgb.part(class_name="card-panel"):
            tgb.text("### Select a time period to explore ship activity and whale detections", mode="md", class_name="bottom-padding underline-combined-graph-title")
            
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

            with tgb.layout(columns="1 4 1"):
                tgb.part()
                with tgb.part(class_name="center-align-text"):
                    tgb.text("Whales had interference for {masking_percentage}% of your chosen duration", class_name="masking-text bottom-padding underline")
                    tgb.text("*This is a low end estimate based on duration of ship passages. Acoustic masking lasts longer than ship passage*", mode="md", class_name="masking-text bottom-padding")
                tgb.part()

            tgb.chart(figure="{ship_and_detections}", on_click="on_gantt_click")
        
        with tgb.part(class_name="card-panel-secondary title-viz"):

            tgb.text("### Sound Visualization - Choose time and date", mode="md", class_name="bottom-padding underline-psd-date-selector")
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
            tgb.text("*Uncalibrated Hydrophone*", mode="md", class_name="bottom-padding combined-broadband")
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
                    tgb.text("#### {detection_title}", mode="md", class_name="bottom-padding secondary-text-color underline-detections")
                    with tgb.part(class_name="scrollable-box", style="max-height: 400px; overflow-y: auto; padding-right: 15px;"):
                        tgb.part(partial="{detection_partial}")

                tgb.part()

                # RIGHT: Ship Statistics Table
                with tgb.part():
                    tgb.text("#### Ships observed near Orcasound Lab in chosen timerange", mode="md", class_name="bottom-padding secondary-text-color underline-detections")
                    tgb.table("{ship_summary_df}", filter=False)
                
                tgb.part()

with tgb.Page() as leaderboard_page:
    with tgb.part(class_name="page-padding"):
        
        tgb.text("## Ship Leaderboard", mode="md", class_name="hero-title center-align-text")
        
        with tgb.part(class_name="card-panel center-align-text"):
            tgb.text("### Customize leaderboard metrics", mode="md")
            
            with tgb.layout(columns = "1 10 1"):
                tgb.part()

                with tgb.part(class_name="button-row-ship-leaderboard bottom-padding"):
                    render_leaderboard_metric_buttons()
                
                tgb.part()
            
            tgb.text("### Ship Passages *( Click any row to inspect )*", mode="md", class_name="bottom-padding")
            tgb.table(
                "{display_leaderboard_df}",
                columns="{leaderboard_table_columns}",
                rebuild="{leaderboard_table_rebuild}",
                on_action=on_ship_row_click,
                filter=True,
                page_size=20
            )

        with tgb.part(class_name="card-panel center-align-text"):
            tgb.text("### {ship_details_title}", mode="md", class_name="bottom-padding secondary-text-color")
            
            with tgb.expandable(title="PSD of Chosen Ship", expanded="{psd_expanded}"):
                tgb.chart(figure="{selected_ship_psd_fig}")
                
            with tgb.expandable(title="Detailed Ship Information", expanded="{stats_expanded}"):
                tgb.table("{selected_ship_stats_df}")

        with tgb.part(class_name="card-panel-secondary"):
            tgb.text("### Data Dictionary", mode="md", class_name="bottom-padding")
            with tgb.layout(columns="1 1"):
                with tgb.part():
                    with tgb.html("ul"):
                        tgb.html("li", "<b>id_track:</b> The unique tracking identifier for the vessel passage.")
                        tgb.html("li", "<b>s_timestamp:</b> The exact time the ship was first detected entering the hydrophone zone.")
                        tgb.html("li", "<b>l_timestamp:</b> The time the ship exited the hydrophone zone.")
                        tgb.html("li", "<b>avg_speed / max_speed:</b> Vessel speed over ground, measured in knots.")
                        tgb.html("li", "<b>mmsi:</b> Maritime Mobile Service Identity, a unique 9-digit maritime radio ID.")
                with tgb.part():
                    with tgb.html("ul"):
                        tgb.html("li", "<b>draft:</b> The vertical distance between the waterline and the bottom of the ship's hull.")
                        tgb.html("li", "<b>is_isolated:</b> True if the ship passed alone. False if it overlapped with other vessels.")
                        tgb.html("li", "<b>bb_lsr_q50:</b> Listening Space Reduction. The median percentage (0-100%) of acoustic space lost to marine life due to this vessel's noise.")
                        tgb.html("li", "<b>min_dist:</b> The closest point of approach to the hydrophone (in meters).")

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
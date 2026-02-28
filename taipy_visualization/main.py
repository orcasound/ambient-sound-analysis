import taipy.gui.builder as tgb
from taipy.gui import Gui
from data_utils import load_ship_data, get_available_hours_map, fetch_acoustic_data, fetch_bout_data, format_bout_data_to_text
from plot_utils import plot_spectrogram
from datetime import datetime, timedelta, date, time
import polars as pl
import pandas as pd
import plotly.graph_objects as go
from zoneinfo import ZoneInfo

GLOBAL_SHIP_DF = None
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
UTC_TZ = ZoneInfo("UTC")

def get_ship_df():
    global GLOBAL_SHIP_DF
    if GLOBAL_SHIP_DF is None:
        GLOBAL_SHIP_DF = load_ship_data("M2_Ship_Data/26_2026_02_tracks_ais.shp.shp")
    return GLOBAL_SHIP_DF

# ------------------- Initial Values -------------------
acoustic_date = datetime(2026, 2, 7, 0, 0, 0)
hours_of_data = get_available_hours_map(2, 7, "orcasound_lab", 2026) 
displayed_hour = hours_of_data[0] if hours_of_data else None
hydrophone = "orcasound_lab"

option_1 = False # Assigned to toggle for Bout API data (whale calls)
option_2 = False # Assigned to toggle for ship passage data

spectrogram_fig = None
is_loading = False 
pd_acoustic_data_cache = pd.DataFrame() 
last_fetched_date = None  
last_fetched_hour = None

bout_date = datetime(2026, 2, 7)
raw_default_bouts = fetch_bout_data(bout_date, bout_date + timedelta(days=1))
bout_detail = format_bout_data_to_text(raw_default_bouts)


# Functions for Interactivity
def on_init(state):
    """
    Taipy automatically runs this function when the page first loads.
    """
    update_chart(state)


def update_date(state, var_name=None, var_value=None):
    """
    This will update the hours of data list based on the user choice of date
    """
    month = state.acoustic_date.month
    day = state.acoustic_date.day
    year = state.acoustic_date.year
    
    state.hours_of_data = get_available_hours_map(month, day, hydrophone, year)
    state.displayed_hour = state.hours_of_data[0] if state.hours_of_data else None

    update_chart(state)

def update_chart(state, var_name=None, var_value=None):
    """
    Master function to fetch data and update the chart. 
    """
    if not state.displayed_hour:
        return

    try:
        # Parse the string format (e.g., "00:00 to 01:00") into datetimes
        start_str, end_str = state.displayed_hour.split(' to ') 

        date_str = state.acoustic_date.strftime('%Y-%m-%d')
        start_dt = datetime.strptime(f"{date_str} {start_str}", '%Y-%m-%d %H:%M')
        
        if end_str == "24:00":
            end_dt = start_dt.replace(hour=0) + timedelta(days=1)
        else:
            end_dt = datetime.strptime(f"{date_str} {end_str}", '%Y-%m-%d %H:%M')

        # --- Checking the Cache
        time_changed = (state.last_fetched_date != state.date) or (state.last_fetched_hour != state.displayed_hour)

        if state.last_fetched_hour is None or time_changed:
            
            # Turn on the loading GIF *only* during a fetch
            state.is_loading = True 
            print(f"[{datetime.now().strftime('%H:%M:%S')}] S3 FETCH: Downloading new data...")
            
            pl_acoustic_data = fetch_acoustic_data(state.acoustic_date, start_dt, end_dt)
            
            if hasattr(pl_acoustic_data, 'to_pandas') and not pl_acoustic_data.is_empty():
                state.pd_acoustic_data_cache = pl_acoustic_data.to_pandas()
            else:
                state.pd_acoustic_data_cache = pd.DataFrame()
                
            # Update the trackers
            state.last_fetched_date = state.acoustic_date
            state.last_fetched_hour = state.displayed_hour

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating plot...") 
        if state.option_2:
            state.spectrogram_fig = plot_spectrogram(state.pd_acoustic_data_cache, "Spectrogram", ship_df=get_ship_df())
        else:
            state.spectrogram_fig = plot_spectrogram(state.pd_acoustic_data_cache, "Spectrogram")
            
    except Exception as e:
        print(f"An error occurred while updating the chart: {e}")
        state.spectrogram_fig = go.Figure().add_annotation(text="Error loading data", showarrow=False)
    
    finally:
        state.is_loading = False

def update_bout_date_and_text(state, var_name=None, var_value=None):
    try:
        state.bout_detail = "*Loading bout data...*" 
        
        selected_local = state.bout_date

        if isinstance(selected_local, date) and not isinstance(selected_local, datetime):
            selected_local = datetime.combine(selected_local, time.min)
        
        if selected_local.tzinfo is None:
            selected_local = selected_local.replace(tzinfo=LOCAL_TZ)
        else:
            selected_local = selected_local.astimezone(LOCAL_TZ)
        
        start_utc = selected_local.astimezone(UTC_TZ)
        end_utc = (selected_local + timedelta(days=1)).astimezone(UTC_TZ)

        raw_bouts = fetch_bout_data(start_utc, end_utc)
        state.bout_detail = format_bout_data_to_text(raw_bouts, display_tz=LOCAL_TZ)
        
    except Exception as e:
        print(f"No Bout Data exists for this day: {e}")
        state.bout_detail = "*No Bout Data exists for this day*"

# --- UI Definition ---
with tgb.Page() as page:
    with tgb.part(class_name="container"):
        tgb.text("# Orcasound Ambient Sound Analysis Dashboard", mode="md")
        
        tgb.html("br")

        with tgb.part(class_name="card"):
            tgb.text("Visualize the interaction of Whale sounds and Ship sounds!", class_name = "subtitle-text")

        tgb.html("br")

        with tgb.part(class_name="card"):
            with tgb.layout(columns="1 1 1"):
                with tgb.part():
                    tgb.text("*Choose a day to see when whale bouts took place:*", mode="md")
                with tgb.part():
                    tgb.date("{bout_date}", on_change = update_bout_date_and_text)
                with tgb.part():
                    tgb.text("{bout_detail}", mode="md")
        tgb.html("br")

        with tgb.part(class_name="card"):
            with tgb.layout(columns="1 1 1 1"):
                with tgb.part():
                    tgb.text("*Choose a date to explore the available sound data*", mode="md")
                with tgb.part():
                    tgb.date("{acoustic_date}", on_change = update_date)
                with tgb.part():
                    tgb.text("*Select a time on this date*", mode = "md")
                with tgb.part():
                    tgb.selector("{displayed_hour}", lov="{hours_of_data}", dropdown = True, on_change=update_chart)

        tgb.html("br")


        with tgb.part(class_name="card"):
            with tgb.layout(columns="1 1"):
                tgb.toggle("{option_1}", label="Superimpose Bout API data (Whale calls) on graph")
                tgb.toggle("{option_2}", label="Superimpose Ship passage data on graph", on_change=update_chart)
        
        tgb.html("br")

        with tgb.part(class_name="card"):
            with tgb.part(render="{is_loading}"):
                tgb.image("https://i.gifer.com/ZKZg.gif", width="40px")
                tgb.text("Fetching acoustic data...", mode="md")
            tgb.chart(figure="{spectrogram_fig}")

if __name__ == "__main__":
    Gui(page=page).run(state={
    "date": acoustic_date,
    "hours_of_data": hours_of_data,
    "displayed_hour": displayed_hour,
    "pd_acoustic_data_cache": pd_acoustic_data_cache,
    "last_fetched_date": last_fetched_date,
    "last_fetched_hour": last_fetched_hour,
    "bout_date": bout_date,
    "bout_detail": bout_detail,
    "option_1": option_1,
    "option_2": option_2,
    "is_loading": is_loading,
    "spectrogram_fig": spectrogram_fig
    })
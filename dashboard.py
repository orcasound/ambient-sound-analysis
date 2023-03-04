import streamlit as st

from src.dashboard import daily_dashboard, dashboard_2, dashboard_3

dailyTab, tab2, tab3 = st.tabs(["Daily Noise", "Tab2", "Tab3"])

with dailyTab:
    daily_dashboard.create_tab()

with tab2:
    dashboard_2.create_tab()

with tab3:
    dashboard_3.create_tab()

import streamlit as st

st.set_page_config(
    page_title="Hello",
    page_icon="👋",
)

st.write("# Welcome to The Orcasound Ambient Noise Dashboard! 👋")

st.sidebar.success("Select a dashboard above.")

st.markdown(
    """
    This dashboard is a tool to explore the historical ambient noise levels gathered from the Orcasound Hydrophone Network.
    
    **👈 Select a view from the sidebar** to explore the trends and patterns of noise levels in the Salish Sea.

    ### Want to learn more?
    - Check out [the noise repository](https://github.com/orcasound/ambient-sound-analysis)
    - View the broader [Orcasound community](https://github.com/orcasound)

"""
)

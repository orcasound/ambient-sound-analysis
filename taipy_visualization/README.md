## Dashboard Overview

This dashboard is a data visualization frontend built entirely in Python. It ties together raw acoustic data (Power Spectral Density and Broadband metrics from S3), Ship tracking data (from Marine Monitor or M2), and AI-driven whale detections (OrcaHello) into a single, cohesive interface.

### Core Technologies
* **[Taipy](https://taipy.io/):** Used as the core framework for the UI and state management. 
* **[Plotly (Graph Objects & Express)](https://plotly.com/python/):** Powers all the interactive visualizations, including the complex Gantt charts for ship passages and the dense heatmaps for the PSD spectrograms.
* **Pandas & Polars:** Utilized heavily for data manipulation, time-series alignment, and caching large acoustic datasets retrieved from AWS S3.

### Key Features
* **Interactive Timeline:** A Gantt chart overlaying commercial ship passages with AI-confirmed whale detections.
* **Acoustic Spectrograms:** Dynamic Power Spectral Density (PSD) heatmaps that allow users to visually separate low-frequency anthropogenic noise from high-frequency biological sounds.
* **Combined Broadband Analysis:** Line charts comparing overall ocean noise, the SRKW communication band, and the commercial shipping band.
* **Ship Leaderboard:** A filterable database of individual ship passages, complete with their specific acoustic signatures and passage metrics (speed, draft, distance to hydrophone).

---

## Known Issues & Limitations

There are a few known bugs and UI quirks related to the underlying framework and data density:

1. **Date Picker Instability:** Users may occasionally experience a bug where the `tgb.date` picker "jumps" or resets to a different date compared to the selected date when a new date is selected. If this happens, re-selecting the desired date usually resolves the state.
   
2. **Gantt Chart Click Overlap (Dense Detections):**
   When clicking on a whale detection in the main timeline to jump to its specific acoustic data, the dashboard fetches the corresponding hour-block of data. If multiple detections are packed very closely together, the chart's click payload may accidentally register an adjacent detection. As a result, the PSD title and loaded timeframe might not perfectly match the specific dot you intended to click.

---

## ⚠️ Disclaimer and Additional Info

The datasets, analyses, and code in this repository are intended for research, education, and conservation-oriented analysis. Ship passage data and derived ship sound metrics are included only to characterize the underwater acoustic environment and its potential effects on orcas.

*Data quality, coverage, and processing assumptions may vary by source, location, and time period. Users should validate fitness for their own use case before drawing conclusions.*
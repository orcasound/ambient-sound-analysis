# Orcasound Ambient Sound Analysis Dashboard

## 📊 Dashboard Overview

This dashboard is a data visualization frontend built entirely in Python. It ties together raw acoustic data (Power Spectral Density and Broadband metrics from S3), Ship tracking data (from Marine Monitor or M2), and Machine Learning based whale detections (OrcaHello) into a single interface.

### Core Technologies
* **[Taipy](https://taipy.io/):** Used as the core framework for the UI and state management. 
* **[Plotly (Graph Objects & Express)](https://plotly.com/python/):** Powers all the interactive visualizations, including the complex Gantt charts for ship passages and the dense heatmaps for the PSD spectrograms.
* **Pandas & Polars:** Utilized heavily for data manipulation, time-series alignment, and caching large acoustic datasets retrieved from AWS S3.

### Key Features
* **Interactive Timeline:** A Gantt chart overlaying commercial ship passages with ML driven whale detections.
* **Acoustic Spectrograms:** Dynamic Power Spectral Density (PSD) heatmaps that allow users to visually separate low-frequency anthropogenic noise from high-frequency biological sounds.
* **Combined Broadband Analysis:** Line charts comparing overall ocean noise, the SRKW communication band, and the commercial shipping band.
* **Ship Leaderboard:** A filterable database of individual ship passages, complete with their specific acoustic signatures and passage metrics (speed, draft, distance to hydrophone).

---

## 📁 Project Structure



The dashboard's logic is modularized across several files to separate UI components from data processing and visualization:

* **`main.py`**: The primary entry point that defines the Taipy UI layout, state variables, and page routing. It also contains various functions for interactivity.
* **`dashboard_utils.py`**: Contains helper functions for data formatting, UI state management, and timestamp localization.
* **`plot_utils.py`**: Responsible for building and dynamically updating the Plotly interactive charts, including the spectrograms and broadband visualizations.
* **`data_utils.py`**: Manages API requests (like fetching OrcaHello detections) and orchestrates data retrieval from AWS S3.
* **`partitioned_accessor.py`**: Efficiently retrieves and queries partitioned Parquet files from S3 using lazy loading via Polars.
* **`ship_metrics.py`**: Contains the core logic and classes for generating the derived ship tracking metrics that populate the dashboard's leaderboard.

---

## ⚙️ Environment Setup



To run this dashboard locally and fetch the necessary acoustic data from S3, you must authenticate with AWS. This project relies on a `.env` file located in the root directory. 

Create a `.env` file and include the following variables:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=your_aws_region

To obtain the correct AWS credentials for the Orcasound S3 buckets, please contact the Orcasound team at https://github.com/orcasound/ambient-sound-analysis
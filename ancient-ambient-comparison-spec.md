# Ancient Ambient Comparison Analysis — Specification

---

## Ambient Reference Level

### Definition

The ambient reference level (also called "ancient ambient") is a percentile-based estimate of the underlying quiet underwater noise baseline at a given hydrophone location. It represents the sound level that would exist in the absence of significant anthropogenic sources — primarily ships. The estimate is the **5th percentile of 1-second broadband sound pressure levels** computed over a rolling lookback window, using all available acoustic data without ship filtering.

### Purpose

1. **Establish a reproducible noise baseline** — Provide a consistent, simple metric for the quietest conditions at each hydrophone site, usable across any time period without dependency on external data sources (AIS, ship tracks, etc.)
2. **Enable cross-temporal comparison** — Compare the same hydrophone against itself across seasons, years, or before/after interventions (e.g., vessel slowdown zones, COVID shipping reductions) using a consistent methodology
3. **Enable cross-hydrophone comparison** — Apply the same calculation across all Orcasound hydrophone sites to identify relative noise levels and hotspots
4. **Inform conservation decisions** — A rigorous ambient baseline is foundational for noise budgets and habitat quality assessments for endangered Southern Resident killer whales (SRKW)
5. **Quantify trends** — Track whether the Salish Sea soundscape is getting louder or quieter over time at each monitoring site

### Units

- **Sound pressure level**: dB re 1 µPa (ref=1, normalized)
- **Frequency bands**:
  - Broadband: 67–22,400 Hz (full hydrophone response)
  - Communication band: 500–15,000 Hz (orca vocalizations)
  - Ship band: 67–200 Hz (low-frequency vessel noise)
- **Temporal resolution**: 1-second samples
- **Lookback window**: 3-day rolling (recommended), 7-day maximum

### Methodology

The ambient reference level is calculated as the **unfiltered 5th percentile** of 1-second broadband sound levels over a **3-day rolling lookback window**.

1. Load 1-second acoustic data for the lookback window using `PartitionedAccessor`
2. No ship filtering is applied — all available samples are used regardless of vessel activity
3. Compute the 5th percentile (`quantile(0.05)`) of the broadband dB values across all seconds in the window
4. Roll the window forward daily to produce a time series of ambient reference levels

**Rationale for no ship filtering:**
- Removes dependency on AIS data availability, which is limited in time range and geographic coverage
- Makes the methodology portable to any hydrophone and any time period
- The 5th percentile inherently selects for the quietest conditions, naturally downweighting ship-heavy periods
- Ship-filtered vs. unfiltered analysis (Method 1 vs. Method 2 in this notebook) evaluates whether the added complexity of ship filtering produces meaningfully different estimates

**Rationale for 3-day lookback:**
- Smooths out single-day anomalies (weather events, data gaps, unusual quiet periods)
- More responsive to real environmental shifts than longer windows — a 7-day window can lag behind actual changes
- Consistency metrics show diminishing stability gains beyond 3 days
- Keeps the calculation lightweight and interpretable

### Implementation and Pipeline

**Data source:** Acoustic data from `s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/`, loaded via `PartitionedAccessor`

**Pipeline steps:**
1. Instantiate `PartitionedAccessor` for the target hydrophone
2. Call `get_broadband(start, end, 67, 22400, ref=1)` for the 3-day window
3. Compute `quantile(0.05)` on the broadband dB column
4. Advance the window by 1 day and repeat
5. Collect daily estimates into a rolling time series
6. Optionally compute consistency metrics (Std, CV, IQR, DoD delta, p95−p5) to assess stability

**Key parameters:**
| Parameter | Value |
|-----------|-------|
| Percentile | 5th (0.05) |
| Lookback window | 3 days (recommended), 7 days (maximum) |
| Frequency range | 67–22,400 Hz (broadband) |
| Reference pressure | ref=1 (normalized) |
| Temporal resolution | 1-second samples |
| Minimum data threshold | 43,200 seconds (12 hours) per day |

---

## Problem Statement

The current definition of "ancient ambient" noise level — the 5th percentile of a month's broadband acoustic data — does not account for anthropogenic noise sources like ship traffic. This analysis compares two approaches to estimating ambient sound levels:

1. **Method 1 (Ship-Filtered)**: Identify periods of no or little ship activity, then compute sound percentiles over those quiet periods for window lengths of 1, 2, 5, and 7 days.
2. **Method 2 (Unfiltered)**: Compute sound percentiles over all data regardless of ship presence, for window lengths of 1, 2, 3, 5, 7, 10, and 14 days.

The goal is to evaluate whether ship filtering produces meaningfully different ambient estimates and how sensitive both methods are to the choice of window length.

---

## Goals / Success Criteria

- Produce a clear visual comparison of Method 1 vs Method 2 ambient estimates across all shared window lengths (1, 2, 5, 7 days)
- Show how each method's estimate changes as window length increases
- Compare results across both broadband and orca communication band (500–15,000 Hz)
- Compare results across multiple percentiles: 5th, 10th, 25th, 50th
- Quantify what fraction of time is ship-free, as a function of window length

---

## Non-Goals

- This is exploratory research, not production code — no CI, no automated tests
- No real-time or streaming analysis
- No comparison of individual ship types or distances
- No analysis beyond Orcasound Lab hydrophone in this iteration

---

## Requirements

### Functional Requirements

**FR1**: Load pre-computed ship metrics parquet files from `s3://acoustic-sandbox/ambient-sound-analysis/temp_ship_metrics/` (partitioned by `year=/month=/day=`, covering 2026-02-07 to 2026-02-13) using the `ambient-sound-team` AWS profile.

**FR2**: Load acoustic data (broadband and PSD) from S3 using `PartitionedAccessor` for the date range needed by each window. Method 1 uses 2/7–2/13 (7 days of ship data). Method 2 extends back further for 10-day and 14-day windows (ending 2/13).

**FR3 — Method 1 (Ship-Filtered Percentiles)**:
- For each window duration D in {1, 2, 5, 7} days (capped by available ship data ending 2/13):
  - Define the analysis window as the last D days of available ship data (ending 2026-02-13 23:59:59)
  - Load ship metrics for that window from S3 parquet
  - Apply validity filter: keep ship tracks where `confidence >= 0.5`
  - Build a per-second ship-presence mask by marking every second between `s_timestamp` and `l_timestamp` for each valid track as "ship present"
  - Extract ship-free 1-second intervals (all seconds not covered by any ship track)
  - For those ship-free seconds, compute broadband percentiles (5th, 10th, 25th, 50th) and communication band percentiles (5th, 10th, 25th, 50th)

**FR4 — Method 2 (Unfiltered Percentiles)**:
- For each window duration D in {1, 2, 3, 5, 7, 10, 14} days (ending 2026-02-13):
  - Load all broadband and communication band data for that window
  - Compute percentiles (5th, 10th, 25th, 50th) with no ship filtering

**FR5 — Comparison outputs**:
- Table: For each (method, window, percentile, band) combination, the estimated ancient ambient level in dB
- Plot A: Line chart — estimated ambient level vs. window length, one line per percentile, faceted by method (Method 1 / Method 2), for a single band. Show both methods on the same axis for the overlapping window lengths.
- Plot B: Bar chart or scatter — Method 1 vs Method 2 at each overlapping window length (1, 2, 5, 7 days), for the 5th percentile, for each band
- Plot C: Ship-free fraction chart — percentage of seconds that are ship-free as a function of window length (for Method 1 windows)
- Plot D: Time-of-day distribution — ship presence as a fraction of time by hour of day, to show when quiet periods cluster

### Non-Functional Requirements

- **NFR1**: Notebook should run end-to-end with a single kernel restart using the `orcasound` conda environment
- **NFR2**: AWS access uses the `ambient-sound-team` profile; no credentials hardcoded
- **NFR3**: Data loading should use `PartitionedAccessor` (from `src/orcasound_noise/analysis/partitioned_accessor.py`) for sound data and `polars.scan_parquet` or `pandas.read_parquet` for ship metrics from S3

---

## Technical Design

### Architecture Overview

A single self-contained Jupyter notebook performs all data loading, filtering, computation, and visualization. It is organized into sequential sections with markdown headers. No new Python modules are introduced — everything lives in the notebook.

### Components

| Component | Responsibility |
|-----------|----------------|
| Ship metrics loader | Read pre-computed ship parquet from S3 using polars `scan_parquet` or `pd.read_parquet`, concatenate across days |
| Ship presence mask builder | Convert ship `s_timestamp`/`l_timestamp` intervals into a per-second boolean mask joined to the acoustic timeseries |
| Acoustic data loader | Use `PartitionedAccessor` to load broadband (`'0'` column) and compute comm band from PSD |
| Percentile calculator | Apply `polars` or `pandas` quantile functions to ship-free and all-data slices |
| Results aggregator | Collect (method, window_days, percentile, band) → dB into a summary DataFrame |
| Visualization | matplotlib/plotly plots of the comparison results |

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `notebooks/ancient_ambient_comparison.ipynb` | Create | Main analysis notebook |
| `ancient-ambient-comparison-spec.md` | Create (this file) | Spec document |

### Key Data Schemas

**Ship metrics parquet** (one file per day, read across all days in window):
```
id_track        int64        — unique track identifier
s_timestamp     datetime64   — ship passage start time
l_timestamp     datetime64   — ship passage end time
confidence      float64      — track confidence (0–1); filter >= 0.5
min_dist        float64      — distance to hydrophone in meters
is_isolated     bool         — True if only ship in passage window
comm_avg        float64      — mean comm band dB during passage
bb_avg          float64      — mean broadband dB during passage
```

**Acoustic data from PartitionedAccessor**:
```
__index_level_0__    datetime    — 1-second timestamp (index)
0                    float64     — broadband sound level (dB)
<freq_hz>            float64     — PSD columns (67, 71, ..., 22400 Hz) for comm band calc
```

**Results summary DataFrame**:
```
method          str      — 'ship_filtered' | 'unfiltered'
window_days     int      — 1, 2, 3, 5, 7, 10, 14
band            str      — 'broadband' | 'comm_band'
percentile      float    — 0.05, 0.10, 0.25, 0.50
value_db        float    — estimated ancient ambient level in dB
n_seconds       int      — number of 1-second samples used
ship_free_pct   float    — (Method 1 only) % of window that was ship-free
```

### Notebook Structure

```
1. Setup & Imports
   - Install/import: polars, pandas, matplotlib, numpy, PartitionedAccessor, Hydrophone
   - Set AWS profile and analysis parameters (date range, hydrophone)

2. Load Ship Metrics (Method 1 only)
   - scan_parquet from S3 across all available days (2/7–2/13)
   - Filter: confidence >= 0.5
   - Parse s_timestamp / l_timestamp

3. Load Acoustic Data
   - PartitionedAccessor(Hydrophone.ORCASOUND_LAB, start=2/1 or earlier, end=2/13)
   - Load broadband via get_time_range(psd=False)
   - Load comm band via get_broadband(500, 15000, ref=1)
   - Merge into a single timeseries DataFrame indexed by timestamp

4. Build Ship-Presence Mask
   - For each ship track, mark all timestamps in acoustic data as ship-present
   - Add boolean column ship_present to acoustic DataFrame
   - Calculate ship_free_pct per window

5. Method 1 — Compute Ship-Filtered Percentiles
   - Loop over window_days in [1, 2, 5, 7]
   - Slice acoustic data to window, keep only ship_present==False rows
   - Compute quantiles(0.05, 0.10, 0.25, 0.50) for both bands

6. Method 2 — Compute Unfiltered Percentiles
   - Loop over window_days in [1, 2, 3, 5, 7, 10, 14]
   - Slice acoustic data to window (no filter)
   - Compute same quantiles for both bands

7. Results Table
   - Combine Method 1 + Method 2 results into summary DataFrame
   - Display as formatted table

8. Visualizations
   - Plot A: Ambient level vs. window length by method
   - Plot B: Method 1 vs Method 2 head-to-head for shared windows
   - Plot C: Ship-free fraction by window length
   - Plot D: Ship presence by hour of day
```

### Integration Points

- **PartitionedAccessor** from `src/orcasound_noise/analysis/partitioned_accessor.py` — using the local main branch version (constructor: `PartitionedAccessor(hydrophone)`)
- **Hydrophone enum** from `src/orcasound_noise/utils/hydrophone.py` — `Hydrophone.ORCASOUND_LAB`
- **AWS S3** — ship metrics at `s3://acoustic-sandbox/ambient-sound-analysis/temp_ship_metrics/` with profile `ambient-sound-team`; sound data at `s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/`
- **orcasound conda env** — Python 3.11, includes polars, pandas, geopandas, matplotlib, numpy, pyarrow

---

## Open Questions / Risks

- **Ship presence mask efficiency**: Joining per-second acoustic timestamps against hundreds of ship intervals can be slow. The notebook's `ShipMetricsCalculator` pattern does this with a per-row `apply()` which is O(ships × seconds). Consider using `polars join_where` (as shown in the demo notebook) for better performance.

- **Ship metrics `bb_series` looks suspicious**: In the sample data, bb values are all `-171.640658` (the `bb_ref` constant negated), suggesting those rows may have had missing or zero broadband data during those passages. The notebook should inspect and document this before relying on acoustic values from the ship metrics file. The raw acoustic data from `PartitionedAccessor` will be used directly instead.

- **Method 1 window anchor**: The analysis uses windows *ending* on 2/13 (the last day of ship data). E.g., the 7-day window is 2/7–2/13; the 1-day window is 2/13 only. If a different anchor is preferred (e.g., always starting from 2/7), this is easy to change.

- **Communication band from PSD**: The comm band calculation requires loading full PSD data (~100 columns), which is larger than broadband-only. The `get_broadband(500, 15000, ref=1)` method on `PartitionedAccessor` handles this but may be slow for 14-day windows.

- **polars 1.38.0 yanked**: The version is marked yanked on PyPI. If it causes runtime issues, pin to the most recent stable release instead.

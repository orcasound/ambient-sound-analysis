# Ancient Ambient Comparison — Sprint Plan

Derived from: `ancient-ambient-comparison-spec.md`

This is a research notebook project. "Mergeable PR" means the notebook runs end-to-end without errors and every committed cell produces visible, interpretable output. There are no automated tests — validation is notebook execution + visual inspection of outputs.

---

## Sprint 1: Fix PartitionedAccessor bugs, create branch, and verify data access

**PR summary**: Creates the `ancient-ambient-analysis` branch, fixes two bugs in `PartitionedAccessor` that would otherwise block the analysis (a cross-month date filter bug and an eager-DataFrame API misuse in `get_broadband`), creates the notebook skeleton with verified end-to-end data access to both S3 sources.

### Tickets

- [ ] **1.1 — Create branch and notebook skeleton**
  Create branch `ancient-ambient-analysis` from `main`. Create `notebooks/ancient_ambient_comparison.ipynb` (this implicitly creates `notebooks/`). Add:
  - Cell 1 (markdown): Title, purpose, date, and a note about the `orcasound` conda environment
  - Cell 2 (code): All imports — `polars`, `pandas`, `numpy`, `matplotlib`, `sys`; `sys.path` insert for `src/`; import `PartitionedAccessor` and `Hydrophone`
  - Cell 3 (code): Parameters block — `HYDROPHONE = Hydrophone.ORCASOUND_LAB`, `ANALYSIS_END = datetime(2026, 2, 13, 23, 59, 59)`, `SHIP_DATA_START = datetime(2026, 2, 7)`, `EXTENDED_START = datetime(2026, 1, 31)`, `AWS_PROFILE = "ambient-sound-team"`, `CONFIDENCE_THRESHOLD = 0.5`, `COMM_BAND = (500, 15000)`, `PERCENTILES = [0.05, 0.10, 0.25, 0.50]`, `METHOD1_WINDOWS = [1, 2, 5, 7]`, `METHOD2_WINDOWS = [1, 2, 3, 5, 7, 10, 14]`
  Validation: Cell 2 runs without ImportError; all parameters defined.

- [ ] **1.2 — Fix `get_time_range` cross-month date filter in `partitioned_accessor.py`**
  In `src/orcasound_noise/analysis/partitioned_accessor.py`, the `get_time_range` method applies independent `>=`/`<=` comparisons on the `year`, `month`, and `day` partition columns, which produces zero results for any date range that crosses a month boundary (e.g., `2026-01-31` to `2026-02-13` would require `day >= 31 AND day <= 13`, which is impossible).

  Fix: replace lines 48–57 with a single filter on the timestamp index column, which is already correct:
  ```python
  filtered = df.filter(
      (pl.col('__index_level_0__') >= start_time) &
      (pl.col('__index_level_0__') <= end_time)
  )
  ```
  The `year`/`month`/`day` partition column filters served only as S3 partition-pruning hints but were incorrect for cross-month ranges; the timestamp index filter handles correctness for all ranges.
  Validation: Existing golden tests still pass (`pytest tests/`). For this sprint, also manually verify that the fix works by calling `get_time_range(datetime(2026, 1, 31), datetime(2026, 2, 2), psd=False)` in the notebook and checking the result spans both months.

- [ ] **1.3 — Fix `get_broadband` eager-DataFrame API misuse in `partitioned_accessor.py`**
  In `get_broadband`, `get_time_range` is called first and returns an already-collected `pl.DataFrame`. Two subsequent calls treat it incorrectly:
  1. `df.collect_schema().names()` — `.collect_schema()` is a `LazyFrame` method; use `df.columns` instead
  2. `return broadband.collect()` — `broadband` is built via `.filter`/`.with_columns`/`.select` on a `pl.DataFrame`, which returns a `pl.DataFrame` (not a `LazyFrame`); remove the `.collect()` call

  Fix in `get_broadband`:
  - Line 78: `col for col in df.collect_schema().names()` → `col for col in df.columns`
  - Line 93: `return broadband.collect()` → `return broadband`
  Validation: Call `accessor.get_broadband(datetime(2026, 2, 13), datetime(2026, 2, 13, 0, 5, 0), 500, 15000, ref=1)` in the notebook and confirm it returns a DataFrame without error.

- [ ] **1.4 — Verify ship metrics S3 access and preview schema**
  Add cells that:
  - Load a single day of ship metrics: `pl.scan_parquet("s3://acoustic-sandbox/ambient-sound-analysis/temp_ship_metrics/year=2026/month=02/day=11/*.parquet", storage_options={"aws_profile": "ambient-sound-team", "aws_region": "us-west-2"}).collect()`
  - Print shape, column names, dtypes, and 3 sample rows
  - Add a markdown cell noting the `bb_series` anomaly (values equal to `-bb_ref`, −171.64 dB, for distant ships with no acoustic data — this analysis will use raw `PartitionedAccessor` data instead)
  Validation: Loads without error; shape is `(N, 27)` where N > 0; columns include `s_timestamp`, `l_timestamp`, `confidence`, `min_dist`, `is_isolated`.

- [ ] **1.5 — Verify acoustic data S3 access via PartitionedAccessor**
  Add cells that:
  - Instantiate `accessor = PartitionedAccessor(Hydrophone.ORCASOUND_LAB)`
  - Call `accessor.get_time_range(datetime(2026, 2, 13, 0, 0, 0), datetime(2026, 2, 13, 0, 5, 0), psd=False)` — 5 minutes of broadband as a smoke test
  - Call `accessor.get_broadband(datetime(2026, 2, 13, 0, 0, 0), datetime(2026, 2, 13, 0, 5, 0), 500, 15000, ref=1)` — 5 minutes of comm band (also validates the bug fix from 1.3)
  - Print shape and head for each result
  Validation: Both calls return DataFrames without error; broadband has column `'0'` with float values in a sensible dB range; comm band result has a `sound_pressure_level_db` column (or equivalent from `get_broadband`).

### Validation
- [ ] Existing golden tests pass: `pytest tests/` from repo root
- [ ] Notebook runs from top to bottom with a fresh kernel without errors
- [ ] Ship metrics 5-min sample loads (27 columns confirmed)
- [ ] Broadband and comm band 5-min samples both load without error

### PR safety notes
Bug fixes in `partitioned_accessor.py` are backwards-compatible: removing the broken partition-column filters in `get_time_range` makes all existing same-month queries continue to work (they relied on `__index_level_0__` for correctness already); fixing `collect_schema` and `.collect()` in `get_broadband` corrects behavior that was previously broken for all callers.

---

## Sprint 2: Ship presence analysis and ship-free statistics

**PR summary**: Loads all 7 days of ship metrics (2/7–2/13), applies the confidence filter, builds an efficient per-second ship-presence mask using polars `join_where`, and produces two plots: ship-free fraction by window length (Plot C) and ship presence by hour of day (Plot D).

### Tickets

- [ ] **2.1 — Load and filter all ship metrics (2/7–2/13)**
  Add cells that:
  - Load all 7 days in one `scan_parquet` call using a wildcard path or loop over days 7–13
  - Apply confidence filter: `confidence >= CONFIDENCE_THRESHOLD`
  - Ensure `s_timestamp` and `l_timestamp` are parsed as datetime
  - Print total track count before and after filter
  Validation: Result is a polars DataFrame with at least 200 valid tracks (based on ~50 ships/day × 7 days); `s_timestamp` and `l_timestamp` are datetime dtype.

- [ ] **2.2 — Build per-second ship-presence mask**
  Add cells that:
  - Create a 1-second timestamp spine covering `SHIP_DATA_START` to `ANALYSIS_END` (approximately 600,000 rows — exact count will vary due to second-level granularity of endpoints)
  - Use polars `join_where` to mark each spine timestamp as `ship_present = True` if any valid track's `[s_timestamp, l_timestamp]` interval overlaps it; otherwise `ship_present = False`
  - Print the total ship-present and ship-free seconds
  Note: This mask is based on the synthetic 7-day spine, independent of acoustic data availability. The acoustic data may have gaps and will not have exactly the same number of rows.
  Validation: All rows in spine have a boolean `ship_present` value; sum of ship-present + ship-free equals total spine rows; ship-free count is positive.

- [ ] **2.3 — Compute ship-free fraction per window**
  Add a cell that loops over `METHOD1_WINDOWS` (1, 2, 5, 7 days), slices the presence mask to the last D days (ending `ANALYSIS_END`), and computes `ship_free_pct = (ship_present==False).sum() / len(window)`. Store in a summary DataFrame: `window_days`, `ship_free_pct`, `ship_free_seconds`, `total_seconds`.
  Validation: All 4 window rows present; all `ship_free_pct` values between 0 and 1. Note: ordering is not guaranteed to be monotonic — individual days may have higher or lower traffic than the average.

- [ ] **2.4 — Plot C: Ship-free fraction by window length**
  Add a matplotlib bar chart: `ship_free_pct` (y-axis, 0–1 scale) vs `window_days` (x-axis) for Method 1 windows. Label bars with percentage text. Title: "Fraction of Ship-Free Time by Analysis Window (2/7–2/13)".
  Validation: Plot renders; all 4 bars visible with labels; y-axis shows 0–1 range.

- [ ] **2.5 — Plot D: Ship presence by hour of day**
  Add a cell that computes, for each hour of day (0–23), the fraction of seconds in that hour (across all 7 days) that had a ship present. Plot as a matplotlib bar chart. Title: "Ship Presence by Hour of Day (2/7–2/13, Orcasound Lab)".
  Validation: Plot renders; 24 bars visible; values between 0 and 1.

### Validation
- [ ] Notebook runs end-to-end from top without errors
- [ ] Both plots render with correct axes and labels
- [ ] Ship-free fractions are reasonable (expected roughly 30–70% based on ~50 ships/day)

### PR safety notes
All new cells appended to the notebook. No existing source files modified.

---

## Sprint 3: Acoustic data loading and Method 1 (ship-filtered percentiles)

**PR summary**: Loads the full acoustic dataset needed for all analysis windows (14 days back to 2026-01-31), computes communication band levels, joins the ship-presence mask to the acoustic timeseries, and produces Method 1 ship-filtered percentiles for all windows (1, 2, 5, 7 days) across both bands.

### Tickets

- [ ] **3.1 — Load broadband and comm band for full analysis range (2026-01-31 to 2026-02-13)**
  Add cells that load once for the maximum window needed:
  - `bb_df = accessor.get_time_range(EXTENDED_START, ANALYSIS_END, psd=False)` — broadband column `'0'`
  - `comm_df = accessor.get_broadband(EXTENDED_START, ANALYSIS_END, COMM_BAND[0], COMM_BAND[1], ref=1)` — returns comm band dB column
  - Merge on `__index_level_0__` into a single DataFrame `acoustic_df` with columns: `timestamp`, `broadband_db`, `comm_band_db`
  - Print shape, date range (min/max timestamp), and 5-row sample
  Add a `%%time` cell and a markdown note: loading 14 days of PSD takes ~30–60 seconds.
  Validation: `acoustic_df` spans at least 2026-01-31 to 2026-02-13; both `broadband_db` and `comm_band_db` columns have non-null values; row count is approximately 1,000,000–1,200,000 (14 days at ~86,400 rows/day, with possible gaps).

- [ ] **3.2 — Join ship-presence mask to acoustic timeseries**
  Add a cell that left-joins the ship-presence mask (Sprint 2) onto `acoustic_df` by timestamp. The join is left on `acoustic_df` so no acoustic rows are dropped. Rows without a matching ship mask entry (e.g., timestamps before 2/7) get `ship_present = False` (acoustic data before the ship data window is always ship-free by definition).
  Print count of ship-present vs ship-free acoustic rows for the 2/7–2/13 slice.
  Validation: No acoustic rows are lost; `ship_present` column is boolean with no nulls; ship-present count for 2/7–2/13 slice is positive and less than total rows in that slice.

- [ ] **3.3 — Compute Method 1 ship-filtered percentiles for all windows**
  Add a cell that loops over `METHOD1_WINDOWS` (1, 2, 5, 7 days):
  - Slice `acoustic_df` to the last D days ending `ANALYSIS_END` (always within 2/7–2/13)
  - Filter to `ship_present == False`
  - Compute `pandas.quantile(PERCENTILES)` (or polars equivalent) for both `broadband_db` and `comm_band_db`
  - Accumulate results with schema: `method='ship_filtered'`, `window_days`, `band` (`'broadband'` or `'comm_band'`), `percentile`, `value_db`, `n_seconds`, `ship_free_pct`
  Print a sample of accumulated rows after each window.
  Validation: 4 windows × 2 bands × 4 percentiles = 32 result rows; no NaN values in `value_db`; broadband values roughly −20 to +30 dB; comm band values roughly 60–85 dB (based on notebook samples).

### Validation
- [ ] Notebook runs end-to-end from top without errors
- [ ] 32 Method 1 result rows present and non-null
- [ ] Acoustic data spans the full extended range (2/1/31–2/13); both bands present

### PR safety notes
The acoustic data load will be the slowest cell in the notebook (potentially 30–60 seconds for 14 days of PSD). No changes to existing source files in this sprint.

---

## Sprint 4: Method 2 (unfiltered percentiles), results table, and comparison plots

**PR summary**: Computes Method 2 unfiltered percentiles for all 7 windows using the already-loaded acoustic dataset, combines with Method 1 results into a formatted summary table, and produces the two comparison plots (Plot A: ambient level vs window length by method; Plot B: Method 1 vs Method 2 head-to-head at the 5th percentile).

### Tickets

- [ ] **4.1 — Compute Method 2 unfiltered percentiles for all windows**
  Add a cell that loops over `METHOD2_WINDOWS` (1, 2, 3, 5, 7, 10, 14 days):
  - Slice `acoustic_df` to the last D days ending `ANALYSIS_END` (no ship filter)
  - Compute `quantile(PERCENTILES)` for both `broadband_db` and `comm_band_db`
  - Accumulate results with schema: `method='unfiltered'`, `window_days`, `band`, `percentile`, `value_db`, `n_seconds`, `ship_free_pct=None`
  Note: The 14-day window requires `EXTENDED_START` (2026-01-31), which was loaded in Sprint 3. No additional data loading needed.
  Validation: 7 windows × 2 bands × 4 percentiles = 56 result rows; all non-null; values in plausible dB ranges.

- [ ] **4.2 — Build and display results summary table**
  Add cells that:
  - Combine Method 1 (32 rows) + Method 2 (56 rows) into a single `results_df` DataFrame (88 rows total)
  - Display a pivot table: rows indexed by `(method, window_days)`, columns as `(band, percentile)`, values as `value_db` formatted to 1 decimal place
  Validation: 88 rows in `results_df`; no NaN in `value_db`; pivot table renders cleanly in notebook output.

- [ ] **4.3 — Plot A: Ambient level vs. window length by method**
  Add a matplotlib figure with 2 subplots (one per band). In each subplot:
  - For each of the 4 percentiles: plot a solid line for Method 2 across all 7 window lengths; plot a dashed line with markers for Method 1 across its 4 window lengths (1, 2, 5, 7 days)
  - Use distinct colors per percentile; shared legend; x-axis = window_days, y-axis = value_db
  - Title per subplot: band name ("Broadband" / "Comm Band 500–15k Hz")
  - Overall figure title: "Estimated Ancient Ambient Level by Method and Window Length"
  Validation: 4 line pairs visible per subplot; axis labels present; legend readable.

- [ ] **4.4 — Plot B: Method 1 vs Method 2 head-to-head at 5th percentile**
  Add a matplotlib grouped bar chart: for each shared window length (1, 2, 5, 7 days), show side-by-side bars for Method 1 (ship-filtered) and Method 2 (unfiltered) 5th percentile, faceted into two subplots (one per band). Annotate each bar pair with the dB difference (Method 2 − Method 1).
  Title: "5th Percentile Ancient Ambient: Ship-Filtered vs Unfiltered"
  Validation: 4 window groups × 2 bars × 2 subplots render; dB differences annotated on each pair.

- [ ] **4.5 — Add interpretation markdown cell**
  Add a final markdown cell documenting findings:
  - How much does ship filtering change the estimate? (typical dB difference across windows)
  - Does the estimate stabilize with longer windows? At what window length?
  - Which band shows more sensitivity to ship filtering?
  - Recommendation: which method and window length best estimates ancient ambient?
  Note: fill this in after running the notebook with real data.
  Validation: Cell is present with section headers and substantive content (not just placeholder text).

### Validation
- [ ] Notebook runs end-to-end from a fresh kernel without errors
- [ ] 88 result rows present, non-null
- [ ] All 4 plots render (A, B, C, D) with correct labels
- [ ] Summary table displays cleanly

### PR safety notes
No source files modified. The only new work is notebook cells. The 14-day extended data was loaded in Sprint 3 so no additional S3 calls are needed here.

---

## Implementation Notes

### Branch
All work on `ancient-ambient-analysis`. Each sprint is a PR to `main`.

### conda environment
```bash
conda activate orcasound
cd ambient-sound-analysis
jupyter notebook notebooks/ancient_ambient_comparison.ipynb
```

### PartitionedAccessor version
Use the local main-branch version. Constructor: `PartitionedAccessor(hydrophone)`. Sprint 1 tickets 1.2–1.3 fix the two bugs in this class before any analysis depends on them.

### Ship-presence mask strategy
Use polars `join_where` (pattern from `explore_shipdata_em_edits.ipynb`) rather than row-wise `apply()`. The `join_where` approach is ~100× faster for the 600,000-row timestamp spine.

### Data loading strategy
Load acoustic data once in Sprint 3 for the full 14-day range (2026-01-31 to 2026-02-13). Both Method 1 (7-day sub-slice) and Method 2 (all windows including 14-day) use this single loaded DataFrame. No redundant S3 fetches.

### Known data quirk
The `bb_series` column in ship metrics parquet shows constant values of −171.64 dB for many ships — this equals the negated `bb_ref` constant and indicates missing broadband data for those passages (e.g., ship too far, or acoustic data gap). Document this in Sprint 1 ticket 1.4 and confirm the analysis uses raw `PartitionedAccessor` data directly rather than the pre-aggregated acoustic values in the ship metrics file.

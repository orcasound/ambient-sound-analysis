# Ambient Noise Analysis

This repository holds code for UW MSDS capstone project analyzing ambient noise levels in historical orcasound hydrophone data. There are three main components:

- The pipeline that converts historical .ts files into compact Power Spetral Density (PSD) grids saves as parquert files.
- The accessor that reads, filters and collates these files to produce PDS dataframes with specific time ranges, and
- The dashboard that displays key information found using Streamlit.

# Definitions

## PSD

A Power Spectral Density describes the power present in the signal as a function of frequency, per unit frequency and time. In this codebase, they are generally interacted with as Pandas Dataframes, where the index represents timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency and time, in decibels.

The **time frequency**, or **delta_t**, represents the number of seconds per sample. A time frequency of 1 means that timestamps are one second apart, and each data point represents the average noise over one second in that frequency band. Teh default for generated data is 1 second frequency.

The **octave band** represents the breakout in frequency bands. This is generally done in fractions of an octave, with the default being 1/3 octaves. The value in the column index represents the upper range. For example, in a 1/3rd octave PSD, the 63 column represents the power in the range of 0 to 63, while the 80 column represents the power from 63 to 80.

# Accessor

The accessor is the toolkit used for accessing the stored files. This is done by initializing a NoiseAccessor object for a specificc hydrophone, and then requesting a time range and optional time and frequency granularity. The accessor will scan the generated archive files, load the correct ones, concatenate the data into a single dataframe and then trim out any data outside of the requested range.

Ex:

```
from src.analysis import NoiseAcccessor

ac = NoiseAcccessor(Hydrophone.ORCASOUND_LAB)
df = ac.create_df(dt.datetime(2023, 2, 1), dt.datetime(2023, 2, 2), delta_t=10, delta_f="3oct")
print(df.shape) # (8638, 26)
```

## Initialization

To initialize a NoiseAccessor object, all thats needed is a Hydrophone enum instance. This instance contains all needed connection info.

## Create a Dataframe

The NoiseAccessor object has a create_df method that can be used to generate dataframes of requested ranges. It needs the following arguments:

- start: datetime object representing start of range
- end: datetime object representing end of range
- delta_t: Int, Time frequency to find
- delta_f: Str, Hz frequency to find. Use format '50hz' for linear hz bands or '3oct' for octave bands
- round_timestamps: Bool, default False. Set to True to round timestamps to the delta_t frequency. Good for when grouping by time.

Currently, only 1 second 3rd octave files (delta_1=1, delta_f="3oct") are periodically generated and available in AWS: anything else must be manually created and uploaded first using the NoiseAnalysisPipeline.

## delta_f

This argument is a string to allow different frequency band methods. Note that onle frequencies that have been pre-compiled are available to access.

- To access a linear frequency band, use the "hz" suffix. For example, a "50hz" would return columns like [0, 50, 100, 150...]
- To access octave frequency, use the "oct" suffix. "3oct" will return the 1/3 octave bands, starting with [63, 80, 100, 125, 160...]
- To access broadband noise, use the "broadband" suffix. This returns a single column representing the total noise level.

## round_timestamps

Due to the nature of the source data, timestamps can experience some drift in the nanosecond precision. A dataframe may start with 00:00:00.010 but may end with 00:00:00.020 or a larger gap.

If you want to do time-based analysis across multiple days, this can cause mis-alignment. To correct, set the _round_timestamps_ argument to true. This will round the timestamps to the delta_t frequency, dropping nanosecond values. For example, at delta_t=10 and round_timestamps=True, every timestamp will be a multiple of 10 seconds from the minute.

_*Warning*_ Rounding is only available when delta_t is a divisor of 60.

# Ambient Noise Analysis

This repository holds code for a [UW MSDS capstone project](https://www.washington.edu/datasciencemasters/capstone-projects/) that analyzes ambient underwater noise levels in historical [Orcasound](https://orcasound.net) hydrophone data. A hydrophone is an underwater microphone that can be used to monitor ocean noise levels. In the critical habitat of endangered Southern Resident killer whales, the predominant souces of anthropogenic noise pollution are commercial ships, and secondarily recreational boats.

This open source project has three main components:

- The pipeline that converts historical .ts files into compact Power Spectral Density (PSD) grids saved as [parquet files](https://parquet.apache.org/).
- The accessor that reads, filters and collates these files to produce PSD dataframes with specific time ranges, and
- The dashboard that displays key results using [Streamlit](https://streamlit.io/).

# Definitions

## PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

The **sample duration**, or **delta_t** (time interval), represents the number of seconds per sample. A duration of 1 means that timestamps are one second apart, and each data point represents the average noise level over one second in that frequency band. The default for generated data is 1 second duration.

The **frequency band** represents the frequency range over which the power is integrated. Within the vessel noise and marine bioacoustic literature, this is commonly done in fractions of an octave, e.g. 1/3 or 1/12 octave bands. The value in the column index represents the upper frequency range. For example, in a 1/3rd octave PSD, the 63 column represents the power in the range of 0 to 63 Hz, while the 80 column represents the power from 63 to 80 Hz.

# Accessor

The accessor is the toolkit used for accessing the stored files. This is done by initializing a NoiseAccessor object for a specific hydrophone, and then requesting a time range and optional time and frequency resolution (or granularity). The accessor scans the generated archive files, loads the correct ones, concatenates the data into a single dataframe, and then trims any data outside of the requested range.

Example:

```
from src.analysis import NoiseAcccessor

ac = NoiseAcccessor(Hydrophone.ORCASOUND_LAB)
df = ac.create_df(dt.datetime(2023, 2, 1), dt.datetime(2023, 2, 2), delta_t=10, delta_f="3oct")
print(df.shape) # (8638, 26)
```

where the parameters `delta_t=10` and `delta_f="3oct"` specify computation of 1/3-octave band levels over 10-second time intervals.

## Initialization

To initialize a NoiseAccessor object, all that is needed a Hydrophone enum instance. This instance contains all needed connection info.

## Create a Dataframe

The NoiseAccessor object has a create_df method that can be used to generate dataframes of requested ranges. It needs the following arguments:

- start: datetime object representing start of range
- end: datetime object representing end of range
- delta_t: Int, Time interval to find
- delta_f: Str, Hz frequency to find. Use format '50hz' for linear hz bands or '3oct' for octave bands
- round_timestamps: Bool, default False. Set to True to round timestamps to the delta_t frequency. Good for when grouping by time.

## delta_f

This argument is a string to allow different frequency banding methods. Note that only frequency bands that have been pre-compiled are available to access.

- To access linear frequency bands, use the "hz" suffix. For example, a "50hz" would return frequency bounds in columns like [0, 50, 100, 150...]
- To access (fractions of) octave bands, use the "oct" suffix. "3oct" will return the 1/3 octave bands, starting with [63, 80, 100, 125, 160...]
- To access broadband noise, use the "broadband" suffix. This returns a single column representing the total noise level across all frequencies sensed by the hydrophone recording system.

## round_timestamps

Due to the nature of Orcasound's source data (see the [orcanode repo](https://github.com/orcasound/orcanode)), timestamps can experience some drift in the nanosecond precision. A dataframe may start with 00:00:00.010 but may end with 00:00:00.020 or a larger gap.

If you want to do time-based analysis across multiple days, this can cause mis-alignment. To correct, set the _round_timestamps_ argument to true. This will round the timestamps to the delta_t value's precision, dropping nanosecond values. For example, at delta_t=10 and round_timestamps=True, every timestamp will be a multiple of 10 seconds from the minute.

_*Warning*_ Rounding is only available when (delta_t < 60) and (60% delta_t = 0)

# Noise Accessor

The accessor is the toolkit used for accessing the stored files. This is done by initializing a NoiseAccessor object for a specific hydrophone, and then requesting a time range and optional time and frequency resolution (or granularity). The accessor scans the generated archive files, loads the correct ones, concatenates the data into a single dataframe, and then trims any data outside of the requested range.

Example:

```python
from src.orcasound_noise.analysis import NoiseAcccessor

ac = NoiseAcccessor(Hydrophone.ORCASOUND_LAB)
df = ac.create_df(dt.datetime(2023, 2, 1), dt.datetime(2023, 2, 2), delta_t=10, delta_f="3oct")
print(df.shape) # (8638, 26)
```

where the parameters `delta_t=10` and `delta_f="3oct"` specify computation of 1/3-octave band levels over 10-second time intervals.

# Usage

To initialize a NoiseAccessor object, all that is needed a Hydrophone enum instance. This instance contains all needed connection info.

## Create a Dataframe

The NoiseAccessor object has a create_df method that can be used to generate dataframes of requested ranges. It needs the following arguments:

- start: datetime object representing start of range
- end: datetime object representing end of range
- delta_t: Int, Time interval to find
- delta_f: Str, Hz frequency to find. Use format '50hz' for linear hz bands or '3oct' for octave bands
- round_timestamps: Bool, default False. Set to True to round timestamps to the delta_t frequency. Good for when grouping by time.

Currently, only 1 second 3rd octave files (`delta_t=1, delta_f="3oct"`) are periodically generated and available in AWS: anything else must be manually created and uploaded first using the [NoiseAnalysisPipeline](../pipeline/README.md).

## delta_f

This argument is a string to allow different frequency banding methods. Note that only frequency bands that have been pre-compiled are available to access.

- To access linear frequency bands, use the "hz" suffix. For example, a "50hz" would return frequency bounds in columns like [0, 50, 100, 150...]
- To access (fractions of) octave bands, use the "oct" suffix. "3oct" will return the 1/3 octave bands, starting with [63, 80, 100, 125, 160...]
- To access broadband noise, use the "broadband" suffix. This returns a single column representing the total noise level across all frequencies sensed by the hydrophone recording system.

## round_timestamps

Due to the nature of Orcasound's source data (see the [orcanode repo](https://github.com/orcasound/orcanode)), timestamps can experience some drift in the nanosecond precision. A dataframe may start with 00:00:00.010 but may end with 00:00:00.020 or a larger gap.

If you want to do time-based analysis across multiple days, this can cause mis-alignment. To correct, set the _round_timestamps_ argument to true. This will round the timestamps to the delta_t value's precision, dropping nanosecond values. For example, at delta_t=10 and round_timestamps=True, every timestamp will be a multiple of 10 seconds from the minute.

_*Warning*_ Rounding is only available when delta_t is a divisor of 60.

# Structure

# Ambient Noise Analysis

This repository holds code for a [UW MSDS capstone project](https://www.washington.edu/datasciencemasters/capstone-projects/) that analyzes ambient underwater noise levels in historical [Orcasound](https://orcasound.net) hydrophone data. A hydrophone is an underwater microphone that can be used to monitor ocean noise levels. In the critical habitat of endangered Southern Resident killer whales, the predominant souces of anthropogenic noise pollution are commercial ships, and secondarily recreational boats.

This open source project has three main components:

- The [pipeline](src/pipeline/README.md) that converts historical .ts files into compact Power Spectral Density (PSD) grids saved as [parquet files](https://parquet.apache.org/).
- The [accessor](src/accessor/README.md) that reads, filters and collates these files to produce PSD dataframes with specific time ranges
- The [dashboard](src/dashboard/README.md) that displays key results using [Streamlit](https://streamlit.io/).

# Quickstart

## Install

## Download a [PSD](#psd) as a dataframe

The accessor tool can be used to download pre-computed PSDs as dataframes. At the current time, only 1 second 1/3 octave PSDs are regularly archived.

```
from src.analysis import NoiseAcccessor

ac = NoiseAcccessor(Hydrophone.ORCASOUND_LAB)
df = ac.create_df(dt.datetime(2023, 2, 1), dt.datetime(2023, 2, 2), delta_t=10, delta_f="3oct")
print(df.shape) # (8638, 26)
```

# Definitions

## PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

The **sample duration**, or **delta_t** (time interval), represents the number of seconds per sample. A duration of 1 means that timestamps are one second apart, and each data point represents the average noise level over one second in that frequency band. The default for generated data is 1 second duration.

The **frequency band** represents the frequency range over which the power is integrated. Within the vessel noise and marine bioacoustic literature, this is commonly done in fractions of an octave, e.g. 1/3 or 1/12 octave bands. The value in the column index represents the upper frequency range. For example, in a 1/3rd octave PSD, the 63 column represents the power in the range of 0 to 63 Hz, while the 80 column represents the power from 63 to 80 Hz.

# Built With

- [librosa](https://librosa.org/) - Used for audio spectral analysis.
- [ffmpeg](https://ffmpeg.org/) - Used for audio conversion.
- [Streamlit](https://streamlit.io/) - Used for the dashboard presentation.
- [orca-hls-utils](https://github.com/orcasound/orca-hls-utils) - Used for HLS acquisition.

# Authors

- Caleb Case - [GitHub](https://github.com/CaseCal) [LinkedIn](https://www.linkedin.com/in/caleb-case-76132782/)
- Mitch Haldeman - [GitHub](https://github.com/mitchhaldeman) [LinkedIn](https://www.linkedin.com/in/mitchhaldeman/)
- Grant Savage - [GitHub](https://github.com/savageGrant)

# Acknowledgments

- Thanks to Valentina Staneva, Val and Scott Veirs, Ben Hendricks, and everyone else connected to the Orcasounds org for their input and guidance.
- Thanks to Megan Hazen and the rest of the UW MSDS faculty for their teachings and guidance.

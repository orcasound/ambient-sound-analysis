# Ambient Noise Analysis

This repository holds code for a [UW MSDS capstone project](https://www.washington.edu/datasciencemasters/capstone-projects/) that analyzes ambient underwater noise levels in historical [Orcasound](https://orcasound.net) hydrophone data. A hydrophone is an underwater microphone that can be used to monitor ocean noise levels. In the critical habitat of endangered Southern Resident killer whales, the predominant souces of anthropogenic noise pollution are commercial ships, and secondarily recreational boats.

This open source project has three main components:

- The [pipeline](src/orcasound_noise/pipeline/README.md) that converts historical .ts files into compact [Power Spectral Density (PSD)](#psd) grids saved as [parquet files](https://parquet.apache.org/).
- The [accessor](src/orcasound_noise/analysis/README.md) that reads, filters and collates these files to produce PSD dataframes with specific time ranges
- The [dashboard](src/orcasound_noise/dashboard/README.md) that displays key results using [Streamlit](https://streamlit.io/). The live dashboard is directly connected to the repo and visible [here](https://orcasound-ambient-sound-analysis-dashboard-boh8ls.streamlit.app)

# Quickstart

## Install

To install directly from git:

```
pip install orcasound_noise @ git+https://github.com/orcasound/ambient-sound-analysis.git
```

To install from a local copy, navigate to the top folder and enter

```
pip install .
```

## Download a [PSD](#psd) as a dataframe

The accessor tool can be used to download pre-computed PSDs as dataframes. At the current time, only 1 second 1/3 octave PSDs are regularly archived.

```python
import datetime as dt

from orcasound_noise.analysis import NoiseAccessor
from orcasound_noise.utils import Hydrophone

ac = NoiseAccessor(Hydrophone.ORCASOUND_LAB)
df = ac.create_df(dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 2), round_timestamps=True)
print(df)
```

## Generate a new PSD

For other time intervals and frequency bands, a new PSD can be computed using the pipeline package.

```python
import datetime as dt

from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone

pipeline = NoiseAnalysisPipeline(Hydrophone.ORCASOUND_LAB, pqt_folder='pqt', delta_f=10, bands=3, delta_t=1)
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2020, 2, 1, 9), dt.datetime(2020, 2, 1, 10), upload_to_s3=False)
```

This will save a PSD with 1 second intervals and 10hz frequency bands as a parquet file in the 'pqt' folder. It will also save a broadband PSD in the same folder.

To open the PSD, simply read parquet using pandas:

```python
import pandas as pd

psd_df = pd.read_parquet(psd_path)
print(psd_df.head())
```

## Run the dashboard locally

Download the repo, then

```
pip install -r requirements.txt
python -m streamlit run dashboard.py
```

The dashboard will open at localhost.

# Definitions

## PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

## Sample duration

The **sample duration**, or **delta_t** (time interval), represents the number of seconds per sample. A duration of 1 means that timestamps are one second apart, and each data point represents the average noise level over one second in that frequency band. The default for generated data is 1 second duration.

## Frequency Band

The **frequency band** represents the frequency range over which the power is integrated. Within the vessel noise and marine bioacoustic literature, this is commonly done in fractions of an octave, e.g. 1/3 or 1/12 octave bands. The value in the column index represents the upper frequency range. For example, in a 1/3rd octave PSD, the 63 column represents the power in the range of 0 to 63 Hz, while the 80 column represents the power from 63 to 80 Hz.

# Hydrophone

Hydrophones are referenced using the Hydrophone enum located in [the utils package.](src/orcasound_noise/utils/hydrophone.py). These enums store all the relevant connection info for each hydrophone, including where to find the streamed ts files and where to store the archived parquet files.

```python
from orcasound_noise.utils import Hydrophone

my_hydrophone = Hydrophone.ORCASOUND_LAB
```

# S3 File Connector

The S3 File connector provides an interface for interacting with the S3 buckets where data is stored. This is generally initialized within other objects and rarely should be used directly.

Currently, all files are available for download without authentication. If files are being uploaded, then an AWS*ACCESS_KEY_ID* and secret must be available in the environment. This can be done by adding a `.aws-config` file to the root of your working folder, (see [example file](.aws-config-example)) or by any other means of modifying the environment.

For example, to programaticaly provide authentication:

```python
import os
from orcasound_noise.pipeline import NoiseAnalysisPipeline

# Set env
os.env["AWS_ACCESS_KEY_ID"] = "my_id"
os.env["AWS_SECRET_ACCESS_KEY"] = "my_secret"

# Upload file
pipeline = NoiseAnalysisPipeline(Hydrophone.ORCASOUND_LAB, pqt_folder='pqt', delta_f=10, bands=3, delta_t=1)
pipeline.generate_parquet_file(dt.datetime(2020, 1, 1), dt.datetime(2020, 2, 1), upload_to_s3=True)
```

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

# Ambient Sound Analysis

This repository holds code for a [UW MSDS capstone project](https://www.washington.edu/datasciencemasters/capstone-projects/) that analyzes ambient underwater noise levels in historical [Orcasound](https://orcasound.net) hydrophone data. A hydrophone is an underwater microphone that can be used to monitor ocean noise levels. In the critical habitat of endangered Southern Resident killer whales, the predominant souces of anthropogenic noise pollution are commercial ships, and secondarily recreational boats.

This open source project has three main components:

- The [pipeline](src/orcasound_noise/pipeline/README.md) that converts historical `.ts` files into compact [Power Spectral Density (PSD)](#psd) grids saved as [parquet files](https://parquet.apache.org/).
- The [accessor](src/orcasound_noise/analysis/README.md) that reads, filters and collates these files to produce PSD dataframes with specific time ranges
- The [dashboard](pages/README.md) that displays key results using [Streamlit](https://streamlit.io/). The live dashboard is directly connected to the repo and visible [here](https://orcasound-ambient-sound-analysis-dashboard-boh8ls.streamlit.app)

Guides to recreate the AWS environments used to process the hydrophone data can be found in the [aws_batch](src/orcasound_noise/aws_batch/README.md) directory.

## Tutorial

This tutorial is designed to provide a step-by-step guide for utilizing this repository.

### Installation

#### Cloning the Repository

In the desired location, perform the following to clone a copy of the repository onto your machine.

```commandline
git clone https://github.com/orcasound/ambient-sound-analysis.git
```

#### Sample Virtual Environment

If starting from a new virtual environment, ensure that ffmpeg is included in the creation, and that the Python version is 3.11.

```commandline
cd ambient-sound-analysis
conda env create -f environment.yml
conda activate orca_env
```

##### For Windows Users

Sometimes `ffmpeg` can have path issues, and result in the following error when pulling the data: 

UnboundLocalError: local variable 'clip_start_time' referenced before assignment

For more information, see: https://stackoverflow.com/questions/65836756/python-ffmpeg-wont-accept-path-why

#### Installing Requirements

To install the requirements for this repository, run:

```commandline
python -m pip install .
```

You can also install directly from GitHub:

```
python -m pip install orcasound_noise@git+https://github.com/orcasound/ambient-sound-analysis
```

### Creating a new PSD

#### Imports

```python
import pandas as pd
from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone
import datetime as dt
```

#### Setting up a Pipeline Object

To access the hydrophone data, we set up a NoiseAnalysisPiepline object to pull from the S3 buckets. At minimum, the pipeline object requires specifying a hydrophone, a sample length, and a frequency.

The following are the available hydrophones:
* Port Townsend: PORT_TOWNSEND
* Bush Point: BUSH_POINT
* Sunsent Bay: SUNSET_BAY
* Orcasound Lab: ORCASOUND_LAB

In the following example, we collect 60-second samples at 1 Hz frequency from the Port Townsend hydrophone. It is recommended not to exceed 10 minute samples. 

Note: The following code needs to be wrapped in main.
```python
#Example 1: Port Townsend, 1 Hz Frequency, 60-second samples
if __name__ == '__main__':
    pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND,
                                     delta_f=1, bands=None,
                                     delta_t=60, mode='safe')
```

Here we can also specify the octave bands. Additionally, the pipeline may produce wav and parquet files in temporary folders. If desired, specify a folder path to save these files into. 

```python
#Example 2: Port Townsend, 1 Hz Frequency, 60-second samples, 
# 1/3rd octave bands, and saving wav+pqt files
if __name__ == '__main__':
    pipeline2 = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND,
                                     delta_f=1, bands=3,
                                     delta_t=60, wav_folder = 'wav',
                                     pqt_folder = 'pqt'
                                     mode='safe')
```

#### Generating a PSD into a Parquet File

Using the `generate_parquet_file` function, we can process the raw data from the S3 source and save the resulting PSDs in parquet files. 
This function requires a date range in the form of a datetime object, and can use down to the minute granularity (in UTC). 
There are two parquet files generated, the PSD and the broadband view, and the function returns the paths to each.  

The generate_parquet_file function calls upon `generate_psds`, which loads the `.ts` files from S3 and converts them to the desired PSDs. 

```python
#Example: Using pipeline object specified above, we generate the parquet files for 12pm - 1pm UTC
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 12), 
                                                          dt.datetime(2023, 3, 22, 13), 
                                                          upload_to_s3=False)
```

### Visualizing the Data

Now that the data has been processed, it can be visualized into spectrograms and time series plots.

#### Imports

```python
import pandas as pd
import matplotlib.pyplot as plt
from orcasound_noise.pipeline.acoustic_util import plot_spec, plot_bb
```

#### PSD/Broadband Data Frames

To read the parquet files generated in the previous section, we use the `read_parquet()` method from pandas.

```python
psd_df = pd.read_parquet(psd_path)
bb_df = pd.read_parquet(broadband_path)
```

#### Spectrogram

With the pandas data frames obtained from the parquet files, we can now visualize the PSD in a spectrogram, using the `plot_spec` method.

```python
plot_spec(psd_df)
```

This will create a spectrogram in plotly on your local machine.

<img width="600" alt="readme_spec" src="https://github.com/orcasound/ambient-sound-analysis/assets/118499445/e9edf520-a297-4f2f-97c8-b05ab6568b0d">

#### Broadband

To visualize the broadband dataframe, we plot it with the plot_bb method:

```python
plot_bb(bb_df)
```

<img width="600" alt="bb_readme" src="https://github.com/orcasound/ambient-sound-analysis/assets/118499445/824df19a-49b6-4810-a692-71028b6e6a01">

### Running the Dashboard Locally

Download the repo, then

```
pip install -r requirements.txt
python -m streamlit run dashboard.py
```

The dashboard will open at localhost.


## Definitions

### PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

### Sample duration

The **sample duration**, or **delta_t** (time interval), represents the number of seconds per sample. A duration of 1 means that timestamps are one second apart, and each data point represents the average noise level over one second in that frequency band. The default for generated data is 1 second duration.

### Frequency Band

The **frequency band** represents the frequency range over which the power is integrated. Within the vessel noise and marine bioacoustic literature, this is commonly done in fractions of an octave, e.g. 1/3 or 1/12 octave bands. The value in the column index represents the upper frequency range. For example, in a 1/3rd octave PSD, the 63 column represents the power in the range of 0 to 63 Hz, while the 80 column represents the power from 63 to 80 Hz.

### Hydrophone

Hydrophones are referenced using the Hydrophone enum located in [the utils package.](src/orcasound_noise/utils/hydrophone.py). These enums store all the relevant connection info for each hydrophone, including where to find the streamed ts files and where to store the archived parquet files.

```python
from orcasound_noise.utils import Hydrophone

my_hydrophone = Hydrophone.ORCASOUND_LAB
```

### S3 File Connector

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

## Built With

- [librosa](https://librosa.org/) - Used for audio spectral analysis.
- [ffmpeg](https://ffmpeg.org/) - Used for audio conversion.
- [Streamlit](https://streamlit.io/) - Used for the dashboard presentation.
- [orca-hls-utils](https://github.com/orcasound/orca-hls-utils) - Used for HLS acquisition.

## Authors

- Caleb Case - [GitHub](https://github.com/CaseCal) [LinkedIn](https://www.linkedin.com/in/caleb-case-76132782/)
- Mitch Haldeman - [GitHub](https://github.com/mitchhaldeman) [LinkedIn](https://www.linkedin.com/in/mitchhaldeman/)
- Grant Savage - [GitHub](https://github.com/savageGrant) [LinkedIn](https://www.linkedin.com/in/grantsavage/)
- Zach Price - [GitHub](https://github.com/zprice12) [LinkedIn](https://www.linkedin.com/in/zach-price-b65b98174/)
- Timothy Tan - [GitHub](https://github.com/ttan06) [LinkedIn](https://www.linkedin.com/in/timothytan6/)
- Vaibhav Mehrotra - [GitHub](https://github.com/vaibhavmehrotraml) [LinkedIn](https://www.linkedin.com/in/thevaibhavmehrotra/)

## Acknowledgments

- Thanks to Valentina Staneva, Val and Scott Veirs, Ben Hendricks, and everyone else connected to the Orcasounds org for their input and guidance.
- Thanks to Megan Hazen and the rest of the UW MSDS faculty for their teachings and guidance.

## References

Erbe, Christine. Underwater Acoustics: Noise and the Effects on Marine Mammals. Jasco Applied Sciences, https://www.oceansinitiative.org/wp-content/uploads/2012/07/PocketBook-3rd-ed.pdf.

Gabriele, C. M., Ponirakis, D., & Klinck, H. (2021). Underwater Sound Levels in Glacier Bay During Reduced Vessel Traffic Due to the COVID-19 Pandemic. Frontiers in Marine Science, 8. https://doi.org/10.3389/fmars.2021.674787

Heise, Kathy, et al. “PROPOSED METRICS FOR THE MANAGEMENT OF UNDERWATER NOISE FOR SOUTHERN RESIDENT KILLER WHALES.” Coastal Ocean Report Series. (2017). 10.25317/CORI20172. 

Sound Measurement. Discovery of Sound in the Sea. https://dosits.org/science/measurement/

Veirs, V. Veirs, S. (2018, November 9). Orcasound lab: a soundscape analysis case study in killer whale habitat with implications for coastal ocean observatories. https://orcasound.net/talks/2018-asa-vveirs/

Veirs, S. (2023, March 9). Salish Sea Bioacoustics: Marine Noise Pollution. https://www.emaze.com/@ALOWTWOLL/uwocean409-2023

Wall, Carrie C., et al. “The next wave of passive acoustic data management: How Centralized Access Can Enhance Science.” Frontiers in Marine Science, vol. 8, 14 July 2021, https://doi.org/10.3389/fmars.2021.703682.

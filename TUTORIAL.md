# Tutorial

This tutorial is designed to provide a step-by-step guide for utilizing this repository.

## Installation

### Cloning the Repository

In the desired location, perform the following to clone a copy of the repository onto your machine.

```commandline
git clone https://github.com/orcasound/ambient-sound-analysis.git
```

### Sample Virtual Environment

If starting from a new virtual environment, ensure that ffmpeg is included in the creation, and that the python version is 3.9.

```commandline
conda create -n orca_env -c conda-forge ffmpeg python=3.9

conda activate orca_env
```

#### For Windows Users

Sometimes ffmpeg can have path issues, and result in the following error when pulling the data: 

UnboundLocalError: local variable 'clip_start_time' referenced before assignment

For more information, see: https://stackoverflow.com/questions/65836756/python-ffmpeg-wont-accept-path-why

### Installing Requirements

To install the requirements for this repository, run:

```commandline
python -m pip install .
```

## Creating a new PSD

### Imports

```python
import pandas as pd
from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone
import datetime as dt
```

### Setting up a Pipeline Object

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

### Generating a PSD into a Parquet File

Using the generate_parquet_file function, we can process the raw data from the S3 source and save the resulting PSDs in parquet files. 
This function requires a date range in the form of a datetime object, and can use down to the minute granularity (in UTC). 
There are two parquet files generated, the PSD and the broadband view, and the function returns the paths to each.  

The generate_parquet_file function calls upon generate_psds, which loads the .ts files from S3 and converts them to the desired PSDs. 

```python
#Example: Using pipeline object specified above, we generate the parquet files for 11am - 12pm UTC
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11), 
                                                          dt.datetime(2023, 3, 22, 12), 
                                                          upload_to_s3=False)
```

## Visualizing the Data

Now that the data has been processed, it can be visualized into spectrograms and graphs.

### Imports

```python
import pandas as pd
import matplotlib.pyplot as plt
from orcasound_noise.pipeline.acoustic_util import plot_spec
```

### PSD/Broadband Data Frames

To read the parquet files generated in the previous section, we use the read_parquet() method from pandas.

```python
bb_df = pd.read_parquet(broadband_path)
psd_df = pd.read_parquet(psd_path)
```

### Spectrogram

With the pandas data frames obtained from the parquet files, we can now visualize the PSD in a spectrogram, using the plot_spec method.

```python
plot_spec(psd_df)
```

This will create a spectrogram in plotly on your local machine.

--insert example spectrogram here--

### Broadband

To visualize the broadband dataframe, we plot it with matplotlib:

```python
plt.plot(bb_df)
plt.show()
```

--insert example broadband here--

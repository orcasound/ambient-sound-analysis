# Pipeline

This pipeline overview is designed to give users an understanding of how the data goes from individual hydrophones to 
power spectral densities in the form of parquet files.

## Hydrophone Data Storage

Orcasound has four hydrophones located throughout the Puget Sound that continuously collect underwater acoustic data. 
Every few minutes, these hydrophones upload audio files, in the form of 10-second .ts clips, to Orcasound Amazon S3 buckets. 
This process has been ongoing for the past 5+ years, resulting in approximately 6TB of raw audio data, comprised of 
roughly 50 million 10-second audio clips. 

The goal of this pipeline is to accurately and efficiently convert these .ts files, 
based on the user's chosen frequency bands, averaging time, and date selection, into power spectral densities in the form 
of parquet files. This allows anyone to access this vast amount of data for exploration and understanding.

## Creating a Pipeline Object

Below we see the code needed to create a pipeline object. We initialize the object with Port Townsend as the chosen hydrophone, 
1Hz bands, 60-second averaging time, and safe mode. Note, we assume for this pipeline overview that everything is done in safe mode,
which uses multithreading to parallelize the downloading of .ts files. Fast mode implements multiprocessing to further increase 
the efficiency of the pipeline; however, fast mode has slight bugs that still need to be worked out.

```python
#Example 1: Port Townsend, 1 Hz Frequency, 60-second samples
if __name__ == '__main__':
    pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND,
                                     delta_f=1, bands=None,
                                     delta_t=60, mode='safe')
```

## Creating a PSD

### Initialization

Using the pipeline object we created, we call generate_parquet_file with a given start and end time. This function 
returns paths for the stored PSD and broadband parquet files. Users can read these parquet files as Dataframes for further 
exploration.

```python
#Example: Using pipeline object specified above, we generate the parquet files for 11am - 12pm UTC
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11), 
                                                          dt.datetime(2023, 3, 22, 12), 
                                                          upload_to_s3=False)
```

### Downloading and Converting the .ts Files

The generate_parquet_file function calls the generate_psds function, both located in [pipeline.py](pipeline.py). This function begins by creating a DateRangeHLSStream object,
providing a link to the Amazon S3 buckets with our desired hydrophone and date interval. Assuming we are operating in safe 
mode, the code uses the stream object to download the .ts files in 10-minute spans. 10-minute spans are determined by the 
polling_interval parameter; we suggest not changing this as larger spans have caused errors.

These 10-minute downloads of .ts files are then converted into 10-minute .wav files, which are saved in a temporary directory,
unless otherwise specified. All of this work is done by the get_next_clip function, a method of DateRangeHLSStream objects 
implemented in the orca_hls_utils package.

### Conversion from .wav to PSD and Broadband

The 10-minute .wav files are created sequentially in a while loop. After the creation of each individual .wav file, we convert 
that 10-minute .wav file into two Dataframes; one is a power spectral density and the other is broadband. This work is done 
by the wav_to_array function found in [acoustic_util.py](acoustic_util.py). In general, this function takes the 10-minute .wav file, applies a 
short-time Fourier transform based on user given frequency bands to create a PSD, sums over the frequencies to produce broadband, 
averages both the PSD and broadband Dataframes over the user supplied averaging interval, and then converts both from amplitude 
to decibels. The PSD and broadband Dataframes are then returned to the generate_psds function.

The previously described process occurs for every 10-minute span of the user supplied date interval. For example, if we 
run the pipeline for an hour of data from 11:00-12:00, we first download the .ts files for 11:00-11:10, convert them into 
.wav format, calculate the PSD and broadband Dataframes, and store them in two separate lists with the generate_psds function. 
We repeat this process 6 times in total, leaving us with a list of 6 10-minute PSD Dataframes and the same for broadband.

### Generating the Parquet File

Still within the generate_psds function, we concatenate the PSD Dataframes and the broadband Dataframes, leaving us with 
two Dataframes in total, one for PSD and one for broadband. Note, we then subtract the hydrophone's reference level from 
the broadband Dataframe. This reference level is an attribute of the hydrophone and is set based on the ancient ambient 
broadband level for that hydrophone. This reference level can be updated for a given hydrophone, year, and month using the 
generate_ref function found in [pipeline.py](pipeline.py).

Finally, generate_psds returns the complete PSD and broadband Dataframes to the generate_parquet_file function, which saves
the two Dataframes and returns their file paths. We can then use these file paths to read the Dataframes for exploration.

## Definitions

### PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

### FFT

A fast Fourier transform (FFT) is an algorithm that computes the discrete Fourier transform (DFT) of a sequence, or its inverse (IDFT). Fourier analysis converts a signal from its original domain (often time or space) to a representation in the frequency domain and vice versa.
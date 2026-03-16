# Pipeline

This pipeline overview is designed to give users an understanding of how the data goes from individual hydrophones to 
power spectral densities in the form of parquet files, as well as the pipeline for pulling ship tracking data from Marine Monitor (M2).

## Hydrophone data, PSD and BroadBand

### Hydrophone Data Storage

Orcasound has four hydrophones located throughout the Puget Sound that continuously collect underwater acoustic data. 
Every few minutes, these hydrophones upload audio files, in the form of 10-second .ts clips, to Orcasound Amazon S3 buckets. 
This process has been ongoing for the past 5+ years, resulting in approximately 6TB of raw audio data, comprised of 
roughly 50 million 10-second audio clips. 

The goal of this pipeline is to accurately and efficiently convert these .ts files, 
based on the user's chosen frequency bands, averaging time, and date selection, into power spectral densities in the form 
of parquet files. This allows anyone to access this vast amount of data for exploration and understanding.

### Creating a Pipeline Object

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

### Creating a PSD

#### Initialization

Using the pipeline object we created, we call generate_parquet_file with a given start and end time. This function 
returns paths for the stored PSD and broadband parquet files. Users can read these parquet files as Dataframes for further 
exploration.

```python
#Example: Using pipeline object specified above, we generate the parquet files for 11am - 12pm UTC
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11), 
                                                          dt.datetime(2023, 3, 22, 12), 
                                                          upload_to_s3=False)
```

#### Downloading and Converting the .ts Files

The generate_parquet_file function calls the generate_psds function, both located in [pipeline.py](pipeline.py). This function begins by creating a DateRangeHLSStream object,
providing a link to the Amazon S3 buckets with our desired hydrophone and date interval. Assuming we are operating in safe 
mode, the code uses the stream object to download the .ts files in 10-minute spans. 10-minute spans are determined by the 
polling_interval parameter; we suggest not changing this as larger spans have caused errors.

These 10-minute downloads of .ts files are then converted into 10-minute .wav files, which are saved in a temporary directory,
unless otherwise specified. All of this work is done by the get_next_clip function, a method of DateRangeHLSStream objects 
implemented in the orca_hls_utils package.

#### Conversion from .wav to PSD and Broadband

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

#### Generating the Parquet File

Still within the generate_psds function, we concatenate the PSD Dataframes and the broadband Dataframes, leaving us with 
two Dataframes in total, one for PSD and one for broadband. Note, we then subtract the hydrophone's reference level from 
the broadband Dataframe. This reference level is retrieved from the reference tables stored in S3. The reference level is updated in the table each day and is based on an esitmate of the ancient ambient sound level approximated by taking the 5th percentile of the previous 7 days.

Finally, generate_psds returns the complete PSD and broadband Dataframes to the generate_parquet_file function, which saves
the two Dataframes and returns their file paths. We can then use these file paths to read the Dataframes for exploration.

### Definitions

#### PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

#### FFT

A fast Fourier transform (FFT) is an algorithm that computes the discrete Fourier transform (DFT) of a sequence, or its inverse (IDFT). Fourier analysis converts a signal from its original domain (often time or space) to a representation in the frequency domain and vice versa.

### PSD and Broadband Calculations

#### PSD
A waveform $x(t)$ with a known sample rate $f_s$ is retrieved from the .wav file. A sample rate of 48,000Hz means each sample is 1/48,000 seconds apart.
```python
y, sr = librosa.load(filepath, sr=None)
````
Define a window length and an overlap for the windows to compute the Fourier transforms over. 
```python
n_fft = int(sr / delta_f)
hop_length = int(n_fft / 2)
```
When computing the discrete Fourier transform a windowing function is typically applied to taper the transition between windows. Librosa's short time Fourier transform function defaults to a Hann window.
```python
D_highres = librosa.stft(y, hop_length=hop_length, n_fft=n_fft)
```
**Note** the output of librosa's STFT function is not normalized to the window power or the sample rate and is not squared. To normalize the window power is retrieved, and the PSD in the correct units is calculated as follows:
```python
window = librosa.filters.get_window("hann", n_fft, fftbins=True)
window_power = np.sum(window**2)
power = np.abs(D_highres) ** 2
psd = power / (window_power * sr)
```
The above method for calculating PSD was validated by comparing scipy signal's PSD output and following scipy's [documentation](https://docs.scipy.org/doc/scipy/tutorial/signal.html#short-time-fourier-transform).

PSD is converted to decibel relative to a reference by applying the following formula.
$$
PSD_{dB}(f,t)=10\log\frac{PSD(f,t)}{P^2_{ref}}
$$

#### Broadband Sound Level

The broadband sound level is calculated by integrating the PSD over all frequencies.
$$
 p^2​= \sum_{k=f_1}^{f_2} PSD(k) \times \Delta f
$$
```python
p_rms = np.sum(psd, axis=0) * delta_f
```
Note: when integrating, the PSD should not be in decibel units.

Broadband sound level is converted to decibels with the following formula.
$$
Broadband_{dB} = 10\log\frac{p^2}{p^2_{ref}}
$$

### Schema of PSD and Broadband and Reference Parquet Dataframes

#### Broadband Dataframe

| Column    | Data Type | Description                                                   | Units             |
| --------- | --------- | ------------------------------------------------------------- | ----------------- |
| bb_o      | Float64   | Broadband normalized to reference                             | $10log(a.u.^2)$   |
| comm_bb_o | Float64   | Orca communication band broadband not normalized to reference | $10log(a.u.^2)$   |
| ship_bb_o | Float64   | Ship band broadband not normalized to reference               | $10log(a.u.^2)$   |
| bb        | Float64   | Normalized broadband                                          | dB re bb_ref      |
| comm_bb   | Float64   | Normalized communication band                                 | dB re comm_bb_ref |
| ship_bb   | Float64   | Normalized ship band                                          | dB re ship_bb_ref |
| ind       | DateTime  | Time Stamp in PST                                             |                   |

The Orca communication band is defined as 1,000-6,0000 Hz. It defines the band most often used by Orcas to communicate.

The Ship band is defined as 1-500 Hz, in this band ship noise the most present.

The original values, (bb_o, comm_bb_o, ship_bb_o), not normalized to reference are on the log scale:
$$
10\log(p^2)
$$
Where $p^2$ is the broadband in terms of signal pressure.

The normalized broadbands, (bb, comm_bb, ship_bb), are calculated as follows:
$$
10\log(p^2) - 10\log(p^2_{ref}) \; or \; 10\log\frac{p^2}{p^2_{ref}}
$$

#### Reference Dataframe


| Column      | Data Type | Description                                 | Units           |
| ----------- | --------- | ------------------------------------------- | --------------- |
| bb_ref      | Float64   | Broadband reference                         | $10log(a.u.^2)$ |
| comm_bb_ref | Float64   | Orca communication band broadband reference | $10log(a.u.^2)$ |
| ship_bb_ref | Float64   | Ship band broadband refernce                | $10log(a.u.^2)$ |
| Date        | DateTime  | Date in PST                                 |                 |

Reference values calculated daily as the 5th percentile of bb_o, comm_bb_o, or ship_bb_o for the last 7 days. The references values are on the same log scale to facilitate calculation of broadbands in dB re ref.

#### PSD Dataframe

| Column              | Data Type | Description                                      | Units           |
| ------------------- | --------- | ------------------------------------------------ | --------------- |
| ind                 | DateTime  | Time Stamp in PST                                |                 |
| 67, 71, ... , 22400 | Float64   | Power spectral density for each 1/12 octave band | $10log(a.u.^2)$ |

PSD values in 10*log scale to facilitate future normalization or implimentation-dependent normalization. An overview of normalization strategies is available in this [jupyter notebook](../analysis/PSD_normalization_example.ipynb)


## Ship Data Pipeline
In this repo, we use ship tracking data from [Marine Monitor (M2)](https://m2marinemonitor.com/). M2 provides two types of data: AIS tracking data (received by an AIS receiver, if installed at the site) and radar tracking data (processed by a marine radar sensor). Currently, M2 only tracks vessels in the area of the `orcasound_lab` hydrophone.

According to information from M2, the radar range is a conservative estimate of a reliable range of up to 5 nautical miles from the system. Sea and weather conditions may impact radar target detection and tracking. The AIS detection range of up to 25 nautical miles is an estimate based on data received by M2. 

In our pipeline, we download a .zip file containing the latest weekly data from M2, unzip it, and transform it into a polars.LazyFrame for metric calculations.

### Pipeline Usage 
```{python}
# A user will need credentials to access M2 data.
from dotenv import load_dotenv
load_dotenv()

ship_pipeline = ShipAnalysisPipeline()
lf_ais, lf_radar = ship_pipeline.get_raw_data_from_m2() # It will load the latest 7 days of tracking data.
```
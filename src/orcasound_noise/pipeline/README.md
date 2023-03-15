# Pipeline

The pipeline component's primary objective is to convert historical .ts files into compact [Power Spectral Density (PSD)](#psd) grids and save them as [parquet files](https://parquet.apache.org/).

This audio processing is done by initializing a NoiseAnalysisPipeline object for a specific hydrophone, and then using the generate_parquet_file() method to specify a time range and optional time and frequency resolution (or granularity). The generate_parquet_file method leverages the generate_psds() method to open a stream to the location of the raw .ts audio files, load the files, process them via FFT into a PSD, then save that PSD as a parquet file. You can save this file locally, and optionally pass a parameter to save the parquet to an S3 bucket location defined in the Hydrophone class. 

Example:
```python
from src.orcasound_noise.pipeline import pipeline

pipe = pipeline.NoiseAnalysisPipeline(Hydrophone.ORCASOUND_LAB, delta_f=10, delta_t=1, bands=3, 
                                      wav_folder="wav_folder", pqt_folder="pqt_folder")

pqt_filepath, bb_filepath =  pipe.generate_parquet_file(start=start_time, end=end_time, upload_to_s3=True)
```

The pipeline has additional utilities and tools that can optionally be used to reduce noise, help normalize audio levels, and generally fine tune the desired audio processing.

# Definitions

## PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

## FFT

A fast Fourier transform (FFT) is an algorithm that computes the discrete Fourier transform (DFT) of a sequence, or its inverse (IDFT). Fourier analysis converts a signal from its original domain (often time or space) to a representation in the frequency domain and vice versa.
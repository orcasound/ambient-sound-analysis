# Pipeline

The pipeline component's primary objective is to convert historical .ts files into compact [Power Spectral Density (PSD)](#psd) grids and save them as [parquet files](https://parquet.apache.org/).

The user will interface with this functionality through the NoiseAnalysisPipeline class.




# Definitions

## PSD

A Power Spectral Density describes the power present in the audio signal as a function of frequency, per unit frequency and for a given averaging time. In this codebase, PSD values are generally stored as Pandas Dataframes, where the index represents the timestamps, the columns represent frequency bands, and each cell value represents the relative power in that frequency band and time interval, in decibels.

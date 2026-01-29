import os
import datetime

import librosa
import librosa.display
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from skimage.restoration import denoise_wavelet
import numpy as np
import pandas as pd
import plotly.graph_objects as go

def apply_per_channel_energy_norm(spectrogram):
    """Apply PCEN.

    This function normalizes a time-frequency representation S by
    performing automatic gain control, followed by nonlinear compression:

    P[f, t] = (S / (eps + M[f, t])**gain + bias)**power - bias**power
    PCEN is a computationally efficient frontend for robust detection
    and classification of acoustic events in heterogeneous environments.

    This can be used to perform automatic gain control on signals that
    cross or span multiple frequency bans, which may be desirable
    for spectrograms with high frequency resolution.

    Args:
        spectrograms: The data from the audio file used to create spectrograms.
        sampling_rate: The sampling rate of the audio files.

    Returns:
        PCEN applied spectrogram data.
    """
    pcen_spectrogram = librosa.core.pcen(spectrogram)
    return pcen_spectrogram


def wavelet_denoising(spectrogram):
    """In this step we would apply Wavelet-denoising.

    Wavelet denoising is an effective method for SNR improvement
    in environments with wide range of noise types competing for the
    same subspace.

    Wavelet denoising relies on the wavelet representation of
    the image. Gaussian noise tends to be represented by small values in the
    wavelet domain and can be removed by setting coefficients below
    a given threshold to zero (hard thresholding) or
    shrinking all coefficients toward zero by a given
    amount (soft thresholding).

    Args:
        data:Spectrogram data in the form of numpy array.

    Returns:
        Denoised spectrogram data in the form of numpy array.
    """
    im_bayes = denoise_wavelet(spectrogram,
                               multichannel=False,
                               convert2ycbcr=False,
                               method="BayesShrink",
                               mode="soft")
    return im_bayes


def spec_plot_and_save(denoised_data, f_name, output_dir):
    """Generate the spectrogram and save them.

    Args:
        denoised_data: The spectrogram data that is generated either by
        PCEN or Wavelet-denoising.
        f_name: The name of the output file.
        output_dir: The path to the output directory.

    Returns:
        none.
    """
    fig, ax = plt.subplots()
    i = 0
    ax.imshow(denoised_data)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    fig.set_size_inches(10, 10)
    # os.chdir(plotPath)
    fig.savefig(os.path.join(output_dir, f"{f_name[:-4]}.png"),
                dpi=80,
                bbox_inches="tight",
                quality=95,
                pad_inches=0.0)
    fig.canvas.draw()
    fig.canvas.flush_events()
    i += 1
    plt.close(fig)


def select_spec_case(plot_path, folder_path, pcen=False, wavelet=False):
    """Selects the preprocessing steps to be applied to the spectrogram.

    Depending upon the choices entered by the user this function would
    select the necessary preprocessing stages and call their respective
    functions.

    Args:
        plot_path: The output path where we want to plot the spectrograms.
        folder: The input_path which contains the audio that would
            be used to generate spectrograms.
        pcen: Could be set to True if we want to apply PCEN to spectrograms.
        wavelet:Could be set to true if we want to apply Wavelet denoising
            to the spectrograms.

    Returns:
        None.
    """
    onlyfiles = [
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
    ]
    for id, file in enumerate(onlyfiles):
        fpath = os.path.join(folder_path, file)
        data, sr = librosa.core.load(fpath, res_type="kaiser_best")
        f_name = os.path.basename(file)

        spectrogram_data = librosa.feature.melspectrogram(data, sr=sr, power=1)
        if pcen and not wavelet:
            pcen_spec = apply_per_channel_energy_norm(spectrogram_data)
        elif pcen and wavelet:
            pcen_spec = apply_per_channel_energy_norm(spectrogram_data)
            spectrogram_data = wavelet_denoising(pcen_spec)
        spec_plot_and_save(spectrogram_data, f_name, plot_path)


def wav_to_array(filepath,
                 t0=datetime.datetime.now(),
                 delta_t=1,
                 delta_f=10,
                 transforms=[wavelet_denoising],
                 ref=1,
                 bands=None
                 ):
    """
    This function converts a wavfile to a dataframe of power spectral density, with the index as the timestamp from the start of the wav file and the columns as the frequency bin.  This function also calculates the broadband average noise level of the input wavefile before the dB conversion per time step after the FFT calculation.

    df1: Spectrogram data.  Index = time, columns = frequency.
    df2: Broadband RMS level.  Index = time, column = average noise.

    Args:
        filepath: file path to .wav
        t0: datetime.  starting time of the recording.
        delta_t: Int, number of seconds per sample
        delta_f: Int, number of hz per frequency band
        n_fft: int. number of points in the acquired time-domain signal.  delta F = sample rate/n_fft
        transforms: List of functions to apply to DB-spectogram before reducing to bands.
          Functions must take in single spectogram as argument and return same. Default is to apply PCEN and wavelet denoising.
        ref: float.  reference level for the amplitude to dB conversion.  must be an absolute value, not dB.
        bands: int. default=None. If not None this value selects how many octave subdivisions the frequency spectrum should
          be divided into, where each frequency step is 1/Nth of an octave with N=bands. Based on the ISO R series.
          Accepts values 1, 3, 6, 12, or 24.

    Returns:
        Tuple of (df1, df2)
    """
    # Load the .wav file
    y, sr = librosa.load(filepath, sr=None)

    # Set FFT parameters
    n_fft = int(sr / delta_f)
    hop_length = int(n_fft / 2)

    # Apply the STFT
    D_highres = librosa.stft(y, hop_length=hop_length, n_fft=n_fft)
    # Convert from amplitude to decibels
    spec = librosa.amplitude_to_db(np.abs(D_highres), ref=ref)
    # Save the frequencies and time for Dataframe construction
    freqs = librosa.core.fft_frequencies(sr=sr, n_fft=n_fft)
    secs = librosa.core.frames_to_time(np.arange(spec.shape[1]), sr=sr, n_fft=n_fft, hop_length=hop_length)
    times = [t0 + datetime.timedelta(seconds=x) for x in secs]

    # Apply transforms
    for transform_func in transforms:
        spec = transform_func(spec)

    rms = []
    delta_f = sr / n_fft
    DT = D_highres.transpose()
    # Sum over the frequencies for each time to calculate broadband
    for i in range(len(DT)):
        rms.append(delta_f * np.sum(np.abs(DT[i, :])))

    # Create the PSD Dataframe with minimal copies: round in-place on a float64 array
    spec_arr = np.asarray(spec.transpose(), dtype=np.float64)
    np.around(spec_arr, 2, out=spec_arr)
    df = pd.DataFrame(spec_arr, columns=freqs, index=times)
    df.columns = df.columns.map(str)
    
    # Create the broadband dataframe with the same strategy
    rms_arr = np.asarray(rms, dtype=np.float64)
    np.around(rms_arr, 2, out=rms_arr)
    rms_df = pd.DataFrame(rms_arr, index=times)
    rms_df.columns = rms_df.columns.map(str)
    # Average over desired time and convert to decibels for the broadband
    rms_df = array_resampler_bands(df=rms_df, delta_t=delta_t)
    
    # Calculate bands if specified
    if bands is not None:
        # Convert to bands
        oct_unscaled, fm = spec_to_bands(np.abs(DT), bands, delta_f, freqs=freqs, ref=ref)
        oct_arr = np.asarray(oct_unscaled, dtype=np.float64)
        np.around(oct_arr, 2, out=oct_arr)
        oct_df = pd.DataFrame(oct_arr, columns=fm, index=times)
        # Average over desired time and convert to decibels for bands
        oct_df = array_resampler_bands(df=oct_df, delta_t=delta_t)
        
        return oct_df, rms_df

    else:
        # Convert PSD back to amplitude, average over time period, and convert back to decibels
        df = array_resampler(df=df, delta_t=delta_t)
        
        return df, rms_df


def array_resampler(df, delta_t=1):
    """
    This function takes in the data frame of spectrogram data, converts it to amplitude, averages over time frame, and converts it back to db.

    Args:
        df: data frame of spectrogram data
        delta_t: Int, number of seconds per sample

    Returns:
        resampled_df: data frame of spectrogram data.
    """
     # Save columns and index for later Dataframe construction
    cols = df.columns
    ind = df.index
    resampled_df = df.to_numpy()
    # Convert back to amplitude for averaging
    resampled_df = librosa.db_to_amplitude(resampled_df)
    resampled_df = pd.DataFrame(resampled_df, columns=cols)
    resampled_df['ind'] = ind
    resampled_df = resampled_df.set_index(pd.DatetimeIndex(resampled_df['ind']))
    resampled_df = resampled_df.drop(columns=['ind']) ## 2026-01-28 fix as pandas doesn't automatically drop the old index column in newer versions
    sample_length = str(delta_t) + 's'

    # Average over given time span
    resampled_df = resampled_df.resample(sample_length).mean()
    resampledIndex = resampled_df.index

    resampled_df = resampled_df.to_numpy()
    # Convert back to decibels
    resampled_df = librosa.amplitude_to_db(resampled_df, ref=1)
    # Reconstruct Dataframe
    resampled_df = pd.DataFrame(resampled_df, index=resampledIndex)

    return resampled_df


def array_resampler_bands(df, delta_t=1):
    """
    This function takes in the data frame for bands or broadband, averages over time frame, and converts it to db.

    Args:
        df: data frame of spectrogram data
        delta_t: Int, number of seconds per sample

    Returns:
        resampled_df: data frame of broadband data.
    """
    resampled_df = df
    sample_length = str(delta_t) + 's'

    # Average over given time span
    resampled_df = resampled_df.resample(sample_length).mean()
    resampledIndex = resampled_df.index

    resampled_df = resampled_df.to_numpy()
    # Convert to decibels
    resampled_df = librosa.amplitude_to_db(resampled_df, ref=1, top_db=200.0)
    # Reconstruct Dataframe
    resampled_df = pd.DataFrame(resampled_df, index=resampledIndex)

    return resampled_df


def ancient_ambient(df):
    """
    Ancient ambient noise level is defined as the 5th percentile noise level of a month's acoustic data.

    Args: Array-like object containing a month of acoustic data.

    Returns: 5th percentile noise level
    """

    return np.percentile(df, 5)


def spec_plot(df, sr=48000, hop_length=256):
    """
    This function converts a table of power spectral data, having the columns represent frequency bins and the rows represent time segments, to a spectrogram.

    Args:
        df: Dataframe of power spectral data.
        sr: int. Sample rate of the audio signal.
        hop_length: int. Number of audio samples between adjacent STFT columns.  See librosa docs for more info.

    Returns: Spectral plot
    """

    D = df.to_numpy()
    D = D.transpose()

    fig = plt.figure()
    librosa.display.specshow(D, y_axis='log', sr=sr, hop_length=hop_length, x_axis='time', x_coords=df.index,
                             cmap='gray')
    fig.gca().set_xlabel("Time")
    fig.gca().set_ylabel("Hz")
    fig.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig.gca().xaxis.set_major_locator(mdates.SecondLocator())
    plt.gcf().autofmt_xdate()


def filt_gain(f, fm, b):
    """
    f: array of frequencies to apply gain to
    fm: center frequency
    b: bandwidth designator. 1 for full octave, 3 for 1/3 octave, etc.
    """

    length = len(f)
    exp = np.full(length, 6, dtype=float)
    fm = np.full(length, fm, dtype=float)
    b_scaled = np.full(length, 1.507 * b, dtype=float)
    ones = np.ones(length, dtype=float)

    d = np.subtract(np.divide(f, fm), np.divide(fm, f))
    f = np.multiply(d, b_scaled)
    h = np.power(f, exp)

    return np.sqrt(np.divide(ones, np.add(ones, h)))


def band_power(psd, g, delta_f):
    """
    https://www.ap.com/technical-library/deriving-fractional-octave-spectra-from-the-fft-with-apx/

    psd: original power spectral density
    g: gains to apply
    """

    exp = np.full(len(psd), 2.0)
    x = np.multiply(psd, np.power(g, exp))
    return np.sqrt(delta_f * np.sum(x))


def octave_band(N, freqs):
    """


    ISO Series
    R5: 1 octave
    R10: 1/3 octave (1/10 decade)
    R20: 1/6 octave (1/20 decade)
    R40: 1/12 octave (1/40 decade)
    R80: 1/24 octave (1/80 decade)

    Arguments:
    N: number of octave divisions
    freqs: frequencies in the original PSD

    Returns:
    ISO R series
    """

    # ISO R5 frequencies
    Rfive = np.array([63, 125, 250, 500, 1000, 2000,
                      4000, 8000, 16000])
    g_Rfive = [filt_gain(freqs, x, 1) for x in Rfive]

    # ISO R10 frequencies from 63 Hz to 22.4 kHz
    Rten = np.array([63, 80, 100, 125, 160, 200,
                     250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
                     4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000])
    # Add additional bands up to your Nyquist frequency as necessary
    # , 25000, 31500, 40000, 50000,
    # 63000, 80000, 100000])
    g_Rten = [filt_gain(freqs, x, 3) for x in Rten]

    # ISO R20 frequencies from 63 Hz to 22.4 kHz
    Rtwenty = np.array([63, 71, 80, 90, 100, 112, 125, 140, 160, 180, 200, 224, 250,
                        280, 315, 355, 400, 450, 500, 560, 630, 710, 800, 900, 1000,
                        1120, 1250, 1400, 1600, 1800, 2000, 2240, 2500, 2800, 3150, 3550, 4000,
                        4500, 5000, 5600, 6300, 7100, 8000, 9000, 10000, 11200, 12500, 14000, 16000,
                        18000, 20000, 22400])

    g_Rtwenty = [filt_gain(freqs, x, 6) for x in Rtwenty]

    # ISO R40 frequencies from 67 Hz to 22.4 kHz
    Rforty = np.array([67, 71, 75, 80, 85, 90, 95, 100, 106, 112, 118, 125,
                       132, 140, 150, 160, 170, 180, 190, 200, 212, 224, 236, 250,
                       265, 280, 300, 315, 335, 355, 375, 400, 425, 450, 475, 500,
                       530, 560, 600, 630, 670, 710, 750, 800, 850, 900, 950, 1000,
                       1060, 1120, 1180, 1250, 1320, 1400, 1500, 1600, 1700, 1800, 1900, 2000,
                       2120, 2240, 2360, 2500, 2650, 2800, 3000, 3150, 3350, 3550, 3750, 4000,
                       4250, 4500, 4750, 5000, 5300, 5600, 6000, 6300, 6700, 7100, 7500, 8000,
                       8500, 9000, 9500, 10000, 10600, 11200, 11800, 12500, 13200, 14000, 15000, 16000,
                       17000, 18000, 19000, 20000, 21200, 22400])

    g_Rforty = [filt_gain(freqs, x, 12) for x in Rforty]

    # ISO R80 frequencies from 67 Hz to 22.4 kHz
    Reighty = np.array([67, 69, 71, 73, 75, 77.5, 80, 82.5, 85, 87.5,
                        90, 92.5, 95, 97.5, 100, 103, 106, 109, 112, 115, 118, 122,
                        125, 128, 132, 136, 140, 145, 150, 155, 160, 165, 170, 175,
                        180, 185, 190, 195, 200, 206, 212, 218, 224, 230, 236, 243,
                        250, 258, 265, 272, 280, 290, 300, 307, 315, 325, 335,
                        345, 355, 365, 375, 387, 400, 412, 425, 437, 450, 462,
                        475, 487, 500, 515, 530, 545, 560, 580, 600, 615, 630,
                        650, 670, 690, 710, 730, 750, 775, 800, 825, 850, 875,
                        900, 925, 950, 975, 1000, 1030, 1060, 1090, 1120, 1150, 1180,
                        1220, 1250, 1280, 1320, 1360, 1400, 1450, 1500, 1550, 1600, 1650,
                        1700, 1750, 1800, 1850, 1900, 1950, 2000, 2060, 2120, 2180, 2240,
                        2300, 2360, 2430, 2500, 2580, 2650, 2720, 2800, 2900, 3000, 3070,
                        3150, 3250, 3350, 3450, 3550, 3650, 3750, 3870, 4000, 4120, 4250,
                        4370, 4500, 4620, 4750, 4870, 5000, 5150, 5300, 5450, 5600, 5800,
                        6000, 6150, 6300, 6500, 6700, 6900, 7100, 7300, 7500, 7750, 8000,
                        8250, 8500, 8750, 9000, 9250, 9500, 9750, 10000, 10300, 10600, 10900,
                        11200, 11500, 11800, 12200, 12500, 12800, 13200, 13600, 14000, 14500, 15000,
                        15500, 16000, 16500, 17000, 17500, 18000, 18500, 19000, 19500, 20000, 20600,
                        21200, 21800, 22400])
    g_Reighty = [filt_gain(freqs, x, 24) for x in Reighty]

    bands = {1: Rfive,
             3: Rten,
             6: Rtwenty,
             12: Rforty,
             24: Reighty}
    filters = {1: g_Rfive,
               3: g_Rten,
               6: g_Rtwenty,
               12: g_Rforty,
               24: g_Reighty}

    if N not in bands:
        raise ValueError
    else:
        return bands[N], filters[N]


def spec_to_bands(psd, N, delta_f, freqs, ref):
    """

    """
    bands, gains = octave_band(N, freqs)
    octaves = np.empty((0, len(bands)), dtype=float)
    for row in psd:
        octaves = np.append(octaves, np.array([[band_power(row, g, delta_f) for g in gains]]), axis=0)

    octaves_scaled = librosa.amplitude_to_db(octaves, ref=ref)

    return octaves_scaled, bands


def plot_noise(testdf, name, output_path=None, save=False):
    fig, ax = plt.subplots()
    spec = ax.pcolormesh(testdf.index, testdf.columns, testdf.values.transpose())
    ax.set_yscale('log')
    ax.set_ylim([50, 20000])
    fig.autofmt_xdate(rotation=45)
    fig.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    # fig.gca().xaxis.set_major_locator(mdates.SecondLocater())
    fig.colorbar(spec, ax=ax, label="dB relative to ancient ambient")
    fig.set_size_inches(10, 10)
    plt.title(name)
    # os.chdir(plotPath)
    if save:
        fig.savefig(output_path,
                    dpi=80,
                    bbox_inches="tight",
                    pad_inches=0.0)

        fig.canvas.draw()
        fig.canvas.flush_events()
        plt.close(fig)


def dBFS_to_aa(df, aa):
    """
    Converts PSD in dBFS to dB relative to ancient ambient. Both values must be in dBFS.

    * df: dataframe to scale
    * aa: ancient ambient.

    """

    return df + abs(aa)


def aa_to_dBFS(df, aa):
    """
    Converts PSD scaled relative to ancient ambient to dBFS. Both values must be in dBFS.

    * df: dataframe to scale
    * aa: ancient ambient.

    """

    return df - abs(aa)


def abs_to_dB(df, ref=1, columns=None):
    """
    Converts PSD in amplitude to decibels.

    * df: dataframe in amplitude
    * ref: reference level to adjust for
    * columns: columns of the dataframe

    """

    if columns == None:
        columns = list(df.columns)
    vals = librosa.amplitude_to_db(df, ref=ref)
    return pd.DataFrame(vals, index=list(df.index), columns=columns)


def plot_spec(psd_df):
    """
    This function converts a table of power spectral data, having the columns represent frequency bins and the rows
    represent time segments, to a spectrogram.

    Args:
        psd_df: Dataframe of power spectral data.

    Returns: Spectral plot
    """

    fig = go.Figure(
        data=go.Heatmap(x=psd_df.index, y=psd_df.columns, z=psd_df.values.transpose(), colorscale='Viridis',
                        colorbar={"title": 'Magnitude'}))
    fig.update_layout(
        title="Hydrophone Power Spectral Density",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        legend_title="Magnitude"
    )
    fig.update_yaxes(type="log")
    return(fig)

def plot_bb(bb_df):
    """
    This function plots the broadband levels in relative decibels.

    Args:
        bb_df: Dataframe of broadband levels.

    Returns: Time series of broadband levels.
    """
    plt.figure()
    plt.xticks(rotation = 45)
    plt.plot(bb_df)
    plt.title('Relative Broadband Levels')
    plt.xlabel('Time')
    plt.ylabel('Relative Decibels')
    plt.xticks(rotation = 45)
    return(plt.gcf())

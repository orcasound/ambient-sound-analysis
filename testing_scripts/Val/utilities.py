import soundfile as sf
import numpy as np
from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream
import logging
import time
from scipy.signal import resample
import matplotlib.pyplot as plt
def convertToNumpy(f, typedict, data, channelchoice):
    if f.channels == 2:
        if channelchoice == -1:  # if no channel choice was made, choose the channel with higher average signal
            try:
                ch0 = np.average(np.abs(np.frombuffer(data, dtype=typedict[f.subtype])[0::2]))
                ch1 = np.average(np.abs(np.frombuffer(data, dtype=typedict[f.subtype])[1::2]))
                if ch0 > ch1:
                    channelchoice = 0
                else:
                    channelchoice = 1
            except:
                channelchoice = 0
        npdata = np.frombuffer(data, dtype=typedict[f.subtype])[channelchoice::2]
    else:
        npdata = np.frombuffer(data, dtype=typedict[f.subtype])
    return npdata

def getSamples(startsecs, Nsamples, WAV):

    channelchoice = -1  # pick channel with higher amplitude
    typedict = {}
    typedict['FLOAT'] = 'float32'
    typedict['PCM_16'] = 'int16'

    NsamplesNeeded = Nsamples
    npsamples = []
    while NsamplesNeeded > 0:

        with sf.SoundFile(WAV) as f:
            #            print("-------------reading wav file", WAVs[wavStartIdx], "wavStartIdx", wavStartIdx)
            availableSamples = f.seek(0, sf.SEEK_END) # - int(startsecs * f.samplerate)

            if len(npsamples) == 0:
                if availableSamples > 0:
                    f.seek(int(startsecs * f.samplerate))  # for first wav file, start at desired number of secs into file
                else:
                    f.seek(0)  # start at beginning of wav file, continuing into a new file
            while availableSamples > 0 and NsamplesNeeded > 0:
                try:
                    if availableSamples >= NsamplesNeeded:
                        data = f.buffer_read(NsamplesNeeded, dtype=typedict[f.subtype])
                        npdata = convertToNumpy(f, typedict, data, channelchoice) # choose channel and return numpy array
                        NsamplesNeeded = 0
                    else:
                        data = f.buffer_read(availableSamples, dtype=typedict[f.subtype])
                        npdata = convertToNumpy(f, typedict, data, channelchoice)  # choose channel and return numpy array
                        NsamplesNeeded -= availableSamples
                        startsecs = 0
                        availableSamples = 0
                except Exception as e:
                    print("Exception in get samples is", e)
                if len(npsamples) == 0:
                    npsamples = npdata
                else:
                    npsamples = np.append(npsamples, npdata)
            totalSecsInFile = f.seek(0, sf.SEEK_END) / f.samplerate
            f.close()
    #    print("n samples", len(npsamples))
    return npsamples, totalSecsInFile

def calculatePSD(wavFile, samplerate, startSecs, Nsamples, fhigh, Nfft, fftWindow, calConstant, plotInterpolation=False):

    samples, secsIntoWav = getSamples(startSecs, Nsamples, wavFile)
    data = []
    if fftWindow == "Hamming":  data = samples * np.hamming(len(samples))
    if fftWindow == "Blackman": data = samples * np.blackman(len(samples))

    psd = np.abs(np.fft.rfft(data, Nfft))
    df = fhigh / len(psd)

    f_values = np.fft.fftfreq(Nfft, d=1. / samplerate)
    f_values = f_values[0:Nfft//2+1]  # drop the un-needed negative frequencies
    f_values[-1] = f_values[-2]

    factor = samplerate/(Nfft)
    resampled_psd = resample(psd, int(len(psd) * factor))

    if plotInterpolation:    # set True to look at the interpolation scheme
        freqs = np.arange(0, len(resampled_psd))
        plt.scatter(freqs, resampled_psd, color = 'red', s=1)
        plt.scatter(f_values, psd, s=100)
        plt.xlim(6000, 6200)
        plt.title("Large dots are psd values from numpy fft. Red from resampling to 1 Hz")
        plt.show()
        freqs = np.arange(0, len(resampled_psd))
        plt.scatter(freqs, resampled_psd, color = 'red', s=1)
        plt.scatter(f_values, psd, s=100)
        plt.xlim(400, 700)
        plt.title("Large dots are psd values from numpy fft. Red from resampling to 1 Hz")
        plt.show()
    return freqs, 20*np.log10(resampled_psd) + calConstant

def get_wav_files(wavDir, hydrophone, dt_start, dt_end, max_files=None, wavFileLength_seconds=600, overwrite_output=True):
    wav_folder = wavDir
    stream = DateRangeHLSStream(
        'https://s3-us-west-2.amazonaws.com/' + hydrophone.value.bucket + '/' + hydrophone.value.ref_folder,
        wavFileLength_seconds,
        time.mktime(dt_start.timetuple()),
        time.mktime(dt_end.timetuple()),
        wav_folder,
        overwrite_output
    )
    if len(stream.valid_folders) == 0:
        print("EXITING...")
        return
    wavFileList = []
    while max_files is None and not stream.is_stream_over():
        try:
            wav_file_path, clip_start_time, _ = stream.get_next_clip()
            wavFileList.append(wav_file_path)
            if clip_start_time is None:
                continue
            start_time = [int(x) for x in clip_start_time.split('_')]
        except FileNotFoundError as fnf_error:
            logging.debug("%s clip failed to download: Error %s", clip_start_time, fnf_error)
            pass
    return wavFileList

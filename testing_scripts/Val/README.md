#  This Python script can download wav files from a S3 bucket at orcasound.net
#  ts segments in the selected datetime interval are downloaded and converted to wav files
#  Then the power spectral density  per hertz is calculated for a selected single time interval

##  Run pip3 install -m requirements.txt     in your code's working directory and virtual environment

## Create a local directory for the wav file(s)

##  Set parameter values in ts_wav_psd.py:

* create local directory for wav file
* wavDir = "/home/val/Music/WAVfiles4Comparison/"
* dt_start = dt.datetime(2023, 12, 25, 19, 0)
* dt_stop =  dt.datetime(2023, 12, 26, 16, 0)
* hydro =  Hydrophone['ORCASOUND_LAB']
* wavFileSecs = 24 * 60 * 60
* deltaT = 60  # one second psd's
* calConstant = 0 #-35
* Nfft = 2048
* Choose "Hamming" or "Blackman"
* fftWindow = "Blackman"
* fftWindow = "Hamming"
* setPlotInterpolaiton = True    # to plot interpolation to 1 hz

## Then run the script ts_wav_psd.py

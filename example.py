import datetime as dt

import matplotlib.pyplot as plt

# Local imports
from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream
from src import pipeline




# Create spectrograms and visualize one
grams = pipeline.ts_to_spectrogram(
    dt.date(2022, 11, 5),
    dt.date(2022, 11, 6),
    'wav'
)


plt.pcolormesh(grams[0])
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time ')
plt.savefig('fig.png')



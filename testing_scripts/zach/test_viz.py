import pandas as pd
import matplotlib.pyplot as plt

data_msds = pd.read_csv('/Users/zach/Desktop/row.txt', delimiter=' ', header=None)
data_ben = pd.read_csv('/Users/zach/Desktop/rpi-port-townsend_2023_03_22_11_05_25_psd.txt', delimiter=' ', header=None)
data_val = pd.read_csv('/Users/zach/Downloads/psdCSVfile.csv', header=None)
print(data_val)

plt.plot(data_ben.loc[0])
plt.plot(data_msds)
plt.plot(data_val)
plt.show()


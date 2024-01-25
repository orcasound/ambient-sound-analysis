import pandas as pd
import matplotlib.pyplot as plt


data=pd.read_csv('/Users/zach/Desktop/rpi-port-townsend_2023_03_22_11_05_25_psd.txt', delimiter=' ', header=None)
data1=pd.read_csv('/Users/zach/Desktop/row.txt', delimiter=' ', header=None)

plt.plot(data.loc[0])
plt.plot(data1)
plt.show()


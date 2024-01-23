'''
SoundSpace Analytics code snippets.
This is code that I have extracted from data processing pipelines. It may not work as an isolated function without minor adjustments.
'''


'''
Compute PSDs, averaged over N seconds and resolved at M Hz.
'''

#
def wav_to_psd(input_file, fpath, samplerate, RootPath_psd, df, dt):
	'''
	input_file = audio waveform
	df = frequency resolution
	dt = time resolution
	'''
	# ---
	fname, fExt = os.path.splitext( os.path.basename(fpath) )
	# -----------
	NFFT = int(samplerate/float(df))
	# -----------
	# --- FFT WINDOW
	noverlap_par = int(NFFT * 0.5)
	window_par = scipy.signal.get_window('hann', Nx = NFFT, fftbins = True)
	# --- Split in N second snippets, EXCLUDING LEFTOVERS
	dn = samplerate * int(dt)
	loop = int(len(input_file) / (dn))
	SOUND_arr = [input_file[i*dn : (i*dn) + dn] for i in range(loop)]
	# ----
	data = []
	for it_0 in range(len(SOUND_arr)):
		SOUND_feed = SOUND_arr[it_0]
		f_vals, t_vals, SOUND_psd = scipy.signal.spectrogram(SOUND_feed, fs=samplerate, nperseg=NFFT, nfft=NFFT, window=window_par, noverlap=noverlap_par, return_onesided=True, scaling='density', mode='psd')
		#
		SOUND_psd = np.mean(SOUND_psd, axis=1)
		# RMS
		SOUND_psd = SOUND_psd / (np.sqrt(2))
		#
		data.append(SOUND_psd)
	#
	data = np.copy(data)
	#
	data = 10.0 * np.log10(data)
	#
	return data



'''
Long Term Spectral Average Visualization 
'''

#
def LTSA_vis(df_PSD, df_dt, dt_string):
	'''
	'''
	plt.style.use('seaborn-poster')
	# ---
	y_axis_vals = np.arange(0, len(list(df_PSD)))
	x_axis_vals_n = np.arange(0, len(df_PSD), 1)
	z_vals = df_PSD.values
	# ---
	cmap_cp = plt.cm.get_cmap("viridis").copy()
	fig = plt.figure(num=1, figsize=(7.0,4.0))
	plt.clf()
	ax1 = plt.subplot(1,1,1)
	im = ax1.pcolorfast(np.copy(x_axis_vals_n), y_axis_vals, z_vals.T, vmin=30, vmax=80, cmap=cmap_cp)
	plt.ylabel('frequency (Hz)')
	# 24 hours:
	daily_axis = int(60)*4# number of 1 minute bins in 4 hours
	x_axis_vals_dates = [i.strftime("%H:%M:%S") for i in df_dt]
	plt.xticks(x_axis_vals_n[::daily_axis], x_axis_vals_dates[::daily_axis], rotation=45)
	# Colorbar
	cmap_cp.set_under('w')
	cbar = plt.colorbar(im, ax=ax1)
	cbar.set_label('dB re 1 $\mu$Pa$^2$/Hz', rotation=90)
	# ---- Layout settings
	ax1.set_yscale('log')
	# ----
	plt.tight_layout(w_pad=0.0)
	# ---
	return fig, ax1


'''
Power Spectral Density Visualization
see this paper: https://doi.org/10.1121/1.4794934 
'''

# 2D HISTOGRAM
def hist_laxis(data, n_bins, range_limits):
	# Setup bins and determine the bin location for each element for the bins
	R = range_limits
	N = data.shape[-1]
	bins = np.linspace(R[0],R[1],n_bins+1)
	data2D = data.reshape(-1,N)
	idx = np.searchsorted(bins, data2D,'right')-1
	# Some elements would be off limits, so get a mask for those
	bad_mask = (idx==-1) | (idx==n_bins)
	# We need to use bincount to get bin based counts. To have unique IDs for
	# each row and not get confused by the ones from other rows, we need to 
	# offset each row by a scale (using row length for this).
	scaled_idx = n_bins*np.arange(data2D.shape[0])[:,None] + idx
	# Set the bad ones to be last possible index+1 : n_bins*data2D.shape[0]
	limit = n_bins*data2D.shape[0]
	scaled_idx[bad_mask] = limit
	# Get the counts and reshape to multi-dim
	counts = np.bincount(scaled_idx.ravel(),minlength=limit+1)[:-1]
	# normalize
	counts = counts / float(data.shape[1])
	#
	counts.shape = data.shape[:-1] + (n_bins,)
	return counts



#
def CoreMetric_PSD_SplitMemory(psd_fnames, n_bins, range_limits):
	# ---
	# ---
	fsample = CronMetrics_SPD_config.fsample
	'''
	f_interval defines the fragmentation size. The smaller the frequency fragments, the less RAM is occupied to compute the SPD metric and the longer the computation will take.
	'''
	f_interval = int(4000) 
	f_from = int(0)
	f_to = f_from + f_interval
	scan_limit = int(fsample/2.0) + 1
	# ---
	runner = 0
	while f_to < scan_limit:
		PSD_array = []
		#
		for lp_0 in tqdm.tqdm(range(len(psd_fnames))):
			#
			filename_psd_item = psd_fnames[lp_0]
			psd_fname = os.path.basename(filename_psd_item)
			psd_datetime = CronMetrics_master_config.fname_itp_datetime(psd_fname)
			#
			psd_file = np.loadtxt(filename_psd_item, dtype=float)
			psd_file = np.atleast_2d(psd_file)
			if psd_file.size == 0:
				print('{} is empty ... jump to next'.format(psd_fname))
				continue
			#
			for lp_1 in range(len(psd_file)):
				psd_item = psd_file[lp_1][f_from:f_to]
				if numpy.isfinite(psd_item).any() == False:
					continue
				PSD_array.append(psd_item)
			if len(PSD_array) == 0:
				continue
		#
		PSD_array_T = np.copy(PSD_array).T
		#
		# --- 
		MultiHist_element = hist_laxis(data = PSD_array_T, n_bins = n_bins, range_limits = range_limits)
		#
		L50_element = np.percentile(PSD_array_T, 50.0, axis=1)
		L05_element = np.percentile(PSD_array_T, 5.0, axis=1)
		L95_element = np.percentile(PSD_array_T, 95.0, axis=1)
		L75_element = np.percentile(PSD_array_T, 75.0, axis=1)
		L25_element = np.percentile(PSD_array_T, 25.0, axis=1)
		Leq_element = np.mean(PSD_array_T, axis=1)
		Mod_element = scipy.stats.mode(PSD_array)[0][0].T
		#
		if runner == 0:
			MultiHist = MultiHist_element
			L50 = L50_element
			L05 = L05_element
			L95 = L95_element
			L75 = L75_element
			L25 = L25_element
			Leq = Leq_element
			Mod = Mod_element
		if runner > 0:
			MultiHist = np.vstack((MultiHist, MultiHist_element))
			L50 = np.concatenate([L50, L50_element])
			L05 = np.concatenate([L05, L05_element])
			L95 = np.concatenate([L95, L95_element])
			L75 = np.concatenate([L75, L75_element])
			L25 = np.concatenate([L25, L25_element])
			Leq = np.concatenate([Leq, Leq_element])
			Mod = np.concatenate([Mod, Mod_element])
		# ---
		f_from += f_interval
		f_to += f_interval
		runner += 1
		# ---
		del PSD_array_T
		del PSD_array
		gc.collect()
	# ---to pandas array
	f_vals = np.arange(0, int(CronMetrics_SPD_config.fsample/2.0), 1)
	data = np.array([f_vals, L05, L25, L50, L75, L95, Leq, Mod]).T
	columns = ['frequency', 'L05', 'L25', 'L50', 'L75', 'L95', 'Leq', 'Mod']
	df_spdPerc = pd.DataFrame(data=data, columns=columns)
	# ---
	return MultiHist, df_spdPerc


#
def SPD_visual(MultiHist, df_spdPerc, range_limits, n_bins, fsample):
	'''
	'''
	# ---
	plt.style.use('seaborn-poster')
	#
	xedges = np.arange(0, MultiHist.shape[0])
	yedges = np.linspace(range_limits[0],range_limits[1], n_bins)
	X, Y = np.meshgrid(xedges, yedges)
	# ---
	fig = plt.figure(num=1, figsize=(7*1,4*1))
	plt.clf()
	ax1 = plt.subplot(1,1,1)
	cmap = plt.cm.get_cmap("viridis").copy()
	im = ax1.pcolormesh(X, Y, MultiHist.T, vmin=0.00000000000001, vmax=0.06/1.0, cmap=cmap)#, shading='gouraud')# shading is only for python3 and optionally:
	im.cmap.set_under('w')
	#
	plt.xlim(10, CronMetrics_SPD_config.fsample/2.0)
	#
	cbar = plt.colorbar(im, ax=ax1)
	# add percentiles
	ax1.plot(df_spdPerc['L05'], 'k-',lw=0.5, label='L05')
	ax1.plot(df_spdPerc['L50'], 'k-',lw=0.5, label='L50')
	ax1.plot(df_spdPerc['L95'], 'k-',lw=0.5, label='L95')
	ax1.plot(df_spdPerc['Leq'], 'r-',lw=0.5, label='Leq')
	#
	ax1.set_xscale('log')
	plt.ylim(20,140)# arbitrary parameter
	plt.xlabel('Frequency (Hz)')
	plt.ylabel('dB re 1 $\mu$Pa$^2$ Hz$^-1$')
	cbar.set_label('Probability Density', rotation=90)
	ax1.legend(loc='upper right')
	#
	plt.tight_layout(pad=0.5)
	# ---
	return fig, ax1
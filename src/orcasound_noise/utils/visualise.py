import argparse
import pandas as pd
import datetime as dt
import plotly.graph_objects as go

from orcasound_noise.utils import Hydrophone
from orcasound_noise.pipeline import pipeline

# Set up argparse to handle command-line arguments
parser = argparse.ArgumentParser(description='Generate a Hydrophone Power Spectral Density heatmap.')
parser.add_argument('-s', '--start-time', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%d %H:%M'),
                    help='Start datetime in the format YYYY-MM-DD HH:MM',
                    default='2020-01-01 00:00', required=False)
parser.add_argument('-e', '--end-time', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%d %H:%M'),
                    help='End datetime in the format YYYY-MM-DD HH:MM',
                    default='2020-01-02 00:00', required=False)
parser.add_argument('-f', '--frequency', type=int,
                    help='Frequency',
                    default=1, required=False)
parser.add_argument('-t', '--delta-t', type=int,
                    help='Averaging Time',
                    default=60, required=False)
parser.add_argument('-b', '--bands', type=str,
                    help='Frequency Bands',
                    default='3', required=False)
parser.add_argument('-l', '--log', type=bool,
                    help='Apply Logarithmic transformation to the y-axis',
                    default='False', required=False)

args = parser.parse_args()

if args.bands == 'None':
    bands = None
else:
    bands = int(args.bands)

print(f'Generating demo visualisation using {args.start_time, args.end_time}')

pipe = pipeline.NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND,
                                      delta_f=args.frequency,
                                      delta_t=args.delta_t,
                                      bands=bands,
                                      wav_folder="wav_folder",
                                      pqt_folder="pqt_folder")
pqt_filepath, bb_filepath = pipe.generate_parquet_file(start=args.start_time,
                                                       end=args.end_time, upload_to_s3=False)
psd_df = pd.read_parquet(pqt_filepath)

# Plot PSD
fig = go.Figure(data=go.Heatmap(x=psd_df.index, y=psd_df.columns, z=psd_df.values.transpose(), colorscale='Viridis',
                                colorbar={"title": 'Magnitude'}))
fig.update_layout(
    title="Hydrophone Power Spectral Density",
    xaxis_title="Time",
    yaxis_title="Frequency (Hz)",
    legend_title="Magnitude"
)
if args.log:
    fig.update_yaxes(type="log")

fig.write_image(f'temp/psd_{args.start_time}_{args.end_time}.png')

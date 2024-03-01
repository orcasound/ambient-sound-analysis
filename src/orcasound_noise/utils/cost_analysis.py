import datetime as dt
import time
import argparse
import logging

from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone


def parse_args():
    parser = argparse.ArgumentParser(description='Run Noise Analysis Pipeline')
    # Adding arguments
    parser.add_argument('--start-time', required=True, help='Start date in YYYY-MM-DD-HH format')
    parser.add_argument('--end-time', required=True, help='End date in YYYY-MM-DD-HH format')
    parser.add_argument('--delta_f', type=int, default=1, help='Frequency resolution')
    parser.add_argument('--bands', nargs='*', default=None, help='List of bands')
    parser.add_argument('--delta_t', type=int, default=1, help='Time resolution')
    parser.add_argument('--mode', default='fast', choices=['fast', 'safe'], help='Mode of operation')
    return parser.parse_args()


def setup_logger():
    logger = logging.getLogger('NoiseAnalysisLogger')
    logger.setLevel(logging.INFO)  # Set the logging level to INFO

    # Check if the logger already has handlers to prevent duplication
    if not logger.handlers:
        # Create a file handler in append mode
        fh = logging.FileHandler('noise_analysis_logs.txt', mode='a')
        fh.setLevel(logging.INFO)

        # Create a formatter and set the format
        formatter = logging.Formatter('%(asctime)s || Execution Time: %(execution_time)s - '
                                      'Data Duration: %(duration)|| '
                                      'Start Time: %(start_time)s - End Time: %(end_time)s | '
                                      'Parameters: delta_f: %(delta_f) - bands: %(bands) - delta_t: %(delta_t) - '
                                      'mode: %(mode)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(fh)

    return logger


if __name__ == '__main__':
    logger = setup_logger()
    args = parse_args()  # Parse arguments

    print('#' * 10, 'Starting Cost Analysis with the following parameters', '#' * 10)
    print(f'start_time: {args.start_time}, end_time: {args.end_time}, 'f'delta_f: {args.delta_f}, '
          f'delta_t: {args.delta_t}, bands: {args.bands}, mode: {args.mode}')

    # Convert string dates to datetime objects
    try:
        start_time = dt.datetime.strptime(args.start_time, "%Y-%m-%d-%H")
        end_time = dt.datetime.strptime(args.end_time, "%Y-%m-%d-%H")
    except ValueError:
        start_time = dt.datetime.strptime(args.start_time, "%Y-%m-%d")
        end_time = dt.datetime.strptime(args.end_time, "%Y-%m-%d")

    pipeline = NoiseAnalysisPipeline(Hydrophone.ORCASOUND_LAB,
                                     pqt_folder='pqt',
                                     delta_f=args.delta_f,
                                     bands=args.bands,
                                     delta_t=args.delta_t,
                                     mode=args.mode)
    ts = time.time()
    psd_path, broadband_path = pipeline.generate_parquet_file(start_time, end_time, upload_to_s3=False)
    execution_time = time.time() - ts
    print(execution_time)

    logger.info('', extra={'execution_time': execution_time,
                           'duration': str(end_time - start_time),
                           'start_time': start_time,
                           'end_time': end_time,
                           'delta_f': args.delta_f,
                           'delta_t': args.delta_t,
                           'bands': args.bands,
                           'mode': args.mode})

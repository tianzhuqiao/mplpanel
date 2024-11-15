import numpy as np
import pandas as pd
from .utility import _dict

def get_stats(axes, visible_range=True):

    stats = []
    for ax in axes:
        xmin, xmax = ax.xaxis.get_view_interval()
        for line in ax.lines:
            label = line.get_label()
            if label.startswith('_bsm'):
                continue

            y_data = line.get_ydata(True)
            if visible_range:
                x_data = line.get_xdata(False)
                y_data = y_data[(xmin <= x_data) & (x_data <= xmax)]

            s = _dict()
            s.name = label
            s.count = len(y_data)
            s.min = np.nanmin(y_data)
            s.max = np.nanmax(y_data)
            s.average = np.nanmean(y_data)
            s.median = np.nanmedian(y_data)
            s.std = np.nanstd(y_data)
            stats.append(s)

    return pd.DataFrame(stats)

def get_data(axes, visible_range=True):

    data = []
    for ax in axes:
        xmin, xmax = ax.xaxis.get_view_interval()
        for line in ax.lines:
            label = line.get_label()
            if label.startswith('_bsm'):
                continue

            y_data = line.get_ydata(True)
            x_data = line.get_xdata(True)
            if visible_range:
                x = line.get_xdata(False)
                idx = (xmin <= x) & (x <= xmax)
                y_data = y_data[idx]
                x_data = x_data[idx]

            df = pd.DataFrame({'x': x_data, label: y_data})
            data.append(df)

        # combine data into single dataframe if all x data are same
        if len(data) > 1:
            data_size = [len(d) for d in data]
            if all(d == data_size[0] for d in data_size):
                same_x = [np.all(d['x'] == data[0]['x']) for d in data]
                if all(same_x):
                    df = data[0]
                    for i in range(1, len(data)):
                        for c in data[i].columns:
                            if c == 'x':
                                continue
                            df[c] = data[i][c]
                    data = df

    return data

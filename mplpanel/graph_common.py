import wx
import wx.py.dispatcher as dp
import numpy as np

class GraphObject():
    def __init__(self, figure):
        self.figure = figure
        dp.connect(receiver=self.OnUpdated, signal='graph.axes_updated')
        dp.connect(self.OnRemovingLine, 'graph.removing_line')
        dp.connect(self.OnRemovedLine, 'graph.removed_line')

    def OnRemovingLine(self, figure, lines):
        if self.figure != figure:
            return False
        return True

    def OnRemovedLine(self, figure, axes):
        if self.figure != figure:
            return False
        return True

    def OnUpdated(self, figure, axes):
        # the axes/lines has been updated
        if self.figure != figure:
            return False
        return True

    def notify_update(self, axes):
        # notify others that the data of axes has changed
        dp.send('graph.axes_updated', figure=self.figure, axes=axes)

    def get_sharex(self, ax):
        sharex = ax
        while sharex and sharex._sharex:
            sharex = sharex._sharex
        return sharex

    def get_sharey(self, ax):
        sharey = ax
        while sharey and sharey._sharey:
            sharey = sharey._sharey
        return sharey

    def get_axes(self, axes, sharex=False, sharey=False, all_axes=False):
        if all_axes:
            axes_out = self.figure.axes
        else:
            axes_out = set(axes)
            if sharex:
                sharexes = set()
                for ax in axes:
                    sharexes.add(self.get_sharex(ax))
                for ax in self.figure.axes:
                    if self.get_sharex(ax) in sharexes:
                        axes_out.add(ax)
            if sharey:
                shareyes = set()
                for ax in axes:
                    shareyes.add(self.get_sharey(ax))
                for ax in self.figure.axes:
                    if self.get_sharey(ax) in shareyes:
                        axes_out.add(ax)
        return axes_out

    def get_xy_dis_gain(self, ax=None):
        # the gain applied to x/y when calculate the distance between to point
        # e.g., a data point to the mouse position
        # for example, if the figure is square (width == height), but
        # x range is [0, 100], and y range is [0, 0.1], the physical distance
        # in y axis will be `ignored` as x is 1000 times larger than y.
        if ax is None:
            ax = self.figure.gca()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        box = ax.get_window_extent()
        if xlim[1] - xlim[0] == 0 or ylim[1] - ylim[0] == 0:
            return 1, 1
        gx = box.width / abs(xlim[1] - xlim[0])
        gy = box.height / abs(ylim[1] - ylim[0])
        return gx, gy

    def get_closest_line(self, axes, mx, my):
        min_dis = np.inf
        active_line = None
        for g in axes:
            for line in g.lines:
                if not line.get_visible():
                    continue
                dis = self.distance_to_line(line, mx, my)
                if dis < min_dis:
                    min_dis = dis
                    active_line = line
        return active_line, min_dis

    def distance_to_line(self, line, mx, my):
        # distance from the closest point in line to (mx, my) in display coordinate
        inv = line.axes.transData.inverted()
        dmx, dmy = inv.transform((mx, my))
        didx, dx, dy = self.get_closest(line, dmx, dmy)
        if didx is None:
            return np.inf

        x0, y0 = line.axes.transData.transform((dx, dy))
        dis = np.sqrt((x0-mx)**2 + (y0-my)**2)
        if wx.Platform != '__WXMSW__':
            ratio = self.figure.canvas.device_pixel_ratio
        else:
            ratio = 1
        return dis/ratio

    def get_closest(self, line, mx, my, tolerance=0):
        """return the index of the points whose distance to (mx, my) is smaller
           than tolerance, or the closest data point to (mx, my)"""
        x, y = line.get_data(False)
        if mx is None and my is None:
            return None, None, None

        gx, gy = self.get_xy_dis_gain(line.axes)
        mini = []
        if tolerance>0:
            if my is None:
                mini = np.where((x-mx)**2 * gx**2 < tolerance**2)[0]
            elif mx is None:
                mini = np.where((y-my)**2 * gx**2 < tolerance**2)[0]
            else:
                mini = np.where(((x-mx)**2 * gx**2 + (y-my)**2 * gy**2) < tolerance**2)[0]
        if len(mini) == 0:
            try:
                if my is None:
                    mini = np.nanargmin((x-mx)**2)
                elif mx is None:
                    mini = np.nanargmin((y-my)**2)
                else:
                    mini = np.nanargmin((x-mx)**2 * gx**2 + (y-my)**2 * gy**2)
            except ValueError:
                return None, None, None
        return mini, x[mini], y[mini]

    @classmethod
    def is_aux_line(cls, l):
        label = l.get_label()
        return label.startswith('_bsm')

    def has_visible_lines(self, ax):
        for l in ax.lines:
            if self.is_aux_line(l):
                continue
            if l.get_visible():
                return True
        return False

    def GetMenu(self, axes):
        '''return the context menu'''
        return []

    def ProcessCommand(self, cmd, axes):
        '''process the menu command'''

    def pick(self, event):
        '''a line is picked'''

    def key_down(self, event):
        pass

    def key_pressed(self, event):
        pass

    def mouse_pressed(self, event):
        '''the mouse is down'''

    def mouse_released(self, event):
        '''the mouse is up'''

    def mouse_move(self, event):
        '''the mouse is moving'''

    def activated(self):
        '''the object is activated'''

    def deactivated(self):
        '''the obje is deactivated'''

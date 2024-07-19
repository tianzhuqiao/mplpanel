import weakref
import datetime
import wx
import matplotlib
from matplotlib.backends.backend_wx import cursors
import numpy as np
import pandas as pd
from .graph_common import GraphObject
from .graph_subplot import refresh_legend
from .utility import send_data_to_shell

class AuxLine:
    def __init__(self, ax):
        self.ax = weakref.ref(ax)
        self.is_show = False
        self.line = None
        self.line2 = None
        self.line3 = None
        self.text = None

        self.active = None

    def create_if_needed(self):
        pass

    def hit_test(self, x, y):
        return False

    def is_close_to(self, x1, x2, threshold=10):
        if wx.Platform != '__WXMSW__':
            ratio = self.ax().figure.canvas.device_pixel_ratio
        else:
            ratio = 1
        return np.abs(x1-x2) < threshold*ratio

    def hit_test_vert(self, line, x, y):
        if line is None:
            return False
        line = line()
        if line is None or not line.get_visible():
            return False
        trans = line.get_transform()
        lx, ly1 = trans.transform((line.get_xdata(False)[1], line.get_ydata()[0]))
        _, ly2 = trans.transform((line.get_xdata(False)[0], line.get_ydata()[1]))
        if self.is_close_to(lx, x, 10) and ly1 <= y <= ly2:
            self.active = line
            return True
        return False

    def hit_test_horz(self, line, x, y):
        if line is None:
            return False
        line = line()
        if line is None or not line.get_visible():
            return False
        trans = line.get_transform()
        lx1, ly = trans.transform((line.get_xdata(False)[0], line.get_ydata()[0]))
        lx2, _ = trans.transform((line.get_xdata(False)[1], line.get_ydata()[1]))
        if self.is_close_to(ly, y, 10) and lx1 <= x <= lx2:
            self.active = line
            return True
        return False

    def show(self, show=True):
        if self.is_show == show:
            return
        self.is_show = show
        # create line if needed
        self.create_if_needed()
        for obj in [self.line, self.line2, self.line3, self.text]:
            if obj is not None and obj() is not None:
                obj().set_visible(show)

    def clear(self):
        for line in [self.line, self.line2, self.line3, self.text]:
            if line is None or line() is None:
                continue
            line().remove()
        self.line = None
        self.line2 = None
        self.line3 = None
        self.text = None

    def update_line12(self, data = None):
        pass

    def update_line3(self, d):
        pass

class XAuxLine(AuxLine):
    # labels for x-axis aux line
    line_label = "_bsm_x_axvline"
    line2_label = "_bsm_x_axvline2"
    line3_label = "_bsm_x_axhline"
    text_label = "_bsm_x_text"

    def __init__(self, ax):
        super().__init__(ax)

        self.line_idx = 0
        self.line2_idx = 0

    def create_if_needed(self):
        ax = self.ax()
        if not self.is_show or ax is None:
            return

        xdata = np.mean(ax.get_xlim())
        style = dict(linestyle='--', zorder=10, color='tab:green')
        if self.line is None or self.line() is None:
            line = ax.axvline(xdata, label=self.line_label, **style)
            self.line = weakref.ref(line)

        if self.line2 is None or self.line2() is None:
            line = ax.axvline(xdata, label=self.line2_label, **style)
            self.line2 = weakref.ref(line)

        if self.line3 is None or self.line3() is None:
            line = ax.axvline(xdata, label=self.line3_label, **style)
            line.set_ydata([0.5, 0.5])
            self.line3 = weakref.ref(line)

        if self.text is None or self.text() is None:
            # text
            trans = ax.get_xaxis_transform(which='grid')
            text = ax.text(xdata, 0.5, '', fontsize=10, va='bottom', ha='center',
                           transform = trans, label=self.text_label, zorder=10)
            text.set_in_layout(False)
            text.set_clip_on(True)
            text.set_visible(False)
            self.text = weakref.ref(text)

    def hit_test(self, x, y):
        for line in [self.line, self.line2]:
            if self.hit_test_vert(line, x, y):
                return True, line(), True

        for line in [self.line3]:
            if self.hit_test_horz(line, x, y):
                return True, line(), False
        return False, None, False

    def update_line3(self, d):
        y = d
        if self.line3() is not None:
            trans = self.line3().get_transform().inverted()
            _, ly = trans.transform((0, y))
            self.line3().set_ydata([ly, ly])
            if self.text() is not None:
                self.text().set_y(ly)

    def update_line12(self, data = None):
        if not self.is_show:
            return
        if self.line() is None or self.line2() is None or \
           self.line3() is None or self.text() is None:
            return

        if not (self.active in [self.line(), self.line2()]):
            return
        xdata = data
        x, idx = None, None
        x_min = np.inf
        if xdata is None:
            xdata = self.active.get_xdata(False)[0]
        for l in self.active.axes.lines:
            label = l.get_label()
            if label.startswith('_bsm'):
                # legend is not visible
                continue
            lx = l.get_xdata(False)
            lidx = np.argmin(np.abs(lx - xdata))
            if np.abs(lx[lidx] - xdata) < x_min:
                x_min = np.abs(lx[lidx] - xdata)
                x = l.get_xdata()
                idx = lidx
        if x is not None and idx is not None:
            self.active.set_xdata([x[idx], x[idx]])
            if self.active == self.line():
                self.line_idx = idx
            else:
                self.line2_idx = idx
            start = self.line().get_xdata()[0]
            end = self.line2().get_xdata()[0]
            if isinstance(start, datetime.date) and not isinstance(end, datetime.date):
                end = matplotlib.dates.num2date(end)

            if not isinstance(start, datetime.date) and isinstance(end, datetime.date):
                start = matplotlib.dates.num2date(start)

            start, end = min(start, end), max(start, end)
            self.line3().set_xdata([start, end])
            if isinstance(start, datetime.date):
                self.text().set_text(f'{abs((start-end).total_seconds()):g}')
            else:
                self.text().set_text(f'{abs(start-end):g}')
            self.text().set_x(start+ (end-start)/2)

class YAuxLine(AuxLine):
    # labels for x-axis aux line
    line_label = "_bsm_y_axvline"
    line2_label = "_bsm_y_axvline2"
    line3_label = "_bsm_y_axhline"
    text_label = "_bsm_y_text"

    def create_if_needed(self):
        ax = self.ax()
        if not self.is_show or ax is None:
            return

        # create the y-axis line/text if needed
        ydata = np.mean(ax.get_ylim())
        style = dict(zorder=10, color='tab:pink', linestyle='--')
        if self.line is None or self.line() is None:
            line = ax.axhline(ydata, label=self.line_label, **style)
            self.line = weakref.ref(line)

        if self.line2 is None or self.line2() is None:
            line = ax.axhline(ydata, label=self.line2_label, **style)
            self.line2 = weakref.ref(line)

        if self.line3 is None or self.line3() is None:
            line = ax.axhline(ydata, label=self.line3_label, **style)
            line.set_xdata([0.5, 0.5])
            self.line3 = weakref.ref(line)

        if self.text is None or self.text() is None:
            trans = ax.get_yaxis_transform(which='grid')
            text = ax.text(0.5, ydata, '', fontsize=10, va='center', ha='right',
                           transform = trans, label=self.text_label, zorder=10)
            text.set_in_layout(False)
            text.set_clip_on(True)
            self.text = weakref.ref(text)

    def hit_test(self, x, y):
        for line in [self.line, self.line2]:
            if self.hit_test_horz(line, x, y):
                return True, line(), False

        for line in [self.line3]:
            if self.hit_test_vert(line, x, y):
                return True, line(), True
        return False, None, False

    def update_line3(self, d):
        x = d
        if self.line3() is not None:
            trans = self.line3().get_transform().inverted()
            lx, _ = trans.transform((x, 0))
            self.line3().set_xdata([lx, lx])
            if self.text() is not None:
                self.text().set_x(lx)

    def update_line12(self, data = None):
        if self.active not in [self.line(), self.line2()]:
            return
        if self.line() is None or self.line2() is None or \
           self.line3() is None or self.text() is None:
            return

        ydata = data
        if ydata is None:
            ydata = self.active.get_ydata()[0]

        if ydata is not None:
            self.active.set_ydata([ydata, ydata])
            start = self.line().get_ydata()[0]
            end = self.line2().get_ydata()[0]
            start, end = min(start, end), max(start, end)
            self.line3().set_ydata([start, end])
            self.text().set_text(f'{abs(start-end):g}')
            self.text().set_y((start+end)/2)


class AxLine:
    # labels for main timeline
    axvline_label = "_bsm_axvline"

    def __init__(self, ax):
        self.ax = weakref.ref(ax)

        # main timeline, shared among all sharex
        self.axvline = None

        # x-axis
        self.x_aux_line = XAuxLine(ax)
        # y-axis
        self.y_aux_line = YAuxLine(ax)

        # active line, used for moving with mouse
        self.active = None

        # x-axis, vertical line, used for moving with key
        self.axvline_idx = 0

    def update(self):
        ax = self.ax()
        if ax is None:
            return
        # create the x-axis line/text if needed
        xdata = np.mean(ax.get_xlim())
        if self.axvline is None or self.axvline() is None:
            # main axvline
            line = ax.axvline(xdata, label=self.axvline_label, zorder=10,
                              color='tab:red')
            self.axvline = weakref.ref(line)

        self.x_aux_line.create_if_needed()
        self.y_aux_line.create_if_needed()

    def update_legend(self, xdata = None):
        # update x-axis axvline and legend
        if xdata is None:
            xdata = self.axvline().get_xdata(False)[0]
        x, y, idx = None, None, None
        x_min = np.inf
        for l in self.ax().lines:
            label = l.get_label()
            if label.startswith('_bsm'):
                # ignore _bsm line
                continue
            lx = l.get_xdata(False)
            lidx = np.argmin(np.abs(lx - xdata))
            if np.abs(lx[lidx] - xdata) < x_min:
                x_min = np.abs(lx[lidx] - xdata)
                x = l.get_xdata()
                idx = lidx
            if label.startswith('_'):
                # legend is not visible
                continue

            label = label.split(' ')
            if len(label) > 1:
                label = label[:-1]
            label = ' '.join(label)
            y = l.get_ydata()
            #idx = np.argmin(np.abs(x - xdata))
            label = f'{label} {y[lidx]:g}'
            l.set_label(label)
        if x is not None and idx is not None:
            self.axvline().set_xdata([x[idx], x[idx]])
            self.axvline_idx = idx

    def hit_test(self, x, y):
        # check if (x, y) is close to the axvline in ax
        for line in (self.axvline,):
            if line is None:
                continue
            line = line()
            if line is None or not line.get_visible():
                continue
            trans = line.get_transform()
            lx, ly1 = trans.transform((line.get_xdata(False)[0], line.get_ydata()[0]))
            _, ly2 = trans.transform((line.get_xdata(False)[1], line.get_ydata()[1]))
            if wx.Platform != '__WXMSW__':
                ratio = self.ax().figure.canvas.device_pixel_ratio
            else:
                ratio = 1
            if np.abs(lx-x) < 10*ratio and ly1 <= y <= ly2:
                self.active = line
                return True, line, True

        ret, line, vert = self.x_aux_line.hit_test(x, y)
        if not ret:
            ret, line, vert = self.y_aux_line.hit_test(x, y)
        return ret, line, vert

    def clear(self):
        for l in self.ax().lines:
            label = l.get_label()
            if label.startswith('_'):
                # ignore line without label
                continue
            label = label.split(' ')
            if len(label) > 1:
                label = label[:-1]
            label = ' '.join(label)
            l.set_label(label)
        if self.axvline() is not None:
            self.axvline().remove()
        self.x_aux_line.clear()
        self.y_aux_line.clear()

class Timeline(GraphObject):
    ID_CLEAR = wx.NewIdRef()
    ID_CLEAR_SHAREX = wx.NewIdRef()
    ID_CLEAR_ALL = wx.NewIdRef()
    ID_EXPORT_TO_TERM = wx.NewIdRef()
    ID_EXPORT_TO_TERM_SHAREX = wx.NewIdRef()
    ID_EXPORT_TO_TERM_ALL = wx.NewIdRef()
    ID_MOVE_TIMELINE_HERE = wx.NewIdRef()
    ID_SHOW_AUX_TIMELINE = wx.NewIdRef()
    ID_SHOW_Y_AUX_TIMELINE = wx.NewIdRef()
    def __init__(self, figure):
        super().__init__(figure)

        self.all_axlines = weakref.WeakKeyDictionary()

        self.active_axvline = None

        self.draggable = False
        self.drag_vert = True

        self.initialized = False

    def get(self, ax, create=True):
        if ax not in self.all_axlines and create:
            self.all_axlines[ax] = AxLine(ax)
        if ax in self.all_axlines:
            axline = self.all_axlines[ax]
            axline.update()
            return axline
        return None

    def OnRemovedLine(self, figure, axes):
        if not super().OnRemovedLine(figure, axes):
            return False

        if not self.has_visible_lines(axes):
            self._clear_axline([axes])
        return True

    def mouse_pressed(self, event):
        if not event.inaxes:
            return

        x, y = event.x, event.y
        ret, axvline, vert = self._is_close_to_axvline(event.inaxes, x, y)
        if ret:
            self.draggable = True
            self.drag_vert = vert
            self.active_axvline = axvline
        else:
            # looks like for the first click, event.key is always 'none', so use
            # the one from wxPython
            if wx.GetKeyState(wx.WXK_SHIFT):
                for ax in [event.inaxes]:
                    xdata = event.xdata
                    self.update_legend([ax], xdata)

    def _is_close_to_axvline(self, ax, x, y):
        # check if (x, y) is close to the axvline in ax
        axvline = self.get(ax, create=False)
        if axvline is None:
            return False, None, False
        return axvline.hit_test(x, y)

    def OnUpdated(self, figure, axes):
        if not super().OnUpdated(figure, axes):
            return

        self.update_legend(axes)

    def update_legend(self, axes, xdata = None):
        # update all sharex
        axes = self.get_axes(axes, sharex=True)
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.update_legend(xdata=xdata)
            refresh_legend(ax)

    def show_x_axline(self, axes, show):
        # update all sharex
        # axes = self.get_axes(axes, sharex=True)
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.x_aux_line.show(show)

    def show_y_axline(self, axes, show):
        # update all sharey
        # axes = self.get_axes(axes, sharey=True)
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.y_aux_line.show(show)

    def update_x_axvline(self, axes, xdata = None):
        # update all sharex
        #axes = self.get_axes(axes, sharex=True)
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.x_aux_line.update_line12(xdata)

    def update_y_axhline(self, axes, ydata = None):
        # update all sharey
        #axes = self.get_axes(axes, sharey=True)
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.y_aux_line.update_line12(ydata)

    def update_x_axhline(self, axes, y):
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.x_aux_line.update_line3(y)

    def update_y_axvline(self, axes, x):
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            axline.y_aux_line.update_line3(x)

    def mouse_move(self, event):
        # TODO remove unnecessary set_cursor
        self.figure.canvas.set_cursor(cursors.POINTER)
        if not event.inaxes:
            return

        x, y = event.x, event.y
        vert = self.drag_vert
        ret = False
        if not self.draggable:
            ret, _, vert = self._is_close_to_axvline(event.inaxes, x, y)

        if ret or self.draggable:
            if vert:
                self.figure.canvas.set_cursor(cursors.RESIZE_HORIZONTAL)
            else:
                self.figure.canvas.set_cursor(cursors.RESIZE_VERTICAL)
        if self.draggable and self.active_axvline:
            if self.active_axvline.get_label() in [XAuxLine.line_label, XAuxLine.line2_label]:
                self.update_x_axvline([event.inaxes], event.xdata)
            elif self.active_axvline.get_label() == XAuxLine.line3_label:
                self.update_x_axhline([event.inaxes], event.y)
            elif self.active_axvline.get_label() in [YAuxLine.line_label, YAuxLine.line2_label]:
                self.update_y_axhline([event.inaxes], event.ydata)
            elif self.active_axvline.get_label() == YAuxLine.line3_label:
                self.update_y_axvline([event.inaxes], event.x)
            else:
                self.update_legend([event.inaxes], event.xdata)

    def mouse_released(self, event):
        self.draggable = False



    def _get_next_x_data(self, ax, xdata, step=1):
        for l in ax.lines:
            if self.is_aux_line(l):
                continue
            x = l.get_xdata(False)
            idx = np.argmin(np.abs(x - xdata))
            idx = min(max(idx + step, 0), len(x)-1)
            return x[idx]
        return None

    def key_pressed(self, event):
        """Callback for key presses."""
        if not event.inaxes:
            return
        if event.key in ['shift+left', 'left', 'shift+right', 'right']:
            if self.active_axvline:
                # get the current x value
                xdata = self.active_axvline.get_xdata(False)
                step = 10 if 'shift' in event.key else 1
                if 'left' in event.key:
                    step = -step
                x = self._get_next_x_data(event.inaxes, xdata[0], step)
                if self.active_axvline.get_label() in [XAuxLine.line_label, XAuxLine.line2_label]:
                    self.update_x_axvline([event.inaxes], x)
                elif self.active_axvline.get_label() == AxLine.axvline_label:
                    self.update_legend([event.inaxes], x)

    def create_axvline_if_needed(self, ax):
        return self.get(ax, create=True) is not None

    def activated(self):
        if self.initialized:
            return
        self.initialized = True
        for ax in self.figure.axes:
            # add axvline if not there
            if self.create_axvline_if_needed(ax):
                xdata = np.mean(ax.get_xlim())
                self.update_legend([ax], xdata)

    def deactivated(self):
        self.draggable = False

    def _clear_axline(self, axes):
        for ax in axes:
            # remove all axvline
            axline = self.get(ax, False)
            if axline is None:
                continue
            axline.clear()
            self.all_axlines.pop(ax, None)
            refresh_legend(ax)

    def _export(self, axes):
        data = {}
        for ax in axes:
            axline = self.get(ax, create=False)
            if axline is None:
                continue
            idx = axline.axvline_idx
            for l in ax.lines:
                label = l.get_label()
                if label.startswith('_bsm'):
                    continue
                if not label.startswith('_'):
                    # visible legend, remove value first
                    label = label.split(' ')
                    if len(label) > 1:
                        label = label[:-1]
                    label = ' '.join(label)
                x = l.get_xdata()
                y = l.get_ydata()
                sharex = self.get_sharex(ax)
                if sharex not in data:
                    data[sharex] = pd.DataFrame()
                    data[sharex]['x'] = [x[idx]]
                data[sharex][label] = [y[idx]]
        data = list(data.values())
        if len(data) == 1:
            data = data[0]
        return data

    def GetMenu(self, axes):
        axline = self.get(axes[0], create=False)
        aux_visible = False
        y_aux_visible = False
        if axline is not None:
            aux_visible = axline.x_aux_line.is_show
            y_aux_visible = axline.y_aux_line.is_show
        cmd = [{'id': self.ID_MOVE_TIMELINE_HERE,
                'label': 'Move timeline in view',
                'enable': self.has_visible_lines(axes[0])},
               {'id': self.ID_SHOW_AUX_TIMELINE,
                'label': 'Hide vertical aux timeline' if aux_visible else "Show vertical aux timeline",
                'enable': self.has_visible_lines(axes[0]),
                'type': wx.ITEM_CHECK,
                'check': aux_visible},
               {'id': self.ID_SHOW_Y_AUX_TIMELINE,
                'label': 'Hide horizontal aux line' if y_aux_visible else "Show horizontal aux line",
                'enable': self.has_visible_lines(axes[0]),
                'type': wx.ITEM_CHECK,
                'check': y_aux_visible},
               {'type': wx.ITEM_SEPARATOR},
               {'id': self.ID_EXPORT_TO_TERM,
                'label': 'Export to shell'},
               {'id': self.ID_EXPORT_TO_TERM_SHAREX,
                'label': 'Export all to shell with shared x-axis'},
               {'id': self.ID_EXPORT_TO_TERM_ALL,
                'label': 'Export all to shell'},
               {'type': wx.ITEM_SEPARATOR},
               {'id': self.ID_CLEAR,
                'label': 'Clear on current subplot'},
               {'id': self.ID_CLEAR_SHAREX,
                'label': 'Clear all with shared x-axis'},
               {'id': self.ID_CLEAR_ALL,
                'label': 'Clear all'},
              ]
        return cmd

    def ProcessCommand(self, cmd, axes):
        if cmd == self.ID_MOVE_TIMELINE_HERE:
            for ax in axes:
                if self.create_axvline_if_needed(ax):
                    xdata = np.mean(ax.get_xlim())
                    self.update_legend([ax], xdata)
        elif cmd in [self.ID_SHOW_AUX_TIMELINE]:
            for ax in axes:
                xdata = np.mean(ax.get_xlim())
                axvline = self.get(ax, create=True)
                if axvline is None:
                    continue
                show = not axvline.x_aux_line.is_show
                self.show_x_axline([ax], show)
                if show:
                    self.update_x_axvline([ax], xdata)
        elif cmd in [self.ID_SHOW_Y_AUX_TIMELINE]:
            for ax in axes:
                ydata = np.mean(ax.get_ylim())
                axvline = self.get(ax, create=True)
                if axvline is None:
                    continue
                show = not axvline.y_aux_line.is_show
                self.show_y_axline([ax], show)
                if show:
                    self.update_y_axhline([ax], ydata)

        elif cmd == self.ID_CLEAR:
            self._clear_axline(axes)
        elif cmd == self.ID_CLEAR_SHAREX:
            self._clear_axline(self.get_axes(axes, sharex=True))
        elif cmd == self.ID_CLEAR_ALL:
            self._clear_axline(self.get_axes(axes, all_axes=True))
        elif cmd in [self.ID_EXPORT_TO_TERM, self.ID_EXPORT_TO_TERM_SHAREX,
                     self.ID_EXPORT_TO_TERM_ALL]:
            if cmd == self.ID_EXPORT_TO_TERM_ALL:
                axes = self.get_axes(axes, all_axes=True)
            elif cmd == self.ID_EXPORT_TO_TERM_SHAREX:
                axes = self.get_axes(axes, sharex=True)

            data = self._export(axes)
            send_data_to_shell('timeline_data', data)

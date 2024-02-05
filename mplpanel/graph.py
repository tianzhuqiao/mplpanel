import wx
import wx.py.dispatcher as dp
import numpy as np
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_wx import FigureManagerWx
from matplotlib.backend_bases import CloseEvent
from matplotlib._pylab_helpers import Gcf
import matplotlib.pyplot as plt
from matplotlib import rcParams
import matplotlib.style as mplstyle
import matplotlib.transforms as mtransforms
from .graph_canvas import FigureCanvas
from .graph_common import GraphObject
from .graph_edit import LineEditor
from .graph_datatip import DataCursor
from .graph_timeline import Timeline
from .graph_dock import GDock
from .utility import build_menu_from_list, svg_to_bitmap
from .graph_svg import split_vert_svg, delete_svg, line_style_svg, \
                    new_page_svg, home_svg, backward_svg, backward_gray_svg, \
                    forward_svg, forward_gray_svg, zoom_svg, pan_svg, copy_svg, \
                    save_svg, edit_svg, note_svg, timeline_svg
from .graph_toolbar import GraphToolbar
from .graph_subplot import add_subplot, del_subplot
rcParams.update({'figure.autolayout': True, 'toolbar': 'None',
                 'path.simplify_threshold': 1})
matplotlib.interactive(True)
mplstyle.use('fast')


class Pan(GraphObject):
    def __init__(self, figure):
        super().__init__(figure)
        self.axes = None

    def key_down(self, event):
        keycode = event.GetKeyCode()
        axes = self.axes
        if axes is None:
            if len(self.figure.get_axes()) > 1:
                return
            axes = [self.figure.gca()]
        xlims_all = []
        ylims_all = []
        for ax in axes:
            # get the xlim from all axes first, as some x-axis may be shared;
            # otherwise, the shared x-axis will be moved multiple times.
            xlims_all.append(np.array(ax.get_xlim()))
            ylims_all.append(np.array(ax.get_ylim()))
        step = 1
        if event.ShiftDown():
            step = 1/10
        for i, ax in enumerate(axes):
            xlims = xlims_all[i]
            ylims = ylims_all[i]
            rng_x = abs(xlims[1] - xlims[0])*step
            rng_y = abs(ylims[1] - ylims[0])*step
            if keycode in [wx.WXK_LEFT, wx.WXK_RIGHT]:
                if keycode == wx.WXK_LEFT:
                    xlims -= rng_x
                else:
                    xlims += rng_x

                ax.set_xlim(xlims)
                # rescale y to show data
                #ax.autoscale(axis='y')
            elif keycode in [wx.WXK_UP, wx.WXK_DOWN]:
                if keycode == wx.WXK_UP:
                    ylims += rng_y
                else:
                    ylims -= rng_y

                ax.set_ylim(ylims)
                #ax.autoscale(axis='x')
            else:
                event.Skip()
        self.figure.canvas.draw_idle()

    def mouse_pressed(self, event):
        self.axes = [a for a in self.figure.get_axes()
                if a.in_axes(event)]
        return False

class Toolbar(GraphToolbar):
    ID_AUTO_SCALE_X = wx.NewIdRef()
    ID_AUTO_SCALE_Y = wx.NewIdRef()
    ID_AUTO_SCALE_XY = wx.NewIdRef()
    ID_SPLIT_HORZ = wx.NewIdRef()
    ID_SPLIT_HORZ_SHARE_XAXIS = wx.NewIdRef()
    ID_SPLIT_HORZ_SHARE_YAXIS = wx.NewIdRef()
    ID_SPLIT_HORZ_SHARE_XYAXIS = wx.NewIdRef()
    ID_SPLIT_VERT = wx.NewIdRef()
    ID_SPLIT_VERT_SHARE_XAXIS = wx.NewIdRef()
    ID_SPLIT_VERT_SHARE_YAXIS = wx.NewIdRef()
    ID_SPLIT_VERT_SHARE_XYAXIS = wx.NewIdRef()
    ID_DELETE_SUBPLOT = wx.NewIdRef()
    ID_DELETE_LINES = wx.NewIdRef()
    ID_LINE_STYLE_LINE = wx.NewIdRef()
    ID_LINE_STYLE_DOT = wx.NewIdRef()
    ID_LINE_STYLE_LINE_DOT = wx.NewIdRef()
    ID_FLIP_Y_AXIS = wx.NewIdRef()
    ID_FLIP_X_AXIS = wx.NewIdRef()
    ID_COPY_SUBPLOT = wx.NewIdRef()

    def __init__(self, canvas, figure):
        if matplotlib.__version__ < '3.3.0':
            self._init_toolbar = self.init_toolbar
        else:
            self._init_toolbar = self.init_toolbar_empty
        GraphToolbar.__init__(self, canvas)

        if matplotlib.__version__ >= '3.3.0':
            self.init_toolbar()
        self.figure = figure
        self.datacursor = DataCursor(self.figure, self)
        self.lineeditor = LineEditor(self.figure)
        self.timeline = Timeline(self.figure)
        self.pan_action = Pan(self.figure)
        self.dock = GDock(self.figure)

        self.actions = {'datatip': self.datacursor,
                        'edit': self.lineeditor,
                        'pan/zoom': self.pan_action,
                        'timeline': self.timeline}

        self.canvas.mpl_connect('pick_event', self.OnPick)
        self.canvas.mpl_connect('motion_notify_event', self.OnMove)
        self.canvas.mpl_connect('button_press_event', self.OnPressed)
        self.canvas.mpl_connect('button_release_event', self.OnReleased)
        self.canvas.mpl_connect('scroll_event', self.OnScroll)
        self.canvas.mpl_connect('key_press_event', self.OnKeyPressed)
        # clear the view history
        wx.CallAfter(self._nav_stack.clear)

        self.linestyle_ids = {}
        self.marker_ids = {}
        self.drawstyle_ids = {}

    def GetMenu(self, axes):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'GetMenu'):
            return [], ""
        return action.GetMenu(axes), self.mode

    def key_down(self, event):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'key_down'):
            return
        action.key_down(event)

    def ProcessCommand(self, cmd, axes):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'ProcessCommand'):
            return
        action.ProcessCommand(cmd, axes)

    def OnPick(self, event):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'pick'):
            return
        action.pick(event)

    def OnKeyPressed(self, event):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'key_pressed'):
            return
        action.key_pressed(event)

    def _set_picker_all(self):
        for g in self.figure.get_axes():
            for l in g.lines:
                if l.get_picker() is None:
                    l.set_picker(5)

    def OnPressed(self, event):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'mouse_pressed'):
            if not self.mode:
                self.dock.mouse_pressed(event)
            return
        # some lines may be added
        self._set_picker_all()
        if action.mouse_pressed(event):
            self.canvas.draw()

    def OnReleased(self, event):

        action = self.actions.get(self.mode, None)
        if action and hasattr(action, 'mouse_released'):
            action.mouse_released(event)

        self.dock.mouse_released(event)
        if event.button == matplotlib.backend_bases.MouseButton.RIGHT:
            self.OnContextMenu(event)
            return

        axes = [a for a in self.figure.get_axes()
                if a.in_axes(event)]
        if axes:
            self.figure.sca(axes[0])

    def OnContextMenu(self, event):
        axes = [a for a in self.figure.get_axes()
                if a.in_axes(event)]
        if not axes:
            return

        menu = wx.Menu()
        # menu for current mode
        menus, name = self.GetMenu(axes)
        if len(menus) > 0:
            menu_mode = build_menu_from_list(menus)
            menu.AppendSubMenu(menu_mode, name.capitalize())
            menu.AppendSeparator()
        scale_menu = wx.Menu()
        scale_menu.Append(self.ID_AUTO_SCALE_XY, "Auto scale")
        scale_menu.AppendSeparator()
        scale_menu.Append(self.ID_AUTO_SCALE_X, "Auto scale x-axis")
        scale_menu.Append(self.ID_AUTO_SCALE_Y, "Auto scale y-axis")
        menu.AppendSubMenu(scale_menu, "Auto scale")
        menu.AppendSeparator()

        menu.Append(self.ID_LINE_STYLE_LINE, "Line")
        menu.Append(self.ID_LINE_STYLE_DOT, "Dot")
        menu.Append(self.ID_LINE_STYLE_LINE_DOT, "Line+Dot")

        style_menu = wx.Menu()
        for k, v in matplotlib.lines.Line2D.lineStyles.items():
            if k and isinstance(k, str) and not k.isspace():
                if k not in self.linestyle_ids:
                    self.linestyle_ids[k] = wx.NewIdRef()
                v = v.replace('_draw_', '')
                v = v.replace('_', ' ')
                style_menu.Append(self.linestyle_ids[k], v)

        menu.AppendSeparator()
        item = menu.AppendSubMenu(style_menu, "Line style")

        if wx.Platform != '__WXMAC__':
            item.SetBitmap(svg_to_bitmap(line_style_svg, win=self))

        marker_menu = wx.Menu()
        for k, v in matplotlib.lines.Line2D.markers.items():
            if k and isinstance(k, str) and not k.isspace():
                if k not in self.marker_ids:
                    self.marker_ids[k] = wx.NewIdRef()
                marker_menu.Append(self.marker_ids[k], k)
        menu.AppendSubMenu(marker_menu, "Marker style")

        drawstyle_menu = wx.Menu()
        for k, v in matplotlib.lines.Line2D.drawStyles.items():
            if k and isinstance(k, str) and not k.isspace():
                if k not in self.drawstyle_ids:
                    self.drawstyle_ids[k] = wx.NewIdRef()
                drawstyle_menu.Append(self.drawstyle_ids[k], k)
        menu.AppendSubMenu(drawstyle_menu, "Draw style")

        menu.AppendSeparator()
        item = menu.Append(self.ID_SPLIT_VERT_SHARE_XAXIS,
                           "Split vertically with shared x-axis")
        if wx.Platform != '__WXMAC__':
            item.SetBitmap(svg_to_bitmap(split_vert_svg, win=self))
        split_vert_menu = wx.Menu()
        split_vert_menu.Append(self.ID_SPLIT_VERT_SHARE_XAXIS, "Share x-axis")
        split_vert_menu.Append(self.ID_SPLIT_VERT_SHARE_YAXIS, "Share y-axis")
        split_vert_menu.Append(self.ID_SPLIT_VERT_SHARE_XYAXIS, "Share x/y-axis")
        split_vert_menu.Append(self.ID_SPLIT_VERT, "Share no axis")
        menu.AppendSubMenu(split_vert_menu, "Split vertically")
        split_horz_menu = wx.Menu()
        split_horz_menu.Append(self.ID_SPLIT_HORZ_SHARE_XAXIS, "Share x-axis")
        split_horz_menu.Append(self.ID_SPLIT_HORZ_SHARE_YAXIS, "Share y-axis")
        split_horz_menu.Append(self.ID_SPLIT_HORZ_SHARE_XYAXIS, "Share x/y-axis")
        split_horz_menu.Append(self.ID_SPLIT_HORZ, "Share horizontally")
        menu.AppendSubMenu(split_horz_menu, "Split horizontally")
        menu.AppendSeparator()

        item = menu.Append(self.ID_DELETE_SUBPLOT, "Delete plot")
        if wx.Platform != '__WXMAC__':
            item.SetBitmap(svg_to_bitmap(delete_svg, win=self))
        menu.Append(self.ID_DELETE_LINES, "Delete all lines")
        menu.AppendSeparator()
        item = menu.AppendCheckItem(self.ID_FLIP_Y_AXIS, "Flip y axis")
        item.Check(all([ax.yaxis.get_inverted() for ax in axes]))
        item = menu.AppendCheckItem(self.ID_FLIP_X_AXIS, "Flip x axis")
        item.Check(all([ax.xaxis.get_inverted() for ax in axes]))

        menu.AppendSeparator()
        menu.Append(self.ID_COPY_SUBPLOT, "Copy to clipboard")

        def _set_linestyle(ls=None, ms=None, ds=None):
            for ax in axes:
                for l in ax.lines:
                    if ls is not None:
                        l.set_linestyle(ls)
                    if ms is not None:
                        l.set_marker(ms)
                    if ds is not None:
                        l.set_drawstyle(ds)
                if ax.get_legend():
                    # update the line/marker on the legend
                    ax.legend()

        cmd = self.GetPopupMenuSelectionFromUser(menu)
        if cmd == wx.ID_NONE:
            return
        if cmd == self.ID_LINE_STYLE_LINE:
            _set_linestyle('-', '')
        elif cmd == self.ID_LINE_STYLE_DOT:
            _set_linestyle('', '.')
        elif cmd == self.ID_LINE_STYLE_LINE_DOT:
            _set_linestyle('-', '.')
        elif cmd in self.linestyle_ids.values():
            style = list(self.linestyle_ids.keys())[list(self.linestyle_ids.values()).index(cmd)]
            _set_linestyle(ls=style)
        elif cmd in self.marker_ids.values():
            marker = list(self.marker_ids.keys())[list(self.marker_ids.values()).index(cmd)]
            _set_linestyle(ms=marker)
        elif cmd in self.drawstyle_ids.values():
            style = list(self.drawstyle_ids.keys())[list(self.drawstyle_ids.values()).index(cmd)]
            _set_linestyle(ds=style)
        elif cmd in [self.ID_SPLIT_VERT, self.ID_SPLIT_VERT_SHARE_XAXIS,
                     self.ID_SPLIT_VERT_SHARE_YAXIS, self.ID_SPLIT_VERT_SHARE_XYAXIS,
                     self.ID_SPLIT_HORZ, self.ID_SPLIT_HORZ_SHARE_XAXIS,
                     self.ID_SPLIT_HORZ_SHARE_YAXIS, self.ID_SPLIT_HORZ_SHARE_XYAXIS]:
            vert = cmd in [self.ID_SPLIT_VERT, self.ID_SPLIT_VERT_SHARE_XAXIS,
                           self.ID_SPLIT_VERT_SHARE_YAXIS, self.ID_SPLIT_VERT_SHARE_XYAXIS]
            sharex = cmd in [self.ID_SPLIT_VERT_SHARE_XAXIS, self.ID_SPLIT_VERT_SHARE_XYAXIS,
                             self.ID_SPLIT_HORZ_SHARE_XAXIS, self.ID_SPLIT_HORZ_SHARE_XYAXIS]
            sharey = cmd in [self.ID_SPLIT_VERT_SHARE_YAXIS, self.ID_SPLIT_VERT_SHARE_XYAXIS,
                             self.ID_SPLIT_HORZ_SHARE_YAXIS, self.ID_SPLIT_HORZ_SHARE_XYAXIS]
            ax = add_subplot(axes[0], vert=vert, sharex=sharex, sharey=sharey)
            if any(line.get_visible() for line in axes[0].get_xgridlines() + axes[0].get_ygridlines()):
                ax.grid(True)
            self._nav_stack.clear()
        elif cmd == self.ID_DELETE_SUBPLOT:
            for ax in axes:
                del_subplot(ax)
            self._nav_stack.clear()
        elif cmd == self.ID_DELETE_LINES:
            for ax in axes:
                grid_on = any(line.get_visible() for line in ax.get_xgridlines() + ax.get_ygridlines())
                ax.cla()
                if grid_on:
                    ax.grid(True)
            self._nav_stack.clear()
        elif cmd == self.ID_FLIP_Y_AXIS:
            for ax in axes:
                ax.invert_yaxis()
        elif cmd == self.ID_FLIP_X_AXIS:
            for ax in axes:
                ax.invert_xaxis()
        elif cmd in [self.ID_AUTO_SCALE_XY, self.ID_AUTO_SCALE_X, self.ID_AUTO_SCALE_Y]:
            if cmd == self.ID_AUTO_SCALE_X:
                self.do_auto_scale(axes, 'x')
            elif cmd == self.ID_AUTO_SCALE_Y:
                self.do_auto_scale(axes, 'y')
            else:
                self.do_auto_scale(axes)
        elif cmd == self.ID_COPY_SUBPLOT:
            bb = []
            for ax in axes:
                bbox = ax.get_tightbbox()
                if bbox.width > 0 and bbox.height > 0:
                    bb.append(bbox)
            if bb:
                buf = np.copy(self.figure.canvas.buffer_rgba())
                bbox = mtransforms.Bbox.union(bb)
                pt = bbox.get_points()
                h, w, _ = buf.shape
                buf2 = np.copy(buf[h-int(pt[1, 1]):h-int(pt[0,1])+1, int(pt[0,0]):int(pt[1,0]+0.5)+1, :])
                h, w, _ = buf2.shape
                bitmap = wx.Bitmap.FromBufferRGBA(w, h, buf2)
                bitmap.SetScaleFactor(self.canvas.device_pixel_ratio)
                bmp_obj = wx.BitmapDataObject()
                bmp_obj.SetBitmap(bitmap)
                if not wx.TheClipboard.IsOpened():
                    open_success = wx.TheClipboard.Open()
                    if open_success:
                        wx.TheClipboard.SetData(bmp_obj)
                        wx.TheClipboard.Flush()
                        wx.TheClipboard.Close()
        else:
            self.ProcessCommand(cmd, axes)

    def OnMove(self, event):
        action = self.actions.get(self.mode, None)
        if action is None or not hasattr(action, 'mouse_move'):
            if not self.mode:
                self.dock.mouse_move(event)
            return
        if action.mouse_move(event):
            self.canvas.draw()
    def OnScroll(self, event):
        self.do_zoom(event)

    def OnZoomFun(self, event):
        # get the current x and y limits
        if not self.GetToolToggled(self.wx_ids['Zoom']):
            return
        self.do_zoom(event)

    def do_zoom(self, event):
        if self._nav_stack() is None:
            self.push_current()

        axes = [a for a in self.figure.get_axes()
                if a.in_axes(event)]

        yzoom_key = xzoom_key = True
        if wx.GetKeyState(wx.WXK_CONTROL_X):
            yzoom_key = False
        elif wx.GetKeyState(wx.WXK_CONTROL_Y):
            xzoom_key = False
        xzoom = yzoom = xzoom_key, yzoom_key
        xdata, ydata = event.xdata, event.ydata
        axes = [[a, xzoom, yzoom, xdata, ydata] for a in self.figure.get_axes()
                if a.in_axes(event)]
        if not axes:
            axes = []
            for ax in self.figure.get_axes():
                x,y = event.x, event.y
                xAxes, yAxes = ax.transAxes.inverted().transform([x, y])
                if -0.1 < xAxes < 0:
                    xzoom = False
                if -0.1 < yAxes < 0:
                    yzoom = False
                xdata, ydata = ax.transData.inverted().transform([x, y])
                if not yzoom or (not xzoom and -0.05 < yAxes < 1):
                    axes.append([ax, xzoom, yzoom, xdata, ydata])
                xzoom = yzoom = xzoom_key, yzoom_key
            if not axes:
                return

        base_scale = 2.0
        if event.button == 'up':
            # deal with zoom in
            scale_factor = 1.0 / base_scale
        elif event.button == 'down':
            # deal with zoom out
            scale_factor = base_scale
        else:
            # deal with something that should never happen
            scale_factor = 1.0

        for ax, xzoom, yzoom, xdata, ydata in axes:
            if xzoom:
                cur_xlim = ax.get_xlim()
                new_width = abs(cur_xlim[1] - cur_xlim[0]) * scale_factor
                relx = abs(cur_xlim[1] - xdata) / abs(cur_xlim[1] - cur_xlim[0])
                if new_width * (1 - relx) > 0:
                    if not ax.xaxis.get_inverted():
                        ax.set_xlim([xdata - new_width * (1 - relx),
                                     xdata + new_width * (relx)])
                    else:
                        ax.set_xlim([xdata + new_width * (1-relx),
                                     xdata - new_width * relx])
            if yzoom:
                cur_ylim = ax.get_ylim()
                new_height = abs(cur_ylim[1] - cur_ylim[0]) * scale_factor
                rely = abs(cur_ylim[1] - ydata) / abs(cur_ylim[1] - cur_ylim[0])
                if new_height * (1 - rely) > 0:
                    if not ax.yaxis.get_inverted():
                        ax.set_ylim([ydata - new_height * (1 - rely),
                                     ydata + new_height * rely])
                    else:
                        ax.set_ylim([ydata + new_height * (1-rely),
                                     ydata - new_height * rely])

        self.canvas.draw()

    def init_toolbar_empty(self):
        # deprecated in 3.3.0
        pass
    def init_toolbar(self):
        toolitems = (
            ('New', 'New figure', new_page_svg, None, 'OnNewFigure'),
            (None, None, None, None, None),
            ('Home', 'Reset original view', home_svg, None, 'home'),
            ('Back', 'Back to  previous view', backward_svg, backward_gray_svg, 'OnBack'),
            ('Forward', 'Forward to next view', forward_svg, forward_gray_svg, 'OnForward'),
            (None, None, None, None, None),
            ('Pan', 'Pan axes with left mouse, zoom with right', pan_svg, None,
             'pan'),
            ('Zoom', 'Zoom to rectangle', zoom_svg, None, 'zoom'),
            ('Datatip', 'Show the data tip', note_svg, None, 'datatip'),
            (None, None, None, None, None),
            ('Save', 'Save the figure', save_svg, None, 'save_figure'),
            ('Copy', 'Copy to clipboard', copy_svg, None, 'copy_figure'),
            (None, None, None, None, None),
            ('Edit', 'Edit curve', edit_svg, None, 'edit_figure'),
            (None, None, None, None, None),
            ('Timeline', 'Timeline', timeline_svg, None, 'timeline_figure'),
            #(None, None, None, "stretch"),
            #(None, None, None, None),
            #('Print', 'Print the figure', print_xpm, 'print_figure'),
        )

        self._parent = self.canvas.GetParent()
        self.ClearTools()
        self.wx_ids = {}
        self.SetToolBitmapSize((16, 16))
        for (text, tooltip_text, img, img_gray, callback) in toolitems:
            if text is None:
                if callback == "stretch":
                    self.AddStretchSpacer()
                else:
                    self.AddSeparator()
                continue
            self.wx_ids[text] = wx.NewIdRef()
            image = svg_to_bitmap(img, win=self)
            image_gray = wx.NullBitmap
            if img_gray:
                image_gray = svg_to_bitmap(img_gray, win=self)
            if text in ['Pan', 'Zoom', 'Datatip', 'Edit', 'Timeline']:
                self.AddCheckTool(self.wx_ids[text],
                                  text,
                                  image,
                                  disabled_bitmap=image_gray,
                                  short_help_string=text,
                                  long_help_string=tooltip_text)
            else:
                self.AddTool(self.wx_ids[text], text,
                             image,
                             disabled_bitmap=image_gray,
                             kind=wx.ITEM_NORMAL, short_help_string=tooltip_text)
            self.Bind(wx.EVT_TOOL,
                      getattr(self, callback),
                      id=self.wx_ids[text])
        self.Realize()

    def OnNewFigure(self, evt):
        plt.figure()

    def do_auto_scale(self, axes, axis='both'):
        for ax in axes:
            ax.autoscale(axis=axis)
        self.figure.canvas.draw_idle()

    def copy_figure(self, evt):
        # self.canvas.Copy_to_Clipboard(event=evt)
        bmp_obj = wx.BitmapDataObject()
        bmp_obj.SetBitmap(self.canvas.bitmap)

        if not wx.TheClipboard.IsOpened():
            open_success = wx.TheClipboard.Open()
            if open_success:
                wx.TheClipboard.SetData(bmp_obj)
                wx.TheClipboard.Flush()
                wx.TheClipboard.Close()

    def print_figure(self, evt):
        self.canvas.Printer_Print(event=evt)

    def set_mode(self, mode):
        if mode != 'datatip':
            self.ToggleTool(self.wx_ids['Datatip'], False)
        if mode != 'edit':
            self.ToggleTool(self.wx_ids['Edit'], False)
        if mode != 'pan':
            self.ToggleTool(self.wx_ids['Pan'], False)
        if mode != 'zoom':
            self.ToggleTool(self.wx_ids['Zoom'], False)
        if mode != 'timeline':
            self.ToggleTool(self.wx_ids['Timeline'], False)

        action = self.actions.get(self.mode, None)
        if action is not  None and  hasattr(action, 'deactivated'):
            action.deactivated()

        if mode in ['pan', 'zoom']:
            # these mode handled by the base class
            return

        self.mode = mode

        action = self.actions.get(self.mode, None)
        if action is not None and hasattr(action, 'activated'):
            action.activated()

    def zoom(self, *args):
        """activate the zoom mode"""
        self.set_mode('zoom')
        super().zoom(*args)

    def pan(self, *args):
        """activated the pan mode"""
        self.set_mode('pan')
        super().pan(*args)

    def OnBack(self, *args):
        super().back(*args)

    def back(self, *args):
        action = self.actions.get(self.mode, None)
        if action is not None:
            return
        super().back(*args)

    def OnForward(self, *args):
        super().forward(*args)

    def forward(self, *args):
        action = self.actions.get(self.mode, None)
        if action is not None:
            return
        super().forward(*args)

    def datatip(self, evt):
        """activate the datatip mode"""
        # disable the pan/zoom mode
        self._active = None
        if hasattr(self, '_idPress'):
            self._idPress = self.canvas.mpl_disconnect(self._idPress)

        if hasattr(self, '_idRelease'):
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
        self.canvas.widgetlock.release(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self._active)

        self._set_picker_all()
        if self.mode == 'datatip':
            self.set_mode('')
        else:
            self.set_mode("datatip")
        self.set_message(self.mode)
        self.datacursor.set_enable(evt.GetInt())

    def edit_figure(self, evt):
        """activate the curve editing  mode"""
        # disable the pan/zoom mode
        self.set_message(self.mode)

        self._active = None
        if hasattr(self, '_idPress'):
            self._idPress = self.canvas.mpl_disconnect(self._idPress)

        if hasattr(self, '_idRelease'):
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
        self.canvas.widgetlock.release(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self._active)

        self._set_picker_all()
        if self.mode == "edit":
            self.set_mode("")
        else:
            self.set_mode("edit")
        self.set_message(self.mode)

    def timeline_figure(self, evt):
        """activate the curve timeline mode"""
        # disable the pan/zoom mode
        self.set_message(self.mode)

        self._active = None
        if hasattr(self, '_idPress'):
            self._idPress = self.canvas.mpl_disconnect(self._idPress)

        if hasattr(self, '_idRelease'):
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
        self.canvas.widgetlock.release(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self._active)

        self._set_picker_all()
        if self.mode == "timeline":
            self.set_mode("")
        else:
            self.set_mode("timeline")
        self.set_message(self.mode)

    def set_message(self, s):
        """show the status message"""
        dp.send(signal='frame.show_status_text', text=s, index=1, width=160)

class MPLPanel(wx.Panel):
    frame = None
    kwargs = {}

    def __init__(self, parent, title=None, num=-1, thisFig=None):
        # set the size to positive value, otherwise the toolbar will assert
        # wxpython/ext/wxWidgets/src/gtk/bitmap.cpp(539): assert ""width > 0 &&
        # height > 0"" failed in Create(): invalid bitmap size
        wx.Panel.__init__(self, parent, size=(100, 100))
        # initialize matplotlib stuff
        self.figure = thisFig
        if not self.figure:
            self.figure = Figure(None, None)
        self.canvas = FigureCanvas(self, -1, self.figure)
        # since matplotlib 3.2, it does not allow canvas size to become smaller
        # than MinSize in wx backend. So the canvas size (e.g., (640, 480))may
        # be large than the window size.
        self.canvas.SetMinSize((2, 2))
        #self.canvas.manager = self

        self.num = num
        if title is None:
            title = 'Figure %d' % self.num
        self.title = title
        self.isdestory = False
        szAll = wx.BoxSizer(wx.VERTICAL)

        self.figure.set_label(title)
        self.toolbar = Toolbar(self.canvas, self.figure)
        szAll.Add(self.toolbar, 0, wx.EXPAND)
        szAll.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)

        self.toolbar.update()
        # set the toolbar tool size again, otherwise the separator is not
        # aligned correctly on macOS.
        self.toolbar.SetToolBitmapSize((16, 16))
        self.SetSizer(szAll)


        self.figmgr = FigureManagerWx(self.canvas, num, self)
        self.Bind(wx.EVT_CLOSE, self._onClose)

        self.canvas.mpl_connect('button_press_event', self._onClick)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)

    def GetToolBar(self):
        """Override wxFrame::GetToolBar as we don't have managed toolbar"""
        return self.toolbar

    def _onClick(self, event):
        if event.dblclick:
            self.toolbar.home()

    def OnKeyDown(self, evt):
        self.toolbar.key_down(evt)

    def close_event(self):
        event = CloseEvent('close_event',  self.canvas, guiEvent=None)
        self.canvas.callbacks.process('close_event', event)

    def _onClose(self, evt):
        self.close_event()
        self.canvas.stop_event_loop()
        Gcf.destroy(self.num)

    def destroy(self, *args):
        if self.isdestory is False:
            dp.send('frame.delete_panel', panel=self)
            wx.WakeUpIdle()

    def Destroy(self, *args, **kwargs):
        self.isdestory = True
        self.close_event()
        self.canvas.stop_event_loop()
        return super().Destroy(*args, **kwargs)

    def GetTitle(self):
        """return the figure title"""
        return self.title

    def SetTitle(self, title):
        """set the figure title"""
        if title == self.title:
            return
        self.title = title

    def set_window_title(self, title):
        self.SetTitle(title)

    @classmethod
    def SetActive(cls, pane):
        """set the active figure"""
        if pane and isinstance(pane, cls):
            Gcf.set_active(pane)

    @classmethod
    def AddFigure(cls, title=None, num=None, thisFig=None):
        fig = cls(cls.frame, title=title, num=num, thisFig=thisFig)
        return fig

    @classmethod
    def Initialize(cls, frame, **kwargs):
        if cls.frame is not None:
            return
        cls.frame = frame
        cls.kwargs = kwargs

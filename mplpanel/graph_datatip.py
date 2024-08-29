import datetime
import math
import wx
import wx.py.dispatcher as dp
import matplotlib
import numpy as np
import pandas as pd
import propgrid as pg
from propgrid import prop
from .graph_common import GraphObject
from .utility import send_data_to_shell, _dict

class TextAnt:
    text_template = 'x: %0.2f\ny: %0.2f'
    def __init__(self, annotation=None, line=None, index=-1):
        self.annotation = annotation
        self.line = line
        self.index = index
        self.config = _dict(pos_xy=(-1, 1), fmt_number='.2f',
                            fmt_datatime='%Y-%m-%d %H:%M:%S',
                            clr_edge='#8E8E93',
                            clr_face='#ffffff',
                            clr_alpha=50,
                            clr_edge_selected='#8E8E93',
                            clr_face_selected='#FF9500',
                            clr_alpha_selected=50)

        self.is_active = False

    def __call__(self):
        return self.annotation

    def set_active(self, active):
        if active == self.is_active:
            return

        self.is_active = active
        self.update_config()

    def remove(self):
        try:
            # the call may fail. For example,
            # 1) create a figure and plot some curve
            # 2) create a datatip
            # 3) call clf() to clear the figure, the datatip will be
            #    cleared, but we will not know
            self().remove()
        except:
            pass

    def contains(self, mx, my):
        box = self().get_bbox_patch().get_extents()
        return box.contains(mx, my)

    def get_data(self):
        if self.line is None or self.index == -1:
            return None, None
        x, y = self.line.get_data(orig=False)
        return x[self.index], y[self.index]

    def get_orig_data(self):
        if self.line is None or self.index == -1:
            return None, None
        x, y = self.line.get_data()
        return x[self.index], y[self.index]

    def set_index(self, index):
        self.index = index
        self.update()
        self.update_position()
        self().set_visible(True)

    def set_position(self, x, y):
        # x/y is 0/1/-1
        bbox = self().get_bbox_patch()
        w, h = bbox.get_width(), bbox.get_height()
        self().xyann = (x*w - w/2 , y*h-h/2)
        self.config['pos_xy'] = (x, y)

    def update_position(self):
        x, y = self.get_position()
        wx.CallAfter(self.set_position, x, y)

    def get_position(self):
        return self.config['pos_xy']

    def update(self):
        x, y = self.get_orig_data()
        self().set_text(self.xy_to_annotation(x, y))
        self().xy = self.get_data()

    def xy_to_annotation(self, x, y, fmt=None):
        if x is None or y is None:
            return ""
        if fmt is None:
            fmt = self.config
        x_str = ""
        y_str = ""
        if isinstance(x, datetime.date):
            x_str = f'x: {x.strftime(fmt["fmt_datetime"])}'
        else:
            x_str= f'x: {x:{fmt["fmt_number"]}}'
        if isinstance(y, datetime.date):
            y_str = f'y: {y.strftime(fmt["fmt_datetime"])}'
        else:
            y_str= f'y: {y:{fmt["fmt_number"]}}'
        return '\n'.join([x_str, y_str])

    def update_config(self, config=None):
        if config is None:
            config = self.config
        self.config = config

        if self.is_active:
            clr_edge = config['clr_edge_selected']
            clr_face = config['clr_face_selected']
            alpha = config['clr_alpha_selected']
        else:
            clr_edge = config['clr_edge']
            clr_face = config['clr_face']
            alpha = config['clr_alpha']

        self().get_bbox_patch().set_edgecolor(clr_edge)
        self().get_bbox_patch().set_facecolor(clr_face)
        self().get_bbox_patch().set_alpha(alpha/100)

        self.update()
        self.update_position()

    @classmethod
    def create(cls, ax):
        """create the annotation"""
        ant = ax.annotate(cls.text_template,
                          xy=(0, 0),
                          xytext=(0, 0),
                          textcoords='offset pixels',
                          ha='left',
                          va='bottom',
                          bbox={'boxstyle': 'round,pad=0.5',
                                'fc': '#FF9500',
                                'alpha': 1},
                          arrowprops={'arrowstyle': '->',
                                      'connectionstyle': 'arc3,rad=0'})
        ant.set_visible(False)
        ant.set_in_layout(False)
        annotation = cls(annotation=ant)
        return annotation

class DataCursor(GraphObject):
    MAX_DISTANCE = 5

    ID_DELETE_DATATIP = wx.NewIdRef()
    ID_CLEAR_DATATIP = wx.NewIdRef()
    ID_EXPORT_DATATIP = wx.NewIdRef()
    ID_SETTING = wx.NewIdRef()

    def __init__(self, figure, win):
        super().__init__(figure)
        self.annotations = []
        self.enable = False
        self.active = None
        self.mx, self.my = None, None
        self.window = win
        self.settings = [
                #[indent, type, name, label, value, fmt]
                prop.PropChoice({
                    (-1, 1): 'top left',
                    (0, 1): 'top',
                    (1, 1): 'top right',
                    (1, 0): 'right',
                    (1, -1): 'bottom right',
                    (0, -1): 'bottom',
                    (-1, -1): 'bottom left',
                    (-1, 0): 'left',
                    }, 'Position').Name('pos_xy').Value((-1, 1)),
                prop.PropSeparator('Format').Name('sep_fmt'),
                prop.PropText('Number').Value('.2f').Name('fmt_number').Indent(1),
                prop.PropText('Datetime').Value('%Y-%m-%d %H:%M:%S').Name('fmt_datetime').Indent(1),
                prop.PropSeparator('Color').Name('sep_color'),
                prop.PropColor('Edge').Value('#8E8E93').Name('clr_edge').Indent(1),
                prop.PropColor('Face').Value('#ffffff').Name('clr_face').Indent(1),
                prop.PropSpin(0, 100, 'Opacity').Name('clr_alpha').Value(50).Indent(1),
                prop.PropSeparator('Selected color').Name('sep_clr_selected'),
                prop.PropColor('Edge').Value('#8E8E93').Name('clr_edge_selected').Indent(1),
                prop.PropColor('Face').Value('#FF9500').Name('clr_face_selected').Indent(1),
                prop.PropSpin(0, 100, 'Opacity').Name('clr_alpha_selected').Value(50).Indent(1),
                ]
        self.LoadConfig()
        self.cx, self.cy = None, None

    def FindAntIndex(self, ant):
        if ant not in self.annotations:
            return -1
        return self.annotations.index(ant)

    def OnRemovingLine(self, figure, lines):
        if not super().OnRemovingLine(figure, lines):
            return False
        for idx in range(len(self.annotations)-1, -1, -1):
            # start from the last annotation, as it may be deleted and change
            # the list size
            if self.annotations[idx].line in lines:
                if self.active == self.annotations[idx]:
                    self.active = None
                self.annotations[idx].remove()
                del self.annotations[idx]
        return True

    def pick(self, event):
        # pick event will not always be triggered for twinx, see following link
        # for detail
        # https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.twinx.html
        return

    def annotation_line(self, line, mx, my):
        # add annotation to a line at location (mx, my)
        if not self.enable:
            return False
        if self.get_annotation(mx, my) is not None:
            # click in the box of existing annotation, ignore it
            return False

        # find the closest point on the line
        # mouse position in data coordinate
        dis = self.distance_to_line(line, mx, my)
        if dis > self.MAX_DISTANCE:
            return False

        if self.active and self.active().get_visible():
            # Check whether the axes of active annotation is same as line,
            # which may happen in a figure with subplots. If not, create one
            # with the axes of line
            if self.active().axes != line.axes:
                self.set_active(None)
        if self.active is None:
            self.create_annotation(line)
        idx = self.FindAntIndex(self.active)
        if idx == -1:
            return False
        # update the annotation line, as it may be moved
        self.annotations[idx].line = line

        # set the annotation
        inv = line.axes.transData.inverted()
        dmx, dmy = inv.transform((mx, my))
        didx, dx, dy = self.get_closest(line, dmx, dmy)
        self.active.set_index(didx)
        self.figure.canvas.draw()
        return True

    def keyboard_move(self, left, step=1):
        if not self.active:
            return
        idx = self.FindAntIndex(self.active)
        if idx == -1:
            return
        line = self.annotations[idx].line
        x, y = line.get_xdata(orig=False), line.get_ydata(orig=False)
        xc, yc = self.active.get_data()
        idx = (np.square(x - xc)).argmin()
        idx_new = idx
        if left:
            idx_new -= step
        else:
            idx_new += step
        idx_new = min(len(x)-1, idx_new)
        idx_new = max(0, idx_new)
        if idx == idx_new:
            return
        xn, yn = x[idx_new], y[idx_new]
        if xn is not None:
            self.active.set_index(idx_new)

    def set_enable(self, enable):
        self.enable = enable
        if self.active:
            config = self.get_config()
            if enable:
                self.active().get_bbox_patch().set_facecolor(config['clr_face_selected'])
            else:
                self.active().get_bbox_patch().set_facecolor(config['clr_face'])

    def mouse_move(self, event):
        """move the annotation position"""
        if event.button != matplotlib.backend_bases.MouseButton.LEFT:
            return False
        # return if no active annotation or the mouse is not pressed
        if self.mx is None or self.my is None or self.active is None or \
                self.cx is None or self.cy is None:
            return False
        # re-position the active annotation based on the mouse movement
        x, y = event.x, event.y
        bbox = self.active().get_bbox_patch()
        w, h = bbox.get_width(), bbox.get_height()
        dx = x - self.mx
        dy = y - self.my
        dis = math.sqrt(dx**2 + dy**2)
        if dis > 40:
            (px, py) = (0, 0)
            px = int(dx / 40)
            py = int(dy / 40)

            cx, cy = self.cx, self.cy
            cx += px
            cy += py
            cx = max(min(cx, 1), -1)
            cy = max(min(cy, 1), -1)
            self.active.set_position(cx, cy)
            return True
        return False

    def get_annotation(self, mx, my):
        for ant in self.annotations:
            if ant.contains(mx, my):
                return ant
        return None

    def OnUpdated(self, figure, axes):
        if not super().OnUpdated(figure, axes):
            return False
        # axes is updated, try to update all the datatip
        for ant in self.annotations:
            if ant.line.axes in axes:
                ant.update()

        self.figure.canvas.draw()
        return True

    def mouse_pressed(self, event):
        """
        select the active annotation which is closest to the mouse position
        """
        if event.button != matplotlib.backend_bases.MouseButton.LEFT:
            return False

        axes = [a for a in self.figure.get_axes()
                if a.in_axes(event)]
        line, dis = self.get_closest_line(axes, event.x, event.y)
        if line:
            if self.annotation_line(line, event.x, event.y):
                return True

        # just created the new annotation, do not move to others
        if self.active and (not self.active().get_visible()):
            return False
        # search the closest annotation
        x, y = event.x, event.y
        self.mx, self.my = x, y
        active = self.get_annotation(x, y)
        self.set_active(active)
        if self.active:
            self.cx, self.cy = self.active.get_position()
        # return True for the parent to redraw
        return True

    def mouse_released(self, event):
        """release the mouse"""
        self.mx, self.my = None, None

    def get_active(self):
        """retrieve the active annotation"""
        return self.active

    def set_active(self, ant):
        """set the active annotation"""
        if ant and self.FindAntIndex(ant) == -1:
            return False

        if self.active == ant:
            return True
        old_active = self.active
        self.active = ant
        if old_active:
            old_active.set_active(False)
        if self.active:
            self.active.set_active(True)
        self.figure.canvas.draw_idle()
        return True

    def get_annotations(self):
        """return all the annotations"""
        return [ant() for ant in self.annotations]

    def create_annotation(self, line):
        """create the annotation and set it active"""
        config = self.get_config()
        ant = TextAnt.create(line.axes)
        ant.line = line
        self.annotations.append(ant)
        ant.update_config(config)
        self.set_active(ant)

    def GetMenu(self, axes):
        active_in_axes = False
        if self.active and self.active().get_visible():
            idx = self.FindAntIndex(self.active)
            active_in_axes = self.annotations[idx].line.axes in axes
        ant_in_axes = any(ant.line.axes in axes for ant in self.annotations)
        cmd = [{'id': self.ID_DELETE_DATATIP, 'label': 'Delete current datatip',
                'enable': active_in_axes},
               {'id': self.ID_CLEAR_DATATIP, 'label': 'Delete all datatip',
                'enable': ant_in_axes},
               {'type': wx.ITEM_SEPARATOR},
               {'id': self.ID_EXPORT_DATATIP, 'label': 'Export datatip data...',
                'enable': ant_in_axes},
               {'type': wx.ITEM_SEPARATOR},
               {'id': self.ID_SETTING, 'label': 'Settings ...'},
               ]
        return cmd

    def key_down(self, event):
        keycode = event.GetKeyCode()
        step = 1
        if event.ShiftDown():
            step = 10
        if keycode == wx.WXK_LEFT:
            self.keyboard_move(True, step=step)
        elif keycode == wx.WXK_RIGHT:
            self.keyboard_move(False, step=step)
        else:
            event.Skip()

    def ProcessCommand(self, cmd, axes):
        """process the context menu command"""
        ant_in_axes = [ant.line.axes in axes for ant in self.annotations]
        active_in_axes = False
        if self.active:
            idx = self.FindAntIndex(self.active)
            active_in_axes = ant_in_axes[idx]

        if cmd == self.ID_DELETE_DATATIP:
            if not active_in_axes:
                return False
            idx = self.FindAntIndex(self.active)
            if idx == -1 or not ant_in_axes[idx]:
                return False
            self.active.remove()
            del self.annotations[idx]
            self.active = None
            return True
        elif cmd == self.ID_CLEAR_DATATIP:
            annotations = []
            for idx, ant in enumerate(self.annotations):
                if ant_in_axes[idx]:
                    ant.remove()
                else:
                    annotations.append(self.annotations[idx])
            self.annotations = annotations
            self.active = None
            return True
        elif cmd == self.ID_EXPORT_DATATIP:
            data = []
            for idx, ant in enumerate(self.annotations):
                if ant_in_axes[idx]:
                    xs, ys = ant.get_orig_data()
                    data.append((xs, ys))
            data = np.array(data)
            df = pd.DataFrame()
            df['x'] = data[:, 0]
            df['y'] = data[:, 1]
            send_data_to_shell('datatip_data', df)
            return True
        elif cmd == self.ID_SETTING:
            settings = [s.duplicate() for s in  self.settings]
            active = None
            if active_in_axes:
                active = self.active
            if active:
                for p in settings:
                    n = p.GetName()
                    if n in active.config:
                        p.SetValue(active.config[n], silent=True)

            dlg = DatatipSettingDlg(settings, active is not None,
                                    self.window.GetParent(),
                                    size=(600, 480))
            dlg.CenterOnParent()

            # this does not return until the dialog is closed.
            val = dlg.ShowModal()
            if val == wx.ID_OK:
                settings = dlg.get_settings()
                save_as_default = settings.get('save_as_default', False)
                apply_all = settings.get('apply_all', False)
                settings = settings['settings']
                if save_as_default:
                    self.SaveConfig(settings)
                if apply_all:
                    self.LoadConfig(settings)
                    config = self.get_config(settings)
                    for idx, ant in enumerate(self.annotations):
                        if ant_in_axes[idx]:
                            ant.update_config(config)
                elif active:
                    self.set_active(active)
                    active.update_config(self.get_config(settings))
                else:
                    self.LoadConfig(settings)

            dlg.Destroy()
        return False

    def activated(self):
        pass
    def deactivated(self):
        pass

    def get_config(self, settings=None):
        if settings is None:
            settings = self.settings
        if isinstance(settings, dict):
            return settings
        config = {p.GetName():p.GetValue() for p in settings if not p.IsSeparator()}
        return config

    def SaveConfig(self, settings):
        config = self.get_config(settings)
        dp.send('frame.set_config', group='graph_datatip', **config)

    def LoadConfig(self, config=None):
        if config is None:
            resp = dp.send('frame.get_config', group='graph_datatip')
            if resp and resp[0][1] is not None:
                config = resp[0][1]
        if not config:
            return
        for idx, p in enumerate(self.settings):
            n = p.GetName()
            if n in config:
                self.settings[idx].SetValue(config[n], True)


class DatatipSettingDlg(wx.Dialog):
    def __init__(self, settings, active, parent, title='Settings ...',
                 size=wx.DefaultSize, pos=wx.DefaultPosition,
                 style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER):
        wx.Dialog.__init__(self)
        self.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        self.Create(parent, title=title, pos=pos, size=size, style=style)

        self.settings = settings
        self.propgrid = pg.PropGrid(self)
        g = self.propgrid
        g.Draggable(False)

        for p in settings:
            g.Insert(p)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(g, 1, wx.EXPAND|wx.ALL, 1)

        self.cbApplyAll = wx.CheckBox(self, label="Apply settings to existing datatips in this figure")
        self.cbSaveAsDefaultCurrent = wx.CheckBox(self, label="Save settings as default for this figure")
        self.cbSaveAsDefaultCurrent.Show(active)
        self.cbSaveAsDefault = wx.CheckBox(self, label="Save settings as default for new figures")

        sizer.Add(self.cbApplyAll, 0, wx.EXPAND|wx.ALL, 5)
        sizer.Add(self.cbSaveAsDefaultCurrent, 0, wx.EXPAND|wx.ALL, 5)
        sizer.Add(self.cbSaveAsDefault, 0, wx.EXPAND|wx.ALL, 5)

        # ok/cancel button
        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        btnsizer.AddStretchSpacer(1)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.Add(btn, 0, wx.EXPAND | wx.ALL, 5)

        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.Add(btn, 0, wx.EXPAND | wx.ALL, 5)

        sizer.Add(btnsizer, 0, wx.ALL|wx.EXPAND, 5)

        self.SetSizer(sizer)

        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

    def OnContextMenu(self, event):
        # it is necessary, otherwise when right click on the dialog, the context
        # menu of the MatplotPanel will show; it may be due to some 'bug' in
        # CaptureMouse/ReleaseMouse (canvas is a panel that capture mouse)
        # and we also need to release the mouse before show the MatplotPanel
        # context menu (wchich will eventually show this dialog)
        pass

    def rgb2hex(self, clr):
        clr = np.sum(clr * 255 * [2**16, 2**8, 1], 1).astype(np.int32)
        return ["#{:06x}".format(c) for c in clr]

    def get_settings(self):
        settings = {}

        settings['apply_all'] = self.cbApplyAll.IsChecked()
        settings['save_as_default'] = self.cbSaveAsDefault.IsChecked()
        settings['save_as_default_cur'] = self.cbSaveAsDefaultCurrent.IsChecked()
        settings['settings'] = {}
        for i in range(0, len(self.settings)):
            p = self.settings[i]
            if p.IsSeparator():
                continue
            p.Activated(False)
            n = p.GetName()
            settings['settings'][n] = self.propgrid.Get(n).GetValue()
        return settings

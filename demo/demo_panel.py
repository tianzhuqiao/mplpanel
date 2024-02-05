import wx
import matplotlib
matplotlib.use('module://mplpanel.demo.demo_backend')

import wx.py.dispatcher as dp
from ..mplpanel.graph import MPLPanel, Gcf

class DemoPanel(MPLPanel):
    @classmethod
    def AddFigure(cls, title=None, num=None, thisFig=None):
        fig = super().AddFigure(title, num, thisFig)

        direction = cls.kwargs.get('direction', 'top')
        # set the minsize to be large enough to avoid some following assert; it
        # will not eliminate all as if a page is added to a notebook, the
        # minsize of notebook is not the max of all its children pages (check
        # frameplus.py).
        # wxpython/ext/wxWidgets/src/gtk/bitmap.cpp(539): assert ""width > 0 &&
        # height > 0"" failed in Create(): invalid bitmap size
        dp.send('frame.add_panel',
                panel=fig,
                direction=direction,
                title=fig.GetTitle(),
                target=Gcf.get_active(),
                minsize=(300, 300))
        return fig

    @classmethod
    def Initialize(cls, frame, **kwargs):
        super().Initialize(frame, **kwargs)
        dp.connect(cls.Uninitialize, 'frame.exiting')
        dp.connect(cls.SetActive, 'frame.activate_panel')

    @classmethod
    def Uninitialize(cls):
        """destroy the module"""
        Gcf.destroy_all()




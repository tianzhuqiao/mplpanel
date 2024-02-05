import ctypes
import wx
from .mainframe import MainFrame
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(True)
except:
    pass


class RunApp(wx.App):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        wx.App.__init__(self, redirect=False)

    def OnInit(self):
        wx.Log.SetActiveTarget(wx.LogStderr())

        self.SetAssertMode(wx.APP_ASSERT_DIALOG)

        frame = MainFrame(None, **self.kwargs)
        frame.Show(True)
        self.SetTopWindow(frame)
        self.frame = frame
        return True


def main():
    app = RunApp()
    app.MainLoop()


if __name__ == '__main__':
    main()

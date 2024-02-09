# mplpanel
**mplpanel** is a wx.Panel that makes it easy to use matplotlib plot in wxPython application.

1. Install
```bash
$ pip install mplpanel
```
2. Usage
``` python
# step 1: derive a class from MPLPanel
import matplotlib
matplotlib.use('module://path.to.demo_backend')
class DemoPanel(MPLPanel):
    ...

# step 2: create a backend, e.g,. to provide some helper functions
...
def new_figure_manager(num, *args, **kwargs):
    ...
    from .demo_panel import DemoPanel
    FigureClass = kwargs.pop('FigureClass', Figure)
    thisFig = FigureClass(*args, **kwargs)

    return DemoPanel.AddFigure('Figure %d' % num, num, thisFig)
...

# step 3: create a figure
...
import matplotlib.pyplot as plt

class MainFrame(wx.Frame):
    ...
    def __init__(self, parent, **kwargs):
        ...
        plt.figure()
...
```
Check the demo for details.

<img src="https://github.com/tianzhuqiao/mplpanel/blob/main/image/demo.png?raw=true"  width="600"></img>

"""define some utility functions"""
import os
import keyword
import pickle
from pathlib import Path
import wx
import wx.svg
import wx.py.dispatcher as dp

def svg_to_bitmap(svg, size=None, win=None):
    if size is None:
        if wx.Platform == '__WXMSW__':
            size = (24, 24)
        else:
            size = (16, 16)
    bmp = wx.svg.SVGimage.CreateFromBytes(str.encode(svg))
    bmp = bmp.ConvertToScaledBitmap(size, win)
    if win:
        bmp.SetScaleFactor(win.GetContentScaleFactor())
    return bmp

def build_menu_from_list(items, menu=None):
    # for each item in items
    # {'type': ITEM_SEPARATOR}
    # {'type': ITEM_NORMAL, 'id': , 'label': , 'enable':}
    # {'type': ITEM_CHECK, 'id': , 'label': , 'enable':, 'check'}
    # {'type': ITEM_RADIO, 'id': , 'label': , 'enable':, 'check'}
    # {'type': ITEM_DROPDOWN, 'label':, 'items': []]
    if menu is None:
        menu = wx.Menu()
    for m in items:
        mtype = m.get('type', wx.ITEM_NORMAL)
        if mtype == wx.ITEM_SEPARATOR:
            item = menu.AppendSeparator()
        elif mtype == wx.ITEM_DROPDOWN:
            child = build_menu_from_list(m['items'])
            menu.AppendSubMenu(child, m['label'])
        elif mtype == wx.ITEM_NORMAL:
            item = menu.Append(m['id'], m['label'])
            item.Enable(m.get('enable', True))
        elif mtype == wx.ITEM_CHECK:
            item = menu.AppendCheckItem(m['id'], m['label'])
            item.Check(m.get('check', True))
            item.Enable(m.get('enable', True))
        elif mtype == wx.ITEM_RADIO:
            item = menu.AppendRadioItem(m['id'], m['label'])
            item.Check(m.get('check', True))
            item.Enable(m.get('enable', True))
    return menu

def get_temp_file(filename):
    path = Path(os.path.join(wx.StandardPaths.Get().GetTempDir(), filename))
    return path.as_posix()

def send_data_to_shell(name, data):
    if not name.isidentifier():
        return False

    filename = get_temp_file('_data.pickle')

    with open(filename, 'wb') as fp:
        pickle.dump(data, fp)
    dp.send('shell.run',
            command=f'with open("{filename}", "rb") as fp:\n    {name} = pickle.load(fp)',
            prompt=False,
            verbose=False,
            history=False)
    dp.send('shell.run',
            command='',
            prompt=False,
            verbose=False,
            history=False)
    dp.send('shell.run',
            command=f'{name}',
            prompt=True,
            verbose=True,
            history=False)
    return True

def get_variable_name(text):
    def _get(text):
        # array[0] -> array0
        # a->b -> a_b
        # a.b -> a_b
        # [1] -> None
        name = text.replace('[', '').replace(']', '')
        name = name.replace('(', '').replace(')', '')
        name = name.replace('{', '').replace('}', '')
        name = name.replace('.', '_').replace('->', '_')
        if keyword.iskeyword(name):
            name = f'{name}_'
        if not name.isidentifier():
            return None
        return name
    if isinstance(text, str):
        text = [text]
    name = ""
    for t in reversed(text):
        name = t + name
        var = _get(name)
        if var:
            return var
    return "unknown"

class _dict(dict):
    """dict like object that exposes keys as attributes"""
    def __getattr__(self, key):
        ret = self.get(key, None)
        if ret is None or key.startswith("__"):
            raise AttributeError()
        return ret
    def __setattr__(self, key, value):
        self[key] = value
    def __getstate__(self):
        return self
    def __setstate__(self, d):
        self.update(d)
    def update(self, d=None, **kwargs):
        """update and return self -- the missing dict feature in python"""
        if d:
            super().update(d)
        if kwargs:
            super().update(kwargs)
        return self

    def copy(self):
        return _dict(dict(self).copy())

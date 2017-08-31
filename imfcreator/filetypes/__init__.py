import importlib
import os

dirname = os.path.dirname(__file__)
_plugins = [f[0:-3] for f
            in os.listdir(dirname)
            if os.path.isfile(os.path.join(dirname, f)) and f.lower().endswith("fileplugin.py")]


def init():
    for plugin in _plugins:
        try:
            importlib.import_module(__name__ + "." + plugin)
        except ImportError as e:
            print("adlib: failed to import {}: {}".format(plugin, e))

init()

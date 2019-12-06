import importlib
import os


def _init():
    """Initializes plugins."""
    dirname = os.path.dirname(__file__)
    plugins = [f[0:-3] for f
               in os.listdir(dirname)
               if os.path.isfile(os.path.join(dirname, f)) and f.lower().endswith("fileplugin.py")]
    for plugin in plugins:
        try:
            importlib.import_module(f"{__name__}.{plugin}")
        except ImportError as e:
            print(f"filetypes plugin: failed to import {plugin}: {e}")


_init()

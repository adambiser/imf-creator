import json
import os
import tkinter as tk


def _get_verify_dir(settings, name, default_path):
    path = settings.get(name, default_path)
    if path is not None and os.path.isdir(path):
        return path
    return default_path


class Settings:
    CONFIG_FILE = "config.json"

    def __init__(self):
        self.gamefolder = tk.StringVar(value=None)
        self.exportfolder = tk.StringVar(value=os.getcwd())
        self.repeatanimations = tk.BooleanVar(value=False)
        self.imagescale = tk.IntVar(value=0)
        self.saveimagefiletype = tk.StringVar(value="")
        self.saveanimationfiletype = tk.StringVar(value="")
        # self.load()

    def load(self):
        if os.path.exists(Settings.CONFIG_FILE):
            with open(Settings.CONFIG_FILE, "r") as f:
                self._fromdict(json.load(f))

    def save(self):
        with open(Settings.CONFIG_FILE, "w") as f:
            json.dump(self._todict(), f, indent=4, separators=(",", ": "))

    def _todict(self):
        settings = {
            "gamefolder": self.gamefolder.get(),
            "exportfolder": self.exportfolder.get(),
            "repeatanimations": self.repeatanimations.get(),
            "imagescale": self.imagescale.get(),
            'saveimagefiletype': self.saveimagefiletype.get(),
            'saveanimationfiletype': self.saveanimationfiletype.get(),
        }
        return settings

    def _fromdict(self, settings):
        # Be sure to use .set so that the value updates and
        # the variable reference doesn"t change.
        self.gamefolder.set(_get_verify_dir(settings, "gamefolder", None))
        self.exportfolder.set(_get_verify_dir(settings, "exportfolder", os.getcwd()))
        self.repeatanimations.set(settings.get("repeatanimations", False))
        self.imagescale.set(settings.get("imagescale", 0))
        self.saveimagefiletype.set(settings.get("saveimagefiletype", ""))
        self.saveanimationfiletype.set(settings.get("saveanimationfiletype", ""))

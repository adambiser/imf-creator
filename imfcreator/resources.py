import os
try:
    import Tix as tix
except ImportError:
    import tkinter.tix as tix


class Resources:
    PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")

    @classmethod
    def getimage(cls, filename):
        return tix.PhotoImage(file=os.path.join(Resources.PATH, filename))

"""**Resource Manager**

Provides access to resource files.
"""
import os
import tkinter.tix as tix

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")


def get_image(filename: str):
    return tix.PhotoImage(file=os.path.join(_PATH, filename))

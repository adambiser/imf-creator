#!/usr/bin/python3.7
# -*- coding: utf-8 -*-

import os
import shutil
import sys

import imfcreator.instruments as _instruments
from imfcreator.plugins import AdlibSong, SongFileReader

if not os.path.isfile("GENMIDI.OP2"):
    shutil.copy("genmidi/GENMIDI.OP2", "GENMIDI.OP2")

_instruments.add_file("GENMIDI.OP2")  # .freedoom

if len(sys.argv) > 1:
    settings = {}
    midi_events = SongFileReader.open_file(sys.argv[1])
    adlib_song = AdlibSong.convert_from(midi_events, "imf1", settings)
    adlib_song.save_file(f"{sys.argv[1]}.imf")
else:
    print(f"Usage: {sys.argv[0]} <path to MIDI file>\n")

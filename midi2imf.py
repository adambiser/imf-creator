#!/usr/bin/python3.7
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import sys
import imfcreator.instruments as _instruments
from imfcreator.plugins import AdlibSongFile, MidiSongFile

# if not os.path.isfile("GENMIDI.OP2"):
#     shutil.copy("genmidi/GENMIDI.OP2", "GENMIDI.OP2")

# parser = argparse.ArgumentParser(description='An AppGameKit build automation script.')
# parser.add_argument('buildfile', metavar='buildfile', type=str, help='The agkbuild file to process.')
# args = parser.parse_args()


_instruments.add_file("GENMIDI.OP2")  # .freedoom

if len(sys.argv) > 1:
    settings = {}
    midi_song = MidiSongFile.open_file(sys.argv[1])
    adlib_song = AdlibSongFile.convert_from(midi_song, "imf1", settings)
    adlib_song.save_file(f"{sys.argv[1]}.imf")
else:
    print(f"Usage: {sys.argv[0]} <path to MIDI file>\n")

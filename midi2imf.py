#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import os
import shutil
import sys

from imfcreator.plugins import instrumentfile
from imfcreator.imf_builder import convert_midi_to_imf
from imfcreator.plugins.midifileplugin import MidiReader

instruments = instrumentfile.get_all_instruments("GENMIDI.OP2")  # .freedoom

if not os.path.isfile("GENMIDI.OP2"):
    shutil.copy("genmidi/GENMIDI.OP2", "GENMIDI.OP2")

reader = MidiReader()
if len(sys.argv) > 1:
    reader.load(sys.argv[1])
    imf = convert_midi_to_imf(reader, instruments, output_file_name=("%s.imf" % sys.argv[1]), imf_file_type=1)
else:
    print "Usage: %s <path to MIDI file>\n" % sys.argv[0]

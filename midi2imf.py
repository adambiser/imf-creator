#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import os
import shutil
import sys

from imfcreator.filetypes import instrumentfile
from imfcreator.imf_builder import convert_midi_to_imf
from imfcreator.filetypes.midifileplugin import MidiReader

if len(sys.argv) > 1:
    bank_file = "GENMIDI.OP2"  # .freedoom
    midi_file = sys.argv[1]
    if len(sys.argv) > 2:
        bank_file = sys.argv[2]
    else:
        if not os.path.isfile("GENMIDI.OP2"):
            shutil.copy("genmidi/GENMIDI.OP2", "GENMIDI.OP2")
    print "Loading bank %s..." % bank_file
    instruments = instrumentfile.get_all_instruments(bank_file)
    print "Processing song %s..." % midi_file
    reader = MidiReader()
    reader.load(midi_file)
    imf = convert_midi_to_imf(reader, instruments, output_file_name=("%s.imf" % sys.argv[1]), imf_file_type=1)
else:
    print "Usage: %s <path to MIDI file>\n" % sys.argv[0]

from imfcreator.mainapplication import MainApplication
from imfcreator.imf.constants import *
from imfcreator.imf.player import ImfPlayer
from imfcreator.imf.imfmusicfile import ImfMusicFile
from imfcreator.signal import Signal
import inspect
import time
import Tix as tix
from imfcreator.midi.reader import MidiReader, MidiEvent
import mido
import math
import timeit


# class Signal:
#     """A simple event system.
#
#     Based on: https://stackoverflow.com/posts/35957226/revisions
#     """
#     def __init__(self, **args):
#         self._args = args
#         self._argnames = set(args.keys())
#         self._listeners = []
#
#     def _args_string(self):
#         return ", ".join(sorted(self._argnames))
#
#     def __iadd__(self, listener):
#         args = inspect.getargspec(listener).args
#         if set(n for n in args) != self._argnames:
#             raise ValueError("Listener must have these arguments: {}".format(self._args_string()))
#         self._listeners.append(listener)
#         return self
#
#     def __isub__(self, listener):
#         self._listeners.remove(listener)
#         return self
#
#     def __call__(self, *args, **kwargs):
#         if args or set(kwargs.keys()) != self._argnames:
#             raise ValueError("This Signal requires these arguments: {}".format(self._args_string()))
#         for listener in self._listeners:
#             listener(**kwargs)


def listener1(x, y):
    print("method listener: {}, {}".format(x, y))


def listener2(x, y):
    print("lambda listener: {}, {}".format(x, y))

def listener3():
    print("no args")


def main(imf):
    # player = ImfPlayer()
    # file_info = player.load("test.wlf")
    # # file_info = player.load("wolf3d.wlf")
    # print(file_info)
    # # print("num_commands: {}".format(player.num_commands))
    # # player.mute[1] = True
    # # player.mute[2] = True
    # # player.mute[3] = True
    # # player.mute[4] = True
    # # player.mute[5] = True
    # # player.mute[6] = True
    # # player.mute[7] = True
    # # player.mute[8] = True
    # # player.seek(200)
    # # player.play(True)
    # while player.isactive:
    #     # print("isactive")
    #     time.sleep(0.1)
    # player.close()
    root = MainApplication()
    root.player.set_song(imf)
    root.mainloop()

def testsignals():
    changed = Signal(x=int, y=int)
    changed += listener1
    changed += lambda x, y: listener2(x, y)
    changed(x=23, y=13)
    changed = Signal()
    changed += listener3
    changed()


def miditest():
    filename = "testfmt0.mid"
    # filename = "testfmt1.mid"
    # filename = "brahms_opus1_1.mid"
    reader = MidiReader()
    reader.load(filename)
    for track in reader.tracks:
        print '=== Track: {}'.format(track.name)
        for message in track:
            print "  " + str(message)
    midi_file = mido.MidiFile(filename)
    for track in midi_file.tracks:
        print '=== Track {}'
        for message in track:
            print '  {!r} = {}'.format(message.__class__.__name__, message.__dict__)


import copy

def sort_midi(midi): #, mute_tracks=None, mute_channels=None):
    # Combine all tracks into one track.
    events = []
    for track in midi.tracks:
        time = 0
        for event in track:
            time += event.delta
            del event.delta
            event = copy.copy(event)
            event.event_time = time
            event.track = track.number
            events.append(event)
    # if mute_tracks:
    #     events = filter(lambda event: event.track not in mute_tracks, events)
    # if mute_channels:
    #     events = filter(lambda event: not hasattr(event, "channel") or event.channel not in mute_channels, events)
    # Sort by event time and channel. Note-on events with a velocity should come last at a given time within the song.
    events = sorted(events, key=lambda event: (
        event.event_time,
        1 if event.type == "note_on" and event.velocity > 0 else 0,
        event.channel if hasattr(event, "channel") else -1,
    ))
    return events

# def add_command(regs, reg, value, ticks):


def convert_midi_to_imf(midi, instruments, mute_tracks=None, mute_channels=None):
    events = sort_midi(midi) #, mute_tracks, mute_channels)
    imf = ImfMusicFile()
    # Prepare MIDI and IMF channel variables.
    midi_channels = {}
    for ch in range(16):
        midi_channels[ch] = {
            "instrument": None,
            "volume": 127,
            "pitch_bend": 0,
            "scaled_pitch_bend": 0.0,
            "active_notes": [],
        }
    imf_channels = [{
        "id": channel,
        "instrument": None,
        "last_note": None,
    } for channel in range(1, 9)]
    regs = [None] * 256
    midi_tempo = 120.0

    # Define helper functions.
    def calc_imf_ticks(value):
        return int(imf.ticks_per_second * (float(value) / midi.division) * (60.0 / midi_tempo))

    def find_imf_channel(instrument, note):
        channel = filter(lambda ch: ch["instrument"] == instrument and ch["last_note"] is None, imf_channels)
        if channel:
            return channel[0]  #["id"]
        channel = filter(lambda ch: ch["last_note"] is None, imf_channels)
        if channel:
            return channel[0]  #["id"]
        # TODO Aggressive channel find.
        return None

    def add_commands(commands):
        added_command = False
        for command in commands:
            reg, value = command
            # if (reg & 0x20) == 0x20:
            #     value = (value & 0xf0) | 1
            if regs[reg] != value:
                imf.add_command(reg, value, 0)
                regs[reg] = value
                added_command = True
        return added_command

    def get_block_and_freq(note, scaled_pitch_bend):
        assert note < 128
        while note >= len(BLOCK_FREQ_NOTE_MAP):
            note -= 12
        block, freq = BLOCK_FREQ_NOTE_MAP[note]
        print "note on: {}, 0x{:x}".format(block, freq)
        # Adjust for pitch bend
        if scaled_pitch_bend < 0:
            semitones = int(math.floor(scaled_pitch_bend))
            bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note - semitones]
            if bend_block < block:
                bend_freq = bend_freq * 0.5 ** (block - bend_block)
            freq = int(freq - (freq - bend_freq) * scaled_pitch_bend / -semitones)
            print "bend down, {}: {}, 0x{:x}".format(scaled_pitch_bend, block, freq)
        elif scaled_pitch_bend > 0:
            semitones = int(math.ceil(scaled_pitch_bend))
            bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note + semitones]
            if bend_block > block:
                bend_freq = bend_freq * 2 ** (block - bend_block)
            freq = int(freq + (bend_freq - freq) * scaled_pitch_bend / semitones)
            # Bounds checking
            print "bend up, {}: {}, 0x{:x}".format(scaled_pitch_bend, block, freq)
            while (freq > 0x7ff):
                freq = freq // 2
                block -= 1
                print "bounds adjust: {}, 0x{:x}".format(block, freq)
                if block < 0:
                    block, freq = (0, 0)
                    break
        else:
            print "no bend"
        return block, freq  # BLOCK_FREQ_NOTE_MAP[note]

    def find_imf_channel_for_instrument_note(instrument, note):
        channel = filter(lambda ch: ch["instrument"] == instrument and ch["last_note"] == note, imf_channels)
        if channel:
            return channel[0]
        return None

    def note_off(event):
        commands = []
        channel = find_imf_channel_for_instrument_note(midi_channels[event.track]["instrument"], event.note)
        midi_channels[event.track]["active_notes"].remove(event.note)
        if channel:
            channel["last_note"] = None
            # block, freq = get_block_and_freq(event)
            commands += [
                # (BLOCK_MSG | channel["id"], KEY_OFF_MASK | (block << 2) | (freq >> 8)),
                (BLOCK_MSG | channel["id"], KEY_OFF_MASK),
            ]
        return commands

    def note_on(event):
        commands = []
        midi_track = midi_channels[event.track]
        if midi_track["instrument"] is None:
            print "No instrument assigned to track {}, defaulting to 0."
            midi_track["instrument"] = 0
        midi_channels[event.track]["active_notes"].append(event.note)
        channel = find_imf_channel(midi_track["instrument"], event.note)
        if channel:
            voice = 0
            # Check for instrument change.
            instrument = instruments[midi_track["instrument"]]
            if channel["instrument"] != midi_track["instrument"]:
                commands += instrument.get_regs(channel["id"], voice)
                channel["instrument"] = midi_track["instrument"]
            volume = int(midi_track["volume"] * event.velocity / 127.0)
            channel["last_note"] = event.note
            block, freq = get_block_and_freq(event.note, midi_channels[event.track]["scaled_pitch_bend"])
            commands += [
                (
                    VOLUME_MSG | CARRIERS[channel["id"]],
                    ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                ),
                (FREQ_MSG | channel["id"], freq & 0xff),
                (BLOCK_MSG | channel["id"], KEY_ON_MASK | (block << 2) | (freq >> 8)),
            ]
        return commands

    def pitch_bend(event):
        commands = []
        amount = event.value - event.value % pitch_bend_resolution
        if midi_channels[event.track]["pitch_bend"] != amount:
            midi_channels[event.track]["pitch_bend"] = amount
            # Scale picth bend to -1..1
            scaled_pitch_bend = amount / -pitch_bend_range[0] if amount < 0 else amount / pitch_bend_range[1]
            scaled_pitch_bend *= 2  # TODO Read from controller messages. 2 semi-tones is the default.
            midi_channels[event.track]["scaled_pitch_bend"] = scaled_pitch_bend
            instrument = midi_channels[event.track]["instrument"]
            for note in midi_channels[event.track]["active_notes"]:
                channel = find_imf_channel_for_instrument_note(instrument, note)
                if channel:
                    block, freq = get_block_and_freq(note, scaled_pitch_bend)
                    commands += [
                        (FREQ_MSG | channel["id"], freq & 0xff),
                        (BLOCK_MSG | channel["id"], KEY_ON_MASK | (block << 2) | (freq >> 8)),
                    ]
                    pass
        return commands

    # Cycle MIDI events and convert to IMF commands.
    last_ticks = 0
    # ticks = 0
    pitch_bend_resolution = 0x100
    pitch_bend_range = (-8192.0 - -8192 % -pitch_bend_resolution, 8191.0 - 8191 % pitch_bend_resolution)
    imf.commands.append((0, 0, 0)) # Always start with 0, 0, 0
    for event in events:
        ticks = calc_imf_ticks(event.event_time)
        if ticks > last_ticks:
            imf.commands[-1] = imf.commands[-1][:2] + (imf.commands[-1][2] + ticks - last_ticks,)
            last_ticks = ticks
        # Perform muting
        if mute_tracks:
            if event.track in mute_tracks:
                continue
        if mute_channels:
            if hasattr(event, "channel") and event.channel in mute_channels:
                continue
        # Handle events.
        commands = []  # list of (reg, value) tuples.
        if (event.type == "note_on" and event.velocity == 0) or event.type == "note_off":
            commands += note_off(event)
        elif event.type == "note_on":
            commands += note_on(event)
        elif event.type == "controller_change" and event.controller == 7:  # volume, TODO: .controller_name
            midi_channels[event.channel]["volume"] = event.value
        elif event.type == "pitch_bend":
            commands += pitch_bend(event)
        elif event.type == "program_change":
            midi_channels[event.track]["instrument"] = event.program
        elif event.type == "meta" and event.meta_type == "set_tempo":
            midi_tempo = float(event.bpm)
        add_commands(commands)
    imf._save("output.wlf")
    # for command in imf.commands:
    #     print(map(hex, command))
    return imf




from imfcreator.adlib import instrumentfile
instruments = instrumentfile.get_all_instruments("GENMIDI.OP2")

reader = MidiReader()
# reader.load("testfmt1.mid")
reader.load("test-pitchbend.mid")
# imf = convert_midi_to_imf(reader, instruments, mute_channels=[9])
imf = convert_midi_to_imf(reader, instruments, mute_channels=[9])
# convert_midi_to_imf(reader, instruments, mute_tracks=[3])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2], mute_channels=[9])

main(imf)
# testsignals()
# miditest()

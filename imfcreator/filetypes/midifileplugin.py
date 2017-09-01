import os
import struct
import _binary

NOTE_OFF_EVENT = 0x80
NOTE_ON_EVENT = 0x90
POLYPHONIC_KEY_PRESSURE_EVENT = 0xa0
CONTROLLER_CHANGE_EVENT = 0xb0  # Also has channel mode messages.
PROGRAM_CHANGE_EVENT = 0xc0
CHANNEL_KEY_PRESSURE_EVENT = 0xd0
PITCH_BEND_EVENT = 0xe0
F0_SYSEX_EVENT = 0xf0
F7_SYSEX_EVENT = 0xf7
META_EVENT = 0xff

_EVENT_TYPE_NAMES = {
    NOTE_OFF_EVENT: "note_off",
    NOTE_ON_EVENT: "note_on",
    POLYPHONIC_KEY_PRESSURE_EVENT: "polyphonic_key_pressure",
    CONTROLLER_CHANGE_EVENT: "controller_change",
    PROGRAM_CHANGE_EVENT: "program_change",
    CHANNEL_KEY_PRESSURE_EVENT: "channel_key_pressure",
    PITCH_BEND_EVENT: "pitch_bend",
    F0_SYSEX_EVENT: "f0_sysex",
    F7_SYSEX_EVENT: "f7_sysex",
    META_EVENT: "meta",
}

_META_TYPE_NAMES = {
    0: 'sequence_number',
    1: 'text_event',
    2: 'copyright',
    3: 'track_name',
    4: 'instrument_name',
    5: 'lyric',
    6: 'marker',
    7: 'cue_point',
    0x20: 'channel_prefix',
    0x2f: 'end_of_track',
    0x51: 'set_tempo',
    0x54: 'smtpe_offset',
    0x58: 'time_signature',
    0x59: 'key_signature',
    0x7f: 'sequencer_specific',
}

_CONTROLLER_NAMES = {
    0: "bank_select_msb",  # MSB is most common, except for #32.
    1: "modulation_wheel_msb",
    2: "breath_controller_msb",
    4: "foot_controller_msb",
    5: "portamento_time_msb",
    6: "data_entry_msb",
    7: "volume_msb",
    8: "balance_msb",
    10: "pan_msb",
    11: "expression_msb",
    12: "effect_1_msb",
    13: "effect_2_msb",
    16: "general_purpose_1_msb",
    17: "general_purpose_2_msb",
    18: "general_purpose_3_msb",
    19: "general_purpose_4_msb",
    32: "bank_select_lsb",
    33: "modulation_lsb",
    34: "breath_controller_lsb",
    36: "foot_controller_lsb",
    37: "portamento_time_lsb",
    38: "data_entry_lsb",
    39: "volume_lsb",
    40: "balance_lsb",
    42: "pan_lsb",
    43: "expression_lsb",
    44: "effect_1_lsb",
    45: "effect_2_lsb",
    48: "general_purpose_1_lsb",
    49: "general_purpose_2_lsb",
    50: "general_purpose_3_lsb",
    51: "general_purpose_4_lsb",
    64: "sustain_pedal_switch",  # 0-63 = Off, 64-127 = On
    65: "portamento_switch",
    66: "sostenuto_switch",
    67: "soft_pedal_switch",
    68: "legato_footswitch",
    69: "hold_2_switch",
    70: "sound_controller_1",
    71: "sound_controller_2",
    72: "sound_controller_3",
    73: "sound_controller_4",
    74: "sound_controller_5",
    75: "sound_controller_6",
    76: "sound_controller_7",
    77: "sound_controller_8",
    78: "sound_controller_9",
    79: "sound_controller_10",
    80: "general_purpose_5",
    81: "general_purpose_6",
    82: "general_purpose_7",
    83: "general_purpose_8",
    84: "portamento_amount",
    91: "effects_1_depth",
    92: "effects_2_depth",
    93: "effects_3_depth",
    94: "effects_4_depth",
    95: "effects_5_depth",
    96: "data_increment",
    97: "data_decrement",
    98: "nrpn_lsb",  # For controllers 6, 38, 96, and 97
    99: "nrpn_msb",  # For controllers 6, 38, 96, and 97
    100: "rpn_lsb",  # For controllers 6, 38, 96, and 97
    101: "rpn_msb",  # For controllers 6, 38, 96, and 97
}


def _read_var_length(f):
    """Reads a length using MIDI's variable length format."""
    length = 0
    b = _u8(f)
    while b & 0x80:
        length = length * 0x80 + (b & 0x7f)
        b = _u8(f)
    return length * 0x80 + b


def _u8(f):
    """Read the next byte as an ordinal."""
    return _binary.u8(f.read(1))


class MidiReader:
    """Reads a MIDI file."""
    def __init__(self):
        self.file_format = None
        self.division = None
        self.f = None
        self._running_status = None
        # self.num_tracks = None
        self.tracks = []

    def load(self, filename):
        """Loads a MIDI file into the reader object."""
        with open(filename, "rb") as f:
            try:
                self.f = f
                # Start the chunk header generator. The data within the chunk must be handled separately.
                chunk_headers = self._iterchunkheader()
                chunk_name, chunk_length = chunk_headers.next()
                if chunk_name != "MThd":
                    raise IOError("Not a MIDI file.")
                if chunk_length != 6:
                    raise IOError("Invalid MIDI header length: {}".format(chunk_length))
                self.file_format, num_tracks, self.division = struct.unpack(">HHH", f.read(6))
                # if self.file_format not in (0, 1):
                #     raise IOError("Unsupported MIDI file format: {}".format(self.file_format))
                # print(self.file_format, num_tracks, self.division)
                # Process remaining chunks.
                for chunk_name, chunk_length in chunk_headers:
                    if chunk_name == "MTrk":
                        track = MidiTrack(len(self.tracks))
                        for event in self._read_events(chunk_length):
                            track.add_event(event)
                        self.tracks.append(track)
                        self._running_status = None
                    else:
                        # Skip any other chunk types that might appear.
                        f.seek(chunk_length, os.SEEK_CUR)
            finally:
                self.f = None

    def convert_to_format_0(self):
        # First, calculate the time from the start of the file for each event.
        events = []
        for track in self.tracks:
            time = 0
            for event in track:
                # if event.type == "meta" and event.meta_type == "end_of_track":
                #     continue
                time += event.delta
                event.time_from_start = time
                events.append(event)
        # Second, combine tracks and sort by time from start.
        events = sorted(events, key=lambda event: (
            event.time_from_start,
            1 if event.type == "note_on" and event.velocity > 0 else 0,
            event.channel if hasattr(event, "channel") else -1,
        ))
        # Remove all "end of track" events and add the last one to the end of the event list.
        end_of_track = filter(lambda event: event.type == "meta" and event.meta_type == "end_of_track", events)
        for event in end_of_track:
            events.remove(event)
        time = 0
        events.append(end_of_track[-1])
        # Remove all track name events.
        for event in filter(lambda event: event.type == "meta" and event.meta_type == "track_name", events):
            events.remove(event)
        time = 0
        # Adjust delta time to be time from previous event.
        for event in events:
            event.delta = event.time_from_start - time
            assert event.delta >= 0
            time = event.time_from_start
            del event.time_from_start

    def _iterchunkheader(self):
        """A generator that assumes that the internal file object is positioned
        at the start of chunk header information.
        """
        while True:
            chunk_name = self.f.read(4)
            if chunk_name == "":
                return
            chunk_length = struct.unpack(">I", self.f.read(4))[0]
            yield chunk_name, chunk_length

    def _read_events(self, length):
        """A generator that assumes that the internal file object is positioned
        at the start of an event delta time.
        """
        end_tell = self.f.tell() + length
        while self.f.tell() < end_tell:
            event = self._read_event()
            if event is None:
                return
            yield event

    def _read_event(self):
        """Reads a MIDI event at the current file position."""
        delta_time = _read_var_length(self.f)
        # Read the event type.
        event_type = _u8(self.f)
        # Check for running status.
        if event_type & 0x80 == 0:
            assert event_type is not None
            self.f.seek(-1, os.SEEK_CUR)
            event_type = self._running_status
        else:
            # New status event. Clear the running status now.
            # It will get reassigned later if necessary.
            self._running_status = None
        # print("Event 0x{:x} at 0x{:x}".format(event_type, self.f.tell() - 1))
        event = MidiEvent.create_event(delta_time, event_type, self.f)
        try:
            if event.channel >= 0:
                self._running_status = event_type
        except AttributeError:
            # Ignore attribute error.
            pass
        return event


class MidiTrack:
    """Represents a MIDI track within a file and stores the events for the track."""
    def __init__(self, number):
        self._events = []
        self.name = None
        self.number = number

    def add_event(self, event):
        if event.type == "meta" and event.meta_type == "track_name":
            self.name = event.text
        self._events.append(event)

    @property
    def num_events(self):
        return len(self._events)

    def __iter__(self):
        return self._events.__iter__()


class MidiEvent:
    """Represents an abstract event within a MIDI file."""
    def __init__(self, **kwargs):
        if kwargs.get("delta") is None:
            raise Exception('A value for "delta" is required.')
        if kwargs.get("type") is None:
            raise Exception('A value for "type" is required.')
        for k, v in kwargs.iteritems():
            self.__dict__[k] = v

    def __repr__(self):
        return str(self.__dict__)

    @classmethod
    def create_event(cls, delta, event_type, stream):
        args = {
            "delta": delta,
        }
        if event_type == F0_SYSEX_EVENT:
            data_length = _read_var_length(stream)
            args.update({
                "type": _EVENT_TYPE_NAMES[event_type],
                "data": [_u8(stream) for x in range(data_length)],
            })
        elif event_type == F7_SYSEX_EVENT:
            data_length = _read_var_length(stream)
            args.update({
                "type": _EVENT_TYPE_NAMES[event_type],
                "data": [_u8(stream) for x in range(data_length)],
            })
        elif event_type == META_EVENT:
            args["type"] = _EVENT_TYPE_NAMES[event_type]
            meta_type = _u8(stream)
            meta_type_name = _META_TYPE_NAMES.get(meta_type)
            if meta_type_name is None:
                meta_type_name = "unknown_0x{:x}".format(meta_type)
            args["meta_type"] = meta_type_name
            data_length = _read_var_length(stream)
            if meta_type_name in [
                    "text_event",
                    "copyright",
                    "track_name",
                    "instrument_name",
                    "lyric",
                    "marker",
                    "cue_point"]:
                args["text"] = stream.read(data_length)
            elif meta_type_name == "set_tempo":
                args["speed"] = (_u8(stream) << 16) + (_u8(stream) << 8) + _u8(stream)
                args["bpm"] = 60000000 / args["speed"]  # 60 seconds as microseconds
            elif meta_type_name == "smtpe_offset":
                args.update({
                    "hours": _u8(stream),
                    "minutes": _u8(stream),
                    "seconds": _u8(stream),
                    "frames": _u8(stream),
                    "fractional_frames": _u8(stream),
                })
            elif meta_type_name == "time_signature":
                args.update({
                    "numerator": _u8(stream),
                    "denominator": 2 ** _u8(stream),  # given in powers of 2.
                    "midi_clocks_per_metronome_tick": _u8(stream),
                    "number_of_32nd_notes_per_beat": _u8(stream),  # almost always 8
                })
            elif meta_type_name == "key_signature":
                keys = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F",
                        "C", "G", "D", "A", "E", "B", "F#",
                        "C#", "G#", "D#", "A#"]
                sharps_flats, major_minor = struct.unpack("<bB", stream.read(2))
                args["key"] = keys[sharps_flats + 7 + major_minor * 3] + "m" * major_minor
            # elif meta_type_name == "sequencer_specific":
            #     # TODO Convert data.
            #       id      1 or 3 bytes representing the Manufacturer's ID
            #       data    binary data
            else:
                if data_length:
                    args["data"] = [_u8(stream) for x in range(data_length)],
        else:
            args["channel"] = event_type & 0xf
            event_type &= 0xf0
            args["type"] = _EVENT_TYPE_NAMES[event_type]
            if args["type"] is None:
                args["type"] = "unknown_0x{:x}".format(event_type)
            if event_type == NOTE_OFF_EVENT:
                args.update({
                    "note": _u8(stream),
                    "velocity": _u8(stream),
                })
            elif event_type == NOTE_ON_EVENT:
                args.update({
                    "note": _u8(stream),
                    "velocity": _u8(stream),
                })
            elif event_type == POLYPHONIC_KEY_PRESSURE_EVENT:
                args.update({
                    "key": _u8(stream),
                    "pressure": _u8(stream),
                })
            elif event_type == CONTROLLER_CHANGE_EVENT:
                controller = _u8(stream)
                controller_name = _CONTROLLER_NAMES.get(controller)
                if controller_name is None:
                    controller_name = "unknown_0x{:x}".format(controller)
                args.update({
                    # "controller": _u8(stream),
                    "controller": controller_name,
                    "value": _u8(stream),
                })
            elif event_type == PROGRAM_CHANGE_EVENT:
                args.update({
                    "program": _u8(stream),
                })
            elif event_type == CHANNEL_KEY_PRESSURE_EVENT:
                args.update({
                    "pressure": _u8(stream),
                })
            elif event_type == PITCH_BEND_EVENT:
                args.update({
                    "value": (_u8(stream) + _u8(stream) * 0x80) - 0x2000,  # 0 is center
                })
            else:
                raise Exception("Unsupported MIDI event code: 0x{:X}".format(event_type))
        return MidiEvent(**args)

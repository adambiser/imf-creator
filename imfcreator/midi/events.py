from .constants import *
import struct


class MidiEvent:
    """Represents an abstract event within a MIDI file."""
    def __init__(self, delta, event_type, data):
        self.delta = delta
        self.event_type = event_type
        self.data = struct.unpack("B" * len(data), data)

    def __repr__(self):
        return "{}: delta: {}".format(self.__class__.__name__, self.delta)

    @classmethod
    def create_event(cls, delta, event_type, stream):
        event_function = MidiEvent._EVENT_FUNC_MAP.get(event_type)
        if event_function is None:
            event_function = MidiEvent._EVENT_FUNC_MAP.get(event_type & 0xf0)
        if event_function is None:
            raise Exception("Unsupported MIDI event code: 0x{:X}".format((event_type)))
        return event_function(delta, event_type, stream)

    @classmethod
    def create_note_off_event(cls, delta, event_type, stream):
        return NoteOffEvent(delta, event_type, stream.f.read(2))

    @classmethod
    def create_note_on_event(cls, delta, event_type, stream):
        return NoteOnEvent(delta, event_type, stream.f.read(2))

    @classmethod
    def create_polyphonic_key_pressure_event(cls, delta, event_type, stream):
        return PolyphonicKeyPressureEvent(delta, event_type, stream.f.read(2))

    @classmethod
    def create_controller_change_event(cls, delta, event_type, stream):
        return ControllerChangeEvent(delta, event_type, stream.f.read(2))

    @classmethod
    def create_program_change_event(cls, delta, event_type, stream):
        return ProgramChangeEvent(delta, event_type, stream.f.read(1))

    @classmethod
    def create_channel_key_pressure_event(cls, delta, event_type, stream):
        return ChannelKeyPressureEvent(delta, event_type, stream.f.read(1))

    @classmethod
    def create_pitch_bend_event(cls, delta, event_type, stream):
        return PitchBendEvent(delta, event_type, stream.f.read(2))

    @classmethod
    def create_sysex_event(cls, delta, event_type, stream):
        data_length = stream._read_var_length()
        return SysExEvent(delta, event_type, stream.f.read(data_length))

    @classmethod
    def create_meta_event(cls, delta, event_type, stream):
        meta_type = stream._next_byte()
        data_length = stream._read_var_length()
        return MetaEvent(delta, event_type, meta_type, stream.f.read(data_length))

# Map MIDI event codes to methods used to create the matching event object.
MidiEvent._EVENT_FUNC_MAP= {
    NOTE_OFF_EVENT: MidiEvent.create_note_off_event,
    NOTE_ON_EVENT: MidiEvent.create_note_on_event,
    POLYPHONIC_KEY_PRESSURE_EVENT: MidiEvent.create_polyphonic_key_pressure_event,
    CONTROLLER_CHANGE_EVENT: MidiEvent.create_controller_change_event,
    PROGRAM_CHANGE_EVENT: MidiEvent.create_program_change_event,
    CHANNEL_KEY_PRESSURE_EVENT: MidiEvent.create_channel_key_pressure_event,
    PITCH_BEND_EVENT: MidiEvent.create_pitch_bend_event,
    F0_SYSEX_EVENT: MidiEvent.create_sysex_event,
    F7_SYSEX_EVENT: MidiEvent.create_sysex_event,
    META_EVENT: MidiEvent.create_meta_event,
}


class ChannelEvent(MidiEvent):
    def __init__(self, delta, event_type, data):
        MidiEvent.__init__(self, delta, event_type & 0xf0, data)
        self.channel = event_type & 0xf

    def __repr__(self):
        return MidiEvent.__repr__(self) + ", channel: {}".format(self.channel)


class NoteOffEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.key = self.data[0]
        self.velocity = self.data[1]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", key: {}, velocity: {}".format(self.key, self.velocity)


class NoteOnEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.key = self.data[0]
        self.velocity = self.data[1]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", key: {}, velocity: {}".format(self.key, self.velocity)


class PolyphonicKeyPressureEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.key = self.data[0]
        self.pressure = self.data[1]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", key: {}, pressure: {}".format(self.key, self.pressure)


class ControllerChangeEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.controller = self.data[0]
        self.value = self.data[1]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", controller: {}, value: {}".format(self.controller, self.value)


class ProgramChangeEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.program = self.data[0]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", program: {}".format(self.program)


class ChannelKeyPressureEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.pressure = self.data[0]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", pressure: {}".format(self.pressure)


class PitchBendEvent(ChannelEvent):
    def __init__(self, delta, event_type, data):
        ChannelEvent.__init__(self, delta, event_type, data)
        self.amount = self.data[1] * 0x80 + self.data[0]

    def __repr__(self):
        return ChannelEvent.__repr__(self) + ", amount: {}".format(self.amount)


class SysExEvent(MidiEvent):
    def __init__(self, delta, event_type, data):
        MidiEvent.__init__(self, delta, event_type, data)


class MetaEvent(MidiEvent):
    _META_TRANSLATE_MAP = {
        0: ('Sequence Number', None),
        1: ('Text Event', "text"),
        2: ('Copyright', "text"),
        3: ('Track Name', "text"),
        4: ('Instrument Name', "text"),
        5: ('Lyric', "text"),
        6: ('Marker', "text"),
        7: ('Cue Point', "text"),
        0x20: ('Channel Prefix', None),
        0x2f: ('End of Track', None),
        0x51: ('Set Tempo', None),  # TODO Convert data to 3 byte tempo.
        0x54: ('SMTPE Offset', None),  # TODO Convert data.
        0x58: ('Time Signature', None),  # TODO Convert data.
        0x59: ('Key Signature', None),  # TODO Convert data.
        0x7f: ('Sequencer-Specific', None),  # TODO Convert data.
    }

    def __init__(self, delta, event_type, meta_type, data):
        MidiEvent.__init__(self, delta, event_type, data)
        # TODO Translate data into string/byte data depending on meta type.
        translate_map = MetaEvent._META_TRANSLATE_MAP.get(meta_type)
        if translate_map is None:
            self.meta_type_name = "Unknown"
        else:
            self.meta_type_name, data_type = translate_map
            if data_type == "text":
                self.data = struct.pack("B" * len(self.data), *self.data)
        self.meta_type = meta_type

    def __repr__(self):
        return MidiEvent.__repr__(self) + ", type: {}, data: {}".format(self.meta_type_name, self.data)

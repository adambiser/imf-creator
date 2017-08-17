import struct
from .constants import *


class MidiReader:
    """Reads a MIDI file."""
    def __init__(self):
        pass

    def load(self, filename):
            with open(filename, "rb") as f:
                # Check header
                chunks = self._read_chunks(f)
                header = chunks.next()
                if header.type != "MThd":
                    raise IOError("Not a MIDI file.")
                if header.length != 6:
                    raise IOError("Invalid MIDI header length.")
                # Parse header data.
                file_format = read_uint16(header.data[0:2])
                if file_format not in (0, 1):
                    raise IOError("Unsupported MIDI file format: {}".format(file_format))
                num_tracks = read_uint16(header.data[2:4])
                division = read_uint16(header.data[4:6])
                print(file_format, num_tracks, division)
                # Parse other chunks.
                for chunk in chunks:
                    if chunk.type == "MTrk":
                        for events in self._read_events(chunk.data):
                            pass

    def _read_chunks(self, f):
        """A generator for reading the """
        while True:
            chunk = self._read_chunk(f)
            if chunk is None:
                break
            yield chunk

    def _read_chunk(self, f):
        """Reads a chunk from the f.

        Returns a MidiChunk or None if the end of file is reached.
        """
        chunk_type = f.read(4)
        if chunk_type == "":
            return None
        chunk_length = read_uint32(f.read(4))
        chunk_data = f.read(chunk_length)
        return MidiChunk(type_name=chunk_type, length=chunk_length, data=chunk_data)

    def _read_events(self, data):
        """Reads and parses events from data."""
        buf = iterbytes(data)
        while True:
            event = self._read_event(buf)
            if event is None:
                return
            yield event

    def _read_event(self, buf):
        # Read delta length
        delta_time = self._read_var_length(buf)
        print(delta_time)
        # Event code.
        event_type = buf.next()
        print("event_type: {:x}".format(event_type))
        meta_type = None
        event_data = None
        if event_type in (F0_SYSEX_EVENT, F7_SYSEX_EVENT):
            data_length = self._read_var_length(buf)
        elif event_type == META_EVENT:
            meta_type = buf.next()
            data_length = self._read_var_length(buf)
        elif event_type in NOTE_OFF_EVENTS \
                or event_type in NOTE_ON_EVENTS \
                or event_type in POLYPHONIC_KEY_EVENTS \
                or event_type in CONTROLLER_CHANGE_EVENTS \
                or event_type in PITCH_BEND_EVENTS:
            data_length = 2
        elif event_type in PROGRAM_CHANGE_EVENTS \
            or event_type in CHANNEL_KEY_EVENTS:
            data_length = 1
        else:
            raise IOError("Unsupported event type: 0x{:x}".format(event_type))
        if data_length > 0:
            event_data = [buf.next() for x in range(data_length)]
        return MidiEvent(delta_time, event_type, data_length, event_data, meta_type)

    def _read_var_length(self, buf):
        length = 0
        b = buf.next()
        while b & 0x80:
            length *= 0x80 + (b & 0x7f)
            b = buf.next()
        return length + b


class MidiChunk(object):
    """Represents a chunk within a MIDI file."""
    def __init__(self, type_name, length, data):
        self._type_name = type_name
        self._length = length
        self._data = data

    @property
    def type(self):
        return self._type_name

    @property
    def length(self):
        return self._length

    @property
    def data(self):
        return self._data


class MidiEvent(object):
    """Represents an event within a MIDI file."""
    def __init__(self, delta, event_type, data_length, data, meta_type=None):
        self._delta = delta
        self._event_type = event_type
        self._data_length = data_length
        self._data = data
        if event_type == META_EVENT:
            self._meta_type = meta_type

    @property
    def delta(self):
        return self._delta

    @property
    def type(self):
        return self._event_type

    @property
    def data_length(self):
        return self._data_length

    @property
    def data(self):
        return self._data

    @property
    def meta_type(self):
        return self._meta_type


#
# Helper functions
#
def read_uint32(value):
    return struct.unpack(">I", value)[0]


def read_uint16(value):
    return struct.unpack(">H", value)[0]


def read_byte(value):
    return struct.unpack("B", value)[0]


# def read_var_length(f):
#     value = 0
#     b = read_byte(f.read(1))
#     while b & 0x80:
#         value *= 0x80 + (b & 0x7f)
#         b = read_byte(f.read(1))
#     return value + b


def iterbytes(data):
    for index in range(len(data)):
        yield ord(data[index])

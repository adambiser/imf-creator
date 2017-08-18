import os
import struct
from .constants import *
from .events import MidiEvent, ChannelEvent


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
                    track = MidiTrack()
                    map(track.add_event, self._read_events(chunk_length))
                    self.tracks.append(track)
                else:
                    # Skip any other chunk types that might appear.
                    f.seek(chunk_length, os.SEEK_CUR)

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

    def _next_byte(self):
        """Read the next byte as an ordinal."""
        return ord(self.f.read(1))

    def _read_event(self):
        """Reads a MIDI event at the current file position."""
        delta_time = self._read_var_length()
        # Read the event type.
        event_type = self._next_byte()
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
        event = MidiEvent.create_event(delta_time, event_type, self)
        if isinstance(event, ChannelEvent):
            self._running_status = event_type
        print(event)
        return event
        # meta_type = None
        # event_data = None
        # Read event data and return a MidiEvent object.
        # if event_type in (F0_SYSEX_EVENT, F7_SYSEX_EVENT):
        #     data_length = self._read_var_length()
        # elif event_type == META_EVENT:
        #     meta_type = self._next_byte()
        #     data_length = self._read_var_length()
        # elif event_type & 0xf0 in (
        #         NOTE_OFF_EVENT,
        #         NOTE_ON_EVENT,
        #         POLYPHONIC_KEY_EVENT,
        #         CONTROLLER_CHANGE_EVENT,
        #         PITCH_BEND_EVENT):
        #     self._running_status = event_type
        #     data_length = 2
        # elif event_type & 0xf0 in (
        #         PROGRAM_CHANGE_EVENT,
        #         CHANNEL_KEY_EVENT):
        #     self._running_status = event_type
        #     data_length = 1
        # else:
        #     raise IOError("Unsupported event type: 0x{:x} at 0x{:x}".format(event_type, self.f.tell() - 1) )
        # if data_length > 0:
        #     event_data = self.f.read(data_length)  # [f.next() for b in range(data_length)]
        # return MidiEvent(delta_time, event_type, data_length, event_data, meta_type)

    def _read_var_length(self):
        """Reads a length using MIDI's variable length format."""
        length = 0
        b = self._next_byte()
        while b & 0x80:
            length = length * 0x80 + (b & 0x7f)
            b = self._next_byte()
        return length * 0x80 + b


class MidiTrack:
    """Represents a MIDI track within a file and stores the events for the track."""
    def __init__(self):
        self._events = []

    def add_event(self, event):
        self._events.append(event)

    @property
    def num_events(self):
        return len(self._events)

    def __iter__(self):
        return self._events.__iter__()


# class MidiEvent:
#     """Represents an event within a MIDI file."""
#     def __init__(self, delta, event_type, data_length, data, meta_type=None):
#         self.delta = delta
#         if NOTE_OFF_EVENT <= event_type < F0_SYSEX_EVENT:
#             self.event_type = event_type & 0xf0
#             self.channel = event_type & 0xf
#         else:
#             self.event_type = event_type
#             self.channel = None
#         self.data_length = data_length
#         self.data = data
#         if event_type == META_EVENT:
#             self.meta_type = meta_type
#
#     def __repr__(self):
#         return "Event 0x{:x}, channel: {}, delta: {}, data_length: {}".format(
#             self.event_type,
#             self.channel,
#             self.delta,
#             self.data_length)


# #
# # Helper functions
# #
# def read_uint32(f):
#     return struct.unpack(">I", f.read(4))[0]
#
#
# def read_uint16(f):
#     return struct.unpack(">H", f.read(2))[0]
#
#
# def read_byte(f):
#     return struct.unpack("B", value)[0]

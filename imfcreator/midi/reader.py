import os
import struct
from .constants import *
from .events import MidiEvent


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
                        track = MidiTrack()
                        map(track.add_event, self._read_events(chunk_length))
                        self.tracks.append(track)
                        self._running_status = None
                    else:
                        # Skip any other chunk types that might appear.
                        f.seek(chunk_length, os.SEEK_CUR)
            finally:
                self.f = None

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
        try:
            if event.channel >= 0:
                self._running_status = event_type
        except AttributeError:
            # Ignore attribute error.
            pass
        return event


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
        self.name = None

    def add_event(self, event):
        if event.type == "meta" and event.meta_type == "track_name":
            self.name = event.text
        self._events.append(event)

    @property
    def num_events(self):
        return len(self._events)

    def __iter__(self):
        return self._events.__iter__()

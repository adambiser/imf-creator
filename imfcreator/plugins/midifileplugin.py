import logging as _logging
import os as _os
import struct as _struct
import typing as _typing
import imfcreator.midi as _midi
import imfcreator.plugins._binary as _binary
import imfcreator.utils as _utils
from . import plugin, SongFileReader

_HEADER_CHUNK_NAME = b"MThd"
_HEADER_CHUNK_LENGTH = 6
_TRACK_CHUNK_NAME = b"MTrk"
_PERCUSSION_CHANNEL = 9


def _u8(f):
    """Read the next byte as an ordinal."""
    return _binary.u8(f.read(1))


@plugin
class MidiFileReader(SongFileReader):
    """Reads a MIDI file."""

    def __init__(self, fp=None, filename=None):
        self._events = None
        self._division = 0.0
        super().__init__(fp, filename)

    @classmethod
    def accept(cls, preview: bytes) -> bool:
        return preview[0:4] == _HEADER_CHUNK_NAME and _binary.u32be(preview[4:8]) == _HEADER_CHUNK_LENGTH

    def _open(self):
        """Loads a MIDI file into the reader object."""
        chunk_name, chunk_length = self._read_chunk_header()
        if chunk_name != _HEADER_CHUNK_NAME:
            raise ValueError(f"Unexpected MIDI header chunk name: {chunk_name}")
        if chunk_length != _HEADER_CHUNK_LENGTH:
            raise ValueError(f"Unexpected MIDI header chunk length: {chunk_length}")
        # Read header chunk data.
        file_format, track_count, self._division = _struct.unpack(">HHH", self.fp.read(chunk_length))
        if file_format not in (0, 1):
            raise ValueError(f"Unsupported MIDI file format: {file_format}")
        # Process remaining chunks.
        self._events = []
        for track_number in range(track_count):
            chunk_name, chunk_length = self._read_chunk_header()
            if chunk_name != _TRACK_CHUNK_NAME:
                _logging.info(f"Skipping unrecognized chunk: {chunk_name}.")
                self.fp.seek(chunk_length, _os.SEEK_CUR)
            else:
                self._events.extend(self._read_events(chunk_length, track_number))

    def _read_chunk_header(self) -> (str, int):
        """Returns the chunk name and length at the current file position or None if at the end of the file."""
        chunk_name = self.fp.read(4)
        if not chunk_name:
            return None
        chunk_length = _binary.u32be(self.fp.read(4))
        return chunk_name, chunk_length

    def _read_events(self, chunk_length, track_number) -> _typing.List[_midi.SongEvent]:
        """Reads all of the events in a track"""

        def _read_var_length():
            """Reads a length using MIDI's variable length format."""
            length = 0
            b = _u8(self.fp)
            while b & 0x80:
                length = length * 0x80 + (b & 0x7f)
                b = _u8(self.fp)
            return length * 0x80 + b

        chunk_end = self.fp.tell() + chunk_length
        running_status = None
        event_time = 0
        events = []
        while self.fp.tell() < chunk_end:
            # Read a MIDI event at the current file position.
            delta_time = _read_var_length()
            event_time += delta_time
            # Read the event type.
            event_type = _u8(self.fp)
            # Check for running status.
            if event_type & 0x80 == 0:
                self.fp.seek(-1, _os.SEEK_CUR)
                if running_status is None:
                    raise ValueError(f"Expected a running status, but it was None at pos {self.fp.tell()}.")
                event_type = running_status
            else:
                # New status event. Clear the running status now.
                # It will get reassigned later if necessary.
                running_status = None
            channel = None
            # Read event type data
            if event_type in [_midi.EventType.F0_SYSEX, _midi.EventType.F7_SYSEX]:
                data_length = _read_var_length()
                event_data = {"bytes": [_u8(self.fp) for _ in range(data_length)]}
            elif event_type == _midi.EventType.META:
                meta_type = _midi.MetaType(_u8(self.fp))
                event_data = {"meta_type": meta_type}
                data_length = _read_var_length()
                if meta_type == _midi.MetaType.SEQUENCE_NUMBER:
                    if data_length != 2:
                        raise ValueError("MetaType.SEQUENCE_NUMBER events should have a data length of 2.")
                    event_data.update({
                        "number": _binary.u16be(self.fp.read(2))
                    })
                elif meta_type in [_midi.MetaType.TEXT_EVENT,
                                   _midi.MetaType.COPYRIGHT,
                                   _midi.MetaType.TRACK_NAME,
                                   _midi.MetaType.INSTRUMENT_NAME,
                                   _midi.MetaType.LYRIC,
                                   _midi.MetaType.MARKER,
                                   _midi.MetaType.CUE_POINT,
                                   _midi.MetaType.PROGRAM_NAME,
                                   _midi.MetaType.DEVICE_NAME]:
                    event_data.update({"text": self.fp.read(data_length)})
                elif meta_type == _midi.MetaType.CHANNEL_PREFIX:
                    if data_length != 1:
                        raise ValueError("MetaType.CHANNEL_PREFIX events should have a data length of 1.")
                    event_data.update({"channel": _u8(self.fp)})
                elif meta_type == _midi.MetaType.PORT:
                    if data_length != 1:
                        raise ValueError("MetaType.PORT events should have a data length of 1.")
                    event_data.update({"port": _u8(self.fp)})
                elif meta_type == _midi.MetaType.SET_TEMPO:
                    if data_length != 3:
                        raise ValueError("MetaType.SET_TEMPO events should have a data length of 3.")
                    speed = (_u8(self.fp) << 16) + (_u8(self.fp) << 8) + _u8(self.fp)
                    event_data.update({"bpm": 60000000 / speed})  # 60 seconds as microseconds
                elif meta_type == _midi.MetaType.SMTPE_OFFSET:
                    if data_length != 5:
                        raise ValueError("MetaType.SMTPE_OFFSET events should have a data length of 5.")
                    event_data.update({
                        "hours": _u8(self.fp),
                        "minutes": _u8(self.fp),
                        "seconds": _u8(self.fp),
                        "frames": _u8(self.fp),
                        "fractional_frames": _u8(self.fp),
                    })
                elif meta_type == _midi.MetaType.TIME_SIGNATURE:
                    if data_length != 4:
                        raise ValueError("MetaType.TIME_SIGNATURE events should have a data length of 4.")
                    event_data.update({
                        "numerator": _u8(self.fp),
                        "denominator": 2 ** _u8(self.fp),  # given in powers of 2.
                        "midi_clocks_per_metronome_tick": _u8(self.fp),
                        "number_of_32nd_notes_per_beat": _u8(self.fp),  # almost always 8
                    })
                elif meta_type == _midi.MetaType.KEY_SIGNATURE:
                    def get_key_signature(sharps_flats, major_minor):
                        keys = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F",
                                "C", "G", "D", "A", "E", "B", "F#",
                                "C#", "G#", "D#", "A#"]
                        return keys[sharps_flats + 7 + major_minor * 3] + "m" * major_minor

                    event_data.update({"key": get_key_signature(*_struct.unpack("<bB", self.fp.read(2)))})
                else:
                    if data_length:
                        event_data.update({"bytes": [_u8(self.fp) for _ in range(data_length)]})
            else:
                running_status = event_type
                channel = event_type & 0xf
                event_type &= 0xf0
                if event_type == _midi.EventType.NOTE_OFF:
                    event_data = {
                        "note": _u8(self.fp),
                        "velocity": _u8(self.fp),
                    }
                elif event_type == _midi.EventType.NOTE_ON:
                    event_data = {
                        "note": _u8(self.fp),
                        "velocity": _u8(self.fp),
                    }
                elif event_type == _midi.EventType.POLYPHONIC_KEY_PRESSURE:
                    event_data = {
                        "note": _u8(self.fp),
                        "pressure": _u8(self.fp),
                    }
                elif event_type == _midi.EventType.CONTROLLER_CHANGE:
                    event_data = {
                        "controller": _midi.ControllerType(_u8(self.fp)),
                        "value": _u8(self.fp),
                    }
                elif event_type == _midi.EventType.PROGRAM_CHANGE:
                    event_data = {
                        "program": _u8(self.fp),
                    }
                elif event_type == _midi.EventType.CHANNEL_KEY_PRESSURE:
                    event_data = {
                        "pressure": _u8(self.fp),
                    }
                elif event_type == _midi.EventType.PITCH_BEND:
                    value = (_u8(self.fp) + _u8(self.fp) * 0x80) - 0x2000
                    event_data = {
                        "value": _utils.clamp(value / float(0x1fff), -1.0, 1.0),
                    }
                else:
                    raise ValueError(f"Unsupported MIDI event code: 0x{event_type:x}")

            # Create the event instance.
            event_type = _midi.EventType(event_type)
            events.append(_midi.SongEvent(track_number, event_time / self._division, event_type, event_data, channel,
                                          channel == _PERCUSSION_CHANNEL))
        return events

    @property
    def event_count(self) -> int:
        """Returns the number of events in the file.

        :return: An integer greater than 0.
        """
        return len(self._events)

    def get_event(self, index: int) -> _midi.SongEvent:
        """Returns the song event for the given index.
        Implementations must be able to retrieve events in an arbitrary order, not just file order.

        :param index: The index of the event to return.
        :return: A list of song events.
        :exception ValueError: When file data is not recognized.
        """
        return self._events[index]

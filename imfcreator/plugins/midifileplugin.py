import logging as _logging
import os as _os
import struct as _struct
import typing as _typing
import imfcreator.midi as _midi
import imfcreator.plugins._binary as _binary
from . import FileTypeInfo, MidiSongFile, plugin
from ._songbuilder import SongBuilder as _SongBuilder

_HEADER_CHUNK_NAME = b"MThd"
_HEADER_CHUNK_LENGTH = 6
_TRACK_CHUNK_NAME = b"MTrk"
_PERCUSSION_CHANNEL = 9


def _u8(f):
    """Read the next byte as an ordinal."""
    return _binary.u8(f.read(1))


@plugin
class MidiFile(MidiSongFile):
    """Reads a MIDI file."""

    def __init__(self, fp=None, filename=None):
        self._division = 0.0
        super().__init__(fp, filename)

    @classmethod
    def _get_filetypes(cls) -> _typing.List[FileTypeInfo]:
        return [
            FileTypeInfo("midi", "MIDI File", "mid")
        ]

    @classmethod
    def accept(cls, preview: bytes, file: str) -> bool:
        return preview[0:4] == _HEADER_CHUNK_NAME and _binary.u32be(preview[4:8]) == _HEADER_CHUNK_LENGTH

    def _load_file(self):
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
        for track_number in range(track_count):
            chunk_name, chunk_length = self._read_chunk_header()
            if chunk_name != _TRACK_CHUNK_NAME:
                _logging.info(f"Skipping unrecognized chunk: {chunk_name}.")
                self.fp.seek(chunk_length, _os.SEEK_CUR)
            else:
                self._read_events(chunk_length, track_number)

    def _read_chunk_header(self) -> (str, int):
        """Returns the chunk name and length at the current file position or None if at the end of the file."""
        chunk_name = self.fp.read(4)
        if not chunk_name:
            return None
        chunk_length = _binary.u32be(self.fp.read(4))
        return chunk_name, chunk_length

    def _read_events(self, chunk_length: int, track_number: int):
        """Reads all of the events in a track chunk."""
        builder = _SongBuilder(self._division, track_number)
        running_status = None
        chunk_end = self.fp.tell() + chunk_length
        while self.fp.tell() < chunk_end:
            # Read a MIDI event at the current file position.
            builder.add_time(_binary.read_midi_var_length(self.fp))
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
            # Read event type data
            if event_type in [_midi.EventType.F0_SYSEX, _midi.EventType.F7_SYSEX]:
                data_length = _binary.read_midi_var_length(self.fp)
                builder.add_sysex_data(event_type, self.fp.read(data_length))
            elif event_type == _midi.EventType.META:
                # PyCharm bug - https://youtrack.jetbrains.com/issue/PY-42287
                # noinspection PyArgumentList
                meta_type = _midi.MetaType(_u8(self.fp))
                # event_data = {"meta_type": meta_type}
                data_length = _binary.read_midi_var_length(self.fp)
                if meta_type == _midi.MetaType.SEQUENCE_NUMBER:
                    if data_length != 2:
                        raise ValueError("MetaType.SEQUENCE_NUMBER events should have a data length of 2.")
                    builder.add_meta_sequence_number(_binary.u16be(self.fp.read(2)))
                elif meta_type in [_midi.MetaType.TEXT_EVENT,
                                   _midi.MetaType.COPYRIGHT,
                                   _midi.MetaType.TRACK_NAME,
                                   _midi.MetaType.INSTRUMENT_NAME,
                                   _midi.MetaType.LYRIC,
                                   _midi.MetaType.MARKER,
                                   _midi.MetaType.CUE_POINT,
                                   _midi.MetaType.PROGRAM_NAME,
                                   _midi.MetaType.DEVICE_NAME]:
                    builder.add_meta_text_event(meta_type, self.fp.read(data_length))
                elif meta_type == _midi.MetaType.CHANNEL_PREFIX:
                    if data_length != 1:
                        raise ValueError("MetaType.CHANNEL_PREFIX events should have a data length of 1.")
                    builder.add_meta_channel_prefix(_u8(self.fp))
                elif meta_type == _midi.MetaType.PORT:
                    if data_length != 1:
                        raise ValueError("MetaType.PORT events should have a data length of 1.")
                    builder.add_meta_port(_u8(self.fp))
                elif meta_type == _midi.MetaType.SET_TEMPO:
                    if data_length != 3:
                        raise ValueError("MetaType.SET_TEMPO events should have a data length of 3.")
                    speed = (_u8(self.fp) << 16) + (_u8(self.fp) << 8) + _u8(self.fp)
                    builder.set_tempo(60000000 / speed)  # 60 seconds as microseconds
                elif meta_type == _midi.MetaType.SMPTE_OFFSET:
                    if data_length != 5:
                        raise ValueError("MetaType.SMPTE_OFFSET events should have a data length of 5.")
                    builder.add_meta_smpte_offset(hours=_u8(self.fp),
                                                  minutes=_u8(self.fp),
                                                  seconds=_u8(self.fp),
                                                  frames=_u8(self.fp),
                                                  fractional_frames=_u8(self.fp))
                elif meta_type == _midi.MetaType.TIME_SIGNATURE:
                    if data_length != 4:
                        raise ValueError("MetaType.TIME_SIGNATURE events should have a data length of 4.")
                    builder.set_time_signature(numerator=_u8(self.fp),
                                               denominator=2 ** _u8(self.fp),  # given in powers of 2.
                                               midi_clocks_per_metronome_tick=_u8(self.fp),
                                               number_of_32nd_notes_per_beat=_u8(self.fp))  # almost always 8
                elif meta_type == _midi.MetaType.KEY_SIGNATURE:
                    if data_length != 2:
                        raise ValueError("MetaType.KEY_SIGNATURE events should have a data length of 2.")
                    sharps_flats, major_minor = _struct.unpack("<bB", self.fp.read(2))
                    builder.set_key_signature(sharps_flats, major_minor)
                else:
                    builder.add_meta_event(meta_type, {"data": self.fp.read(data_length)} if data_length else None)
            else:
                running_status = event_type
                channel = event_type & 0xf
                event_type &= 0xf0
                if event_type == _midi.EventType.NOTE_OFF:
                    builder.note_off(channel, note=_u8(self.fp), velocity=_u8(self.fp))
                elif event_type == _midi.EventType.NOTE_ON:
                    builder.note_on(channel, note=_u8(self.fp), velocity=_u8(self.fp))
                elif event_type == _midi.EventType.POLYPHONIC_KEY_PRESSURE:
                    builder.change_polyphonic_key_pressure(channel, note=_u8(self.fp), pressure=_u8(self.fp))
                elif event_type == _midi.EventType.CONTROLLER_CHANGE:
                    # PyCharm bug - https://youtrack.jetbrains.com/issue/PY-42287
                    # noinspection PyArgumentList
                    builder.change_controller(channel,
                                              controller=_midi.ControllerType(_u8(self.fp)),
                                              value=_u8(self.fp))
                elif event_type == _midi.EventType.PROGRAM_CHANGE:
                    builder.set_instrument(channel, program=_u8(self.fp))
                elif event_type == _midi.EventType.CHANNEL_KEY_PRESSURE:
                    builder.set_channel_key_pressure(channel, pressure=_u8(self.fp))
                elif event_type == _midi.EventType.PITCH_BEND:
                    value = (_u8(self.fp) + (_u8(self.fp) << 7))
                    builder.pitch_bend(channel, amount=_midi.balance_14bit(value))
                else:
                    raise ValueError(f"Unsupported MIDI event code: 0x{event_type:x}")
        self.events.extend(builder.events)

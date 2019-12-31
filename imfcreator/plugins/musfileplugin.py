import logging as _logging
import os as _os
import struct as _struct
import typing as _typing
import imfcreator.midi as _midi
import imfcreator.plugins._binary as _binary
from enum import IntEnum as _IntEnum
from . import MidiSongFile, plugin

_SIGNATURE = b"MUS\x1a"


# Event types
class EventType(_IntEnum):
    RELEASE_NOTE = 0
    PLAY_NOTE = 1
    PITCH_BEND = 2
    SYSTEM = 3
    CONTROLLER = 4
    END_OF_MEASURE = 5
    FINISH = 6
    UNUSED = 7


class SystemEventType(_IntEnum):
    ALL_SOUNDS_OFF = 10  # MIDI CC 120 - All sounds off (notes will silence immediately)
    ALL_NOTES_OFF = 11  # MIDI CC 123 - All notes off (notes will fade out)
    MONO = 12  # MIDI CC 126 - Mono (one note per channel)
    POLY = 13  # MIDI CC 127 - Poly (multiple notes per channel)
    RESET = 14  # MIDI CC 121 - Reset all controllers on this channel
    # 15 	- 	"Event" (never implemented)


class ControllerType(_IntEnum):
    CHANGE_INSTRUMENT = 0  # MIDI event 0xC0 - Change instrument
    BANK_SELECT = 1  # MIDI CC 0 or 32 - Bank select: 0 by default
    MODULATION = 2  # MIDI CC 1 - Modulation (frequency vibrato depth)
    VOLUME = 3  # MIDI CC 7 - Volume: 0-silent, ~100-normal, 127-loud
    PAN = 4  # MIDI CC 10 - Pan (balance): 0-left, 64-center (default), 127-right
    EXPRESSION = 5  # MIDI CC 11 - Expression
    REVERB_DEPTH = 6  # MIDI CC 91 - Reverb depth
    CHORUS_DEPTH = 7  # MIDI CC 93 - Chorus depth
    SUSTAIN_PEDAL = 8  # MIDI CC 64 - Sustain pedal (hold)
    SOFT_PEDAL = 9  # MIDI CC 67 - Soft pedal


def _u8(f):
    """Read the next byte as an ordinal."""
    return _binary.u8(f.read(1))


@plugin
class MusFile(MidiSongFile):
    """Reads a MIDI file."""

    PERCUSSION_CHANNEL = 15

    def __init__(self, fp=None, filename=None):
        self._division = 0.0
        super().__init__(fp, filename)

    @classmethod
    def accept(cls, preview: bytes, file: str) -> bool:
        return preview[0:4] == _SIGNATURE

    def _load_file(self):
        """Loads a MIDI file into the reader object."""
        signature = self.fp.read(4)
        if signature != _SIGNATURE:
            raise ValueError(f"Unexpected file signature: {signature}")
        # Read header.
        song_length = _binary.u16le(self.fp.read(2))
        song_offset = _binary.u16le(self.fp.read(2))
        # None of this is needed.
        # primary_channel_count = _binary.u16le(self.fp.read(2))
        # secondary_channel_count = _binary.u16le(self.fp.read(2))
        # instrument_count = _binary.u16le(self.fp.read(2))
        # self.fp.read(2)  # reserved
        # instruments = [_binary.u16le(self.fp.read(2)) for _ in range(instrument_count)]
        # Read song data.
        self._read_song_data(song_offset, song_length)

    def _read_song_data(self, song_offset: int, song_length: int):
        """Reads all of the events in a track chunk."""

        def _read_var_length():
            """Reads a length using MIDI's variable length format."""
            length = 0
            b = _u8(self.fp)
            while b & 0x80:
                length = length * 0x80 + (b & 0x7f)
                b = _u8(self.fp)
            return length * 0x80 + b

        channel_volume = [127] * 16  # Start full volume.
        playback_rate = 140.0  # TODO 70.0 for Raptor.

        self.events.append(_midi.SongEvent(len(self.events), 0, 0, _midi.EventType.META, data={
            "meta_type": _midi.MetaType.SET_TEMPO,
            "bpm": 60.0,
        }))

        self.fp.seek(song_offset)
        song_end = song_offset + song_length
        event_time = 0
        while self.fp.tell() < song_end:
            event_data = {}  # type: dict
            data_byte = _u8(self.fp)
            has_delay = (data_byte & 0x80)
            event_type = (data_byte & 0x70) >> 4
            channel = data_byte & 0x0f
            midi_event_type = 0
            # print(has_delay, event_type, channel)
            if event_type == EventType.RELEASE_NOTE:
                note_number = _u8(self.fp)
                # Convert to MIDI
                midi_event_type = _midi.EventType.NOTE_OFF
                event_data = {
                    "note": note_number,
                    "velocity": 127,
                }
            elif event_type == EventType.PLAY_NOTE:
                data_byte = _u8(self.fp)
                note_number = data_byte & 0x7f
                if data_byte & 0x80:
                    channel_volume[channel] = _u8(self.fp)
                # Convert to MIDI
                midi_event_type = _midi.EventType.NOTE_ON
                event_data = {
                    "note": note_number,
                    "velocity": channel_volume[channel],
                }
            elif event_type == EventType.PITCH_BEND:
                amount = _binary.u8(self.fp.read(1)) - 0x80
                amount = amount / (128.0 if amount < 0 else 127.0)
                midi_event_type = _midi.EventType.PITCH_BEND
                event_data = {"amount" : amount}
            elif event_type == EventType.SYSTEM:
                system_controller = _u8(self.fp)
                if system_controller == SystemEventType.ALL_SOUNDS_OFF:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.ALL_SOUND_OFF,
                        "value": 0
                    }
                elif system_controller == SystemEventType.ALL_NOTES_OFF:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.ALL_NOTES_OFF,
                        "value": 0
                    }
                elif system_controller == SystemEventType.MONO:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.MONOPHONIC_MODE,
                        "value": 0
                    }
                elif system_controller == SystemEventType.POLY:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.POLYPHONIC_MODE,
                        "value": 0
                    }
                elif system_controller == SystemEventType.RESET:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.RESET_ALL_CONTROLLERS,
                        "value": 0
                    }
            elif event_type == EventType.CONTROLLER:
                controller = _u8(self.fp)
                value = _u8(self.fp) & 0x7f
                if controller == ControllerType.CHANGE_INSTRUMENT:
                    if channel != MusFile.PERCUSSION_CHANNEL:
                        midi_event_type = _midi.EventType.PROGRAM_CHANGE
                        event_data = {"program": value}
                elif controller == ControllerType.BANK_SELECT:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.BANK_SELECT_MSB,
                        "value": value
                    }
                elif controller == ControllerType.MODULATION:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.MODULATION_WHEEL_MSB,
                        "value": value
                    }
                elif controller == ControllerType.VOLUME:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.VOLUME_MSB,
                        "value": value
                    }
                elif controller == ControllerType.PAN:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.PAN_MSB,
                        "value": value
                    }
                elif controller == ControllerType.EXPRESSION:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.EXPRESSION_MSB,
                        "value": value
                    }
                elif controller == ControllerType.REVERB_DEPTH:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.REVERB_DEPTH,
                        "value": value
                    }
                elif controller == ControllerType.CHORUS_DEPTH:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.CHORUS_DEPTH,
                        "value": value
                    }
                elif controller == ControllerType.SUSTAIN_PEDAL:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.SUSTAIN_PEDAL_SWITCH,
                        "value": value
                    }
                elif controller == ControllerType.SOFT_PEDAL:
                    midi_event_type = _midi.EventType.CONTROLLER_CHANGE
                    event_data = {
                        "controller": _midi.ControllerType.SOFT_PEDAL_SWITCH,
                        "value": value
                    }
            elif event_type == EventType.END_OF_MEASURE:
                pass
            elif event_type == EventType.FINISH:
                midi_event_type = _midi.EventType.META
                event_data = {"meta_type": _midi.MetaType.END_OF_TRACK}
                channel = None
            elif event_type == EventType.UNUSED:
                self.fp.read(1)
            if midi_event_type:
                midi_event_type = _midi.EventType(midi_event_type)
                self.events.append(_midi.SongEvent(len(self.events), 0, event_time / float(playback_rate),
                                                   midi_event_type, event_data, channel))
            if event_type == EventType.FINISH:
                break
            if has_delay:
                event_time += _read_var_length()

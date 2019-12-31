import imfcreator.midi as _midi
import imfcreator.plugins._binary as _binary
from enum import IntEnum as _IntEnum
from . import MidiSongFile, plugin
from ._songbuilder import SongBuilder as _SongBuilder

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

        channel_volume = [127] * 16  # Start full volume.
        playback_rate = 140.0  # TODO 70.0 for Raptor.

        builder = _SongBuilder(playback_rate)
        builder.set_tempo(60.0)

        self.fp.seek(song_offset)
        song_end = song_offset + song_length
        while self.fp.tell() < song_end:
            data_byte = _u8(self.fp)
            has_delay = (data_byte & 0x80)
            event_type = (data_byte & 0x70) >> 4
            channel = data_byte & 0x0f
            # Process the event.
            if event_type == EventType.RELEASE_NOTE:
                note_number = _u8(self.fp)
                builder.note_off(channel, note_number, 127)
            elif event_type == EventType.PLAY_NOTE:
                data_byte = _u8(self.fp)
                note_number = data_byte & 0x7f
                if data_byte & 0x80:
                    channel_volume[channel] = _u8(self.fp)
                builder.note_on(channel, note_number, channel_volume[channel])
            elif event_type == EventType.PITCH_BEND:
                amount = _binary.u8(self.fp.read(1)) - 0x80
                amount = amount / (128.0 if amount < 0 else 127.0)
                builder.pitch_bend(channel, amount)
            elif event_type == EventType.SYSTEM:
                system_controller = _u8(self.fp)
                if system_controller == SystemEventType.ALL_SOUNDS_OFF:
                    builder.change_controller(channel, _midi.ControllerType.ALL_SOUND_OFF, 0)
                elif system_controller == SystemEventType.ALL_NOTES_OFF:
                    builder.change_controller(channel, _midi.ControllerType.ALL_NOTES_OFF, 0)
                elif system_controller == SystemEventType.MONO:
                    builder.change_controller(channel, _midi.ControllerType.MONOPHONIC_MODE, 0)
                elif system_controller == SystemEventType.POLY:
                    builder.change_controller(channel, _midi.ControllerType.POLYPHONIC_MODE, 0)
                elif system_controller == SystemEventType.RESET:
                    builder.change_controller(channel, _midi.ControllerType.RESET_ALL_CONTROLLERS, 0)
            elif event_type == EventType.CONTROLLER:
                controller = _u8(self.fp)
                value = _u8(self.fp)
                if controller == ControllerType.CHANGE_INSTRUMENT:
                    builder.set_instrument(channel, value)
                elif controller == ControllerType.BANK_SELECT:
                    builder.select_bank(channel, value)
                elif controller == ControllerType.MODULATION:
                    builder.set_modulation_wheel(channel, value)
                elif controller == ControllerType.VOLUME:
                    builder.set_volume(channel, value)
                elif controller == ControllerType.PAN:
                    builder.set_pan(channel, value)
                elif controller == ControllerType.EXPRESSION:
                    builder.set_expression(channel, value)
                elif controller == ControllerType.REVERB_DEPTH:
                    builder.change_controller(channel, _midi.ControllerType.REVERB_DEPTH, value)
                elif controller == ControllerType.CHORUS_DEPTH:
                    builder.change_controller(channel, _midi.ControllerType.CHORUS_DEPTH, value)
                elif controller == ControllerType.SUSTAIN_PEDAL:
                    builder.change_controller(channel, _midi.ControllerType.SUSTAIN_PEDAL_SWITCH, value)
                elif controller == ControllerType.SOFT_PEDAL:
                    builder.change_controller(channel, _midi.ControllerType.SOFT_PEDAL_SWITCH, value)
            elif event_type == EventType.END_OF_MEASURE:
                builder.add_marker("End of measure")
                pass
            elif event_type == EventType.FINISH:
                builder.add_end_of_track()
                break
            elif event_type == EventType.UNUSED:
                self.fp.read(1)
            if has_delay:
                builder.add_time(_binary.read_midi_var_length(self.fp))
        self.events = builder.events

import logging as _logging
import math as _math
import struct as _struct
import typing as _typing
import imfcreator.instruments as instruments
import imfcreator.midi as _midi
import imfcreator.utils as _utils
from . import AdlibSongFile, FileTypeInfo, plugin
from collections import namedtuple as _namedtuple
from imfcreator.adlib import *

_ActiveNote = _namedtuple("_ActiveNote", ["note", "song_event"])


@plugin
class ImfSong(AdlibSongFile):
    _MAXIMUM_COMMAND_COUNT = 65535 // 4
    _TAG_BYTE = b"\x1a"

    def __init__(self, filetype: str = "imf1", ticks: int = None, title: str = None, composer: str = None,
                 remarks: str = None, program: str = None):
        self._filetype = filetype
        self._ticks = None
        self.ticks = ticks if ticks else 560 if filetype == "imf0" else 700
        self.title = title
        self.composer = composer
        self.remarks = remarks
        self.program = program if program else "PyImf" if (self.title or self.composer or self.remarks) else None
        if (self.title or self.composer or self.remarks or self.program) and filetype == "imf0":
            _logging.warning(f"The title, composer, remarks, and program settings are not used by type '{filetype}'.")
        # self._filetype = None
        # self.ticks = None
        # self.title = None
        # self.composer = None
        # self.remarks = None
        # self.program = None
        self._commands = []  # type: _typing.List[_typing.Tuple[int, int, int]]  # reg, value, delay

    @property
    def ticks(self):
        return self._ticks

    @ticks.setter
    def ticks(self, value):
        if value not in [280, 560, 700]:
            raise ValueError("Invalid ticks value.  Must be 280, 560, or 700.")
        self._ticks = value

    @property
    def command_count(self):
        """Returns the number of commands."""
        return len(self._commands)

    @classmethod
    def _get_filetypes(cls) -> _typing.Dict[str, str]:
        return {
            "imf0": FileTypeInfo("IMF Type 0", "imf"),
            "imf1": FileTypeInfo("IMF Type 1", "wlf"),
        }

    @classmethod
    def _get_settings(cls) -> _typing.Dict[str, str]:
        return {
            "ticks": "The song speed.  Must be 280, 560, or 700 depending on the game.",
            "title": "The song title.  Only stored in type 1 files.  Limited to 255 characters.",
            "composer": "The song composer.  Only stored in type 1 files.  Limited to 255 characters.",
            "remarks": "The song remarks.  Only stored in type 1 files.  Limited to 255 characters.",
            "program": "The program used to make the song.  Only stored in type 1 files.  Limited to 8 characters.  "
                       "Defaults to 'PyImf' if title, composer, or remarks are set.",
        }

    @classmethod
    def accept(cls, preview: bytes, filename: str) -> bool:
        return _utils.get_file_extension(filename).lower() in ["imf", "wlf"]

    @classmethod
    def _open_file(cls, fp, filename) -> "ImfSong":
        pass

    def _save_file(self, fp, filename):
        command_count = self.command_count
        if self._filetype == "imf1":
            # IMF Type 1 is limited to a 2-byte unsigned data length.
            if command_count > ImfSong._MAXIMUM_COMMAND_COUNT:
                _logging.warning(f"IMF file overflow.  Total commands: {command_count}; "
                                 f"Written commands: {ImfSong._MAXIMUM_COMMAND_COUNT})")
                command_count = ImfSong._MAXIMUM_COMMAND_COUNT
            fp.write(_struct.pack("<H", command_count * 4))
        for command in self._commands[0:command_count]:
            fp.write(_struct.pack("<BBH", *command))
        # Add unofficial tag for type 1 files.
        if self._filetype == "imf1" and (self.title or self.composer or self.remarks or self.program):
            fp.write(ImfSong._TAG_BYTE)
            if self.title:
                fp.write(bytearray(self.title, "ascii")[0:255])
            fp.write(b"\x00")
            if self.composer:
                fp.write(bytearray(self.composer, "ascii")[0:255])
            fp.write(b"\x00")
            if self.remarks:
                fp.write(bytearray(self.remarks, "ascii")[0:255])
            fp.write(b"\x00")
            # Padded to 8 bytes + 1 null terminator.
            fp.write((bytearray(self.program if self.program else "", "ascii") + b"\x00" * 8)[0:8])
            fp.write(b"\x00")

    @classmethod
    def _convert_from(cls, events: _typing.Iterable[_midi.SongEvent], filetype: str,
                      settings: _typing.Dict) -> "ImfSong":
        # Load settings.
        song = ImfSong(filetype, **settings)
        # Set up variables.
        # events = sorted([_ for _ in events])
        midi_channels = [_MidiChannelInfo(ch) for ch in range(16)]
        imf_channels = [_ImfChannelInfo(ch) for ch in range(1, 9)]
        regs = [None] * 256
        ticks_per_beat = 0
        last_ticks = 0

        # Define helper functions.
        def set_tempo(bpm: float):
            nonlocal ticks_per_beat
            ticks_per_beat = song.ticks * (60.0 / bpm)

        def calc_imf_ticks(value):
            return int(ticks_per_beat * value)

        # noinspection PyUnusedLocal
        def find_imf_channel(instrument, note):
            # Find a channel that is set to the given instrument and is not currently playing a note.
            channel = next(filter(lambda ch: ch.instrument == instrument and ch.last_note is None, imf_channels), None)
            if channel:
                return channel
            # Find a channel that isn't playing a note.
            channel = next(filter(lambda ch: ch.last_note is None, imf_channels), None)
            if channel:
                return channel
            # TODO Aggressive channel find.
            return None

        def add_command(reg: int, value: int, delay: int = 0):
            """Adds a command to the song."""
            nonlocal regs
            if regs[reg] == value:
                return
            try:
                assert 0 <= reg <= 0xff
                assert 0 <= value <= 0xff
                assert 0 <= delay <= 0xffff
            except AssertionError:
                _logging.error(f"Value out of range! 0x{reg:x}, 0x{value:x}, {delay}, cmd: {len(song._commands)}")
                raise
            regs[reg] = value
            song._commands.append((reg, value, delay))

        def get_block_and_freq(note, scaled_pitch_bend):
            assert note < 128
            while note >= len(BLOCK_FREQ_NOTE_MAP):
                note -= 12
            block, freq = BLOCK_FREQ_NOTE_MAP[note]
            # Adjust for pitch bend.
            # The octave adjustment relies heavily on how the BLOCK_FREQ_NOTE_MAP has been calculated.
            # F# is close to the top of the 1023 limit while G is in the middle at 517. Because of this,
            # bends that cross over the line between F# and G are better handled in the range below G and the
            # lower block/freq is adjusted upward so that it is in the same block as the other note.
            # For each increment of 1 to the block, the f-num needs to be halved.  This can lead to a loss of
            # precision, but hopefully it won't be too drastic.
            if scaled_pitch_bend < 0:
                semitones = int(_math.floor(scaled_pitch_bend))
                bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note + semitones]
                # If the bend-to note is on a lower block/octave, multiply the *bend-to* f-num by 0.5 per block
                # to bring it up to the same block as the original note.
                # assert not (bend_block == 1 and block == 0 and note == 18 and semitones == -1)
                if bend_block < block:
                    bend_freq /= (2.0 ** (block - bend_block))
                freq = int(freq + (bend_freq - freq) * scaled_pitch_bend / semitones)
            elif scaled_pitch_bend > 0:
                semitones = int(_math.ceil(scaled_pitch_bend))
                bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note + semitones]
                # If the bend-to note is on a higher block/octave, multiply the *original* f-num by 0.5 per block
                # to bring it up to the same block as the bend-to note.
                if bend_block > block:
                    freq /= (2.0 ** (bend_block - block))
                    block = bend_block
                freq = int(freq + (bend_freq - freq) * scaled_pitch_bend / semitones)
            assert 0 <= block <= 7
            assert 0 <= freq <= 0x3ff
            return block, freq

        def find_imf_channel_for_instrument_note(instrument, note):
            return next(filter(lambda ch: ch.instrument == instrument and ch.last_note == note, imf_channels), None)

        def note_off(song_event: _midi.SongEvent):
            instrument = get_event_instrument(song_event)
            if instrument is None:
                return None
            commands = []
            voice = 0
            midi_channel = midi_channels[song_event.channel]
            note = get_instrument_note(instrument, song_event, voice)
            if song_event.channel != 9:
                match = next(filter(lambda note_info: note_info.song_event["note"] == song_event['note'],
                                    midi_channel.active_notes), None)  # type: _ActiveNote
                if match:
                    note = match.note
                    # inst_num = match["inst_num"]
                    midi_channel.active_notes.remove(match)
                else:
                    raise ValueError(f"Tried to remove non-active note: track {song_event.track}, note {note}")
            channel = find_imf_channel_for_instrument_note(instrument, note)
            if channel:
                channel.last_note = None
                # block, freq = get_block_and_freq(event)
                commands += [
                    # (BLOCK_MSG | channel.number, KEY_OFF_MASK | (block << 2) | (freq >> 8)),
                    # (BLOCK_MSG | channel.number, KEY_OFF_MASK),
                    (BLOCK_MSG | channel.number, regs[BLOCK_MSG | channel.number] & ~KEY_ON_MASK),
                    # Release notes quickly.
                    # (SUSTAIN_RELEASE_MSG | MODULATORS[channel.number], 0xf),
                    # (SUSTAIN_RELEASE_MSG | CARRIERS[channel.number], 0xf),
                ]
            # else:
            #     print(f"Could not find note to shut off! inst: {inst_num}, note: {note}")
            return commands

        def get_event_instrument(song_event: _midi.SongEvent) -> AdlibInstrument:
            # TODO banks support
            bank = 0
            if song_event.is_percussion:
                # _logging.debug(f"Searching for PERCUSSION instrument {event['note']}")
                return instruments.get(instruments.PERCUSSION, bank, song_event["note"])
            else:
                midi_channel = midi_channels[song_event.channel]
                inst_num = midi_channel.instrument
                if inst_num is None:
                    _logging.warning(f"No instrument assigned to channel {song_event.channel}, defaulting to 0.")
                    midi_channel.instrument = 0
                    inst_num = 0
                # _logging.debug(f"Searching for MELODIC instrument {inst_num}")
                return instruments.get(instruments.MELODIC, bank, inst_num)

        def get_instrument_note(instrument: AdlibInstrument, song_event: _midi.SongEvent, voice: int = 0):
            note = song_event["note"]
            if instrument.use_given_note:
                note = instrument.given_note
            note += instrument.note_offset[voice]
            if note < 0 or note > 127:
                _logging.error(f"Note out of range: {song_event}")
                note = 60
            return note

        def get_volume_commands(channel, instrument, midi_volume, voice=0):
            volume_table = [
                0, 1, 3, 5, 6, 8, 10, 11,
                13, 14, 16, 17, 19, 20, 22, 23,
                25, 26, 27, 29, 30, 32, 33, 34,
                36, 37, 39, 41, 43, 45, 47, 49,
                50, 52, 54, 55, 57, 59, 60, 61,
                63, 64, 66, 67, 68, 69, 71, 72,
                73, 74, 75, 76, 77, 79, 80, 81,
                82, 83, 84, 84, 85, 86, 87, 88,
                89, 90, 91, 92, 92, 93, 94, 95,
                96, 96, 97, 98, 99, 99, 100, 101,
                101, 102, 103, 103, 104, 105, 105, 106,
                107, 107, 108, 109, 109, 110, 110, 111,
                112, 112, 113, 113, 114, 114, 115, 115,
                116, 117, 117, 118, 118, 119, 119, 120,
                120, 121, 121, 122, 122, 123, 123, 123,
                124, 124, 125, 125, 126, 126, 127, 127
            ]
            if midi_volume > 127:
                midi_volume = 127

            def get_operator_volume(op_volume):
                n = 0x3f - (op_volume & 0x3f)
                n = (n * volume_table[midi_volume]) >> 7
                return 0x3f - n
                # return op_volume

            if (instrument.feedback[voice] & 0x01) == 1:  # When AM, scale both operators
                return [
                    (
                        VOLUME_MSG | MODULATORS[channel.number],
                        get_operator_volume(instrument.modulator[voice].output_level)
                        | (instrument.modulator[voice].key_scale_level << 6)
                    ),
                    (
                        VOLUME_MSG | CARRIERS[channel.number],
                        get_operator_volume(instrument.carrier[voice].output_level)
                        | (instrument.carrier[voice].key_scale_level << 6)
                    ),
                ]
            else:  # When FM, scale carrier only, keep modulator as-is
                return [
                    (
                        VOLUME_MSG | MODULATORS[channel.number],
                        instrument.modulator[voice].output_level & 0x3f
                        | (instrument.modulator[voice].key_scale_level << 6)
                    ),
                    (
                        VOLUME_MSG | CARRIERS[channel.number],
                        get_operator_volume(instrument.carrier[voice].output_level)
                        | (instrument.carrier[voice].key_scale_level << 6)
                    ),
                ]

        def note_on(song_event: _midi.SongEvent):
            instrument = get_event_instrument(song_event)
            if instrument is None:
                return None
            voice = 0
            midi_channel = midi_channels[song_event.channel]
            note = get_instrument_note(instrument, song_event, voice)
            if song_event.channel != 9:
                # _logging.debug(f"Adding active note: {event['note']} -> {note}, channel {event.channel}")
                midi_channel.active_notes.append(_ActiveNote(note, song_event))
            commands = []
            channel = find_imf_channel(instrument, note)
            if channel:
                # Check for instrument change.
                # instrument = instruments[inst_num]
                if channel.instrument != instrument:
                    # Removed volume messages. Volume will initialize to OFF.
                    commands += [cmd for cmd in instrument.get_regs(channel.number, voice) if
                                 (cmd[0] & 0xf0) != VOLUME_MSG]
                    commands += [
                        (VOLUME_MSG | MODULATORS[channel.number], 0x3f),
                        (VOLUME_MSG | CARRIERS[channel.number], 0x3f),
                    ]
                    # adlib_write_channel(0x20, slot,
                    #                     (instr[6] & 1) ? (instr[7] | state): instr[0],
                    #                                                          instr[7] | state);
                    # }
                    channel.instrument = instrument
                volume = int(midi_channel.volume * song_event["velocity"] / 127.0)
                channel.last_note = note
                block, freq = get_block_and_freq(note, midi_channel.scaled_pitch_bend)
                commands += get_volume_commands(channel, instrument, volume)
                commands += [
                    # (
                    #     VOLUME_MSG | MODULATORS[channel.number],
                    #     ((127 - volume) / 2) | instrument.modulator[voice].key_scale_level
                    # ),
                    # (
                    #     VOLUME_MSG | CARRIERS[channel.number],
                    #     ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                    # ),
                    (FREQ_MSG | channel.number, freq & 0xff),
                    (BLOCK_MSG | channel.number, KEY_ON_MASK | (block << 2) | (freq >> 8)),
                ]
            # else:
            #     print(f"Could not find channel for note on! inst: {inst_num}, note: {note}")
            return commands

        def pitch_bend(song_event: _midi.SongEvent):
            # Can't pitch bend percussion.
            if song_event.is_percussion:
                return None
            commands = []
            amount = song_event["value"]  # - event["value"] % pitch_bend_resolution
            if midi_channels[song_event.channel].pitch_bend != amount:
                midi_channels[song_event.channel].pitch_bend = amount
                # Scale pitch bend to -1..1
                scaled_pitch_bend = amount  # / -pitch_bend_range[0] if amount < 0 else amount / pitch_bend_range[1]
                scaled_pitch_bend *= 2  # TODO Read from controller messages. 2 semi-tones is the default.
                midi_channels[song_event.channel].scaled_pitch_bend = scaled_pitch_bend
                instrument = get_event_instrument(song_event)  # midi_channels[event.channel]["instrument"]
                for note_info in midi_channels[song_event.channel].active_notes:
                    note = note_info.note
                    channel = find_imf_channel_for_instrument_note(instrument, note)
                    if channel:
                        block, freq = get_block_and_freq(note, scaled_pitch_bend)
                        commands += [
                            (FREQ_MSG | channel.number, freq & 0xff),
                            (BLOCK_MSG | channel.number, KEY_ON_MASK | (block << 2) | (freq >> 8)),
                        ]
                    else:
                        _logging.warning(f"Could not find Adlib channel for channel {song_event.channel} note {note}.")
            return commands

        def adjust_volume(song_event: _midi.SongEvent):
            # Can't adjust volume of active percussion.
            if song_event.is_percussion:
                return None
            commands = []
            # voice = 0
            midi_channel = midi_channels[song_event.channel]
            midi_channel.volume = song_event["value"]
            if midi_channel.active_notes:
                instrument = get_event_instrument(song_event)
                for note_info in midi_channel.active_notes:
                    channel = find_imf_channel_for_instrument_note(instrument, note_info.note)
                    if channel:
                        volume = int(midi_channel.volume * note_info.song_event["velocity"] / 127.0)
                        # instrument = instruments[inst_num]
                        commands += get_volume_commands(channel, instrument, volume)
                        # commands += [
                        #     (
                        #         VOLUME_MSG | MODULATORS[channel.number],
                        #         ((127 - volume) / 2) | instrument.modulator[voice].key_scale_level
                        #     ),
                        #     (
                        #         VOLUME_MSG | CARRIERS[channel.number],
                        #         ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                        #     ),
                        # ]
            return commands

        def add_delay(time):
            nonlocal last_ticks, song
            ticks = calc_imf_ticks(time - last_ticks)
            # noinspection PyProtectedMember
            song._commands[-1] = song._commands[-1][0:2] + (ticks,)
            last_ticks = time

        def process_events():
            for event in events:
                # TODO Perform muting
                # if mute_tracks:
                #     if event.track in mute_tracks:
                #         continue
                # if mute_channels:
                #     if event.channel in mute_channels:
                #         continue
                # Handle events.
                commands = None  # list of (reg, value) tuples.
                if event.type == _midi.EventType.NOTE_OFF or (
                        event.type == _midi.EventType.NOTE_ON and event["velocity"] == 0):
                    commands = note_off(event)
                elif event.type == _midi.EventType.NOTE_ON:
                    commands = note_on(event)
                elif event.type == _midi.EventType.CONTROLLER_CHANGE \
                        and event["controller"] == _midi.ControllerType.VOLUME_MSB:
                    commands = adjust_volume(event)
                elif event.type == _midi.EventType.PITCH_BEND:
                    commands = pitch_bend(event)
                elif event.type == _midi.EventType.PROGRAM_CHANGE:
                    midi_channels[event.channel].instrument = event["program"]
                elif event.type == _midi.EventType.META and event["meta_type"] == _midi.MetaType.SET_TEMPO:
                    set_tempo(float(event["bpm"]))
                if commands:
                    # Set the delay on the previous command.
                    add_delay(event.time)
                    # Now add the new commands
                    for command in commands:
                        add_command(*command)
            # Add any remaining delay to the final command for wrap-around timing.
            add_delay(max([event.time for event in events]))

        # Cycle MIDI events and convert to IMF commands.
        set_tempo(120)  # Arbitrary default tempo if none is set by the song.
        # ticks = 0
        # pitch_bend_resolution = 0x200
        # pitch_bend_range = (-8192.0 - -8192 % -pitch_bend_resolution, 8191.0 - 8191 % pitch_bend_resolution)
        song._commands += [
            (0, 0, 0),  # Always start with 0, 0, 0
            (0xBD, 0, 0),
            (0x8, 0, 0),
        ]
        process_events()
        for mc in midi_channels:
            if mc.active_notes:
                print(f"midi track {mc.number} had open notes: {mc.active_notes}")
        for ch in imf_channels:
            if ch.last_note:
                print(f"imf channel {ch.number} had open note: {ch.last_note}")

        return song


class _MidiChannelInfo:
    def __init__(self, number):
        self.number = number
        self.instrument = None
        self.volume = 127
        self.pitch_bend = 0
        self.scaled_pitch_bend = 0.0
        self.active_notes = []  # type: _typing.List[_ActiveNote]

    def add_active_note(self):
        pass

    def get_active_note(self):
        pass

    def remove_active_note(self):
        pass


class _ImfChannelInfo:
    def __init__(self, number):
        self.number = number
        self.instrument = None
        self.last_note = None

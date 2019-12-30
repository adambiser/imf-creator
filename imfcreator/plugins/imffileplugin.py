import logging as _logging
import math as _math
import struct as _struct
import typing as _typing
import imfcreator.instruments as instruments
import imfcreator.midi as _midi
import imfcreator.utils as _utils
import imfcreator.plugins._midiengine as _midiengine
from . import AdlibSongFile, FileTypeInfo, MidiSongFile, plugin
from imfcreator.adlib import *


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
        _logging.info(f"Writing {command_count} commands.")
        if self._filetype == "imf1":
            # IMF Type 1 is limited to a 2-byte unsigned data length.
            if command_count > ImfSong._MAXIMUM_COMMAND_COUNT:
                _logging.warning(f"IMF file overflow.  Total commands: {command_count}; "
                                 f"Written commands: {ImfSong._MAXIMUM_COMMAND_COUNT})")
                command_count = ImfSong._MAXIMUM_COMMAND_COUNT
            fp.write(_struct.pack("<H", command_count * 4))
        command_count = ImfSong._MAXIMUM_COMMAND_COUNT
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
    def _convert_from(cls, midi_song: MidiSongFile, filetype: str, settings: _typing.Dict) -> "ImfSong":
        # Load settings.
        song = cls(filetype, **settings)
        # Set up variables.
        engine = _midiengine.MidiEngine(midi_song)
        # midi_channels = [_MidiChannelInfo(ch) for ch in range(16)]
        imf_channels = [_ImfChannelInfo(ch) for ch in range(1, 9)]
        regs = [None] * 256

        # Tempo/delay related variables and methods.
        ticks_per_beat = 0
        last_command_ticks = 0  # The ticks at which the last IMF command occurred.
        tempo_start_time = 0.0  # The time, in beats, at which the last tempo change occurred.

        # Define helper functions.
        def set_tempo(event_time: float, bpm: float):
            nonlocal ticks_per_beat, tempo_start_time
            ticks_per_beat = song.ticks * (60.0 / bpm)
            tempo_start_time = event_time

        def on_tempo_change(song_event: _midiengine.TempoChangeMetaEvent):
            set_tempo(song_event.time, song_event.bpm)

        def add_delay(time: float, command_index: int):
            nonlocal last_command_ticks, song
            # To reduce rounding errors, calculate the ticks from the last tempo change and subtract the ticks at which
            # the last command took place.
            ticks = int(ticks_per_beat * (time - tempo_start_time))
            # PyCharm has an incorrect warning here.
            # noinspection PyTypeChecker
            song._commands[command_index] = song._commands[command_index][:2] + (ticks - last_command_ticks,)
            last_command_ticks = ticks

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

        def add_commands(event_time: float, commands):
            old_commands_length = len(song._commands)
            # Now add the new commands
            for command in commands:
                add_command(*command)
            if old_commands_length != len(song._commands):
                add_delay(event_time, old_commands_length - 1)

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

        def get_event_instrument(channel: int, note: int = 0) -> AdlibInstrument:
            midi_channel = engine.channels[channel]
            bank = midi_channel.bank
            if engine.is_percussion_channel(channel):
                # _logging.debug(f"Searching for PERCUSSION instrument {event['note']}")
                return instruments.get(instruments.PERCUSSION, bank, note)
            else:
                inst_num = midi_channel.instrument
                if inst_num is None:
                    _logging.warning(f"No instrument assigned to channel {channel}, defaulting to 0.")
                    midi_channel.instrument = 0
                    inst_num = 0
                # _logging.debug(f"Searching for MELODIC instrument {inst_num}")
                return instruments.get(instruments.MELODIC, bank, inst_num)

        def get_instrument_note(instrument: AdlibInstrument, note: int, voice: int = 0):
            if instrument.use_given_note:
                note = instrument.given_note
            note += instrument.note_offset[voice]
            if note < 0 or note > 127:
                _logging.error(f"Note out of range: {note}")
                note = 60
            return note

        def get_volume_commands(imf_channel: _ImfChannelInfo, instrument: AdlibInstrument,
                                midi_channel: _midiengine.MidiChannelInfo, note_velocity: int, voice: int = 0):
            # https://github.com/lantus/Strife/blob/master/i_oplmusic.c#L288
            # https://github.com/chocolate-doom/chocolate-doom/blob/master/src/i_oplmusic.c#L285
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
            midi_volume = int(midi_channel.volume * midi_channel.expression * note_velocity)
            # if midi_volume > 127:
            #     midi_volume = 127
            midi_brightness = midi_channel.get_controller_value(_midi.ControllerType.XG_BRIGHTNESS)
            midi_brightness = 127 if midi_brightness >= 64 else midi_brightness * 2

            def get_operator_volume(op_volume):
                n = 0x3f - (op_volume & 0x3f)
                volume = volume_table[midi_volume] // 2
                n = (n * volume) >> 6
                return 0x3f - n

            def get_operator_brightness(op_volume):
                if midi_brightness == 127:
                    return op_volume & 0x3f
                n = 0x3f - (op_volume & 0x3f)
                brightness = int(round(127 * _math.sqrt(midi_brightness / 127.0)) // 2)
                n = (n * brightness) >> 6
                return 0x3f - n

            # For AM, volume changes both modulator and carrier.
            # For FM, brightness changes modulator and volume only changes the carrier.
            get_modulator_volume = get_operator_volume if instrument.feedback[voice] & 0x1 else get_operator_brightness
            modulator_volume = get_modulator_volume(instrument.modulator[voice].output_level)
            carrier_volume = get_operator_volume(instrument.carrier[voice].output_level)
            return [
                (
                    VOLUME_MSG | MODULATORS[imf_channel.number],
                    modulator_volume | (instrument.modulator[voice].key_scale_level << 6)
                ),
                (
                    VOLUME_MSG | CARRIERS[imf_channel.number],
                    carrier_volume | (instrument.carrier[voice].key_scale_level << 6)
                ),
            ]

        def on_note_on(song_event: _midiengine.NoteEvent):
            instrument = get_event_instrument(song_event.channel, song_event.note)
            if instrument is None:
                return
            voice = 0
            midi_channel = engine.channels[song_event.channel]
            adjusted_note = get_instrument_note(instrument, song_event.note, voice)
            if not engine.is_percussion_channel(song_event.channel):
                # _logging.debug(f"Adding active note: {event['note']} -> {note}, channel {event.channel}")
                midi_channel.active_notes.append(_midiengine.ActiveNote(song_event.note, song_event.velocity,
                                                                        adjusted_note))
            imf_channel = find_imf_channel(instrument, adjusted_note)
            if imf_channel:
                commands = []
                # Check for instrument change.
                if imf_channel.instrument != instrument:
                    # Removed volume messages. Volume will initialize to OFF.
                    commands += [cmd for cmd in instrument.get_regs(imf_channel.number, voice) if
                                 (cmd[0] & 0xf0) != VOLUME_MSG]
                    # commands += [
                    #     (VOLUME_MSG | MODULATORS[channel.number], 0x3f),
                    #     (VOLUME_MSG | CARRIERS[channel.number], 0x3f),
                    # ]
                    imf_channel.instrument = instrument
                imf_channel.last_note = adjusted_note
                block, freq = get_block_and_freq(adjusted_note, midi_channel.scaled_pitch_bend)
                # volume = calculate_volume(midi_channel, song_event["velocity"])
                commands += get_volume_commands(imf_channel, instrument, midi_channel, song_event.velocity)
                commands += [
                    (FREQ_MSG | imf_channel.number, freq & 0xff),
                    (BLOCK_MSG | imf_channel.number, KEY_ON_MASK | (block << 2) | (freq >> 8)),
                ]
                add_commands(song_event.time, commands)
                # else:
            #     print(f"Could not find channel for note on! inst: {inst_num}, note: {note}")
            # return commands

        def on_note_off(song_event: _midiengine.NoteEvent):
            instrument = get_event_instrument(song_event.channel, song_event.note)
            if instrument is None:
                return
            voice = 0
            adjusted_note = get_instrument_note(instrument, song_event.note, voice)
            if not engine.is_percussion_channel(song_event.channel):
                midi_channel = engine.channels[song_event.channel]
                match = next(filter(lambda note_info: note_info.given_note == song_event.note,
                                    midi_channel.active_notes), None)  # type: _midiengine.ActiveNote
                if match:
                    adjusted_note = match.adjusted_note
                    # inst_num = match["inst_num"]
                    midi_channel.active_notes.remove(match)
                else:
                    raise ValueError(f"Tried to remove non-active note: track {song_event.track}, note {adjusted_note}")
            imf_channel = find_imf_channel_for_instrument_note(instrument, adjusted_note)
            if imf_channel:
                imf_channel.last_note = None
                # block, freq = get_block_and_freq(event)
                add_commands(song_event.time, [
                    (BLOCK_MSG | imf_channel.number, regs[BLOCK_MSG | imf_channel.number] & ~KEY_ON_MASK),
                ])
            # else:
            #     print(f"Could not find note to shut off! inst: {inst_num}, note: {note}")

        def on_pitch_bend(song_event: _midiengine.PitchBendEvent):
            # Can't pitch bend percussion.
            if engine.is_percussion_channel(song_event.channel):
                return
            midi_channel = engine.channels[song_event.channel]
            pitch_bend = midi_channel.scaled_pitch_bend
            instrument = get_event_instrument(song_event.channel)  # midi_channels[event.channel]["instrument"]
            for active_note in midi_channel.active_notes:
                note = active_note.adjusted_note
                imf_channel = find_imf_channel_for_instrument_note(instrument, note)
                if imf_channel:
                    block, freq = get_block_and_freq(note, pitch_bend)
                    add_commands(song_event.time, [
                        (FREQ_MSG | imf_channel.number, freq & 0xff),
                        (BLOCK_MSG | imf_channel.number, KEY_ON_MASK | (block << 2) | (freq >> 8)),
                    ])
                else:
                    _logging.warning(f"Could not find Adlib channel for channel {song_event.channel} note {note}.")

        def on_controller_change(song_event: _midiengine.ControllerChangeEvent):
            if song_event.controller in (_midi.ControllerType.VOLUME_MSB,
                                         _midi.ControllerType.EXPRESSION_MSB,
                                         _midi.ControllerType.XG_BRIGHTNESS,
                                         ):
                # Can't adjust volume of active percussion.
                if engine.is_percussion_channel(song_event.channel):
                    return
                midi_channel = engine.channels[song_event.channel]
                if midi_channel.active_notes:
                    commands = []
                    instrument = get_event_instrument(song_event.channel)
                    for active_note in midi_channel.active_notes:
                        imf_channel = find_imf_channel_for_instrument_note(instrument, active_note.adjusted_note)
                        if imf_channel:
                            commands += get_volume_commands(imf_channel, instrument, midi_channel, active_note.velocity)
                    add_commands(song_event.time, commands)

        def on_end_of_song(song_event: _midiengine.EndOfSongEvent):
            add_delay(song_event.time, -1)

        # Set up the song and start the midi engine.
        set_tempo(0.0, 120)  # Arbitrary default tempo if none is set by the song.
        song._commands = [
            (0, 0, 0),  # Always start with 0, 0, 0
            (0xBD, 0, 0),
            (0x8, 0, 0),
        ]
        engine.on_tempo_change.add_handler(on_tempo_change)
        engine.on_note_on.add_handler(on_note_on)
        engine.on_note_off.add_handler(on_note_off)
        engine.on_pitch_bend.add_handler(on_pitch_bend)
        engine.on_controller_change.add_handler(on_controller_change)
        engine.on_end_of_song.add_handler(on_end_of_song)
        engine.start()

        for mc in engine.channels:
            if mc.active_notes:
                _logging.warning(f"midi track {mc.number} had open notes: {mc.active_notes}")
        for ch in imf_channels:
            if ch.last_note:
                _logging.warning(f"imf channel {ch.number} had open note: {ch.last_note}")

        # Remove commands that do nothing, ie: register value changes with no delay.
        # temp_commands = []
        # removed_commands = 0
        # for index in range(len(song._commands)):
        #     command = song._commands[index]
        #     if command[2] == 0:
        #         regs = [None] * 256
        #     if regs[command[0]] is None:
        #         regs[command[0]] = regs[command[1]]
        #         temp_commands.append(command)
        #     else:
        #         removed_commands += 1
        # _logging.debug(f"Removed {removed_commands} commands.")

        return song


class _ImfChannelInfo:
    def __init__(self, number):
        self.number = number
        self.instrument = None
        self.last_note = None

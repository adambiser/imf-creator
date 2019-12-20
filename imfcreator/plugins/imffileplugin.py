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

_GM_DRUM_BANK = _midi.calculate_msb_lsb(120, 0)
_XG_DRUM_BANK = _midi.calculate_msb_lsb(127, 0)
_DRUM_BANKS = [_GM_DRUM_BANK, _XG_DRUM_BANK]


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
        midi_channels = [_MidiChannelInfo(ch) for ch in range(16)]
        imf_channels = [_ImfChannelInfo(ch) for ch in range(1, 9)]
        regs = [None] * 256

        # Tempo/delay related variables and methods.
        ticks_per_beat = 0
        last_command_ticks = 0  # The ticks at which the last IMF command occurred.
        tempo_start_time = 0.0  # The time, in beats, at which the last tempo change occurred.

        # Define helper functions.
        def set_tempo(bpm: float, event_time: float = 0):
            nonlocal ticks_per_beat, tempo_start_time
            ticks_per_beat = song.ticks * (60.0 / bpm)
            tempo_start_time = event_time

        def calc_imf_ticks(value):
            return int(ticks_per_beat * value)

        def add_delay(time, command_index: int):
            nonlocal last_command_ticks, song
            # To reduce rounding errors, calculate the ticks from the last tempo change and subtract the ticks at which
            # the last command took place.
            ticks = calc_imf_ticks(time - tempo_start_time)
            # noinspection PyProtectedMember
            song._commands[command_index] = song._commands[command_index][0:2] + (ticks - last_command_ticks,)
            last_command_ticks = ticks

        def is_percussion_event(song_event: _midi.SongEvent) -> bool:
            return song_event.is_percussion or midi_channels[song_event.channel].get_bank() in _DRUM_BANKS

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
            note = get_instrument_note(instrument, song_event, voice)
            if not is_percussion_event(song_event):
                midi_channel = midi_channels[song_event.channel]
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
            midi_channel = midi_channels[song_event.channel]
            bank = midi_channel.get_bank()
            if is_percussion_event(song_event):
                # _logging.debug(f"Searching for PERCUSSION instrument {event['note']}")
                return instruments.get(instruments.PERCUSSION, bank, song_event["note"])
            else:
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

        def get_volume_commands(channel, instrument, midi_channel: _MidiChannelInfo, note_velocity: int, voice=0):
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
            midi_volume = (midi_channel.controllers[_midi.ControllerType.VOLUME_MSB]
                           * midi_channel.controllers[_midi.ControllerType.EXPRESSION_MSB]
                           * note_velocity) // 16129
            if midi_volume > 127:
                midi_volume = 127
            midi_brightness = midi_channel.controllers[_midi.ControllerType.XG_BRIGHTNESS]
            midi_brightness = 127 if midi_brightness >= 64 else midi_brightness * 2

            def get_operator_volume(op_volume):
                n = 0x3f - (op_volume & 0x3f)
                # n = (n * volume_table[midi_volume]) >> 7
                n = ((n * 2) * volume_table[midi_volume]) >> 8
                return 0x3f - n

            def get_operator_brightness(op_volume):
                if midi_brightness == 127:
                    return op_volume & 0x3f
                n = 0x3f - (op_volume & 0x3f)
                # brightness = int(round(127 * _math.sqrt(midi_brightness / 127.0)) // 2)
                # n = (n * brightness) >> 6
                brightness = int(round(127.0 * _math.sqrt(float(midi_brightness) * (1.0 / 127.0))) / 2.0)
                n = (n * brightness) // 0x3f
                return 0x3f - n

            # For AM, volume changes both modulator and carrier.
            # For FM, brightness changes modulator and volume only changes the carrier.
            get_modulator_volume = get_operator_volume if instrument.feedback[voice] & 0x01 else get_operator_brightness
            # if instrument.feedback[voice] & 0x01:
            #     modulator_volume = get_modulator_volume(instrument.modulator[voice].output_level)
            # else:
            #     modulator_volume = instrument.modulator[voice].output_level & 0x3f
            modulator_volume = get_modulator_volume(instrument.modulator[voice].output_level)
            carrier_volume = get_operator_volume(instrument.carrier[voice].output_level)
            return [
                (
                    VOLUME_MSG | MODULATORS[channel.number],
                    modulator_volume | (instrument.modulator[voice].key_scale_level << 6)
                ),
                (
                    VOLUME_MSG | CARRIERS[channel.number],
                    carrier_volume | (instrument.carrier[voice].key_scale_level << 6)
                ),
            ]

        def note_on(song_event: _midi.SongEvent):
            instrument = get_event_instrument(song_event)
            if instrument is None:
                return None
            voice = 0
            midi_channel = midi_channels[song_event.channel]
            note = get_instrument_note(instrument, song_event, voice)
            if not is_percussion_event(song_event):
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
                    # commands += [
                    #     (VOLUME_MSG | MODULATORS[channel.number], 0x3f),
                    #     (VOLUME_MSG | CARRIERS[channel.number], 0x3f),
                    # ]
                    # adlib_write_channel(0x20, slot,
                    #                     (instr[6] & 1) ? (instr[7] | state): instr[0],
                    #                                                          instr[7] | state);
                    # }
                    channel.instrument = instrument
                channel.last_note = note
                block, freq = get_block_and_freq(note, midi_channel.scaled_pitch_bend)
                # volume = calculate_volume(midi_channel, song_event["velocity"])
                commands += get_volume_commands(channel, instrument, midi_channel, song_event["velocity"])
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
            if is_percussion_event(song_event):
                return None
            commands = []
            amount = song_event["value"]  # This has a range of -1..1  # - event["value"] % pitch_bend_resolution
            midi_channel = midi_channels[song_event.channel]
            if midi_channel.pitch_bend != amount:
                midi_channel.pitch_bend = amount
                # Scale pitch bend to -1..1
                scaled_pitch_bend = amount  # / -pitch_bend_range[0] if amount < 0 else amount / pitch_bend_range[1]
                print(f"pitch bend: {scaled_pitch_bend}")
                scaled_pitch_bend *= 2  # TODO Read from controller messages. 2 semi-tones is the default.
                midi_channel.scaled_pitch_bend = scaled_pitch_bend
                instrument = get_event_instrument(song_event)  # midi_channels[event.channel]["instrument"]
                for note_info in midi_channel.active_notes:
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
            midi_channel = midi_channels[song_event.channel]
            if midi_channel.active_notes:
                instrument = get_event_instrument(song_event)
                for note_info in midi_channel.active_notes:
                    imf_channel = find_imf_channel_for_instrument_note(instrument, note_info.note)
                    if imf_channel:
                        commands += get_volume_commands(imf_channel, instrument, midi_channel,
                                                        note_info.song_event["velocity"])
            return commands

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
                elif event.type == _midi.EventType.CONTROLLER_CHANGE:
                    controller = event["controller"]  # type: _midi.ControllerType
                    midi_channels[event.channel].controllers[controller] = event["value"]
                    if controller in (_midi.ControllerType.VOLUME_MSB,
                                      _midi.ControllerType.EXPRESSION_MSB,
                                      _midi.ControllerType.XG_BRIGHTNESS,
                                      ):
                        commands = adjust_volume(event)
                elif event.type == _midi.EventType.PITCH_BEND:
                    commands = pitch_bend(event)
                elif event.type == _midi.EventType.PROGRAM_CHANGE:
                    midi_channels[event.channel].instrument = event["program"]
                elif event.type == _midi.EventType.META and event["meta_type"] == _midi.MetaType.SET_TEMPO:
                    set_tempo(float(event["bpm"]), event.time)
                if commands:
                    # TODO Filter out same-register commands on the same tick.
                    old_commands_length = len(song._commands)
                    # add_delay(event.time)
                    # Now add the new commands
                    for command in commands:
                        add_command(*command)
                    if old_commands_length != len(song._commands):
                        add_delay(event.time, old_commands_length - 1)
            # Add any remaining delay to the final command for wrap-around timing.
            add_delay(max([event.time for event in events]), -1)

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
    PITCH_BEND_SENSITIVITY_RPN = _midi.calculate_msb_lsb(0, 0)
    FINE_TUNING_RPN = _midi.calculate_msb_lsb(0, 1)
    COARSE_TUNING_RPN = _midi.calculate_msb_lsb(0, 2)
    TUNING_PROGRAM_SELECT_RPN = _midi.calculate_msb_lsb(0, 3)
    TUNING_BANK_SELECT_RPN = _midi.calculate_msb_lsb(0, 4)
    NULL_RPN = _midi.calculate_msb_lsb(127, 127)

    def __init__(self, number):
        self.number = number
        self.instrument = None
        self.active_notes = []  # type: _typing.List[_ActiveNote]
        self.pitch_bend = 0
        self.controllers = [0] * 128
        # http://www.philrees.co.uk/nrpnq.htm
        self.rpn = {
            _MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN: [0, 0],  # MSB = semitones, LSB = cents
            _MidiChannelInfo.FINE_TUNING_RPN: [0, 0],  # 8192 = Center/A440, 0 = 1 semitone down, 16383 = 1 semitone up
            _MidiChannelInfo.COARSE_TUNING_RPN: [0, 0],  # MSB = semitones; 64 = center, LSB = unused
            _MidiChannelInfo.TUNING_PROGRAM_SELECT_RPN: [0, 0],  # MIDI Tuning Standard.  Not widely implemented.
            _MidiChannelInfo.TUNING_BANK_SELECT_RPN: [0, 0],  # MIDI Tuning Standard.  Not widely implemented.
        }
        # TODO Ignore NRPN for CC6 and 38
        # self.pitch_bend_sensitivity = [0, 0]
        self.reset_controllers()

    def reset_controllers(self):
        for x in range(len(self.controllers)):
            self.controllers[x] = 0
        self.controllers[_midi.ControllerType.VOLUME_MSB] = 100
        self.controllers[_midi.ControllerType.XG_BRIGHTNESS] = 127
        self.controllers[_midi.ControllerType.EXPRESSION_MSB] = 127
        self.controllers[_midi.ControllerType.RPN_MSB] = 127
        self.controllers[_midi.ControllerType.RPN_LSB] = 127
        self.rpn[_MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN] = [2, 0]
        self.rpn[_MidiChannelInfo.FINE_TUNING_RPN] = list(_midi.split_msb_lsb(8192))
        self.rpn[_MidiChannelInfo.COARSE_TUNING_RPN][0] = 64

    def _get_msb_lsb(self, msb_controller: _midi.ControllerType, lsb_controller: _midi.ControllerType):
        assert msb_controller + 32 == lsb_controller
        return _midi.calculate_msb_lsb(self.controllers[msb_controller], self.controllers[lsb_controller])

    def get_bank(self):
        return self._get_msb_lsb(_midi.ControllerType.BANK_SELECT_MSB, _midi.ControllerType.BANK_SELECT_LSB)

    # BANK_SELECT_MSB = 0,  # Allows user to switch bank for patch selection. Program change used with Bank Select.
    # MODULATION_WHEEL_MSB = 1,  # Generally controls a vibrato effect (pitch, loudness, brighness), depends on patch.
    # BREATH_CONTROLLER_MSB = 2,  # Often used with aftertouch messages. Can be used for modulation as well.
    # # 3 is undefined
    # FOOT_CONTROLLER_MSB = 4,  # Often used with aftertouch messages. Values based on how the pedal is used.
    # PORTAMENTO_TIME_MSB = 5,  # Controls portamento rate to slide between 2 notes played subsequently.
    # DATA_ENTRY_MSB = 6,  # Controls Value for NRPN or RPN parameters.
    # VOLUME_MSB = 7,  # Control the volume of the channel
    # BALANCE_MSB = 8,  # Controls balance, generally for stereo patches.  0 = hard left, 64 = center, 127 = hard right
    # # 9 is undefined
    # PAN_MSB = 10,  # Controls panning, generally for mono patches.  0 = hard left, 64 = center, 127 = hard right
    # EXPRESSION_MSB = 11,  # Expression is a percentage of volume (CC7).
    # EFFECT_1_MSB = 12,  # Usually used to control a parameter of an effect within the synth/workstation.
    # EFFECT_2_MSB = 13,  # Usually used to control a parameter of an effect within the synth/workstation.
    # # 14-15 are undefined
    # GENERAL_PURPOSE_1_MSB = 16,
    # GENERAL_PURPOSE_2_MSB = 17,
    # GENERAL_PURPOSE_3_MSB = 18,
    # GENERAL_PURPOSE_4_MSB = 19,

    def get_pitch_bend(self):
        amount = self._get_msb_lsb(_midi.ControllerType.)

    # def add_active_note(self):
    #     pass
    #
    # def get_active_note(self):
    #     pass
    #
    # def remove_active_note(self):
    #     pass


class _ImfChannelInfo:
    def __init__(self, number):
        self.number = number
        self.instrument = None
        self.last_note = None

import copy
import math

from .adlib import *
from .filetypes.imfmusicfile import ImfMusicFile


def _sort_midi(midi):  # , mute_tracks=None, mute_channels=None):
    # Combine all tracks into one track.
    events = []
    for track in midi.tracks:
        time = 0
        for event in track:
            time += event.delta
            del event.delta
            event = copy.copy(event)
            event.event_time = time
            event.track = track.number
            events.append(event)
    # if mute_tracks:
    #     events = filter(lambda event: event.track not in mute_tracks, events)
    # if mute_channels:
    #     events = filter(lambda event: not hasattr(event, "channel") or event.channel not in mute_channels, events)
    # Sort by event time and channel. Note-on events with a velocity should come last at a given time within the song.
    events = sorted(events, key=lambda event: (
        event.event_time,
        1 if event.type == "note_on" and event.velocity > 0 else 0,
        event.channel if hasattr(event, "channel") else -1,
    ))
    return events


def convert_midi_to_imf(midi, instruments, mute_tracks=None, mute_channels=None, output_file_name="output.wlf", imf_file_type=0):
    events = _sort_midi(midi)  # , mute_tracks, mute_channels)
    imf = ImfMusicFile()
    # Prepare MIDI and IMF channel variables.
    midi_channels = {}
    for ch in range(16):
        midi_channels[ch] = {
            "instrument": None,
            "volume": 127,
            "pitch_bend": 0,
            "scaled_pitch_bend": 0.0,
            "active_notes": [],
        }
    imf_channels = [{
        "id": channel,
        "instrument": None,
        "last_note": None,
    } for channel in range(1, 9)]
    regs = [None] * 256
    midi_tempo = 120.0

    # Define helper functions.
    def _calc_imf_ticks(value):
        return int(imf.ticks_per_second * (float(value) / midi.division) * (60.0 / midi_tempo))

    def _find_imf_channel(instrument, note):
        channel = filter(lambda ch: ch["instrument"] == instrument and ch["last_note"] is None, imf_channels)
        if channel:
            return channel[0]  # ["id"]
        # channel = filter(lambda ch: ch["instrument"] == instrument, imf_channels)
        # if channel:
        #     return channel[0]  # ["id"]
        channel = filter(lambda ch: ch["last_note"] is None, imf_channels)
        if channel:
            return channel[0]  # ["id"]
        # TODO Aggressive channel find.
        return None

    def _add_commands(commands):
        added_command = False
        for command in commands:
            reg, value = command
            # if (reg & 0x20) == 0x20:
            #     value = (value & 0xf0) | 1
            if regs[reg] != value:
                imf.add_command(reg, value, 0)
                regs[reg] = value
                added_command = True
        return added_command

    def _get_block_and_freq(note, scaled_pitch_bend):
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
            semitones = int(math.floor(scaled_pitch_bend))
            bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[note + semitones]
            # If the bend-to note is on a lower block/octave, multiply the *bend-to* f-num by 0.5 per block
            # to bring it up to the same block as the original note.
            # assert not (bend_block == 1 and block == 0 and note == 18 and semitones == -1)
            if bend_block < block:
                bend_freq /= (2.0 ** (block - bend_block))
            freq = int(freq + (bend_freq - freq) * scaled_pitch_bend / semitones)
        elif scaled_pitch_bend > 0:
            semitones = int(math.ceil(scaled_pitch_bend))
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

    def _find_imf_channel_for_instrument_note(instrument, note):
        channel = filter(lambda ch: ch["instrument"] == instrument and ch["last_note"] == note, imf_channels)
        if channel:
            return channel[0]
        return None

    def _note_off(event):
        commands = []
        inst_num, note, ins = _get_inst_and_note(event, False)
        channel = _find_imf_channel_for_instrument_note(inst_num, note)
        if channel:
            channel["last_note"] = None
            # block, freq = get_block_and_freq(event)
            commands += [
                # (BLOCK_MSG | channel["id"], KEY_OFF_MASK | (block << 2) | (freq >> 8)),
                # (BLOCK_MSG | channel["id"], KEY_OFF_MASK),
                (BLOCK_MSG | channel["id"], regs[BLOCK_MSG | channel["id"]] & ~KEY_ON_MASK),
                # Release notes quickly.
                # (SUSTAIN_RELEASE_MSG | MODULATORS[channel["id"]], 0xf),
                # (SUSTAIN_RELEASE_MSG | CARRIERS[channel["id"]], 0xf),
            ]
        # else:
        #     print "Could not find note to shut off! inst: {}, note: {}".format(inst_num, note)
        return commands

    def _encode_ins_number(type, bank, patch):
        t = 0x1000000 if type == 'p' else 0
        b = bank << 2
        return t + bank + patch

    def _get_inst_by_code(code):
        type = 'p' if (code & 0x1000000) != 0 else 'm'
        bank = (code & 0x0FFFF00) >> 2
        patch = (code & 0x00000FF)
        return instruments[type][bank][patch]

    def _find_inst_and_bank(type, bank, inst):
        if bank not in instruments[type]:
            bank = 0  # Fallback to zero bank
            if bank not in instruments[type]:
                return -1, -1  # Error when not found even in zero bank
        if inst not in instruments[type][bank]:
            bank = 0  # Fallback to zero bank
            if bank not in instruments[type] or inst not in instruments[type][bank]:
                return -1, -1  # Error when not found even in zero bank
        return bank, inst

    def _get_inst_and_note(event, is_note_on, voice=0):
        bank = 0  # TODO: Read controllers 0 and 32 to choose the bank number. Watch out for GS and XG logic difference!
        if event.channel == 9:
            assert 'p' in instruments
            bank, inst = _find_inst_and_bank('p', bank, event.note)
            if bank < 0 or inst < 0:
                return -1, -1, None  # Bank / instrument is not foind
            ins = instruments['p'][bank][inst]
            inst_num = _encode_ins_number('p', bank, event.note)
            note = ins.given_note
            note += ins.note_offset[voice]
            if note < 0 or note > 127:
                print "Note out of range: {}".format(note)
                note = 60
        else:
            assert 'm' in instruments
            midi_track = midi_channels[event.channel]
            if midi_track["instrument"] is None:
                print "No instrument assigned to track {}, defaulting to 0."
                midi_track["instrument"] = 0
            bank, inst = _find_inst_and_bank('m', bank, midi_track["instrument"])
            if bank < 0 or inst < 0:
                return -1, -1, None  # Bank / instrument is not foind
            ins = instruments['m'][bank][inst]
            inst_num = _encode_ins_number('p', bank, inst)
            note = event.note
            note += ins.note_offset[voice]
            if note < 0 or note > 127:
                print "Note out of range: {}".format(note)
                note = 60
            if is_note_on:
                midi_track["active_notes"].append({
                    "note": note,
                    "inst_num": inst_num,
                    "event": event,
                })
            else:
                # match = midi_track["notes"].get(event.note)
                match = filter(lambda note_info: note_info["event"].note == event.note, midi_track["active_notes"])
                if match:
                    match = match[0]
                    note = match["note"]
                    inst_num = match["inst_num"]
                    midi_track["active_notes"].remove(match)
                else:
                    print "Tried to remove non-active note: track {}, inst {} note {}"\
                        .format(event.track, inst_num, note)
        return inst_num, note, ins

    def _get_volume_commands(channel, instrument, midi_volume, voice=0):
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
        if (instrument.feedback[voice] & 0x01) == 1:  # when AM, scale both operators
            return [
                (
                    VOLUME_MSG | MODULATORS[channel["id"]],
                    get_operator_volume(instrument.modulator[voice].output_level)
                    | (instrument.modulator[voice].key_scale_level << 6)
                ),
                (
                    VOLUME_MSG | CARRIERS[channel["id"]],
                    get_operator_volume(instrument.carrier[voice].output_level)
                    | (instrument.carrier[voice].key_scale_level << 6)
                ),
            ]
        else:  # When FM, scale carrier only, keep modulator as-is
            return [
                (
                    VOLUME_MSG | MODULATORS[channel["id"]],
                    instrument.modulator[voice].output_level & 0x3f
                    | (instrument.modulator[voice].key_scale_level << 6)
                ),
                (
                    VOLUME_MSG | CARRIERS[channel["id"]],
                    get_operator_volume(instrument.carrier[voice].output_level)
                    | (instrument.carrier[voice].key_scale_level << 6)
                ),
            ]

    def _note_on(event):
        commands = []
        voice = 0
        midi_track = midi_channels[event.channel]
        inst_num, note, ins = _get_inst_and_note(event, True)
        if inst_num < 0 or ins is None:
            return commands
        channel = _find_imf_channel(inst_num, note)
        if channel:
            # Check for instrument change.
            instrument = ins
            if channel["instrument"] != inst_num:
                # Removed volume messages. Volume will initialize to OFF.
                commands += [cmd for cmd in instrument.get_regs(channel["id"], voice) if (cmd[0] & 0xf0) != VOLUME_MSG]
                commands += [
                    (VOLUME_MSG | MODULATORS[channel["id"]], 0x3f),
                    (VOLUME_MSG | CARRIERS[channel["id"]], 0x3f),
                ]
                # adlib_write_channel(0x20, slot,
                #                     (instr[6] & 1) ? (instr[7] | state): instr[0],
                #                                                          instr[7] | state);
                # }
                channel["instrument"] = inst_num
            volume = int(midi_track["volume"] * event.velocity / 127.0)
            channel["last_note"] = note
            block, freq = _get_block_and_freq(note, midi_track["scaled_pitch_bend"])
            commands += _get_volume_commands(channel, instrument, volume)
            commands += [
                # (
                #     VOLUME_MSG | MODULATORS[channel["id"]],
                #     ((127 - volume) / 2) | instrument.modulator[voice].key_scale_level
                # ),
                # (
                #     VOLUME_MSG | CARRIERS[channel["id"]],
                #     ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                # ),
                (FREQ_MSG | channel["id"], freq & 0xff),
                (BLOCK_MSG | channel["id"], KEY_ON_MASK | (block << 2) | (freq >> 8)),
            ]
        # else:
        #     print "Could not find channel for note on! inst: {}, note: {}".format(inst_num, note)
        return commands

    def _pitch_bend(event):
        commands = []
        amount = event.value - event.value % pitch_bend_resolution
        if midi_channels[event.channel]["pitch_bend"] != amount:
            midi_channels[event.channel]["pitch_bend"] = amount
            # Scale picth bend to -1..1
            scaled_pitch_bend = amount / -pitch_bend_range[0] if amount < 0 else amount / pitch_bend_range[1]
            scaled_pitch_bend *= 2  # TODO Read from controller messages. 2 semi-tones is the default.
            midi_channels[event.channel]["scaled_pitch_bend"] = scaled_pitch_bend
            instrument = midi_channels[event.channel]["instrument"]
            for note_info in midi_channels[event.channel]["active_notes"]:
                note = note_info["note"]
                channel = _find_imf_channel_for_instrument_note(instrument, note)
                if channel:
                    block, freq = _get_block_and_freq(note, scaled_pitch_bend)
                    commands += [
                        (FREQ_MSG | channel["id"], freq & 0xff),
                        (BLOCK_MSG | channel["id"], KEY_ON_MASK | (block << 2) | (freq >> 8)),
                    ]
                    pass
        return commands

    def _adjust_volume(event):
        commands = []
        voice = 0
        midi_track = midi_channels[event.channel]
        midi_track["volume"] = event.value
        inst_num = midi_track["instrument"]
        for note_info in midi_track["active_notes"]:
            channel = _find_imf_channel_for_instrument_note(inst_num, note_info["note"])
            if channel:
                volume = int(midi_track["volume"] * note_info["event"].velocity / 127.0)
                instrument = _get_inst_by_code(inst_num)
                commands += _get_volume_commands(channel, instrument, volume)
                # commands += [
                #     (
                #         VOLUME_MSG | MODULATORS[channel["id"]],
                #         ((127 - volume) / 2) | instrument.modulator[voice].key_scale_level
                #     ),
                #     (
                #         VOLUME_MSG | CARRIERS[channel["id"]],
                #         ((127 - volume) / 2) | instrument.carrier[voice].key_scale_level
                #     ),
                # ]
        return commands

    # Cycle MIDI events and convert to IMF commands.
    last_ticks = 0
    # ticks = 0
    pitch_bend_resolution = 0x200
    pitch_bend_range = (-8192.0 - -8192 % -pitch_bend_resolution, 8191.0 - 8191 % pitch_bend_resolution)
    imf.commands += [
        (0, 0, 0),  # Always start with 0, 0, 0
        (0xBD, 0, 0),
        (0x8, 0, 0),
    ]
    for event in events:
        ticks = _calc_imf_ticks(event.event_time - last_ticks)
        if ticks > 0:
            prev_ticks = imf.commands[-1][2] + ticks
            imf.commands[-1] = imf.commands[-1][:2] + (prev_ticks,)
            last_ticks = event.event_time  # ticks
        # Perform muting
        if mute_tracks:
            if event.track in mute_tracks:
                continue
        if mute_channels:
            if hasattr(event, "channel") and event.channel in mute_channels:
                continue
        # Handle events.
        commands = []  # list of (reg, value) tuples.
        if (event.type == "note_on" and event.velocity == 0) or event.type == "note_off":
            commands += _note_off(event)
        elif event.type == "note_on":
            commands += _note_on(event)
        elif event.type == "controller_change" and event.controller == "volume_msb":
            commands += _adjust_volume(event)
        elif event.type == "pitch_bend":
            commands += _pitch_bend(event)
        elif event.type == "program_change":
            midi_channels[event.channel]["instrument"] = event.program
        elif event.type == "meta" and event.meta_type == "set_tempo":
            midi_tempo = float(event.bpm)
        _add_commands(commands)
    imf.save(output_file_name, file_type=imf_file_type)
    # for command in imf.commands:
    #     print(map(hex, command))
    for mc in range(16):
        if midi_channels[mc]["active_notes"]:
            print "midi track {} had open notes: {}".format(mc, midi_channels[mc]["active_notes"])
    for ch in imf_channels:
        if ch["last_note"]:
            print "imf channel {} had open note: {}".format(ch["id"], ch["last_note"])
    return imf

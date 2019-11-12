# -*- coding: utf-8 -*-
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
            "bank_lsb": 0,
            "bank_msb": 0,
            "last_lrpn": 0,
            "last_mrpn": 0,
            "nrpn": False,
            "volume": 127,
            "pitch_bend": 0,
            "pitch_bend_sensitivity_lsb": 0,
            "pitch_bend_sensitivity_msb": 2,
            "pitch_bend_sensitivity": 2.0,
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
        if scaled_pitch_bend < 0 or scaled_pitch_bend > 0:
            semitones = int(math.floor(scaled_pitch_bend))
            offset = note + semitones
            if offset < 0:
                offset = 0
            elif offset > len(BLOCK_FREQ_NOTE_MAP):
                offset = len(BLOCK_FREQ_NOTE_MAP) - 1
            bend_block, bend_freq = BLOCK_FREQ_NOTE_MAP[offset]
            if semitones != 0:
                if scaled_pitch_bend < 0:
                    # If the bend-to note is on a lower block/octave, multiply the *bend-to* f-num by 0.5 per block
                    # to bring it up to the same block as the original note.
                    # assert not (bend_block == 1 and block == 0 and note == 18 and semitones == -1)
                    if bend_block < block:
                        bend_freq /= (2.0 ** (block - bend_block))
                    freq = int(freq + (bend_freq - freq) * scaled_pitch_bend / semitones)
                elif scaled_pitch_bend > 0:
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
        if inst_num is None or ins is None:
            return commands
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
        b = bank << 8
        return t + b + patch

    def _get_inst_by_code(code):
        type = 'p' if (code & 0x1000000) != 0 else 'm'
        bank = (code & 0x0FFFF00) >> 8
        patch = (code & 0x00000FF)
        return instruments[type][bank][patch]

    def _find_inst_and_bank(type, bank, inst):
        if bank not in instruments[type]:
            bank = 0  # Fallback to zero bank
            if bank not in instruments[type]:
                return None, None  # Error when not found even in zero bank
        if inst not in instruments[type][bank]:
            bank = 0  # Fallback to zero bank
            if bank not in instruments[type] or inst not in instruments[type][bank]:
                return None, None  # Error when not found even in zero bank
        return bank, inst

    def _get_inst_and_note(event, is_note_on, voice=0):
        midi_chan = midi_channels[event.channel]
        if midi_chan["instrument"] is None:
            print "No instrument assigned to track {}, defaulting to 0."
            midi_chan["instrument"] = 0
        bank = (midi_chan["bank_msb"] * 256) + midi_chan["bank_lsb"]
        if event.channel == 9 or bank == 0x7F00:
            assert 'p' in instruments
            note = event.note
            bank, inst = _find_inst_and_bank('p', midi_chan["instrument"], note)
            if bank is None or inst is None:
                return None, None, None  # Bank / instrument is not foind
            ins = instruments['p'][bank][inst]
            inst_num = _encode_ins_number('p', bank, note)
            note = ins.given_note
            note += ins.note_offset[voice]
        else:
            assert 'm' in instruments
            bank, inst = _find_inst_and_bank('m', bank, midi_chan["instrument"])
            if bank is None or inst is None:
                return None, None, None  # Bank / instrument is not foind
            ins = instruments['m'][bank][inst]
            inst_num = _encode_ins_number('m', bank, inst)
            note = event.note
            note += ins.note_offset[voice]
            if note < 0 or note > 127:
                print "Note out of range: {}".format(note)
                note = 60
            if is_note_on:
                midi_chan["active_notes"].append({
                    "note": note,
                    "inst_num": inst_num,
                    "event": event,
                })
            else:
                # match = midi_chan["notes"].get(event.note)
                match = filter(lambda note_info: note_info["event"].note == event.note, midi_chan["active_notes"])
                if match:
                    match = match[0]
                    note = match["note"]
                    inst_num = match["inst_num"]
                    midi_chan["active_notes"].remove(match)
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
        if inst_num is None or ins is None:
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
            scaled_pitch_bend *= midi_channels[event.channel]["pitch_bend_sensitivity"]
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

    def _update_bend_sense(channel):
        cent = (channel["pitch_bend_sensitivity_msb"]) * 128 + channel["pitch_bend_sensitivity_lsb"]
        channel["pitch_bend_sensitivity"] = float(cent) / 128.0

    def _set_rpn(event, channel, is_msb):
        nrpn = channel["nrpn"]
        addr = channel["last_mrpn"] * 0x100 + channel["last_lrpn"]
        msb = 1 if is_msb else 0
        key = addr + nrpn * 0x10000 + msb * 0x20000
        if key == 0x0000 + 0*0x10000 + 1*0x20000: # Pitch-bender sensitivity
            channel["pitch_bend_sensitivity_msb"] = event.value
            _update_bend_sense(channel)
        elif key == 0x0000 + 0*0x10000 + 0*0x20000:  # Pitch-bender sensitivity LSB
            channel["pitch_bend_sensitivity_lsb"] = event.value
            _update_bend_sense(channel)


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
        elif event.type == "controller_change" and event.controller == "bank_select_msb":
            midi_channels[event.channel]["bank_msb"] = event.value
        elif event.type == "controller_change" and event.controller == "bank_select_lsb":
            midi_channels[event.channel]["bank_lsb"] = event.value
        elif event.type == "controller_change" and event.controller == "nrpn_lsb":
            midi_channels[event.channel]["last_lrpn"] = event.value
            midi_channels[event.channel]["nrpn"] = True
        elif event.type == "controller_change" and event.controller == "nrpn_msb":
            midi_channels[event.channel]["last_mrpn"] = event.value
            midi_channels[event.channel]["nrpn"] = True
        elif event.type == "controller_change" and event.controller == "rpn_lsb":
            midi_channels[event.channel]["last_lrpn"] = event.value
            midi_channels[event.channel]["nrpn"] = False
        elif event.type == "controller_change" and event.controller == "rpn_msb":
            midi_channels[event.channel]["last_mrpn"] = event.value
            midi_channels[event.channel]["nrpn"] = False
        elif event.type == "controller_change" and event.controller == "data_entry_lsb":
            _set_rpn(event, midi_channels[event.channel], False)
        elif event.type == "controller_change" and event.controller == "data_entry_msb":
            _set_rpn(event, midi_channels[event.channel], True)
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

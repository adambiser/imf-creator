from enum import IntEnum


class SongEvent:
    """Represents a song event.
    This is pretty much just a MIDI event and song readers should convert their file format's events to match MIDI.

    The data dictionary will vary per event_type.  See EventType.
    """

    def __init__(self, track: int, time: int, event_type: "EventType", data: dict = None, channel: int = None):
        """Creates a song event.

        :param track: The track number for the event.
        :param time: The time of the event from the start of the song.
        :param event_type: The event type.
        :param data: A data dictionary for the event.  Contents will vary per event_type.
        :param channel: The event channel.  Must be None for sysex and meta event types and an integer for all others.
        """
        # Validate arguments.
        if event_type in [EventType.F0_SYSEX, EventType.F7_SYSEX, EventType.META]:
            if channel is not None:
                raise ValueError(f"Channel must be None for {event_type} events.")
        elif channel is None or type(channel) is not int:
            raise ValueError(f"Channel must be an integer for {event_type} events.")
        if event_type == EventType.META and "meta_type" not in data:
            raise ValueError(f"{event_type} events must have a 'meta_type' data entry.")
        # Set fields.
        self.track = track
        self.time = time
        self.type = event_type
        self._data = data
        self.channel = channel

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value


class EventType(IntEnum):
    """Song event types.

    Data dictionary for each type:
     * NOTE_OFF: "note", "velocity"
     * NOTE_ON: "note", "velocity"
     * POLYPHONIC_KEY_PRESSURE: "note", "pressure"
     * CONTROLLER_CHANGE: "controller", "value"
     * PROGRAM_CHANGE: "program"
     * CHANNEL_KEY_PRESSURE: "pressure"
     * PITCH_BEND: "value" from -1.0 to 1.0 where 0 = center.  Bend by current bend amount.
     * F0_SYSEX: "bytes"
     * F7_SYSEX: "bytes"
     * META: See MetaType
    """
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLYPHONIC_KEY_PRESSURE = 0xa0
    CONTROLLER_CHANGE = 0xb0  # Also has channel mode messages.
    PROGRAM_CHANGE = 0xc0
    CHANNEL_KEY_PRESSURE = 0xd0
    PITCH_BEND = 0xe0
    F0_SYSEX = 0xf0
    F7_SYSEX = 0xf7
    META = 0xff


class MetaType(IntEnum):
    """Song meta event types.
    Not all meta types are used by the conversion process.

    Data dictionary for each meta type:
     * SEQUENCE_NUMBER: "number"
     * TEXT_EVENT: "text"
     * COPYRIGHT: "text"
     * TRACK_NAME: "text"
     * INSTRUMENT_NAME: "text"
     * LYRIC: "text"
     * MARKER: "text"
     * CUE_POINT: "text"
     * PROGRAM_NAME: "text"
     * DEVICE_NAME: "text"
     * CHANNEL_PREFIX: "channel" 0..15
     * PORT: "port" 0..127
     * END_OF_TRACK: None
     * SET_TEMPO: "bpm"
     * SMTPE_OFFSET: "hours", "minutes", "seconds", "frams", "fractional_frames"
     * TIME_SIGNATURE: "numerator", "denominator", "midi_clocks_per_metronome_tick", "number_of_32nd_notes_per_beat"
     * KEY_SIGNATURE: "key"  # should reflect major/minor, A vs Am
     * SEQUENCER_SPECIFIC: "bytes"
    """
    SEQUENCE_NUMBER = 0x00,
    TEXT_EVENT = 0x01,
    COPYRIGHT = 0x02,
    TRACK_NAME = 0x03,
    INSTRUMENT_NAME = 0x04,
    LYRIC = 0x05,
    MARKER = 0x06,
    CUE_POINT = 0x07,
    PROGRAM_NAME = 0x08,
    DEVICE_NAME = 0x09,
    CHANNEL_PREFIX = 0x20,
    PORT = 0x21,
    END_OF_TRACK = 0x2f,
    SET_TEMPO = 0x51,
    SMTPE_OFFSET = 0x54,
    TIME_SIGNATURE = 0x58,
    KEY_SIGNATURE = 0x59,
    SEQUENCER_SPECIFIC = 0x7f,


class ControllerType(IntEnum):
    """MIDI controller type codes."""
    BANK_SELECT_MSB = 0,  # MSB is most common, except for #32.
    MODULATION_WHEEL_MSB = 1,
    BREATH_CONTROLLER_MSB = 2,
    FOOT_CONTROLLER_MSB = 4,
    PORTAMENTO_TIME_MSB = 5,
    DATA_ENTRY_MSB = 6,
    VOLUME_MSB = 7,
    BALANCE_MSB = 8,
    PAN_MSB = 10,
    EXPRESSION_MSB = 11,
    EFFECT_1_MSB = 12,
    EFFECT_2_MSB = 13,
    GENERAL_PURPOSE_1_MSB = 16,
    GENERAL_PURPOSE_2_MSB = 17,
    GENERAL_PURPOSE_3_MSB = 18,
    GENERAL_PURPOSE_4_MSB = 19,
    BANK_SELECT_LSB = 32,
    MODULATION_LSB = 33,
    BREATH_CONTROLLER_LSB = 34,
    FOOT_CONTROLLER_LSB = 36,
    PORTAMENTO_TIME_LSB = 37,
    DATA_ENTRY_LSB = 38,
    VOLUME_LSB = 39,
    BALANCE_LSB = 40,
    PAN_LSB = 42,
    EXPRESSION_LSB = 43,
    EFFECT_1_LSB = 44,
    EFFECT_2_LSB = 45,
    GENERAL_PURPOSE_1_LSB = 48,
    GENERAL_PURPOSE_2_LSB = 49,
    GENERAL_PURPOSE_3_LSB = 50,
    GENERAL_PURPOSE_4_LSB = 51,
    SUSTAIN_PEDAL_SWITCH = 64,  # 0-63 = Off, 64-127 = On
    PORTAMENTO_SWITCH = 65,
    SOSTENUTO_SWITCH = 66,
    SOFT_PEDAL_SWITCH = 67,
    LEGATO_FOOTSWITCH = 68,
    HOLD_2_SWITCH = 69,
    SOUND_CONTROLLER_1 = 70,
    SOUND_CONTROLLER_2 = 71,
    SOUND_CONTROLLER_3 = 72,
    SOUND_CONTROLLER_4 = 73,
    SOUND_CONTROLLER_5 = 74,
    SOUND_CONTROLLER_6 = 75,
    SOUND_CONTROLLER_7 = 76,
    SOUND_CONTROLLER_8 = 77,
    SOUND_CONTROLLER_9 = 78,
    SOUND_CONTROLLER_10 = 79,
    GENERAL_PURPOSE_5 = 80,
    GENERAL_PURPOSE_6 = 81,
    GENERAL_PURPOSE_7 = 82,
    GENERAL_PURPOSE_8 = 83,
    PORTAMENTO_AMOUNT = 84,
    EFFECTS_1_DEPTH = 91,
    EFFECTS_2_DEPTH = 92,
    EFFECTS_3_DEPTH = 93,
    EFFECTS_4_DEPTH = 94,
    EFFECTS_5_DEPTH = 95,
    DATA_INCREMENT = 96,
    DATA_DECREMENT = 97,
    NRPN_LSB = 98,  # For controllers 6, 38, 96, and 97
    NRPN_MSB = 99,  # For controllers 6, 38, 96, and 97
    RPN_LSB = 100,  # For controllers 6, 38, 96, and 97
    RPN_MSB = 101,  # For controllers 6, 38, 96, and 97

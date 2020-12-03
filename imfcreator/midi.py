import logging as _logging
from enum import IntEnum
from functools import total_ordering


def scale_14bit(value: int) -> float:
    """Scales a 14-bit integer value to a float from 0.0 to 1.0."""
    return value / 0x3fff


def balance_14bit(value: int) -> float:
    """Scales a 14-bit integer value to a float from -1.0 to 1.0."""
    value -= 0x2000
    return value / (0x1fff if value >= 0 else 0x2000)


def get_key_signature_text(sharps_flats: int, major_minor: int):
    keys = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F",
            "C", "G", "D", "A", "E", "B", "F#",
            "C#", "G#", "D#", "A#"]
    return keys[sharps_flats + 7 + major_minor * 3] + "m" * major_minor


@total_ordering
class SongEvent:
    """Represents a song event.
    This is just a MIDI event and song readers should convert their file format's events to use this.

    The data dictionary will vary per event_type.  See EventType.
    """

    def __init__(self, index: int, track: int, time: float, event_type: "EventType", data: dict = None,
                 channel: int = None):
        """Creates a song event.

        :param index: The index of the event in the MIDI track (used when sorting).
        :param track: The track number for the event.
        :param time: The time of the event from the start of the song, in beats.
        :param event_type: The event type.
        :param data: A data dictionary for the event.  Contents will vary per event_type.
        :param channel: The event channel.  Must be None for sysex and meta event types and an integer for all others.
        """
        # Validate arguments.
        if event_type in [EventType.F0_SYSEX, EventType.F7_SYSEX, EventType.META]:
            if channel is not None:
                raise ValueError(f"Channel must be None for {str(event_type)} events.")
        elif channel is None or type(channel) is not int:
            raise ValueError(f"Channel must be an integer for {str(event_type)} events.")
        if event_type == EventType.META and "meta_type" not in data:
            raise ValueError(f"{str(event_type)} events must have a 'meta_type' data entry.")
        # Set fields.
        self.index = index
        self.track = track
        self.time = time
        self.type = event_type
        self.data = data
        self.channel = channel  # _typing.Optional[int]

    def __repr__(self):
        text = f"{self.time:0.3f}: {str(self.type)} - #{self.index}"
        if self.type == EventType.META:
            text += f" - {str(self.data['meta_type'])}"
        elif self.channel is not None:
            text += f" - ch {self.channel}"
        return f"[{text} - {self.data}]"

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __eq__(self, other: "SongEvent"):
        if self.time != other.time:
            return False
        if _EVENT_TYPE_ORDER[self.type] != _EVENT_TYPE_ORDER[other.type]:
            return False
        if self.channel != other.channel:
            return False
        if self.track != other.track:
            return False
        if self.index != other.index:
            return False
        return True

    def __lt__(self, other: "SongEvent"):
        if self.time < other.time:
            return True
        elif self.time > other.time:
            return False
        if _EVENT_TYPE_ORDER[self.type] < _EVENT_TYPE_ORDER[other.type]:
            return True
        elif _EVENT_TYPE_ORDER[self.type] > _EVENT_TYPE_ORDER[other.type]:
            return False
        # Non-channel events are "less than" channel events.
        self_channel = -1 if self.channel is None else self.channel
        other_channel = -1 if other.channel is None else other.channel
        if self_channel < other_channel:
            return True
        elif self_channel > other_channel:
            return False
        if self.track < other.track:
            return True
        elif self.track > other.track:
            return False
        return self.index < other.index


class EventType(IntEnum):
    """Song event types.

    Data dictionary for each type:
     * NOTE_OFF: "note", "velocity"
     * NOTE_ON: "note", "velocity"
     * POLYPHONIC_KEY_PRESSURE: "note", "pressure"
     * CONTROLLER_CHANGE: "controller", "value"
     * PROGRAM_CHANGE: "program"
     * CHANNEL_KEY_PRESSURE: "pressure"
     * PITCH_BEND: "amount" from -1.0 to 1.0 where 0 = center.  Scale to the channel's bend sensitivity.
     * F0_SYSEX: "data"
     * F7_SYSEX: "data"
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


_EVENT_TYPE_ORDER = {
    EventType.NOTE_OFF: 10,
    EventType.NOTE_ON: 100,
    EventType.POLYPHONIC_KEY_PRESSURE: 40,
    EventType.CONTROLLER_CHANGE: 2,  # Controller changes are high priority (volume), just lower than program change.
    EventType.PROGRAM_CHANGE: 1,  # Program changes are high priority.
    EventType.CHANNEL_KEY_PRESSURE: 50,
    EventType.PITCH_BEND: 30,
    EventType.F0_SYSEX: 0,
    EventType.F7_SYSEX: 0,
    EventType.META: 0,  # Tempo changes, for example, should be high priority.
}


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
     * SMPTE_OFFSET: "hours", "minutes", "seconds", "frames", "fractional_frames"
     * TIME_SIGNATURE: "numerator", "denominator", "midi_clocks_per_metronome_tick", "number_of_32nd_notes_per_beat"
     * KEY_SIGNATURE: "sharps_flats", "major_minor"
     * SEQUENCER_SPECIFIC: "data"
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
    SMPTE_OFFSET = 0x54,
    TIME_SIGNATURE = 0x58,
    KEY_SIGNATURE = 0x59,
    SEQUENCER_SPECIFIC = 0x7f,


class ControllerType(IntEnum):
    """MIDI controller type codes."""
    BANK_SELECT_MSB = 0,  # Allows user to switch bank for patch selection. Program change used with Bank Select.
    MODULATION_WHEEL_MSB = 1,  # Generally controls a vibrato effect (pitch, loudness, brightness), depends on patch.
    BREATH_CONTROLLER_MSB = 2,  # Often used with aftertouch messages. Can be used for modulation as well.
    # 3 is undefined
    FOOT_CONTROLLER_MSB = 4,  # Often used with aftertouch messages. Values based on how the pedal is used.
    PORTAMENTO_TIME_MSB = 5,  # Controls portamento rate to slide between 2 notes played subsequently.
    DATA_ENTRY_MSB = 6,  # Controls Value for NRPN or RPN parameters.
    VOLUME_MSB = 7,  # Control the volume of the channel
    BALANCE_MSB = 8,  # Controls balance, generally for stereo patches.  0 = hard left, 64 = center, 127 = hard right
    # 9 is undefined
    PAN_MSB = 10,  # Controls panning, generally for mono patches.  0 = hard left, 64 = center, 127 = hard right
    EXPRESSION_MSB = 11,  # Expression is a percentage of volume (CC7).
    EFFECT_1_MSB = 12,  # Usually used to control a parameter of an effect within the synth/workstation.
    EFFECT_2_MSB = 13,  # Usually used to control a parameter of an effect within the synth/workstation.
    # 14-15 are undefined
    GENERAL_PURPOSE_1_MSB = 16,
    GENERAL_PURPOSE_2_MSB = 17,
    GENERAL_PURPOSE_3_MSB = 18,
    GENERAL_PURPOSE_4_MSB = 19,
    # 20-31 are undefined
    BANK_SELECT_LSB = 32,
    MODULATION_WHEEL_LSB = 33,
    BREATH_CONTROLLER_LSB = 34,
    # 35 is undefined
    FOOT_CONTROLLER_LSB = 36,
    PORTAMENTO_TIME_LSB = 37,
    DATA_ENTRY_LSB = 38,
    VOLUME_LSB = 39,
    BALANCE_LSB = 40,
    # 41 is undefined
    PAN_LSB = 42,
    EXPRESSION_LSB = 43,
    EFFECT_1_LSB = 44,
    EFFECT_2_LSB = 45,
    # 46-47 are undefined
    GENERAL_PURPOSE_1_LSB = 48,
    GENERAL_PURPOSE_2_LSB = 49,
    GENERAL_PURPOSE_3_LSB = 50,
    GENERAL_PURPOSE_4_LSB = 51,
    # 52-63 are undefined
    # For On/Off switches: 0..63 = Off, 64..127 = On
    SUSTAIN_PEDAL_SWITCH = 64,  # On/Off switch for sustain. (See also Sostenuto CC 66.)
    PORTAMENTO_SWITCH = 65,  # On/Off switch.
    SOSTENUTO_SWITCH = 66,  # On/Off switch.  Holds notes that are currently "on". (See also Sustain CC 64)
    SOFT_PEDAL_SWITCH = 67,  # On/Off switch. Lowers the volume of notes played.
    LEGATO_FOOTSWITCH = 68,  # On/Off switch. Turns Legato effect between two subsequent notes On or Off.
    HOLD_2_SWITCH = 69,  # On/Off switch.  Holds notes, but fades using their release param not pedal.  (see CC 64, 66)
    SOUND_CONTROLLER_1 = 70,  # Usually controls the way a sound is produced. Default = Sound Variation
    SOUND_CONTROLLER_2 = 71,  # Allows shaping the Voltage Controlled Filter (VCF). Default = Timbre/Harmonic Intensity
    SOUND_CONTROLLER_3 = 72,  # Controls release time of the Voltage controlled Amplifier (VCA). Default = Release Time
    SOUND_CONTROLLER_4 = 73,  # Controls the “Attack’ of a sound.
    SOUND_CONTROLLER_5 = 74,  # Controls VCFs cutoff frequency of the filter.  Brightness
    SOUND_CONTROLLER_6 = 75,  # Default: Decay Time
    SOUND_CONTROLLER_7 = 76,  # Default: Vibrato Rate
    SOUND_CONTROLLER_8 = 77,  # Default: Vibrato Depth
    SOUND_CONTROLLER_9 = 78,  # Default: Vibrato Delay
    SOUND_CONTROLLER_10 = 79,
    XG_FILTER_RESONANCE = SOUND_CONTROLLER_2
    XG_RELEASE_TIME = SOUND_CONTROLLER_3
    XG_ATTACK_TIME = SOUND_CONTROLLER_4
    XG_BRIGHTNESS = SOUND_CONTROLLER_5
    XG_DECAY_TIME = SOUND_CONTROLLER_6
    XG_VIBRATO_RATE = SOUND_CONTROLLER_7
    XG_VIBRATO_DEPTH = SOUND_CONTROLLER_8
    XG_VIBRATO_DELAY = SOUND_CONTROLLER_9
    GENERAL_PURPOSE_5 = 80,  # Generic On/Off switch
    GENERAL_PURPOSE_6 = 81,  # Generic On/Off switch
    GENERAL_PURPOSE_7 = 82,  # Generic On/Off switch
    GENERAL_PURPOSE_8 = 83,  # Generic On/Off switch
    PORTAMENTO_AMOUNT = 84,
    # 85-90 are undefined
    EFFECTS_1_DEPTH = 91,  # Usually controls reverb send amount
    EFFECTS_2_DEPTH = 92,  # Usually controls tremolo amount
    EFFECTS_3_DEPTH = 93,  # Usually controls chorus amount
    EFFECTS_4_DEPTH = 94,  # Usually controls detune amount
    EFFECTS_5_DEPTH = 95,  # Usually controls phaser amount
    REVERB_DEPTH = EFFECTS_1_DEPTH
    TREMOLO_DEPTH = EFFECTS_2_DEPTH
    CHORUS_DEPTH = EFFECTS_3_DEPTH
    DETUNE_DEPTH = EFFECTS_4_DEPTH
    PHASER_DEPTH = EFFECTS_5_DEPTH
    DATA_INCREMENT = 96,  # Usually used to increment data for RPN and NRPN messages.
    DATA_DECREMENT = 97,  # Usually used to decrement data for RPN and NRPN messages.
    NRPN_LSB = 98,  # For controllers 6, 38, 96, and 97 it selects the NRPN parameter.
    NRPN_MSB = 99,  # For controllers 6, 38, 96, and 97 it selects the NRPN parameter.
    RPN_LSB = 100,  # For controllers 6, 38, 96, and 97 it selects the RPN parameter.
    RPN_MSB = 101,  # For controllers 6, 38, 96, and 97 it selects the RPN parameter.
    # 102-119 are undefined
    ALL_SOUND_OFF = 120
    RESET_ALL_CONTROLLERS = 121
    LOCAL_ON_OFF_SWITCH = 122
    ALL_NOTES_OFF = 123
    OMNI_MODE_OFF = 124
    OMNI_MODE_ON = 125
    MONOPHONIC_MODE = 126
    POLYPHONIC_MODE = 127

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, int) and 0 <= value <= 127:
            _logging.debug(f"Found undefined controller value {value}.  Creating definition.")
            return cls._create_pseudo_member_(value)
        return None

    @classmethod
    def _create_pseudo_member_(cls, value):
        pseudo_member = cls._value2member_map_.get(value, None)
        if pseudo_member is None:
            pseudo_member = int.__new__(cls)
            pseudo_member._name_ = f"UNDEFINED_{value}"
            pseudo_member._value_ = value
            pseudo_member = cls._value2member_map_.setdefault(value, pseudo_member)
        return pseudo_member

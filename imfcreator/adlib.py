"""**Adlib Information**

This module contains fields and classes representing Adlib register values and instruments.
"""
import logging as _logging

OPL_CHANNELS = 9

# OPERATORS
MODULATORS = [0, 1, 2, 8, 9, 10, 16, 17, 18]
CARRIERS = [m + 3 for m in MODULATORS]

# REGISTERS
TEST_MSG = 0x1                  # Chip-wide
TIMER_1_COUNT_MSG = 0x2         # Chip-wide
TIMER_2_COUNT_MSG = 0x3         # Chip-wide
IRQ_RESET_MSG = 0x4             # Chip-wide
COMP_SINE_WAVE_MODE_MSG = 0x8   # Chip-wide
VIBRATO_MSG = 0x20              # Operator-based
VOLUME_MSG = 0x40               # Operator-based
ATTACK_DECAY_MSG = 0x60         # Operator-based
SUSTAIN_RELEASE_MSG = 0x80      # Operator-based
FREQ_MSG = 0xa0                 # Channel-based
BLOCK_MSG = 0xb0                # Channel-based
DRUM_MSG = 0xbd                 # Percussion mode: Tremolo / Vibrato / Percussion Mode / BD/SD/TT/CY/HH On
FEEDBACK_MSG = 0xc0             # Channel-based
WAVEFORM_SELECT_MSG = 0xe0      # # Operator-based

# BLOCK_MSG Bit Masks
KEY_OFF_MASK = 0x0  # 0000 0000
KEY_ON_MASK = 0x20  # 0010 0000
# BLOCK_MASK = 0x1c   # 0001 1100, >> 2 to get the block number
# FREQ_MSB_MASK = 0x3 # 0000 0011

BLOCK_FREQ_NOTE_MAP = [  # f-num = freq * 2^(20 - block) / 49716
    # (0, 172), (0, 183), (0, 194), (0, 205), (0, 217), (0, 230),
    # (0, 244), (0, 258), (0, 274), (0, 290), (0, 307), (0, 326),
    # MUSPLAY and the HERETIC source start with these values. Otherwise, the music sounds an octave lower.
    (0, 345), (0, 365), (0, 387), (0, 410), (0, 435), (0, 460),
    (0, 488), (0, 517), (0, 547), (0, 580), (0, 615), (0, 651),
    (0, 690), (0, 731), (0, 774), (0, 820), (0, 869), (0, 921),
    (0, 975), (1, 517), (1, 547), (1, 580), (1, 615), (1, 651),
    (1, 690), (1, 731), (1, 774), (1, 820), (1, 869), (1, 921),
    (1, 975), (2, 517), (2, 547), (2, 580), (2, 615), (2, 651),
    (2, 690), (2, 731), (2, 774), (2, 820), (2, 869), (2, 921),
    (2, 975), (3, 517), (3, 547), (3, 580), (3, 615), (3, 651),
    (3, 690), (3, 731), (3, 774), (3, 820), (3, 869), (3, 921),
    (3, 975), (4, 517), (4, 547), (4, 580), (4, 615), (4, 651),
    (4, 690), (4, 731), (4, 774), (4, 820), (4, 869), (4, 921),
    (4, 975), (5, 517), (5, 547), (5, 580), (5, 615), (5, 651),
    (5, 690), (5, 731), (5, 774), (5, 820), (5, 869), (5, 921),
    (5, 975), (6, 517), (6, 547), (6, 580), (6, 615), (6, 651),
    (6, 690), (6, 731), (6, 774), (6, 820), (6, 869), (6, 921),
    (6, 975), (7, 517), (7, 547), (7, 580), (7, 615), (7, 651),
    (7, 690), (7, 731), (7, 774), (7, 820), (7, 869), (7, 921),
    (7, 975)
    # , (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023),
    # (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023)
]

# PERCUSSION MODE
PERCUSSION_MODE_BASS_DRUM_MODULATOR = 12
PERCUSSION_MODE_BASS_DRUM_CARRIER = 15
PERCUSSION_MODE_SNARE_DRUM = 16
PERCUSSION_MODE_TOM_TOM = 14
PERCUSSION_MODE_CYMBAL = 17
PERCUSSION_MODE_HI_HAT = 13

PERCUSSION_MODE_TREMOLO_MASK = 0b10000000
PERCUSSION_MODE_VIBRATO_MASK = 0b01000000
PERCUSSION_MODE_PERCUSSION_MODE_MASK = 0b00100000
PERCUSSION_MODE_BASS_DRUM_MASK = 0b00010000
PERCUSSION_MODE_SNARE_DRUM_MASK = 0b00001000
PERCUSSION_MODE_TOM_TOM_MASK = 0b00000100
PERCUSSION_MODE_CYMBAL_MASK = 0b00000010
PERCUSSION_MODE_HI_HAT_MASK = 0b00000001


class AdlibInstrument(object):
    """Represents an Adlib instrument.

    Instruments can contain one or more voices, each consisting of a modulator and a carrier.
    This is based upon the instrument information in an OP2 file.
    """

    def __init__(self, name=None, num_voices: int = 1):
        self.name = name
        """The name of the instrument, if one is available."""
        self.use_given_note = False
        """When true, this instrument acts like a percussion instrument using given_note."""
        self.use_secondary_voice = False
        """When true, the second voice can be used in addition to the first.
        Also, fine_tuning should be taken into account.
        """
        # Fine tune value is an index offset of frequencies table. 128 is a center, i.e. don't detune.
        # Formula of index offset is: (fine_tune / 2) - 64.
        # Each unit of fine tune field is approximately equal to 1/0.015625 of tone.
        self.fine_tuning = 0x80  # 8-bit, 0x80 = center
        self.given_note = 0  # 8-bit, for percussion
        self.num_voices = num_voices
        # Voice settings.
        self.modulator = [AdlibOperator() for _ in range(num_voices)]
        self.carrier = [AdlibOperator() for _ in range(num_voices)]
        self.feedback = [0] * num_voices  # 8-bit
        self.note_offset = [0] * num_voices  # 16-bit, signed

    def __repr__(self):
        return str(self.__dict__)

    def get_regs(self, channel: int, voice: int = 0):
        mod_op = MODULATORS[channel]
        car_op = CARRIERS[channel]
        return [
            (VIBRATO_MSG | mod_op, self.modulator[voice].tvskm),
            (VOLUME_MSG | mod_op, self.modulator[voice].ksl_output),
            (ATTACK_DECAY_MSG | mod_op, self.modulator[voice].attack_decay),
            (SUSTAIN_RELEASE_MSG | mod_op, self.modulator[voice].sustain_release),
            (WAVEFORM_SELECT_MSG | mod_op, self.modulator[voice].waveform_select),
            (VIBRATO_MSG | car_op, self.carrier[voice].tvskm),
            (VOLUME_MSG | car_op, self.carrier[voice].ksl_output),
            (ATTACK_DECAY_MSG | car_op, self.carrier[voice].attack_decay),
            (SUSTAIN_RELEASE_MSG | car_op, self.carrier[voice].sustain_release),
            (WAVEFORM_SELECT_MSG | car_op, self.carrier[voice].waveform_select),
            (FEEDBACK_MSG | channel, self.feedback[voice]),  # | 0x30),
        ]

    def registers_match(self, other: "AdlibInstrument"):
        if self.num_voices != other.num_voices:
            return False
        for v in range(self.num_voices):
            if self.modulator[v] != other.modulator[v]:
                return False
            if self.carrier[v] != other.carrier[v]:
                return False
            if self.feedback[v] != other.feedback[v]:
                return False
        return True

    def compare_registers(self, other: "AdlibInstrument"):
        # TODO if self.num_voices != other.num_voices:
        #     return False
        count = 0
        for v in range(min(self.num_voices, other.num_voices)):
            count += self.modulator[v].compare_registers(other.modulator[v])
            count += self.carrier[v].compare_registers(other.carrier[v])
            if self.feedback[v] != other.feedback[v]:
                count += 1
        return count

    def get_play_note(self, note: int, voice: int = 0):
        if self.use_given_note:
            note = self.given_note
        note += self.note_offset[voice]
        if note < 0 or note > 127:
            _logging.error(f"Note went out of range: {note}")
            while note < 0:
                note += 12
            while note > 127:
                note -= 12
        return note


def _create_bit_property(var_name: str, bits: int, shift: int):
    """Creates a property that is a bit-wise representation of a register.

    The property performs bitshifting and value range checks.
    """
    max_value = 2 ** bits - 1
    return property(
        fget=lambda self: (getattr(self, var_name) >> shift) & max_value,
        fset=lambda self, value: setattr(self, var_name,
                                         (getattr(self, var_name) & ~(max_value << shift))
                                         | (_check_range(value, max_value) << shift))
    )


class AdlibOperator(object):  # MUST inherit from object for properties to work.
    """Represents an adlib operator's register values."""

    def __init__(self, tvskm: int = 0, ksl_output: int = 0, attack_decay: int = 0, sustain_release: int = 0,
                 waveform_select: int = 0):
        self.tvskm = 0  # tvskffff = tremolo, vibrato, sustain, ksr, frequency multiplier
        self.ksl_output = 0  # kkoooooo = key scale level, output level
        self.attack_decay = 0  # aaaadddd = attack rate, decay rate
        self.sustain_release = 0  # ssssrrrr = sustain level, release rate
        self.waveform_select = 0  # -----www = waveform select
        self.set_regs(tvskm, ksl_output, attack_decay, sustain_release, waveform_select)

    # Bit-level properties.
    tremolo = _create_bit_property("tvskm", 1, 7)
    vibrato = _create_bit_property("tvskm", 1, 6)
    sustain = _create_bit_property("tvskm", 1, 5)
    ksr = _create_bit_property("tvskm", 1, 4)
    freq_mult = _create_bit_property("tvskm", 4, 0)
    key_scale_level = _create_bit_property("ksl_output", 2, 6)
    output_level = _create_bit_property("ksl_output", 6, 0)
    attack_rate = _create_bit_property("attack_decay", 4, 4)
    decay_rate = _create_bit_property("attack_decay", 4, 0)
    sustain_level = _create_bit_property("sustain_release", 4, 4)
    release_rate = _create_bit_property("sustain_release", 4, 0)

    def set_regs(self, tvskm: int, ksl_output: int, attack_decay: int, sustain_release: int,
                 waveform_select: int) -> None:
        """Sets all operator register values."""
        self.tvskm = tvskm
        self.ksl_output = ksl_output
        self.attack_decay = attack_decay
        self.sustain_release = sustain_release
        self.waveform_select = waveform_select

    def compare_registers(self, other: "AdlibOperator"):
        count = 0
        if self.tvskm != other.tvskm:
            count += 1
        # if self.ksl_output != other.ksl_output:
        #     count += 1
        if self.attack_decay != other.attack_decay:
            count += 1
        if self.sustain_release != other.sustain_release:
            count += 1
        if self.waveform_select != other.waveform_select:
            count += 1
        return count

    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


def _check_range(value: int, max_value: int):
    """Checks a value to verify that it is between 0 and maxvalue, inclusive."""
    if value is None:
        raise ValueError("Value is required.")
    if 0 <= value <= max_value:
        return value
    else:
        raise ValueError(f"Value should be between 0 and {max_value} inclusive. Got: {value}.")


def get_repr_adlib_reg(reg: int, value: int, delay: int):
    # Do not change anything in here.  Doing so will screw up the tests.
    text = f"{delay:<5d}: {reg:#04x} <= {value:#04x} ({value:08b}): "

    def get_operator_str():
        r = reg % 0x20
        try:
            return f"ch {MODULATORS.index(r)} mod"
        except ValueError:
            return f"ch {CARRIERS.index(r)} car"

    def get_channel_str():
        return f"ch {reg % 0x10}"

    def get_bits(shift: int, bit_count: int = 1):
        max_value = 2 ** bit_count - 1
        return (value >> shift) & max_value

    def get_on_off(bit: int, on_text="ON", off_text="OFF"):
        return on_text if get_bits(bit) else off_text

    if reg == TEST_MSG:
        text += f"Test Register / Waveform Select: {get_on_off(5)}"  # (--w-----)"
    elif reg == TIMER_1_COUNT_MSG:
        text += "Timer 1"
    elif reg == TIMER_2_COUNT_MSG:
        text += "Timer 2"
    elif reg == IRQ_RESET_MSG:
        text += "Timer Mask/Control / IRQ Reset"  # (imm---cc)"
    elif reg == COMP_SINE_WAVE_MODE_MSG:
        text += "CSM Mode / Keyboard Split"  # (ck------)"
    elif VIBRATO_MSG <= reg <= VIBRATO_MSG + 0x15:
        text += f"{get_operator_str()} - "
        text += f"AM: {get_on_off(7)}, Vibr: {get_on_off(6)}, Env: {get_on_off(5)}, " \
                f"KSR: {get_on_off(5)}, Freq Mult: {get_bits(0, 4)}"  # (avekffff)
    elif VOLUME_MSG <= reg <= VOLUME_MSG + 0x15:
        text += f"{get_operator_str()} - "
        text += f"Volume: {get_bits(0, 6)}, KSL: {get_bits(6, 2)}"  # (ssvvvvvv)
    elif ATTACK_DECAY_MSG <= reg <= ATTACK_DECAY_MSG + 0x15:
        text += f"{get_operator_str()} - "
        text += f"Attack: {get_bits(4, 4)},  Decay {get_bits(0, 4)}"  # (aaaadddd)
    elif SUSTAIN_RELEASE_MSG <= reg <= SUSTAIN_RELEASE_MSG + 0x15:
        text += f"{get_operator_str()} - "
        text += f"Sustain: {get_bits(4, 4)}, Release {get_bits(0, 4)}"  # (ssssrrrr)
    elif FREQ_MSG <= reg <= FREQ_MSG + 0x08:
        text += f"{get_channel_str()} - "
        text += f"Freq: {value}"
    elif BLOCK_MSG <= reg <= BLOCK_MSG + 0x08:
        text += f"{get_channel_str()} - "
        text += f"Oct: {get_bits(2, 3)}, Freq (msb): {get_bits(0, 2)}, Key {get_on_off(5)}"  # (--koooff)
    elif reg == DRUM_MSG:
        text += f"{get_on_off(5, 'Percussion', 'Melodic')} mode, Trem: {get_bits(7)}, Vibr: {get_bits(6)}"
        text += "".join([get_on_off(4, ", BD", ""),
                         get_on_off(3, ", SD", ""),
                         get_on_off(2, ", TT", ""),
                         get_on_off(1, ", CY", ""),
                         get_on_off(0, ", HH", "")])  # (avrbstch)
    elif FEEDBACK_MSG <= reg <= FEEDBACK_MSG + 0x08:
        text += f"{get_channel_str()} - "
        text += f"Feedback: {get_bits(1, 3)}, {get_on_off(0, 'Freq Mod', 'Additive')} synthesis"  # (----fffd)
    elif WAVEFORM_SELECT_MSG <= reg <= WAVEFORM_SELECT_MSG + 0x15:
        text += f"{get_operator_str()} - "
        text += f"Waveform: {get_bits(0, 2)}"  # (------ww)
    else:
        text += "UNKNOWN"
    return text

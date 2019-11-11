import instrumentfile
from .instrumentfile import InstrumentFile
from ..adlib import AdlibInstrument
from ._binary import u8, u16le, s16le

from ..instrumentnames import GM2_DRUM_NOTE_MAPPING


def _accept(preview):
    return preview[0:8] == "#OPL_II#"


class Op2FilePlugin(InstrumentFile):
    ID = "OP2"
    DESCRIPTION = "OPL2 DMX Sound Library"
    ENTRY_START = 8
    ENTRY_SIZE = 36
    NUM_ENTRIES = 175 + 14  # Always 175 for OP2 files. (and +14 for GM2 mapping aliases)
    NAME_START = ENTRY_START + ENTRY_SIZE * NUM_ENTRIES
    NAME_SIZE = 32
    FLAG_USE_GIVEN_NOTE = 1
    FLAG_UNKNOWN = 2
    FLAG_USE_SECONDARY_VOICE = 4
    # FLAG_USE_FINE_TUNING = 4???
    _last_entry = 0
    _patch_override = None
    _is_drum = False

    GM2_DRUM_NOTE_OPL2_EXTRA = [
        27,  # "High Q"
        28,  # "Slap"
        29,  # "Scratch Push"
        30,  # "Scratch Pull"
        31,  # "Sticks"
        32,  # "Square Click"
        33,  # "Metronome Click"
        34,  # "Metronome Bell"
        82,  # "Shaker"
        83,  # "Jingle Bell"
        84,  # "Belltree"
        85,  # "Castanets"
        86,  # "Mute Surdo"
        87,  # "Open Surdo"
    ]

    def _open(self):
        self.seek(0)

    def _load(self):
        pass

    def seek(self, index):
        assert index is not None
        if index >= 175:  # 0...174 - file data, and 175+ - GM2 drums aliases
            self._patch_override = self.GM2_DRUM_NOTE_OPL2_EXTRA[index - 175]
            self._is_drum = True
            index = 128 + GM2_DRUM_NOTE_MAPPING.get(self._patch_override, None) - 35
        self.info = [
            Op2FilePlugin.ENTRY_START + index * Op2FilePlugin.ENTRY_SIZE,
            Op2FilePlugin.NAME_START + index * Op2FilePlugin.NAME_SIZE,
        ]

    def load(self):
        entry_offset, name_offset = self.info
        self.info = []
        # Read entry and name from file.
        self.fp.seek(entry_offset)
        entry = self.fp.read(Op2FilePlugin.ENTRY_SIZE)
        self.fp.seek(name_offset)
        name = self.fp.read(Op2FilePlugin.NAME_SIZE).partition('\x00')[0]
        # Set up the instrument.
        instrument = AdlibInstrument(name=name, num_voices=2)
        flags = u16le(entry[0:2])
        instrument.use_secondary_voice = flags & Op2FilePlugin.FLAG_USE_SECONDARY_VOICE
        instrument.use_given_note = flags & Op2FilePlugin.FLAG_USE_GIVEN_NOTE
        instrument.fine_tuning = u8(entry[2])
        instrument.given_note = u8(entry[3])
        Op2FilePlugin._read_voice(instrument, 0, entry[4:20])
        Op2FilePlugin._read_voice(instrument, 1, entry[20:36])
        instrument.bank_msb = 0
        instrument.bank_lsb = 0
        instrument.patch_id = self._last_entry if self._patch_override is None else self._patch_override
        instrument.bank_is_percussion = self._is_drum
        if self._patch_override is None:
            self._last_entry += 1
            if self._last_entry >= 128:
                self._is_drum = True
                self._last_entry = 35
        return instrument

    @staticmethod
    def _read_voice(instrument, voice_number, data):
        instrument.modulator[voice_number].set_regs(**Op2FilePlugin._get_operator_regs(data[0:6]))
        instrument.feedback[voice_number] = u8(data[6])
        instrument.carrier[voice_number].set_regs(**Op2FilePlugin._get_operator_regs(data[7:13]))
        # entry[13] = unused
        instrument.note_offset[voice_number] = s16le(data[14:16])

    @staticmethod
    def _get_operator_regs(data):
        return {
            "tvskm": u8(data[0]),
            "attack_decay": u8(data[1]),
            "sustain_release": u8(data[2]),
            "waveform_select": u8(data[3]),
            "ksl_output": u8(data[4]) | u8(data[5])
        }

    @property
    def num_instruments(self):
        return Op2FilePlugin.NUM_ENTRIES


# Register the plugin.
instrumentfile.register_open(Op2FilePlugin.ID, Op2FilePlugin, _accept)

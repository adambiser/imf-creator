import instrumentfile
from .instrumentfile import InstrumentFile
from ..adlib import AdlibInstrument
from ._binary import u8, u16le, s16le


def _accept(preview):
    return preview[0:8] == "#OPL_II#"


class Op2FilePlugin(InstrumentFile):
    ID = "OP2"
    DESCRIPTION = "OPL2 DMX Sound Library"
    ENTRY_START = 8
    ENTRY_SIZE = 36
    NUM_ENTRIES = 175  # Always 175 for OP2 files.
    NAME_START = ENTRY_START + ENTRY_SIZE * NUM_ENTRIES
    NAME_SIZE = 32
    FLAG_USE_GIVEN_NOTE = 1
    FLAG_UNKNOWN = 2
    FLAG_USE_SECONDARY_VOICE = 4
    # FLAG_USE_FINE_TUNING = 4???

    def _open(self):
        self.seek(0)

    def seek(self, index):
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

import instrumentfile
from .instrumentfile import InstrumentFile
from ..adlib import AdlibInstrument
from ._binary import u8, s8, u16le, u16be, s16be


def _accept(preview):
    return preview[0:11] == "WOPL3-BANK\0"


class WoplFilePlugin(InstrumentFile):
    ID = "WOPL"
    DESCRIPTION = "Wohlstand's OPL3 bank file"
    _version = 0
    _mbanks = 0
    _pbanks = 0
    _flags = 0x00
    _volumeModel = 0
    NUM_ENTRIES = 0
    INSTRUMENT_ENTRY_START = -1
    BANK_META_ENTRY_START = -1
    ENTRY_SIZE = -1
    BANK_META_ENTRY_SIZE = -1
    OFFSET_MELODIC_INSTS = -1
    OFFSET_PERCUSIVE_INSTS = -1
    OFFSET_MELODIC_METAS = -1
    OFFSET_PERCUSIVE_METAS = -1

    bank_entry = None
    _is_drum = False
    ins_data = None
    _patch_id = 0

    FLAG_2OP_MODE = 0x00
    FLAG_4OP_MODE = 0x01
    FLAG_Pseudo4OP = 0x02
    FLAG_IS_BLANK = 0x04
    FLAG_RHYTHM_MASK = 0x38

    def _open(self):
        self.fp.seek(0)
        magic = self.fp.read(11)
        if magic != "WOPL3-BANK\0":
            raise ValueError("Bad WOPL file: invalid magic number!")
        self._version = u16le(self.fp.read(2))
        if self._version == 3:
            self.BANK_META_ENTRY_START = 19
            self.BANK_META_ENTRY_SIZE = 32 + 1 + 1
            self.ENTRY_SIZE = 66
        elif self._version == 2:
            self.BANK_META_ENTRY_START = 19
            self.BANK_META_ENTRY_SIZE = 32 + 1 + 1
            self.ENTRY_SIZE = 62
        elif self._version == 1:
            self.INSTRUMENT_ENTRY_START = 19
            self.ENTRY_SIZE = 62
        else:
            raise ValueError("WOPL of version %d is not supported yet!" % self._version)
        self._mbanks = u16be(self.fp.read(2))
        self._pbanks = u16be(self.fp.read(2))
        self._flags = u8(self.fp.read(1))
        self._volumeModel = u8(self.fp.read(1))
        if self._version >= 2:
            self.INSTRUMENT_ENTRY_START = self.BANK_META_ENTRY_START + \
                                          ((self._mbanks + self._pbanks) * self.BANK_META_ENTRY_SIZE)
            self.OFFSET_MELODIC_METAS = self.BANK_META_ENTRY_START
            self.OFFSET_PERCUSIVE_METAS = self.BANK_META_ENTRY_START + (self._mbanks * self.BANK_META_ENTRY_SIZE)
        self.OFFSET_MELODIC_INSTS = self.INSTRUMENT_ENTRY_START
        self.OFFSET_PERCUSIVE_INSTS = self.INSTRUMENT_ENTRY_START + (self._mbanks * self.ENTRY_SIZE * 128)
        self.NUM_ENTRIES = (self._mbanks + self._pbanks) * 128

    def _load(self):
        pass

    def seek(self, index):
        assert index is not None
        assert index < self.NUM_ENTRIES
        bank = (index - (index % 128)) / 128
        if self._version >= 2:
            self.fp.seek(self.BANK_META_ENTRY_START + (bank * self.BANK_META_ENTRY_SIZE))
            self.bank_entry = dict()
            self.bank_entry["name"] = self.fp.read(32).decode("utf-8")
            self.bank_entry["lsb"] = u8(self.fp.read(1))
            self.bank_entry["msb"] = u8(self.fp.read(1))
        to_offset = self.INSTRUMENT_ENTRY_START + (index * self.ENTRY_SIZE)
        self._is_drum = True if to_offset >= self.OFFSET_PERCUSIVE_INSTS else False
        self.fp.seek(to_offset)
        self.ins_data = self.fp.read(self.ENTRY_SIZE)
        self._patch_id = index % 128 if not self._is_drum else ((index - (self._mbanks * 128)) % 128)
        pass

    def load(self):
        instrument = AdlibInstrument(name=self.ins_data[0:32].decode('utf-8'), num_voices=2)
        instrument.note_offset[0] = s16be(self.ins_data[32:34]) - 12
        instrument.note_offset[1] = s16be(self.ins_data[34:36]) - 12
        flags = u8(self.ins_data[39])
        if flags & self.FLAG_IS_BLANK:
            return None  # Skip blank instruments
        if flags & self.FLAG_RHYTHM_MASK:
            return None  # Rhythm-mode instruments doesn't supported
        if flags & self.FLAG_4OP_MODE and not flags & self.FLAG_Pseudo4OP:
            return None  # true 4-operator instruments aren't supported
        instrument.use_secondary_voice = True if flags & self.FLAG_4OP_MODE and flags & self.FLAG_Pseudo4OP else False
        instrument.use_given_note = self._is_drum
        instrument.fine_tuning = u8(self.ins_data[37])
        instrument.given_note = u8(self.ins_data[38])
        instrument.bank_msb = self.bank_entry["msb"] if self.bank_entry else 0
        instrument.bank_lsb = self.bank_entry["lsb"] if self.bank_entry else 0
        instrument.patch_id = self._patch_id
        instrument.bank_is_percussion = self._is_drum
        fb1 = u8(self.ins_data[40])
        fb2 = u8(self.ins_data[41])
        WoplFilePlugin._read_voice(instrument, 0, fb1, self.ins_data[42:52])
        WoplFilePlugin._read_voice(instrument, 1, fb2, self.ins_data[52:62])
        return instrument

    @staticmethod
    def _read_voice(instrument, voice_number, fb, data):
        instrument.carrier[voice_number].set_regs(**WoplFilePlugin._get_operator_regs(data[0:5]))
        instrument.modulator[voice_number].set_regs(**WoplFilePlugin._get_operator_regs(data[5:10]))
        instrument.feedback[voice_number] = fb

    @staticmethod
    def _get_operator_regs(data):
        return {
            "tvskm": u8(data[0]),
            "ksl_output": u8(data[1]),
            "attack_decay": u8(data[2]),
            "sustain_release": u8(data[3]),
            "waveform_select": u8(data[4])
        }

    @property
    def num_instruments(self):
        return self.NUM_ENTRIES


# Register the plugin.
instrumentfile.register_open(WoplFilePlugin.ID, WoplFilePlugin, _accept)

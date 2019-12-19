import typing as _typing
import imfcreator.adlib as _adlib
import imfcreator.instruments as _instruments
from collections import namedtuple
from . import plugin, InstrumentFile, InstrumentId
from ._binary import u8, s8, u16le, u16be, s16be


_BANK_ENTRY = namedtuple("_BANK_ENTRY", ["name", "lsb", "msb"])


@plugin
class WoplFilePlugin(InstrumentFile):
    DESCRIPTION = "Wohlstand's OPL3 bank file"
    _FILE_SIGNATURE = b"WOPL3-BANK\0"
    # Flags
    _FLAG_2OP_MODE = 0x00
    _FLAG_4OP_MODE = 0x01
    _FLAG_PSEUDO_4OP = 0x02
    _FLAG_IS_BLANK = 0x04
    _FLAG_RHYTHM_MASK = 0x38

    def __init__(self, fp, file):
        # Add instance variables.
        self._instrument_entry_start = None
        self._entry_size = None
        self._bank_meta_entry_start = None
        self._bank_meta_entry_size = None
        super().__init__(fp, file)

    @classmethod
    def accept(cls, preview: bytes, file: str):
        return preview[0:11] == WoplFilePlugin._FILE_SIGNATURE

    def _load_file(self):
        if not WoplFilePlugin.accept(self.fp.read(11), self.file):
            raise ValueError("Bad WOPL file!")
        self._version = u16le(self.fp.read(2))
        if self._version == 1:
            self._instrument_entry_start = 19
            self._entry_size = 62
        elif self._version == 2:
            self._bank_meta_entry_start = 19
            self._bank_meta_entry_size = 32 + 1 + 1
            self._entry_size = 62
        elif self._version == 3:
            self._bank_meta_entry_start = 19
            self._bank_meta_entry_size = 32 + 1 + 1
            self._entry_size = 66
        else:
            raise ValueError(f"WOPL of version {self._version} is not yet supported!")
        self._melodic_bank_count = u16be(self.fp.read(2))
        self._percussive_bank_count = u16be(self.fp.read(2))
        self._flags = u8(self.fp.read(1))
        self._volumeModel = u8(self.fp.read(1))
        if self._version >= 2:
            self._instrument_entry_start = self._bank_meta_entry_start + \
                                          ((self._melodic_bank_count + self._percussive_bank_count) *
                                           self._bank_meta_entry_size)
        self._percussive_inst_offset = self._instrument_entry_start + (self._melodic_bank_count * self._entry_size * 128)
        self._entry_count = (self._melodic_bank_count + self._percussive_bank_count) * 128
        # Load the instruments
        for index in range(self._entry_count):
            instrument_info = self._get_instrument(index)
            if instrument_info:
                self.instruments.update([instrument_info])

    def _get_instrument(self, index: int) -> (InstrumentId, _adlib.AdlibInstrument):
        entry_offset = self._instrument_entry_start + (index * self._entry_size)
        # Read the entry from the file.
        self.fp.seek(entry_offset)
        entry = self.fp.read(self._entry_size)
        # Set up the instrument.
        if entry_offset < self._percussive_inst_offset:
            inst_type = _instruments.MELODIC
        else:
            inst_type = _instruments.PERCUSSION
        program = index % 128
        instrument = _adlib.AdlibInstrument(name=entry[0:32].decode('utf-8'), num_voices=2)
        instrument.note_offset[0] = s16be(entry[32:34]) - 12
        instrument.note_offset[1] = s16be(entry[34:36]) - 12
        flags = u8(entry[39])
        if flags & WoplFilePlugin._FLAG_IS_BLANK:
            return None  # Skip blank instruments.
        if flags & WoplFilePlugin._FLAG_RHYTHM_MASK:
            return None  # Rhythm-mode instruments aren't supported.
        if flags & WoplFilePlugin._FLAG_4OP_MODE and not flags & self._FLAG_PSEUDO_4OP:
            return None  # True 4-operator instruments aren't supported.
        instrument.use_secondary_voice = flags & WoplFilePlugin._FLAG_4OP_MODE and flags & self._FLAG_PSEUDO_4OP
        instrument.use_given_note = inst_type == _instruments.PERCUSSION
        instrument.fine_tuning = u8(entry[37])
        instrument.given_note = u8(entry[38])
        WoplFilePlugin._read_voice(instrument, 0, u8(entry[40]), entry[42:52])
        WoplFilePlugin._read_voice(instrument, 1, u8(entry[41]), entry[52:62])
        bank_entry = self._get_bank_entry(index)
        bank = bank_entry.msb * 128 + bank_entry.lsb if bank_entry else 0
        return InstrumentId(inst_type, bank, program), instrument

    def _get_bank_entry(self, index) -> _typing.Optional[_BANK_ENTRY]:
        if self._version >= 2:
            bank = index // 128
            self.fp.seek(self._bank_meta_entry_start + (bank * self._bank_meta_entry_size))
            name = self.fp.read(32).decode("utf-8")
            lsb = u8(self.fp.read(1))
            msb = u8(self.fp.read(1))
            return _BANK_ENTRY(name, lsb, msb)
        return None

    @staticmethod
    def _read_voice(instrument, voice_number, feedback, data):
        instrument.carrier[voice_number].set_regs(**WoplFilePlugin._get_operator_regs(data[0:5]))
        instrument.modulator[voice_number].set_regs(**WoplFilePlugin._get_operator_regs(data[5:10]))
        instrument.feedback[voice_number] = feedback

    @staticmethod
    def _get_operator_regs(data):
        return {
            "tvskm": u8(data[0]),
            "ksl_output": u8(data[1]),
            "attack_decay": u8(data[2]),
            "sustain_release": u8(data[3]),
            "waveform_select": u8(data[4])
        }

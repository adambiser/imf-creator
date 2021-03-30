import typing as _typing
import imfcreator.adlib as _adlib
import imfcreator.utils as _utils
from . import FileTypeInfo, plugin, InstrumentFile, InstrumentId, InstrumentType
from ._binary import u8, u16le, s16le, get_unicode_text


@plugin
class Op2FilePlugin(InstrumentFile):
    """Read instruments from a DMX Sound Library file."""
    DESCRIPTION = "DMX Sound Library"
    _FILE_SIGNATURE = b"#OPL_II#"
    _FILE_SIZE = 11908
    _ENTRY_START = 8
    _ENTRY_SIZE = 36
    _FIRST_PERCUSSION_ENTRY = 128
    _FIRST_PERCUSSION_PROGRAM = 35
    _ENTRY_COUNT = 175  # Always 175 for OP2 files.
    _NAME_START = _ENTRY_START + _ENTRY_SIZE * _ENTRY_COUNT
    _NAME_SIZE = 32
    _FLAG_USE_GIVEN_NOTE = 1
    _FLAG_UNKNOWN = 2
    _FLAG_USE_SECONDARY_VOICE = 4

    @classmethod
    def _get_filetypes(cls) -> _typing.List[FileTypeInfo]:
        return [
            FileTypeInfo("op2", "DMX Sound Library", "op2")
        ]

    @classmethod
    def accept(cls, preview: bytes, file: str):
        return preview[0:8] == Op2FilePlugin._FILE_SIGNATURE and _utils.get_file_size(file) == cls._FILE_SIZE

    def _load_file(self):
        if not Op2FilePlugin.accept(self.fp.read(8), self.file):
            raise ValueError("Bad OP2 file!")
        for index in range(Op2FilePlugin._ENTRY_COUNT):
            self._add_instrument(*self._get_instrument(index))

    def _get_instrument(self, index: int) -> (InstrumentId, _adlib.AdlibInstrument):
        entry_offset = Op2FilePlugin._ENTRY_START + index * Op2FilePlugin._ENTRY_SIZE
        name_offset = Op2FilePlugin._NAME_START + index * Op2FilePlugin._NAME_SIZE
        # Read entry and name from file.
        self.fp.seek(entry_offset)
        entry = self.fp.read(Op2FilePlugin._ENTRY_SIZE)
        self.fp.seek(name_offset)
        name = get_unicode_text(self.fp.read(Op2FilePlugin._NAME_SIZE))
        # Set up the instrument.
        instrument = _adlib.AdlibInstrument(name=name, num_voices=2)
        flags = u16le(entry[0:2])
        instrument.use_secondary_voice = bool(flags & Op2FilePlugin._FLAG_USE_SECONDARY_VOICE)
        instrument.use_given_note = bool(flags & Op2FilePlugin._FLAG_USE_GIVEN_NOTE)
        instrument.fine_tuning = u8(entry[2])
        instrument.given_note = u8(entry[3])
        Op2FilePlugin._read_voice(instrument, 0, entry[4:20])
        Op2FilePlugin._read_voice(instrument, 1, entry[20:36])
        if index < Op2FilePlugin._FIRST_PERCUSSION_ENTRY:
            inst_type = InstrumentType.MELODIC
            program = index
        else:
            inst_type = InstrumentType.PERCUSSION
            program = index - Op2FilePlugin._FIRST_PERCUSSION_ENTRY + Op2FilePlugin._FIRST_PERCUSSION_PROGRAM
        return InstrumentId(inst_type, 0, program), instrument

    @staticmethod
    def _read_voice(instrument, voice_number, data):
        """Read voice data."""
        instrument.modulator[voice_number].set_regs(**Op2FilePlugin._get_operator_regs(data[0:6]))
        instrument.feedback[voice_number] = u8(data[6])
        instrument.carrier[voice_number].set_regs(**Op2FilePlugin._get_operator_regs(data[7:13]))
        # entry[13] = unused
        instrument.note_offset[voice_number] = s16le(data[14:16])

    @staticmethod
    def _get_operator_regs(data) -> dict:
        """Get the register values from the given data."""
        return {
            "tvskm": u8(data[0]),
            "attack_decay": u8(data[1]),
            "sustain_release": u8(data[2]),
            "waveform_select": u8(data[3]),
            "ksl_output": u8(data[4]) | u8(data[5])
        }

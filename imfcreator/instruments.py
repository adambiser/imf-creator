"""**Instrument Manager**

This loads and stores instruments that the conversion process uses.

Instruments are added using `add`, `add_file`, or `update`.
They are retrieved using `get`.

Bank numbers should be MSB << 7 + LSB since the MSB and LSB values are limited to 0..127.

Use `get_name` to get the instrument name
"""
import logging as _logging
import typing as _typing
from imfcreator.adlib import AdlibInstrument as _AdlibInstrument
from imfcreator.plugins import InstrumentId, InstrumentFile as _InstrumentFile, MidiSongFile as _MidiSongFile
# TODO Add GM2 drum instrument mapping flag and dictionary.

# Instrument types.
MELODIC = 0
PERCUSSION = 1
_TYPE_NAMES = {MELODIC: "MELODIC", PERCUSSION: "PERCUSSION"}

# The key is (inst_type, bank, program), value is the Adlib instrument.
_INSTRUMENTS = {}  # type: _typing.Dict[InstrumentId, _AdlibInstrument]

# List of searches that gave no results.
_WARNINGS = []


def add(inst_type: int, bank: int, program: int, adlib_instrument: _AdlibInstrument):
    """Add an instrument to the instrument manager.

    :param inst_type: The instrument type.  MELODIC or PERCUSSION.
    :param bank: The instrument bank.
    :param program: The program or patch number.
    :param adlib_instrument: The Adlib instrument.
    :return: None
    """
    key = (inst_type, bank, program)
    _validate_args(inst_type, bank, program)
    if key in _INSTRUMENTS:
        _logging.info(f"Replacing instrument {key}")
    _INSTRUMENTS[InstrumentId(*key)] = adlib_instrument


def update(instruments: _typing.Dict[InstrumentId, _AdlibInstrument], bank_offset: int = 0):
    """Updates the instrument dictionary with another instrument dictionary.

    :param instruments: The new instrument dictionary.
    :param bank_offset: Offset by which instrument banks are adjusted.
    """
    # _INSTRUMENTS.update(instruments)
    if instruments:
        for key, instrument in instruments.items():
            add(key.instrument_type, key.bank + bank_offset, key.program, instrument)
        _logging.info(f"Total instruments loaded: {count()}")


def add_file(f, bank_offset: int = 0):
    """Adds all of the instruments in a file.

    :param f: A filename or file object.
    :param bank_offset: Offset by which instrument banks are adjusted.
    """
    try:
        instrument_file = _InstrumentFile.load_file(f)
    except ValueError:
        instrument_file = _MidiSongFile.load_file(f)
    update(instrument_file.instruments, bank_offset)


def count() -> int:
    """Returns the instrument count."""
    return len(_INSTRUMENTS)


def get(inst_type: int, bank: int, program: int) -> _AdlibInstrument:
    """Returns the Adlib instrument based on the given type, program, and bank.

    :param inst_type: The instrument type.  MELODIC or PERCUSSION.
    :param bank: The instrument bank.
    :param program: The program or patch number.
    :return: An Adlib instrument if a match is found; otherwise None.
    """
    _validate_args(inst_type, bank, program)
    key = (inst_type, bank, program)
    if bank > 0:
        if key not in _INSTRUMENTS:
            if key not in _WARNINGS:
                _WARNINGS.append(key)
                _logging.warning(f"Could not find {_TYPE_NAMES[inst_type]} instrument: bank {bank:#06x}, "
                                 f"program {program}.  Trying bank 0.")
            bank = 0
            key = (inst_type, 0, program)
    instrument = _INSTRUMENTS.get(key)
    if instrument is None:
        if key not in _WARNINGS:
            _WARNINGS.append(key)
            _logging.warning(f"Could not find {_TYPE_NAMES[inst_type]} instrument: bank {bank:#06x}, program {program}")
    return instrument


def has(inst_type: int, bank: int, program: int) -> bool:
    """Tests whether an Adlib instrument has been assigned based on the given type, program, and bank.

    :param inst_type: The instrument type.  MELODIC or PERCUSSION.
    :param bank: The instrument bank.
    :param program: The program or patch number.
    :return: A boolean.
    """
    _validate_args(inst_type, bank, program)
    key = (inst_type, bank, program)
    return key in _INSTRUMENTS


def _validate_args(inst_type: int, bank: int, program: int):
    """Validates the entry argument values."""
    if inst_type not in [MELODIC, PERCUSSION]:
        raise ValueError("inst_type must be 0 (MELODIC) or 1 (PERCUSSION).")
    if bank < 0 or bank > 16383:
        raise ValueError("bank must be between 0 and 16383 (inclusive).")
    if program < 0 or program > 127:
        raise ValueError("program must be between 0 and 127 (inclusive).")


def get_name(inst_type: int, program: int) -> str:
    """Returns the instrument name as defined by the MIDI standard."""
    _validate_args(inst_type, 0, program)
    if inst_type == MELODIC:
        return _MELODIC_NAMES[program]
    elif inst_type == PERCUSSION:
        if program in _PERCUSSION_NAMES:
            return _PERCUSSION_NAMES[program]
        return f"Unknown percussion {program}"


_MELODIC_NAMES = [
    "Acoustic Grand Piano",
    "Bright Acoustic Piano",
    "Electric Grand Piano",
    "Honky-tonk Piano",
    "Electric Piano 1",
    "Electric Piano 2",
    "Harpsichord",
    "Clavinet",
    "Celesta",
    "Glockenspiel",
    "Music Box",
    "Vibraphone",
    "Marimba",
    "Xylophone",
    "Tubular Bells",
    "Dulcimer",
    "Drawbar Organ",
    "Percussive Organ",
    "Rock Organ",
    "Church Organ",
    "Reed Organ",
    "Accordion",
    "Harmonica",
    "Tango Accordion",
    "Acoustic Guitar (nylon)",
    "Acoustic Guitar (steel)",
    "Electric Guitar (jazz)",
    "Electric Guitar (clean)",
    "Electric Guitar (muted)",
    "Overdriven Guitar",
    "Distortion Guitar",
    "Guitar harmonics",
    "Acoustic Bass",
    "Electric Bass (finger)",
    "Electric Bass (pick)",
    "Fretless Bass",
    "Slap Bass 1",
    "Slap Bass 2",
    "Synth Bass 1",
    "Synth Bass 2",
    "Violin",
    "Viola",
    "Cello",
    "Contrabass",
    "Tremolo Strings",
    "Pizzicato Strings",
    "Orchestral Harp",
    "Timpani",
    "String Ensemble 1",
    "String Ensemble 2",
    "Synth Strings 1",
    "Synth Strings 2",
    "Choir Aahs",
    "Voice Oohs",
    "Synth Choir",
    "Orchestra Hit",
    "Trumpet",
    "Trombone",
    "Tuba",
    "Muted Trumpet",
    "French Horn",
    "Brass Section",
    "Synth Brass 1",
    "Synth Brass 2",
    "Soprano Sax",
    "Alto Sax",
    "Tenor Sax",
    "Baritone Sax",
    "Oboe",
    "English Horn",
    "Bassoon",
    "Clarinet",
    "Piccolo",
    "Flute",
    "Recorder",
    "Pan Flute",
    "Blown Bottle",
    "Shakuhachi",
    "Whistle",
    "Ocarina",
    "Lead 1 (square)",
    "Lead 2 (sawtooth)",
    "Lead 3 (calliope)",
    "Lead 4 (chiff)",
    "Lead 5 (charang)",
    "Lead 6 (voice)",
    "Lead 7 (fifths)",
    "Lead 8 (bass + lead)",
    "Pad 1 (new age)",
    "Pad 2 (warm)",
    "Pad 3 (polysynth)",
    "Pad 4 (choir)",
    "Pad 5 (bowed)",
    "Pad 6 (metallic)",
    "Pad 7 (halo)",
    "Pad 8 (sweep)",
    "FX 1 (rain)",
    "FX 2 (soundtrack)",
    "FX 3 (crystal)",
    "FX 4 (atmosphere)",
    "FX 5 (brightness)",
    "FX 6 (goblins)",
    "FX 7 (echoes)",
    "FX 8 (sci-fi)",
    "Sitar",
    "Banjo",
    "Shamisen",
    "Koto",
    "Kalimba",
    "Bag pipe",
    "Fiddle",
    "Shanai",
    "Tinkle Bell",
    "Agogo",
    "Steel Drums",
    "Woodblock",
    "Taiko Drum",
    "Melodic Tom",
    "Synth Drum",
    "Reverse Cymbal",
    "Guitar Fret Noise",
    "Breath Noise",
    "Seashore",
    "Bird Tweet",
    "Telephone Ring",
    "Helicopter",
    "Applause",
    "Gunshot",
]

_PERCUSSION_NAMES = {
    27: "High Q",  # GM2
    28: "Slap",  # GM2
    29: "Scratch Push",  # GM2
    30: "Scratch Pull",  # GM2
    31: "Sticks",  # GM2
    32: "Square Click",  # GM2
    33: "Metronome Click",  # GM2
    34: "Metronome Bell",  # GM2
    35: "Acoustic Bass Drum",
    36: "Bass Drum 1",
    37: "Side Stick",
    38: "Acoustic Snare",
    39: "Hand Clap",
    40: "Electric Snare",
    41: "Low Floor Tom",
    42: "Closed Hi Hat",
    43: "High Floor Tom",
    44: "Pedal Hi-Hat",
    45: "Low Tom",
    46: "Open Hi-Hat",
    47: "Low-Mid Tom",
    48: "Hi-Mid Tom",
    49: "Crash Cymbal 1",
    50: "High Tom",
    51: "Ride Cymbal 1",
    52: "Chinese Cymbal",
    53: "Ride Bell",
    54: "Tambourine",
    55: "Splash Cymbal",
    56: "Cowbell",
    57: "Crash Cymbal 2",
    58: "Vibraslap",
    59: "Ride Cymbal 2",
    60: "Hi Bongo",
    61: "Low Bongo",
    62: "Mute Hi Conga",
    63: "Open Hi Conga",
    64: "Low Conga",
    65: "High Timbale",
    66: "Low Timbale",
    67: "High Agogo",
    68: "Low Agogo",
    69: "Cabasa",
    70: "Maracas",
    71: "Short Whistle",
    72: "Long Whistle",
    73: "Short Guiro",
    74: "Long Guiro",
    75: "Claves",
    76: "Hi Wood Block",
    77: "Low Wood Block",
    78: "Mute Cuica",
    79: "Open Cuica",
    80: "Mute Triangle",
    81: "Open Triangle",
    82: "Shaker",  # GM2
    83: "Jingle Bell",  # GM2
    84: "Belltree",  # GM2
    85: "Castanets",  # GM2
    86: "Mute Surdo",  # GM2
    87: "Open Surdo",  # GM2
}

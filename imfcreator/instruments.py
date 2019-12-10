"""**Instrument Manager**

This loads and stores instruments that the conversion process uses.

Instruments are added using `add` and `add_file`.
They are retrieved using `get`.
Use `get_name` to get the instrument name
"""
import logging as _logging
import typing as _typing
import imfcreator.adlib as _adlib
import imfcreator.filetypes as _filetypes
import imfcreator.utils as _utils
# TODO Add GM2 drum instrument mapping flag and dictionary.

# Instrument types.
MELODIC = 0
PERCUSSION = 1
_TYPE_NAMES = {MELODIC: "MELODIC", PERCUSSION: "PERCUSSION"}

# The key is (inst_type, program, bank), value is the Adlib instrument.
_INSTRUMENTS = {}  # type: _typing.Dict[_typing.Tuple[int, int, int], _adlib.AdlibInstrument]

# List of searches that gave no results.
_WARNINGS = []


def add(inst_type: int, program: int, adlib_instrument: _adlib.AdlibInstrument, bank: int = 0):
    """Add an instrument to the instrument manager.

    :param inst_type: The instrument type.  MELODIC or PERCUSSION.
    :param program: The program or patch number.
    :param adlib_instrument: The Adlib instrument.
    :param bank: The instrument bank.
    :return: None
    """
    _validate_args(inst_type, program, bank)
    _INSTRUMENTS[(inst_type, program, bank)] = adlib_instrument


def add_file(f):
    """Adds all of the instruments in a file.

    :param f: A filename or file object.
    """
    for i in _open_file(f):
        add(*i)
    _logging.info(f"Loaded instruments: {count()}")


def count() -> int:
    """Returns the instrument count."""
    return len(_INSTRUMENTS)


def get(inst_type: int, program: int, bank: int = 0) -> _adlib.AdlibInstrument:
    """Returns the Adlib instrument based on the given type, program, and bank.

    :param inst_type: The instrument type.  MELODIC or PERCUSSION.
    :param program: The program or patch number.
    :param bank: The instrument bank.
    :return: An Adlib instrument if a match is found; otherwise None.
    """
    _validate_args(inst_type, program, bank)
    key = (inst_type, program, bank)
    instrument = _INSTRUMENTS.get(key)
    if instrument is None:
        if key not in _WARNINGS:
            _WARNINGS.append(key)
            _logging.warning(f"Could not find {_TYPE_NAMES[inst_type]} instrument: program {program}, bank {bank}")
    return instrument


def has(inst_type: int, program: int, bank: int = 0) -> bool:
    """Tests whether an Adlib instrument has been assigned based on the given type, program, and bank.

    :param inst_type: The instrument type.  MELODIC or PERCUSSION.
    :param program: The program or patch number.
    :param bank: The instrument bank.
    :return: A boolean.
    """
    _validate_args(inst_type, program, bank)
    key = (inst_type, program, bank)
    return key in _INSTRUMENTS


def get_name(inst_type: int, program: int) -> str:
    """Returns the instrument name as defined by the MIDI standard."""
    _validate_args(inst_type, program)
    if inst_type == MELODIC:
        return _MELODIC_NAMES[program]
    elif inst_type == PERCUSSION:
        if program in _PERCUSSION_NAMES:
            return _PERCUSSION_NAMES[program]
        return f"Unknown percussion {program}"


def _validate_args(inst_type: int, program: int, bank: int = 0):
    """Validates the entry argument values."""
    if inst_type not in [MELODIC, PERCUSSION]:
        raise ValueError("inst_type must be 0 (MELODIC) or 1 (PERCUSSION).")
    if program < 0 or program > 127:
        raise ValueError("program must be between 0 and 127 (inclusive).")
    if bank < 0 or bank > 65535:
        raise ValueError("bank must be between 0 and 65535 (inclusive).")


def _open_file(f):
    """Opens the given instrument file.

    :param f: A filename or file object.
    """
    if type(f) is str:  # filename
        filename = f
        fp = open(filename, "rb")
        exclusive_fp = True
    else:
        filename = ""
        fp = f
        exclusive_fp = False
    # Scan plugin classes for one that can open the file.
    preview = fp.read(32)
    for cls in _utils.get_all_subclasses(_filetypes.InstrumentFile):
        if cls.accept(preview):
            try:
                _logging.debug(f'Attempting to load "{filename}" using {cls.__name__}.')
                # Reset the file position for each attempt.
                fp.seek(0)
                instance = cls(fp, filename)
                # The instance now owns the fp.
                instance._exclusive_fp = exclusive_fp
                _logging.info(f'Loaded "{filename}" using {cls.__name__}.')
                return instance
            except (ValueError, IOError, OSError) as ex:
                _logging.warning(f'Error while attempting to load "{filename}" using {cls.__name__}: {ex}')
    if exclusive_fp:
        fp.close()
    raise ValueError(f"Failed to load instrument file: {filename}")


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
# import builtins
import __builtin__
builtins = __builtin__

IDS = []
PLUGINS = {}


def register_open(id, plugin, accept=None):
    """Registers a file type plugin used when opening instrument files."""
    id = id.upper()
    IDS.append(id)
    PLUGINS[id] = (plugin, accept)


def open(f):
    """Opens the given instrument file.

    :param f: A filename or file object.
    """
    filename = ""
    if type(f) is str:  # filename
        filename = f
        fp = builtins.open(filename, "rb")
        exclusive_fp = True
    else:
        fp = f
        exclusive_fp = False
    preview = fp.read(32)
    fp.seek(0)

    def open_with_plugin(fp, filename, preview):
        for id in IDS:
            cls, accept = PLUGINS[id]
            if accept is None or accept(preview):
                try:
                    return cls(fp, filename)
                except:
                    pass
        return None

    inst = open_with_plugin(fp, filename, preview)
    if inst:
        # The plugin now owns the fp.
        inst._exclusive_fp = exclusive_fp
        return inst
    if exclusive_fp:
        fp.close()
    raise IOError("Cannot identify instrument file {}".format(filename))


def get_all_instruments(f):
    """Returns all of the instruments in a file.

    :param f: A filename or file object.
    """
    return [i for i in open(f)]


class InstrumentFile(object):
    """The abstract class from which all instrument file plugins should inherit."""
    def __init__(self, fp = None, filename = None):
        """Initializes and opens the instrument file."""
        if fp is None:
            self.fp = builtins.open(filename, "rb")
            self._exclusive_fp = True
        else:
            self.fp = fp
            self._exclusive_fp = False
        self.filename = filename
        self.info = None
        self.instrument = None
        self._num_instruments = 1
        try:
            self._open()
        except (TypeError, IOError) as ex:
            self.close()
            raise SyntaxError(ex)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def _open(self):
        """Sets self.info to contain the information needed to load the first or only instrument in the file."""
        raise NotImplementedError("Subclass must override _open method.")

    def __iter__(self):
        if self.num_instruments == 1:
            yield self.load()
            return
        for index in range(self.num_instruments):
            self.seek(index)
            yield self.load()

    def close(self):
        """Closes the internal file object when it is owned by this instance."""
        try:
            if self._exclusive_fp and self.fp is not None:
                self._exclusive_fp = False
                self.fp.close()
                self.fp = None
        except Exception as ex:
            print("Error closing file: " + str(ex))

    def load(self):
        """Returns the instrument at the current position within the instrument file."""
        if self.info is None:
            raise IOError("Cannot load this instrument file.")
        if not self.info:
            return self.instrument
        self.instrument = self._load()
        return self.instrument

    def _load(self):
        """Loads the instrument from the plugin using the information from self.info."""
        raise NotImplementedError("Subclass must override _load method.")

    @property
    def num_instruments(self):
        """Returns the number of instruments in the file. Initializes and defaults to 1."""
        return self._num_instruments

    def seek(self, index):
        """Prepare self.info with the information needed to load the instrument at the given index."""
        raise NotImplementedError("Subclass must override seek method if it contains more than one instrument.")


class Instrument(object):
    """Represents an adlib instrument.

    Instruments can contain one or more voices, each consisting of a modulator and a carrier.
    This largely reflects the information stored per instrument in an OP2 file.
    """
    def __init__(self, name=None, num_voices=1):
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
        self.modulator = [Operator() for x in range(num_voices)]
        self.carrier = [Operator() for x in range(num_voices)]
        self.feedback = [0] * num_voices  # 8-bit
        self.note_offset = [0] * num_voices  # 16-bit, signed

    def __repr__(self):
        return str(self.__dict__ )

    def registers_match(self, other):
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


class Operator(object):  # MUST inherit from object for properties to work.
    """Represents an adlib operator's register values."""
    def __init__(self, tvskm=0, ksl_output=0, attack_decay=0, sustain_release=0, waveform_select=0):
        self.tvskm = 0  # tvskffff = tremolo, vibrato, sustain, ksr, frequency multiplier
        self.ksl_output = 0  # kkoooooo = key scale level, output level
        self.attack_decay = 0  # aaaadddd = attack rate, decay rate
        self.sustain_release = 0  # ssssrrrr = sustain level, release rate
        self.waveform_select = 0  # -----www = waveform select
        self.set_regs(tvskm, ksl_output, attack_decay, sustain_release, waveform_select)
        # Bit-level properties.
        Operator.tremolo = _create_bit_property("tvskm", 1, 7)
        Operator.vibrato = _create_bit_property("tvskm", 1, 6)
        Operator.sustain = _create_bit_property("tvskm", 1, 5)
        Operator.ksr = _create_bit_property("tvskm", 1, 4)
        Operator.freq_mult = _create_bit_property("tvskm", 4, 0)
        Operator.key_scale_level = _create_bit_property("ksl_output", 2, 6)
        Operator.output_level = _create_bit_property("ksl_output", 6, 0)
        Operator.attack_rate = _create_bit_property("attack_decay", 4, 4)
        Operator.decay_rate = _create_bit_property("attack_decay", 4, 0)
        Operator.sustain_level = _create_bit_property("sustain_release", 4, 4)
        Operator.release_rate = _create_bit_property("sustain_release", 4, 0)

    def set_regs(self, tvskm, ksl_output, attack_decay, sustain_release, waveform_select):
        """Sets all operator registers."""
        self.tvskm = tvskm
        self.ksl_output = ksl_output
        self.attack_decay = attack_decay
        self.sustain_release = sustain_release
        self.waveform_select = waveform_select

    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


def _create_bit_property(var_name, bits, shift):
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


def _check_range(value, max_value):
    """Checks a value to verify that it is between 0 and maxvalue, inclusive."""
    if value is None:
        raise ValueError("Value is required.")
    if 0 <= value <= max_value:
        return value
    else:
        raise ValueError("Value should be between 0 and {} inclusive. Got: {}.".format(max_value, value))

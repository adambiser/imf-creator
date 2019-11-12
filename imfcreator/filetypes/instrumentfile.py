# import builtins
import __builtin__

builtins = __builtin__

IDS = []
PLUGINS = {}


def register_open(plugin_id, plugin, accept=None):
    """Registers a file type plugin used when opening instrument files."""
    plugin_id = plugin_id.upper()
    IDS.append(plugin_id)
    PLUGINS[plugin_id] = (plugin, accept)


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
        for plugin_id in IDS:
            cls, accept = PLUGINS[plugin_id]
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
    q = open(f)
    dest = dict()
    dest['m'] = dict()
    dest['p'] = dict()
    for i in q:
        if i is None:
            continue
        k = 'p' if i.bank_is_percussion else 'm'
        b = (i.bank_msb * 256) + i.bank_lsb
        if b not in dest[k]:
            dest[k][b] = dict()
        dest[k][b][i.patch_id] = i

    return dest


class InstrumentFile(object):
    """The abstract class from which all instrument file plugins should inherit."""
    def __init__(self, fp=None, filename=None):
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

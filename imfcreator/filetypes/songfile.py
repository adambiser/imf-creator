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
    """Opens the given song file.

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
                except Exception as ex:
                    raise
        return None

    inst = open_with_plugin(fp, filename, preview)
    if inst:
        # The plugin now owns the fp.
        inst._exclusive_fp = exclusive_fp
        return inst
    if exclusive_fp:
        fp.close()
    raise IOError("Cannot identify song file {}".format(filename))


class SongFile(object):
    """The abstract class from which all song file plugins should inherit."""
    def __init__(self, fp=None, filename=None):
        """Initializes and opens the instrument file."""
        if fp is None:
            self.fp = builtins.open(filename, "rb")
            self._exclusive_fp = True
        else:
            self.fp = fp
            self._exclusive_fp = False
        self.filename = filename
        self.tracks = []
        # try:
        #     self._open()
        # except (TypeError, IOError) as ex:
        #     self.close()
        #     raise SyntaxError(ex)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def load(self):
        """Loads all song tracks and their events."""
        raise NotImplementedError("Subclass must override load method.")

    def load(self):
        """Loads all song tracks and their events."""
        raise NotImplementedError("Subclass must override load method.")

    def save(self, filename, **kwargs):
        """Saves the song to a file."""
        raise NotImplementedError("Subclass must override save method.")

    def close(self):
        """Closes the internal file object when it is owned by this instance."""
        try:
            if self._exclusive_fp and self.fp is not None:
                self._exclusive_fp = False
                self.fp.close()
                self.fp = None
        except Exception as ex:
            print("Error closing file: " + str(ex))

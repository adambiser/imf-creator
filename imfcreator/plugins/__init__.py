import importlib as _importlib
import logging as _logging
import os as _os
import imfcreator.utils as _utils
from imfcreator.adlib import AdlibInstrument as _AdlibInstrument
from imfcreator.midi import SongEvent as _SongEvent

# key is the plugin type class.
_PLUGINS = {}


def plugin(cls):
    """Plugin decorator.  Registers a class as a plugin."""
    _logging.debug(f"Registering plugin: {cls.__name__}")
    for plugin_type in _PLUGINS.keys():
        if issubclass(cls, plugin_type):
            _PLUGINS[plugin_type].append(cls)
            return cls
    raise ValueError(f"Unrecognized plugin type.  Valid types: {_PLUGINS.keys()}")


def _plugin_type(cls):
    """Plugin type decorator.  Registers a class as a plugin type."""
    _logging.debug(f"Registering plugin type: {cls.__name__}")
    _PLUGINS[cls] = []
    return cls


def _get_plugins(cls):
    """Gets the plugins for the given plugin type class."""
    return _PLUGINS[cls]


class _FileReaderPlugin(object):
    """The base class from which all file reader plugin classes should inherit."""

    def __init__(self, fp=None, filename=None):
        """Initializes and opens the plugin file."""
        if fp is None:
            self.fp = open(filename, "rb")
            self._exclusive_fp = True
        else:
            self.fp = fp
            self._exclusive_fp = False
        self.filename = filename
        try:
            self._open()
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        self.close()

    def close(self):
        """Closes the internal file object when it is owned by this instance."""
        try:
            if self._exclusive_fp and self.fp is not None:
                self._exclusive_fp = False
                self.fp.close()
                self.fp = None
        except AttributeError:
            pass

    @classmethod
    def accept(cls, preview: bytes) -> bool:
        """Checks the preview bytes to see whether this class might be able to read the given file.

        :param preview: 32 preview bytes
        :return: True if the class might be able to open the file; otherwise, False.
        """
        raise NotImplementedError()

    def _open(self):
        """Reads any header information and verifies that the given file is indeed one that this class can read.

        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()

    @classmethod
    def open_file(cls, f):
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
        for subclass in _get_plugins(cls):
            _logging.debug(f'Testing accept for "{filename}" using {subclass.__name__}.')
            if subclass.accept(preview):
                try:
                    _logging.debug(f'Attempting to load "{filename}" using {subclass.__name__}.')
                    # Reset the file position for each attempt.
                    fp.seek(0)
                    instance = subclass(fp, filename)
                    # The instance now owns the fp.
                    instance._exclusive_fp = exclusive_fp
                    _logging.info(f'Loaded "{filename}" using {subclass.__name__}.')
                    return instance
                except (ValueError, IOError, OSError) as ex:
                    _logging.warning(f'Error while attempting to load "{filename}" using {cls.__name__}: {ex}')
        if exclusive_fp:
            fp.close()
        raise ValueError(f'Failed to load "{filename}" as {cls.__name__}.')


@_plugin_type
class InstrumentFileReader(_FileReaderPlugin):
    """The base class from which all instrument file plugins should inherit."""

    def __iter__(self) -> (int, int, _AdlibInstrument, int):
        for index in range(self.instrument_count):
            yield self.get_instrument(index)

    @classmethod
    def accept(cls, preview: bytes) -> bool:
        """Checks the preview bytes to see whether this class might be able to read the given file.

        :param preview: 32 preview bytes
        :return: True if the class might be able to open the file; otherwise, False.
        """
        raise NotImplementedError()

    def _open(self):
        """Reads any header information and verifies that the given file is indeed one that this class can read.

        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()

    @property
    def instrument_count(self) -> int:
        """Returns the number of instruments in the file.

        :return: An integer greater than 0.
        """
        raise NotImplementedError()

    def get_instrument(self, index: int) -> (int, int, _AdlibInstrument, int):
        """Returns the instrument for the given index.
        Implementations must be able to retrieve instruments in an arbitrary order, not just file order.

        :param index: The index of the instrument to return.
        :return: An Adlib instrument.
        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()


@_plugin_type
class SongFileReader(_FileReaderPlugin):
    """The base class from which all song reader plugins should inherit."""

    def __iter__(self) -> _SongEvent:
        for index in range(self.event_count):
            yield self.get_event(index)

    @classmethod
    def accept(cls, preview: bytes) -> bool:
        """Checks the preview bytes to see whether this class might be able to read the given file.

        :param preview: 32 preview bytes
        :return: True if the class might be able to open the file; otherwise, False.
        """
        raise NotImplementedError()

    def _open(self):
        """Reads any header information and verifies that the given file is indeed one that this class can read.
        If necessary, this can also read the song events.

        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()

    @property
    def event_count(self) -> int:
        """Returns the number of events in the file.

        :return: An integer greater than 0.
        """
        raise NotImplementedError()

    def get_event(self, index: int) -> _SongEvent:
        """Returns the song event for the given index.
        Implementations must be able to retrieve events in an arbitrary order, not just file order.

        :param index: The index of the event to return.
        :return: A list of song events.
        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()


def _load_plugins():
    """Initializes plugins."""
    global _PLUGINS
    for key in _PLUGINS.keys():
        _PLUGINS[key] = []
    # Load plugins.
    dirname = _os.path.dirname(__file__)
    plugins = [f[0:-3] for f
               in _os.listdir(dirname)
               if _os.path.isfile(_os.path.join(dirname, f)) and f.lower().endswith("fileplugin.py")]
    for p in plugins:
        try:
            _importlib.import_module(f"{__name__}.{p}")
        except ImportError as e:
            print(f"plugin: failed to import {p}: {e}")


_load_plugins()

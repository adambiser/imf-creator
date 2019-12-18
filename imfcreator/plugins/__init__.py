import importlib as _importlib
import logging as _logging
import os as _os
import typing as _typing
from collections import namedtuple as _namedtuple
from imfcreator.adlib import AdlibInstrument as _AdlibInstrument
from imfcreator.midi import SongEvent as _SongEvent

_PLUGIN_TYPES = []  # List of plugin type classes.
FileTypeInfo = _namedtuple("FileTypeInfo", ["description", "default_extension"])


def _plugin_type(cls):
    """Plugin type decorator.  Registers a class as a plugin type.

    This adds a _PLUGINS list to the class definition.   As plugins are registered, they are added to this list.
    """
    _logging.debug(f"Registering plugin type: {cls.__name__}")
    cls._PLUGINS = []
    _PLUGIN_TYPES.append(cls)
    return cls


def plugin(cls):
    """Plugin decorator.  Registers a class as a plugin."""
    _logging.debug(f"Registering plugin: {cls.__name__}")
    plugin_type = next((c for c in _PLUGIN_TYPES if issubclass(cls, c)), None)
    if plugin_type:
        # noinspection PyProtectedMember
        plugin_type._PLUGINS.append(cls)
        register_plugin = getattr(cls, "_register_plugin", None)
        if callable(register_plugin):
            register_plugin()
        return cls
    raise ValueError(f"Unrecognized plugin type.  Valid types: {_PLUGIN_TYPES}")


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
        # noinspection PyUnresolvedReferences
        for subclass in cls._PLUGINS:
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
                    _logging.error(f'Error while loading "{filename}" using {subclass.__name__}: {ex}')
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


@_plugin_type
class AdlibSong(object):
    """The base class from which all song converter plugin classes should inherit.

    Interacts with the song player.
    """
    _FILE_TYPES = {}  # type: _typing.Dict[str, str]

    @classmethod
    def _get_filetypes(cls) -> _typing.Dict[str, str]:
        """A dictionary keyed by file type with the descriptions as the value.
        File types should be unique among ALL writer plugins.
        """
        raise NotImplementedError()

    @classmethod
    def _get_settings(cls) -> _typing.Dict[str, str]:
        """A dictionary keyed by setting name with the description as the value."""
        raise NotImplementedError()

    @classmethod
    def accept(cls, preview: bytes, filename: str) -> bool:
        """Checks the preview bytes to see whether this class might be able to open the given file.

        :param preview: 32 preview bytes
        :param filename: The filename to be opened.
        :return: True if the class might be able to open the file; otherwise, False.
        """
        raise NotImplementedError()

    @classmethod
    def _open_file(cls, fp, filename) -> "AdlibSong":
        """Loads a song from the given file object.

        :param fp: A file object opened with "rb" mode.
        :param filename: The filename.
        """
        raise NotImplementedError()

    def _save_file(self, fp, filename):
        """Saves the song data to the given file object.

        :param fp: A file object opened with "wb" mode.
        :param filename: The filename.
        """
        raise NotImplementedError()

    @classmethod
    def _convert_from(cls, events: _typing.Iterable[_SongEvent], filetype: str, settings: _typing.Dict) -> "AdlibSong":
        """Converts song events to bytes data for the given file type.

        :param events: The events to be converted.
        :param filetype: The file type to convert the events to.
        :param settings: Any additional settings for the conversion.
        :exception ValueError: When the given data is not valid.
        :return: A bytes object containing the converted song data.
        """
        raise NotImplementedError()

    @classmethod
    def open_file(cls, filename) -> "AdlibSong":
        """Loads a song from the given file object.

        Implementing classes must override `_open_file`.
        """
        with open(filename, "rb") as fp:
            preview = fp.read(32)
            # noinspection PyProtectedMember
            for subclass in AdlibSong._PLUGINS:  # type: AdlibSong
                _logging.debug(f'Testing accept for "{filename}" using {subclass.__name__}.')
                if subclass.accept(preview, filename):
                    try:
                        _logging.debug(f'Attempting to load "{filename}" using {subclass.__name__}.')
                        # Reset the file position for each attempt.
                        fp.seek(0)
                        song = subclass._open_file(fp, filename)
                        # The instance now owns the fp.
                        _logging.info(f'Loaded "{filename}" using {subclass.__name__}.')
                        return song
                    except (ValueError, IOError, OSError) as ex:
                        _logging.error(f'Error while loading "{filename}" using {subclass.__name__}: {ex}')
        raise ValueError(f'Could not determine file type for "{filename}".')

    def save_file(self, filename):
        """Saves the file data to the given file object."""
        with open(filename, "wb") as fp:
            self._save_file(fp, filename)

    @classmethod
    def convert_from(cls, events: _typing.Iterable[_SongEvent], filetype: str, settings: _typing.Dict) -> "AdlibSong":
        """Converts song events to bytes data for the given file type.

        Implementing classes muse override `_convert_from`.

        :param events: The events to be converted.
        :param filetype: The file type to convert the events to.
        :param settings: Any additional settings for the conversion.
        :exception ValueError: When the given data is not valid.
        :return: A bytes object containing the converted song data.
        """
        return AdlibSong.get_filetype_class(filetype)._convert_from(events, filetype, settings)

    @classmethod
    def get_filetype_class(cls, filetype: str) -> "AdlibSong":
        _logging.debug(f"Finding AdlibSong class for {filetype}.")
        # noinspection PyProtectedMember
        song_class = next((p for p in AdlibSong._PLUGINS if filetype in p._get_filetypes()), None)
        if not song_class:
            raise ValueError("Could not find a song converter for the given file type.")
        _logging.debug(f"Found AdlibSong class for {filetype}: {song_class.__name__}")
        return song_class

    @classmethod
    def _register_plugin(cls):
        """Extra plugin registration code.  Registers the class's filetypes"""
        def validate_name(n):
            invalid_chars = [c for c in n if not c.isalnum()]
            if invalid_chars:
                raise ValueError(f"Text must be alphanumeric only.  Invalid characters: {invalid_chars}")

        # Process _filetypes
        for filetype, desc in cls._get_filetypes().items():
            # filetypes can only be alphanumeric.
            validate_name(filetype)
            # filetypes must be unique across all plugins
            if filetype in AdlibSong._FILE_TYPES:
                raise ValueError(f"A plugin for filetype {filetype} already exists.  "
                                 f"Existing: {AdlibSong._FILE_TYPES[filetype].__name__}, "
                                 f"Current: {cls.__name__}")
            _logging.debug(f"Registering filetype: {filetype} -> {cls.__name__}")
            AdlibSong._FILE_TYPES[filetype] = desc
        # Validate setting names.
        for name in cls._get_settings().keys():
            validate_name(name)


def _load_plugins():
    """Initializes plugins."""
    for p in _PLUGIN_TYPES:
        p._PLUGINS = []
    # Load plugins.
    dirname = _os.path.dirname(__file__)
    plugins = [f[0:-3] for f
               in _os.listdir(dirname)
               if _os.path.isfile(_os.path.join(dirname, f)) and f.lower().endswith("fileplugin.py")]
    for p in plugins:
        # try:
        _importlib.import_module(f"{__name__}.{p}")
        # except ImportError as e:
        # _logging.error(f"plugin: failed to import {p}: {e}")
        # raise


_load_plugins()

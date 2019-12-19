import importlib as _importlib
import logging as _logging
import os as _os
import typing as _typing
from collections import namedtuple as _namedtuple
from imfcreator.adlib import AdlibInstrument as _AdlibInstrument
from imfcreator.midi import SongEvent as _SongEvent

_PLUGIN_TYPES = []  # List of plugin type classes.
FileTypeInfo = _namedtuple("FileTypeInfo", ["description", "default_extension"])
InstrumentId = _namedtuple("InstrumentId", ["instrument_type", "bank", "program"])


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


@_plugin_type
class InstrumentFile:
    """The base class for instrument file types."""

    def __init__(self, fp, file: str):
        self.instruments = {}  # type: _typing.Dict[InstrumentId, _AdlibInstrument]
        self.file = file
        try:
            self.fp = fp
            self._load_file()
        finally:
            del self.fp

    # def __iter__(self):
    #     for instrument in self.instruments:
    #         yield instrument

    @classmethod
    def accept(cls, preview: bytes, path: str) -> bool:
        """Checks the preview bytes and/or filename to see whether this class might be able to open the given file.

        :param preview: 32 preview bytes read from the beginning of the file.
        :param path: The path to the file to be opened.
        :return: True if the class might be able to open the file; otherwise, False.
        """
        raise NotImplementedError()

    def _load_file(self):
        """Loads file data from self.fp.  Note that self.fp only exists while this method is being called."""
        raise NotImplementedError()

    @classmethod
    def load_file(cls, file: str) -> "InstrumentFile":
        """Checks plugin classes for one that can load the given file.  If one is found, the file is loaded."""
        with open(file, "rb") as fp:
            # Scan plugin classes for one that can open the file.
            preview = fp.read(32)
            for subclass in cls._PLUGINS:  # type: _typing.Type[InstrumentFile]
                _logging.debug(f'Testing accept for "{file}" using {subclass.__name__}.')
                if subclass.accept(preview, file):
                    try:
                        _logging.debug(f'Attempting to load "{file}" using {subclass.__name__}.')
                        # Reset the file position for each attempt.
                        fp.seek(0)
                        instance = subclass(fp, file)
                        _logging.info(f'Loaded "{file}" using {subclass.__name__}.')
                        return instance
                    except (ValueError, IOError, OSError) as ex:
                        _logging.error(f'Error while loading "{file}" using {subclass.__name__}: {ex}')
        raise ValueError(f'Failed to load "{file}" as {cls.__name__}.')


@_plugin_type
class MidiSongFile:
    """The base class for 'input' song file types.

    Implementing classes should populate `self.events` during `_load_file`.
    """

    def __init__(self, fp, file: str):
        self.events = []  # type: _typing.List[_SongEvent]
        self.instruments = {}  # type: _typing.Dict[int, _AdlibInstrument]
        self.title = None  # type: _typing.Optional[str]
        self.composer = None  # type: _typing.Optional[str]
        self.remarks = None  # type: _typing.Optional[str]
        self.file = file
        self.tics_per_second = 0
        try:
            self.fp = fp
            self._load_file()
            self.sort()
        finally:
            del self.fp

    # def __iter__(self):
    #     for song_event in self.events:
    #         yield song_event

    @classmethod
    def accept(cls, preview: bytes, path: str) -> bool:
        """Checks the preview bytes and/or filename to see whether this class might be able to open the given file.

        :param preview: 32 preview bytes read from the beginning of the file.
        :param path: The path to the file to be opened.
        :return: True if the class might be able to open the file; otherwise, False.
        """
        raise NotImplementedError()

    def _load_file(self):
        """Loads file data from self.fp.  Note that self.fp only exists for the duration of _load_file."""
        raise NotImplementedError()

    def sort(self):
        """Sorts the song events into chronological order."""
        self.events = sorted([_ for _ in self.events])

    @classmethod
    def load_file(cls, file: str) -> "MidiSongFile":
        """Checks plugin classes for one that can load the given file.  If one is found, the file is loaded."""
        with open(file, "rb") as fp:
            # Scan plugin classes for one that can open the file.
            preview = fp.read(32)
            for subclass in cls._PLUGINS:  # type: _typing.Type[MidiSongFile]
                _logging.debug(f'Testing accept for "{file}" using {subclass.__name__}.')
                if subclass.accept(preview, file):
                    try:
                        _logging.debug(f'Attempting to load "{file}" using {subclass.__name__}.')
                        # Reset the file position for each attempt.
                        fp.seek(0)
                        instance = subclass(fp, file)
                        _logging.info(f'Loaded "{file}" using {subclass.__name__}.')
                        return instance
                    except (ValueError, IOError, OSError) as ex:
                        _logging.error(f'Error while loading "{file}" using {subclass.__name__}: {ex}')
        raise ValueError(f'Failed to load "{file}" as {cls.__name__}.')


@_plugin_type
class AdlibSongFile:
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

    # @classmethod
    # def _open_file(cls, fp, filename) -> "AdlibSongFile":
    #     """Loads a song from the given file object.
    #
    #     :param fp: A file object opened with "rb" mode.
    #     :param filename: The filename.
    #     """
    #     raise NotImplementedError()

    def _save_file(self, fp, filename):
        """Saves the song data to the given file object.

        :param fp: A file object opened with "wb" mode.
        :param filename: The filename.
        """
        raise NotImplementedError()

    @classmethod
    def _convert_from(cls, events: _typing.Iterable[_SongEvent], filetype: str,
                      settings: _typing.Dict) -> "AdlibSongFile":
        """Converts song events to bytes data for the given file type.

        :param events: The events to be converted.
        :param filetype: The file type to convert the events to.
        :param settings: Any additional settings for the conversion.
        :exception ValueError: When the given data is not valid.
        :return: A bytes object containing the converted song data.
        """
        raise NotImplementedError()

    # @classmethod
    # def open_file(cls, filename) -> "AdlibSongFile":
    #     """Loads a song from the given file object.
    #
    #     Implementing classes must override `_open_file`.
    #     """
    #     with open(filename, "rb") as fp:
    #         preview = fp.read(32)
    #         for subclass in cls._PLUGINS:  # type: _typing.Type[AdlibSongFile]
    #             _logging.debug(f'Testing accept for "{filename}" using {subclass.__name__}.')
    #             if subclass.accept(preview, filename):
    #                 try:
    #                     _logging.debug(f'Attempting to load "{filename}" using {subclass.__name__}.')
    #                     # Reset the file position for each attempt.
    #                     fp.seek(0)
    #                     song = subclass._open_file(fp, filename)
    #                     # The instance now owns the fp.
    #                     _logging.info(f'Loaded "{filename}" using {subclass.__name__}.')
    #                     return song
    #                 except (ValueError, IOError, OSError) as ex:
    #                     _logging.error(f'Error while loading "{filename}" using {subclass.__name__}: {ex}')
    #     raise ValueError(f'Could not determine file type for "{filename}".')

    def save_file(self, filename):
        """Saves the file data to the given file object."""
        with open(filename, "wb") as fp:
            self._save_file(fp, filename)

    @classmethod
    def convert_from(cls, events: _typing.Iterable[_SongEvent], filetype: str,
                     settings: _typing.Dict) -> "AdlibSongFile":
        """Converts song events to bytes data for the given file type.

        Implementing classes muse override `_convert_from`.

        :param events: The events to be converted.
        :param filetype: The file type to convert the events to.
        :param settings: Any additional settings for the conversion.
        :exception ValueError: When the given data is not valid.
        :return: A bytes object containing the converted song data.
        """
        return cls.get_filetype_class(filetype)._convert_from(events, filetype, settings)

    @classmethod
    def get_filetype_class(cls, filetype: str) -> "AdlibSongFile":
        _logging.debug(f"Finding AdlibSong class for {filetype}.")
        # noinspection PyProtectedMember
        song_class = next((p for p in cls._PLUGINS if filetype in p._get_filetypes()), None)
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
            if filetype in cls._FILE_TYPES:
                raise ValueError(f"A plugin for filetype {filetype} already exists.  "
                                 f"Existing: {cls._FILE_TYPES[filetype].__name__}, "
                                 f"Current: {cls.__name__}")
            _logging.debug(f"Registering filetype: {filetype} -> {cls.__name__}")
            cls._FILE_TYPES[filetype] = desc
        # Validate setting names.
        for name in cls._get_settings().keys():
            validate_name(name)


def _load_plugins():
    """Initializes plugins."""
    for p in _PLUGIN_TYPES:
        p._PLUGINS = []
    # Load plugins.
    dirname = _os.path.dirname(__file__)
    plugins = [f[0:-3] for f in _os.listdir(dirname)
               if _os.path.isfile(_os.path.join(dirname, f)) and f.lower().endswith("fileplugin.py")]
    for p in plugins:
        _importlib.import_module(f"{__name__}.{p}")


_load_plugins()

import importlib as _importlib
import logging as _logging
import os as _os
import typing as _typing
import imfcreator.midi as _midi  # import SongEvent as _SongEvent
from imfcreator.adlib import AdlibInstrument as _AdlibInstrument


_PLUGIN_TYPES = []  # List of plugin type classes.


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
        # register_plugin = getattr(cls, "_register_plugin", None)
        # if callable(register_plugin):
        #     register_plugin()

        def validate_name(n):
            invalid_chars = [c for c in n if not c.isalnum()]
            if invalid_chars:
                raise ValueError(f"Text must be alphanumeric only.  Invalid characters: {invalid_chars}")

        # Process _filetypes
        for filetype in cls._get_filetypes():
            # filetypes can only be alphanumeric.
            validate_name(filetype.name)
            # filetypes must be unique across all plugins
            # noinspection PyProtectedMember
            current_filetype_class = next((c.cls for c in plugin_type._FILETYPES if c.info.name == filetype), None)
            if current_filetype_class:
                raise ValueError(f"A plugin for filetype {filetype.name} already exists.  "
                                 f"Existing: {current_filetype_class.__name__}, "
                                 f"Current: {cls.__name__}")
            _logging.debug(f"Registering filetype: {filetype.name} -> {cls.__name__}")
            # noinspection PyProtectedMember
            plugin_type._FILETYPES.append(_FileTypeEntry(cls, filetype))
            if getattr(cls, "_get_filetype_settings", None):
                settings = cls._get_filetype_settings(filetype.name)
                if settings:
                    # Validate setting names.
                    for setting in settings:
                        validate_name(setting.name)
        return cls
    raise ValueError(f"Unrecognized plugin type.  Valid types: {_PLUGIN_TYPES}")


class InstrumentId(_typing.NamedTuple):
    """Represents an instrument ID.

    **arguments**: instrument_type, bank, program
    """
    instrument_type: int
    bank: int
    program: int


class FileTypeInfo(_typing.NamedTuple):
    """Represents a file type that music can be converted to.
    Each file type's `name` must be unique.

    **arguments**: name, description, default_extension
    """
    name: str
    description: str
    # TODO Multiple extensions, ie : *.mid, *.smf, ^.midi
    default_extension: str


class FileTypeSetting(_typing.NamedTuple):
    """Represents a user-modifiable setting for a file type.

    **arguments**: name, description, [kwargs]

    `kwargs` are the keyword arguments passed into `argparser`.
    """
    name: str
    description: str
    kwargs: _typing.Dict[str, _typing.Any] = {}


@_plugin_type
class InstrumentFile:
    """The base class for instrument file types."""

    _FILETYPES = []  # type: _typing.List[_FileTypeEntry]

    def __init__(self, fp, file: str):
        self.instruments = {}  # type: _typing.Dict[InstrumentId, _AdlibInstrument]
        self.file = file
        try:
            self.fp = fp
            self._load_file()
        finally:
            del self.fp

    @classmethod
    def _get_filetypes(cls) -> _typing.List[FileTypeInfo]:
        """Returns a list of file types the class can read."""
        raise NotImplementedError()

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
    def load_file(cls, f) -> "InstrumentFile":
        """Checks plugin classes for one that can load the given file.  If one is found, the file is loaded."""

        if type(f) is str:
            filename = f
            fp = open(filename, "rb")
            exclusive_fp = True
        else:
            fp = f  # type: _typing.IO
            filename = fp.name
            exclusive_fp = False
        try:
            # Scan plugin classes for one that can open the file.
            _logging.info(f'Loading "{filename}".')
            preview = fp.read(32)
            for subclass in cls._PLUGINS:  # type: _typing.Type[InstrumentFile]
                # _logging.debug(f'Testing accept for "{filename}" using {subclass.__name__}.')
                if subclass.accept(preview, filename):
                    try:
                        # _logging.debug(f'Attempting to load "{filename}" using {subclass.__name__}.')
                        # Reset the file position for each attempt.
                        fp.seek(0)
                        instance = subclass(fp, filename)
                        _logging.info(f'Loaded "{filename}" using {subclass.__name__}.')
                        return instance
                    except (ValueError, IOError, OSError) as ex:
                        _logging.error(f'Error while loading "{filename}" using {subclass.__name__}: {ex}')
        finally:
            if exclusive_fp:
                fp.close()
        raise ValueError(f'Failed to load "{filename}" as {cls.__name__}.')

    @classmethod
    def get_filetypes(cls) -> _typing.List["FileTypeInfo"]:
        return [c.info for c in cls._FILETYPES]


@_plugin_type
class MidiSongFile:
    """The base class for 'input' song file types.

    Implementing classes should populate `self.events` during `_load_file`.
    """

    _FILETYPES = []  # type: _typing.List[_FileTypeEntry]
    PERCUSSION_CHANNEL = 9
    DEFAULT_PITCH_BEND_SCALE = 2.0

    def __init__(self, fp: _typing.IO, file: str):
        self.events = []  # type: _typing.List[_midi.SongEvent]
        self.instruments = {}  # type: _typing.Dict[InstrumentId, _AdlibInstrument]
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

    @classmethod
    def _get_filetypes(cls) -> _typing.List[FileTypeInfo]:
        """Returns a list of file types the class can read."""
        raise NotImplementedError()

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
        """Sorts the song events into chronological order.  Also reassigns event indices."""
        self.events = sorted([_ for _ in self.events])  # type: _typing.List[_midi.SongEvent]
        for index in range(len(self.events)):
            self.events[index].index = index

    @classmethod
    def load_file(cls, filename: str) -> "MidiSongFile":
        """Checks plugin classes for one that can load the given file.  If one is found, the file is loaded."""
        with open(filename, "rb") as fp:
            # Scan plugin classes for one that can open the file.
            preview = fp.read(32)
            _logging.info(f'Loading "{filename}".')
            for subclass in cls._PLUGINS:  # type: _typing.Type[MidiSongFile]
                # _logging.debug(f'Testing accept for "{filename}" using {subclass.__name__}.')
                if subclass.accept(preview, filename):
                    try:
                        # _logging.debug(f'Attempting to load "{filename}" using {subclass.__name__}.')
                        # Reset the file position for each attempt.
                        fp.seek(0)
                        instance = subclass(fp, filename)
                        _logging.info(f'Loaded "{filename}" using {subclass.__name__}.')
                        return instance
                    except (ValueError, IOError, OSError) as ex:
                        _logging.error(f'Error while loading "{filename}" using {subclass.__name__}: {ex}')
        raise ValueError(f'Failed to load "{filename}" as {cls.__name__}.')

    @classmethod
    def get_filetypes(cls) -> _typing.List["FileTypeInfo"]:
        return [c.info for c in cls._FILETYPES]


class _FileTypeEntry(_typing.NamedTuple):
    cls: _typing.Type["AdlibSongFile"]
    info: FileTypeInfo


@_plugin_type
class AdlibSongFile:
    """The base class from which all song converter plugin classes should inherit.

    Interacts with the song player.
    """

    _FILETYPES = []  # type: _typing.List[_FileTypeEntry]

    def __init__(self, midi_song: MidiSongFile, filetype: str):
        self._default_outfile = _os.path.splitext(midi_song.file)[0]
        self._filetype = filetype

    @classmethod
    def _get_filetypes(cls) -> _typing.List["FileTypeInfo"]:
        """A list of FileTypeInfo instances representing valid filetypes for the class.
        File type names must be unique among ALL AdlibSongFile plugins.
        """
        raise NotImplementedError()

    @classmethod
    def _get_filetype_settings(cls, filetype) -> _typing.Optional[_typing.List["FileTypeSetting"]]:
        """A list of FileTypeSettings for the given filetype name."""
        raise NotImplementedError()

    # @classmethod
    # def accept(cls, preview: bytes, filename: str) -> bool:
    #     """Checks the preview bytes to see whether this class might be able to open the given file.
    #
    #     :param preview: 32 preview bytes
    #     :param filename: The filename to be opened.
    #     :return: True if the class might be able to open the file; otherwise, False.
    #     """
    #     raise NotImplementedError()

    def _save_file(self, fp, filename):
        """Saves the song data to the given file object.

        :param fp: A file object opened with "wb" mode.
        :param filename: The filename.
        """
        raise NotImplementedError()

    @classmethod
    def _convert_from(cls, midi_song: MidiSongFile, filetype: str, settings: _typing.Dict) -> "AdlibSongFile":
        """Converts a MIDI song to bytes data for the given file type.

        :param midi_song: The MIDI song to convert from.
        :param filetype: The file type to convert the events to.
        :param settings: Any additional settings for the conversion.
        :exception ValueError: When the given data is not valid.
        :return: A bytes object containing the converted song data.
        """
        raise NotImplementedError()

    def save_file(self, filename: str = None):
        """Saves the file data to the given file object."""
        if not filename:
            filename = self._default_outfile
        filename, ext = _os.path.splitext(filename)
        if not ext:
            ext = AdlibSongFile.get_default_extension(self._filetype)
        filename = f"{filename}{ext}"
        with open(filename, "wb") as fp:
            self._save_file(fp, filename)
            _logging.info(f'Converted music saved as "{filename}".')

    @classmethod
    def convert_from(cls, midi_song: MidiSongFile, filetype: str,
                     settings: _typing.Dict = None) -> "AdlibSongFile":
        """Converts a MIDI song to bytes data for the given file type.

        Implementing classes muse override `_convert_from`.

        :param midi_song: The MIDI song to convert from.
        :param filetype: The file type to convert the events to.
        :param settings: Any additional settings for the conversion.
        :exception ValueError: When the given data is not valid.
        :return: A bytes object containing the converted song data.
        """
        settings = settings or {}
        filetype_class = cls.get_filetype_class(filetype)
        valid_settings = [s.name for s in filetype_class._get_filetype_settings(filetype) or []]
        for setting in settings:
            if setting not in valid_settings:
                raise ValueError(f"Unexpected setting: {setting}.  Valid settings are: {', '.join(valid_settings)}")
        # Validate settings.
        return filetype_class._convert_from(midi_song, filetype, settings)

    @classmethod
    def get_filetypes(cls) -> _typing.List["FileTypeInfo"]:
        return [c.info for c in cls._FILETYPES]

    @classmethod
    def _get_filetype_entry(cls, filetype) -> _typing.Optional[_typing.Type[_FileTypeEntry]]:
        return next((entry for entry in cls._FILETYPES if entry.info.name == filetype), None)

    @classmethod
    def get_filetype_class(cls, filetype: str) -> _typing.Type["AdlibSongFile"]:
        # _logging.debug(f"Finding AdlibSong class for {filetype}.")
        entry = cls._get_filetype_entry(filetype)
        if not entry:
            raise ValueError(f"Could not find a song converter for the given file type: {filetype}")
        # _logging.debug(f"Found AdlibSong class for {filetype}: {entry.cls.__name__}")
        return entry.cls

    @classmethod
    def get_filetype_settings(cls, filetype) -> _typing.List["FileTypeSetting"]:
        return cls._get_filetype_entry(filetype).cls._get_filetype_settings(filetype) or []

    @classmethod
    def get_default_extension(cls, filetype: str) -> _typing.Optional[str]:
        entry = cls._get_filetype_entry(filetype)
        ext = entry.info.default_extension
        return ext if ext.startswith(".") else f".{ext}"

    # @classmethod
    # def _register_plugin(cls):
    #     """Extra plugin registration code.  Registers the class's filetypes"""
    #     def validate_name(n):
    #         invalid_chars = [c for c in n if not c.isalnum()]
    #         if invalid_chars:
    #             raise ValueError(f"Text must be alphanumeric only.  Invalid characters: {invalid_chars}")
    #
    #     # Process _filetypes
    #     for filetype in cls._get_filetypes():
    #         # filetypes can only be alphanumeric.
    #         validate_name(filetype.name)
    #         # filetypes must be unique across all plugins
    #         current_filetype_class = next((c.cls for c in cls._FILETYPES if c.info.name == filetype), None)
    #         if current_filetype_class:
    #             raise ValueError(f"A plugin for filetype {filetype.name} already exists.  "
    #                              f"Existing: {current_filetype_class.__name__}, "
    #                              f"Current: {cls.__name__}")
    #         _logging.debug(f"Registering filetype: {filetype.name} -> {cls.__name__}")
    #         cls._FILETYPES.append(_FileTypeEntry(cls, filetype))
    #         settings = cls._get_filetype_settings(filetype.name)
    #         if settings:
    #             # Validate setting names.
    #             for setting in settings:
    #                 validate_name(setting.name)


def plugins_init():
    """Initializes plugins."""
    for p in _PLUGIN_TYPES:
        p._PLUGINS = []
    # Load plugins.
    dirname = _os.path.dirname(__file__)
    plugins = [f[0:-3] for f in _os.listdir(dirname)
               if _os.path.isfile(_os.path.join(dirname, f)) and f.lower().endswith("fileplugin.py")]
    for p in plugins:
        _importlib.import_module(f"{__name__}.{p}")


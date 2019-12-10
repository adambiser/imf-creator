import logging as _logging
import imfcreator.utils as _utils
from imfcreator.adlib import AdlibInstrument
from imfcreator.midi import SongEvent


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


class InstrumentFile(_FileReaderPlugin):
    """The base class from which all instrument file plugins should inherit."""

    def __iter__(self) -> (int, int, AdlibInstrument, int):
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

    def get_instrument(self, index: int) -> (int, int, AdlibInstrument, int):
        """Returns the instrument for the given index.
        Implementations must be able to retrieve instruments in an arbitrary order, not just file order.

        :param index: The index of the instrument to return.
        :return: An Adlib instrument.
        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()


class SongReader(_FileReaderPlugin):
    """The base class from which all song reader plugins should inherit."""

    def __iter__(self) -> SongEvent:
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

    def get_event(self, index: int) -> SongEvent:
        """Returns the song event for the given index.
        Implementations must be able to retrieve events in an arbitrary order, not just file order.

        :param index: The index of the event to return.
        :return: A list of song events.
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
        for subclass in _utils.get_all_subclasses(cls):
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
        raise ValueError(f"Failed to load song file: {filename}")

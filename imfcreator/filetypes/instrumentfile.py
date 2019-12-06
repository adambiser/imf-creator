import logging
import imfcreator.utils
from imfcreator.adlib import AdlibInstrument


class InstrumentFile(object):
    """The base class from which all instrument file plugins should inherit."""

    def __init__(self, fp=None, filename=None):
        """Initializes and opens the instrument file."""
        if fp is None:
            self.fp = open(filename, "rb")
            self._exclusive_fp = True
        else:
            self.fp = fp
            self._exclusive_fp = False
        self.filename = filename
        try:
            self._open()
        except (ValueError, IOError, OSError) as ex:
            self.close()
            raise ValueError(ex)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        self.close()

    def __iter__(self) -> (int, int, AdlibInstrument, int):
        for index in range(self.instrument_count):
            yield self.get_instrument(index)

    def close(self):
        """Closes the internal file object when it is owned by this instance."""
        if self._exclusive_fp and self.fp is not None:
            self._exclusive_fp = False
            self.fp.close()
            self.fp = None

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
        Implementations must be able to instruments in an arbitrary order, not just in file order.

        :param index: The index of the instrument to return.
        :return: An Adlib instrument.
        :exception ValueError: When file data is not recognized.
        """
        raise NotImplementedError()


# def open_file(f):
#     """Opens the given instrument file.
#
#     :param f: A filename or file object.
#     """
#     if type(f) is str:  # filename
#         filename = f
#         fp = open(filename, "rb")
#         exclusive_fp = True
#     else:
#         filename = ""
#         fp = f
#         exclusive_fp = False
#     # Scan plugin classes for one that can open the file.
#     preview = fp.read(32)
#     for cls in utils.get_all_subclasses(InstrumentFile):
#         if cls.accept(preview):
#             try:
#                 logging.debug(f'Attempting to load "{filename}" using {cls.__name__}.')
#                 # Reset the file position for each attempt.
#                 fp.seek(0)
#                 instance = cls(fp, filename)
#                 # The instance now owns the fp.
#                 instance._exclusive_fp = exclusive_fp
#                 logging.info(f'Loaded "{filename}" using {cls.__name__}.')
#                 return instance
#             except (ValueError, IOError, OSError) as ex:
#                 logging.warning(f'Error while attempting to load "{filename}" using {cls.__name__}: {ex}')
#     if exclusive_fp:
#         fp.close()
#     raise ValueError(f"Cannot identify instrument file: {filename}")
#
#
# def get_all_instruments(f):
#     """Returns all of the instruments in a file.
#
#     :param f: A filename or file object.
#     """
#     return [i for i in open_file(f)]

import inspect
import logging
import io
import os
import unittest

try:
    # Only show errors when importing here.
    logging.basicConfig(level=logging.ERROR, format='%(levelname)s\t%(message)s')
    import imfcreator.plugins
    import imfcreator.instruments
except ImportError:
    raise

_FILES_FOLDER = os.path.abspath("files")
_MIDI_FILES = [
    "AC.mid",
    "ievan_polkka2.mid",
]


class LoggingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setLevel(logging.WARNING)
        self.handler.setFormatter(logging.Formatter('%(levelname)s\t%(message)s'))
        self.logger = logging.getLogger('')
        for handler in self.logger.handlers:
            self.logger.removeHandler(handler)
        self.logger.addHandler(self.handler)

    def tearDown(self) -> None:
        self.logger.removeHandler(self.handler)
        self.handler.close()

    def get_stream_value(self):
        self.handler.flush()
        return self.stream.getvalue()


class PluginTestCase(LoggingTestCase):
    def test_load_plugins(self):
        # noinspection PyBroadException
        try:
            imfcreator.plugins.load_plugins()
        except Exception:
            self.fail("Exception loading plugins")

    def test_check_for_midi_filetype(self):
        filetypes = imfcreator.plugins.MidiSongFile.get_filetypes()
        value = next((ft for ft in filetypes if ft.default_extension == "mid"), None)
        self.assertIsNotNone(value, "Could not find plugin for 'mid' file type.")

    def test_check_for_imf1_filetype(self):
        value = imfcreator.plugins.AdlibSongFile.get_filetype_class("imf1")
        self.assertIsNotNone(value, "Could not find plugin for 'imf1' file type.")


class InstrumentTestCase(LoggingTestCase):
    def test_load_wopl(self):
        # imfcreator.instruments.add_file(os.path.join(_FILES_FOLDER, "GENMIDI.GS.wopl"))
        # self.assertEqual(imfcreator.instruments.count(), 330)
        imfcreator.instruments.add_file(os.path.join(_FILES_FOLDER, "Apogee-IMF-90.wopl"))
        self.assertEqual(imfcreator.instruments.count(), 174)


class SongTestCase(LoggingTestCase):
    def __init__(self, method_name, filename):
        super().__init__(methodName=method_name)
        self.filename = filename

    def compare_to_results(self, debug_info: str):
        calling_function = inspect.stack()[1].function
        result_file = self.filename + f".{calling_function}.log"
        if os.path.exists(result_file):
            try:
                with open(result_file, "r") as fp:
                    result_info = fp.read().splitlines()
                debug_lines = debug_info.splitlines()
                for index in range(min(len(debug_lines), len(result_info))):
                    self.assertEqual(debug_lines[index], result_info[index],
                                     f"First difference found in line {index + 1}.  "
                                     f"File: {os.path.basename(result_file)}")
                # Do the line count check after making sure everything up to the end of one list is the same.
                self.assertEqual(len(debug_lines), len(result_info), f"Line count mismatch.  "
                                                                     f"File: {os.path.basename(result_file)}")
            except AssertionError:
                # Write the new results to a temp file.
                with open(self.filename + f".{calling_function}.fail.log", "w") as fp:
                    fp.write(debug_info)
                raise
        else:
            # No verification, save what we have for next time.
            with open(result_file, "w") as fp:
                fp.write(debug_info)
            print(f"Verify file did not exist.  Created verify file: {os.path.basename(result_file)}")

    def test_midi_load(self):
        midi_song = imfcreator.plugins.MidiSongFile.load_file(self.filename)
        debug_info = midi_song.get_debug_info()
        self.compare_to_results(debug_info)

    def test_convert_to_imf(self):
        midi_song = imfcreator.plugins.MidiSongFile.load_file(self.filename)
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s\t%(message)s')
        adlib_song = imfcreator.plugins.AdlibSongFile.convert_from(midi_song, "imf1")
        debug_info = adlib_song.get_debug_info()
        self.compare_to_results(debug_info)


def get_test_files(path: str, extension: str):
    """Extension should include the period and is case insensitive."""
    extension = extension.lower()
    return [os.path.join(root, f)
            for root, _, files in os.walk(path)
            for f in files
            if os.path.splitext(f)[1].lower() == extension]


def get_tests():
    suite = unittest.TestSuite([
        PluginTestCase("test_load_plugins"),
        PluginTestCase("test_check_for_midi_filetype"),
        PluginTestCase("test_check_for_imf1_filetype"),
        InstrumentTestCase("test_load_wopl"),
    ])
    # for filename in get_test_files(_FILES_FOLDER, ".mid"):
    for f in _MIDI_FILES:
        filename = os.path.join(_FILES_FOLDER, f)
        suite.addTest(SongTestCase("test_midi_load", filename))
        suite.addTest(SongTestCase("test_convert_to_imf", filename))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(failfast=True)
    runner.run(get_tests())

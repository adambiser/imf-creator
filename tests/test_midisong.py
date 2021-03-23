from shutil import copyfile
import logging
import os
import unittest

import imfcreator.plugins

imfcreator.plugins.load_plugins()

_INPUT_FOLDER = os.path.abspath("input")
_OUTPUT_FOLDER = os.path.abspath("output")
_VERIFY_FOLDER = os.path.abspath("verify")

os.makedirs(_OUTPUT_FOLDER, exist_ok=True)


class TestMidiSong(unittest.TestCase):
    INPUT_FILES = ["AC.mid"]
    TEMP_FILENAME = "output.txt"

    # def setUp(self) -> None:
    #     logging.basicConfig(level=logging.DEBUG, format='%(levelname)s\t%(message)s',
    #                         filename=TestMidiSong.TEMP_FILENAME)
    #
    # def tearDown(self) -> None:
    #     if os.path.exists(TestMidiSong.TEMP_FILENAME):
    #         os.remove(TestMidiSong.TEMP_FILENAME)

    def test_file(self):
        filename = os.path.join(_INPUT_FOLDER, TestMidiSong.INPUT_FILES.pop(0))
        song = imfcreator.plugins.MidiSongFile.load_file(filename)
        lines = song.get_debug_info()
        dump_filename = os.path.basename(filename) + ".txt"
        output_filename = os.path.join(_OUTPUT_FOLDER, dump_filename)
        with open(output_filename, "w") as fp:
            fp.writelines(line + "\n" for line in lines)
        # Verify contents.
        verify_filename = os.path.join(_VERIFY_FOLDER, dump_filename)
        if os.path.exists(verify_filename):
            with open(verify_filename, "r") as fp:
                check = fp.read().splitlines()
            self.assertEqual(len(lines), len(check), "Line count mismatch.")
            for index in range(len(lines)):
                self.assertEqual(lines[index], check[index], f"Line {index} differs.")
        else:
            # No verification, save what we have for next time.
            copyfile(output_filename, verify_filename)
            self.assertFalse(False, f"Copied verify file: {verify_filename}")


if __name__ == "__main__":
    unittest.main()

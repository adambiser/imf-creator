from ._binary import u8, u16le
import os
import struct


class ImfMusicFile(object):
    def __init__(self, filename=None):
        self.commands = []
        self.file_type = 1
        self.ticks_per_second = 700
        self.title = ""
        self.composer = ""
        self.remarks = ""
        self.program = ""
        if filename:
            self._open(filename)

    # def reset(self):
    #     self.commands = []
    #     self.file_type = 1
    #     self.ticks_per_second = 700
    #     self.title = ""
    #     self.composer = ""
    #     self.remarks = ""
    #     self.program = ""

    def add_command(self, reg, value, ticks):
        """Adds a command to the list of commands."""
        try:
            assert 0 <= reg <= 0xff
            assert 0 <= value <= 0xff
            assert 0 <= ticks <= 0xffff
        except AssertionError:
            print "Value out of range! 0x{:x}, 0x{:x}, {}, cmd: {}".format(reg, value, ticks, self.num_commands)
            raise
        self.commands.append((reg, value, ticks))

    @property
    def num_commands(self):
        """Returns the number of commands."""
        return len(self.commands)

    def _open(self, filename):
        try:
            with open(filename, "rb") as f:
                data_length = u16le(f.read(2))
                self.file_type = 1 if data_length > 0 else 0
                if self.file_type == 0:
                    data_length = os.stat(filename).st_size
                    f.seek(0)
                if data_length % 4 > 0:
                    raise ValueError("Data length is not a multiple of 4.")
                ext = os.path.splitext(filename)[1].lower()
                self.ticks_per_second = 700 if ext == ".wlf" else 560
                for x in range(0, data_length, 4):
                    self.add_command(*struct.unpack('<BBH', f.read(4)))
                if self.file_type == 1:
                    # Check for unofficial tag.
                    if f.read(1) == '\x1a':
                        self.title, self.composer, self.remarks, self.program = f.read().split('\x00')[0:4]
                    else:
                        f.seek(-1, os.SEEK_CUR)
                        self.remarks = f.read()
        except EOFError:
            return None

    def save(self, filename, file_type=None, include_tag=False, remarks=None):
        if file_type is None:
            file_type = self.file_type
        # TODO include_tags, remarks, etc
        data = ""
        if file_type == 1:
            data += struct.pack("<H", self.num_commands * 4)
        for command in self.commands:
            data += struct.pack("<BBH", *command)
        with open(filename, "wb") as f:
            f.write(data)

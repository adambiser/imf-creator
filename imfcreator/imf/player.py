from .constants import *
from ..signal import Signal
import os
import pyaudio
import pyopl
import struct

_FREQUENCY = 44100


class ImfPlayer:
    """A streaming IMF music player."""
    SAMPLE_SIZE = 2  # 16-bit
    CHANNELS = 2  # stereo
    BUFFER_SAMPLE_COUNT = 512  # Max allowed: 512
    # States
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2

    def __init__(self, freq=_FREQUENCY, ticks_per_second=700):
        """Initializes the PyAudio and OPL synth."""
        self._freq = freq
        self.ticks_per_second = ticks_per_second
        # Prepare PyAudio
        self._audio = pyaudio.PyAudio()
        # Prepare buffers.
        self._data = bytearray(ImfPlayer.BUFFER_SAMPLE_COUNT * ImfPlayer.SAMPLE_SIZE * ImfPlayer.CHANNELS)
        self._buffer = buffer(self._data)  # Wraps self.data. Used by PyAudio.
        # Prepare stream attribute and opl player.
        self._stream = None  # Created later.
        self._opl = pyopl.opl(freq=freq, sampleSize=ImfPlayer.SAMPLE_SIZE, channels=ImfPlayer.CHANNELS)
        # reset
        self._commands = []
        # rewind
        self._position = 0
        self._delay = 0
        self.repeat = False
        self.ignoreregs = []
        self.onstatechanged = Signal(state=int)
        # self.mute = [False] * OPL_CHANNELS
        # self._create_stream(start=False)

    def _create_stream(self, start=True):
        """Create a new PyAudio stream."""
        self._stream = self._audio.open(
            format=self._audio.get_format_from_width(ImfPlayer.SAMPLE_SIZE),
            channels=ImfPlayer.CHANNELS,
            frames_per_buffer=ImfPlayer.BUFFER_SAMPLE_COUNT,
            rate=self._freq,
            output=True,
            start=start,  # Don't start playing immediately!
            stream_callback=self._callback)

    def remove_all_commands(self):
        """Resets the command list and rewinds."""
        self._commands = []
        self.rewind()

    def add_command(self, reg, value, ticks):
        """Adds a command to the list of commands."""
        self._commands.append((reg, value, ticks))

    @property
    def num_commands(self):
        """Returns the number of commands."""
        return len(self._commands)

    def seek(self, offset, whence=0):
        """Moves the play position to the command at the given offset."""
        if whence == 0:
            new_position = offset
        elif whence == 1:
            new_position = self._position + offset
        elif whence == 2:
            new_position = len(self._commands) + offset
        else:
            raise ValueError("Invalid argument")
        new_position = _clamp(new_position, 0, len(self._commands) - 1)
        if self._position == new_position:
            return
        # Process commands between old and new positions. If the new position is before the old,
        # rewind and start from there.
        if new_position < self._position:
            self.rewind()
        for c in range(self._position, new_position):
            self._process_command()
        # Clear the delay accumulator after processing commands.
        self._delay = 0

    def tell(self):
        """Returns the current command number."""
        return self._position

    def reset_opl(self):
        """Resets OPL player values back to defaults."""
        for x in range(1, 8):
            self.writereg(VOLUME_MSG + MODIFIERS[x], 0xf)
            self.writereg(VOLUME_MSG + CARRIERS[x], 0xf)
            self.writereg(BLOCK_MSG + x, KEY_OFF_MASK)
            self.writereg(ATTACK_DECAY_MSG + MODIFIERS[x], 0xf)
            self.writereg(ATTACK_DECAY_MSG + CARRIERS[x], 0xf)
            self.writereg(SUSTAIN_RELEASE_MSG + MODIFIERS[x], 0xf)
            self.writereg(SUSTAIN_RELEASE_MSG + CARRIERS[x], 0xf)

    def rewind(self):
        """Sets the playback position back to the beginning."""
        self._position = 0
        self._delay = 0
        self.reset_opl()

    def writereg(self, reg, value):
        if reg in self.ignoreregs:
            return
        # if (reg & 0xf0) == BLOCK_MSG:
        #     c = reg & 0xf
        #     if c < OPL_CHANNELS:
        #         if self.mute[c]:
        #             value = 0
        # if reg & 0x40:
        #     print(hex(reg))
        self._opl.writeReg(reg, value)

    def _process_command(self):
        """Processes the command at the current position and moves to the next command.

        The delay is also incremented if the command has a ticks value.
        """
        reg, value, ticks = self._commands[self._position]
        self.writereg(reg, value)
        self._position += 1
        if ticks:
            self._delay += (ticks * self._freq) // self.ticks_per_second

    def load(self, filename):
        """Loads the IMF commands from the given filename."""
        self.remove_all_commands()
        try:
            with open(filename, "rb") as f:
                data_length = struct.unpack("<H", f.read(2))[0]
                file_type = 1 if data_length > 0 else 0
                if file_type == 0:
                    data_length = os.stat(filename).st_size
                    f.seek(0)
                if data_length % 4 > 0:
                    raise ValueError("Data length is not a multiple of 4.")
                ext = os.path.splitext(filename)[1].lower()
                self.ticks_per_second = 700 if ext == ".wlf" else 560
                for x in range(0, data_length, 4):
                    self.add_command(*struct.unpack('<BBH', f.read(4)))
                comment = f.read()
            # Pass back some file information.
            # noinspection PyUnboundLocalVariable
            return {
                "file_type": file_type,
                "data_length": data_length,
                "num_commands": self.num_commands,
                "ticks_per_second": self.ticks_per_second,
                "comment": comment
                }
        except EOFError:
            return None

    # @property
    # def isactive(self):
    #     return self._stream is not None and self._stream.is_active()

    @property
    def state(self):
        if self._stream is None:
            # No stream exists, so it is stopped.
            return ImfPlayer.STOPPED
        if self._stream.is_stopped():
            if self._position == 0:
                return ImfPlayer.STOPPED
            else:
                # Stopped, but not rewound, so paused.
                return ImfPlayer.PAUSED
        if self._stream.is_active():
            return ImfPlayer.PLAYING
        else:
            # Not active and not stopped means that the stream has closed because it reached the end of its data.
            # Consider it stopped here.
            return ImfPlayer.STOPPED

    # noinspection PyUnusedLocal
    def _callback(self, input_data, frame_count, time_info, status):
        # print("_callback")
        # Build enough of a delay to fill the buffer.
        while self._delay < ImfPlayer.BUFFER_SAMPLE_COUNT and self._position < len(self._commands):
            self._process_command()
            if self.repeat and self._position == len(self._commands):
                self._position = 0
        # If we have enough to fill the buffer, do so. Otherwise quit.
        if self._delay >= ImfPlayer.BUFFER_SAMPLE_COUNT:
            self._opl.getSamples(self._data)
            self._delay -= ImfPlayer.BUFFER_SAMPLE_COUNT
            return self._buffer, pyaudio.paContinue
        else:
            self.rewind()
            self.onstatechanged(state=ImfPlayer.STOPPED)
            # self.reset_opl()
            return None, pyaudio.paComplete
        # return self.buffer, pyaudio.paContinue if self.position < len(self.commands) else pyaudio.paComplete

    def play(self, repeat=False):
        """Starts playing the song at the current position."""
        self.repeat = repeat
        if self.num_commands == 0:
            return
        # If a stream exists and it is not active and not stopped, it needs to be closed and a new one created.
        if self._stream is not None and not self._stream.is_active() and not self._stream.is_stopped():
            self._stream.close()  # close for good measure.
            self._stream = None
        # If there's no stream at this point, create one.
        if self._stream is None:
            self._create_stream(False)
        self._stream.start_stream()
        # self._stream = self._create_stream()
        self.onstatechanged(state=ImfPlayer.PLAYING)

    def pause(self):
        """Stops the PyAudio stream, but does not rewind the playback position."""
        self._stream.stop_stream()
        self.onstatechanged(state=ImfPlayer.PAUSED)

    def stop(self):
        """Stops the PyAudio stream and resets the playback position."""
        self._stream.stop_stream()
        # self.reset_opl()
        self.rewind()
        self.onstatechanged(state=ImfPlayer.STOPPED)

    def close(self):
        """Closes the PyAudio stream and terminates it."""
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._audio.terminate()


def _clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))

"""Contains classes for playing Adlib music."""
import pyaudio
import pyopl
import sys
import imfcreator.utils as utils
from enum import IntEnum, auto
from os import SEEK_SET, SEEK_CUR, SEEK_END
from imfcreator.adlib import *
from imfcreator.signal import Signal
from typing import Optional


class PlayerState(IntEnum):
    """Represents a music player state."""
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class AdlibPlayer:
    """A streaming IMF music player."""
    FREQUENCY = 44100
    SAMPLE_SIZE = 2  # 16-bit
    CHANNELS = 2  # stereo
    BUFFER_SAMPLE_COUNT = 512  # Max allowed: 512

    def __init__(self, freq: int = FREQUENCY, ticks_per_second: int = 700):
        """Initializes PyAudio and the PyOPL synth."""
        self._freq = freq
        self.ticks_per_second = ticks_per_second
        # Prepare PyAudio
        self._audio = pyaudio.PyAudio()
        # Prepare buffers.
        self._data = bytearray(AdlibPlayer.BUFFER_SAMPLE_COUNT * AdlibPlayer.SAMPLE_SIZE * AdlibPlayer.CHANNELS)
        if sys.version_info[0] < 3:
            # noinspection PyUnresolvedReferences
            self._buffer = buffer(self._data)  # Wraps self.data. Used by PyAudio.
        else:
            # Since Python 3 doesn't have buffer() and PyAudio doesn't support memoryview.
            # noinspection PyShadowingNames
            AdlibPlayer._buffer = property(lambda self: bytes(self._data))

        # Prepare stream attribute and opl player.
        self._stream = None  # type: Optional[pyaudio.Stream]  # Created later.
        self._opl = pyopl.opl(freq=freq, sampleSize=AdlibPlayer.SAMPLE_SIZE, channels=AdlibPlayer.CHANNELS)
        # reset
        # self._commands = []
        self._song = None
        # rewind
        self._position = 0
        self._delay = 0
        self.repeat = False
        # self.ignoreregs = []
        self.onstatechanged = Signal(state=PlayerState)
        # self.mute = [False] * OPL_CHANNELS
        # self._create_stream(start=False)

    def _create_stream(self, start: bool = True):
        """Create a new PyAudio stream."""
        self._stream = self._audio.open(
            format=self._audio.get_format_from_width(AdlibPlayer.SAMPLE_SIZE),
            channels=AdlibPlayer.CHANNELS,
            frames_per_buffer=AdlibPlayer.BUFFER_SAMPLE_COUNT,
            rate=self._freq,
            output=True,
            start=start,  # Don't start playing immediately!
            stream_callback=self._callback)

    def set_song(self, song):
        self._song = song
        self.rewind()

    def seek(self, offset: int, whence: int = 0):
        """Moves the play position to the command at the given offset."""
        if whence == SEEK_SET:
            new_position = offset
        elif whence == SEEK_CUR:
            new_position = self._position + offset
        elif whence == SEEK_END:
            new_position = self._song.command_count + offset
        else:
            raise ValueError("Invalid argument")
        new_position = utils.clamp(new_position, 0, self._song.command_count - 1)
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
        # for reg in range(255):
        #     self.writereg(reg, 0)
        self.writereg(0x01, 0x20)  # enable Waveform Select
        self.writereg(0x08, 0x40)  # turn off CSW mode
        self.writereg(0xBD, 0x00)  # set vibrato / tremolo depth to low, set melodic mode
        for i in range(9):
            self.writereg(0x40 | MODULATORS[i], 0x3f)  # turn off volume
            self.writereg(0x40 | CARRIERS[i], 0x3f)  # turn off volume
            self.writereg(0xb0 | i, 0)  # KEY-OFF

    def rewind(self):
        """Sets the playback position back to the beginning."""
        self._position = 0
        self._delay = 0
        self.reset_opl()

    def writereg(self, reg: int, value: int):
        # if reg in self.ignoreregs:
        #     return
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
        # noinspection PyProtectedMember
        reg, value, ticks = self._song._commands[self._position]
        self.writereg(reg, value)
        self._position += 1
        if ticks:
            self._delay += (ticks * self._freq) // self.ticks_per_second

    @property
    def state(self):
        if self._stream is None:
            # No stream exists, so it is stopped.
            return PlayerState.STOPPED
        if self._stream.is_stopped():
            if self._position == 0:
                return PlayerState.STOPPED
            else:
                # Stopped, but not rewound, so paused.
                return PlayerState.PAUSED
        if self._stream.is_active():
            return PlayerState.PLAYING
        else:
            # Not active and not stopped means that the stream has closed because it reached the end of its data.
            # Consider it stopped here.
            return PlayerState.STOPPED

    # noinspection PyUnusedLocal
    def _callback(self, input_data, frame_count, time_info, status):
        # Build enough of a delay to fill the buffer.
        while self._delay < AdlibPlayer.BUFFER_SAMPLE_COUNT and self._position < self._song.command_count:
            self._process_command()
            if self.repeat and self._position == self._song.command_count:
                self._position = 0
        # If we have enough to fill the buffer, do so. Otherwise quit.
        if self._delay >= AdlibPlayer.BUFFER_SAMPLE_COUNT:
            self._opl.getSamples(self._data)
            self._delay -= AdlibPlayer.BUFFER_SAMPLE_COUNT
            return self._buffer, pyaudio.paContinue
        else:
            self.rewind()
            self.onstatechanged(state=PlayerState.STOPPED)
            return None, pyaudio.paComplete
        # return self.buffer, pyaudio.paContinue if self.position < len(self.commands) else pyaudio.paComplete

    def play(self, repeat: bool = False):
        """Starts playing the song at the current position."""
        self.repeat = repeat
        if self._song is None or self._song.command_count == 0:
            return
        # If a stream exists and it is not active and not stopped, it needs to be closed and a new one created.
        if self._stream is not None and not self._stream.is_active() and not self._stream.is_stopped():
            self._stream.close()  # close for good measure.
            self._stream = None  # type: Optional[pyaudio.Stream]
        # If there's no stream at this point, create one.
        if self._stream is None:
            self._create_stream(False)
        self._stream.start_stream()
        # self._stream = self._create_stream()
        self.onstatechanged(state=PlayerState.PLAYING)

    def pause(self):
        """Stops the PyAudio stream, but does not rewind the playback position."""
        if self._stream:
            self._stream.stop_stream()
            self.onstatechanged(state=PlayerState.PAUSED)

    def stop(self):
        """Stops the PyAudio stream and resets the playback position."""
        if self._stream:
            self._stream.stop_stream()
            self.rewind()
            self.onstatechanged(state=PlayerState.STOPPED)

    def close(self):
        """Closes the PyAudio stream and terminates it."""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._audio.terminate()

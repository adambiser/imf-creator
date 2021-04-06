"""
PyOPL: OPL2/3 emulation for Python
Copyright 2011-2012 Adam Nielsen <malvineous@shikadi.net>
http://www.github.com/Malvineous/pyopl

PyOPL is a simple wrapper around an OPL synthesiser so that it can be accessed
from within Python.  It uses the DOSBox synth, which has been released under
the GPL license.

PyOPL does not include any audio output mechanism, it simply converts register
and value pairs into PCM data.  The example programs use PyAudio for audio
output.  Note that PyGame is not suitable for this as it lacks a method for
streaming audio generated on-the-fly, and faking it by creating new Sound
objects is unreliable as they do not always queue correctly.
"""


# noinspection PyPep8Naming
class opl:
    """
    OPL emulator
    """

    def __init__(self, freq: int, sampleSize: int, channels: int) -> None:
        """Creates an OPL emulator instance.

        :param freq: The playback rate.
        :param sampleSize: The sample size.  Must be 2.
        :param channels: Channel count. 1 for mono, 2 for stereo.
        """

    def writeReg(self, reg: int, val: int) -> None:
        """Write a value to an OPL register.

        :param reg: The register.
        :param val: The value.
        :return: None
        """

    def getSamples(self, buffer) -> None:
        """Fills the supplied buffer with audio samples.

        :param buffer: The buffer.  Note that this is a positional argument, not keyword.
        :return: None
        """

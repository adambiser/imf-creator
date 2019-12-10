"""Utility methods for unpacking byte data."""
import struct as _struct


def u8(c):
    """Read an unsigned 8-bit integer."""
    try:
        return _struct.unpack("<B", c)[0]
    except TypeError:
        return _struct.unpack("<B", bytes([c]))[0]


def s8(c):
    """Read a signed 8-bit integer."""
    try:
        return _struct.unpack("<b", c)[0]
    except TypeError:
        return _struct.unpack("<b", bytes([c]))[0]


def u16le(c):
    """Read an unsigned little-endian 16-bit integer."""
    return _struct.unpack("<H", c)[0]


def u16be(c):
    """Read an unsigned big-endian 16-bit integer."""
    return _struct.unpack(">H", c)[0]


def s16le(c):
    """Read a signed little-endian 16-bit integer."""
    return _struct.unpack("<h", c)[0]


def s16be(c):
    """Read a signed big-endian 16-bit integer."""
    return _struct.unpack(">h", c)[0]


def u32le(c):
    """Read an unsigned little-endian 32-bit integer."""
    return _struct.unpack("<I", c)[0]


def u32be(c):
    """Read an unsigned big-endian 32-bit integer."""
    return _struct.unpack(">I", c)[0]


def s32le(c):
    """Read a signed little-endian 32-bit integer."""
    return _struct.unpack("<i", c)[0]


def s32be(c):
    """Read a signed big-endian 32-bit integer."""
    return _struct.unpack(">i", c)[0]


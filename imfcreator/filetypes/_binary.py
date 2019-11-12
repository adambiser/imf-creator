import struct


def u8(c):
    return struct.unpack("<B", c)[0]


def s8(c):
    return struct.unpack("<b", c)[0]


def u16le(c):
    return struct.unpack("<H", c)[0]


def u16be(c):
    return struct.unpack(">H", c)[0]


def s16le(c):
    return struct.unpack("<h", c)[0]


def s16be(c):
    return struct.unpack(">h", c)[0]


def u32le(c):
    return struct.unpack("<I", c)[0]


def u32be(c):
    return struct.unpack(">I", c)[0]


def s32le(c):
    return struct.unpack("<i", c)[0]


def s32be(c):
    return struct.unpack(">i", c)[0]

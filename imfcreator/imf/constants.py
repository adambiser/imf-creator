OPL_CHANNELS = 9

# Register bases
TEST_MSG = 0x1
TIMER_1_COUNT_MSG = 0x2
TIMER_2_COUNT_MSG = 0x3
IRQ_RESET_MSG = 0x4
COMP_SINE_WAVE_MODE_MSG = 0x8
VIBRATO_MSG = 0x20  # Use ChannelOp, Channel/Instrument-related
VOLUME_MSG = 0x40  # Use ChannelOp, Channel/Instrument-related
ATTACK_DECAY_MSG = 0x60  # Use ChannelOp, Channel/Instrument-related
SUSTAIN_RELEASE_MSG = 0x80  # Use ChannelOp, Channel/Instrument-related
FREQ_MSG = 0xa0  # Use ChannelNum, Note-related, group with BLOCK_MSG
BLOCK_MSG = 0xb0  # Use ChannelNum, Note-related
DRUM_MSG = 0xbd
FEEDBACK_MSG = 0xc0  # Use ChannelNum, Note-related
WAVEFORM_SELECT_MSG = 0xe0  # Use ChannelOp, Channel/Instrument-related

# BLOCK_MSG Bit Masks
KEY_OFF_MASK = 0x0  # 0000 0000
KEY_ON_MASK = 0x20  # 0010 0000
BLOCK_MASK = 0x1c   # 0001 1100, >> 2 to get the block number
FREQ_MSB_MASK = 0x3 # 0000 0011

FREQ_TABLE = [
    172, 183, 194, 205, 217, 230, 244, 258, 274, 290, 307, 326,
    345, 365, 387, 410, 435, 460, 488, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 517, 547, 580, 615, 651,
    690, 731, 774, 820, 869, 921, 975, 1023, 1023, 1023, 1023, 1023,
    1023, 1023, 1023, 1023, 1023, 1023, 1023, 1023
]
BLOCK_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1
]
CARRIERS = [3, 4, 5, 11, 12, 13, 19, 20, 21]
MODIFIERS = [0, 1, 2, 8, 9, 10, 16, 17, 18]

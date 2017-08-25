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

BLOCK_FREQ_NOTE_MAP = [  # f-num = freq * 2^(20 - block) / 49716
# (0, 172), (0, 183), (0, 194), (0, 205), (0, 217), (0, 230), (0, 244), (0, 258), (0, 274), (0, 290), (0, 307), (0, 326),
# MUSPLAY and the HERETIC source start with these values. Otherwise, the music sounds an octave lower.
(0, 345), (0, 365), (0, 387), (0, 410), (0, 435), (0, 460), (0, 488), (0, 517), (0, 547), (0, 580), (0, 615), (0, 651),
(0, 690), (0, 731), (0, 774), (0, 820), (0, 869), (0, 921), (0, 975), (1, 517), (1, 547), (1, 580), (1, 615), (1, 651),
(1, 690), (1, 731), (1, 774), (1, 820), (1, 869), (1, 921), (1, 975), (2, 517), (2, 547), (2, 580), (2, 615), (2, 651),
(2, 690), (2, 731), (2, 774), (2, 820), (2, 869), (2, 921), (2, 975), (3, 517), (3, 547), (3, 580), (3, 615), (3, 651),
# C4 - Middle C, MIDI 60
(3, 690), (3, 731), (3, 774), (3, 820), (3, 869), (3, 921), (3, 975), (4, 517), (4, 547), (4, 580), (4, 615), (4, 651),
(4, 690), (4, 731), (4, 774), (4, 820), (4, 869), (4, 921), (4, 975), (5, 517), (5, 547), (5, 580), (5, 615), (5, 651),
(5, 690), (5, 731), (5, 774), (5, 820), (5, 869), (5, 921), (5, 975), (6, 517), (6, 547), (6, 580), (6, 615), (6, 651),
(6, 690), (6, 731), (6, 774), (6, 820), (6, 869), (6, 921), (6, 975), (7, 517), (7, 547), (7, 580), (7, 615), (7, 651),
(7, 690), (7, 731), (7, 774), (7, 820), (7, 869), (7, 921), (7, 975)
# , (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023),
# (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023), (-1,1023)
]
MODULATORS = [0, 1, 2, 8, 9, 10, 16, 17, 18]
CARRIERS = [3, 4, 5, 11, 12, 13, 19, 20, 21]

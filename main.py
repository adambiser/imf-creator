import logging
import os
import imfcreator.instruments as instruments
from imfcreator.imf_builder import convert_midi_to_imf
from imfcreator.mainapplication import MainApplication
from imfcreator.filetypes import SongReader

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s\t%(message)s')


def main(song):
    # player = ImfPlayer()
    # file_info = player.load("test.wlf")
    # # file_info = player.load("wolf3d.wlf")
    # print(file_info)
    # # print("num_commands: {}".format(player.num_commands))
    # # player.mute[1] = True
    # # player.mute[2] = True
    # # player.mute[3] = True
    # # player.mute[4] = True
    # # player.mute[5] = True
    # # player.mute[6] = True
    # # player.mute[7] = True
    # # player.mute[8] = True
    # # player.seek(200)
    # # player.play(True)
    # while player.isactive:
    #     # print("isactive")
    #     time.sleep(0.1)
    # player.close()
    root = MainApplication()
    root.player.set_song(song)
    root.mainloop()


# def add_command(regs, reg, value, ticks):


def copy_file(src, dst):
    with open(src, "rb") as sf:
        with open(dst, "wb") as df:
            df.write(sf.read())


if not os.path.isfile("GENMIDI.OP2"):
    copy_file("genmidi/GENMIDI.OP2", "GENMIDI.OP2")

instruments.add_file("GENMIDI.OP2")


# reader = SongReader.open_file("test/test-pitchbend.mid")
reader = SongReader.open_file("test/Ecu_10_Bass_xg-hr.mid")
# reader = SongReader.open_file("exclude/OUT1FM.mid")
# reader = SongReader.open_file("test/testfmt0.mid")
# reader = SongReader.open_file("test/testfmt1.mid")
# reader = SongReader.open_file("test/test-velocity.mid")
imf = convert_midi_to_imf(reader)   # , instruments)  # , mute_channels=[9])
# imf = convert_midi_to_imf(reader, instruments, mute_tracks=[1], mute_channels=[9])
# convert_midi_to_imf(reader, instruments, mute_tracks=[3])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2], mute_channels=[9])

main(imf)

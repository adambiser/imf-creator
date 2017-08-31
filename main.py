import os

from imfcreator.filetypes import instrumentfile
from imfcreator.imf_builder import convert_midi_to_imf
from imfcreator.mainapplication import MainApplication
from imfcreator.filetypes.midifileplugin import MidiReader


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

instruments = instrumentfile.get_all_instruments("GENMIDI.OP2")  # .freedoom


reader = MidiReader()
reader.load("test/test-pitchbend.mid")
# reader.load("exclude/OUT1FM.mid")
# reader.load("test-pitchbend.mid")
# reader.load("testfmt1.mid")
# reader.load("blobs.mid")
imf = convert_midi_to_imf(reader, instruments)  # , mute_channels=[9])
# imf = convert_midi_to_imf(reader, instruments, mute_tracks=[1], mute_channels=[9])
# convert_midi_to_imf(reader, instruments, mute_tracks=[3])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2], mute_channels=[9])

main(imf)

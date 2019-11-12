#!/usr/bin/python

from imfcreator.mainapplication import MainApplication


def main():
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
    root.mainloop()


# def add_command(regs, reg, value, ticks):


# reader.load("exclude/OUT1FM.mid")
# reader.load("test-pitchbend.mid")
# reader.load("testfmt1.mid")
# reader.load("blobs.mid")
# , mute_channels=[9])
# imf = convert_midi_to_imf(reader, instruments, mute_tracks=[1], mute_channels=[9])
# convert_midi_to_imf(reader, instruments, mute_tracks=[3])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2])
# convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2], mute_channels=[9])

main()

import imfcreator.instruments as instruments
from imfcreator.mainapplication import MainApplication
from imfcreator.plugins import MidiSongFile, AdlibSongFile


def open_ui(song):
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


def main():
    # if not os.path.isfile("GENMIDI.OP2"):
    #     shutil.copy("genmidi/GENMIDI.OP2", "GENMIDI.OP2")

    instruments.add_file("GENMIDI.OP2")
    # reader = SongReader.open_file("test/test-pitchbend.mid")
    midi_song = MidiSongFile.load_file("test/Ecu_10_Bass_xg-hr.mid")
    # reader = SongReader.open_file("exclude/OUT1FM.mid")
    # reader = SongReader.open_file("test/testfmt0.mid")
    # reader = SongReader.open_file("test/testfmt1.mid")
    # reader = SongReader.open_file("test/test-velocity.mid")
    settings = {"title": "Hello"}
    song = AdlibSongFile.convert_from(midi_song, "imf1", settings)
    song.save_file("output.wlf")
    # if data:
    #     with open("output.wlf", "wb") as f:
    #         f.write(data)
    # imf = convert_midi_to_imf(reader)   # , instruments)  # , mute_channels=[9])
    # imf = convert_midi_to_imf(reader, instruments, mute_tracks=[1], mute_channels=[9])
    # convert_midi_to_imf(reader, instruments, mute_tracks=[3])
    # convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2])
    # convert_midi_to_imf(reader, instruments, mute_tracks=[0, 1, 2], mute_channels=[9])
    open_ui(song)


if __name__ == "__main__":
    main()

from .filetypes.imfmusicfile import ImfMusicFile
from player import ImfPlayer
from resources import Resources
from imfcreator.filetypes import instrumentfile
from imfcreator.imf_builder import convert_midi_to_imf
from imfcreator.filetypes.midifileplugin import MidiReader


try:
    import Tix as tix
    import tkFileDialog
except ImportError:
    import tkinter.tix as tix
    import tkinter.filedialog as tkFileDialog


def copy_file(src, dst):
    with open(src, "rb") as sf:
        with open(dst, "wb") as df:
            df.write(sf.read())


class MainApplication(tix.Tk):
    def __init__(self, screen_name=None, base_name=None, class_name='Tix'):
        # Set up the window.
        tix.Tk.__init__(self, screen_name, base_name, class_name)
        self.title('IMF Creator')
        # self.tk.call('wm', 'iconbitmap', self._w, '-default', os.path.join(Resources.PATH, 'icon.ico'))
        # self.settings = Settings()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.player = ImfPlayer()
        self.bank_file = "genmidi/GENMIDI.OP2"  # freedoom
        self.song_path = "test/testtag.wlf"
        self.instruments = None
        self.load_bank(self.bank_file)
        self.reload_song()
        self.open_bank_button = tix.Button(self, text='Open bank', command=self.open_bank_file)
        self.open_bank_button.image = Resources.getimage('bank.gif')
        self.open_bank_button.config(image=self.open_bank_button.image)
        self.open_bank_button.pack(side='left')
        self.open_midi_button = tix.Button(self, text='Open MIDI', command=self.open_music_file)
        self.open_midi_button.image = Resources.getimage('song.gif')
        self.open_midi_button.config(image=self.open_midi_button.image)
        self.open_midi_button.pack(side='left')
        self.play_button = tix.Button(self, text='Play', command=self.toggle_play)
        self.play_button.image = Resources.getimage('play.gif')
        self.play_button.config(image=self.play_button.image)
        self.play_button.pack(side='left')

        self.player.onstatechanged.add_handler(self.on_player_state_changed)

    def open_bank_file(self):
        bank = tkFileDialog.askopenfilename(title="Open an instruments bank file",
                                            filetypes=(
                                                ("Bank files", "*.op2 *.wopl *.OP2 *.WOPL"),
                                                ("all files", "*.*")
                                            ),
                                            parent=self)
        if bank:
            self.bank_file = bank
            self.load_bank(self.bank_file)
            self.reload_song()

    def open_music_file(self):
        song = tkFileDialog.askopenfilename(title="Open a music file (MIDI or IMF)",
                                            filetypes=(
                                                ("MIDI files", "*.mid *.MID"),
                                                ("IMF files", "*.imf *.wlf *.IMF *.WLF"),
                                                ("all files", "*.*")
                                            ),
                                            parent=self)
        if song:
            self.song_path = song
            self.reload_song()

    def load_bank(self, path):
        self.instruments = instrumentfile.get_all_instruments(path)

    def reload_song(self):
        if self.song_path.lower().endswith(".imf") or self.song_path.lower().endswith(".wlf"):
            imf = ImfMusicFile(self.song_path)
        else:
            reader = MidiReader()
            reader.load(self.song_path)
            imf = convert_midi_to_imf(reader, self.instruments)
            del reader
        self.player.set_song(imf)

    def toggle_play(self):
        if self.player.state == ImfPlayer.PLAYING:
            self.player.stop()
        else:
            self.player.play()

    def on_player_state_changed(self, state):
        # print("on_player_state_changed: {}".format(state))
        if state == ImfPlayer.PLAYING:
            self.play_button.image = Resources.getimage('stop.gif')
        elif state == ImfPlayer.STOPPED:
            self.play_button.image = Resources.getimage('play.gif')
        self.play_button.config(image=self.play_button.image)

    def _on_closing(self):
        self.player.close()
        self.destroy()

from imfcreator import resources
from imfcreator.plugins.imfmusicfile import ImfMusicFile
from imfcreator.player import ImfPlayer, PlayerState

try:
    # noinspection PyPep8Naming
    import Tix as tix
except ImportError:
    import tkinter.tix as tix


class MainApplication(tix.Tk):
    # noinspection PyPep8Naming
    def __init__(self, screenName=None, baseName=None, className='Tix'):
        # Set up the window.
        tix.Tk.__init__(self, screenName, baseName, className)
        self.title('IMF Creator')
        # self.tk.call('wm', 'iconbitmap', self._w, '-default', os.path.join(Resources.PATH, 'icon.ico'))
        # self.settings = Settings()
        self.protocol("WM_DELETE_WINDOW", self._onclosing)
        self.player = ImfPlayer()
        # self.player.load("test.wlf")
        self.player.set_song(ImfMusicFile("test/testtag.wlf"))
        # self.player.load("wolf3d.wlf")
        # print(fileinfo)
        self.play_button = tix.Button(self, text='Play', command=self.toggle_play)
        self.play_button.image = resources.get_image('play.gif')
        self.play_button.config(image=self.play_button.image)
        self.play_button.pack(side='left')
        self.player.onstatechanged.add_handler(self._onplayerstatechanged)

    def toggle_play(self):
        if self.player.state == PlayerState.PLAYING:
            self.player.stop()
        else:
            self.player.play()

    def _onplayerstatechanged(self, state: PlayerState):
        # print(f"onplayerstatechanged: {state}")
        if state == PlayerState.PLAYING:
            self.play_button.image = resources.get_image('stop.gif')
        elif state == PlayerState.STOPPED:
            self.play_button.image = resources.get_image('play.gif')
        self.play_button.config(image=self.play_button.image)

    def _onclosing(self):
        self.player.close()
        self.destroy()

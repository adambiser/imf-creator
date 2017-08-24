from imf.player import ImfPlayer
from imf.imfmusicfile import ImfMusicFile
from resources import Resources
# try:
#     import Tkinter as tk
# except ImportError:
#     import tkinter as tk
try:
    import Tix as tix
except ImportError:
    import tkinter.tix as tix


class MainApplication(tix.Tk):
    def __init__(self, screenName=None, baseName=None, className='Tix'):
        # Set up the window.
        tix.Tk.__init__(self, screenName, baseName, className)
        self.title('IMF Creator')
        # self.tk.call('wm', 'iconbitmap', self._w, '-default', os.path.join(Resources.PATH, 'icon.ico'))
        # self.settings = Settings()
        # self.protocol("WM_DELETE_WINDOW", self._onclosing)
        self.player = ImfPlayer()
        # self.player.load("test.wlf")
        self.player.set_song(ImfMusicFile("testtag.wlf"))
        # self.player.load("wolf3d.wlf")
        # print(fileinfo)
        self.play_button = tix.Button(self, text='Play', command=self.toggle_play)
        self.play_button.image = Resources.getimage('play.gif')
        self.play_button.config(image=self.play_button.image)
        self.play_button.pack(side='left')
        self.player.onstatechanged.add_handler(self.onplayerstatechanged)

    def toggle_play(self):
        if self.player.state == ImfPlayer.PLAYING:
            self.player.stop()
        else:
            self.player.play()

    def onplayerstatechanged(self, state):
        # print("onplayerstatechanged: {}".format(state))
        if state == ImfPlayer.PLAYING:
            self.play_button.image = Resources.getimage('stop.gif')
        elif state == ImfPlayer.STOPPED:
            self.play_button.image = Resources.getimage('play.gif')
        self.play_button.config(image=self.play_button.image)

import os
import shelve
import subprocess
import pyinotify
import platform
import threading
from distutils import spawn
from .filetypes.imfmusicfile import ImfMusicFile
from player import ImfPlayer
from resources import Resources
from imfcreator.filetypes import instrumentfile
from imfcreator.imf_builder import convert_midi_to_imf
from imfcreator.filetypes.midifileplugin import MidiReader

try:
    import Tix as tix
    import ttk
    import tkFileDialog
    import tkMessageBox
except ImportError:
    import tkinter.tix as tix
    from tkinter import tix
    import tkinter.filedialog as tkFileDialog
    import tkinter.messagebox as tkMessageBox


def copy_file(src, dst):
    with open(src, "rb") as sf:
        with open(dst, "wb") as df:
            df.write(sf.read())


def run_and_exit(on_exit, proc_args):
    def run_in_thread(_on_exit, _proc_args):
        proc = subprocess.Popen(proc_args)
        proc.wait()
        _on_exit()
        return
    thread = threading.Thread(target=run_in_thread, args=(on_exit, proc_args))
    thread.start()
    # returns immediately after the thread starts
    return thread


class MainApplication:
    def __init__(self, master):
        # Set up the window.
        self.frame = ttk.Frame(master)
        self.frame.pack()
        self.master = master
        self.master.title('IMF Creator')
        # self.tk.call('wm', 'iconbitmap', self._w, '-default', os.path.join(Resources.PATH, 'icon.ico'))
        self.instruments = None
        self.imf = None
        self.imf_format = 0
        self.song_path = ""
        self.bank_file = ""
        self.be_notifier = None
        self.be_wm = None
        self.be_wdd = None
        self.be_thread = None
        self._load_settings()
        self._build_ui()
        self.reload_bank()
        self.reload_song()
        self.player.onstatechanged.add_handler(self.on_player_state_changed)

    def _load_settings(self):
        self.settings = shelve.open('settings.dat', writeback=True)
        self.master.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.player = ImfPlayer()
        self.bank_file = self.settings['bank_file'] if 'bank_file' in self.settings else "genmidi/GENMIDI.OP2"
        self.song_path = self.settings['song_file'] if 'song_file' in self.settings else "test/testtag.wlf"
        self.imf_format = self.settings['imf_format'] if 'imf_format' in self.settings else 0

    def _build_ui(self):
        def do_nothing():
            pass

        # Menubar
        self.menubar = tix.Menu(self.master)

        file_menu = tix.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_music_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)
        self.menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tix.Menu(self.menubar, tearoff=0)
        edit_menu.add_command(label="Instruments", command=self.edit_instruments)
        self.menubar.add_cascade(label="Edit", menu=edit_menu)

        options_menu = tix.Menu(self.menubar, tearoff=0)
        options_menu_imf_format = tix.Menu(self.menubar, tearoff=0)
        options_menu_imf_format.add_command(label="IMF Type 0 (Duke Nukem 2)", command=self.imf_set_format_0)
        options_menu_imf_format.add_command(label="IMF Type 1 (Wolf3D)", command=self.imf_set_format_1)
        options_menu_imf_format.add_command(label="IMF Type 2 (Wolf4GW)", command=self.imf_set_format_2)
        options_menu.add_cascade(label="IMF Format", menu=options_menu_imf_format)
        options_menu.add_separator()
        options_menu.add_command(label="IMF Ticks/Second", command=do_nothing, state=tix.DISABLED)
        options_menu.add_separator()
        options_menu.add_command(label="Use OPL Fine tuning", command=do_nothing, state=tix.DISABLED)
        options_menu.add_command(label="Use OPL Secondary voices", command=do_nothing, state=tix.DISABLED)
        options_menu.add_separator()
        options_menu.add_command(label="Add Chord Spacing", command=do_nothing, state=tix.DISABLED)
        options_menu.add_command(label="Aggressive Channel Selection", command=do_nothing, state=tix.DISABLED)
        options_menu.add_command(label="Do Pitchbends", command=do_nothing, state=tix.DISABLED)
        options_menu.add_separator()
        options_menu.add_command(label="Select bank file", command=self.open_bank_file)
        options_menu.add_command(label="Pitchbend Scale", command=self.open_bank_file, state=tix.DISABLED)
        options_menu.add_command(label="Pitchbend Threshold", command=self.open_bank_file, state=tix.DISABLED)
        options_menu.add_separator()
        options_menu.add_command(label="Calculate Discarded Notes", command=self.open_bank_file, state=tix.DISABLED)
        self.menubar.add_cascade(label="Options", menu=options_menu)

        help_menu = tix.Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="Contents", command=do_nothing, state=tix.DISABLED)
        help_menu.add_command(label="About...", command=do_nothing, state=tix.DISABLED)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        self.master.config(menu=self.menubar)

        self.label_current_music_box = ttk.Frame(self.frame)
        self.label_current_music = ttk.Label(self.label_current_music_box,
                                             text=os.path.basename(self.song_path),
                                             justify='left',
                                             width=50)
        self.label_current_music.pack()
        self.label_current_music_box.pack(side='top')

        self.label_current_bank_box = ttk.Frame(self.frame)
        self.label_current_bank = ttk.Label(self.label_current_bank_box,
                                            text=os.path.basename(self.bank_file),
                                            justify='left',
                                            width=50)
        self.label_current_bank.pack()
        self.label_current_bank_box.pack(side='top')

        self.label_current_imf_format_box = ttk.Frame(self.frame)
        self.label_current_imf_format = ttk.Label(self.label_current_bank_box,
                                                  text=("IMF Format Type %d" % self.imf_format),
                                                  justify='left',
                                                  width=50)
        self.label_current_imf_format.pack()
        self.label_current_imf_format_box.pack(side='top')

        # Open bank file
        self.open_bank_button = ttk.Button(self.frame, text='Open bank', command=self.open_bank_file)
        self.open_bank_button.image = Resources.getimage('bank.gif')
        self.open_bank_button.config(image=self.open_bank_button.image)
        self.open_bank_button.pack(side='left')
        # Open MIDI file
        self.open_midi_button = ttk.Button(self.frame, text='Open MIDI', command=self.open_music_file)
        self.open_midi_button.image = Resources.getimage('song.gif')
        self.open_midi_button.config(image=self.open_midi_button.image)
        self.open_midi_button.pack(side='left')
        # Play the song
        self.play_button = ttk.Button(self.frame, text='Play', command=self.toggle_play)
        self.play_button.image = Resources.getimage('play.gif')
        self.play_button.config(image=self.play_button.image)
        self.play_button.pack(side='left')
        # Save IMF file
        self.save_button = ttk.Button(self.frame, text='Save', command=self.save_imf)
        self.save_button.image = Resources.getimage('save.gif')
        self.save_button.config(image=self.save_button.image, state=tix.DISABLED)
        self.save_button.pack(side='left')
        self.master.update()

    def _bank_editor_exit(self):
        self.be_notifier.stop()
        del self.be_wdd
        del self.be_notifier
        del self.be_wm
        del self.be_thread
        self.be_notifier = None
        self.be_wm = None
        self.be_wdd = None
        self.be_thread = None

    class FileModifyHandler(pyinotify.ProcessEvent):
        def __init__(self, p_root):
            pyinotify.ProcessEvent.__init__(self)
            self.root = p_root

        # Reload bank and the song once bank was saved on the side of OPL3 Bank Editor
        def process_IN_CLOSE_WRITE(self, evt):
            self.root.reload_bank()
            self.root.reload_song()

    def edit_instruments(self):
        be_exec = spawn.find_executable('opl3_bank_editor')
        # TODO: Add an option to manually specify a path to Bank Editor executable when it can't be find automatically
        if be_exec is None:
            tkMessageBox.showwarning("OPL3 Bank Editor is not found",
                                     "Can't run %s because it's probably not installed. "
                                     "You can find it here: \n"
                                     "https://github.com/Wohlstand/OPL3BankEditor" % be_exec, parent=self.frame)
        elif self.be_wm is None and self.be_thread is None:
            # Setup file modify watcher (after saving of bank file by Bank Editor
            # a reload of bank and music files should happen automatically)
            handler = MainApplication.FileModifyHandler(self)
            self.be_wm = pyinotify.WatchManager()
            self.be_notifier = pyinotify.ThreadedNotifier(self.be_wm, handler)
            self.be_notifier.start()
            self.be_wdd = self.be_wm.add_watch(self.bank_file, pyinotify.IN_CLOSE_WRITE, rec=True)
            # Start Bank Editor
            self.be_thread = run_and_exit(self._bank_editor_exit, [be_exec, self.bank_file])
        else:
            tkMessageBox.showwarning("Already open", "Instruments Editor is already running.", parent=self.frame)

    def imf_set_format_0(self):
        self.imf_format = 0
        self.settings['imf_format'] = self.imf_format
        self.label_current_imf_format['text'] = ("IMF Format Type %d" % self.imf_format)
        self.reload_song()

    def imf_set_format_1(self):
        self.imf_format = 1
        self.settings['imf_format'] = self.imf_format
        self.label_current_imf_format['text'] = ("IMF Format Type %d" % self.imf_format)
        self.reload_song()

    def imf_set_format_2(self):
        self.imf_format = 2
        self.settings['imf_format'] = self.imf_format
        self.label_current_imf_format['text'] = ("IMF Format Type %d" % self.imf_format)
        self.reload_song()

    def open_bank_file(self):
        dir_path = os.path.dirname(self.bank_file) if self.bank_file is not None else None
        bank = tkFileDialog.askopenfilename(title="Open an instruments bank file",
                                            filetypes=(
                                                ("Bank files", "*.op2 *.wopl *.OP2 *.WOPL"),
                                                ("all files", "*.*")
                                            ),
                                            parent=self.master,
                                            initialdir=dir_path)
        if bank:
            self.bank_file = bank
            self.settings['bank_file'] = self.bank_file
            self.label_current_bank['text'] = os.path.basename(self.bank_file)
            self.load_bank(self.bank_file)
            self.reload_song()

    def open_music_file(self):
        dir_path = os.path.dirname(self.song_path) if self.song_path is not None else None
        song = tkFileDialog.askopenfilename(title="Open a music file (MIDI or IMF)",
                                            filetypes=(
                                                ("MIDI files", "*.mid *.MID"),
                                                ("IMF files", "*.imf *.wlf *.IMF *.WLF"),
                                                ("all files", "*.*")
                                            ),
                                            parent=self.master,
                                            initialdir=dir_path)
        if song:
            self.song_path = song
            self.settings['song_file'] = self.song_path
            self.label_current_music['text'] = os.path.basename(self.song_path)
            self.reload_song()

    def reload_bank(self):
        self.load_bank(self.bank_file)

    def load_bank(self, path):
        self.instruments = instrumentfile.get_all_instruments(path)

    def reload_song(self):
        self.save_button['state'] = tix.DISABLED
        if self.song_path.lower().endswith(".imf") or self.song_path.lower().endswith(".wlf"):
            self.imf = ImfMusicFile(self.song_path)
        else:
            reader = MidiReader()
            reader.load(self.song_path)
            self.imf = convert_midi_to_imf(reader, self.instruments, imf_file_type=self.imf_format)
            del reader
            self.save_button['state'] = tix.NORMAL
        self.player.set_song(self.imf)

    def toggle_play(self):
        if self.player.state == ImfPlayer.PLAYING:
            self.player.stop()
        else:
            self.player.play()

    def save_imf(self):
        dir_path = os.path.dirname(self.song_path) if self.song_path is not None else None
        file_basename = os.path.splitext(os.path.basename(self.song_path))[0] if self.song_path is not None else None
        options = dict()
        options['defaultextension'] = '.imf'
        options['initialdir'] = dir_path
        options['initialfile'] = file_basename + ".imf"
        options['parent'] = self.master
        options['filetypes'] = [("IMF file", ".imf")]
        options['title'] = "Save an IMF file"
        dst_song = tkFileDialog.asksaveasfilename(**options)
        if dst_song:
            self.imf.save(dst_song, file_type=self.imf_format)

    def on_player_state_changed(self, state):
        # print("on_player_state_changed: {}".format(state))
        if state == ImfPlayer.PLAYING:
            self.play_button.image = Resources.getimage('stop.gif')
        elif state == ImfPlayer.STOPPED:
            self.play_button.image = Resources.getimage('play.gif')
        self.play_button.config(image=self.play_button.image)

    def _on_closing(self):
        self.settings.sync()
        self.settings.close()
        self.player.close()
        self.frame.destroy()
        self.master.quit()


root = tix.Tk()
if platform.system() != "Windows":
    root.style = ttk.Style()
    root.style.theme_use('clam')


def run_app():
    global root
    app = MainApplication(root)
    root.mainloop()

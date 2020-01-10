import logging
import os
import shelve
import subprocess
import typing
# import pyinotify
import platform
import threading
import imfcreator.instruments as instruments
import imfcreator.resources as resources
# from distutils import spawn
from imfcreator.plugins import AdlibSongFile, MidiSongFile
from imfcreator.player import AdlibPlayer, PlayerState

try:
    # noinspection PyPep8Naming
    import Tkinter as tk
    import ttk
    # noinspection PyPep8Naming
    import tkFileDialog as filedialog
    # noinspection PyPep8Naming
    import tkMessageBox as messagebox
except ImportError:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox

__version__ = 0.1
_ADLIB_FILETYPES = AdlibSongFile.get_filetypes()
PADDING = {"padx": 5, "pady": 5}


# def get_filetype_info(filetype):
#     """
#     Gets the filetype info for the given filetype index or name.
#
#     :param filetype: can be an index in the _FILETYPES list or a filetype name
#     :return: The FileType info.
#     """
#     try:
#         # filetype is an index.
#         return _FILETYPES[filetype]
#     except TypeError:
#         # filetype is a name.
#         return next((info for info in _FILETYPES if info.name == filetype), None)


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


class Menu(tk.Menu):
    def __init__(self, parent: "MainApplication", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        def create_menu(label):
            menu = tk.Menu(self, tearoff=0)
            self.add_cascade(label=label, menu=menu)
            return menu

        self.file_menu = create_menu("File")
        self.file_menu.add_command(label="Open", command=parent.open_music_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=parent.close_window)

        self.edit_menu = create_menu("Edit")
        self.edit_menu.add_command(label="Instruments", command=parent.edit_instruments)

        self.options_menu = create_menu("Options")
        # options_menu_filetypes = tk.Menu(menubar, tearoff=0)
        # for info in AdlibSongFile.get_filetypes():
        #     options_menu_filetypes.add_command(label=info.description,
        #                                        command=lambda filetype=info: self.set_filetype(filetype))
        # options_menu.add_cascade(label="File Types", menu=options_menu_filetypes)
        # options_menu.add_separator()
        # options_menu.add_command(label="IMF Ticks/Second", command=do_nothing, state=tk.DISABLED)
        # options_menu.add_separator()
        # options_menu.add_command(label="Use OPL Fine tuning", command=do_nothing, state=tk.DISABLED)
        # options_menu.add_command(label="Use OPL Secondary voices", command=do_nothing, state=tk.DISABLED)
        # options_menu.add_separator()
        # options_menu.add_command(label="Add Chord Spacing", command=do_nothing, state=tk.DISABLED)
        # options_menu.add_command(label="Aggressive Channel Selection", command=do_nothing, state=tk.DISABLED)
        # options_menu.add_command(label="Do Pitchbends", command=do_nothing, state=tk.DISABLED)
        # self.options_menu.add_separator()
        self.options_menu.add_command(label="Select bank file", command=parent.open_bank_file)
        # options_menu.add_command(label="Pitchbend Scale", command=self.open_bank_file, state=tk.DISABLED)
        # options_menu.add_command(label="Pitchbend Threshold", command=self.open_bank_file, state=tk.DISABLED)
        # options_menu.add_separator()
        # options_menu.add_command(label="Calculate Discarded Notes", command=self.open_bank_file, state=tk.DISABLED)

        self.help_menu = create_menu("Help")
        self.help_menu.add_command(label="Contents", command=None, state=tk.DISABLED)
        self.help_menu.add_command(label="About...", command=None, state=tk.DISABLED)


class InfoFrame(tk.Frame):
    def __init__(self, parent: "MainApplication", *_, **kwargs):
        super().__init__(parent, **kwargs)
        # File type row.
        row = 0
        ttk.Label(self, text="Output File Type:").grid(row=row, column=0, sticky=tk.W, **PADDING)
        self.filetype_combo = ttk.Combobox(self,
                                           justify='left',
                                           state="readonly",
                                           values=[filetype.description for filetype in _ADLIB_FILETYPES],
                                           height=8,
                                           width=70)
        self.filetype_combo.bind("<<ComboboxSelected>>",
                                 lambda event:
                                 parent.set_filetype(_ADLIB_FILETYPES[self.filetype_combo.current()].name))
        self.filetype_combo.grid(row=row, column=1, sticky=tk.W, **PADDING)
        # Current song file row.
        row += 1
        ttk.Label(self, text="Current Song:").grid(row=row, column=0, sticky=tk.W, **PADDING)
        self.song_label = ttk.Label(self,
                                    justify=tk.LEFT,
                                    width=70,
                                    relief=tk.SUNKEN)
        self.song_label.grid(row=row, column=1, sticky=tk.W, **PADDING)
        # Current bank file row.
        row += 1
        ttk.Label(self, text="Current Bank:").grid(row=row, column=0, sticky=tk.W, **PADDING)
        self.bank_label = ttk.Label(self,
                                    text="BANK FILE",  # os.path.basename(self.bank_file),
                                    justify=tk.LEFT,
                                    width=70,
                                    relief=tk.SUNKEN)  # flat, groove, raised, ridge, solid, or sunken
        self.bank_label.grid(row=row, column=1, sticky=tk.W, **PADDING)

        # Set up variable monitoring.
        def monitor_filetype_variable(combo, var):
            def update_combo(*_):
                filetype = var.get()
                index = next((index for index, _ in enumerate(_ADLIB_FILETYPES) if _.name == filetype), None)
                combo.current(index)
            update_combo()
            var.trace_add("write", update_combo)

        monitor_filetype_variable(self.filetype_combo, parent.filetype)

        def monitor_file_variable(label, file_var):
            def update_file_label(*_):
                label["text"] = os.path.basename(file_var.get())
            update_file_label()
            file_var.trace_add("write", update_file_label)

        monitor_file_variable(self.song_label, parent.song_file)
        monitor_file_variable(self.bank_label, parent.bank_file)


class ToolBar(ttk.Frame):
    def __init__(self, parent: "MainApplication", *_, **kwargs):
        super().__init__(parent, **kwargs)
        style = ttk.Style()
        style.configure("ToolBar.TFrame", background="white")
        self["style"] = "ToolBar.TFrame"

        def create_button(text, image_file, command):
            button = ttk.Button(self, text=text, command=command)
            button.image = resources.get_image(image_file)
            button["image"] = button.image
            button.pack(side=tk.LEFT)
            return button

        self.open_bank_button = create_button("Open Bank File", "bank.gif", parent.open_bank_file)
        self.open_music_button = create_button("Open Music File", "song.gif", parent.open_music_file)
        self.play_button = create_button("Play", "play.gif", parent.toggle_play)
        self.save_button = create_button("Save", "save.gif", parent.save_imf)
        self.save_button["state"] = tk.DISABLED

        self.play_image = resources.get_image('play.gif')
        self.stop_image = resources.get_image('stop.gif')
        parent.player.onstatechanged.add_handler(self._on_player_state_changed)

    def _on_player_state_changed(self, state):
        if state == PlayerState.PLAYING:
            self.play_button.image = self.stop_image
        elif state == PlayerState.STOPPED:
            self.play_button.image = self.play_image
        # TODO Add pausing?
        self.play_button["image"] = self.play_button.image


class Settings:
    def __init__(self, parent):
        self._db = shelve.open('settings', writeback=True)

        def monitor_variable(var: tk.Variable, settings_key: str, default):
            def write_setting(*_):
                self._db[settings_key] = var.get()

            var.set(self._db.get(settings_key, default))
            var.trace_add("write", write_setting)

        monitor_variable(parent.bank_file, "bank_file", "genmidi/GENMIDI.OP2")
        monitor_variable(parent.song_file, "song_file", "")
        monitor_variable(parent.filetype, "filetype", "")

    def close(self):
        self._db.sync()
        self._db.close()
        del self._db


class MainApplication(ttk.Frame):
    def __init__(self, parent, *_, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        # self.tk.call('wm', 'iconbitmap', self._w, '-default', os.path.join(Resources.PATH, 'icon.ico'))
        # Define variables
        self._adlib_song = None  # type: typing.Optional[AdlibSongFile]
        self._midi_song = None  # type: typing.Optional[MidiSongFile]
        self.filetype = tk.StringVar()
        self.song_file = tk.StringVar()
        self.bank_file = tk.StringVar()
        self.filetype.trace_add("write", lambda *_: self._convert_song())
        self.song_file.trace_add("write", lambda *_: self.reload_song())
        self.bank_file.trace_add("write", lambda *_: self.reload_bank())
        # self.be_notifier = None
        # self.be_wm = None
        # self.be_wdd = None
        # self.be_thread = None
        # Create the UI
        self.player = AdlibPlayer()
        self.menubar = Menu(self)
        self.toolbar = ToolBar(self)
        self.infoframe = InfoFrame(self)
        parent["menu"] = self.menubar
        self.toolbar.pack(side=tk.TOP, anchor=tk.W)
        self.infoframe.pack(side=tk.TOP, anchor=tk.W)
        self._settings = Settings(self)
        self.update()

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

    # class FileModifyHandler(pyinotify.ProcessEvent):
    #     def __init__(self, p_root):
    #         pyinotify.ProcessEvent.__init__(self)
    #         self.root = p_root
    #
    #     # Reload bank and the song once bank was saved on the side of OPL3 Bank Editor
    #     def process_IN_CLOSE_WRITE(self, evt):
    #         self.root.reload_bank()
    #         self.root.reload_song()

    def edit_instruments(self):
        pass
        # be_exec = spawn.find_executable('opl3_bank_editor')
        # # TODO: Add an option to manually specify a path to Bank Editor executable when it can't be find automatically
        # if be_exec is None:
        #     messagebox.showwarning("OPL3 Bank Editor is not found",
        #                            "Can't run opl3_bank_editor because it's probably not installed. "
        #                            "You can find it here: \n"
        #                            "https://github.com/Wohlstand/OPL3BankEditor", parent=self.frame)
        # elif self.be_wm is None and self.be_thread is None:
        #     # Setup file modify watcher (after saving of bank file by Bank Editor
        #     # a reload of bank and music files should happen automatically)
        #     # handler = MainApplication.FileModifyHandler(self)
        #     # self.be_wm = pyinotify.WatchManager()
        #     # self.be_notifier = pyinotify.ThreadedNotifier(self.be_wm, handler)
        #     # self.be_notifier.start()
        #     # self.be_wdd = self.be_wm.add_watch(self.bank_file.get(), pyinotify.IN_CLOSE_WRITE, rec=True)
        #     # # Start Bank Editor
        #     # self.be_thread = run_and_exit(self._bank_editor_exit, [be_exec, self.bank_file])
        # else:
        #     messagebox.showwarning("Already open", "Instruments Editor is already running.", parent=self.frame)

    def set_filetype(self, filetype):
        self.filetype.set(filetype)

    def open_bank_file(self):
        dir_path = os.path.dirname(self.bank_file.get()) if self.bank_file.get() else None
        bank = filedialog.askopenfilename(title="Open an instruments bank file",
                                          filetypes=(
                                              ("Bank files", "*.op2 *.wopl *.OP2 *.WOPL"),
                                              ("all files", "*.*")
                                          ),
                                          parent=self,
                                          initialdir=dir_path)
        if bank:
            self.bank_file.set(bank)
            self.load_bank(self.bank_file.get())
            self.reload_song()

    def open_music_file(self):
        dir_path = os.path.dirname(self.song_file.get()) if self.song_file.get() else None
        song = filedialog.askopenfilename(title="Open a music file (MIDI or IMF)",
                                          filetypes=(
                                              ("MIDI files", "*.mid *.MID"),
                                              ("IMF files", "*.imf *.wlf *.IMF *.WLF"),
                                              ("all files", "*.*")
                                          ),
                                          parent=self,
                                          initialdir=dir_path)
        if song:
            self.song_file.set(song)

    def reload_bank(self):
        self.load_bank(self.bank_file.get())

    # noinspection PyMethodMayBeStatic
    def load_bank(self, path):
        instruments.clear()
        instruments.add_file(path)
        self._convert_song()

    def reload_song(self):
        self.toolbar.save_button['state'] = tk.DISABLED
        self._midi_song = None
        if self.song_file.get():
            self._midi_song = MidiSongFile.load_file(self.song_file.get())
            self._convert_song()

    def _convert_song(self):
        self.player.stop()
        self.toolbar.save_button['state'] = tk.DISABLED
        self._adlib_song = None
        try:
            if self._midi_song and self.filetype.get():
                self._adlib_song = AdlibSongFile.convert_from(self._midi_song, self.filetype.get())
                self.toolbar.save_button['state'] = tk.NORMAL
            self.player.set_song(self._adlib_song)
        except ValueError as ex:
            logging.error(ex)
            self._adlib_song = None

    def toggle_play(self):
        if self.player.state == PlayerState.PLAYING:
            self.player.stop()
        else:
            self.player.play()

    def save_imf(self):
        dir_path = os.path.dirname(self.song_file.get()) if self.song_file.get() else None
        file_basename = os.path.splitext(os.path.basename(self.song_file.get()))[0] if self.song_file else None
        options = {
            'defaultextension': '.imf',
            'initialdir': dir_path,
            'initialfile': file_basename + ".imf",
            'parent': self,
            'filetypes': [("IMF file", ".imf")],
            'title': "Save an IMF file"
        }
        dst_song = filedialog.asksaveasfilename(**options)
        if dst_song:
            self._adlib_song.save_file(dst_song)  # , filetype=self.filetype)

    def close_window(self):
        self._settings.close()
        self.player.close()
        self.destroy()
        self.parent.quit()


def main():
    def center_window(toplevel):
        toplevel.update_idletasks()
        x = (toplevel.winfo_screenwidth() - toplevel.winfo_width()) // 2
        y = (toplevel.winfo_screenheight() - toplevel.winfo_height()) // 2
        toplevel.geometry(f"+{x}+{y}")
        # toplevel.update()
    root = tk.Tk()
    root.resizable(False, False)
    root.title(f'PyImfCreator {__version__}')
    root.style = ttk.Style()
    root.style.theme_use("vista" if platform.system() == "Windows" else "clam")
    app = MainApplication(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.protocol("WM_DELETE_WINDOW", app.close_window)
    center_window(root)
    root.mainloop()


if __name__ == "__main__":
    main()

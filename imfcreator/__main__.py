import logging
import os
import threading
import typing
import shelve
import shutil
import subprocess
import platform
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
import imfcreator.instruments as instruments
import imfcreator.resources as resources
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


def run_and_exit(proc_args, on_exit: callable) -> threading.Thread:
    def run_in_thread(_proc_args, _on_exit):
        proc = subprocess.Popen(proc_args)
        proc.wait()
        _on_exit()
    thread = threading.Thread(target=run_in_thread, args=(proc_args, on_exit))
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
        padding = {"padx": 5, "pady": 5}
        # File type row.
        row = 0
        ttk.Label(self, text="Output File Type:").grid(row=row, column=0, sticky=tk.W, **padding)
        self.filetype_combo = ttk.Combobox(self,
                                           justify="left",
                                           state="readonly",
                                           values=[filetype.description for filetype in _ADLIB_FILETYPES],
                                           height=8,
                                           width=70)
        self.filetype_combo.bind("<<ComboboxSelected>>",
                                 lambda event:
                                 parent.set_filetype(_ADLIB_FILETYPES[self.filetype_combo.current()].name))
        self.filetype_combo.grid(row=row, column=1, sticky=tk.W, **padding)
        # Current song file row.
        row += 1
        ttk.Label(self, text="Current Song:").grid(row=row, column=0, sticky=tk.W, **padding)
        self.song_label = ttk.Label(self,
                                    justify=tk.LEFT,
                                    width=70,
                                    relief=tk.SUNKEN)
        self.song_label.grid(row=row, column=1, sticky=tk.W, **padding)
        # Current bank file row.
        row += 1
        ttk.Label(self, text="Current Bank:").grid(row=row, column=0, sticky=tk.W, **padding)
        self.bank_label = ttk.Label(self,
                                    justify=tk.LEFT,
                                    width=70,
                                    relief=tk.SUNKEN)
        self.bank_label.grid(row=row, column=1, sticky=tk.W, **padding)

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
        self.play_button["state"] = tk.DISABLED
        self.save_button = create_button("Save", "save.gif", parent.save_imf)
        self.save_button["state"] = tk.DISABLED

        self.play_image = resources.get_image("play.gif")
        self.stop_image = resources.get_image("stop.gif")
        parent.player.onstatechanged.add_handler(self._on_player_state_changed)

    def _on_player_state_changed(self, state):
        if state == PlayerState.PLAYING:
            self.play_button.image = self.stop_image
        elif state == PlayerState.STOPPED:
            self.play_button.image = self.play_image
        # TODO Add pausing?
        self.play_button["image"] = self.play_button.image


class BankEditor:
    def __init__(self, parent: "MainApplication"):
        self.parent = parent
        self._observer = None  # type: typing.Optional[Observer]
        self._thread = None  # type: typing.Optional[threading.Thread]
        # self._reload_timer = None  # type: typing.Optional[threading.Timer]
        self._reload_timer = threading.Timer(0.2, self.parent.reload_bank)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def executable(self) -> str:
        # TODO: Add an option to manually specify a path to Bank Editor executable when it can't be find automatically
        return shutil.which("opl3_bank_editor", path="./opl3-bank-editor")

    def _close(self):
        if self._observer:
            self._observer.stop()
            self._observer = None
        self._thread = None

    def open(self):
        editor = self.executable
        if editor is None:
            messagebox.showwarning("OPL3 Bank Editor Not Found",
                                   "Could not run opl3_bank_editor.  Please install it and try again.\n"
                                   "It can be downloaded from:\n"
                                   "https://github.com/Wohlstand/OPL3BankEditor", parent=self.parent)
        elif self._observer is None:
            # Setup file modify watcher (after saving of bank file by Bank Editor
            # a reload of bank and music files should happen automatically)
            bank_file = self.parent.bank_file.get()
            # handler = BankEditor.FileEventHandler(self.parent, bank_file)
            handler = PatternMatchingEventHandler(patterns=[bank_file], ignore_directories=True)

            def start_reload_timer(event):
                if not self._reload_timer.is_alive():
                    self._reload_timer.start()

            # Multiple events can fire quickly, so use a timer to reload only once.
            handler.on_modified = start_reload_timer  # lambda event: self.parent.reload_bank()
            self._observer = Observer()
            self._observer.schedule(handler, path=os.path.split(bank_file)[0])
            self._observer.start()
            # Start Bank Editor
            self._thread = run_and_exit([editor, bank_file], self._close)
        else:
            messagebox.showwarning("OPL3 Bank EditorAlready Open",
                                   "The instruments editor is already running.", parent=self.parent)

    # class FileEventHandler(PatternMatchingEventHandler):
    #     def __init__(self, parent: "MainApplication", filename: str):
    #         super().__init__(patterns=[filename], ignore_directories=True)
    #         self.parent = parent
    #
    #     def on_modified(self, event):
    #         self.parent.reload_bank()


class Settings:
    def __init__(self, parent):
        self._db = shelve.open("settings", writeback=True)

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
        # self.tk.call("wm", "iconbitmap", self._w, "-default", os.path.join(Resources.PATH, "icon.ico"))
        # Define variables
        self._adlib_song = None  # type: typing.Optional[AdlibSongFile]
        self._midi_song = None  # type: typing.Optional[MidiSongFile]
        self.filetype = tk.StringVar()
        self.song_file = tk.StringVar()
        self.bank_file = tk.StringVar()
        self.filetype.trace_add("write", lambda *_: self._convert_song())
        self.song_file.trace_add("write", lambda *_: self.reload_song())
        self.bank_file.trace_add("write", lambda *_: self.reload_bank())
        # Create the UI
        self.player = AdlibPlayer()
        self.menubar = Menu(self)
        self.toolbar = ToolBar(self)
        self.infoframe = InfoFrame(self)
        parent["menu"] = self.menubar
        self.toolbar.pack(side=tk.TOP, anchor=tk.W)
        self.infoframe.pack(side=tk.TOP, anchor=tk.W)
        self._settings = Settings(self)
        self._bank_editor = BankEditor(self)
        self.update()

    def edit_instruments(self):
        self._bank_editor.open()

    def set_filetype(self, filetype):
        self.filetype.set(filetype)

    def open_bank_file(self):
        dir_path = os.path.dirname(self.bank_file.get()) if self.bank_file.get() else None
        bank = filedialog.askopenfilename(title="Open an instruments bank file",
                                          # TODO build filetypes list from plugins
                                          filetypes=(
                                              ("Bank files", "*.op2 *.wopl *.OP2 *.WOPL"),
                                              ("all files", "*.*")
                                          ),
                                          parent=self,
                                          initialdir=dir_path)
        if bank:
            self.bank_file.set(bank)
            # self.load_bank(self.bank_file.get())
            # self.reload_song()

    def open_music_file(self):
        dir_path = os.path.dirname(self.song_file.get()) if self.song_file.get() else None
        song = filedialog.askopenfilename(title="Open a music file (MIDI or IMF)",
                                          # TODO build filetypes list from plugins
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

    def load_bank(self, path):
        instruments.clear()
        instruments.add_file(path)
        self._convert_song()

    def reload_song(self):
        self.toolbar.play_button["state"] = tk.DISABLED
        self.toolbar.save_button["state"] = tk.DISABLED
        self._midi_song = None
        if self.song_file.get():
            self._midi_song = MidiSongFile.load_file(self.song_file.get())
            self._convert_song()

    def _convert_song(self):
        self.player.stop()
        self.toolbar.play_button["state"] = tk.DISABLED
        self.toolbar.save_button["state"] = tk.DISABLED
        self._adlib_song = None
        try:
            if self._midi_song and self.filetype.get():
                self._adlib_song = AdlibSongFile.convert_from(self._midi_song, self.filetype.get())
                self.toolbar.play_button["state"] = tk.NORMAL
                self.toolbar.save_button["state"] = tk.NORMAL
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
            "defaultextension": ".imf",
            "initialdir": dir_path,
            "initialfile": file_basename + ".imf",
            "parent": self,
            # TODO build filetypes list from plugins
            "filetypes": [("IMF file", ".imf")],
            "title": "Save an IMF file"
        }
        dst_song = filedialog.asksaveasfilename(**options)
        if dst_song:
            self._adlib_song.save_file(dst_song)  # , filetype=self.filetype)

    def close_window(self):
        if self._bank_editor.is_alive():
            messagebox.showwarning("OPL3 Bank Editor Open", "Please close opl3_bank_editor first.", parent=self)
            return
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
    root.title(f"PyImfCreator {__version__}")
    root.style = ttk.Style()
    root.style.theme_use("vista" if platform.system() == "Windows" else "clam")
    app = MainApplication(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.protocol("WM_DELETE_WINDOW", app.close_window)
    center_window(root)
    root.mainloop()


if __name__ == "__main__":
    main()

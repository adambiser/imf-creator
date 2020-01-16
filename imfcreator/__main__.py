import logging
import os
import threading
import typing
import shelve
import shutil
import subprocess
import platform
from tkinter import PhotoImage
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
import imfcreator.instruments as instruments
import imfcreator.resources as resources
from imfcreator.plugins import AdlibSongFile, MidiSongFile, InstrumentFile, load_plugins
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
load_plugins()
_ADLIB_FILETYPES = AdlibSongFile.get_filetypes()
_MIDI_FILETYPES = MidiSongFile.get_filetypes()
_INSTRUMENT_FILETYPES = InstrumentFile.get_filetypes()


def run_and_exit(args, on_exit_method: callable) -> threading.Thread:
    def run_in_thread(_args, _on_exit_method):
        proc = subprocess.Popen(args)
        proc.wait()
        _on_exit_method()
    thread = threading.Thread(target=run_in_thread, args=(args, on_exit_method))
    thread.start()
    # returns immediately after the thread starts
    return thread


def is_windows() -> bool:
    return platform.system() == "Windows"


class Menu(tk.Menu):
    def __init__(self, parent: "MainApplication", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        def create_menu(label):
            menu = tk.Menu(self, tearoff=0)
            self.add_cascade(label=label, menu=menu)
            return menu

        self.file_menu = create_menu("File")
        self.file_menu.add_command(label="Open Song File", command=parent.open_midi_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Select Bank File", command=parent.open_bank_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=parent.close_window)

        self.tools_menu = create_menu("Tools")
        instrument_editor_label = "Open Instrument Editor"
        self.tools_menu.add_command(label=instrument_editor_label, command=parent.bank_editor.open, state=tk.DISABLED)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="Select Instrument Editor", command=parent.bank_editor.select_path)

        def monitor_bank_editor_path(menu, index, var):
            def update_menu_state(*_):
                menu.entryconfig(index, state=tk.NORMAL if os.path.isfile(var.get()) else tk.DISABLED)
            update_menu_state()
            var.trace_add("write", update_menu_state)

        monitor_bank_editor_path(self.tools_menu, instrument_editor_label, parent.settings.bank_editor_path)

        # self.options_menu = create_menu("Options")
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
        # self.options_menu.add_command(label="Select bank file", command=parent.open_bank_file)
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

        monitor_filetype_variable(self.filetype_combo, parent.settings.filetype)

        def monitor_file_variable(label, file_var):
            def update_file_label(*_):
                label["text"] = os.path.basename(file_var.get())
            update_file_label()
            file_var.trace_add("write", update_file_label)

        monitor_file_variable(self.song_label, parent.settings.song_file)
        monitor_file_variable(self.bank_label, parent.settings.bank_file)


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
        self.open_music_button = create_button("Open Music File", "song.gif", parent.open_midi_file)
        self.play_button = create_button("Play", "play.gif", parent.toggle_play)
        self.play_button["state"] = tk.DISABLED
        self.save_button = create_button("Save", "save.gif", parent.save_adlib_song)
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


class FileModifiedObserver(Observer):
    def __init__(self, parent, filename, on_modified):
        super().__init__()
        self.parent = parent
        handler = FileModifiedObserver.FileModifiedEventHandler(filename, on_modified)
        self.schedule(handler, path=os.path.split(filename)[0])
        self.start()

    class FileModifiedEventHandler(PatternMatchingEventHandler):
        def __init__(self, filename: str, on_modified: callable):
            super().__init__(patterns=[filename], ignore_directories=True)
            self._on_modified = on_modified
            self._reload_timer = None  # type: typing.Optional[threading.Timer]

        def on_modified(self, event):
            if self._reload_timer and not self._reload_timer.is_alive():
                self._reload_timer = None
            if not self._reload_timer:
                self._reload_timer = threading.Timer(0.2, self._on_modified)
                self._reload_timer.start()


class BankEditor:
    def __init__(self, parent: "MainApplication"):
        self.parent = parent
        self._observer = None  # type: typing.Optional[Observer]
        self._thread = None  # type: typing.Optional[threading.Thread]

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def path(self) -> str:
        path = self.parent.settings.bank_editor_path.get()
        if os.path.isfile(path):
            return path
        path = shutil.which("opl3_bank_editor")
        # Store to notify any watchers of the change..
        self.parent.settings.bank_editor_path.set(path)
        return path

    def select_path(self):
        dir_path = os.path.dirname(self.parent.settings.bank_editor_path.get()) \
            if self.parent.settings.bank_editor_path.get() else None
        path = filedialog.askdirectory(title="Choose the Location of the OPL3 Bank Editor",
                                       parent=self.parent,
                                       initialdir=dir_path)
        if path:
            path = shutil.which("opl3_bank_editor", path=path)
            if not path:
                messagebox.showwarning("OPL3 Bank Editor Not Found",
                                       "Could not find opl3_bank_editor.  Please install it and try again.\n"
                                       "It can be downloaded from:\n"
                                       "https://github.com/Wohlstand/OPL3BankEditor", parent=self.parent)
        else:
            path = None
        self.parent.settings.bank_editor_path.set(path)
        return path

    def _close(self):
        if self._observer:
            self._observer.stop()
            self._observer = None
        self._thread = None

    def open(self):
        editor_path = self.path
        if not editor_path:
            editor_path = self.select_path()
        if not editor_path:
            return
        elif self._observer is None:
            # Start watching the bank file for modifications, too, and automatically reload.
            bank_file = self.parent.settings.bank_file.get()
            self._observer = FileModifiedObserver(self.parent, bank_file, self.parent.reload_bank)
            self._thread = run_and_exit([editor_path, bank_file], self._close)
        else:
            messagebox.showwarning("OPL3 Bank EditorAlready Open",
                                   "The instruments editor is already running.", parent=self.parent)


class Settings:
    _DEFAULT_VALUES = {
        "bank_file": "genmidi/GENMIDI.OP2"
    }

    def __init__(self):
        self._db = shelve.open("settings", writeback=True)
        self.bank_file = tk.StringVar()
        self.song_file = tk.StringVar()
        self.filetype = tk.StringVar()
        self.bank_editor_path = tk.StringVar()

    def load(self):
        def monitor_variable(settings_key: str, default):
            def write_setting(*_):
                self._db[settings_key] = var.get()

            var = getattr(self, settings_key)
            var.set(self._db.get(settings_key, default))
            var.trace_add("write", write_setting)

        for var_name in [k for k, v in self.__dict__.items() if isinstance(v, tk.Variable)]:
            monitor_variable(var_name, Settings._DEFAULT_VALUES.get(var_name, None))
        # monitor_variable(parent.bank_file, "bank_file", "genmidi/GENMIDI.OP2")
        # monitor_variable(parent.song_file, "song_file", "")
        # monitor_variable(parent.filetype, "filetype", "")
        # monitor_variable(parent.bank_editor_path, "bank_editor_path", "")

    def close(self):
        self._db.sync()
        self._db.close()
        del self._db


class MainApplication(ttk.Frame):
    def __init__(self, parent: tk.Tk, *_, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.parent.iconphoto(True, resources.get_image("imfcreator.png"))
        # Define variables
        self._adlib_song = None  # type: typing.Optional[AdlibSongFile]
        self._midi_song = None  # type: typing.Optional[MidiSongFile]
        self.settings = Settings()
        self.settings.filetype.trace_add("write", lambda *_: self._convert_song())
        self.settings.song_file.trace_add("write", lambda *_: self.reload_midi_song())
        self.settings.bank_file.trace_add("write", lambda *_: self.reload_bank())
        # Create the UI
        self.player = AdlibPlayer()
        self.bank_editor = BankEditor(self)
        self.menubar = Menu(self)
        self.toolbar = ToolBar(self)
        self.infoframe = InfoFrame(self)
        parent["menu"] = self.menubar
        self.toolbar.pack(side=tk.TOP, anchor=tk.W)
        self.infoframe.pack(side=tk.TOP, anchor=tk.W)
        self.settings.load()
        # self.update()

    def set_filetype(self, filetype):
        self.settings.filetype.set(filetype)

    def open_bank_file(self):
        filetypes = " ".join(f"*.{ft.default_extension.lower()} *.{ft.default_extension.upper()}"
                             for ft in _INSTRUMENT_FILETYPES)
        dir_path = os.path.dirname(self.settings.bank_file.get()) if self.settings.bank_file.get() else None
        bank = filedialog.askopenfilename(title="Open an instruments bank file",
                                          filetypes=(
                                              ("Supported Instrument Files", filetypes),
                                              ("All Files", "*.*")
                                          ),
                                          parent=self,
                                          initialdir=dir_path)
        if bank:
            self.settings.bank_file.set(bank)

    def reload_bank(self):
        self.load_bank(self.settings.bank_file.get())

    def load_bank(self, path):
        instruments.clear()
        instruments.add_file(path)
        self._convert_song()

    def open_midi_file(self):
        filetypes = [("Supported Music Files",
                      " ".join(f"*.{ft.default_extension.lower()} *.{ft.default_extension.upper()}"
                               for ft in _MIDI_FILETYPES))]
        filetypes.extend([(ft.description, f"*.{ft.default_extension.lower()} *.{ft.default_extension.upper()}")
                          for ft in _MIDI_FILETYPES])
        filetypes.append(("All Files", "*.*"))
        dir_path = os.path.dirname(self.settings.song_file.get()) if self.settings.song_file.get() else None
        song = filedialog.askopenfilename(title="Open a music file (MIDI or IMF)",
                                          filetypes=tuple(filetypes),
                                          parent=self,
                                          initialdir=dir_path)
        if song:
            self.settings.song_file.set(song)

    def reload_midi_song(self):
        self.toolbar.play_button["state"] = tk.DISABLED
        self.toolbar.save_button["state"] = tk.DISABLED
        self._midi_song = None
        if self.settings.song_file.get():
            self._midi_song = MidiSongFile.load_file(self.settings.song_file.get())
            self._convert_song()

    def _convert_song(self):
        self.player.stop()
        self.toolbar.play_button["state"] = tk.DISABLED
        self.toolbar.save_button["state"] = tk.DISABLED
        self._adlib_song = None
        try:
            if self._midi_song and self.settings.filetype.get():
                self._adlib_song = AdlibSongFile.convert_from(self._midi_song, self.settings.filetype.get())
                self.toolbar.play_button["state"] = tk.NORMAL
                self.toolbar.save_button["state"] = tk.NORMAL
            self.player.set_song(self._adlib_song)
        except ValueError as ex:
            logging.error(ex)
            self._adlib_song = None

    def save_adlib_song(self):
        dir_path = os.path.dirname(self.settings.song_file.get()) if self.settings.song_file.get() else None
        file_basename = os.path.splitext(os.path.basename(self.settings.song_file.get()))[0] \
            if self.settings.song_file else None
        options = {
            "title": "Save Adlib File",
            # TODO build filetypes list from plugins
            "filetypes": [("IMF file", ".imf")],
            "defaultextension": ".imf",
            "initialdir": dir_path,
            "initialfile": file_basename + ".imf",
            "parent": self
        }
        dst_song = filedialog.asksaveasfilename(**options)
        if dst_song:
            self._adlib_song.save_file(dst_song)  # , filetype=self.filetype)

    def toggle_play(self):
        if self.player.state == PlayerState.PLAYING:
            self.player.stop()
        else:
            self.player.play()

    def close_window(self):
        if self.bank_editor.is_alive():
            messagebox.showwarning("OPL3 Bank Editor Open", "Please close opl3_bank_editor first.", parent=self)
            return
        self.settings.close()
        self.player.close()
        self.destroy()
        self.parent.quit()


def main():
    def center_window(toplevel):
        # toplevel.update_idletasks()
        toplevel.eval(f"tk::PlaceWindow {toplevel.winfo_toplevel()} center")
    root = tk.Tk()
    root.resizable(False, False)
    root.title(f"PyImfCreator {__version__}")
    root.style = ttk.Style()
    root.style.theme_use("vista" if is_windows() else "clam")
    app = MainApplication(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.protocol("WM_DELETE_WINDOW", app.close_window)
    center_window(root)
    root.mainloop()


if __name__ == "__main__":
    main()

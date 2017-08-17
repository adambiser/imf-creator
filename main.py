from imfcreator.mainapplication import MainApplication
from imfcreator.imf.player import ImfPlayer
from imfcreator.signal import Signal
import inspect
import time
import Tix as tix
from imfcreator.midi.reader import MidiReader


# class Signal:
#     """A simple event system.
#
#     Based on: https://stackoverflow.com/posts/35957226/revisions
#     """
#     def __init__(self, **args):
#         self._args = args
#         self._argnames = set(args.keys())
#         self._listeners = []
#
#     def _args_string(self):
#         return ", ".join(sorted(self._argnames))
#
#     def __iadd__(self, listener):
#         args = inspect.getargspec(listener).args
#         if set(n for n in args) != self._argnames:
#             raise ValueError("Listener must have these arguments: {}".format(self._args_string()))
#         self._listeners.append(listener)
#         return self
#
#     def __isub__(self, listener):
#         self._listeners.remove(listener)
#         return self
#
#     def __call__(self, *args, **kwargs):
#         if args or set(kwargs.keys()) != self._argnames:
#             raise ValueError("This Signal requires these arguments: {}".format(self._args_string()))
#         for listener in self._listeners:
#             listener(**kwargs)


def listener1(x, y):
    print("method listener: {}, {}".format(x, y))


def listener2(x, y):
    print("lambda listener: {}, {}".format(x, y))

def listener3():
    print("no args")


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

def testsignals():
    changed = Signal(x=int, y=int)
    changed += listener1
    changed += lambda x, y: listener2(x, y)
    changed(x=23, y=13)
    changed = Signal()
    changed += listener3
    changed()

def miditest():
    reader = MidiReader()
    reader.load("testfmt0.mid")

# main()
# testsignals()
miditest()
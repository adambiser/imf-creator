import logging as _logging
import typing as _typing
import imfcreator.midi as _midi
from collections import namedtuple as _namedtuple
# from functools import wraps
from . import MidiSongFile
from imfcreator.signal import Signal


ActiveNote = _namedtuple("ActiveNote", ["given_note", "velocity", "adjusted_note"])
_CONTROLLER_HANDLERS = {}


def calculate_msb_lsb(msb: int, lsb: int) -> int:
    assert msb & ~0x7f == 0
    assert lsb & ~0x7f == 0
    return (msb << 7) + lsb


def _controller_handler(*controllers):
    def _decorator(f):
        # @wraps(f)
        def _wrapper(self, controller):
            return f(self, controller)

        for cc in controllers:
            _CONTROLLER_HANDLERS[cc] = _wrapper
        return _wrapper
    return _decorator


class MidiEngine:
    """A class to process song events in chronological order.

    AdlibSongFile should create an instance, add signal handlers, and call start to process the events.

    The engine's channels process and store controller values and notify any handler of changes.

    Channel Controllers, Properties, and Range
     * Bank Select - `bank` - 0 to 16383
     * Modulation Wheel - `modulation_wheel` - 0.0 to 1.0
     * Foot Pedal - `foot_pedal` - 0.0 to 1.0
     * Portamento Time - `portamento_time` - 0.0 to 1.0
     * Volume - `volume` - 0.0 to 1.0
     * Balance - `balance` - -1.0 to 1.0 where -1.0 is hard left, 0.0 is center, 1.0 is is hard right
     * Pan - `pan` - -1.0 to 1.0 where -1.0 is hard left, 0.0 is center, 1.0 is is hard right
     * Expression - `expression` - 0.0 to 1.0
    """

    PERCUSSION_CHANNEL = 9
    GM_DRUM_BANK = calculate_msb_lsb(120, 0)
    XG_DRUM_BANK = calculate_msb_lsb(127, 0)
    _DRUM_BANKS = [GM_DRUM_BANK, XG_DRUM_BANK]

    def __init__(self, song: MidiSongFile):
        song.sort()
        self._song = song
        self.channels = [MidiChannelInfo(ch) for ch in range(16)]
        # Channel event handlers.
        self.on_note_on = Signal(event_time=float, track=int, channel=int, note=int, velocity=int)
        self.on_note_off = Signal(event_time=float, track=int, channel=int, note=int, velocity=int)
        self.on_polyphonic_key_pressure = Signal(event_time=float, track=int, channel=int, note=int, pressure=int)
        self.on_controller_change = Signal(event_time=float, track=int, channel=int, controller=_midi.ControllerType,
                                           value=int)
        self.on_program_change = Signal(event_time=float, track=int, channel=int, program=int)
        self.on_channel_key_pressure = Signal(event_time=float, track=int, channel=int, pressure=int)
        self.on_pitch_bend = Signal(event_time=float, track=int, channel=int, value=float)
        # Sysex event handlers.
        self.on_f0_sysex = Signal(event_time=float, track=int, data=bytes)
        self.on_f7_sysex = Signal(event_time=float, track=int, data=bytes)
        # Meta event handlers.
        self.on_meta_sequence_number = Signal(event_time=float, track=int, number=int)
        self.on_meta_text = Signal(event_time=float, track=int, meta_type=_midi.MetaType, text=bytes)
        self.on_meta_channel_prefix = Signal(event_time=float, track=int, channel=int)
        self.on_meta_port = Signal(event_time=float, track=int, port=int)
        self.on_end_of_track = Signal(event_time=float, track=int)
        self.on_tempo_change = Signal(event_time=float, track=int, bpm=float)
        self.on_smpte_offset = Signal(event_time=float, track=int, hours=int, minutes=int, seconds=int, frames=int,
                                      fractional_frames=int)
        self.on_time_signature = Signal(event_time=float, track=int, numerator=int, denominator=int,
                                        midi_clocks_per_metronome_tick=int, number_of_32nd_notes_per_beat=int)
        self.on_key_signature = Signal(event_time=float, track=int, key=str)
        self.on_sequencer_specific = Signal(event_time=float, track=int, data=bytes)
        self.on_end_of_song = Signal(event_time=float)

    def is_percussion_channel(self, channel: int) -> bool:
        return channel == MidiEngine.PERCUSSION_CHANNEL or self.channels[channel].bank in MidiEngine._DRUM_BANKS

    def start(self):
        for song_event in self._song.events:
            if song_event.type == _midi.EventType.NOTE_OFF or (
                    song_event.type == _midi.EventType.NOTE_ON and song_event["velocity"] == 0):
                self.on_note_off(event_time=song_event.time,
                                 track=song_event.track,
                                 channel=song_event.channel,
                                 note=song_event["note"],
                                 velocity=song_event["velocity"])
            elif song_event.type == _midi.EventType.NOTE_ON:
                self.on_note_on(event_time=song_event.time,
                                track=song_event.track,
                                channel=song_event.channel,
                                note=song_event["note"],
                                velocity=song_event["velocity"])
            elif song_event.type == _midi.EventType.POLYPHONIC_KEY_PRESSURE:
                self.on_polyphonic_key_pressure(event_time=song_event.time,
                                                track=song_event.track,
                                                channel=song_event.channel,
                                                note=song_event["note"],
                                                pressure=song_event["pressure"])
            elif song_event.type == _midi.EventType.CONTROLLER_CHANGE:
                controller = _midi.ControllerType(song_event["controller"])  # type: _midi.ControllerType
                value = song_event["value"]
                self.channels[song_event.channel].set_controller_value(controller, value)
                self.on_controller_change(event_time=song_event.time,
                                          track=song_event.track,
                                          channel=song_event.channel,
                                          controller=controller,
                                          value=value)
            elif song_event.type == _midi.EventType.PROGRAM_CHANGE:
                # Only trigger the signal if the value changes.
                if self.channels[song_event.channel].instrument != song_event["program"]:
                    self.channels[song_event.channel].instrument = song_event["program"]
                    self.on_program_change(event_time=song_event.time,
                                           track=song_event.track,
                                           channel=song_event.channel,
                                           program=song_event["program"])
            elif song_event.type == _midi.EventType.CHANNEL_KEY_PRESSURE:
                # Only trigger the signal if the value changes.
                if self.channels[song_event.channel].key_pressure != song_event["pressure"]:
                    self.channels[song_event.channel].key_pressure = song_event["pressure"]
                    self.on_channel_key_pressure(event_time=song_event.time,
                                                 track=song_event.track,
                                                 channel=song_event.channel,
                                                 pressure=song_event["pressure"])
            elif song_event.type == _midi.EventType.PITCH_BEND:
                # Only trigger the signal if the value changes.
                if self.channels[song_event.channel].pitch_bend != song_event["value"]:
                    self.channels[song_event.channel].pitch_bend = song_event["value"]
                    self.on_pitch_bend(event_time=song_event.time,
                                       track=song_event.track,
                                       channel=song_event.channel,
                                       value=song_event["value"])
            elif song_event.type == _midi.EventType.F0_SYSEX:
                self.on_f0_sysex(event_time=song_event.time,
                                 track=song_event.track,
                                 data=song_event["data"])
            elif song_event.type == _midi.EventType.F7_SYSEX:
                self.on_f7_sysex(event_time=song_event.time,
                                 track=song_event.track,
                                 data=song_event["data"])
            elif song_event.type == _midi.EventType.META:
                meta_type = song_event["meta_type"]
                if meta_type == _midi.MetaType.SEQUENCE_NUMBER:
                    self.on_meta_sequence_number(event_time=song_event.time,
                                                 track=song_event.track,
                                                 number=song_event["number"])
                elif meta_type in [_midi.MetaType.TEXT_EVENT,
                                   _midi.MetaType.COPYRIGHT,
                                   _midi.MetaType.TRACK_NAME,
                                   _midi.MetaType.INSTRUMENT_NAME,
                                   _midi.MetaType.LYRIC,
                                   _midi.MetaType.MARKER,
                                   _midi.MetaType.CUE_POINT,
                                   _midi.MetaType.PROGRAM_NAME,
                                   _midi.MetaType.DEVICE_NAME]:
                    self.on_meta_text(event_time=song_event.time,
                                      track=song_event.track,
                                      meta_type=meta_type,
                                      text=song_event["text"])
                elif meta_type == _midi.MetaType.CHANNEL_PREFIX:
                    self.on_meta_channel_prefix(event_time=song_event.time,
                                                track=song_event.track,
                                                channel=song_event["channel"])
                elif meta_type == _midi.MetaType.PORT:
                    self.on_meta_port(event_time=song_event.time,
                                      track=song_event.track,
                                      port=song_event["port"])
                elif meta_type == _midi.MetaType.END_OF_TRACK:
                    self.on_end_of_track(event_time=song_event.time,
                                         track=song_event.track)
                elif meta_type == _midi.MetaType.SET_TEMPO:
                    self.on_tempo_change(event_time=song_event.time,
                                         track=song_event.track,
                                         bpm=song_event["bpm"])
                elif meta_type == _midi.MetaType.SMPTE_OFFSET:
                    self.on_smpte_offset(event_time=song_event.time,
                                         track=song_event.track,
                                         hours=song_event["hours"],
                                         minutes=song_event["minutes"],
                                         seconds=song_event["seconds"],
                                         frames=song_event["frames"],
                                         fractional_frames=song_event["fractional_frames"])
                elif meta_type == _midi.MetaType.TIME_SIGNATURE:
                    self.on_time_signature(event_time=song_event.time,
                                           track=song_event.track,
                                           numerator=song_event["numerator"],
                                           denominator=song_event["denominator"],
                                           midi_clocks_per_metronome_tick=song_event["midi_clocks_per_metronome_tick"],
                                           number_of_32nd_notes_per_beat=song_event["number_of_32nd_notes_per_beat"])
                elif meta_type == _midi.MetaType.KEY_SIGNATURE:
                    self.on_key_signature(event_time=song_event.time,
                                          track=song_event.track,
                                          key=song_event["key"])
                elif meta_type == _midi.MetaType.SEQUENCER_SPECIFIC:
                    self.on_sequencer_specific(event_time=song_event.time,
                                               track=song_event.track,
                                               data=song_event["data"])
                else:
                    _logging.error(f"Unexpected meta event type: {meta_type}")
            else:
                _logging.error(f"Unexpected MIDI event type: {song_event.type}")
        last_event_time = max([event.time for event in self._song.events])
        self.on_end_of_song(event_time=last_event_time)


class MidiChannelInfo:
    # Controller info:
    # http://www.ccarh.org/courses/253/handout/controllers/controllers.html
    # Values are (MSB, LSB)
    PITCH_BEND_SENSITIVITY_RPN = (0, 0)
    FINE_TUNING_RPN = (0, 1)
    COARSE_TUNING_RPN = (0, 2)
    TUNING_PROGRAM_SELECT_RPN = (0, 3)
    TUNING_BANK_SELECT_RPN = (0, 4)
    NULL_RPN = (127, 127)

    def __init__(self, number):
        self.number = number
        # Set by the MidiEngine.
        self.instrument = None
        self.pitch_bend = 0.0
        self.key_pressure = 127
        self.active_notes = []  # type: _typing.List[ActiveNote]
        # Controller value cache.
        self._controllers = [0] * 128
        self._in_rpn_data = None
        # http://www.philrees.co.uk/nrpnq.htm
        # Values are [MSB, LSB]
        self.rpn = {
            MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN: [0, 0],  # MSB = semitones, LSB = cents
            MidiChannelInfo.FINE_TUNING_RPN: [0, 0],  # 8192 = Center/A440, 0 = 1 semitone down, 16383 = 1 semitone up
            MidiChannelInfo.COARSE_TUNING_RPN: [0, 0],  # MSB = semitones; 64 = center, LSB = unused
            MidiChannelInfo.TUNING_PROGRAM_SELECT_RPN: [0, 0],  # MIDI Tuning Standard.  Not widely implemented.
            MidiChannelInfo.TUNING_BANK_SELECT_RPN: [0, 0],  # MIDI Tuning Standard.  Not widely implemented.
        }
        # Calculated controller values.
        self._bank = 0
        self._modulation_wheel = 0.0
        self._breath_controller = 0.0
        self._foot_controller = 0.0
        self._portamento_time = 0.0
        self._volume = 0.0
        self._balance = 0.0
        self._pan = 0.0
        self._expression = 0.0
        # Calculated RPN values
        self._pitch_bend_sensitivity = 0.0
        self._tuning = 0.0  # Combines FINE_TUNING_RPN and COARSE_TUNING_RPN.
        self.reset_controllers()

    def reset_controllers(self):
        """Sets controllers back to their defaults."""
        # Clear all controller values.
        for cc in range(len(self._controllers)):
            self._controllers[cc] = 0
        self._bank = 0
        self._modulation_wheel = 0.0
        self._breath_controller = 0.0
        self._foot_controller = 0.0
        self._portamento_time = 0.0
        self._volume = 0.0
        self._balance = 0.0
        self._pan = 0.0
        self._expression = 0.0
        for key in self.rpn.keys():
            self.set_rpn_value(key, 0, 0)
        # Set controller values to defaults.
        self.set_controller_value(_midi.ControllerType.VOLUME_MSB, 127)
        self.set_controller_value(_midi.ControllerType.BALANCE_MSB, 64)  # center
        self.set_controller_value(_midi.ControllerType.PAN_MSB, 64)  # center
        self.set_controller_value(_midi.ControllerType.XG_BRIGHTNESS, 127)
        self.set_controller_value(_midi.ControllerType.EXPRESSION_MSB, 127)
        self.set_controller_value(_midi.ControllerType.RPN_MSB, 127)
        self.set_controller_value(_midi.ControllerType.RPN_LSB, 127)
        self.set_controller_value(_midi.ControllerType.NRPN_MSB, 127)
        self.set_controller_value(_midi.ControllerType.NRPN_LSB, 127)
        self.set_rpn_value(MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN, 2, 0)  # 2 semitones, 0 cents
        self.set_rpn_value(MidiChannelInfo.FINE_TUNING_RPN, 64, 0)  # Center/A440
        self.set_rpn_value(MidiChannelInfo.COARSE_TUNING_RPN, 64, 0)  # center

    def get_controller_value(self, controller: _midi.ControllerType) -> int:
        """Returns a value from 0 to 127."""
        return self._controllers[controller]

    def set_controller_value(self, controller: _midi.ControllerType, value: int):
        assert 0 <= value <= 127
        self._controllers[controller] = value
        # Check controller handlers.
        if controller in _CONTROLLER_HANDLERS:
            _CONTROLLER_HANDLERS[controller](self, controller)

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.BANK_SELECT_MSB, _midi.ControllerType.BANK_SELECT_LSB)
    def _set_bank(self, controller):
        self._bank = self.calculate_msb_lsb(_midi.ControllerType.BANK_SELECT_MSB, _midi.ControllerType.BANK_SELECT_LSB)

    @property
    def bank(self) -> int:
        return self._bank

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.MODULATION_WHEEL_MSB, _midi.ControllerType.MODULATION_WHEEL_LSB)
    def _set_modulation_wheel(self, controller):
        self._modulation_wheel = _midi.scale_14bit(self.calculate_msb_lsb(_midi.ControllerType.MODULATION_WHEEL_MSB,
                                                                          _midi.ControllerType.MODULATION_WHEEL_LSB))

    @property
    def modulation_wheel(self) -> float:
        return self._modulation_wheel

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.BREATH_CONTROLLER_MSB, _midi.ControllerType.BREATH_CONTROLLER_LSB)
    def _set_breath_controller(self, controller):
        self._breath_controller = _midi.scale_14bit(self.calculate_msb_lsb(_midi.ControllerType.BREATH_CONTROLLER_MSB,
                                                                           _midi.ControllerType.BREATH_CONTROLLER_LSB))

    @property
    def breath_controller(self) -> float:
        return self._breath_controller

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.FOOT_CONTROLLER_MSB, _midi.ControllerType.FOOT_CONTROLLER_LSB)
    def _set_foot_controller(self, controller):
        self._foot_controller = _midi.scale_14bit(self.calculate_msb_lsb(_midi.ControllerType.FOOT_CONTROLLER_MSB,
                                                                         _midi.ControllerType.FOOT_CONTROLLER_LSB))

    @property
    def foot_controller(self) -> float:
        return self._foot_controller

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.PORTAMENTO_TIME_MSB, _midi.ControllerType.PORTAMENTO_TIME_LSB)
    def _set_portamento_time(self, controller):
        self._portamento_time = _midi.scale_14bit(self.calculate_msb_lsb(_midi.ControllerType.PORTAMENTO_TIME_MSB,
                                                                         _midi.ControllerType.PORTAMENTO_TIME_LSB))

    @property
    def portamento_time(self) -> float:
        return self._portamento_time

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.VOLUME_MSB, _midi.ControllerType.VOLUME_LSB)
    def _set_volume(self, controller):
        self._volume = _midi.scale_14bit(self.calculate_msb_lsb(_midi.ControllerType.VOLUME_MSB,
                                                                _midi.ControllerType.VOLUME_LSB))

    @property
    def volume(self) -> float:
        return self._volume

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.BALANCE_MSB, _midi.ControllerType.BALANCE_LSB)
    def _set_balance(self, controller):
        self._balance = _midi.balance_14bit(self.calculate_msb_lsb(_midi.ControllerType.BALANCE_MSB,
                                                                   _midi.ControllerType.BALANCE_LSB))

    @property
    def balance(self) -> float:
        return self._balance

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.PAN_MSB, _midi.ControllerType.PAN_LSB)
    def _set_pan(self, controller):
        self._pan = _midi.balance_14bit(self.calculate_msb_lsb(_midi.ControllerType.PAN_MSB,
                                                               _midi.ControllerType.PAN_LSB))

    @property
    def pan(self) -> float:
        return self._pan

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.EXPRESSION_MSB, _midi.ControllerType.EXPRESSION_LSB)
    def _set_expression(self, controller):
        self._expression = _midi.scale_14bit(self.calculate_msb_lsb(_midi.ControllerType.EXPRESSION_MSB,
                                                                    _midi.ControllerType.EXPRESSION_LSB))

    @property
    def expression(self) -> float:
        return self._expression

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.RPN_MSB, _midi.ControllerType.RPN_LSB)
    def _set_rpn(self, controller):
        assert self._in_rpn_data is None or self._in_rpn_data
        self._in_rpn_data = None if self.get_msb_lsb_values(_midi.ControllerType.RPN_MSB) == MidiChannelInfo.NULL_RPN \
            else True

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.NRPN_MSB, _midi.ControllerType.NRPN_LSB)
    def _set_nrpn(self, controller):
        assert not self._in_rpn_data  # None or False
        self._in_rpn_data = None if self.get_msb_lsb_values(_midi.ControllerType.NRPN_MSB) == MidiChannelInfo.NULL_RPN \
            else False

    @_controller_handler(_midi.ControllerType.DATA_ENTRY_MSB, _midi.ControllerType.DATA_ENTRY_LSB)
    def _set_expression(self, controller):
        # Ignore NRPN data.
        if self._in_rpn_data is None:
            _logging.warning(f"Had {str(controller)} controller outside of RPN or NRPN.")
        elif self._in_rpn_data:
            rpn = self.get_msb_lsb_values(_midi.ControllerType.RPN_MSB)
            self.set_rpn_value(rpn,
                               self._controllers[_midi.ControllerType.DATA_ENTRY_MSB],
                               self._controllers[_midi.ControllerType.DATA_ENTRY_LSB])
            # # byte_index = 0 if controller == _midi.ControllerType.DATA_ENTRY_MSB else 1
            # if controller == _midi.ControllerType.DATA_ENTRY_MSB:
            #     self.set_rpn_value(rpn, msb=value)
            # else:
            #     self.set_rpn_value(rpn, lsb=value)

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.RESET_ALL_CONTROLLERS)
    def _reset_all_controllers(self, controller):
        self.reset_controllers()

    def set_rpn_value(self, rpn: _typing.Tuple[int, int], msb: int = None, lsb: int = None):
        if msb is not None:
            self.rpn[rpn][0] = msb
        if lsb is not None:
            self.rpn[rpn][1] = lsb
        if rpn == MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN:
            semitones, cents = self.rpn[MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN]
            assert cents < 100
            self._pitch_bend_sensitivity = semitones + cents / 100.0
        elif rpn in [MidiChannelInfo.FINE_TUNING_RPN, MidiChannelInfo.COARSE_TUNING_RPN]:
            # semitones, cents = self.rpn[MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN]
            fine_tuning = _midi.scale_14bit(calculate_msb_lsb(*self.rpn[MidiChannelInfo.FINE_TUNING_RPN]))
            coarse_tuning = self.rpn[MidiChannelInfo.COARSE_TUNING_RPN][0] - 64
            self._tuning = coarse_tuning + fine_tuning

    @property
    def pitch_bend_sensitivity(self) -> float:
        return self._pitch_bend_sensitivity

    @property
    def scaled_pitch_bend(self) -> float:
        return self.pitch_bend * self._pitch_bend_sensitivity

    def calculate_msb_lsb(self, msb: _midi.ControllerType, lsb: _midi.ControllerType) -> int:
        assert msb < 32
        assert 32 <= lsb < 63
        return calculate_msb_lsb(self._controllers[msb], self._controllers[lsb])

    def get_msb_lsb_values(self, controller: _midi.ControllerType) -> _typing.Tuple[int, int]:
        """Returns the MSB and LSB values based on the given MSB or LSB controller type as a tuple.
        :except ValueError: when a non-MSB/LSB controller is given
        """
        if controller in [_midi.ControllerType.RPN_MSB, _midi.ControllerType.NRPN_MSB]:
            msb = controller
            lsb = msb - 1
        elif controller in [_midi.ControllerType.RPN_MSB, _midi.ControllerType.NRPN_MSB]:
            lsb = controller
            msb = lsb + 1
        else:
            if controller >= 64:
                raise ValueError("Must be an MSB or LSB controller type.")
            msb = _midi.ControllerType(controller % 32)
            lsb = msb + 32
        return self._controllers[msb], self._controllers[lsb]

    # def add_active_note(self):
    #     pass
    #
    # def get_active_note(self):
    #     pass
    #
    # def remove_active_note(self):
    #     pass


def _event_property(name: str) -> property:
    # noinspection PyProtectedMember
    return property(lambda self: self._data.get(name))


class _ChildSongEvent(_midi.SongEvent):
    @classmethod
    def from_songevent(cls, e: _midi.SongEvent):
        return cls(e.index, e.track, e.time, e.type, e._data, e.channel)


class NoteEvent(_ChildSongEvent):
    # note = property(lambda self: self._data.get("note"))  # type: int
    # velocity = property(lambda self: self._data.get("velocity"))  # type: int
    note = _event_property("note")  # type: int
    # @property
    # def note(self) -> int:
    #     return self["note"]

    @property
    def velocity(self) -> int:
        return self["velocity"]


# class PressureEvent(_ChildSongEvent):
#     @property
#     def note(self) -> int:
#         return self._data.get("note")
#
#     @property
#     def pressure(self) -> int:
#         return self["pressure"]
#
#
# class ControllerChange(_ChildSongEvent):
#     @property
#     def controller(self) -> _midi.ControllerType:
#         return self._data["controller"]
#
#     @property
#     def value(self) -> int:
#         return self["value"]

# self.on_program_change = Signal(event_time=float, track=int, channel=int, program=int)
# self.on_channel_key_pressure = Signal(event_time=float, track=int, channel=int, pressure=int)
# self.on_pitch_bend = Signal(event_time=float, track=int, channel=int, value=float)
# # Sysex event handlers.
# self.on_f0_sysex = Signal(event_time=float, track=int, data=bytes)
# self.on_f7_sysex = Signal(event_time=float, track=int, data=bytes)
# # Meta event handlers.
# self.on_meta_sequence_number = Signal(event_time=float, track=int, number=int)
# self.on_meta_text = Signal(event_time=float, track=int, meta_type=_midi.MetaType, text=bytes)
# self.on_meta_channel_prefix = Signal(event_time=float, track=int, channel=int)
# self.on_meta_port = Signal(event_time=float, track=int, port=int)
# self.on_end_of_track = Signal(event_time=float, track=int)
# self.on_tempo_change = Signal(event_time=float, track=int, bpm=float)
# self.on_smpte_offset = Signal(event_time=float, track=int, hours=int, minutes=int, seconds=int, frames=int,
#                               fractional_frames=int)
# self.on_time_signature = Signal(event_time=float, track=int, numerator=int, denominator=int,
#                                 midi_clocks_per_metronome_tick=int, number_of_32nd_notes_per_beat=int)
# self.on_key_signature = Signal(event_time=float, track=int, key=str)
# self.on_sequencer_specific = Signal(event_time=float, track=int, data=bytes)

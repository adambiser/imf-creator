import logging as _logging
import typing as _typing
import imfcreator.midi as _midi
from functools import wraps
from . import MidiSongFile
from imfcreator.signal import Signal


class ActiveNote(_typing.NamedTuple):
    given_note: int
    velocity: int
    adjusted_note: int


def calculate_msb_lsb(msb: int, lsb: int) -> int:
    assert msb & ~0x7f == 0
    assert lsb & ~0x7f == 0
    return (msb << 7) + lsb


_CONTROLLER_HANDLERS = {}


def _controller_handler(*controllers):
    def _decorator(f):
        @wraps(f)
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

    GM_DRUM_BANK = calculate_msb_lsb(120, 0)
    XG_SFX_BANK = calculate_msb_lsb(126, 0)
    XG_DRUM_BANK = calculate_msb_lsb(127, 0)
    _DRUM_BANKS = [GM_DRUM_BANK, XG_SFX_BANK, XG_DRUM_BANK]

    def __init__(self, song: MidiSongFile):
        song.sort()
        self._song = song
        self.channels = [MidiChannelInfo(ch, song) for ch in range(16)]
        self.on_debug_event = Signal(song_event=_midi.SongEvent)
        # Channel event handlers.
        self.on_note_on = Signal(song_event=NoteEvent)
        self.on_note_off = Signal(song_event=NoteEvent)
        self.on_polyphonic_key_pressure = Signal(song_event=PolyphonicKeyPressureEvent)
        self.on_controller_change = Signal(song_event=ControllerChangeEvent)
        self.on_program_change = Signal(song_event=ProgramChangeEvent)
        self.on_channel_key_pressure = Signal(song_event=ChannelKeyPressureEvent)
        self.on_pitch_bend = Signal(song_event=PitchBendEvent)
        # Sysex event handlers.
        self.on_sysex = Signal(song_event=SysexEvent)
        # Meta event handlers.
        self.on_meta_sequence_number = Signal(song_event=SequenceNumberMetaEvent)
        self.on_meta_text = Signal(song_event=TextMetaEvent)
        self.on_meta_channel_prefix = Signal(song_event=ChannelPrefixMetaEvent)
        self.on_meta_port = Signal(song_event=PortMetaEvent)
        self.on_end_of_track = Signal(song_event=EndOfTrackMetaEvent)
        self.on_tempo_change = Signal(song_event=TempoChangeMetaEvent)
        self.on_smpte_offset = Signal(song_event=SmpteOffsetMetaEvent)
        self.on_time_signature = Signal(song_event=TimeSignatureMetaEvent)
        self.on_key_signature = Signal(song_event=KeySignatureMetaEvent)
        self.on_sequencer_specific = Signal(song_event=SequencerSpecificMetaEvent)
        self.on_end_of_song = Signal(song_event=EndOfSongEvent)

    def is_percussion_channel(self, channel: int) -> bool:
        return channel == self._song.PERCUSSION_CHANNEL or self.channels[channel].bank in MidiEngine._DRUM_BANKS

    def start(self):
        for song_event in self._song.events:
            self.on_debug_event(song_event=song_event)
            # Build event args.
            event_args = {
                "time": song_event.time,
                "track": song_event.track,
                "type": song_event.type,
            }
            if song_event.channel is not None:
                event_args["channel"] = song_event.channel
            event_args.update(song_event.data)
            # Fire events
            if song_event.type == _midi.EventType.NOTE_OFF:
                self.on_note_off(song_event=NoteEvent(**event_args))
            elif song_event.type == _midi.EventType.NOTE_ON:
                if song_event["velocity"] == 0:
                    self.on_note_off(song_event=NoteEvent(**event_args))
                else:
                    self.on_note_on(song_event=NoteEvent(**event_args))
            elif song_event.type == _midi.EventType.POLYPHONIC_KEY_PRESSURE:
                self.on_polyphonic_key_pressure(song_event=PolyphonicKeyPressureEvent(**event_args))
            elif song_event.type == _midi.EventType.CONTROLLER_CHANGE:
                # PyCharm bug - https://youtrack.jetbrains.com/issue/PY-42287
                # noinspection PyArgumentList
                controller = _midi.ControllerType(song_event["controller"])  # type: _midi.ControllerType
                value = song_event["value"]
                self.channels[song_event.channel].set_controller_value(controller, value)
                self.on_controller_change(song_event=ControllerChangeEvent(**event_args))
            elif song_event.type == _midi.EventType.PROGRAM_CHANGE:
                # Only trigger the signal if the value changes.
                if self.channels[song_event.channel].instrument != song_event["program"]:
                    self.channels[song_event.channel].instrument = song_event["program"]
                    self.on_program_change(song_event=ProgramChangeEvent(**event_args))
            elif song_event.type == _midi.EventType.CHANNEL_KEY_PRESSURE:
                # Only trigger the signal if the value changes.
                if self.channels[song_event.channel].key_pressure != song_event["pressure"]:
                    self.channels[song_event.channel].key_pressure = song_event["pressure"]
                    self.on_channel_key_pressure(song_event=ChannelKeyPressureEvent(**event_args))
            elif song_event.type == _midi.EventType.PITCH_BEND:
                # Only trigger the signal if the value changes.
                if self.channels[song_event.channel].pitch_bend != song_event["amount"]:
                    self.channels[song_event.channel].pitch_bend = song_event["amount"]
                    self.on_pitch_bend(song_event=PitchBendEvent(**event_args))
            elif song_event.type in [_midi.EventType.F0_SYSEX, _midi.EventType.F7_SYSEX]:
                self.on_sysex(song_event=SysexEvent(**event_args))
            elif song_event.type == _midi.EventType.META:
                meta_type = song_event["meta_type"]
                if meta_type == _midi.MetaType.SEQUENCE_NUMBER:
                    self.on_meta_sequence_number(song_event=SequenceNumberMetaEvent(**event_args))
                elif meta_type in [_midi.MetaType.TEXT_EVENT,
                                   _midi.MetaType.COPYRIGHT,
                                   _midi.MetaType.TRACK_NAME,
                                   _midi.MetaType.INSTRUMENT_NAME,
                                   _midi.MetaType.LYRIC,
                                   _midi.MetaType.MARKER,
                                   _midi.MetaType.CUE_POINT,
                                   _midi.MetaType.PROGRAM_NAME,
                                   _midi.MetaType.DEVICE_NAME]:
                    self.on_meta_text(song_event=TextMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.CHANNEL_PREFIX:
                    self.on_meta_channel_prefix(song_event=ChannelPrefixMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.PORT:
                    self.on_meta_port(song_event=PortMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.END_OF_TRACK:
                    self.on_end_of_track(song_event=EndOfTrackMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.SET_TEMPO:
                    self.on_tempo_change(song_event=TempoChangeMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.SMPTE_OFFSET:
                    self.on_smpte_offset(song_event=SmpteOffsetMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.TIME_SIGNATURE:
                    self.on_time_signature(song_event=TimeSignatureMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.KEY_SIGNATURE:
                    self.on_key_signature(song_event=KeySignatureMetaEvent(**event_args))
                elif meta_type == _midi.MetaType.SEQUENCER_SPECIFIC:
                    self.on_sequencer_specific(song_event=SequencerSpecificMetaEvent(**event_args))
                else:
                    _logging.error(f"Unexpected meta event type: {meta_type}")
            else:
                _logging.error(f"Unexpected MIDI event type: {song_event.type}")
        last_event_time = max([event.time for event in self._song.events])
        self.on_end_of_song(song_event=EndOfSongEvent(time=last_event_time))


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

    def __init__(self, number, song: MidiSongFile):
        self.number = number
        # Set by the MidiEngine.
        self._instrument = None
        self.pitch_bend = 0.0
        self.key_pressure = 127
        self.active_notes = []  # type: _typing.List[ActiveNote]
        # Controller value cache.
        self._controllers = [0] * 128
        self._in_rpn_data = None
        self._default_pitch_bend_msb = song.DEFAULT_PITCH_BEND_SCALE
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
        self.set_rpn_value(MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN, self._default_pitch_bend_msb, 0)  # semi, cents
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

    @property
    def instrument(self) -> int:
        if self._instrument is None:
            _logging.warning(f"No instrument assigned to channel {self.number}, defaulting to 0.")
            self._instrument = 0
        # Follow WOPL in that normal drums are 0..127 and SFX are 128..255
        if self.bank == MidiEngine.XG_SFX_BANK:
            return self._instrument + 128
        return self._instrument

    @instrument.setter
    def instrument(self, value: int):
        # Adjust SFX banks to be between 0..127.
        if self.bank == MidiEngine.XG_SFX_BANK and value >= 128:
            value -= 128
        self._instrument = value

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
        self._in_rpn_data = None if self.get_msb_lsb_values(_midi.ControllerType.RPN_MSB) == MidiChannelInfo.NULL_RPN \
            else True

    # noinspection PyUnusedLocal
    @_controller_handler(_midi.ControllerType.NRPN_MSB, _midi.ControllerType.NRPN_LSB)
    def _set_nrpn(self, controller):
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
            # NOTE: The MIDI specs calls the LSB "cents", but 127 = 100 cents
            semitones, cents = self.rpn[MidiChannelInfo.PITCH_BEND_SENSITIVITY_RPN]
            self._pitch_bend_sensitivity = semitones + cents / 127.0
        elif rpn in [MidiChannelInfo.FINE_TUNING_RPN, MidiChannelInfo.COARSE_TUNING_RPN]:
            fine_tuning = _midi.balance_14bit(calculate_msb_lsb(*self.rpn[MidiChannelInfo.FINE_TUNING_RPN]))
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
            # PyCharm bug - https://youtrack.jetbrains.com/issue/PY-42287
            # noinspection PyArgumentList
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


class NoteEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    channel: int
    note: int
    velocity: int


class PolyphonicKeyPressureEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    channel: int
    note: int
    pressure: int


class ControllerChangeEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    channel: int
    controller: _midi.ControllerType
    value: int


class ProgramChangeEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    channel: int
    program: int


class ChannelKeyPressureEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    channel: int
    pressure: int


class PitchBendEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    channel: int
    amount: float


class SysexEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    data: bytes


class SequenceNumberMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    number: int


class TextMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    text: str


class ChannelPrefixMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    channel: int


class PortMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    port: int


class EndOfTrackMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType


class TempoChangeMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    bpm: float


class SmpteOffsetMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    hours: int
    minutes: int
    seconds: int
    frames: int
    fractional_frames: int


class TimeSignatureMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    numerator: int
    denominator: int
    midi_clocks_per_metronome_tick: int
    number_of_32nd_notes_per_beat: int


class KeySignatureMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    sharps_flats: int
    major_minor: int


class SequencerSpecificMetaEvent(_typing.NamedTuple):
    time: float
    track: int
    type: _midi.EventType
    meta_type: _midi.MetaType
    data: bytes


class EndOfSongEvent(_typing.NamedTuple):
    time: float

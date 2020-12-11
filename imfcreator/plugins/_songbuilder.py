import typing as _typing
import imfcreator.midi as _midi


class SongBuilder:
    """A class to help build event lists for MidiSongFile classes."""

    def __init__(self, playback_rate: float, track: int = 0):
        """Starts the builder.

        :param playback_rate: The playback rate for the events.  Event times are divided by this value.
        :param track: The track number for the generated event list.
        """
        self.track = track
        self.playback_rate = playback_rate
        self._events = []  # type: _typing.List[_midi.SongEvent]
        self.current_time = 0

    def add_time(self, time: int):
        """Progresses the current time within the track."""
        self.current_time += time

    def add_event(self, event_type: _midi.EventType, data: dict = None, channel: int = None):
        song_event = _midi.SongEvent(len(self._events), self.track, self.current_time / float(self.playback_rate),
                                     event_type, data, channel)
        self._events.append(song_event)

    @property
    def events(self) -> _typing.List[_midi.SongEvent]:
        return self._events

    def note_off(self, channel: int, note: int, velocity: int):
        self.add_event(_midi.EventType.NOTE_OFF, {"note": note, "velocity": velocity}, channel)

    def note_on(self, channel: int, note: int, velocity: int):
        self.add_event(_midi.EventType.NOTE_ON, {"note": note, "velocity": velocity}, channel)

    def change_polyphonic_key_pressure(self, channel: int, note: int, pressure: int):
        self.add_event(_midi.EventType.POLYPHONIC_KEY_PRESSURE, {"note": note, "pressure": pressure}, channel)

    def change_controller(self, channel: int, controller: _midi.ControllerType, value: int):
        self.add_event(_midi.EventType.CONTROLLER_CHANGE, {"controller": controller, "value": value}, channel)

    # Shortcuts for commonly used controllers.
    def select_bank(self, channel: int, msb: int, lsb: int = None):
        self.change_controller(channel, _midi.ControllerType.BANK_SELECT_MSB, msb)
        if lsb is not None:
            self.change_controller(channel, _midi.ControllerType.BANK_SELECT_LSB, lsb)

    def set_modulation_wheel(self, channel: int, msb: int, lsb: int = None):
        self.change_controller(channel, _midi.ControllerType.MODULATION_WHEEL_MSB, msb)
        if lsb is not None:
            self.change_controller(channel, _midi.ControllerType.MODULATION_WHEEL_LSB, lsb)

    def set_volume(self, channel: int, msb: int, lsb: int = None):
        self.change_controller(channel, _midi.ControllerType.VOLUME_MSB, msb)
        if lsb is not None:
            self.change_controller(channel, _midi.ControllerType.VOLUME_LSB, lsb)

    def set_pan(self, channel: int, msb: int, lsb: int = None):
        self.change_controller(channel, _midi.ControllerType.PAN_MSB, msb)
        if lsb is not None:
            self.change_controller(channel, _midi.ControllerType.PAN_LSB, lsb)

    def set_expression(self, channel: int, msb: int, lsb: int = None):
        self.change_controller(channel, _midi.ControllerType.EXPRESSION_MSB, msb)
        if lsb is not None:
            self.change_controller(channel, _midi.ControllerType.EXPRESSION_MSB, lsb)

    def set_instrument(self, channel: int, program: int):
        self.add_event(_midi.EventType.PROGRAM_CHANGE, {"program": program}, channel)

    def set_channel_key_pressure(self, channel: int, pressure: int):
        self.add_event(_midi.EventType.CHANNEL_KEY_PRESSURE, {"pressure": pressure}, channel)

    def pitch_bend(self, channel: int, amount: float):
        self.add_event(_midi.EventType.PITCH_BEND, {"amount": amount}, channel)

    def add_sysex_data(self, event_type: _midi.EventType, data: bytes):
        self.add_event(event_type, {"data": data})

    def add_meta_sequence_number(self, number: int):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.SEQUENCE_NUMBER, "number": number})

    def add_meta_event(self, meta_type: _midi.MetaType, data: dict):
        temp_data = {"meta_type": meta_type}
        if data:
            temp_data.update(data)
        self.add_event(_midi.EventType.META, temp_data)

    def add_meta_text_event(self, meta_type: _midi.MetaType, text: str):
        self.add_meta_event(meta_type, {"text": text})

    def add_copyright(self, text: str):
        self.add_meta_text_event(_midi.MetaType.COPYRIGHT, text)

    def add_track_name(self, text: str):
        self.add_meta_text_event(_midi.MetaType.TRACK_NAME, text)

    def add_instrument_name(self, text: str):
        self.add_meta_text_event(_midi.MetaType.INSTRUMENT_NAME, text)

    def add_lyric(self, text: str):
        self.add_meta_text_event(_midi.MetaType.LYRIC, text)

    def add_marker(self, text: str):
        self.add_meta_text_event(_midi.MetaType.MARKER, text)

    def add_cue_point(self, text: str):
        self.add_meta_text_event(_midi.MetaType.CUE_POINT, text)

    def add_meta_program_name(self, text: str):
        self.add_meta_text_event(_midi.MetaType.PROGRAM_NAME, text)

    def add_meta_device_name(self, text: str):
        self.add_meta_text_event(_midi.MetaType.DEVICE_NAME, text)

    def add_meta_channel_prefix(self, channel: int):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.CHANNEL_PREFIX, "channel": channel})

    def add_meta_port(self, port: int):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.PORT, "port": port})

    def add_end_of_track(self):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.END_OF_TRACK})

    def set_tempo(self, bpm: float):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.SET_TEMPO, "bpm": bpm})

    def add_meta_smpte_offset(self, hours: int, minutes: int, seconds: int, frames: int, fractional_frames: int):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.SMPTE_OFFSET,
                                              "hours": hours,
                                              "minutes": minutes,
                                              "seconds": seconds,
                                              "frames": frames,
                                              "fractional_frames": fractional_frames,
                                              })

    def set_time_signature(self, numerator: int, denominator: int, midi_clocks_per_metronome_tick: int = None,
                           number_of_32nd_notes_per_beat: int = None):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.TIME_SIGNATURE,
                                              "numerator": numerator,
                                              "denominator": denominator,
                                              "midi_clocks_per_metronome_tick": midi_clocks_per_metronome_tick,
                                              "number_of_32nd_notes_per_beat": number_of_32nd_notes_per_beat,
                                              })

    def set_key_signature(self, sharps_flats: int, major_minor: int):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.KEY_SIGNATURE,
                                              "sharps_flats": sharps_flats,
                                              "major_minor": major_minor,
                                              })

    def add_sequencer_specific_data(self, data: bytes):
        self.add_event(_midi.EventType.META, {"meta_type": _midi.MetaType.SEQUENCER_SPECIFIC, "data": data})

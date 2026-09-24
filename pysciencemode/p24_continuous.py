"""
Non-blocking (continuous) mid-level stimulation for the P24.

The P24 stops a mid-level stimulation by itself when it receives neither a ``Ml_update`` nor a
``Ml_get_current_data`` (keep-alive) command for 2 s (P24 Instructions for Use v1.1, 2023-01-25,
section "Mid-Level Update", p. 23: "The stimulation has an automatic timeout of 2 s. To keep the
stimulation alive, you need to send the keep-alive-signal (Ml_get_current_data) or a Ml_update.").

``ContinuousStimulation`` runs a daemon thread that becomes the single owner of the serial port while the
stimulation runs. It:

* applies the parameter updates requested from other threads (latest request wins),
* sends ``Ml_get_current_data`` on a deadline-based schedule (default every 0.5 s, i.e. 4x faster than
  the device timeout), which both keeps the stimulation alive and reports the electrode errors,
* waits for every ack with a timeout and discards stray acks,
* stores any exception so that it is re-raised in the caller thread on the next call.

This class is internal: use ``P24.start_stimulation(..., blocking=False)``, ``P24.update_stimulation`` and
``P24.stop_stimulation`` instead.
"""

from dataclasses import dataclass
import threading
import time
from typing import Callable

from .enums import ErrorCode

#  Device timeout of the mid-level stimulation (P24 IFU v1.1, p. 23).
DEVICE_ML_TIMEOUT_S = 2.0
#  Default period of the keep-alive command, 4x shorter than the device timeout.
DEFAULT_KEEP_ALIVE_PERIOD_S = 0.5
#  Largest keep-alive period accepted: keeps a margin of 0.5 s for the ack round trip and OS jitter.
MAX_KEEP_ALIVE_PERIOD_S = 1.5
#  Default time allowed to the device to answer a command.
DEFAULT_ACK_TIMEOUT_S = 0.5


@dataclass(frozen=True)
class StimulationEvent:
    """
    Event passed to the ``callback`` of a continuous stimulation. The callback is called from the
    stimulation thread: it must return quickly (it delays the keep-alive) and must not call any method of the
    stimulator that talks to the device (``update_stimulation`` is allowed, it only queues a request).

    Attributes
    ----------
    kind : str
        "update" after an ``Ml_update`` has been acknowledged by the device (including the first one, which
        starts the stimulation, and the final zero-amplitude one sent by ``stop_stimulation``),
        "keep_alive" after an ``Ml_get_current_data`` has been acknowledged and checked for errors.
    t : float
        ``time.perf_counter()`` timestamp taken when the ack was received.
    seq : int
        Sequence number of the last applied update request (1 for the first update, 0 for the final
        zero-amplitude update).
    channel_states : tuple | None
        For "keep_alive" events, the 8 raw ``Smpt_Ml_Channel_State`` values returned by the device.
        None for "update" events.
    """

    kind: str
    t: float
    seq: int
    channel_states: tuple | None = None


def snapshot_channels(list_channels: list, zero_amplitude: bool = False) -> tuple:
    """
    Copy the stimulation parameters of the channels into an immutable structure, so that the stimulation thread
    never reads the Channel objects that the user may be modifying at the same time.

    Returns
    -------
    A tuple of (channel_index, period, ramp, ((pulse_width, amplitude), ...)).
    """
    return tuple(
        (
            channel._no_channel - 1,
            channel._period,
            channel._ramp,
            tuple(
                (point.pulse_width, 0 if zero_amplitude else point.amplitude)
                for point in channel.list_point
            ),
        )
        for channel in list_channels
    )


def zero_amplitude_snapshot(snapshot: tuple) -> tuple:
    """
    Return a copy of the snapshot with all amplitudes set to zero (used to pause the stimulation).
    """
    return tuple(
        (index, period, ramp, tuple((pulse_width, 0) for pulse_width, _ in points))
        for index, period, ramp, points in snapshot
    )


def channel_state_error(sciencemode, channel_number: int, channel_state: int) -> str | None:
    """
    Convert a Smpt_Ml_Channel_State into an error message, None if the channel is ok.
    """
    lib = sciencemode.lib
    if channel_state == lib.Smpt_Ml_Channel_State_Ok:
        return None
    if channel_state == lib.Smpt_Ml_Channel_State_Electrode_Error:
        return f"Electrode error on channel {channel_number}"
    if channel_state == lib.Smpt_Ml_Channel_State_Timeout_Error:
        return f"Timeout error on channel {channel_number}"
    if channel_state == lib.Smpt_Ml_Channel_State_Low_Current_Error:
        return f"Low current error on channel {channel_number}"
    if channel_state == lib.Smpt_Ml_Channel_State_Last_Item:
        return f"Last item error on channel {channel_number}"
    return f"Unknown error on channel {channel_number}"


class ContinuousStimulation:
    """
    Background thread keeping a P24 mid-level stimulation alive. See the module docstring.
    """

    def __init__(
        self,
        stimulator,
        sciencemode,
        snapshot: tuple,
        stimulation_duration: float | None = None,
        keep_alive_period: float = DEFAULT_KEEP_ALIVE_PERIOD_S,
        ack_timeout: float = DEFAULT_ACK_TIMEOUT_S,
        callback: Callable[[StimulationEvent], None] | None = None,
    ):
        if not 0 < keep_alive_period <= MAX_KEEP_ALIVE_PERIOD_S:
            raise ValueError(
                f"keep_alive_period must be in ]0, {MAX_KEEP_ALIVE_PERIOD_S}] s "
                f"(device timeout {DEVICE_ML_TIMEOUT_S} s), value given {keep_alive_period} s."
            )
        if not 0 < ack_timeout < DEVICE_ML_TIMEOUT_S - keep_alive_period:
            raise ValueError(
                f"ack_timeout must be in ]0, {DEVICE_ML_TIMEOUT_S} - keep_alive_period[ s, "
                f"value given {ack_timeout} s."
            )
        if callback is not None and not callable(callback):
            raise TypeError("Please provide a callable for callback")

        self._stimulator = stimulator
        self._sm = sciencemode
        self.keep_alive_period = keep_alive_period
        self.ack_timeout = ack_timeout
        self.callback = callback

        self._cond = threading.Condition()
        self._pending = snapshot  # Guarded by _cond
        self._requested_seq = 1  # Guarded by _cond
        self._applied_seq = 0  # Guarded by _cond
        self._stop_requested = False  # Guarded by _cond
        self._pause_on_stop = True  # Guarded by _cond
        self._deadline = (
            None if stimulation_duration is None else time.perf_counter() + stimulation_duration
        )  # Guarded by _cond
        self._active_snapshot = None  # Only used by the thread
        self.error = None
        self.last_channel_states = None

        self._thread = threading.Thread(
            target=self._run, name="P24ContinuousStimulation", daemon=True
        )

    #  Caller side
    @property
    def thread(self) -> threading.Thread:
        return self._thread

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def start(self, timeout: float):
        """
        Start the thread and wait until the first update is acknowledged by the device.
        """
        self._thread.start()
        self.wait_applied(1, timeout)

    def request_update(
        self, snapshot: tuple, stimulation_duration: float | None = None
    ) -> int:
        """
        Queue a parameter update. If an update is still pending it is replaced (latest request wins).

        Returns
        -------
        The sequence number of the request, to be given to wait_applied.
        """
        with self._cond:
            if self._stop_requested:
                raise RuntimeError("The continuous stimulation is stopping.")
            self._pending = snapshot
            self._requested_seq += 1
            if stimulation_duration is not None:
                self._deadline = time.perf_counter() + stimulation_duration
            self._cond.notify_all()
            return self._requested_seq

    def wait_applied(self, seq: int, timeout: float):
        """
        Wait until the update request seq (or a more recent one) has been acknowledged by the device.
        """
        end = time.perf_counter() + timeout
        with self._cond:
            while self._applied_seq < seq:
                if self.error is not None or not self._thread.is_alive():
                    break
                remaining = end - time.perf_counter()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Stimulation update {seq} not acknowledged within {timeout} s."
                    )
                self._cond.wait(remaining)
        if self.error is not None:
            raise self.error
        if self._applied_seq < seq:
            raise RuntimeError("The continuous stimulation ended before the update was applied.")

    def stop(self, pause: bool = True, timeout: float = 3.0):
        """
        Ask the thread to stop (after a zero-amplitude update if pause is True) and join it.
        """
        with self._cond:
            self._stop_requested = True
            self._pause_on_stop = pause
            self._cond.notify_all()
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise RuntimeError(
                    f"The continuous stimulation thread did not stop within {timeout} s."
                )

    #  Thread side
    def _run(self):
        try:
            self._loop()
        except BaseException as e:  # Propagated to the caller thread on its next call
            self.error = e
            self._best_effort_pause()
        finally:
            with self._cond:
                self._cond.notify_all()

    def _loop(self):
        next_keep_alive = None
        while True:
            with self._cond:
                pending, seq = self._pending, self._requested_seq
                self._pending = None
                stop, pause = self._stop_requested, self._pause_on_stop
                deadline = self._deadline

            if stop:
                if pause and self._active_snapshot is not None:
                    self._send_update(zero_amplitude_snapshot(self._active_snapshot), 0)
                return

            if pending is not None:
                self._send_update(pending, seq)
                if next_keep_alive is None:
                    next_keep_alive = time.perf_counter() + self.keep_alive_period

            now = time.perf_counter()
            if deadline is not None and now >= deadline:
                with self._cond:
                    self._stop_requested = True
                continue

            if next_keep_alive is not None and now >= next_keep_alive:
                self._send_keep_alive()
                next_keep_alive += self.keep_alive_period
                now = time.perf_counter()
                if next_keep_alive <= now:  # Late (slow ack or OS jitter): do not burst, restart the schedule
                    next_keep_alive = now + self.keep_alive_period

            wake_up = next_keep_alive if deadline is None else min(next_keep_alive, deadline)
            with self._cond:
                if self._pending is None and not self._stop_requested:
                    self._cond.wait(max(wake_up - time.perf_counter(), 0))

    def _send_update(self, snapshot: tuple, seq: int):
        lib = self._sm.lib
        stim = self._stimulator
        ml_update = stim.ml_update
        for index, period, ramp, points in snapshot:
            ml_update.enable_channel[index] = True
            config = ml_update.channel_config[index]
            config.period = period
            config.ramp = ramp
            config.number_of_points = len(points)
            for j, (pulse_width, amplitude) in enumerate(points):
                config.points[j].time = pulse_width
                config.points[j].current = amplitude
        ml_update.packet_number = stim.get_next_packet_number()
        if not lib.smpt_send_ml_update(stim.device, ml_update):
            raise RuntimeError("Failed to send stimulation update")
        self._wait_ack(lib.Smpt_Cmd_Ml_Update_Ack)
        t = time.perf_counter()
        self._active_snapshot = snapshot
        with self._cond:
            if seq > self._applied_seq:
                self._applied_seq = seq
            self._cond.notify_all()
        stim.log({0: "Stimulation paused", 1: "Stimulation started"}.get(seq, "Stimulation updated"))
        self._emit(StimulationEvent("update", t, seq))

    def _send_keep_alive(self):
        sm = self._sm
        lib = sm.lib
        stim = self._stimulator
        request = sm.ffi.new("Smpt_ml_get_current_data*")
        request.data_selection = lib.Smpt_Ml_Data_Channels
        request.packet_number = stim.get_next_packet_number()
        if not lib.smpt_send_ml_get_current_data(stim.device, request):
            raise RuntimeError("Failed to send the keep-alive (Ml_get_current_data).")
        self._wait_ack(lib.Smpt_Cmd_Ml_Get_Current_Data_Ack)
        t = time.perf_counter()
        data_ack = stim.ml_get_current_data_ack
        lib.smpt_get_ml_get_current_data_ack(stim.device, data_ack)
        states = tuple(data_ack.channel_data.channel_state[i] for i in range(8))
        self.last_channel_states = states
        for index, _, _, _ in self._active_snapshot or ():
            message = channel_state_error(sm, index + 1, states[index])
            if message is not None:
                raise RuntimeError(message)
        with self._cond:
            seq = self._applied_seq
        self._emit(StimulationEvent("keep_alive", t, seq, states))

    def _wait_ack(self, expected_command: int):
        """
        Wait for the ack of the expected command, discarding any other ack received in the meantime.
        """
        lib = self._sm.lib
        stim = self._stimulator
        end = time.perf_counter() + self.ack_timeout
        while True:
            while not lib.smpt_new_packet_received(stim.device):
                if time.perf_counter() >= end:
                    raise TimeoutError(
                        f"No ack {stim.P24Commands(expected_command).name} received "
                        f"within {self.ack_timeout} s."
                    )
                time.sleep(0.0005)
            lib.smpt_last_ack(stim.device, stim.ack)
            if stim.show_log is True:
                print("Ack received by P24: ", stim.P24Commands(stim.ack.command_number).name)
            if stim.ack.command_number == expected_command:
                break
        result = stim.ack.result
        if result != lib.Smpt_Result_Successful:
            try:
                message = ErrorCode(result).message
            except ValueError:
                message = None
            raise RuntimeError(
                f"{stim.P24Commands(expected_command).name} returned the error "
                f"{result}{': ' + message if message else ''}"
            )

    def _emit(self, event: StimulationEvent):
        if self.callback is not None:
            self.callback(event)

    def _best_effort_pause(self):
        """
        After an error, try to set the amplitudes to zero. Errors are ignored (the device may already
        have stopped: it stops by itself after 2 s without keep-alive).
        """
        if self._active_snapshot is None:
            return
        try:
            callback, self.callback = self.callback, None
            self._send_update(zero_amplitude_snapshot(self._active_snapshot), 0)
        except BaseException:
            pass
        finally:
            self.callback = callback

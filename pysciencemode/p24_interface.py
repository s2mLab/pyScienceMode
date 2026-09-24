import threading
import time
from typing import Callable

from .utils import (
    check_unique_channel,
    calc_electrode_number,
    generic_error_check,
    check_list_channel_order,
    check_stimulation_parameter_list,
    check_pulse_interval_list,
)
from .sciencemode import RehastimGeneric
try:
    from sciencemode import sciencemode
except ImportError:
    pass
from .enums import Device, HighVoltage, Modes, StimStatus
from .channel import Point, Channel
from .p24_continuous import (
    ContinuousStimulation,
    StimulationEvent,
    DEFAULT_ACK_TIMEOUT_S,
    DEFAULT_KEEP_ALIVE_PERIOD_S,
    snapshot_channels,
)


class P24(RehastimGeneric):
    """
    Class used for the communication with P24.
    """

    def __init__(self, port: str, show_log: bool | str = False):
        """
        Creates an object stimulator for the P24.

        Parameters
        ----------
        port : str
            Port of the computer connected to the Rehastim.
        show_log: bool | str
            If True, all logs of the communication will be printed.
            If "Status", only basic logs will be printed.
            If False, no logs will be printed.
        """
        if show_log not in [True, False, "Status"]:
            raise ValueError("show_log must be True, False, or 'Status'.")

        self.list_channels = None
        self.electrode_number = 0
        self.stimulation_started = None
        self.show_log = show_log
        self._current_no_channel = None
        self._current_stim_sequence = None
        self._current_pulse_interval = None
        self._current_stim_duration = None
        self.device_type = Device.P24.value
        self._safety = True
        self._continuous = None  # ContinuousStimulation of the non-blocking mode, None otherwise

        super().__init__(port, device_type=self.device_type, show_log=self.show_log)

    def get_next_packet_number(self):
        """
        Get the next packet number. While a non-blocking stimulation runs, its thread is the only owner of the
        serial port: any command sent from another thread would steal its acks, so it is refused.
        """
        continuous = getattr(self, "_continuous", None)
        if (
            continuous is not None
            and continuous.is_alive()
            and threading.current_thread() is not continuous.thread
        ):
            raise RuntimeError(
                "A non-blocking stimulation is running: only update_stimulation is allowed. "
                "Call stop_stimulation() (or end_stimulation()) before sending other commands."
            )
        return super().get_next_packet_number()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Stop any non-blocking stimulation, leave the mid level if it was initialized and close the port.
        """
        try:
            self._stop_continuous(pause=False, raise_error=exc_type is None)
            if self.stimulation_started:
                self.end_stimulation()
        finally:
            self.close_port()
        return False

    @property
    def is_stimulating(self) -> bool:
        """
        True while a non-blocking stimulation started with start_stimulation(..., blocking=False) is running.
        Raises the error of the stimulation thread if it stopped on an error.
        """
        self.check_stimulation_thread()
        return self._continuous is not None and self._continuous.is_alive()

    def check_stimulation_thread(self):
        """
        Re-raise, in the caller thread, the exception that stopped the non-blocking stimulation thread (electrode
        error, missing ack, exception in the callback...). Called automatically by start_stimulation,
        update_stimulation, stop_stimulation, end_stimulation and is_stimulating. The error is raised only once.
        """
        continuous = self._continuous
        if continuous is not None and continuous.error is not None:
            continuous.thread.join(1.0)
            self._continuous = None
            raise continuous.error

    def stop_stimulation(self, pause: bool = True, timeout: float = 3.0):
        """
        Stop a non-blocking stimulation started with start_stimulation(..., blocking=False) and join its thread.
        The mid level stays initialized: the stimulation can be started again with start_stimulation. Use
        end_stimulation to leave the mid level. Does nothing if no non-blocking stimulation is running.

        Parameters
        ----------
        pause : bool
            If True, a last update with all amplitudes set to zero is sent before stopping (same final state as
            the blocking start_stimulation). If False, the device stops by itself 2 s after the last keep-alive,
            unless end_stimulation is called.
        timeout : float
            Maximum time in seconds to wait for the thread to stop.
        """
        self._stop_continuous(pause=pause, timeout=timeout)

    def _stop_continuous(
        self, pause: bool = True, timeout: float = 3.0, raise_error: bool = True
    ):
        continuous = self._continuous
        if continuous is None:
            return
        try:
            continuous.stop(pause=pause, timeout=timeout)
        finally:
            self._continuous = None
        if raise_error and continuous.error is not None:
            raise continuous.error

    def close_port(self):
        """
        Close the port, after stopping the non-blocking stimulation if any.
        """
        self._stop_continuous(pause=True, raise_error=False)
        super().close_port()

    #  General level commands
    def get_extended_version(self) -> tuple:
        """
        Get the extended version of the device (firmware,uc_version) . General Level command.

        Returns
        -------
        tuple
        fw_hash : int
            Firmware hash.
        uc_version : int
            Microcontroller version.
        """
        extended_version_ack = sciencemode.ffi.new("Smpt_get_extended_version_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.lib.smpt_send_get_extended_version(self.device, packet_number)
        if self.show_log is True:
            print(
                "Command sent to rehastim:",
                self.P24Commands(
                    sciencemode.lib.Smpt_Cmd_Get_Extended_Version
                ).name,
            )
        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_extended_version_ack(
            self.device, extended_version_ack
        )
        fw_hash = f"fw_hash :{extended_version_ack.fw_hash}"
        uc_version = f"uc_version : {extended_version_ack.uc_version} "
        return fw_hash, uc_version

    def get_device_id(self) -> str:
        """
        Get the device id.

        Returns
        -------
        device_id : str
            Device id.
        """
        device_id_ack = sciencemode.ffi.new("Smpt_get_device_id_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.lib.smpt_send_get_device_id(self.device, packet_number)

        if self.show_log is True:
            print(
                "Command sent to rehastim:",
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Get_Device_Id).name,
            )

        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_device_id_ack(self.device, device_id_ack)
        device_id = f"device_id : {device_id_ack.device_id} "
        return device_id

    def get_stim_status(self) -> tuple:
        """
        Get the stimulation status. General Level command.

        Returns
        -------
        tuple
        stim_status : int
            Stimulation status.
        voltage_level : str
            Current voltage level.
        """

        stim_status_ack = sciencemode.ffi.new("Smpt_get_stim_status_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.lib.smpt_send_get_stim_status(self.device, packet_number)

        if self.show_log is True:
            print(
                "Command sent to rehastim:",
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Get_Stim_Status).name,
            )

        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_stim_status_ack(self.device, stim_status_ack)
        stim_status = f"stim status : {StimStatus(stim_status_ack.stim_status).name}"
        voltage_level = (
            f"voltage level : {HighVoltage(stim_status_ack.high_voltage_level).name}"
        )
        return stim_status, voltage_level

    def get_battery_status(self) -> tuple:
        """
        Get the battery status (battery level and battery voltage). General Level command.

        Returns
        -------
        tuple
        battery_level : int
            Battery level.
        battery_voltage : float
            Battery voltage.
        """
        battery_status_ack = sciencemode.ffi.new("Smpt_get_battery_status_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.lib.smpt_send_get_battery_status(self.device, packet_number)

        if self.show_log is True:
            print(
                "Command sent to rehastim:",
                self.P24Commands(
                    sciencemode.lib.Smpt_Cmd_Get_Battery_Status
                ).name,
            )

        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_battery_status_ack(
            self.device, battery_status_ack
        )
        battery_level = f"battery level : {battery_status_ack.battery_level}"
        battery_voltage = f"battery voltage : {battery_status_ack.battery_voltage}"
        return battery_level, battery_voltage

    def get_main_status(self):
        """
        Get the main status. General Level command.

        Returns
        -------
        main_status : int
            Main status.
        """
        main_status_ack = sciencemode.ffi.new("Smpt_get_main_status_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.lib.smpt_send_get_main_status(self.device, packet_number)

        if self.show_log is True:
            print(
                "Command sent to rehastim:",
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Get_Main_Status).name,
            )

        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_main_status_ack(self.device, main_status_ack)
        main_status = f"main status : {main_status_ack.main_status}"
        return main_status

    def reset(self):
        """
        Reset the device. General Level command.
        """
        packet_number = self.get_next_packet_number()
        ret = sciencemode.lib.smpt_send_reset(self.device, packet_number)

        if self.show_log is True:
            print(
                "Command sent to rehastim:",
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Reset).name,
            )
        self._get_last_ack()

    def get_all(self):
        """
        Get all the device information. General Level command.
        """
        extended_version_success = self.get_extended_version()
        device_id_success = self.get_device_id()
        stim_status_success = self.get_stim_status()
        battery_status_success = self.get_battery_status()
        main_status_success = self.get_main_status()

        return (
            extended_version_success,
            device_id_success,
            stim_status_success,
            battery_status_success,
            main_status_success,
        )

    @staticmethod
    def _channel_number_to_channel_connector(no_channel):
        """
        Converts the channel number to the corresponding channel and connector.
        For example, if the user enters no_channel 3,
        it will convert this number and interpret it as channel 2 of 4 [0,3] for the yellow connector.

        Parameters
        ----------
        no_channel : int
            The channel number.

        Returns
        -------
        channel and connector
        """
        channels = [
            sciencemode.lib.Smpt_Channel_Red,
            sciencemode.lib.Smpt_Channel_Blue,
            sciencemode.lib.Smpt_Channel_Black,
            sciencemode.lib.Smpt_Channel_White,
        ]

        connectors = [
            sciencemode.lib.Smpt_Connector_Yellow,
            sciencemode.lib.Smpt_Connector_Green,
        ]

        # Determine the connector
        connector_idx = (no_channel - 1) // 4
        connector = connectors[connector_idx]

        # Determine the channel
        channel = channels[(no_channel - 1) % 4]

        return channel, connector

    #  Low level commands

    def ll_init(self):
        """
        Initialize the lower level of the device. The low-level is used for defining a custom shaped pulse.
        Each stimulation pulse needs to triggered from the computer.
        You can only stimulate one channel. This is useful for the execution of stimulation pulses with a high frequency
        """
        ll_init = sciencemode.ffi.new("Smpt_ll_init*")
        ll_init.high_voltage_level = (
            sciencemode.lib.Smpt_High_Voltage_Default
        )  # This switches on the high voltage source
        ll_init.packet_number = self.get_next_packet_number()

        if not sciencemode.lib.smpt_send_ll_init(self.device, ll_init):
            raise RuntimeError("Low level initialization failed.")
        self.log(
            "Low level initialized",
            "Command sent to rehastim: {}".format(
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Ll_Init).name
            ),
        )

        self.get_next_packet_number()
        self._get_last_ack()
        self.check_ll_init_ack()

    def check_ll_init_ack(self):
        """
        Check the low level initialization status.
        """
        if not sciencemode.lib.smpt_get_ll_init_ack(self.device, self.ll_init_ack):
            raise RuntimeError("Low level initialization failed.")
        generic_error_check(self.ll_init_ack)

    def start_stim_one_channel_stimulation(
        self,
        no_channel: int,
        points: list,
        stim_sequence: int,
        pulse_interval: int | float,
        safety: bool = True,
    ):
        """
        Starts the low level mode stimulation.

        Parameters
        ----------
        no_channel : int
            The channel number [1,8].
        points : list
            Points to stimulate. [1,16]
        stim_sequence : int
            Number of stimulation sequence to be repeated.
        pulse_interval : int | float
            Interval between each stimulation sequence in ms.
        safety : bool
            Set to True if you want to check the pulse symmetry. False otherwise.
        """

        self.ll_init()
        if not isinstance(stim_sequence, int):
            raise TypeError("Please provide a int type for stim_sequence")
        if not isinstance(pulse_interval, int | float):
            raise TypeError("Please provide a int or float type for pulse_interval")
        if not isinstance(points, list):
            raise TypeError("points must be a list.")
        if not points:
            raise ValueError("Please provide at least one point for stimulation.")
        for index, point in enumerate(points):
            if not isinstance(point, Point):
                raise TypeError(
                    f"Item at index {index} is not a Point instance, got {type(point).__name__} type instead."
                )
        if not 0.5 < pulse_interval < 16383:
            raise ValueError(
                f"pulse_interval min = 0.5ms, max = 16383ms, value given {pulse_interval}ms. "
            )

        self._current_no_channel = no_channel
        self._current_stim_sequence = stim_sequence
        self._current_pulse_interval = pulse_interval
        self.log("Low level stimulation started")

        positive_area = 0
        negative_area = 0

        channel, connector = self._channel_number_to_channel_connector(no_channel)
        ll_config = sciencemode.ffi.new("Smpt_ll_channel_config*")

        ll_config.enable_stimulation = True
        ll_config.channel = channel
        ll_config.connector = connector
        ll_config.number_of_points = len(points)

        for j, point in enumerate(points):
            ll_config.points[j].time = point.pulse_width
            ll_config.points[j].current = point.amplitude

        if safety is True:
            for point in points:
                if point.amplitude > 0:
                    positive_area += point.amplitude * point.pulse_width
                else:
                    negative_area -= point.amplitude * point.pulse_width
            if abs(positive_area - negative_area) > 1e-6:
                raise ValueError(
                    "The points are not symmetric based on amplitude.\n"
                    "Polarization and depolarization must have the same area.\n"
                    "Or set safety=False in start_stim_one_channel_stimulation."
                )

        for _ in range(stim_sequence):
            ll_config.packet_number = self.get_next_packet_number()
            sciencemode.lib.smpt_send_ll_channel_config(self.device, ll_config)
            if self.show_log is True:
                print(
                    "Command sent to rehastim:",
                    self.P24Commands(
                        sciencemode.lib.Smpt_Cmd_Ll_Channel_Config
                    ).name,
                )
            time.sleep(pulse_interval / 1000)
            self._get_last_ack()
            self.check_ll_channel_config_ack()

    def check_ll_channel_config_ack(self):
        """
        Check the low level channel config status.
        """
        if not sciencemode.lib.smpt_get_ll_channel_config_ack(
            self.device, self.ll_channel_config_ack
        ):
            raise ValueError("Failed to get the ll_channel_config_ack.")
        generic_error_check(self.ll_channel_config_ack)

    def update_stim_one_channel(
        self,
        upd_list_point,
        no_channel=None,
        stim_sequence: int = None,
        pulse_interval: int | float = None,
    ):
        """
        Update the stimulation in low level mode.

        Parameters
        ----------
        no_channel : int
            The channel number [1,8].
        upd_list_point : list
            Points to stimulate. [1,16]
        stim_sequence : int
            Number of stimulation sequence to be repeated.
        pulse_interval : int | float
            Interval between each stimulation sequence in ms.
        """
        if stim_sequence is None:
            stim_sequence = self._current_stim_sequence
        if no_channel is None:
            no_channel = self._current_no_channel
        if pulse_interval is None:
            pulse_interval = self._current_pulse_interval
        self.start_stim_one_channel_stimulation(
            no_channel, upd_list_point, stim_sequence, pulse_interval
        )

    def end_stim_one_channel(self):
        """
        Stop the device lower level.
        """
        packet_number = self.get_next_packet_number()
        if not sciencemode.lib.smpt_send_ll_stop(self.device, packet_number):
            raise RuntimeError("Low level stop failed.")
        self.log(
            "Low level stopped",
            "Command sent to rehastim: {}".format(
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Ll_Stop).name
            ),
        )
        self._get_last_ack()

    def init_stimulation(self, list_channels: list, stop_all_on_error: bool = True):
        """
        Initialize the mid level stimulation on the device. It is used for defining a stimulation pattern

        Parameters
        ----------
        list_channels : list
            Channels to stimulate.
        stop_all_on_error : bool
            If flag is set to True ,stop stimulation if one channel has an error.
        """
        if self.stimulation_started:
            self.end_stimulation()

        for index, channel in enumerate(list_channels):
            if not isinstance(channel, Channel):
                raise TypeError(
                    f"Item at index {index} is not a Channel instance, got {type(channel).__name__} type instead."
                )
        if not list_channels:
            raise ValueError("Please provide at least one channel for stimulation.")
        else:
            self.list_channels = list_channels

        check_unique_channel(list_channels)
        self.electrode_number = calc_electrode_number(self.list_channels)

        ml_init = sciencemode.ffi.new("Smpt_ml_init*")
        ml_init.stop_all_channels_on_error = stop_all_on_error
        ml_init.packet_number = self.get_next_packet_number()

        if not sciencemode.lib.smpt_send_ml_init(self.device, ml_init):
            raise RuntimeError("Failed to start stimulation")
        self.log(
            "Stimulation initialized",
            "Command sent to rehastim: {}".format(
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Ml_Init).name
            ),
        )
        self._get_last_ack()

    def start_stimulation(
        self,
        upd_list_channels: list,
        stimulation_duration: int | float = None,
        safety: bool = True,
        blocking: bool = True,
        callback: Callable[[StimulationEvent], None] = None,
        keep_alive_period: float = DEFAULT_KEEP_ALIVE_PERIOD_S,
        ack_timeout: float = DEFAULT_ACK_TIMEOUT_S,
    ):
        """
        Start the mid level stimulation on the device.

        Parameters
        ----------
        stimulation_duration : int | float
            Duration of the stimulation in seconds.
            If blocking is True and it is None, the update is sent and the stimulation is immediately paused.
            If blocking is False and it is None, the stimulation runs until stop_stimulation or end_stimulation.
        upd_list_channels : list
            Channels to stimulate.
        safety : bool
            Set to True if you want to check the pulse symmetry. False otherwise.
        blocking : bool
            If True (default, historical behavior), the method returns when the stimulation is over.
            If False, a background thread keeps the stimulation alive (the device stops a mid-level stimulation
            after 2 s without command, P24 IFU v1.1 p. 23) and the method returns as soon as the device
            acknowledged the first update. The parameters can then be changed with update_stimulation. While the
            thread runs, it is the only one allowed to talk to the device: other commands raise a RuntimeError
            until stop_stimulation or end_stimulation is called. If a non-blocking stimulation is already running,
            the call is forwarded to update_stimulation.
        callback : callable
            Non-blocking mode only. Called from the stimulation thread with a StimulationEvent after each
            acknowledged update and keep-alive, with a time.perf_counter timestamp. It must return quickly; if it
            raises, the stimulation stops and the exception is re-raised on the next call.
        keep_alive_period : float
            Non-blocking mode only. Period in s of the keep-alive and electrode error check, in ]0, 1.5].
        ack_timeout : float
            Non-blocking mode only. Maximum time in s to wait for each ack of the device.
        """
        self.check_stimulation_thread()
        if self._continuous is not None:
            if blocking:
                self._stop_continuous(pause=False)
            else:
                self.update_stimulation(upd_list_channels, stimulation_duration)
                return

        if stimulation_duration and not isinstance(stimulation_duration, int | float):
            raise TypeError(
                "Please provide a int or float type for stimulation duration"
            )

        self._check_update_channels(upd_list_channels, safety)

        self.list_channels = upd_list_channels
        self._safety = safety
        if stimulation_duration:
            self._current_stim_duration = stimulation_duration

        if not blocking:
            continuous = ContinuousStimulation(
                self,
                sciencemode,
                snapshot_channels(upd_list_channels),
                stimulation_duration=stimulation_duration,
                keep_alive_period=keep_alive_period,
                ack_timeout=ack_timeout,
                callback=callback,
            )
            self._continuous = continuous
            self.stimulation_started = True
            try:
                continuous.start(timeout=3 * ack_timeout)
            except BaseException:
                self._stop_continuous(pause=True, raise_error=False)
                raise
            return

        self.ml_update.packet_number = self.get_next_packet_number()
        self._send_stimulation_update()

        if stimulation_duration:
            start_time = time.time()
            while (time.time() - start_time) < stimulation_duration:
                self._get_current_data()
                self._get_last_ack()
                self.check_stimulation_errors()
                time.sleep(0.005)

        self.pause_stimulation()
        self.stimulation_started = True

    def _check_update_channels(self, upd_list_channels: list, safety: bool):
        """
        Check the channels given to start or update the mid level stimulation.
        """
        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError(
                    "Error update: all channels have not been initialised"
                )

        check_list_channel_order(upd_list_channels)

        for channel in upd_list_channels:
            if safety and not channel.is_pulse_symmetric():
                raise ValueError(
                    f"Pulse for channel {channel._no_channel} is not symmetric.\n"
                    f"Polarization and depolarization must have the same area.\n"
                    f"Or set safety=False in start_stimulation."
                )
            #  Check if points are provided for each channel stimulated
            if not channel.list_point:
                raise ValueError(
                    "No stimulation point provided for channel {}. "
                    "Please either provide an amplitude and pulse width for a biphasic stimulation."
                    "Or specify specific stimulation points.".format(
                        channel._no_channel
                    )
                )

    def start_pulse_by_pulse_stimulation(
        self,
        upd_list_channels: list,
        pulse_width_list: dict,
        amplitude_list: dict = None,
        pulse_interval_list: list = None,
        stop_condition: Callable = None,
    ):
        """
        Start the mid level stimulation on the device, sending the stimulation parameters pulse by pulse.

        Contrary to start_stimulation, the stimulation is not held for a fixed duration with a fixed set of
        parameters. The parameters are updated between each pulse and the stimulation stops when all the given
        parameters have been sent, or as soon as the stop_condition is met.

        Parameters
        ----------
        upd_list_channels : list
            Channels to stimulate. Each channel must use a Single, Doublet or Triplet mode.
        pulse_width_list : dict
            Pulse width sent for each pulse. The key is the channel number and the value is the list of the pulse
            widths in μs sent one pulse after the other.
        amplitude_list : dict
            Amplitude sent for each pulse. The key is the channel number and the value is the list of the amplitudes
            in mA sent one pulse after the other. If None, the amplitude of each channel is left unchanged.
        pulse_interval_list : list
            Interval in ms between a pulse and the next one. One interval must be given for each pulse and it is
            shared by all the channels, as they are all updated at the same time. It sets the period of every channel
            and paces the stimulation, so it can not be shorter than the communication time with the device.
            If None, the frequency of each channel is left unchanged and the parameters are sent as soon as the
            device has answered.
        stop_condition : callable
            Function called before each pulse. The stimulation stops as soon as it returns True.
        """

        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError(
                    "Error update: all channels have not been initialised"
                )

        check_list_channel_order(upd_list_channels)

        #  The pulse is regenerated between each pulse, so each channel needs a mode to shape it.
        for channel in upd_list_channels:
            if channel.get_mode() == Modes.NONE.value:
                raise ValueError(
                    "No mode provided for channel {}. "
                    "Please provide a Single, Doublet or Triplet mode to stimulate pulse by pulse. "
                    "Specific stimulation points are not supported by this method.".format(
                        channel._no_channel
                    )
                )

        nb_pulses = check_stimulation_parameter_list(
            upd_list_channels, pulse_width_list, "pulse width"
        )
        if amplitude_list is not None:
            nb_amplitudes = check_stimulation_parameter_list(
                upd_list_channels, amplitude_list, "amplitude"
            )
            if nb_amplitudes != nb_pulses:
                raise ValueError(
                    "Error : the pulse width and amplitude lists must have the same length, "
                    "given lengths : %s and %s." % (nb_pulses, nb_amplitudes)
                )
        if pulse_interval_list is not None:
            check_pulse_interval_list(pulse_interval_list, nb_pulses)

        if stop_condition is not None and not callable(stop_condition):
            raise TypeError("Please provide a callable for stop_condition")

        self.list_channels = upd_list_channels
        self.ml_update.packet_number = self.get_next_packet_number()

        for pulse_index in range(nb_pulses):
            if stop_condition is not None and stop_condition():
                break
            tic = time.time()

            for channel in upd_list_channels:
                if amplitude_list is not None:
                    channel.set_amplitude(
                        amplitude_list[channel.get_no_channel()][pulse_index]
                    )
                if pulse_interval_list is not None:
                    channel.set_frequency(1000.0 / pulse_interval_list[pulse_index])
                channel.set_pulse_width(
                    pulse_width_list[channel.get_no_channel()][pulse_index]
                )

            self._send_stimulation_update()
            self._get_current_data()
            self._get_last_ack()
            self.check_stimulation_errors()

            if pulse_interval_list is None:
                time.sleep(0.005)
            else:
                #  Wait for the remaining time of the pulse interval, the device stimulates in the meantime.
                pulse_duration = time.time() - tic
                time.sleep(
                    max(pulse_interval_list[pulse_index] / 1000 - pulse_duration, 0)
                )

        self.pause_stimulation()
        self.stimulation_started = True

    def pause_stimulation(self):
        """
        Pause the mid-level stimulation on the P24 device by setting all points to zero amplitude.
        """
        if self.list_channels is None:
            raise RuntimeError("No channels initialized for pausing stimulation.")

        original_points = {}
        for channel in self.list_channels:
            original_points[channel._no_channel] = [
                Point(point.pulse_width, point.amplitude)
                for point in channel.list_point
            ]
            for point in channel.list_point:
                point.amplitude = 0

        self._send_stimulation_update()
        for channel in self.list_channels:
            channel.list_point = original_points[channel._no_channel]

    def _send_stimulation_update(self):
        """
        Send the current stimulation configuration to the device.
        """

        for channel in self.list_channels:
            channel_index = channel._no_channel - 1
            self.ml_update.enable_channel[channel_index] = True
            self.ml_update.channel_config[channel_index].period = channel._period
            self.ml_update.channel_config[channel_index].ramp = channel._ramp
            self.ml_update.channel_config[channel_index].number_of_points = len(
                channel.list_point
            )
            for j, point in enumerate(channel.list_point):
                self.ml_update.channel_config[channel_index].points[
                    j
                ].time = point.pulse_width
                self.ml_update.channel_config[channel_index].points[
                    j
                ].current = point.amplitude

        if not sciencemode.lib.smpt_send_ml_update(self.device, self.ml_update):
            raise RuntimeError("Failed to send stimulation update")
        self.log(
            "Stimulation started",
            "Command sent to rehastim: {}".format(
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Ml_Update).name
            ),
        )
        self._get_last_ack()

    def update_stimulation(
        self,
        upd_list_channels: list,
        stimulation_duration: int | float = None,
        wait: bool = False,
        timeout: float = 1.0,
    ) -> int | None:
        """
        Update the ml stimulation on the device with new channel configurations.

        If a non-blocking stimulation is running (start_stimulation(..., blocking=False)), the new parameters are
        copied and queued for the stimulation thread and the method returns immediately. It is thread safe and
        can be called from any thread, including the callback. If several updates are queued before the thread
        sends them, only the latest one is sent. Otherwise, the blocking start_stimulation is called again.

        Parameters
        ----------
        upd_list_channels : list
            Channels to stimulate.
        stimulation_duration : int | float
            Duration of the updated stimulation in seconds. In non-blocking mode, the stimulation stops this
            duration after the call (None keeps the current end, if any).
        wait : bool
            Non-blocking mode only. If True, return once the device acknowledged the update.
        timeout : float
            Non-blocking mode only. Maximum time in s to wait for the ack when wait is True.

        Returns
        -------
        In non-blocking mode, the sequence number of the update (see StimulationEvent.seq), None otherwise.
        """
        self.check_stimulation_thread()
        continuous = self._continuous
        if continuous is not None and continuous.is_alive():
            if stimulation_duration is not None and not isinstance(
                stimulation_duration, int | float
            ):
                raise TypeError(
                    "Please provide a int or float type for stimulation duration"
                )
            self._check_update_channels(upd_list_channels, self._safety)
            self.list_channels = upd_list_channels
            seq = continuous.request_update(
                snapshot_channels(upd_list_channels), stimulation_duration
            )
            if wait:
                continuous.wait_applied(seq, timeout)
            return seq
        if continuous is not None:  # The thread ended normally (stimulation_duration elapsed)
            self._continuous = None
            raise RuntimeError(
                "The non-blocking stimulation has ended (stimulation_duration elapsed). "
                "Call start_stimulation(..., blocking=False) to start it again."
            )

        if stimulation_duration is not None:
            self._current_stim_duration = stimulation_duration

        self.start_stimulation(
            upd_list_channels, self._current_stim_duration, self._safety
        )

    def end_stimulation(self):
        """
        Stop the mid level stimulation (after stopping the non-blocking stimulation thread, if any).
        """
        #  The thread error, if any, is raised after Ml_stop has been sent.
        continuous_error = None
        try:
            self._stop_continuous(pause=False)
        except Exception as e:
            continuous_error = e
        packet_number = self.get_next_packet_number()

        if not sciencemode.lib.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("Failure to stop stimulation.")
        self.log(
            "Stimulation stopped",
            "Command sent to rehastim: {}".format(
                self.P24Commands(sciencemode.lib.Smpt_Cmd_Ml_Stop).name
            ),
        )
        self._get_last_ack()
        self.stimulation_started = False
        if continuous_error is not None:
            raise continuous_error

    def check_stimulation_errors(self):
        """
        Check if there is an error during the mid level stimulation.
        """

        sciencemode.lib.smpt_get_ml_get_current_data_ack(
            self.device, self.ml_get_current_data_ack
        )
        for channel in self.list_channels:
            channel_number = channel._no_channel
            channel_state_index = channel_number - 1

            channel_state = self.ml_get_current_data_ack.channel_data.channel_state[
                channel_state_index
            ]
            if channel_state != sciencemode.lib.Smpt_Ml_Channel_State_Ok:
                if (
                    channel_state
                    == sciencemode.lib.Smpt_Ml_Channel_State_Electrode_Error
                ):
                    error_message = f"Electrode error on channel {channel_number}"
                elif (
                    channel_state == sciencemode.lib.Smpt_Ml_Channel_State_Timeout_Error
                ):
                    error_message = f"Timeout error on channel {channel_number}"
                elif (
                    channel_state
                    == sciencemode.lib.Smpt_Ml_Channel_State_Low_Current_Error
                ):
                    error_message = f"Low current error on channel {channel_number}"
                elif channel_state == sciencemode.lib.Smpt_Ml_Channel_State_Last_Item:
                    error_message = f"Last item error on channel {channel_number}"
                else:
                    error_message = f"Unknown error on channel {channel_number}"
                raise RuntimeError(error_message)

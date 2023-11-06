
import time
from pyScienceMode2.utils import check_unique_channel, calc_electrode_number, generic_error_check
from pyScienceMode2 import RehastimGeneric
from sciencemode_p24 import sciencemode



class RehastimP24(RehastimGeneric):
    """
    Class used for the communication with RehastimP24.
    """

    ERROR_MAP = {
        0: None,
        1: "Transfer error.",
        2: "Parameter error.",
        3: "Protocol error.",
        5: "Timeout error.",
        7: "Current level not initialized. Close the current level or initialize it.",
        10: "Electrode error.",
        11: "Invalid command error.",
    }

    def __init__(self, port: str, show_log: bool | str = False):
        """
        Creates an object stimulator for the RehastimP24.

        Parameters
        ----------
        port : str
            Port of the computer connected to the Rehastim.
        show_log: bool | str
            If True, all logs of the communication will be printed.
            If "Partial", only basic logs will be printed.
            If False, no logs will be printed.
        """
        if show_log not in [True, False, "Partial"]:
            raise ValueError("show_log must be True, False, or 'Partial'.")

        self.list_channels = None
        self.electrode_number = 0
        self.stimulation_started = None
        self.show_log = show_log
        self._current_no_channel = None
        self._current_stim_sequence = None
        self._current_pulse_interval = None
        self.device_type = "RehastimP24"
        self._safety = True

        super().__init__(port, device_type=self.device_type, show_log=self.show_log)

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
            print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Get_Extended_Version).name)
        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_extended_version_ack(self.device, extended_version_ack)
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
            print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Get_Device_Id).name)

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
        from pyScienceMode2.enums import HighVoltage
        stim_status_ack = sciencemode.ffi.new("Smpt_get_stim_status_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.lib.smpt_send_get_stim_status(self.device, packet_number)

        if self.show_log is True:
            print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Get_Stim_Status).name)

        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_stim_status_ack(self.device, stim_status_ack)
        stim_status = f"stim status : {stim_status_ack.stim_status}"
        voltage_level = f"voltage level : {HighVoltage(stim_status_ack.high_voltage_level).name}"
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
            print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Get_Battery_Status).name)

        self._get_last_ack()
        ret = sciencemode.lib.smpt_get_get_battery_status_ack(self.device, battery_status_ack)
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
            print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Get_Main_Status).name)

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
            print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Reset).name)
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

        connectors = [sciencemode.lib.Smpt_Connector_Yellow, sciencemode.lib.Smpt_Connector_Green]

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
            "Command sent to rehastim: {}".format(self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ll_Init).name),
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

    def start_ll_channel_config(
        self,
        no_channel: int,
        points=list,
        stim_sequence: int = 1,
        pulse_interval: int | float = 50,
        safety: bool = True,
    ):
        from pyScienceMode2 import Point
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
        self._current_no_channel = no_channel
        self._current_stim_sequence = stim_sequence
        self._current_pulse_interval = pulse_interval
        self.log("Low level stimulation started")
        positive_area = 0
        negative_area = 0

        if not isinstance(points, list):
            raise TypeError("points must be a list.")
        if not points:
            raise ValueError("Please provide at least one point for stimulation.")
        if not all(isinstance(point, Point) for point in points):
            raise TypeError("All items in the points list must be instances of the Point class.")

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
                raise ValueError("The points are not symmetric based on amplitude.")

        for _ in range(stim_sequence):
            ll_config.packet_number = self.get_next_packet_number()
            sciencemode.lib.smpt_send_ll_channel_config(self.device, ll_config)
            if self.show_log is True:
                print("Command sent to rehastim:", self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ll_Channel_Config).name)
            time.sleep(pulse_interval / 1000)
            self._get_last_ack()
            self.check_ll_channel_config_ack()

    def check_ll_channel_config_ack(self):
        """
        Check the low level channel config status.
        """
        if not sciencemode.lib.smpt_get_ll_channel_config_ack(self.device, self.ll_channel_config_ack):
            raise ValueError("Failed to get the ll_channel_config_ack.")
        generic_error_check(self.ll_channel_config_ack)

    def update_ll_channel_config(
        self, upd_list_point, no_channel=None, stim_sequence: int = None, pulse_interval: int | float = None
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
        self.start_ll_channel_config(no_channel, upd_list_point, stim_sequence, pulse_interval)

    def ll_stop(self):
        """
        Stop the device lower level.
        """
        packet_number = self.get_next_packet_number()
        if not sciencemode.lib.smpt_send_ll_stop(self.device, packet_number):
            raise RuntimeError("Low level stop failed.")
        self.log(
            "Low level stopped",
            "Command sent to rehastim: {}".format(self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ll_Stop).name),
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
            "Command sent to rehastim: {}".format(self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ml_Init).name),
        )
        self._get_last_ack()

    def start_stimulation(self, upd_list_channels: list, stimulation_duration: int | float = None, safety: bool = True):
        """
        Start the mid level stimulation on the device.

        Parameters
        ----------
        stimulation_duration : int | float
            Duration of the stimulation in seconds.
        upd_list_channels : list
            Channels to stimulate.
        safety : bool
            Set to True if you want to check the pulse symmetry. False otherwise.
        """
        if not stimulation_duration:
            raise ValueError("Please indicate the stimulation duration")

        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError("Error update: all channels have not been initialised")

        self.list_channels = upd_list_channels
        self._safety = safety
        ml_update = sciencemode.ffi.new("Smpt_ml_update*")
        ml_update.packet_number = self.get_next_packet_number()

        for channel in upd_list_channels:
            if safety and not channel.is_pulse_symmetric():
                raise ValueError(
                    f"Pulse for channel {channel._no_channel} is not symmetric. "
                    f"Please put the same positive and negative current."
                )
            #  Check if points are provided for each channel stimulated
            if not channel.list_point:
                raise ValueError(
                    "No stimulation point provided for channel {}. "
                    "Please either provide an amplitude and pulse width for a biphasic stimulation."
                    "Or specify specific stimulation points.".format(channel._no_channel)
                    )
            channel_index = channel._no_channel - 1
            ml_update.enable_channel[channel_index] = True
            ml_update.channel_config[channel_index].period = channel._period
            ml_update.channel_config[channel_index].ramp = channel._ramp
            ml_update.channel_config[channel_index].number_of_points = len(channel.list_point)
            for j, point in enumerate(channel.list_point):
                ml_update.channel_config[channel_index].points[j].time = point.pulse_width
                ml_update.channel_config[channel_index].points[j].current = point.amplitude

        if not sciencemode.lib.smpt_send_ml_update(self.device, ml_update):
            raise RuntimeError("Failed to start stimulation")
        self.log(
            "Stimulation started",
            "Command sent to rehastim: {}".format(self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ml_Update).name),
        )
        self._get_last_ack()

        # This code is used to set the stimulation duration
        total_time = 0
        while total_time < stimulation_duration:
            self._get_current_data()
            self.check_stimulation_errors()
            sleep_time = min(1, stimulation_duration - total_time)
            time.sleep(sleep_time)
            total_time += sleep_time
            self._get_last_ack()
        self.stimulation_started = True

    def update_stimulation(self, upd_list_channels: list, stimulation_duration: int | float = None):
        """
        Update the ml stimulation on the device with new channel configurations.

        Parameters
        ----------
        upd_list_channels : list
            Channels to stimulate.
        stimulation_duration : int | float
            Duration of the updated stimulation in seconds.
        """

        self.start_stimulation(upd_list_channels, stimulation_duration,self._safety)

    def end_stimulation(self):
        """
        Stop the mid level stimulation.
        """
        packet_number = self.get_next_packet_number()

        if not sciencemode.lib.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("Failure to stop stimulation.")
        self.log(
            "Stimulation stopped",
            "Command sent to rehastim: {}".format(self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ml_Stop).name),
        )
        self._get_last_ack()
        self.stimulation_started = False

    def check_stimulation_errors(self):
        """
        Check if there is an error during the mid level stimulation.
        """

        sciencemode.lib.smpt_get_ml_get_current_data_ack(self.device, self.ml_get_current_data_ack)

        num_channels = len(self.list_channels)
        for j in range(num_channels):
            channel_state = self.ml_get_current_data_ack.channel_data.channel_state[j]
            if channel_state != sciencemode.lib.Smpt_Ml_Channel_State_Ok:
                if channel_state == sciencemode.lib.Smpt_Ml_Channel_State_Electrode_Error:
                    error_message = f"Electrode error on channel {j+1}"
                elif channel_state == sciencemode.lib.Smpt_Ml_Channel_State_Timeout_Error:
                    error_message = f"Timeout error on channel {j+1}"
                elif channel_state == sciencemode.lib.Smpt_Ml_Channel_State_Low_Current_Error:
                    error_message = f"Low current error on channel {j+1}"
                elif channel_state == sciencemode.lib.Smpt_Ml_Channel_State_Last_Item:
                    error_message = f"Last item error on channel {j+1}"
                else:
                    error_message = f"Unknown error on channel {j+1}"

                raise RuntimeError(error_message)

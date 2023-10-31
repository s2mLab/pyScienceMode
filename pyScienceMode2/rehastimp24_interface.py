from sciencemode import sciencemode
from pyScienceMode2.sciencemode import RehastimGeneric
from pyScienceMode2.utils import *
import time


class StimulatorP24(RehastimGeneric):

    """
    Class used for the communication with RehastimP24.
    """

    MAX_PACKET_BYTES = 69
    STUFFED_BYTES = [240, 15, 129, 85, 10]
    BAUD_RATE = 3000000
    HIGH_VOLTAGE_MAPPING = {
        5: "Smpt_High_Voltage_120V",
        6: "Smpt_High_Voltage_150V",
        2: "Smpt_High_Voltage_30V",
        3: "Smpt_High_Voltage_60V",
        4: "Smpt_High_Voltage_90V",
        0: "Smpt_High_Voltage_Default"
    }
    ERROR_MAP = {
        0: None,
        1: "Transfer error.",
        2: "Parameter error.",
        3: "Protocol error.",
        5: "Timeout error.",
        7: "Current level not initialized. Close the current level or initialize it.",
        10: "Electrode error.",
        11: "Invalid command error."
    }

    def __init__(self, port: str, show_log: bool = False):
        """
        Creates an object stimulator for the RehastimP24.

        Parameters
        ----------
        port : str
            Port of the computer connected to the Rehastim.
        show_log: bool
            If True, the log of the communication will be printed.
        """

        self.list_channels = None
        self.electrode_number = 0
        self.stimulation_started = None
        self.show_log = show_log
        self._current_no_channel = None
        self._current_stim_sequence = None
        self._current_pulse_interval = None

        super().__init__(port, show_log, device_type="RehastimP24")

    #  General level commands
    def get_extended_version(self) -> bool:
        """
        Get the extended version of the device. General Level command.

        Returns
        -------
        bool
            True if the command was successful, False otherwise.
        """
        extended_version_ack = sciencemode.ffi.new("Smpt_get_extended_version_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.smpt_send_get_extended_version(self.device, packet_number)
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Get_Extended_Version).name)
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_extended_version_ack(self.device, extended_version_ack)
        print("get extended version", ret)
        print("fw_hash :", extended_version_ack.fw_hash)
        # print("uc_version", extended_version_ack.uc_version)
        return ret

    def get_device_id(self) -> bool:
        """
        Get the device id.

        Returns
        -------
        bool
            True if the command was successful, False otherwise. General Level command.
        """
        device_id_ack = sciencemode.ffi.new("Smpt_get_device_id_ack*")
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
        ret = sciencemode.smpt_send_get_device_id(self.device, packet_number)
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Get_Device_Id).name)
        ret = False
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_device_id_ack(self.device, device_id_ack)
        print("get device id", ret)
        print("device id :", device_id_ack.device_id)
        return ret

    def get_stim_status(self) -> bool:
        """
        Get the stimulation status. General Level command.

        Returns
        -------
        bool
            True if the command was successful, False otherwise.
        """
        stim_status_ack = sciencemode.ffi.new("Smpt_get_stim_status_ack*")
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
        ret = sciencemode.smpt_send_get_stim_status(self.device, packet_number)
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Get_Stim_Status).name)
        ret = False
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_stim_status_ack(self.device, stim_status_ack)
        print("get stim status", ret)
        print("stim status :", stim_status_ack.stim_status)
        print("High voltage level :", self.HIGH_VOLTAGE_MAPPING.get(stim_status_ack.high_voltage_level, "Unknown"))
        return ret

    def get_battery_status(self) -> bool:
        """
        Get the battery status. General Level command.

        Returns
        -------
        bool
            True if the command was successful, False otherwise.
        """
        battery_status_ack = sciencemode.ffi.new("Smpt_get_battery_status_ack*")
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
        ret = sciencemode.smpt_send_get_battery_status(self.device, packet_number)
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Get_Battery_Status).name)
        ret = False
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_battery_status_ack(self.device, battery_status_ack)
        print("get battery status", ret)
        print("battery level :", battery_status_ack.battery_level)
        print("battery voltage :", battery_status_ack.battery_voltage)
        return ret

    def get_main_status(self) -> bool:
        """
        Get the main status. General Level command.

        Returns
        -------
        bool
            True if the command was successful, False otherwise.
        """
        main_status_ack = sciencemode.ffi.new("Smpt_get_main_status_ack*")
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
        ret = sciencemode.smpt_send_get_main_status(self.device, packet_number)
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Get_Main_Status).name)
        ret = False
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_main_status_ack(self.device, main_status_ack)
        print("get main status", ret)
        print("main status :", main_status_ack.main_status)
        return ret

    def reset(self) -> bool:
        """
        Reset the device. General Level command.

        Returns
        -------
        bool
            True if the command was successful, False otherwise.
        """
        packet_number = self.get_next_packet_number()
        ret = sciencemode.smpt_send_reset(self.device, packet_number)
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Reset).name)
        ret = False
        self._get_last_ack()
        return ret

    def get_all(self) -> bool:
        """
        Get all the device information. General Level command.

        Returns
        -------
        bool
            True if all the commands were successful, False otherwise.
        """
        extended_version_success = self.get_extended_version()
        device_id_success = self.get_device_id()
        stim_status_success = self.get_stim_status()
        battery_status_success = self.get_battery_status()
        main_status_success = self.get_main_status()

        return extended_version_success and device_id_success and stim_status_success and battery_status_success and main_status_success

    @staticmethod
    def channel_number_to_channel_connector(no_channel):
        """
        Converts the channel number to the corresponding channel and connector.

        Parameters
        ----------
        no_channel : int
            The channel number.

        Returns
        -------
        channel and connector
        """
        channels = [
            sciencemode.Smpt_Channel_Red,
            sciencemode.Smpt_Channel_Blue,
            sciencemode.Smpt_Channel_Black,
            sciencemode.Smpt_Channel_White
        ]

        connectors = [
            sciencemode.Smpt_Connector_Yellow,
            sciencemode.Smpt_Connector_Green
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
        Each stimulation pulse needs to triggered from the PC.
        """
        ll_init = sciencemode.ffi.new("Smpt_ll_init*")
        ll_init.high_voltage_level = sciencemode.Smpt_High_Voltage_Default  # This switches on the high voltage source
        ll_init.packet_number = self.get_next_packet_number()

        if not sciencemode.smpt_send_ll_init(self.device, ll_init):
            raise RuntimeError("Ll initialization failed.")
        print("lower level initialized")
        self.get_next_packet_number()
        self._get_last_ack()
        self.check_ll_init_ack()

    def check_ll_init_ack(self):
        if not sciencemode.smpt_get_ll_init_ack(self.device, self.ll_init_ack) :
            raise RuntimeError("Ll initialization failed.")
        generic_error_check(self.ll_init_ack, self.ERROR_MAP)

    def start_ll_channel_config(self, no_channel, points=None, stim_sequence: int = None, pulse_interval: int = None):
        """
        Starts the stimulation in Low Level mode.

        Parameters
        ----------
        no_channel : int
            The channel number.
        points : list
            Points to stimulate.
        stim_sequence : int
            Number of stimulation sequence.
        pulse_interval : int
            Interval between each stimulation sequence.
       """
        self._current_no_channel = no_channel
        self._current_stim_sequence = stim_sequence
        self._current_pulse_interval = pulse_interval

        if points is None or len(points) == 0:
            raise ValueError("Please provide at least one point for stimulation.")
        channel, connector = self.channel_number_to_channel_connector(no_channel)
        ll_config = sciencemode.ffi.new("Smpt_ll_channel_config*")

        ll_config.enable_stimulation = True
        ll_config.channel = channel
        ll_config.connector = connector
        ll_config.number_of_points = len(points)

        for j, point in enumerate(points):
            ll_config.points[j].time = point.pulse_width
            ll_config.points[j].current = point.amplitude

        for _ in range(stim_sequence):
            ll_config.packet_number = self.get_next_packet_number()
            sciencemode.smpt_send_ll_channel_config(self.device, ll_config)
            time.sleep(pulse_interval/1000)
            self._get_last_ack()
            self.check_ll_channel_config_ack()

    def check_ll_channel_config_ack(self):
        """
        Check if there is an error during the ll stimulation.
        """
        if not sciencemode.smpt_get_ll_channel_config_ack(self.device, self.ll_channel_config_ack):
            raise ValueError("Failed to get the ll_channel_config_ack.")

    def update_ll_channel_config(self, upd_list_point, no_channel=None, stim_sequence: int = None, pulse_interval: int = None):
        """
        Update the stimulation in Low Level mode.

        Parameters
        ----------
        upd_list_point : list
            Points to update.
        no_channel : int
            The channel number.
        stim_sequence : int
            Number of stimulation sequence.
        pulse_interval : int
            Interval between each stimulation sequence.
        """
        if stim_sequence is None:
            stim_sequence = self._current_stim_sequence
        if no_channel is None:
            no_channel = self._current_no_channel
        if pulse_interval is None:
            pulse_interval = self._current_pulse_interval
        self.start_ll_channel_config(no_channel, upd_list_point, stim_sequence,pulse_interval)

    def ll_stop(self):
        """
        Stop the lower level of the device.
        generic_error_check(self.ll_channel_config_ack, self.ERROR_MAP)
        """
        packet_number = self.get_next_packet_number()
        if not sciencemode.smpt_send_ll_stop(self.device, packet_number):
            raise RuntimeError("Ll stop failed.")
        print("lower level stopped")
        self._get_last_ack()

    def init_stimulation(self, list_channels: list):
        """
        Initialize the ml stimulation on the device. The mid-level  is used for defining a stimulation pattern
        """
        if self.stimulation_started:
            self.stop_stimulation()
        self.list_channels = list_channels
        check_unique_channel(list_channels)
        self.electrode_number = calc_electrode_number(self.list_channels)

        ml_init = sciencemode.ffi.new("Smpt_ml_init*")
        ml_init.stop_all_channels_on_error = True  # if true all channels will stop if one channel has an error
        ml_init.packet_number = self.get_next_packet_number()

        if not sciencemode.smpt_send_ml_init(self.device, ml_init):
            raise RuntimeError("failed to start stimulation")
        print("Stimulation initialized")
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Ml_Init).name)
        self._get_last_ack()

    def start_stimulation(self, upd_list_channels: list, stimulation_duration: float = None):
        """
        Start the ml stimulation on the device.

        Parameters
        ----------
        stimulation_duration : float
            Duration of the stimulation in seconds.
        upd_list_channels : list
            Channels to stimulate.
        """
        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError("Error update: all channels have not been initialised")
        self.list_channels = upd_list_channels

        ml_update = sciencemode.ffi.new("Smpt_ml_update*")
        ml_update.packet_number = self.get_next_packet_number()

        #  Check if points are provided for each channel stimulated

        for channel in upd_list_channels:
            if not channel.list_point:
                raise ValueError(
                    "No stimulation point provided for channel {}. Please either provide an amplitude and pulse width for a biphasic stimulation, or specify specific stimulation points.".format(
                        channel._no_channel))
            channel_index = channel._no_channel - 1
            ml_update.enable_channel[channel_index] = True
            ml_update.channel_config[channel_index].period = channel._period
            ml_update.channel_config[channel_index].ramp = channel._ramp
            ml_update.channel_config[channel_index].number_of_points = len(channel.list_point)
            for j, point in enumerate(channel.list_point):
                ml_update.channel_config[channel_index].points[j].time = point.pulse_width
                ml_update.channel_config[channel_index].points[j].current = point.amplitude

        if not sciencemode.smpt_send_ml_update(self.device, ml_update):
            raise RuntimeError("failed to start stimulation")
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Ml_Update).name)
        print("Stimulation started")

        self._get_last_ack()

        # This code is used to set the stimulation duration

        ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")
        number_of_polls = int(stimulation_duration) if stimulation_duration is not None else 1
        for i in range(number_of_polls):
            ml_get_current_data.data_selection = sciencemode.Smpt_Ml_Data_Channels
            ml_get_current_data.packet_number = self.get_next_packet_number()
            ret = sciencemode.smpt_send_ml_get_current_data(self.device, ml_get_current_data)
            if ret:
                pass
            else:
                print("Failed to get current data.")
            print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Ml_Get_Current_Data).name)
            self.check_stimulation_errors()
            time.sleep(1)

            self._get_last_ack()
        self.stimulation_started = True

    def update_stimulation(self, upd_list_channels: list, stimulation_duration: float = None):
        """
        Update the ml stimulation on the device with new channel configurations.

        Parameters
        ----------
        upd_list_channels : list
            Channels to stimulate.
        stimulation_duration : float, optional
            Duration of the updated stimulation in seconds.
        """

        if self.stimulation_started:
            self.stop_stimulation()

        self.start_stimulation(upd_list_channels, stimulation_duration)

    def stop_stimulation(self):
        """
        Stop the ml stimulation.
        """
        packet_number = self.get_next_packet_number()

        if not sciencemode.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("failure to stop stimulation.")
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Ml_Stop).name)
        self._get_last_ack()
        self.stimulation_started = False

        print("Stimulation stopped.")

    def check_stimulation_errors(self):
        """
        Check if there is an error during the ml stimulation.
        """

        sciencemode.smpt_get_ml_get_current_data_ack(self.device, self.ml_get_current_data_ack)

        num_channels = len(self.list_channels)
        for j in range(num_channels):
            channel_state = self.ml_get_current_data_ack.channel_data.channel_state[j]
            if channel_state != sciencemode.Smpt_Ml_Channel_State_Ok:
                if channel_state == sciencemode.Smpt_Ml_Channel_State_Electrode_Error:
                    error_message = f"Electrode error on channel {j+1}"
                elif channel_state == sciencemode.Smpt_Ml_Channel_State_Timeout_Error:
                    error_message = f"Timeout error on channel {j+1}"
                elif channel_state == sciencemode.Smpt_Ml_Channel_State_Low_Current_Error:
                    error_message = f"Low current error on channel {j+1}"
                elif channel_state == sciencemode.Smpt_Ml_Channel_State_Last_Item:
                    error_message = f"Last item error on channel {j+1}"
                else:
                    error_message = f"Unknown error on channel {j+1}"

                raise RuntimeError(error_message)



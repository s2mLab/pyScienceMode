"""
Stimulator Interface class used to control the rehamove2.
See ScienceMode2 - Description and protocol for more information.
"""
from typing import Tuple
import time
from pyScienceMode2.acks import *
from pyScienceMode2 import channel
from pyScienceMode2.utils import *
from pyScienceMode2.sciencemode import RehastimGeneric
from pyScienceMode2.motomed_interface import _Motomed
from sciencemode_p24 import sciencemode


class Stimulator2(RehastimGeneric):
    """
    Class used for the communication with Rehastim2.
    """

    def __init__(
        self,
        port: str,
        show_log: bool = False,
        with_motomed: bool = False
    ):
        """
        Creates an object stimulator.

        Parameters
        ----------
        port : str
            Port of the computer connected to the Rehastim2.
        show_log: bool
            If True, the log of the communication will be printed.
        with_motomed: bool
            If the motomed is connected to the Rehastim, put this flag to True.
        """
        self.list_channels = None
        self.stimulation_interval = None
        self.inter_pulse_interval = 2
        self.low_frequency_factor = 0
        self.electrode_number = 0
        self.electrode_number_low_frequency = 0

        self.amplitude = []
        self.pulse_width = []
        self.mode = []
        self.muscle = []
        self.given_channels = []
        self.stimulation_started = None
        self.device_type = "Rehastim2"

        super().__init__(port, show_log, with_motomed, device_type=self.device_type)

        if with_motomed:
            self.motomed = _Motomed(self)

        # Connect to rehastim
        packet = None
        while packet is None:
            packet = self._get_last_ack(init=True)

        self.send_generic_packet("InitAck", packet=self._init_ack(packet[5]))

    def set_stimulation_signal(self, list_channels: list):
        """
        Sets or updates the stimulation's parameters.

        Parameters
        ----------
        list_channels: list[channel]
            Contain the channels and their parameters.
        """
        self.amplitude = []
        self.pulse_width = []
        self.mode = []
        self.muscle = []
        self.given_channels = []

        check_list_channel_order(list_channels)

        for i in range(len(list_channels)):
            self.amplitude.append(list_channels[i].get_amplitude())
            self.pulse_width.append(list_channels[i].get_pulse_width())
            self.mode.append(list_channels[i].get_mode())
            self.given_channels.append(list_channels[i].get_no_channel())

    def _send_packet(self, cmd: str) -> str:
        """
        Calls the methode that construct the packet according to the command.

        Parameters
        ----------
        cmd: str
            Command that will be sent.

        Returns
        -------
        In the case of an InitAck, return the string 'InitAck'.
        """

        packet = [-1]
        if cmd == "GetStimulationMode":
            packet = packet_construction(self.packet_count, "GetStimulationMode")
        elif cmd == "InitChannelListMode":
            packet = self._packet_init_stimulation()
        elif cmd == "StartChannelListMode":
            packet = self._packet_start_stimulation()
        elif cmd == "StopChannelListMode":
            packet = packet_construction(self.packet_count, "StopChannelListMode")
        self.motomed_done.set()
        init_ack = self.send_generic_packet(cmd, packet)
        if init_ack:
            return init_ack

    def _calling_ack(self, packet) -> str:
        """
        Processing ack from rehastim

        Parameters
        ----------
        packet:
            Packet which needs to be processed.

        Returns
        -------
        A string which is the message corresponding to the processing of the packet.
        """
        if packet == "InitAck" or packet[6] == 1:
            return "InitAck"
        elif packet[6] == self.TypeReha2["GetStimulationModeAck"].value:
            return get_mode_ack(packet)
        elif packet[6] == self.TypeReha2["InitChannelListModeAck"].value:
            return init_stimulation_ack(packet)
        elif packet[6] == self.TypeReha2["StopChannelListModeAck"].value:
            return stop_stimulation_ack(packet)
        elif packet[6] == self.TypeReha2["StartChannelListModeAck"].value:
            return start_stimulation_ack(packet)
        elif packet[6] == self.TypeReha2["StimulationError"].value:
            return rehastim_error(signed_int(packet[7:8]))
        elif packet[6] == self.TypeReha2["ActualValues"].value:
            raise RuntimeError("Motomed is connected, so put the flag with_motomed to True.")
        else:
            raise RuntimeError(f"Error packet : not understood {packet[6]}")

    def _packet_init_stimulation(self) -> bytes:
        """
        Returns the packet for the InitChannelMode.
        """
        coded_inter_pulse_interval = int((self.inter_pulse_interval - 1.5) * 2)
        msb, lsb = self._msb_lsb_main_stim()

        data_stimulation = [
            self.low_frequency_factor,
            self.electrode_number,
            self.electrode_number_low_frequency,
            coded_inter_pulse_interval,
            msb,
            lsb,
            0,
        ]

        packet = packet_construction(self.packet_count, "InitChannelListMode", data_stimulation)
        return packet

    def _packet_start_stimulation(self) -> bytes:
        """
        Returns the packet for the StartChannelListMode.
        """
        data_stimulation = []
        for i in range(len(self.amplitude)):
            msb, lsb = self._msb_lsb_pulse_stim(self.pulse_width[i])
            data_stimulation.append(self.mode[i])
            data_stimulation.append(msb)
            data_stimulation.append(lsb)
            data_stimulation.append(int(self.amplitude[i]))
        packet = packet_construction(self.packet_count, "StartChannelListMode", data_stimulation)
        return packet

    def _msb_lsb_main_stim(self) -> Tuple[int, int]:
        """
        Returns the most significant bit (msb) and least significant bit (lsb) corresponding to the main stimulation
        interval.
        Main stimulation interval = [0, 2048] ∙ 0.5 ms + 1 ms
        Main stimulation interval = [1, 1025] ms
        Note that in the current software version the minimum main stimulation interval is 8 ms.
        (ScienceMode2 - Description and Protocol, 4.3 Stimulation Commands, InitChannelListMode)

        Returns
        -------
        (msb, lsb): tuple
            MSB and LSB of main stimulation interval
        """
        lsb = msb = -1
        stimulation_interval_coded = (self.stimulation_interval - 1) / 0.5
        if stimulation_interval_coded <= 255:
            lsb = stimulation_interval_coded
            msb = 0
        elif 256 <= stimulation_interval_coded <= 511:
            lsb = stimulation_interval_coded - 256
            msb = 1
        elif 512 <= stimulation_interval_coded <= 767:
            lsb = stimulation_interval_coded - 512
            msb = 2
        elif 768 <= stimulation_interval_coded <= 1023:
            lsb = stimulation_interval_coded - 768
            msb = 3
        elif 1024 <= stimulation_interval_coded <= 1279:
            lsb = stimulation_interval_coded - 1024
            msb = 4
        elif 1280 <= stimulation_interval_coded <= 1535:
            lsb = stimulation_interval_coded - 1280
            msb = 5
        elif 1536 <= stimulation_interval_coded <= 1791:
            lsb = stimulation_interval_coded - 1536
            msb = 6
        elif 1792 <= stimulation_interval_coded <= 2047:
            lsb = stimulation_interval_coded - 1792
            msb = 7
        elif stimulation_interval_coded == 2048:
            lsb = 0
            msb = 8

        return msb, int(lsb)

    @staticmethod
    def _msb_lsb_pulse_stim(pulse_width: int) -> Tuple[int, int]:
        """
        Returns MSB and LSB corresponding to the pulse width given.
        Range: [0, 500] μs (in current version [20, 500] μs, if (pw < 20) then pw = 20)
        (ScienceMode2 - Description and Protocol, 4.3 Stimulation Commands, StartChannelListMode)

        Parameters
        ----------
        pulse_width: int
            Pulse width of a signal.

        Returns
        -------
        (msb, lsb): tuple
            MSB and LSB of pulse_width.
        """
        msb = lsb = -1
        if pulse_width <= 255:
            lsb = pulse_width
            msb = 0
        elif 256 <= pulse_width <= 500:
            lsb = pulse_width - 256
            msb = 1
        return msb, lsb

    def init_channel(
        self,
        stimulation_interval: int,
        list_channels: list,
        inter_pulse_interval: int = 2,
        low_frequency_factor: int = 0,
    ):
        """
        Initialize the requested channel.
        Can update stimulation interval if one is given.
        Can update list_channels if one is iven.

        stimulation_interval: int
            Period of the main stimulation. [8,1025] ms.
        list_channels: list[Channel]
            List containing the channels and their parameters.
        """
        if self.stimulation_active:
            self.end_stimulation()

        check_stimulation_interval(stimulation_interval)
        check_unique_channel(list_channels)
        self.stimulation_interval = stimulation_interval
        self.list_channels = list_channels

        self.inter_pulse_interval = inter_pulse_interval
        check_inter_pulse_interval(inter_pulse_interval)

        self.low_frequency_factor = low_frequency_factor
        check_low_frequency_factor(low_frequency_factor)

        # Find electrode_number (according to Science_Mode2_Description_Protocol_20121212 p17)
        self.electrode_number = calc_electrode_number(self.list_channels)
        self.electrode_number_low_frequency = calc_electrode_number(self.list_channels, enable_low_frequency=True)

        self.set_stimulation_signal(self.list_channels)
        self._send_packet("InitChannelListMode")
        self._get_last_ack()

    def start_stimulation(self, stimulation_duration: float = None, upd_list_channels: list = None):
        """
        Update a stimulation.
        Warning: only the channel that has been initiated can be updated.

        Parameters
        ----------
        stimulation_duration: float
            Time of the stimulation after the update.
        upd_list_channels: list[channel]
            List of the channels that will be updated
        """

        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)

            # Verify if the updated channels have been initialised
            if new_electrode_number != self.electrode_number:
                raise RuntimeError("Error update: all channels have not been initialised")
            self.list_channels = upd_list_channels
            self.set_stimulation_signal(self.list_channels)
        self._send_packet("StartChannelListMode")
        time_start_stim = time.time()

        self._get_last_ack()
        self.stimulation_active = True

        if stimulation_duration is not None:
            if stimulation_duration < time.time() - time_start_stim:
                raise RuntimeError("Asked stimulation duration too short")
            time.sleep(stimulation_duration - (time.time() - time_start_stim))
            self.pause_stimulation()

    def pause_stimulation(self):
        """
        Update a stimulation.
        Warning: only the channel that has been initiated can be updated.
        """
        tmp_amp = self.amplitude
        self.amplitude = [0] * len(self.list_channels)
        self._send_packet("StartChannelListMode")
        self._get_last_ack()
        self.amplitude = tmp_amp

    def end_stimulation(self):
        """
        Stop a stimulation, after calling this method, init_channel must be used if stimulation need to be restarted.
        """
        self._send_packet("StopChannelListMode")
        self._get_last_ack()
        self.packet_count = 0

    def get_motomed_angle(self) -> float:
        """
        Get the angle of the Motomed.

        Returns
        -------
        angle: float
            Angle of the Motomed.
        """
        return self.get_angle()

    def get_motomed_speed(self) -> float:
        """
        Get the angle of the Motomed.

        Returns
        -------
        angle: float
            Angle of the Motomed.
        """
        return self.get_speed()

    def get_motomed_torque(self) -> float:
        """
        Get the angle of the Motomed.

        Returns
        -------
        angle: float
            Angle of the Motomed.
        """
        return self.get_torque()


class StimulatorP24(RehastimGeneric):
    """
    Class used for the communication with RehastimP24.
    """
    HIGH_VOLTAGE_MAPPING = {
        0: "Smpt_High_Voltage_Default",
        2: "Smpt_High_Voltage_30V",
        3: "Smpt_High_Voltage_60V",
        4: "Smpt_High_Voltage_90V",
        5: "Smpt_High_Voltage_120V",
        6: "Smpt_High_Voltage_150V"
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
        sciencemode.smpt_send_get_extended_version(self.device, packet_number)
        if self.show_log is True:
            print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Get_Extended_Version).name)
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_extended_version_ack(self.device, extended_version_ack)
        fw_hash = f"fw_hash :{extended_version_ack.fw_hash}"
        uc_version = f"uc_version : {extended_version_ack.uc_version} "
        return fw_hash, uc_version

    def get_device_id(self) -> tuple:
        """
        Get the device id.

        Returns
        -------
        device_id : str
            Device id.
        """
        device_id_ack = sciencemode.ffi.new("Smpt_get_device_id_ack*")
        packet_number = self.get_next_packet_number()
        sciencemode.smpt_send_get_device_id(self.device, packet_number)

        if self.show_log is True:
            print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Get_Device_Id).name)

        self._get_last_ack()
        ret = sciencemode.smpt_get_get_device_id_ack(self.device, device_id_ack)
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
        sciencemode.smpt_send_get_stim_status(self.device, packet_number)

        if self.show_log is True:
            print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Get_Stim_Status).name)

        self._get_last_ack()
        ret = sciencemode.smpt_get_get_stim_status_ack(self.device, stim_status_ack)
        stim_status = f"stim status : {stim_status_ack.stim_status}"
        voltage_level = f"voltage level : {self.HIGH_VOLTAGE_MAPPING.get(stim_status_ack.high_voltage_level,'Unknown')}"
        return stim_status,voltage_level

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
        sciencemode.smpt_send_get_battery_status(self.device, packet_number)

        if self.show_log is True:
            print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Get_Battery_Status).name)

        self._get_last_ack()
        ret = sciencemode.smpt_get_get_battery_status_ack(self.device, battery_status_ack)
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
        sciencemode.smpt_send_get_main_status(self.device, packet_number)

        if self.show_log is True:
            print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Get_Main_Status).name)

        self._get_last_ack()
        ret = sciencemode.smpt_get_get_main_status_ack(self.device, main_status_ack)
        main_status = f"main status : {main_status_ack.main_status}"
        return main_status

    def reset(self):
        """
        Reset the device. General Level command.
        """
        packet_number = self.get_next_packet_number()
        ret = sciencemode.smpt_send_reset(self.device, packet_number)

        if self.show_log is True:
            print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Reset).name)
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

        return extended_version_success ,device_id_success ,stim_status_success ,battery_status_success ,main_status_success

    @staticmethod
    def channel_number_to_channel_connector(no_channel):
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
        Each stimulation pulse needs to triggered from the computer.
        """
        ll_init = sciencemode.ffi.new("Smpt_ll_init*")
        ll_init.high_voltage_level = sciencemode.Smpt_High_Voltage_Default  # This switches on the high voltage source
        ll_init.packet_number = self.get_next_packet_number()

        if not sciencemode.smpt_send_ll_init(self.device, ll_init):
            raise RuntimeError("Low level initialization failed.")
        self.log("Low level initialized",
                 "Command sent to rehastim: {}".format(self.TypeRehap24(sciencemode.Smpt_Cmd_Ll_Init).name))

        self.get_next_packet_number()
        self._get_last_ack()
        self.check_ll_init_ack()

    def check_ll_init_ack(self):
        """
        Check the low level initialization status.
        """
        if not sciencemode.smpt_get_ll_init_ack(self.device, self.ll_init_ack):
            raise RuntimeError("Low level initialization failed.")
        generic_error_check(self.ll_init_ack, self.ERROR_MAP)

    def start_ll_channel_config(self, no_channel,
                                points=None, stim_sequence: int = None,
                                pulse_interval: int | float = None,
                                safety : bool = True):
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

        if safety is True:
            for point in points:
                if point.amplitude > 0:
                    positive_area += point.amplitude * point.pulse_width
                else :
                    negative_area -= point.amplitude * point.pulse_width
            if abs(positive_area - negative_area) > 1e-6:
                raise ValueError("The points are not symmetric based on amplitude.")

        for _ in range(stim_sequence):
            ll_config.packet_number = self.get_next_packet_number()
            sciencemode.smpt_send_ll_channel_config(self.device, ll_config)
            if self.show_log is True:
                print("Command sent to rehastim:", self.TypeRehap24(sciencemode.Smpt_Cmd_Ll_Channel_Config).name)
            time.sleep(pulse_interval/1000)
            self._get_last_ack()
            self.check_ll_channel_config_ack()

    def check_ll_channel_config_ack(self):
        """
        Check the low level channel config status.
        """
        if not sciencemode.smpt_get_ll_channel_config_ack(self.device, self.ll_channel_config_ack):
            raise ValueError("Failed to get the ll_channel_config_ack.")
        generic_error_check(self.ll_channel_config_ack, self.ERROR_MAP)

    def update_ll_channel_config(self, upd_list_point, no_channel=None, stim_sequence: int = None, pulse_interval: int | float = None):
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
        if not sciencemode.smpt_send_ll_stop(self.device, packet_number):
            raise RuntimeError("Low level stop failed.")
        self.log("Low level stopped", "Command sent to rehastim: {}".format(self.TypeRehap24(sciencemode.Smpt_Cmd_Ll_Stop).name))
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
            self.stop_stimulation()
        self.list_channels = list_channels
        check_unique_channel(list_channels)
        self.electrode_number = calc_electrode_number(self.list_channels)

        ml_init = sciencemode.ffi.new("Smpt_ml_init*")
        ml_init.stop_all_channels_on_error = stop_all_on_error
        ml_init.packet_number = self.get_next_packet_number()

        if not sciencemode.smpt_send_ml_init(self.device, ml_init):
            raise RuntimeError("Failed to start stimulation")
        self.log("Stimulation initialized", "Command sent to rehastim: {}".format(self.TypeRehap24(sciencemode.Smpt_Cmd_Ml_Init).name))
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
        if not stimulation_duration :
            raise ValueError("Please indicate the stimulation duration")
        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError("Error update: all channels have not been initialised")
        self.list_channels = upd_list_channels

        ml_update = sciencemode.ffi.new("Smpt_ml_update*")
        ml_update.packet_number = self.get_next_packet_number()

        #  Check if points are provided for each channel stimulated
        for channel in upd_list_channels:
            if not channel.is_pulse_symmetric(safety=safety):
                raise ValueError(f"Pulse for channel {channel._no_channel} is not symmetric. Please put the same positive and negative current.")
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
            raise RuntimeError("Failed to start stimulation")
        self.log("Stimulation started", "Command sent to rehastim: {}".format(self.TypeRehap24(sciencemode.Smpt_Cmd_Ml_Update).name))
        self._get_last_ack()

        # This code is used to set the stimulation duration
        ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")
        total_time = 0
        while total_time < stimulation_duration:
            self._get_current_data()
            self.check_stimulation_errors()
            sleep_time = min(1, stimulation_duration - total_time)
            time.sleep(sleep_time)
            total_time += sleep_time
            self._get_last_ack()
        self.stimulation_started = True

    def update_stimulation(self, upd_list_channels: list, stimulation_duration: int | float = None, safety: bool = True):
        """
        Update the ml stimulation on the device with new channel configurations.

        Parameters
        ----------
        upd_list_channels : list
            Channels to stimulate.
        stimulation_duration : int | float
            Duration of the updated stimulation in seconds.
        safety : bool
            Set to True if you want to check the pulse symmetry. False otherwise.
        """

        self.start_stimulation(upd_list_channels, stimulation_duration, safety)

    def stop_stimulation(self):
        """
        Stop the mid level stimulation.
        """
        packet_number = self.get_next_packet_number()

        if not sciencemode.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("Failure to stop stimulation.")
        self.log("Stimulation stopped", "Command sent to rehastim: {}".format(self.TypeRehap24(sciencemode.Smpt_Cmd_Ml_Stop).name))
        self._get_last_ack()
        self.stimulation_started = False

    def check_stimulation_errors(self):
        """
        Check if there is an error during the mid level stimulation.
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


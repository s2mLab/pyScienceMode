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
    Flow_Control = True

    def __init__(self, port: str, show_log: bool = False):
        """
        Creates an object stimulator for the rehastim P24.

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
        super().__init__(port, show_log, device_type = "RehastimP24")

    def get_extended_version(self) -> bool:
        """
        Get the extended version of the device.
        """
        extended_version_ack = sciencemode.ffi.new("Smpt_get_extended_version_ack*")
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
        ret = sciencemode.smpt_send_get_extended_version(self.device, packet_number)
        print("smpt_send_get_extended_version: {}", ret)
        ret = False
        self._get_last_ack()
        ret = sciencemode.smpt_get_get_extended_version_ack(self.device, extended_version_ack)
        print("smpt_get_get_extended_version_ack: {}", ret)
        print("fw_hash {} ", extended_version_ack.fw_hash)
        return ret

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

        self._get_last_ack()
        # # ll_init_ack = sciencemode.ffi.new("Smpt_ll_init_ack*")
        # # ll_init_ack.result = sciencemode.smpt_get_ll_init_ack(self.device,ll_init_ack)
        # # print("result {}", ll_init_ack.result)
        #
        # print("command number {}, packet_number {}", self.ack.command_number, self.ack.packet_number)

    def ll_stop(self):
        """
        Stop the lower level of the device.
        """
        packet_number = self.get_next_packet_number()
        if not sciencemode.smpt_send_ll_stop(self.device, packet_number):
            raise RuntimeError("Ll stop failed.")
        print("lower level stopped")
        self._get_last_ack()

    def init_stimulation(self, list_channels: list):
        """
        Initialize the ml stimulation on the device.
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
        print("Command sent to rehastim:" , self.Types(sciencemode.Smpt_Cmd_Ml_Init).name)
        self._get_last_ack()

    def start_stimulation(self, stimulation_duration: float = None, upd_list_channels: list = None):
        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError("Error update: all channels have not been initialised")
            self.list_channels = upd_list_channels

        ml_update = sciencemode.ffi.new("Smpt_ml_update*")
        ml_update.packet_number = self.get_next_packet_number()

        for channel in upd_list_channels:
            channel_index = channel._no_channel - 1
            ml_update.enable_channel[channel_index] = True
            ml_update.channel_config[channel_index].period = channel._period
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
        number_of_polls = int(stimulation_duration) if stimulation_duration is not None else 20
        for i in range(number_of_polls):
            ml_get_current_data.data_selection = sciencemode.Smpt_Ml_Data_Channels
            ml_get_current_data.packet_number = self.get_next_packet_number()
            ret = sciencemode.smpt_send_ml_get_current_data(self.device, ml_get_current_data)
            if ret:
                # print(f"Stimulated: {ret}")
                pass
            else:
                print("Failed to get current data.")
            print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Ml_Get_Current_Data).name)
            self.check_stimulation_errors()
            time.sleep(1)
            # try:
            #     self.check_stimulation_errors()
            # except RuntimeError as e:
            #     print(f"An error occurred during stimulation: {e}")

            self._get_last_ack()
        self.stimulation_started = True

    def stop_stimulation(self):
        """
        Stop the stimulation on the device
        """
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)

        if not sciencemode.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("failure to stop stimulation.")
        print("Command sent to rehastim:", self.Types(sciencemode.Smpt_Cmd_Ml_Stop).name)
        self._get_last_ack()
        self.stimulation_started = False

        print("Stimulation stopped.")

    def check_stimulation_errors(self):

        sciencemode.smpt_get_ml_get_current_data_ack(self.device, self.ml_get_current_data_ack)

        error_on_channel = False
        num_channels = len(self.list_channels)
        for j in range(num_channels):
            if self.ml_get_current_data_ack.channel_data.channel_state[j] != sciencemode.Smpt_Ml_Channel_State_Ok:
                error_on_channel = True
                break
        if error_on_channel:
            if self.ml_get_current_data_ack.channel_data.channel_state[j] == sciencemode.Smpt_Ml_Channel_State_Electrode_Error:
                error_message = "Electrode error"
            elif self.ml_get_current_data_ack.channel_data.channel_state[j] == sciencemode.Smpt_Ml_Channel_State_Timeout_Error:
                error_message = "Timeout error"
            elif self.ml_get_current_data_ack.channel_data.channel_state[j] == sciencemode.Smpt_Ml_Channel_State_Low_Current_Error:
                error_message = "Low current error"
            elif self.ml_get_current_data_ack.channel_data.channel_state[j] == sciencemode.Smpt_Ml_Channel_State_Last_Item:
                error_message = "Last item error"

            raise RuntimeError(error_message)

    def close_port(self):
        """
        Close the serial port
        """
        ret = sciencemode.smpt_close_serial_port(self.device)

        return ret

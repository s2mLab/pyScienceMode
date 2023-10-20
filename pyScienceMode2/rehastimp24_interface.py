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

    def __init__(self, port: str, show_log: bool = False, device_type: str = "RehastimP24"):
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


        super().__init__(port, show_log, device_type=device_type)

    def ll_init(self):
        ll_init = sciencemode.ffi.new("Smpt_ll_init*")
        ll_init.high_voltage_level = sciencemode.Smpt_High_Voltage_Default
        ll_init.packet_number = self.get_next_packet_number()
        # ll_init.packet_number = sciencemode.smpt_packet_number_generator_next(self.device)

        if not sciencemode.smpt_send_ll_init(self.device, ll_init):
            raise RuntimeError("Ll initialization failed.")
        print("lower level initialized")
        self.get_next_packet_number()

    def init_stimulation(self, list_channels: list):
        """
        Initialize the ml stimulation on the device.
        """
        if self.stimulation_started:
            self.stop_stimulation()
        check_unique_channel(list_channels)
        self.list_channels = list_channels
        self.electrode_number = calc_electrode_number(self.list_channels)

        ml_init = sciencemode.ffi.new("Smpt_ml_init*")
        ml_init.packet_number = sciencemode.smpt_packet_number_generator_next(self.device)

        if not sciencemode.smpt_send_ml_init(self.device, ml_init):
            raise RuntimeError("failed to start stimulation")

        print("Stimulation initialized")

    def start_stimulation(self, stimulation_duration: float = None, upd_list_channels: list = None):
        if upd_list_channels is not None:
            new_electrode_number = calc_electrode_number(upd_list_channels)
            if new_electrode_number != self.electrode_number:
                raise RuntimeError("Error update: all channels have not been initialised")
            self.list_channels = upd_list_channels

        ml_update = sciencemode.ffi.new("Smpt_ml_update*")
        ml_update.packet_number = self.get_next_packet_number()

        for i, channel in enumerate(upd_list_channels):
            ml_update.enable_channel[i] = True
            ml_update.channel_config[i].period = channel._period
            ml_update.channel_config[i].number_of_points = len(channel.list_point)

            for j, point in enumerate(channel.list_point):
                ml_update.channel_config[i].points[j].time = point.time
                ml_update.channel_config[i].points[j].current = point.current


        if not sciencemode.smpt_send_ml_update(self.device, ml_update):
            raise RuntimeError("failed to start stimulation")
        print("Stimulation started")

        # This code is used to set the stimulation duration

        ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")
        number_of_polls = int(stimulation_duration) if stimulation_duration is not None else 20
        for i in range(number_of_polls):
            ml_get_current_data.data_selection = sciencemode.Smpt_Ml_Data_Channels
            ml_get_current_data.packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
            ret = sciencemode.smpt_send_ml_get_current_data(self.device, ml_get_current_data)

            if ret:
                print(f"Stimulated: {ret}")
            else:
                print("Failed to get current data.")

            time.sleep(1)
        self.stimulation_started = True


    def stop_stimulation(self):
        """
        Stop the stimulation on the device
        """
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)

        if not sciencemode.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("failure to stop stimulation.")

        print("Stimulation stopped.")
        self.stimulation_started = False

    def close_port(self):
        """
        Close the serial port
        """
        ret = sciencemode.smpt_close_serial_port(self.device)

        return ret

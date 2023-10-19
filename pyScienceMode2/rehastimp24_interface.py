from sciencemode import sciencemode
from pyScienceMode2.sciencemode import RehastimGeneric
import serial
from pyScienceMode2.utils import *


import time


class StimulatorP24(RehastimGeneric):
    """
    Class used for the communication with Rehastim P24.
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
        self.stimulation_interval = None
        self.inter_pulse_interval = 2
        self.electrode_number = 0
        self.amplitude = []
        self.pulse_width = []
        self.mode = []
        self.muscle = []
        self.given_channels = []
        self.stimulation_started = None
        self.point_number = 0
        self.list_points = []
        self.show_log = show_log

        super().__init__(port, show_log, device_type=device_type)
        self.nbr_points = 0

    def set_stimulation_signal(self, list_channels: list): #TODO check new parameters
        """
        Sets or updates the stimulation's parameters.

        Parameters
        ----------
        list_channels: list[Channel]
            Contain the channels and their parameters.
        """
        self.amplitude = []
        self.pulse_width = []
        self.mode = []
        self.muscle = []
        self.given_channels = []
        self.nbr_points = 0

        check_list_channel_order(list_channels)

        for i in range(len(list_channels)):
            self.amplitude.append(list_channels[i].get_amplitude())
            self.pulse_width.append(list_channels[i].get_pulse_width())
            self.mode.append(list_channels[i].get_mode())
            self.given_channels.append(list_channels[i].get_no_channel())

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
        Démarre la stimulation sur le dispositif.
        """

        check_unique_channel(list_channels)

        self.list_channels = list_channels


        self.electrode_number = calc_electrode_number(self.list_channels)

        self.set_stimulation_signal(self.list_channels)

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

            # for j, point in enumerate(self.list_points):
            #     ml_update.channel_config[i].points[j].time = point['time']
            #     ml_update.channel_config[i].points[j].current = point['current']


        if not sciencemode.smpt_send_ml_update(self.device, ml_update):
            raise RuntimeError("failed to start stimulation")
        print("Stimulation started")
        time_start_stim = time.time()

        # This code is used to set the stimulation duration

        ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")
        number_of_polls = int(stimulation_duration) if stimulation_duration is not None else 20
        for i in range(number_of_polls):
            ml_get_current_data.data_selection = sciencemode.Smpt_Ml_Data_Channels
            ml_get_current_data.packet_number = sciencemode.smpt_packet_number_generator_next(self.device)
            ret = sciencemode.smpt_send_ml_get_current_data(self.device, ml_get_current_data)

            if ret:
                print(f"smpt_send_ml_get_current_data: {ret}")
            else:
                print("Failed to get current data.")

            time.sleep(1)


    def stop_stimulation(self):
        """
        Arrête la stimulation sur le dispositif.
        """
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)

        if not sciencemode.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("Échec de l'arrêt de la stimulation.")

        print("Stimulation arrêtée avec succès.")

    def close_port(self):
        ret = sciencemode.smpt_close_serial_port(self.device)

        return ret

    def add_point_configuration(self, time, current):
        point_config = {'time': time, 'current': current}
        self.list_points.append(point_config)
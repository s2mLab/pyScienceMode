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
        self.show_log = show_log

        super().__init__(port, show_log, device_type=device_type)

    def set_stimulation_signal(self, list_channels: list):
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

    def init_stimulation(self, list_channels: list, stimulation_interval: int  = None, interpulse_interval: int = 5):
        """
        Démarre la stimulation sur le dispositif.
        """
        check_stimulation_interval(stimulation_interval)
        check_unique_channel(list_channels)
        self.stimulation_interval = stimulation_interval
        self.list_channels = list_channels

        self.inter_pulse_interval = interpulse_interval
        check_inter_pulse_interval(interpulse_interval)

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
        ml_update = sciencemode.ffi.new("Smpt_ml_update*")
        ml_update.packet_number = self.get_next_packet_number()
        for i in range(len(upd_list_channels)):
            ml_update.enable_channel[i] = True
            ml_update.channel_config[i].period = 20
            ml_update.channel_config[i].amplitude = 10
            ml_update.channel_config[i].number_of_points = 3
            ml_update.channel_config[i].points[0].time = 100
            ml_update.channel_config[i].points[0].current = 10
            ml_update.channel_config[i].points[1].time = 100
            ml_update.channel_config[i].points[1].current = 10
            ml_update.channel_config[i].points[2].time = 100
            ml_update.channel_config[i].points[2].current = -10
        if not sciencemode.smpt_send_ml_update(self.device, ml_update):
            raise RuntimeError("failed to start stimulation")
        print("Stimulation started")

    def stop_stimulation(self):
        """
        Arrête la stimulation sur le dispositif.
        """
        packet_number = sciencemode.smpt_packet_number_generator_next(self.device)

        if not sciencemode.smpt_send_ml_stop(self.device, packet_number):
            raise RuntimeError("Échec de l'arrêt de la stimulation.")

        print("Stimulation arrêtée avec succès.")
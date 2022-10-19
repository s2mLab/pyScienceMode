# Stimulator class

import crccheck.checksum
from colorama import Fore
from typing import Tuple
import time
import threading
from pyScienceMode2 import Channel
from pyScienceMode2.utils import *
from pyScienceMode2.sciencemode import RehastimGeneric
import numpy as np

# Notes :
# This code needs to be used in parallel with the "ScienceMode2 - Description and protocol" document


class Stimulator(RehastimGeneric):
    """
    Class used for the communication with Rehastim.

    Attributes
    ----------
    list_channels : list[Channel]
        A list of Channel object. The Channel must be in order.
    packet_count : int
        Contain the number of packet sent to the Rehastim since the Init.
    electrode_number : int
        Number corresponding to which electrode is activated during InitChannelListMode.
    electrode_number_low_frequency: int
        Number corresponding to which electrode has low frequency factor enabled.
    port : class Serial
        Used to control the COM port.
    amplitude : list[int]
        Contain the amplitude of each corresponding channel.
    low_frequency_factor: int
        Number of stimulation skipped by low frequency channels. [0, 7]
    stimulation_interval : int
        Main stimulation period in ms.
    inter_pulse_interval: int
        Interval between the start of to stimulation in Doublet or Triplet mode. [2, 129] ms
    pulse_width : list[int]
        Contain all pulse width of the corresponding channel.
    muscle : list[int]
        Contain the name of the muscle of the corresponding channel.
    given_channels: list[int]
        Contain the number of the channels that where given during __init__ or update.
    debug_reha_show_log : bool
        Tell if the log will be displayed (True) or not (False).
    debug_reha_show_com : bool
        Tell if the communication will be displayed (True) or not (False). Except watchdog.
    debug_reha_show_watchdog : bool
        Tell if the watchdog will be displayed (True) or not (False).
    time_last_cmd : int
        Time of the last command which was sent to the Rehastim.
    packet_send_history : list[int]
        Last packet sent to the Rehastim. Used for error and debugging purposes.
    reha_connected : bool
        Tell if the computer is connected (True) to the Rehastim or not (False).
    stimulation_started : bool
        Tell if a stimulation is started (True) or not (False).
    multiple_packet_flag : int
        Flag raised when multiple packet are waiting in the port COM. The methode _check_multiple_packet_rec() needs to
        be used after each call of _calling_ack() or wait_for_packet() in order to process those packets.
    buffer_rec : list[int]
        Contain the packet receive which has not been processed.
    __thread_watchdog: threading.Thread
        ID of the thread responsible for sending regularly a watchdog.
    """

    # Constructor
    def __init__(self, list_channels: list, stimulation_interval: int, port: str,
                 inter_pulse_interval: int = 2, low_frequency_factor: int = 0, with_motomed: bool = False):
        """
        Creates an object stimulator.

        Parameters
        ----------
        list_channels : list[Channel]
            Contain the channels that wille be used. The Channels must be placed in order.
        stimulation_interval : int
            Main stimulation period in ms.
        port_path : str
            Port of the computer connected to the Rehastim.
        inter_pulse_interval: int
            Interval between the start of to stimulation in Doublet or Triplet mode. [2, 129] ms
        low_frequency_factor: int
            Number of stimulation skipped by low frequency channels. [0, 7]
        """
        self.list_channels = list_channels
        self.stimulation_interval = stimulation_interval
        self.inter_pulse_interval = inter_pulse_interval
        self.low_frequency_factor = low_frequency_factor
        self.electrode_number = 0
        self.electrode_number_low_frequency = 0

        self.amplitude = []
        self.pulse_width = []
        self.mode = []
        self.muscle = []
        self.given_channels = []

        self.check_stimulation_interval()
        self.check_low_frequency_factor()
        self.check_unique_channel(self.list_channels)
        self.stimulation_started = None
        super().__init__(port, with_motomed)

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

        self.check_list_channel_order()

        for i in range(len(list_channels)):
            self.amplitude.append(list_channels[i].get_amplitude())
            self.pulse_width.append(list_channels[i].get_pulse_width())
            self.mode.append(list_channels[i].get_mode())
            self.given_channels.append(list_channels[i].get_no_channel())

    def _send_packet(self, cmd: str, packet_number: int) -> str:
        """
        Calls the methode that construct the packet according to the command.

        Parameters
        ----------
        cmd: str
            Command that will be sent.
        packet_number: int
            Correspond to self.packet_count.

        Returns
        -------
        In the case of an InitAck, return the string 'InitAck'.
        """

        packet = [-1]
        if cmd == 'GetStimulationMode':
            packet = self._packet_get_mode()
        elif cmd == 'InitChannelListMode':
            packet = self._packet_init_stimulation()
        elif cmd == 'StartChannelListMode':
            packet = self._packet_start_stimulation()
        elif cmd == 'StopChannelListMode':
            packet = self._packet_stop_stimulation()
        init_ack = self._send_generic_packet(cmd, packet)
        if init_ack:
            return init_ack

    # Creates packet for every command part of dictionary TYPES
    def _calling_ack(self, packet) -> str:
        """
        Collects the packet waiting in the port if no packet is given.
        Processes the packet given or collected.

        _check_multiple_packet_rec() must be called after the call of _calling_ack.
        After calling _calling_ack() must print(Fore.WHITE) because some error messages are written in red and the print
        function needs to be reset to WHITE after a print in another coloured occurred.

        Parameters
        ----------
        packet: list[int]
            Packet which needs to be processed.

        Returns
        -------
        A string which is the message corresponding to the processing of the packet.
        """
        packet = self._calling_generic_ack(packet)
        if packet == "InitAck":
            return "InitAck"
        elif packet[6] == self._type('GetStimulationModeAck'):
            return self._get_mode_ack(packet)
        elif packet[6] == self._type('InitChannelListModeAck'):
            return self._init_stimulation_ack(packet)
        elif packet[6] == self._type('StopChannelListModeAck'):
            return self._stop_stimulation_ack(packet)
        elif packet[6] == self._type('StartChannelListModeAck'):
            return self._start_stimulation_ack(packet)
        elif packet[6] == self._type('StimulationError'):
            return stimulation_error(packet)

    def _packet_get_mode(self) -> bytes:
        """
        Returns the packet corresponding to the GetStimulationMode command.
        """
        packet = self._packet_construction(self.packet_count, 'GetStimulationMode')
        return packet

    @staticmethod
    def _get_mode_ack(packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'getModeAck' packet.
        """
        if str(packet[7] == '0'):
            if str(packet[8]) == '0':
                return 'Start Mode'
            elif str(packet[8]) == '1':
                return 'Stimulation initialized'
            elif str(packet[8]) == '2':
                return 'Stimulation started'
        elif str(packet[7]) == '255':
            print(Fore.LIGHTRED_EX, end='')
            return 'Transfer error'
        elif str(packet[7]) == '248':
            print(Fore.LIGHTRED_EX, end='')
            return 'Busy error'

    def _packet_init_stimulation(self) -> bytes:
        """
        Returns the packet for the InitChannelMode.
        """
        coded_inter_pulse_interval = self._code_inter_pulse_interval()
        msb, lsb = self._msb_lsb_main_stim()

        data_stimulation = [self.low_frequency_factor,
                            self.electrode_number,
                            self.electrode_number_low_frequency,
                            coded_inter_pulse_interval,
                            msb,
                            lsb,
                            0]

        packet = self._packet_construction(self.packet_count, 'InitChannelListMode', data_stimulation)
        return packet

    @staticmethod
    def _init_stimulation_ack(packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'InitChannelListModeAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Stimulation initialized'
        elif str(packet[7]) == '255':
            print(Fore.LIGHTRED_EX, end='')
            return 'Transfer error'
        elif str(packet[7]) == '254':
            print(Fore.LIGHTRED_EX, end='')
            return 'Parameter error'
        elif str(packet[7]) == '253':
            print(Fore.LIGHTRED_EX, end='')
            return 'Wrong mode error'
        elif str(packet[7]) == '248':
            print(Fore.LIGHTRED_EX, end='')
            return 'Busy error'

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

        packet = self._packet_construction(self.packet_count, 'StartChannelListMode', data_stimulation)

        return packet

    def _start_stimulation_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartChannelListModeAck' packet.
        """
        if str(packet[7]) == '0':
            self.stimulation_started = True
            return 'Stimulation started'
        if str(packet[7]) == '255':
            print(Fore.LIGHTRED_EX, end='')
            return 'Transfer error'
        if str(packet[7]) == '254':
            print(Fore.LIGHTRED_EX, end='')
            return 'Parameter error'
        if str(packet[7]) == '253':
            print(Fore.LIGHTRED_EX, end='')
            return 'Wrong mode error'
        if str(packet[7]) == '248':
            print(Fore.LIGHTRED_EX, end='')
            return ' Busy error'

    def _packet_stop_stimulation(self) -> bytes:
        """
        Returns the packet for the StopChannelListMode.
        """
        packet = self._packet_construction(self.packet_count, 'StopChannelListMode')
        return packet

    def _stop_stimulation_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StopChannelListModeAck' packet.
        """
        if str(packet[7]) == '0':
            self.packet_count = 0
            self.stimulation_started = False
            return ' Stimulation stopped'
        elif str(packet[7]) == '255':
            print(Fore.LIGHTRED_EX, end='')
            return ' Transfer error'

    def _code_inter_pulse_interval(self) -> int:
        """
        Returns the "inter pulse interval" value encoded as follows :
        Inter pulse interval = [0, 255] ∙ 0.5 ms + 1.5
        Inter pulse interval = = [1.5, 129] ms
        Coded Inter pulse interval = (Inter pulse interval - 1.5) * 2
        Note that in the current software version the minimum inter pulse interval is 8 ms.

        Returns
        -------
        coded_inter_pulse_interval: int
            Coded value of inter pulse interval [0, 255].
        """
        return int((self.inter_pulse_interval - 1.5) * 2)

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

    def init_channel(self, stimulation_interval: int = None,
                     list_channels: list = None,
                     inter_pulse_interval: int = None,
                     low_frequency_factor: int = None):
        """
        Initialize the requested channel.
        Can update stimulation interval if one is given.
        Can update list_channels if one is iven.

        stimulation_interval: int
            Period of the main stimulation. [8,1025] ms.
        list_channels: list[Channel]
            List containing the channels and their parameters.
        """
        if self.stimulation_started:
            self._stop_stimulation()

        if stimulation_interval is not None:
            self.stimulation_interval = stimulation_interval
            check_stimulation_interval(stimulation_interval)

        if list_channels is not None:
            self.list_channels = list_channels

        if inter_pulse_interval is not None:
            self.inter_pulse_interval = inter_pulse_interval
            check_inter_pulse_interval(inter_pulse_interval)

        if low_frequency_factor is not None:
            self.low_frequency_factor = low_frequency_factor
            check_low_frequency_factor(low_frequency_factor)

        # Find electrode_number (according to Science_Mode2_Description_Protocol_20121212 p17)
        self.electrode_number = calc_electrode_number(self.list_channels)
        self.electrode_number_low_frequency = calc_electrode_number(self.list_channels, enable_low_frequency=True)

        self.set_stimulation_signal(self.list_channels)
        self._send_packet('InitChannelListMode', self.packet_count)
        init_channel_list_mode_ack = self._get_last_ack()
        if init_channel_list_mode_ack != 'Stimulation initialized':
            raise RuntimeError("Error channel initialisation : " + str(init_channel_list_mode_ack))

    def start_stimulation(self, stimulation_duration: float = None, upd_list_channels: list = None):
        """
        Update a stimulation.
        Warning: only the channel that has been initiated can be updated.

        Parameters
        ----------
        stimulation_duration: float
            Time of the stimulation after the update.
        upd_list_channels: list[Channel]
            List of the channels that will be updated
        """
        if upd_list_channels is not None:
            new_electrode_number = self._calc_electrode_number(upd_list_channels)

            # Verify if the updated channels have been initialised
            if new_electrode_number != self.electrode_number:
                print(Fore.LIGHTRED_EX + "Error update: all channels have not been initialised" + Fore.WHITE)
                raise RuntimeError("Error update: all channels have not been initialised")
            self.list_channels = upd_list_channels
            self.set_stimulation_signal(self.list_channels)

        self._send_packet('StartChannelListMode', self.packet_count)

        time_start_stim = time.time()

        start_channel_list_mode_ack = self._get_last_ack()
        if start_channel_list_mode_ack != 'Stimulation started':
            raise RuntimeError("Error : StartChannelListMode" + str(start_channel_list_mode_ack))

        if self.debug_reha_show_log:
            if upd_list_channels is None:
                print("Stimulation started")
            else:
                stop = True
                for i in range(len(self.list_channels)):
                    if self.list_channels[i].get_amplitude() != 0:
                        stop = False
                        break
                if not stop:
                    print("Stimulation updated and started")
                if stop:
                    print("Stimulation stopped")

        if stimulation_duration is not None:
            if stimulation_duration < time.time() - time_start_stim:
                raise RuntimeError("Asked stimulation duration too short")
            time.sleep(stimulation_duration - (time.time() - time_start_stim))
            self.stop_stimulation()

    def stop_stimulation(self):
        """
        Stop a stimulation by setting all amplitudes to 0.
        """
        for i in range(len(self.list_channels)):
            self.list_channels[i].set_amplitude(0)
        self.start_stimulation(upd_list_channels=self.list_channels)

    def _stop_stimulation(self):
        """
        Stop a stimulation, after calling this method, init_channel must be used if stimulation need to be restarted.
        """
        self._send_packet('StopChannelListMode', self.packet_count)
        stop_channel_list_mode_ack = self._get_last_ack()
        if stop_channel_list_mode_ack != ' Stimulation stopped':
            raise RuntimeError("Error : StopChannelListMode" + stop_channel_list_mode_ack)

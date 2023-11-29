"""
Class to control the RehaMove 2 device from the ScienceMode 2 protocol.
See ScienceMode2 - Description and protocol for more information.
"""

import threading
import serial
import time

import numpy as np

from .utils import packet_construction, signed_int
from .acks import (
    motomed_error_ack,
    rehastim_error,
    init_stimulation_ack,
    get_mode_ack,
    stop_stimulation_ack,
    start_stimulation_ack,
)
from .enums import Rehastim2Commands, RehastimP24Commands, Device

from sciencemode import sciencemode

# Notes :
# This code needs to be used in parallel with the "ScienceMode2 - Description and protocol" document


class RehastimGeneric:
    """
    Class used for the sciencemode communication protocol.

    Class Attributes
    ----------------
    VERSION : int
        version of software of Rehastim.
    START_BYTE : int
        Start byte of protocol. (Science Mode2 Description Protocol, 2.2 Packet structure)
    STOP_BYTE : int
        Stop byte of protocol.
    STUFFING_BYTE : int
        Stuffing byte of protocol.
    STUFFING_KEY : int
        Stuffing key of protocol.
    MAX_PACKET_BYTES : int
        Number max of bytes per packet in protocol.
    BAUD_RATE : int
        Baud rate of protocol.
    STUFFING_BYTE : list
        Stuffed byte of protocol.
    """

    #  Constant for the Rehastim2
    BAUD_RATE = 460800
    VERSION = 0x01
    START_BYTE = 0xF0
    STOP_BYTE = 0x0F
    STUFFING_BYTE = 0x81
    STUFFING_KEY = 0x55
    MAX_PACKET_BYTES = 69
    STUFFED_BYTES = [240, 15, 129, 85, 10]

    def __init__(
        self, port: str, show_log: bool | str = False, with_motomed: bool = False, device_type: str | Device = None
    ):
        """
        Init the class.

        Parameters
        ----------
        port : str
            COM port of the Rehastim.
        show_log: bool | str
            If True, all logs of the communication will be printed.
            If "Status", only specific logs will be printed.
            If False, no logs will be printed.
        with_motomed : bool
            If the motomed is connected to the Rehastim, put this flag to True.
        device_type : str | Device
            Device type. Can be either "Rehastim2" or "RehastimP24".
        """
        self.device_type = device_type
        self.port_name = port
        if self.device_type == Device.Rehastim2.value:
            self.port = serial.Serial(
                port,
                self.BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )

        elif self.device_type == Device.Rehastimp24.value:
            self.device = sciencemode.ffi.new("Smpt_device*")
            self.com = sciencemode.ffi.new("char[]", self.port_name.encode())
            self.cmd = sciencemode.ffi.new("Smpt_cmd*")
            self.ack = sciencemode.ffi.new("Smpt_ack*")
            self.ml_get_current_data_ack = sciencemode.ffi.new("Smpt_ml_get_current_data_ack*")
            self.ll_channel_config_ack = sciencemode.ffi.new("Smpt_ll_channel_config_ack*")
            self.ll_init_ack = sciencemode.ffi.new("Smpt_ll_init_ack*")
            self.ml_update = sciencemode.ffi.new("Smpt_ml_update*")

            if not self.check_serial_port():
                raise RuntimeError(f"Failed to access port {self.port_name}.")

            if not self.open_serial_port():
                raise RuntimeError(f"Unable to open port {self.port_name}.")
        else:
            raise ValueError("Device type not recognized")

        self.port_open = True
        self.time_last_cmd = 0
        self.packet_count = 0
        self.reha_connected = False
        self.show_log = show_log
        self.time_last_cmd = 0
        self.packet_send_history = []
        self.read_port_time = 0.0
        self.last_ack = None
        self.last_init_ack = None
        self.motomed_values = None
        self.max_motomed_values = 100
        self.max_phase_result = 1
        self.__thread_watchdog = None
        self.lock = threading.Lock()
        self.motomed_done = threading.Event()
        self.is_phase_result = threading.Event()
        self.event_ack = threading.Event()
        self.last_phase_result = None
        self._motomed_command_done = True
        self.is_motomed_connected = with_motomed
        self.__comparison_thread_started = False
        self.__watchdog_thread_started = False
        self.command_send = []  # Command sent to the rehastim2
        self.ack_received = []  # Command received by the rehastim2

        self.Rehastim2Commands = Rehastim2Commands
        self.RehastimP24Commands = RehastimP24Commands

        self.error_occured = (
            False  # If the stimulation is not working and error occured flag set to true, raise an error
        )
        self.stimulation_active = False

        if self.reha_connected and not self.__comparison_thread_started:
            self._start_thread_catch_ack()

    def check_serial_port(self):
        """
        Verify if the serial port is available and functional. Used for the RehastimP24
        """
        ret = sciencemode.lib.smpt_check_serial_port(self.com)
        if self.show_log:
            print(f"Port check for {self.port_name} : {'successful' if ret else 'unsuccessful'}")
        return ret

    def open_serial_port(self):
        """
        Try to open the serial port.Used for the RehastimP24
        """
        ret = sciencemode.lib.smpt_open_serial_port(self.device, self.com)
        if self.show_log:
            print(f"Open {self.port_name} : {'successful' if ret else 'unsuccessful'}")
        return ret

    def get_next_packet_number(self):
        """
        Get the next packet to send another command. Used for the RehastimP24
        """
        if hasattr(self, "device") and self.device is not None:
            packet_number = sciencemode.lib.smpt_packet_number_generator_next(self.device)
            return packet_number

    def log(self, status_msg: str, full_msg: str = None):
        """
        Log messages based on the show_log mode.

        Parameters:
        - status_msg: The message to show when show_log is "Status" or True.
        - full_msg: The additional message to show when show_log is True.
        """
        if self.show_log is True and full_msg:
            print(full_msg)
        if self.show_log is True or self.show_log == "Status":
            print(status_msg)

    def _get_current_data(self):
        """
        Retrieve current data from the rehastimP24 mid level stimulation.
        """
        ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")
        if self.device_type == Device.Rehastimp24.value:
            ml_get_current_data.data_selection = sciencemode.lib.Smpt_Ml_Data_Channels
            ml_get_current_data.packet_number = self.get_next_packet_number()

            ret = sciencemode.lib.smpt_send_ml_get_current_data(self.device, ml_get_current_data)
            if not ret:
                print("Failed to get current data.")
            if self.show_log is True:
                print(
                    "Command sent to rehastim:",
                    self.RehastimP24Commands(sciencemode.lib.Smpt_Cmd_Ml_Get_Current_Data).name,
                )

    def _get_last_ack(self, init: bool = False) -> bytes:
        """
        Get the last ack received.

        Parameters
        ----------
        init : bool
            If True, get the last ack of the init packet. If False, get the last ack of the normal packet.
        Returns
        -------
        bytes
        """
        if self.error_occured:
            raise RuntimeError("Stimulation error")

        if self.is_motomed_connected:
            if init:
                while not self.last_init_ack:
                    pass
                last_ack = self.last_init_ack
                self.ack_received.append(last_ack)
                self.last_init_ack = None
            else:
                while not self.last_ack:
                    pass
                last_ack = self.last_ack
                self.ack_received.append(last_ack)
                self.last_ack = None
            return last_ack

        if self.device_type == Device.Rehastimp24.value:
            while not sciencemode.lib.smpt_new_packet_received(self.device):
                time.sleep(0.005)
            ret = sciencemode.lib.smpt_last_ack(self.device, self.ack)
            if self.show_log is True:
                print("Ack received by rehastimP24: ", self.RehastimP24Commands(self.ack.command_number).name)
            return ret
        elif self.device_type == Device.Rehastim2.value:
            while 1:
                packet = self._read_packet()
                if packet and len(packet) != 0:
                    break
            if packet and not self.error_occured:
                if self.show_log and packet[-1][6] in [t.value for t in self.Rehastim2Commands]:
                    print(f"Ack received by rehastim: {self.Rehastim2Commands(packet[-1][6]).name}")
                    self.ack_received.append(packet[-1])
            return packet[-1]

    def _return_list_ack_received(self) -> list:
        """
        Return the list of the ack received from the rehastim

        Returns
        -------
        self.ack_received : list
            Acks received from the rehastim
        """
        return self.ack_received

    def _return_command_sent(self) -> list:
        """
        Return the command sent list to the rehastim

        Returns
        -------
        self.command_send : list
            Commands sent to the rehastim
        """
        return self.command_send

    def _start_thread_catch_ack(self):
        """
        Start the thread which catches rehastim data and motomed data if motomed flag is true.
        """
        self.__comparison_thread_started = True
        self.__thread_catch_ack = threading.Thread(target=self._thread_catch_ack)
        self.__thread_catch_ack.start()

    def _thread_catch_ack(self):
        """
        Compare the command sent and received by the rehastim
        And retrieve the data sent by the motomed if motomed flag is true.
        """

        print("thread started")
        time_to_sleep = 0.005
        while self.stimulation_active and self.device_type == Device.Rehastim2.value:
            tic = time.time()
            """
            Compare the command sent and received by the rehastim in 2 lists. Raise an error if the command sent is 
            not the same as the command received.
            """
            if self.is_motomed_connected:
                packets = self._read_packet()
                if packets:
                    for packet in packets:
                        if len(packet) > 7:
                            if self.show_log and packet[6] in [t.value for t in self.Rehastim2Commands]:
                                if self.Rehastim2Commands(packet[6]).name == "MotomedError":
                                    ack = motomed_error_ack(signed_int(packet[7:8]))
                                    if signed_int(packet[7:8]) in [-4, -6]:
                                        print(f"Ack received by rehastim: {ack}")
                                elif self.Rehastim2Commands(packet[6]).name != "ActualValues":
                                    print(f"Ack received by rehastim: {self.Rehastim2Commands(packet[6]).name}")
                            if packet[6] == self.Rehastim2Commands["ActualValues"].value:
                                self._actual_values_ack(packet)
                            elif packet[6] == Rehastim2Commands["PhaseResult"].value:
                                return self._phase_result_ack(packet)
                            elif packet[6] == 90:
                                pass
                            elif packet[6] == self.Rehastim2Commands["MotomedCommandDone"].value:
                                self.motomed_done.set()
                            elif packet[6] in [t.value for t in self.Rehastim2Commands]:
                                if packet[6] == 1:
                                    self.last_init_ack = packet
                                    self.event_ack.set()
                                else:
                                    if packet[6] == 90 and signed_int(packet[7:8]) not in [-4, -6]:
                                        packet = packet[1:]
                                    self.last_ack = packet
                                    self.event_ack.set()

            if self.command_send and self.ack_received:
                for i in reversed(range(min(len(self.command_send), len(self.ack_received)))):
                    if self.ack_received[i][6] == self.Rehastim2Commands["StimulationError"].value:
                        ack = rehastim_error(signed_int(self.ack_received[i][7:8]))
                        if signed_int(self.ack_received[i][7:8]) in [-1, -2, -3]:
                            self.error_occured = True
                            raise RuntimeError("Stimulation error : ", ack)
                    elif (
                        self.ack_received[i][6] == self.Rehastim2Commands["ActualValues"].value
                        and not self.is_motomed_connected
                    ):
                        self.error_occured = True
                        raise RuntimeError("Motomed is connected, so put the flag with_motomed to True.")
                    elif self.command_send[i][6] + 1 == self.ack_received[i][6] and i > 0:
                        for packet in self.ack_received:
                            if packet[6] == self.Rehastim2Commands["InitChannelListModeAck"].value:
                                init_stimulation_ack(packet)
                                if init_stimulation_ack(packet) != "Stimulation initialized":
                                    self.error_occured = True
                                    raise RuntimeError("Stimulation not initialized")
                            elif packet[6] == self.Rehastim2Commands["GetStimulationModeAck"].value:
                                get_mode_ack(packet)
                            elif packet[6] == self.Rehastim2Commands["StopChannelListModeAck"].value:
                                stop_stimulation_ack(packet)
                                if stop_stimulation_ack(packet) != "Stimulation stopped":
                                    self.error_occured = True
                                    raise RuntimeError(
                                        "Error : StoppedChannelListMode :" + stop_stimulation_ack(packet)
                                    )
                            elif packet[6] == self.Rehastim2Commands["StartChannelListModeAck"].value:
                                start_stimulation_ack(packet)
                                if start_stimulation_ack(packet) != "Stimulation started":
                                    self.error_occured = True
                                    raise RuntimeError("Error : StartChannelListMode :" + start_stimulation_ack(packet))
                        del self.command_send[i]
                        del self.ack_received[i]

            loop_duration = tic - time.time()
            time.sleep(time_to_sleep - loop_duration)

    def _actual_values_ack(self, packet: bytes):
        """
        Ack of the actual values packet.

        Parameters
        ----------
        packet : bytes
            Packet received.
        """
        # handle the LSB and MSB and stuffed bytes
        count = 0
        if packet[8] == 129:
            angle = 255 * signed_int(packet[7:8]) + packet[9] ^ self.STUFFING_KEY
            count += 1
        else:
            angle = 255 * signed_int(packet[7:8]) + packet[8]
        if packet[10 + count] == 129:
            speed = signed_int(packet[10 + count + 1 : 10 + count + 2]) ^ self.STUFFING_KEY
            count += 1
        else:
            speed = signed_int(packet[10 + count : 11 + count])

        if packet[12 + count] == 129:
            torque = signed_int(packet[12 + count + 1 : 12 + count + 2]) ^ self.STUFFING_KEY
            count += 1
        else:
            torque = signed_int(packet[12 + count : 13 + count])

        actual_values = np.array([angle, speed, torque])[:, np.newaxis]
        if self.motomed_values is None:
            self.motomed_values = actual_values
        elif self.motomed_values.shape[1] < self.max_motomed_values:
            self.motomed_values = np.append(self.motomed_values, actual_values, axis=1)
        else:
            self.motomed_values = np.append(self.motomed_values[:, 1:], actual_values, axis=1)

    def _watchdog(self):
        """
        Send a watchdog if the last command send by the pc was more than 500ms ago and if the rehastim is connected.
        """
        while 1 and self.reha_connected:
            if time.time() - self.time_last_cmd > 0.8:
                self.send_generic_packet("Watchdog", packet=self._packet_watchdog())
            time.sleep(0.8)

    def send_generic_packet(self, cmd: str, packet: bytes) -> (None, str):
        """
        Send a packet to the rehastim.

        Parameters
        ----------
        cmd : str
            Command to send.
        packet : bytes
            Packet to send.
        Returns
        -------
            "InitAck" if the cmd are "InitAck". None otherwise.
        """
        if cmd == "InitAck":
            self.motomed_done.set()
            self._start_watchdog()

        if self.show_log:
            if self.Rehastim2Commands(packet[6]).name != "Watchdog":
                print(f"Command sent to Rehastim : {self.Rehastim2Commands(packet[6]).name}")
                self.command_send.append(packet)

        with self.lock:
            if time.time() - self.time_last_cmd > 1:
                self.port.write(self._packet_watchdog())
            self.port.write(packet)
            if cmd == "InitAck":
                self.reha_connected = True

        self.time_last_cmd = time.time()
        self.packet_send_history = packet
        self.packet_count = (self.packet_count + 1) % 256

        if cmd == "InitAck":
            return "InitAck"

    @staticmethod
    def _init_ack(packet_count: int) -> bytes:
        """
        Returns the packet corresponding to an InitAck.

        Parameters
        ----------
        packet_count: int
             Packet number of Rehastim.

        Returns
        -------
        packet: list
            Packet corresponding to an InitAck.
        """
        packet = packet_construction(packet_count, "InitAck", [0])
        return packet

    def close_port(self):
        """
        Closes the port.
        """
        if self.device_type == Device.Rehastimp24.value:
            sciencemode.lib.smpt_close_serial_port(self.device)
        elif self.device_type == Device.Rehastim2.value:
            self.port.close()

    def _read_packet(self) -> list:
        """
        Read the bytes are waiting in the serial port.
        Returns
        -------
        packet: list
            List of command sent by rehastim.
        """
        packet = bytes()
        while True:
            packet_tmp = self.port.read(self.port.inWaiting())
            if len(packet_tmp) != 0:
                packet += packet_tmp
            else:
                if packet and packet[-1] == self.STOP_BYTE:
                    break
        packet_list = []
        if len(packet) > 8:
            first_start_byte = packet.index(self.START_BYTE)
            packet_tmp = packet[first_start_byte:]
            while len(packet_tmp) != 0:
                next_stop_byte = packet_tmp.index(self.STOP_BYTE)
                while next_stop_byte < 8:
                    try:
                        next_stop_byte += packet_tmp[next_stop_byte + 1 :].index(self.STOP_BYTE) + 1
                    except:
                        packet_list = []
                        break
                packet_list.append(packet_tmp[: next_stop_byte + 1])
                packet_tmp = packet_tmp[next_stop_byte + 1 :]
            return packet_list

    def disconnect(self):
        """
        Disconnect the pc to the Rehastim by stopping sending watchdog and motomed threads (if applicable).
        """
        self._stop_watchdog()
        if self.reha_connected:
            self._stop_thread_catch_ack()
        self.stimulation_active = False

    def _stop_thread_catch_ack(self):
        """
        Stop the rehastim thread.
        """
        self.is_motomed_connected = False
        self.reha_connected = False
        self.__thread_catch_ack.join()

    def _start_watchdog(self):
        """
        Start the thread which sends watchdog.
        """
        self.reha_connected = True
        if not self.__watchdog_thread_started:
            self.__thread_watchdog = threading.Thread(target=self._watchdog)
            self.__thread_watchdog.start()

    def _stop_watchdog(self):
        """
        Stop the thread which sends watchdog.
        """
        self.reha_connected = False
        self.__thread_watchdog.join()

    def _packet_watchdog(self) -> bytes:
        """
        Constructs the watchdog packet.

        Returns
        -------
        packet: list
            Packet corresponding to the watchdog
        """
        packet = packet_construction(self.packet_count, "Watchdog")
        return packet

    def get_angle(self) -> float:
        """
        Returns the angle of the Rehastim.

        Returns
        -------
        angle: float
            Angle of the Rehastim.
        """
        return self.motomed_values[0, -1]

    def get_speed(self) -> float:
        """
        Returns the angle of the Rehastim.

        Returns
        -------
        angle: float
            Angle of the Rehastim.
        """
        return self.motomed_values[1, -1]

    def get_torque(self) -> float:
        """
        Returns the angle of the Rehastim.

        Returns
        -------
        angle: float
            Angle of the Rehastim.
        """
        return self.motomed_values[2, -1]

    def _phase_result_ack(self, packet: bytes) -> str:
        """
        Process the phase result packet.

        Parameters
        ----------
        packet: bytes
            Packet which needs to be processed.

        Returns
        -------
            A string which is the message corresponding to the processing of the packet.
        """
        count = 0
        if packet[7] == 129:
            phase_number = packet[8] ^ self.STUFFING_KEY
            count += 1
        else:
            phase_number = packet[7]
        if packet[9 + count] == 129:
            passive_distance = 255 * packet[8 + count] + packet[9 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            passive_distance = 255 * packet[8 + count] + packet[9 + count]

        if packet[11 + count] == 129:
            active_distance = 255 * packet[10 + count] + packet[11 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            active_distance = 255 * packet[10 + count] + packet[10 + count + 1]

        if packet[12 + count] == 129:
            average_power = packet[12 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            average_power = packet[12 + count]

        if packet[13 + count] == 129:
            maximum_power = packet[13 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            maximum_power = packet[13 + count]

        if packet[15 + count] == 129:
            phase_duration = 255 * packet[14 + count] + packet[15 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            phase_duration = 255 * packet[14 + count] + packet[15 + count]

        if packet[17 + count] == 129:
            active_phase_duration = 255 * packet[16 + count] + packet[17 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            active_phase_duration = 255 * packet[16 + count] + packet[17 + count]

        if packet[19 + count] == 129:
            phase_work = 255 * packet[18 + count] + packet[19 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            phase_work = 255 * packet[18 + count] + packet[19 + count]

        if packet[20 + count] == 129:
            success_value = packet[20 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            success_value = packet[20 + count]

        if packet[21 + count] == 129:
            symmetry = signed_int(packet[21 + count : 21 + count + 1]) ^ self.STUFFING_KEY
            count += 1
        else:
            symmetry = signed_int(packet[21 + count : 21 + count + 1])

        if packet[22 + count] == 129:
            average_muscle_tone = packet[22 + count + 1] ^ self.STUFFING_KEY
            count += 1
        else:
            average_muscle_tone = packet[22 + count]

        last_phase_result = np.array(
            [
                phase_number,
                passive_distance,
                active_distance,
                average_power,
                maximum_power,
                phase_duration,
                active_phase_duration,
                phase_work,
                success_value,
                symmetry,
                average_muscle_tone,
            ]
        )[:, np.newaxis]

        if self.last_phase_result is None:
            self.last_phase_result = last_phase_result
        elif self.last_phase_result.shape[1] < self.max_phase_result:
            self.last_phase_result = np.append(self.last_phase_result, last_phase_result, axis=1)
        else:
            self.last_phase_result = np.append(self.last_phase_result[:, 1:], last_phase_result, axis=1)
        self.is_phase_result.set()
        return "PhaseResult"

    def get_phase_result(self):
        """
        Get the actual torqur of the motomed.

        Returns
        -------
            The torque of the motomed.
        """
        self.is_phase_result.wait()
        last_result = self.last_phase_result
        self.is_phase_result.clear()
        return last_result

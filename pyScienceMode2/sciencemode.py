"""
Class to control the RehaMove 2 device from the ScienceMode 2 protocol.
See ScienceMode2 - Description and protocol for more information.
"""

import serial
import time
import threading
from pyScienceMode2.utils import *
from .acks import *
import numpy as np

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

    VERSION = 0x01

    START_BYTE = 0xF0
    STOP_BYTE = 0x0F
    STUFFING_BYTE = 0x81
    STUFFING_KEY = 0x55
    MAX_PACKET_BYTES = 69
    STUFFED_BYTES = [240, 15, 129, 85, 10]

    BAUD_RATE = 460800

    def __init__(self, port: str, show_log: bool = False, with_motomed : bool=False):
        """
        Init the class.

        Parameters
        ----------
        port : str
            COM port of the Rehastim.
        show_log : bool
            Tell if the log will be displayed (True) or not (False).
        with_motomed : bool
            If the motomed is connected to the Rehastim, put this flag to True.
        """
        self.port = serial.Serial(
            port,
            self.BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        self.port_open = True
        self.time_last_cmd = 0
        self.packet_count = 0
        self.reha_connected = False
        self.is_reha_connected = False #Need to check
        self.show_log = show_log
        self.time_last_cmd = 0
        self.packet_send_history = []
        self.read_port_time = 0.0
        self.last_ack = None
        self.last_init_ack = None #for motomed
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
        self.event_send_updated = threading.Event()
        self.event_ack_updated = threading.Event()
        self.__comparison_thread_started = False
        self.__watchdog_thread_started = False
        self.info_send = [] #Command sent to the rehastim
        self.info_received= [] #Command received by the rehastim
        self.packet_received = [] #Packet received by the rehastim
        self.Type = Type
        self.error_occured = False # if true raise error if the stimulation is not working

        self._start_thread_comparison()

        if self.reha_connected and not self.__comparison_thread_started :
            self._start_thread_comparison()

        self.Type = Type



    def _get_last_ack(self,init :bool =False) -> bytes:
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
        if self.is_motomed_connected:
            if init:
                while not self.last_init_ack:
                    pass
                last_ack = self.last_init_ack
                self.last_init_ack = None
            else:
                while not self.last_ack:
                    pass
                last_ack = self.last_ack
                self.last_ack = None
            return last_ack
        else:
            while 1:
                packet = self._read_packet()
                if packet and len(packet) != 0:
                    break
            if packet and not self.error_occured :
                if self.show_log and packet[-1][6] in [t.value for t in self.Type]:
                     print(f"Ack received by rehastim: {self.Type(packet[-1][6]).name}")
                     self.info_received.append(self.Type(packet[-1][6]).value)
                     #append only the entire packet
                     self.packet_received.append(packet)
                     self.return_packet_received()
                     self.return_list_ack()
                     self.verif_last_element(packet)

            if self.error_occured:
                raise RuntimeError("Stimulation error")

            return packet[-1]
    def return_packet_received(self)-> list:
        """
        Return the list of the packet received from the rehastim

        Returns
        -------
        self.packet_received : list
            Packets received from the rehastim
        """
        self.event_ack_updated.set()
        return self.packet_received

    def return_list_ack(self)-> list:
        """
        Return the list of the command received from the rehastim

        Returns
        -------
        self.info_received : list
            Commands received from the rehastim
        """
        self.event_ack_updated.set()
        return self.info_received
    def return_list_send(self)-> list:
        """
        Return the list of the command sent to the rehastim

        Returns
        -------
        self.info_send : list
            Commands sent to the rehastim
        """
        self.event_send_updated.set()
        return self.info_send
    def verif_last_element(self,packet):
        """
        Verify if the last element of the list of command received is the same as the last element of the list of command sent

        Parameters
        ----------
        packet : list
            List of command received from the rehastim
        """
        if self.info_received :
            if self.info_received[-1] != packet[-1][6] :
                raise ValueError("Error in the order of the received packets")

    def _start_thread_comparison(self): #Need to rename I think
        """
        Start the thread which catch rehastim data.
        """
        self.__comparison_thread_started = True
        self.__thread_comparison = threading.Thread(target=self._catch_data_comparison)
        self.__thread_comparison.start()

    def _catch_data_comparison(self): #Need to rename

        """
        Catch the rehastim data.
        """

        print("Thread started")
        time_to_sleep = 0.005
        while 1:
            # packets = self._read_packet()
            # tic=time.time()
            # if packets:
            #     for packet in packets:
            #         if len(packet) > 7:
            #             if self.show_log and packet[6] in [t.value for t in self.Type]:
            #                 if self.Type(packet[6]).name == "MotomedError":
            #                     ack = motomed_error_ack(signed_int(packet[7:8]))
            #                     if signed_int(packet[7:8]) in [-4, -6]:
            #                         print(f"Ack received by rehastim: {ack}")
            #                 elif self.Type(packet[6]).name == "StimulationError":
            #                     ack = rehastim_error(signed_int(packet[7:8]))
            #                     if signed_int(packet[7:8]) in [-1, -2, -3]:
            #                         self.error_occured = True
            #                         raise RuntimeError(f"Stimulation error : {ack}")
            #                 elif self.Type(packet[6]).name != "ActualValues":
            #                     print(f"Ack received by rehastim: {self.Type(packet[6]).name}")
            #
            #             if packet[6] == self.Type["ActualValues"].value:
            #                 self._actual_values_ack(packet)
            #             elif packet[6] == Type["PhaseResult"].value:
            #                 return self._phase_result_ack(packet)
            #             elif packet[6] == 90:
            #                 pass
            #             elif packet[6] == self.Type["MotomedCommandDone"].value:
            #                 self.motomed_done.set()
            #             elif packet[6] in [t.value for t in self.Type]:
            #                 if packet[6] == 1:
            #                     self.last_init_ack = packet
            #                     self.event_ack.set()
            #                 else:
            #                     if packet[6] == 90 and signed_int(packet[7:8]) not in [-4, -6]:
            #                         packet = packet[1:]
            #                     self.last_ack = packet
            #                     self.event_ack.set()
            packet_ack = self.return_packet_received()
            list_send = self.return_list_send()
            list_ack = self.return_list_ack()
            tic = time.time()
            while list_send and list_ack:
                for i in reversed(range(min(len(list_send), len(list_ack)))):
                    # for i in range(min(len(list_send), len(list_ack))):
                    self.event_ack_updated.wait()
                    self.event_send_updated.wait()
                    with self.lock:

                        if list_send[i] + 1 == list_ack[i]:

                            if packet_ack[i][-1][6] == self.Type["GetStimulationModeAck"].value:
                                get_mode_ack(packet_ack[i][-1])
                                # print("init")
                            elif packet_ack[i][-1][6] == self.Type["InitChannelListModeAck"].value:
                                # print("init")
                                init_stimulation_ack(packet_ack[i][-1])
                            elif packet_ack[i][-1][6] == self.Type["StopChannelListModeAck"].value:
                                stop_stimulation_ack(packet_ack[i][-1])
                                # print("init")
                            elif packet_ack[i][-1][6] == self.Type["StartChannelListModeAck"].value:
                                start_stimulation_ack(packet_ack[i][-1])
                                # print("init")
                            else :
                                raise RuntimeError("packet not understood")
                        elif self.Type(packet_ack[i][-1][6]).name == "StimulationError":
                            ack = rehastim_error(signed_int(packet_ack[i][-1][7:8]))
                            if signed_int(packet_ack[i][-1][7:8]) in [-1, -2, -3]:
                                self.error_occured = True
                                raise RuntimeError(f"Stimulation error : {ack}")

                        elif (list_send[i] + 1 != list_ack[i]) and i > 0:
                            self.error_occured = True
                            raise RuntimeError(
                                f"Error not in same order at index {i}: list_send[{i}]={list_send[i]} doesn't match list_ack[{i}]={list_ack[i]}")

            while self.is_motomed_connected :
                packets = self._read_packet()
                tic = time.time()
                if packets:
                    for packet in packets:
                        if len(packet) > 7:
                            if self.show_log and packet[6] in [t.value for t in self.Type]:
                                if self.Type(packet[6]).name == "MotomedError":
                                    ack = motomed_error_ack(signed_int(packet[7:8]))
                                    if signed_int(packet[7:8]) in [-4, -6]:
                                        print(f"Ack received by rehastim: {ack}")
                                elif self.Type(packet[6]).name != "ActualValues":
                                    print(f"Ack received by rehastim: {self.Type(packet[6]).name}")

                            if packet[6] == self.Type["ActualValues"].value:
                                self._actual_values_ack(packet)
                            elif packet[6] == Type["PhaseResult"].value:
                                return self._phase_result_ack(packet)
                            elif packet[6] == 90:
                                pass
                            elif packet[6] == self.Type["MotomedCommandDone"].value:
                                self.motomed_done.set()
                            elif packet[6] in [t.value for t in self.Type]:
                                if packet[6] == 1:
                                    self.last_init_ack = packet
                                    self.event_ack.set()
                                else:
                                    if packet[6] == 90 and signed_int(packet[7:8]) not in [-4, -6]:
                                        packet = packet[1:]
                                    self.last_ack = packet
                                    self.event_ack.set()

            self.event_send_updated.clear()
            self.event_ack_updated.clear()
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
            if self.Type(packet[6]).name != "Watchdog":
                print(f"Command sent to Rehastim : {self.Type(packet[6]).name}")
                self.info_send.append((self.Type(packet[6]).value))
                # append only the entire packet

        with self.lock:
            if time.time() - self.time_last_cmd > 1:
                self.port.write(self._packet_watchdog())
            self.port.write(packet)
            if cmd == "InitAck":
                self.reha_connected = True

        # if self.is_motomed_connected and cmd != "Watchdog":
        #     self.motomed_done.wait()
        self.time_last_cmd = time.time()
        self.packet_send_history = packet
        self.return_list_send()
        # print(f"LIST SENT {self.return_list_send()}")
        self.packet_count = (self.packet_count + 1) % 256
        if cmd == "InitAck":
            # self.motomed_done.set()
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
                    next_stop_byte += packet_tmp[next_stop_byte + 1 :].index(self.STOP_BYTE) + 1
                packet_list.append(packet_tmp[: next_stop_byte + 1])
                packet_tmp = packet_tmp[next_stop_byte + 1 :]
            return packet_list

    def disconnect(self):
        """
        Disconnect the pc to the Rehastim by stopping sending watchdog and motomed threads (if applicable).
        """
        self._stop_watchdog()
        if self.reha_connected:
            self._stop_thread_comparison()
        self.is_motomed_connected=False


    def _stop_thread_comparison(self): #infinit loop of reha  --> need to stop it but not pressing
        """
        Stop the rehastim thread.
        """
        self.is_motomed_connected = False
        self.reha_connected = False
        self.__thread_comparison.join()
        print("succeed")
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
        print("Thread watchdog stopped")


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
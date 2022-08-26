# Stimulator class

# Imports
import struct

import crccheck.checksum
from colorama import Fore
from typing import Tuple, Union
import serial
import time
import threading
from pyScienceMode2 import Channel
import numpy as np

# Notes :
# This code needs to be used in parallel with the "ScienceMode2 - Description and protocol" document


class RehastimGeneric:
    """
        Class used for the communication with Rehastim.

        Attributes
        ----------
        packet_count : int
            Contain the number of packet sent to the Rehastim since the Init.
        port : class Serial
            Used to control the COM port.
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
        multiple_packet_flag : int
            Flag raised when multiple packet are waiting in the port COM. The methode _check_multiple_packet_rec() needs to
            be used after each call of _calling_ack() or wait_for_packet() in order to process those packets.
        buffer_rec : list[int]
            Contain the packet receive which has not been processed.
        __thread_watchdog: threading.Thread
            ID of the thread responsible for sending regularly a watchdog.

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
        TYPES : dict
            Dictionary which contains Rehastim commands for protocol and their values. (Motomed command are not implemented)
        RECEIVE, SEND, ERR : int
            Packet type. Used for _packet_show() method.
        """
    VERSION = 0x01

    START_BYTE = 0xF0
    STOP_BYTE = 0x0F
    STUFFING_BYTE = 0x81
    STUFFING_KEY = 0x55
    MAX_PACKET_BYTES = 69

    BAUD_RATE = 460800

    TYPES = {
        # Rehastim command
        'Init': 0x01, 'InitAck': 0x02, 'UnknownCommand': 0x03, 'Watchdog': 0x04, 'GetStimulationMode': 0x0A,
        'GetStimulationModeAck': 0x0B, 'InitChannelListMode': 0x1E, 'InitChannelListModeAck': 0x1F,
        'StartChannelListMode': 0x20, 'StartChannelListModeAck': 0x21, 'StopChannelListMode': 0x22,
        'StopChannelListModeAck': 0x23, 'SinglePulse': 0x24, 'SinglePulseAck': 0x25, 'StimulationError': 0x26,
        0x01: 'Init', 0x02: 'InitAck', 0x03: 'UnknownCommand', 0x04: 'Watchdog',
        0x0A: 'GetStimulationMode', 0x0B: 'GetStimulationModeAck', 0x1E: 'InitChannelListMode',
        0x1F: 'InitChannelListModeAck', 0x20: 'StartChannelListMode', 0x21: 'StartChannelListModeAck',
        0x22: 'StopChannelListMode', 0x23: 'StopChannelListModeAck', 0x24: 'SinglePulse', 0x25: 'SinglePulseAck',
        0x26: 'StimulationError',
        #  Motomed commmand
        'MotomedError': 0x5A, 0x5A: 'MotomedError', 0x32: "InitPhaseTraining", 0x33: "InitPhaseTrainingAck",
        "InitPhaseTraining": 0x32, "InitPhaseTrainingAck": 0x33, 0x34: "StartPhase", "StartPhase": 0x34,
        0x35: "StartPhaseAck", "StartPhaseAck": 0x35, 0x36: "PausePhase", "PausePhase": 0x36, 0x37: "PausePhaseAck",
        "PausePhaseAck": 0x37, "StopPhaseTraining": 0x38, "StopPhaseTrainingAck": 0x39, 0x38: "StopPhaseTraining",
        0x39: "StopPhaseTrainingAck", "PhaseResult": 0x3a, 0x3a: "PhaseResult", "ActualValues": 0x3c,
        0x3c: "ActualValues", 0x46: "SetRotationDirection", 0x47: "SetRotationDirectionAck",
        "SetRotationDirection": 0x46, "SetRotationDirectionAck": 0x47, 0x48: "SetSpeed", 0x49: "SetSpeedAck",
        "SetSpeed": 0x48, "SetSpeedAck": 0x49, "SetGear": 0x4a, "SetGearAck": 0x4b, 0x4a: "SetGear",
        0x4b: "SetGearAck", "SetKeyboardLock": 0x4c, "SetKeyboardLockAck": 0x4d,
        0x4c: "SetKeyboardLock", 0x4d: "SetKeyboardLockAck", "StartBasicTraining": 0x80,
        "StartBasicTrainingAck": 0x81, 0x81: "StartBasicTrainingAck", 0x80: "StartBasicTraining",
        0x82: "PauseBasicTraining", 0x83: "PauseBasicTrainingAck", "PauseBasicTraining": 0x82,
        "PauseBasicTrainingAck": 0x83, 0x84: "ContinueBasicTraining", "ContinueBasicTraining": 0x84,
        "ContinueBasicTrainingAck": 0x85, 0x85: "ContinueBasicTrainingAck", 0x86: "StopBasicTraining",
        0x87: "StopBasicTrainingAck", "StopBasicTraining": 0x86, "StopBasicTrainingAck": 0x87,
        "MotomedCommandDone": 0x59, 0x59: "MotomedCommandDone", "GetMotomedModeAck": 0xd, 0xd: "GetMotomedModeAck",
        0xc: "GetMotomedMode", "GetMotomedMode": 0xc
    }

    def __init__(self, port, with_motomed: bool = False):
        self.port = serial.Serial(port, self.BAUD_RATE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_EVEN,
                                  stopbits=serial.STOPBITS_ONE, timeout=0.1)
        self.port_open = True
        self.debug_reha_show_log = False
        self.debug_reha_show_com = False
        self.debug_reha_show_watchdog = False
        self.time_last_cmd = 0
        self.packet_count = 0
        self.reha_connected = False

        self.time_last_cmd = 0
        self.packet_send_history = []

        self.multiple_packet_flag = 0
        self.buffer_rec = []
        self.read_port_time = 0.0
        self.last_ack = None
        self.motomed_values = None
        self.last_phase_result = None
        self.is_motomed_connected = with_motomed
        self.max_motomed_values = 100
        self.max_phase_result = 1

        self.__thread_watchdog = None
        self.lock = threading.Lock()
        # self.port.read(self.port.inWaiting())
        # self._send_generic_packet("InitAck", [-1], self.packet_count)
        if self.is_motomed_connected:
            self._start_motomed_thread()

    def _get_last_ack(self):
        if self.is_motomed_connected:
            return self.last_ack
        else:
            return self._read_packet()[0]

    def _start_motomed_thread(self):
        """
        Start the thread which sends watchdog.
        """
        if self.debug_reha_show_log:
            print("Start Motomed data thread")
        self.__thread_motomed = threading.Thread(target=self._catch_motomed_data)
        self.__thread_motomed.start()

    def _stop_motomed_thread(self):
        """
        Stop the thread which sends watchdog.
        """
        if self.debug_reha_show_log:
            print("Disconnect Motomed data thread")
        self.__thread_motomed.join()

    def _catch_motomed_data(self):
        # Empty the buffer before starting thread
        # self.port.read(self.port.inWaiting())
        # self._send_generic_packet("InitAck", [-1])
        time_to_sleep = 0.02
        while 1:
            packets = self._read_packet()
            if len(packets) > 0:
                tic = time.time()
                for packet in packets:
                    if len(packet) > 7:
                        if int(packet[6]) == self.TYPES['PhaseResult']:
                            self._phase_result_ack(packet)
                        elif int(packet[6]) == self.TYPES['ActualValues']:
                            self._actual_values_ack(packet)
                        else:
                            self.last_ack = packet
                loop_duration = tic - time.time()
                time.sleep(time_to_sleep - loop_duration)

    def _actual_values_ack(self, packet: (list, str)):
        msb_angle = int(packet[7])
        lsb_angle = int(packet[8])
        angle = None
        speed = None
        torque = None
        msb_speed = int(packet[9])
        lsb_speed = int(packet[10])
        msb_torque = int(packet[11])
        lsb_torque = int(packet[12])

        actual_values = np.array([angle, speed, torque])[:, np.newaxis]
        if self.motomed_values is None:
            self.motomed_values = actual_values
        elif self.motomed_values.shape[1] < self.max_motomed_values:
            self.motomed_values = np.append(self.motomed_values, actual_values, axis=1)
        else:
            self.motomed_values = np.append(self.motomed_values[:, 1:], actual_values, axis=1)

    def _phase_result_ack(self, packet: (list, str)):
        msb_passive_distance = int(packet[8])
        lsb_passive_distance = int(packet[9])
        msb_active_distance = int(packet[10])
        lsb_active_distance = int(packet[11])
        average_power = int(packet[12])
        maximum_power = int(packet[13])
        msb_phase_duration = int(packet[14])
        lsb_phase_duration = int(packet[15])
        msb_active_phase_duration = int(packet[16])
        lsb_active_phase_duration = int(packet[17])
        msb_phase_work = int(packet[18])
        lsb_phase_work = int(packet[19])
        success_value = int(packet[20])
        symmetry = int(packet[21])
        average_muscle_tone = int(packet[22])

        passive_distance = msb_passive_distance * 255 + lsb_passive_distance
        active_distance = None
        phase_duration = None
        active_phase_duration = None
        phase_work = None
        last_phase_result = np.array([
            passive_distance,
            active_distance,
            average_power,
            maximum_power,
            phase_duration,
            active_phase_duration,
            phase_work ,
            success_value,
            symmetry,
            average_muscle_tone,
        ])[:, np.newaxis]

        if self.last_phase_result is None:
            self.last_phase_result = last_phase_result
        elif self.last_phase_result.shape[1] < self.max_phase_result:
            self.last_phase_result = np.append(self.last_phase_result, last_phase_result, axis=1)
        else:
            self.last_phase_result = np.append(self.last_phase_result[:, 1:], last_phase_result, axis=1)

    # def wait_for_packet(self) -> str:
    #     """
    #     Waits until a packet is received from the Rehastim then processes it with _calling_ack().
    #
    #     Returns
    #     -------
    #     message: str
    #         Message that correspond to the packet received.
    #     """
    #     while 1:
    #         if self.port.in_waiting >= 7:
    #             return self._calling_ack()

    # Creates packet for every command part of dictionary TYPES
    def _calling_generic_ack(self, packet: list):
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
        if packet and len(packet) >= 7:
            if int(packet[6]) == self.TYPES['Init'] and int(packet[7]) == self.VERSION:
                return self._send_generic_packet('InitAck', packet=[], packet_number=int(packet[5]))
            if int(packet[6]) == self.TYPES['Init'] and int(packet[7]) != self.VERSION:
                raise RuntimeError(Fore.LIGHTRED_EX, "Error initialisation: incompatible version (program version : %s"
                      % self.VERSION, Fore.WHITE)
            elif int(packet[6]) == self.TYPES['UnknownCommand']:
                self._packet_show(self.packet_send_history, "SEND")
                self._packet_show(packet, "ERR")
                raise RuntimeError(Fore.LIGHTRED_EX + "UnknownCommand, Packet rec:"
                                                      f"Command received by Rehastim value: {str(packet[7])}")
            else:
                return packet
        # else:
            # self._packet_show(self.packet_send_history, "SEND")
            # self._packet_show(packet, "ERR")
            # raise RuntimeError("Wrong packet received, too short")

    def _watchdog(self):
        """
        Send a watchdog if the last command send by the pc was more than 500ms ago and if the rehastim is connected.
        """
        while 1 and self.is_connected():
            if time.time() - self.time_last_cmd > 0.5:
                self._send_generic_packet('Watchdog', packet=[], packet_number=self.packet_count)
                time.sleep(0.5)

    def is_connected(self) -> bool:
        """
        Checks if the pc and the rehastim are connected.

        Returns
        -------
        True if connected, False if not.
        """
        if self.time_last_cmd - time.time() > 1.2 or not self.reha_connected:
            self.reha_connected = False
            return False
        else:
            return True

    def _send_generic_packet(self, cmd: str, packet: list, packet_number: int = None):
        if cmd == 'InitAck':
            packet = self._init_ack(packet_number)
            self._start_watchdog()
        elif cmd == 'Watchdog':
            packet = self._packet_watchdog()
        self.lock.acquire()
        self.port.write(packet)
        if cmd == "InitAck":
            self.reha_connected = True
        self.lock.release()
        if self.debug_reha_show_com and cmd != 'Watchdog':
            self._packet_show(packet, "SEND")
        if self.debug_reha_show_watchdog and cmd == 'Watchdog':
            self._packet_show(packet, "SEND")
        self.time_last_cmd = time.time()
        self.packet_send_history = packet
        self.packet_count = (self.packet_count + 1) % 256

        if cmd == 'InitAck':
            return 'InitAck'

    def _packet_show(self, packet: list, header: str = None):
        """
        Print the packet given in arguments in the color corresponding to the header.
        Parameters
        ----------
        packet: list[int]
            Packet that will be print
        header: int
            Tell if the packet is either receive, send or err. In the case of an error, an error message is previously
            written and the print colour is set to red. That's why this case is not processed in this method.
        """
        pass
        # if header == "SEND":
        #     print(Fore.LIGHTBLUE_EX + "Packet send, ", end='')
        # # elif header == "RECEIVE":
        # #     print(Fore.LIGHTGREEN_EX + "Packet rec, ", end='')
        # if packet and len(packet) >= 7:
        #     if packet[6] in self.TYPES.values():
        #         if self.TYPES[packet[6]] == 'StimulationError':
        #             raise RuntimeError('StimulationError')
        # for i in range(len(packet)):
        #     if i == 0:
        #         print("  Start:%s" % packet[0], end='')
        #     elif i == 1:
        #         print(", Stuff:%s" % packet[1], end='')
        #     elif i == 2:
        #         print(", Checksum:%s" % packet[2], end='')
        #     elif i == 3:
        #         print(", Stuff:%s" % packet[3], end='')
        #     elif i == 4:
        #         print(", Data length:%s" % packet[4], end='')
        #     elif i == 5:
        #         print(", Number:%s" % packet[5], end='')
        #     elif i == 6:
        #         print(", Cmd:%s" % packet[6], end='')
        #     else:
        #         print(", packet[%s]" % i, ":%s" % packet[i], end='')

    def _init_ack(self, packet_count: int) -> bytes:
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
        packet = self._packet_construction(packet_count, 'InitAck', [0])
        return packet

    def _packet_construction(self, packet_count: int, packet_type: str, packet_data: list = None) -> bytes:
        """
        Constructs the packet which will be sent to the Rehastim.

        Parameters
        ----------
        packet_count: int
            Correspond to the number of packet sent to the Rehastim since the Init if the packet that will be sent.
            In the case of an acknowledged of a command of the Rehastim. The packet_count represent the number of packet
            that the rehastim has sent to the pc since the init.
        packet_type: str
            Correspond to the command that will be sent. The str is coded into an int with the class attributes TYPES.
        packet_data: list[int]
            Contain the data of the packet.

        Returns
        -------
        packet_construct: bytes
            Packet constructed which will be sent.
        """
        start_byte = self.START_BYTE
        stop_byte = self.STOP_BYTE
        packet_command = self.TYPES[packet_type]
        packet_payload = [packet_count, packet_command]
        packet_payload = self._stuff_packet_byte(packet_payload)
        if packet_data is not None:
            packet_data = self._stuff_packet_byte(packet_data)
            packet_payload += packet_data

        checksum = crccheck.crc.Crc8.calc(packet_payload)
        checksum = self._stuff_byte(checksum)
        data_length = self._stuff_byte(len(packet_payload))

        packet_lead = [start_byte, self.STUFFING_BYTE, checksum, self.STUFFING_BYTE, data_length]
        packet_end = [stop_byte]
        packet = packet_lead + packet_payload + packet_end

        return b''.join([byte.to_bytes(1, 'little') for byte in packet])

    def _stuff_packet_byte(self, packet: list) -> list:
        """
        Stuffs each byte if necessary of the packet.

        Parameters
        ----------
        packet: list[int]
            Packet containing the bytes that will be checked and stuffed if necessary.

        Returns
        -------
        packet: list[int]
            Packet returned with stuffed byte.
        """
        # Stuff the byte equal to 0xf0 (240), 0x0f (15), 0x81(129), 0x55 (85) and 0x0a(10)
        # (for more details check : Science_Mode2_Description_Protocol_20121212.pdf, 2.2 PacketStructure)
        for i in range(len(packet)):
            if packet[i] == 240 or packet[i] == 15 or packet[i] == 129 or packet[i] == 85 or packet[i] == 10:
                packet[i] = self._stuff_byte(packet[i])
        return packet

    @staticmethod
    def _stuff_byte(byte: int) -> int:
        """
        Stuffs the byte given. (Science_Mode2_Description_Protocol, 2.2 Packet Structure)

        Parameters
        ----------
        byte: int
            Byte which needs to be stuffed.

        Returns
        -------
        byte_stuffed: int
            The byte stuffed.
        """
        # return bytes(a ^ b for (a, b) in zip(byte, bitarray(self.STUFFING_KEY)))
        return (byte & ~Stimulator.STUFFING_KEY) | (~byte & Stimulator.STUFFING_KEY)

    def close_port(self):
        """
        Closes the port.
        """
        self.port.close()

    def show_log(self, param: bool = True):
        """
        Choose if log are shown (True) or not (False).

        Parameters
        ----------
        param: int
            Tell if the communication is displayed.
        """
        self.debug_reha_show_log = param

    def show_com(self, param: bool = True):
        """
        Choose if the communications between pc and rehastim are shown (True) or not (False).

        Parameters
        ----------
        param: int
            Tell if the communication is displayed.
        """
        self.debug_reha_show_com = param

    def show_watchdog(self, param: bool = True):
        """
        Choose if the watchdogs send by the pc to the rehastim are shown (True) or not (False).

        Parameters
        ----------
        param: int
            Tell if the communication is displayed.
        """
        self.debug_reha_show_watchdog = param

    def _read_packet(self):
        """
        Processes packet(s) that are waiting in the port.
        If there is only one packet, the packet is returned.
        If they are multiples packet, the first one is returned, the other are stored into self.buffer_rec and a flag
        (self.multiple_packet_flag) is raised.
        If the data received does not start with a START_BYTE, an empty packet is returned.

        Returns
        -------
        The first packet received or an empty packet if the data does not start with a START_BYTE
        """
        # Read port
        packet = self.port.read(self.port.inWaiting())
        if packet:
            while packet[-1] != self.STOP_BYTE:
                packet += self.port.read(self.port.inWaiting())
            # while packet[0] != self.START_BYTE:
            #     packet = packet[1:]
            current_packet = []
            self.buffer_rec = []
            buffer_rec = []
            print(packet)

            if packet[0] == self.START_BYTE:
                for i in range(len(packet)):
                    if packet[i] != self.STOP_BYTE:
                        current_packet.append(packet[i])
                    elif packet[i] == self.STOP_BYTE:
                        current_packet.append(packet[i])
                        buffer_rec.append(current_packet)
                        # self.buffer_rec.append(current_packet)
                        current_packet = []
                if self.debug_reha_show_com:
                    # self._packet_show(self.buffer_rec[0], "RECEIVE")
                    self._packet_show(buffer_rec, "RECEIVE")
                return buffer_rec
                # return self.buffer_rec.pop(0)

            else:
                if len(packet) == 0:
                    return b''
        else:
            return b''

    # def _check_multiple_packet_rec(self) -> bool:
    #     """
    #     Checks if multiple packets were received with the self.multiple_packet_flag and processes them.
    #     This methode must be called after each call of the methods wait_for_packet() or _calling_ack(). Otherwise, the
    #     multiples packets sent by the rehastim are not processed.
    #
    #     Returns
    #     -------
    #     True if there was multiples packets, False if not.
    #     """
    #     if self.multiple_packet_flag == 0:
    #         return False
    #     else:
    #         for i in range(len(self.buffer_rec)):
    #             message = self._calling_ack(self.buffer_rec[i])
    #             if self.debug_reha_show_log:
    #                 print(message)
    #             if self.debug_reha_show_com:
    #                 self._packet_show(self.buffer_rec[i])
    #         self.multiple_packet_flag = 0
    #         return True

    def disconnect(self):
        """
        Disconnect the pc to the Rehastim by stopping sending watchdog.
        """
        self._stop_watchdog()

    def _start_watchdog(self):
        """
        Start the thread which sends watchdog.
        """
        if self.debug_reha_show_log:
            print("Start Watchdog")
        self.reha_connected = True
        self.__thread_watchdog = threading.Thread(target=self._watchdog)
        self.__thread_watchdog.start()

    def _stop_watchdog(self):
        """
        Stop the thread which sends watchdog.
        """
        if self.debug_reha_show_log:
            print("Disconnect watchdog")
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
        packet = self._packet_construction(self.packet_count, 'Watchdog')
        return packet


class Motomed(RehastimGeneric):
    def __init__(self, port):
        self.port = port
        self.speed = 0
        self.gear = 0
        self.body_training = 1
        self.direction = 0
        self.active = 0
        self.passive_speed = 0  # tr/min
        self.is_phase_initialize = False
        self.training_side = 0
        self.crank_orientation = 0
        self.fly_wheel = 0
        self.phase_variant = 0
        self.spasm_detection = 0
        self.actual_values = 0
        self.last_phase_result = 0
        self.is_phase_training = False

        super().__init__(port, True)
        self.debug_reha_show_com = True
        # Connect to rehastim
        time.sleep(0.5)
        message = self._calling_generic_ack(self._get_last_ack())
        if message != "InitAck":
            raise RuntimeError("Connection error")

        # motomed_mode = self.get_motomed_mode()
        # if motomed_mode != "start mode":
        #     self.is_motomed_connected = False
        #     raise RuntimeError("Motomed mode not in right configuration")
        # else:
        #     self.is_motomed_connected = True

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
        if cmd == "GetMotomedMode":
            packet = self._packet_get_motomed_mode()
        elif cmd == "InitPhaseTraining":
            packet = self._packet_init_phase_training()
        elif cmd == "StartPhase":
            packet = self._packet_start_phase()
        elif cmd == "PausePhase":
            packet = self._packet_pause_phase()
        elif cmd == "StopPhaseTraining":
            packet = self._packet_stop_phase_training()
        elif cmd == "SetRotationDirection":
            packet = self._packet_set_rotation_direction()
        elif cmd == "SetSpeed":
            packet = self._packet_set_speed()
        elif cmd == "SetGear":
            packet = self._packet_set_gear()
        elif cmd == "StartBasicTraining":
            packet = self._packet_start_basic_training()
        elif cmd == "StopBasicTraining":
            packet = self._packet_stop_basic_training()
        elif cmd == "PauseBasicTraining":
            packet = self._packet_pause_basic_training()
        elif cmd == "ContinueBasicTraining":
            packet = self._packet_continue_basic_training()
        init_ack = self._send_generic_packet(cmd, packet)
        if init_ack:
            return init_ack

    def _packet_get_motomed_mode(self):
        packet = self._packet_construction(self.packet_count,
                                           "GetMotomedMode"
                                           )
        return packet

    def _packet_init_phase_training(self):
        packet = self._packet_construction(self.packet_count,
                                           "InitPhaseTraining",
                                           [self.body_training]
                                           )
        return packet

    def _packet_start_phase(self):
        packet = self._packet_construction(self.packet_count,
                                           "StartPhase",
                                           [self.phase_variant,
                                            self.body_training,
                                            self.passive_speed,
                                            self.gear,
                                            self.direction,
                                            self.fly_wheel,
                                            self.spasm_detection,
                                            self.training_side,
                                            self.crank_orientation
                                            ]
                                           )
        return packet

    def _packet_pause_phase(self):
        packet = self._packet_construction(self.packet_count,
                                           "PausePhase"
                                           )
        return packet

    def _packet_stop_phase_training(self):
        packet = self._packet_construction(self.packet_count,
                                           "StopPhaseTraining"
                                           )
        return packet

    def _packet_set_rotation_direction(self):
        packet = self._packet_construction(self.packet_count,
                                           "SetRotationDirection",
                                           [self.direction]
                                           )
        return packet

    def _packet_set_speed(self):
        packet = self._packet_construction(self.packet_count,
                                           "SetSpeed",
                                           [self.passive_speed]
                                           )
        return packet

    def _packet_set_gear(self):
        packet = self._packet_construction(self.packet_count,
                                           "SetGear",
                                           [self.gear]
                                           )
        return packet

    def _packet_start_basic_training(self):
        packet = self._packet_construction(self.packet_count,
                                           "StartBasicTraining",
                                           [self.body_training]
                                           )
        return packet

    def _packet_stop_basic_training(self):
        packet = self._packet_construction(self.packet_count,
                                           "StopBasicTraining"
                                           )
        return packet

    def _packet_continue_basic_training(self):
        packet = self._packet_construction(self.packet_count,
                                           "ContinueBasicTraining"
                                           )
        return packet

    def _packet_pause_basic_training(self):
        packet = self._packet_construction(self.packet_count,
                                           "PauseBasicTraining"
                                           )
        return packet

    def get_motomed_mode(self):
        self._send_packet("GetMotomedMode", self.packet_count)
        get_motomed_mode_ack = self._calling_ack(self._get_last_ack())
        if get_motomed_mode_ack in ['Transfer error', 'Busy error', "Motomed busy", "Motomed connection error"]:
            raise RuntimeError("Error starting phase : " + str(get_motomed_mode_ack))
        else:
            return get_motomed_mode_ack

    def init_phase_training(self, arm_training: bool = True):
        self.body_training = 1 if arm_training else 0
        self._send_packet("InitPhaseTraining", self.packet_count)
        init_phase_training_ack = self._calling_ack(self._get_last_ack())
        if init_phase_training_ack != 'Phase training initialized':
            raise RuntimeError("Error initializing phase : " + str(init_phase_training_ack))
        self.is_phase_initialize = True

    def start_phase(self,
                    arm_training: bool = True,
                    go_forward: bool = True,
                    active: bool = False,
                    passive: bool = False,
                    symmetry_training: bool = False,
                    motomedmax_game: bool = False,
                    gear: int = 0,
                    speed: int = 0,
                    fly_wheel: int = 0,
                    spasm_detection: bool = False,
                    direction_restoration: bool = False,
                    training_side: str = "both",
                    crank_equal_orientation: bool = True,
                    ):
        if active + symmetry_training + motomedmax_game + passive != 1:
            raise RuntimeError("Please chose one option between 'active', 'passive',"
                               " 'symmetry_training' and 'Motomedmax_game'.")
        if active:
            self.phase_variant = 0
        elif passive:
            self.phase_variant = 1
        elif symmetry_training:
            self.phase_variant = 2
        elif motomedmax_game:
            self.phase_variant = 3

        if not self.is_phase_initialize:
            raise RuntimeError("Phase not initialized.")
        self.body_training = 1 if arm_training else 0

        self.direction = 1 if go_forward else 0
        if gear > 20 or gear < 0:
            raise RuntimeError("Gear must be in [0, 20].")
        else:
            self.gear = gear

        if speed > 90 or speed < 0:
            raise RuntimeError("Speed must be in [0, 90].")
        else:
            self.passive_speed = speed

        if fly_wheel > 100 or fly_wheel < 0:
            raise RuntimeError("fly_wheel must be in [0, 100].")
        else:
            self.fly_wheel = fly_wheel
        if not spasm_detection:
            self.spasm_detection = 0
            if direction_restoration:
                raise RuntimeError("You can use direction restoration only if spasm detection is active.")
        else:
            if direction_restoration:
                self.spasm_detection = 2
            else:
                self.spasm_detection = 1
        if training_side == "both":
            self.training_side = 0
        elif training_side == "left":
            self.training_side = 1
        elif training_side == "right":
            self.training_side = 2
        else:
            raise RuntimeError("Training side must be 'both', 'right' or 'left'."
                               f"You have : {training_side}.")
        self.crank_orientation = 1 if crank_equal_orientation else 0

        self._send_packet("StartPhase", self.packet_count)
        start_phase_ack = self._calling_ack(self._get_last_ack())
        if start_phase_ack != 'Start phase training / change phase sent to MOTOmed':
            raise RuntimeError("Error starting phase : " + str(start_phase_ack))

    def _pause_phase_training(self):
        self._send_packet("PausePhase", self.packet_count)
        pause_phase_ack = self._calling_ack(self._get_last_ack())
        if pause_phase_ack != 'Start pause sent to MOTOmed':
            raise RuntimeError("Error starting phase : " + str(pause_phase_ack))

    def _stop_phase_training(self):
        self._send_packet("StopPhaseTraining", self.packet_count)
        start_phase_ack = self._calling_ack(self._get_last_ack())
        if start_phase_ack != 'Stop phase training sent to MOTOmed':
            raise RuntimeError("Error starting phase : " + str(start_phase_ack))

    def _continue_phase_training(self):
        self._send_packet("StopPhaseTraining", self.packet_count)
        start_phase_ack = self._calling_ack(self._get_last_ack())
        if start_phase_ack != 'Stop phase training sent to MOTOmed':
            raise RuntimeError("Error starting phase : " + str(start_phase_ack))

    def stop_training(self):
        if self.is_phase_training:
            self._stop_phase_training()
            # self.phase_result = self._get_phase_result()
        else:
            self._stop_basic_training()

    def pause_training(self):
        if self.is_phase_training:
            self._pause_phase_training()
        else:
            self._pause_basic_training()

    def continue_training(self):
        self._continue_phase_training()

    def start_basic_training(self, arm_training: bool = True):
        self.body_training = 1 if arm_training else 0
        self._send_packet("StartBasicTraining", self.packet_count)
        start_basic_training_ack = self._calling_ack(self._get_last_ack())
        if start_basic_training_ack != 'Start phase training / change phase sent to MOTOmed':
            raise RuntimeError("Error starting phase : " + str(start_basic_training_ack))

    def _stop_basic_training(self):
        self._send_packet("StopBasicTraining", self.packet_count)

    def _pause_basic_training(self):
        self._send_packet("PauseBasicTraining", self.packet_count)

    def set_direction(self, go_forward: bool = True):
        self.direction = 1 if go_forward else 0
        self._send_packet("SetDirection", self.packet_count)

    def set_speed(self, passive_speed: int):
        self.passive_speed = passive_speed
        self._send_packet("SetSpeed", self.packet_count)

    def _calling_ack(self, packet: list):
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
        if packet == "InitAck":
            return "InitAck"
        elif int(packet[6]) == self.TYPES['GetMotomedModeAck']:
            return self._get_motomed_mode_ack(packet)
        elif int(packet[6]) == self.TYPES['InitPhaseTrainingAck']:
            return self._init_phase_training_ack(packet)
        elif int(packet[6]) == self.TYPES['StartPhaseAck']:
            return self._start_phase_ack(packet)
        elif int(packet[6]) == self.TYPES['PausePhaseAck']:
            return self._pause_phase_ack(packet)
        elif int(packet[6]) == self.TYPES['StopPhaseTrainingAck']:
            return self._stop_phase_training_ack(packet)
        elif int(packet[6]) == self.TYPES['SetRotationDirectionAck']:
            return self._set_rotation_direction_ack(packet)
        elif int(packet[6]) == self.TYPES['SetSpeedAck']:
            return self._set_speed_ack(packet)
        elif int(packet[6]) == self.TYPES['SetGearAck']:
            return self._set_gear_ack(packet)
        elif int(packet[6]) == self.TYPES['StartBasicTrainingAck']:
            return self._start_basic_training_ack(packet)
        elif int(packet[6]) == self.TYPES['PauseBasicTrainingAck']:
            return self._pause_basic_training_ack(packet)
        elif int(packet[6]) == self.TYPES['ContinueBasicTrainingAck']:
            return self._continue_basic_training_ack(packet)
        elif int(packet[6]) == self.TYPES['StopBasicTrainingAck']:
            return self._stop_basic_training_ack(packet)
        else:
            # self._packet_show(self.packet_send_history, "SEND")
            # print(Fore.LIGHTRED_EX + "Error packet : not understood, Packet rec:")
            # self._packet_show(packet, "ERR")
            raise RuntimeError("Error packet : not understood")

    @staticmethod
    def _get_motomed_mode_ack(packet: (list, str)) -> str:
        """
        Returns the string corresponding to the information contain in the 'InitPhaseTrainingAck' packet.
        """
        if str(packet[7]) == '0':
            if str(packet[8]) == '0':
                return "Start mode"
            elif str(packet[8]) == '1':
                return "Phase training initialized"
            elif str(packet[8]) == '2':
                return "Phase training started"
            elif str(packet[8]) == '3':
                return "Phase training break"
            elif str(packet[8]) == '4':
                return "Basic training started"
            elif str(packet[8]) == '5':
                return "Basic training pause"
            elif str(packet[8]) == '6':
                return "Motomed busy"
            elif str(packet[8]) == '255':
                return "Motomed connection error"
        elif str(packet[7]) == '255':
            return 'Transfer error'
        elif str(packet[7]) == '248':
            return 'Busy error'

    def _init_phase_training_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'InitPhaseTrainingAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Phase training initialized'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _start_phase_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Start phase training / change phase sent to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _pause_phase_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Start pause sent to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _stop_phase_training_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Stop phase training sent to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _set_rotation_direction_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Sent rotation direction to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _set_speed_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Sent speed to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _set_gear_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Set Gear to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _start_basic_training_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Sent start basic training to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _pause_basic_training_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Sent basic pause to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _continue_basic_training_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Sent continue basic training to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    def _stop_basic_training_ack(self, packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
        """
        if str(packet[7]) == '0':
            return 'Sent stop basic training to MOTOmed'
        else:
            self.__motomed_error_values(str(packet[7]))

    @staticmethod
    def __motomed_error_values(error_code):
        if str(error_code) == '255':
            return 'Transfer error'
        elif str(error_code) == '254':
            return 'Parameter error'
        elif str(error_code) == '253':
            return 'Wrong mode error'
        elif str(error_code) == '252':
            return 'Motomed connection error'
        elif str(error_code) == '249':
            return 'Motomed busy error'
        elif str(error_code) == '248':
            return 'Busy error'
        else:
            return f'Unknown error. Error code : {str(error_code)}'


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
        elif int(packet[6]) == self.TYPES['GetStimulationModeAck']:
            return self._get_mode_ack(packet)
        elif int(packet[6]) == self.TYPES['InitChannelListModeAck']:
            return self._init_stimulation_ack(packet)
        elif int(packet[6]) == self.TYPES['StopChannelListModeAck']:
            return self._stop_stimulation_ack(packet)
        elif int(packet[6]) == self.TYPES['StartChannelListModeAck']:
            return self._start_stimulation_ack(packet)
        elif int(packet[6]) == self.TYPES['StimulationError']:
            return self._stimulation_error(packet)
        else:
            self._packet_show(self.packet_send_history, "SEND")
            print(Fore.LIGHTRED_EX + "Error packet : not understood, Packet rec:")
            self._packet_show(packet, "ERR")

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

    @staticmethod
    def _stimulation_error(packet: list) -> str:
        """
        Returns the string corresponding to the information contain in the 'StimulationError' packet.
        """
        if str(packet[7]) == '255':
            print(Fore.LIGHTRED_EX, end='')
            return ' Emergency switch activated/not connected'
        elif str(packet[7]) == '254':
            print(Fore.LIGHTRED_EX, end='')
            return ' Electrode error'
        elif str(packet[7]) == '253':
            print(Fore.LIGHTRED_EX, end='')
            return 'Stimulation module error'

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

    def check_stimulation_interval(self):
        """
        Checks if the stimulation interval is within limits.
        """
        if self.stimulation_interval < 8 or self.stimulation_interval > 1025:
            raise ValueError("Error : Stimulation interval [8,1025]. Stimulation given : %s"
                             % self.stimulation_interval)

    def check_inter_pulse_interval(self):
        """
        Checks if the "inter pulse interval" is within limits.
        """
        if self.inter_pulse_interval < 2 or self.inter_pulse_interval > 129:
            raise ValueError("Error : Inter pulse interval [2,129], given : %s" % self.inter_pulse_interval)

    def check_low_frequency_factor(self):
        """
        Checks if the low frequency factor is within limits.
        """
        if self.low_frequency_factor < 0 or self.low_frequency_factor > 7:
            raise ValueError("Error : Low frequency factor [0,7], given : %s" % self.low_frequency_factor)

    @staticmethod
    def check_unique_channel(list_channels: list) -> bool:
        """
        Checks if there is not 2 times the same channel in the ist given.

        Parameters
        ----------
        list_channels: list[Channel]
            Contains a list of channel.

        Returns
        -------
        True if all channels are unique, False and print a warning if not.
        """
        active_channel = []
        for i in range(len(list_channels)):
            if list_channels[i].get_no_channel() in active_channel:
                print(Fore.LIGHTYELLOW_EX + "Warning : 2 channel no%s" % list_channels[i].get_no_channel() +
                      " in list_channels given. The first one given will be used." + Fore.WHITE)
                list_channels.pop(i)
                return False
            else:
                active_channel.append(list_channels[i].get_no_channel())
        return True

    def check_list_channel_order(self):
        """
        Checks if the channels in the list_channels given are ordered.
        """
        number_previous_channel = 0
        for i in range(len(self.list_channels)):
            if self.list_channels[i].get_no_channel() < number_previous_channel:
                raise RuntimeError("Error: channels in list_channels given are not in order.")
            number_previous_channel = self.list_channels[i].get_no_channel()

    @staticmethod
    def _calc_electrode_number(list_channels: list, enable_low_frequency: bool = False) -> int:
        """
        When enable_low_frequency = False :
        Calculates the number corresponding to which electrode is activated.
        During the initialisation, the computer needs to tell the Rehastim which channel needs to be activated. It is
        done through the addition of 2 pow the number of the channel.
        For example if the channel 1 and 4 needs to be activated, electrode_number = 2**1 + 2**4

        When enable_low_frequency = True :
        Calculates the number corresponding to which electrode has the low_frequency_factor enabled.

        Parameters
        ----------
        list_channels: list[Channel]
            Contains the channels that will be activated.
        enable_low_frequency: bool
            Choose whether the number correspond to active channel (False) or correspond to channel with low frequency
            factor enabled (True).

        Returns
        -------
        electrode_number: int
            Electrode number calculated.
        """
        electrode_number = 0
        for i in range(len(list_channels)):
            if enable_low_frequency:
                if list_channels[i].get_enable_low_frequency():
                    electrode_number += 2 ** (list_channels[i].get_no_channel() - 1)
            if not enable_low_frequency:
                electrode_number += 2 ** (list_channels[i].get_no_channel() - 1)
        return electrode_number

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
        if not self.is_connected():
            message = self.wait_for_packet()
            if self.debug_reha_show_log:
                print(Fore.WHITE + message)
            self._check_multiple_packet_rec()

        if self.stimulation_started:
            self._stop_stimulation()

        if stimulation_interval is not None:
            self.stimulation_interval = stimulation_interval
            self.check_stimulation_interval()

        if list_channels is not None:
            self.list_channels = list_channels

        if inter_pulse_interval is not None:
            self.inter_pulse_interval = inter_pulse_interval
            self.check_inter_pulse_interval()

        if low_frequency_factor is not None:
            self.low_frequency_factor = low_frequency_factor
            self.check_low_frequency_factor()

        # Find electrode_number (according to Science_Mode2_Description_Protocol_20121212 p17)
        self.electrode_number = self._calc_electrode_number(self.list_channels)
        self.electrode_number_low_frequency = self._calc_electrode_number(self.list_channels, enable_low_frequency=True)

        self.set_stimulation_signal(self.list_channels)
        self._send_packet('InitChannelListMode', self.packet_count)
        init_channel_list_mode_ack = self.wait_for_packet()
        if init_channel_list_mode_ack != 'Stimulation initialized':
            raise RuntimeError("Error channel initialisation : " + str(init_channel_list_mode_ack))
        if self.debug_reha_show_log:
            print(Fore.WHITE + init_channel_list_mode_ack)
        self._check_multiple_packet_rec()

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

        start_channel_list_mode_ack = self.wait_for_packet()
        if start_channel_list_mode_ack != 'Stimulation started':
            raise RuntimeError("Error : StartChannelListMode" + str(start_channel_list_mode_ack))
        print(Fore.WHITE, end='')
        self._check_multiple_packet_rec()

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
        stop_channel_list_mode_ack = self.wait_for_packet()
        if stop_channel_list_mode_ack != ' Stimulation stopped':
            raise RuntimeError("Error : StopChannelListMode" + stop_channel_list_mode_ack)
        print(Fore.WHITE, end='')
        self._check_multiple_packet_rec()

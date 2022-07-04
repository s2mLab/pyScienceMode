# Stimulator class

# Imports
import crccheck.checksum
from colorama import Fore
from typing import Tuple
import serial
import time
import threading
from pyScienceMode2 import Channel

# Notes :
# This code needs to be used in parallel with the "ScienceMode2 - Description and protocol" document


class Stimulator:
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
    port : class Serial
        Used to control the COM port.
    amplitude : list[int]
        Contain the amplitude of each corresponding channel.
    stimulation_interval : int
        Main stimulation period in ms.
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
    self.__thread_watchdog: threading.Thread
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

    TYPES = {'Init': 0x01, 'InitAck': 0x02, 'UnknownCommand': 0x03, 'Watchdog': 0x04, 'GetStimulationMode': 0x0A,
             'GetStimulationModeAck': 0x0B, 'InitChannelListMode': 0x1E, 'InitChannelListModeAck': 0x1F,
             'StartChannelListMode': 0x20, 'StartChannelListModeAck': 0x21, 'StopChannelListMode': 0x22,
             'StopChannelListModeAck': 0x23, 'SinglePulse': 0x24, 'SinglePulseAck': 0x25, 'StimulationError': 0x26,
             'MotomedError': 0x5A, 0x01: 'Init', 0x02: 'InitAck', 0x03: 'UnknownCommand', 0x04: 'Watchdog',
             0x0A: 'GetStimulationMode', 0x0B: 'GetStimulationModeAck', 0x1E: 'InitChannelListMode',
             0x1F: 'InitChannelListModeAck', 0x20: 'StartChannelListMode', 0x21: 'StartChannelListModeAck',
             0x22: 'StopChannelListMode', 0x23: 'StopChannelListModeAck', 0x24: 'SinglePulse', 0x25: 'SinglePulseAck',
             0x26: 'StimulationError', 0x5A: 'MotomedError'}

    # Constructor
    def __init__(self, list_channels: list, stimulation_interval: int, port_path: str):
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
        """

        self.list_channels = list_channels
        self.stimulation_interval = stimulation_interval
        self.port = serial.Serial(port_path, self.BAUD_RATE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_EVEN,
                                  stopbits=serial.STOPBITS_ONE, timeout=0.1)
        self.packet_count = 0
        self.electrode_number = 0

        self.amplitude = []
        self.pulse_width = []
        self.muscle = []
        self.given_channels = []
        self.debug_reha_show_log = False
        self.debug_reha_show_com = False
        self.debug_reha_show_watchdog = False
        self.time_last_cmd = 0
        self.packet_send_history = []
        self.reha_connected = False
        self.stimulation_started = False
        self.multiple_packet_flag = 0
        self.buffer_rec = []
        self.read_port_time = 0.0

        self.check_stimulation_interval()
        self.check_unique_channel(self.list_channels)

        self.__thread_watchdog = threading.Thread(target=self._watchdog)
        self.lock = threading.Lock()

    def wait_for_packet(self) -> str:
        """
        Waits until a packet is received from the Rehastim then processes it with _calling_ack().

        Returns
        -------
        message: str
            Message that correspond to the packet received.
        """
        while 1:
            if self.port.in_waiting >= 7:
                return self._calling_ack()

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
        self.muscle = []
        self.given_channels = []

        self.check_list_channel_order()

        for i in range(len(list_channels)):
            self.amplitude.append(list_channels[i].amplitude)
            self.pulse_width.append(list_channels[i].pulse_width)
            self.given_channels.append(list_channels[i].no_channel)

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
        if cmd == 'InitAck':
            packet = self._init_ack(packet_number)
            self._start_watchdog()
        elif cmd == 'Watchdog':
            packet = self._packet_watchdog()
        elif cmd == 'GetStimulationMode':
            packet = self._packet_get_mode()
        elif cmd == 'InitChannelListMode':
            packet = self._packet_init_stimulation()
        elif cmd == 'StartChannelListMode':
            packet = self._packet_start_stimulation()
        elif cmd == 'StopChannelListMode':
            packet = self._packet_stop_stimulation()

        self.lock.acquire()
        self.port.write(packet)
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
        while packet[-1] != self.STOP_BYTE:
            packet += self.port.read(self.port.inWaiting())

        current_packet = []
        self.buffer_rec = []

        if packet[0] == self.START_BYTE:
            for i in range(len(packet)):
                if packet[i] != self.STOP_BYTE:
                    current_packet.append(packet[i])
                elif packet[i] == self.STOP_BYTE:
                    current_packet.append(packet[i])
                    self.buffer_rec.append(current_packet)
                    current_packet = []
                    if i != len(packet) - 1:
                        self.multiple_packet_flag = 1
            if self.debug_reha_show_com:
                self._packet_show(self.buffer_rec[0], "RECEIVE")
            return self.buffer_rec.pop(0)

        else:
            # Return empty string to avoid hanging
            print(Fore.LIGHTRED_EX + "Error packet receive: first byte does not correspond to start byte, "
                                     "packet returned is empty" + Fore.WHITE)
            return b''

    def _check_multiple_packet_rec(self) -> bool:
        """
        Checks if multiple packets were received with the self.multiple_packet_flag and processes them.
        This methode must be called after each call of the methods wait_for_packet() or _calling_ack(). Otherwise, the
        multiples packets sent by the rehastim are not processed.

        Returns
        -------
        True if there was multiples packets, False if not.
        """
        if self.multiple_packet_flag == 0:
            return False
        else:
            for i in range(len(self.buffer_rec)):
                message = self._calling_ack(self.buffer_rec[i])
                if self.debug_reha_show_log:
                    print(message)
                if self.debug_reha_show_com:
                    self._packet_show(self.buffer_rec[i])
            self.multiple_packet_flag = 0
            return True

    # Creates packet for every command part of dictionary TYPES
    def _calling_ack(self, packet: list = None) -> str:
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
        if packet is None:
            packet = self._read_packet()
        if len(packet) >= 7:
            if int(packet[6]) == Stimulator.TYPES['Init'] and int(packet[7]) == self.VERSION:
                return self._send_packet('InitAck', int(packet[5]))
            if int(packet[6]) == Stimulator.TYPES['Init'] and int(packet[7]) != self.VERSION:
                print(Fore.LIGHTRED_EX, "Error initialisation: incompatible version (program version : %s"
                      % self.VERSION, Fore.WHITE)
            elif int(packet[6]) == Stimulator.TYPES['UnknownCommand']:
                self._packet_show(self.packet_send_history, "SEND")
                print(Fore.LIGHTRED_EX + "UnknownCommand, Packet rec:")
                self._packet_show(packet, "ERR")
                return f"Command received by Rehastim value: {str(packet[7])}"
            elif int(packet[6]) == Stimulator.TYPES['GetStimulationModeAck']:
                return self._get_mode_ack(packet)
            elif int(packet[6]) == Stimulator.TYPES['InitChannelListModeAck']:
                return self._init_stimulation_ack(packet)
            elif int(packet[6]) == Stimulator.TYPES['StopChannelListModeAck']:
                return self._stop_stimulation_ack(packet)
            elif int(packet[6]) == Stimulator.TYPES['StartChannelListModeAck']:
                return self._start_stimulation_ack(packet)
            elif int(packet[6]) == Stimulator.TYPES['StimulationError']:
                return self._stimulation_error(packet)
            else:
                self._packet_show(self.packet_send_history, "SEND")
                print(Fore.LIGHTRED_EX + "Error packet : not understood, Packet rec:")
                self._packet_show(packet, "ERR")
                # raise RuntimeError("Error packet : not understood")
        else:
            self._packet_show(self.packet_send_history, "SEND")
            print(Fore.LIGHTRED_EX + "Error packet : packet too short, Packet rec:")
            self._packet_show(packet, "ERR")
            # raise RuntimeError("Wrong packet received, too short")

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
        if header == "SEND":
            print(Fore.LIGHTBLUE_EX + "Packet send, ", end='')
        elif header == "RECEIVE":
            print(Fore.LIGHTGREEN_EX + "Packet rec, ", end='')
        if len(packet) >= 7:
            if packet[6] in self.TYPES.values():
                if self.TYPES[packet[6]] == 'StimulationError':
                    print(Fore.LIGHTRED_EX + "Packet rec, ", end='')
                print(self.TYPES[packet[6]], ":")
            else:
                print(packet[6], ":")
        for i in range(len(packet)):
            if i == 0:
                print("  Start:%s" % packet[0], end='')
            elif i == 1:
                print(", Stuff:%s" % packet[1], end='')
            elif i == 2:
                print(", Checksum:%s" % packet[2], end='')
            elif i == 3:
                print(", Stuff:%s" % packet[3], end='')
            elif i == 4:
                print(", Data length:%s" % packet[4], end='')
            elif i == 5:
                print(", Number:%s" % packet[5], end='')
            elif i == 6:
                print(", Cmd:%s" % packet[6], end='')
            else:
                print(", packet[%s]" % i, ":%s" % packet[i], end='')
        print(Fore.WHITE)

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

    def _watchdog(self):
        """
        Send a watchdog if the last command send by the pc was more than 500ms ago and if the rehastim is connected.
        """
        while 1 and self.is_connected():
            if time.time() - self.time_last_cmd > 0.5:
                self._send_packet('Watchdog', self.packet_count)
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

    def disconnect(self):
        """
        Disconnect the pc to the Rehastim by stopping sending watchdog.
        """
        self._stop_watchdog()

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
        msb, lsb = self._msb_lsb_main_stim()
        new_electrode_numb = self.electrode_number
        data_stimulation = [0, new_electrode_numb, 0, 2, msb, lsb, 0]
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
        mode = 0
        for i in range(len(self.amplitude)):
            msb, lsb = self._msb_lsb_pulse_stim(self.pulse_width[i])
            data_stimulation.append(mode)
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

    def _msb_lsb_main_stim(self) -> Tuple[int, int]:
        """
        Returns the most significant bit (msb) and least significant bit (lsb) corresponding to the main stimulation
        interval.
        Main stimulation interval = [0, 2048] ∙ 0.5 ms + 1 ms
        Main stimulation interval = [1, 1025] ms
        Note that in the current software version the minimum
        main stimulation interval is 8 ms.
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
            if list_channels[i].no_channel in active_channel:
                print(Fore.LIGHTYELLOW_EX + "Warning : 2 channel no%s" % list_channels[i].no_channel +
                      " in list_channels given. The first one given will be used." + Fore.WHITE)
                list_channels.pop(i)
                return False
            else:
                active_channel.append(list_channels[i].no_channel)
        return True

    def check_list_channel_order(self):
        """
        Checks if the channels in the list_channels given are ordered.
        """
        number_previous_channel = 0
        for i in range(len(self.list_channels)):
            if self.list_channels[i].no_channel < number_previous_channel:
                raise RuntimeError("Error: channels in list_channels given are not in order.")
            number_previous_channel = self.list_channels[i].no_channel

    @staticmethod
    def _calc_electrode_number(list_channels: list) -> int:
        """
        Calculates the number corresponding to which electrode is activated.
        During the initialisation, the computer needs to tell the Rehastim which channel needs to be activated. It is
        done through the addition of 2 pow the number of the channel.
        For example if the channel 1 and 4 needs to be activated, electrode_number = 2**1 + 2**4

        Parameters
        ----------
        list_channels: list[Channel]
            Contain the channels that will be activated.

        Returns
        -------
        electrode_number: int
            Electrode number calculated.
        """
        electrode_number = 0
        for i in range(len(list_channels)):
            electrode_number += 2 ** (list_channels[i].no_channel - 1)
        return electrode_number

    def init_channel(self, stimulation_interval: int = None, list_channels: list = None):
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

        # Find electrode_number (according to Science_Mode2_Description_Protocol_20121212 p17)
        self.electrode_number = self._calc_electrode_number(self.list_channels)

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
                    if self.list_channels[i].amplitude != 0:
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
            self.list_channels[i].amplitude = 0
        self.start_stimulation(upd_list_channels=self.list_channels)

    def _stop_stimulation(self):
        """
        Stop a stimulation, after calling this method, init_channel must be used if stimulations need to be restarted.
        """
        self._send_packet('StopChannelListMode', self.packet_count)
        stop_channel_list_mode_ack = self.wait_for_packet()
        if stop_channel_list_mode_ack != ' Stimulation stopped':
            raise RuntimeError("Error : StopChannelListMode" + stop_channel_list_mode_ack)
        print(Fore.WHITE, end='')
        self._check_multiple_packet_rec()

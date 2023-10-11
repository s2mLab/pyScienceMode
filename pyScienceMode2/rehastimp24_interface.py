import sciencemode
from pyScienceMode2.sciencemode import RehastimGeneric
import serial

import time


class Stimulator_P24 (RehastimGeneric) :
    """
    Class used for the communication with Rehastim P24.
    """

    MAX_PACKET_BYTES = 69
    STUFFED_BYTES = [240, 15, 129, 85, 10]

    BAUD_RATE = 3000000
    Flow_Control = True

    def __init__ (self, port: str, show_log: bool = False):
        """
        Creates an object stimulator for the rehastim P24.

        Parameters
        ----------
        port : str
            Port of the computer connected to the Rehastim.
        show_log: bool
            If True, the log of the communication will be printed.

        """
        super().__init__(port, show_log)
        self.port = serial.Serial(
            port,
            self.BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=0.1,
        )


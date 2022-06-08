# Class Channel

from colorama import Fore
import sys


class Channel:
    """
    Class representing a channel.

    Attributes
    ----------
    mode: MODE
        Tell which mode is used.
    no_channel: int
        Number of the channel [1,8].
    amplitude: int
        Current to send in the channel. [0,130] Amp
    frequency: int
        Frequency of the main stimulation. [1,50] Hz
    pulse_width: int
        Width of the stimulation. [0,500] μs (current version of rehastim [20, 500] μs, if (pw < 20) then pw = 20)
    stimulation_interval: int
        Period of the main stimulation. [8,1025] ms
    inter_pulse_interval: int
        Interval between the start of to stimulation in Doublet or Triplet mode. [2, 129] ms
    name: str
        Name of the muscle corresponding to the channel.

    Class Attributes
    ----------------
    MODE: dict
        Contain the different names of the different modes
    """

    MODE = {'Single': 0, 'Doublet': 1, 'Triplet': 2}

    def __init__(self, mode: str = 'Single', no_channel: int = 1, amplitude: int = 0, frequency: int = 1,
                 pulse_width: int = 1, stimulation_interval: int = 8, inter_pulse_interval: int = 2, name: str = None):
        """
        Create an object Channel.
        Check if the values given are in limits.

        Parameters
        ----------
        mode: MODE
            Tell which mode is used.
        no_channel: int
            Number of the channel [1,8].
        amplitude: int
            Current to send in the channel. [0,130] Amp
        frequency: int
            Frequency of the main stimulation. [1,50] Hz
        pulse_width: int
            Width of the stimulation. [0,500] μs (current version of rehastim [20, 500] μs, if (pw < 20) then pw = 20)
        stimulation_interval: int
            Period of the main stimulation. [8,1025] ms
        inter_pulse_interval: int
            Interval between the start of to stimulation in Doublet or Triplet mode. [2, 129] ms
        name: str
            Name of the muscle corresponding to the channel.
        """
        self.mode = mode
        self.no_channel = no_channel
        self.amplitude = amplitude
        self.frequency = frequency
        self.pulse_width = pulse_width
        self.stimulation_interval = stimulation_interval
        self.inter_pulse_interval = inter_pulse_interval
        self.name = name if name else f"muscle_{self.no_channel}"

        self.check_value_param()
        self.check_same_period_freq()

    def __str__(self) -> str:
        """
        Used for printing an object Channel.

        Returns
        -------
        A string representing all parameters of Class Channel.
        """
        return f"Channel {self.no_channel} {self.name}: {self.mode=}, {self.amplitude=}, {self.frequency=}, " \
               f"{self.stimulation_interval}, {self.pulse_width=}, {self.inter_pulse_interval=}"

    def check_same_period_freq(self) -> bool:
        """
        Checks if the stimulation interval given correspond to the frequency given.

        Returns
        -------
        True if they correspond, False if not.
        """
        if 1/self.frequency != self.stimulation_interval/1000 and self.stimulation_interval != 0:
            print(Fore.LIGHTYELLOW_EX + "Warning : amplitude and frequency are different. "
                                        "By default, amplitude overwrite frequency " + Fore.WHITE)
            self.frequency = int(1000/self.stimulation_interval)
            return False
        return True

    def check_value_param(self):
        """
        Checks if the values given correspond are in limits.
        """
        try:
            if self.amplitude < 0 or self.amplitude > 130:
                raise ValueError(Fore.LIGHTRED_EX + "Error : Amplitude min = 0, max = 130. Amplitude given : %s"
                                 % self.amplitude + Fore.WHITE)
            if self.frequency < 1 or self.frequency > 50:
                raise ValueError(Fore.LIGHTRED_EX + "Error : Frequency [1,50]. Freq given : %s"
                                 % self.amplitude + Fore.WHITE)
            if self.no_channel < 1 or self.no_channel > 8:
                raise ValueError(Fore.LIGHTRED_EX + "Error : 8 channel possible. Channel given : %s"
                                 % self.no_channel + Fore.WHITE)
            if self.stimulation_interval < 8 or self.stimulation_interval > 1025:
                raise ValueError(Fore.LIGHTRED_EX + "Error : Stimulation interval [8,1025]. Stimulation given : %s"
                                 % self.stimulation_interval + Fore.WHITE)
            if self.pulse_width < 0 or self.pulse_width > 500:
                raise ValueError(Fore.LIGHTRED_EX + "Error : Impulsion time [0,500], given : %s"
                                 % self.pulse_width + Fore.WHITE)
            if self.inter_pulse_interval < 2 or self.inter_pulse_interval > 129:
                raise ValueError(Fore.LIGHTRED_EX + "Error : Inter pulse interval [2,129], given : %s"
                                 % self.inter_pulse_interval + Fore.WHITE)
        except ValueError as e:
            print(e)
            sys.exit()

    def set_mode(self, mode: MODE):
        """
        Set mode.
        """
        self.mode = mode

    def get_mode(self) -> MODE:
        """
        Returns mode.
        """
        return self.mode

    def set_amplitude(self, amp: int):
        """
        Set amplitude.
        """
        self.amplitude = amp

    def get_amplitude(self) -> int:
        """
        Returns amplitude.
        """
        return self.amplitude

    def set_no_channel(self, no_channel: int):
        """
        Set no_channel.
        """
        self.no_channel = no_channel

    def get_no_channel(self) -> int:
        """
        Returns no_channel.
        """
        return self.no_channel

    def set_frequency(self, frequency: int):
        """
        Set frequency.
        """
        self.frequency = frequency

    def get_frequency(self) -> int:
        """
        Returns frequency.
        """
        return self.frequency

    def set_pulse_width(self, pulse_width: int):
        """
        Set pulse_width.
        """
        self.pulse_width = pulse_width

    def get_pulse_width(self) -> int:
        """
        Returns pulse_width.
        """
        return self.pulse_width

    def set_stimulation_interval(self, stimulation_interval: int):
        """
        Set stimulation_interval.
        """
        self.stimulation_interval = stimulation_interval

    def get_stimulation_interval(self) -> int:
        """
        Returns stimulation_interval.
        """
        return self.stimulation_interval

    def set_inter_pulse_interval(self, inter_pulse_interval: int):
        """
        Set inter_pulse_interval.
        """
        self.inter_pulse_interval = inter_pulse_interval

    def get_inter_pulse_interval(self) -> int:
        """
        Returns inter_pulse_interval.
        """
        return self.inter_pulse_interval

    def set_name(self, name: str):
        """
        Set name.
        """
        self.name = name

    def get_name(self) -> str:
        """
        Returns name.
        """
        return self.name

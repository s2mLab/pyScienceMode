"""
Class used to construct a channel for each different electrode.
"""


class Channel:
    """
    Class representing a channel for controlling electrodes.

    Class Attributes
    ----------------
    MODE: dict
        Contain the different names of the different modes
        Valid modes: "Single", "Doublet", "Triplet"
    """

    MODE = {"Single": 0, "Doublet": 1, "Triplet": 2}

    def __init__(
        self,
        mode: str = "Single",
        no_channel: int = 1,
        amplitude: int = 0,
        pulse_width: int = 1,
        enable_low_frequency: bool = False,
        name: str = None,
    ):
        """
        Create an object Channel.
        Check if the values given are in limits.

        Parameters
        ----------
        mode: str
            Tell which mode is used.
        no_channel: int
            Number of the channel [1,8] for the electrode.
        amplitude: int
            Current to send in the channel. [0,130] milli amp
        pulse_width: int
            Width of the stimulation. [0,500] μs (current version of rehastim [20, 500] μs, if (pw < 20) then pw = 20)
        enable_low_frequency: bool
            Choose if the channel skip (True) or not (False) a given number of stimulation.
        name: str
            Name of the muscle corresponding to the channel.
        """

        self._mode = self.MODE[mode]
        self._no_channel = no_channel
        self._amplitude = amplitude
        self._pulse_width = pulse_width
        self._enable_low_frequency = enable_low_frequency
        self._name = name if name else f"muscle_{self._no_channel}"

        self.check_value_param()

    def __str__(self) -> str:
        """
        Used for printing an object Channel.

        Returns
        -------
        str
        A string representing all parameters of Class Channel._
        """
        return (
            f"Channel {self._no_channel} {self._name}: {self._mode=}, {self._amplitude=}, {self._pulse_width=}, "
            f"{self._enable_low_frequency=}"
        )

    def check_value_param(self):
        """
        Checks if the values given correspond are in limits. Raise ValueError if not.
        """
        if self._amplitude < 0 or self._amplitude > 130:
            raise ValueError("Error : Amplitude min = 0, max = 130. Amplitude given : %s" % self._amplitude)
        if self._no_channel < 1 or self._no_channel > 8:
            raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
        if self._pulse_width < 0 or self._pulse_width > 500:
            raise ValueError("Error : Impulsion time [0,500], given : %s" % self._pulse_width)

    def set_mode(self, mode: MODE):
        """
        Set the stimulation mode for the channel.
        Parameters
        ----------
        mode: MODE
            Specifies the mode of stimulation.
        """
        self._mode = mode

    def get_mode(self) -> MODE:
        """
        Get the stimulation mode for the channel.

        Returns
        -------
        MODE
            Return the current stimulation mode.
        """
        return self._mode

    def set_amplitude(self, amp: int):
        """
        Set the amplitude for the channel.

        Parameters
        ----------
        amp: int
            Specifies the amplitude of the stimulation.
        """
        self._amplitude = amp
        self.check_value_param()

    def get_amplitude(self) -> int:
        """
        Get the amplitude for the channel.

        Returns
        -------
        int
            Returns amplitude in milliamps
        """
        return self._amplitude

    def set_no_channel(self, no_channel: int):
        """
        Set the channel number for the electrode.

        Parameters
        ----------
        no_channel: int
            Specifies the channel number [1,8]
        """
        self._no_channel = no_channel
        self.check_value_param()

    def get_no_channel(self) -> int:
        """
        Get the channel number for the electrode.

        Returns
        -------
        int
            Returns the current channel number.
        """
        return self._no_channel

    def set_pulse_width(self, pulse_width: int):
        """
        Set the pulse width for the stimulation.

        Parameters
        ----------
        pulse_width: int
            Specifies the pulse width in microseconds [20,500
        """
        self._pulse_width = pulse_width
        self.check_value_param()

    def get_pulse_width(self) -> int:
        """
        Get the pulse width for the stimulation.

        Returns
        -------
        int
            Returns the current pulse width in microseconds.
        """
        return self._pulse_width

    def set_name(self, name: str):
        """
        Set the name of the muscle corresponding to the channel.

        Parameters
        ----------
        name: str
            Specifies the name of the muscle.
        """
        self._name = name

    def get_name(self) -> str:
        """
        Get the name of the muscle corresponding to the channel.

        Returns
        -------
        str
            Returns the current name of the muscle.
        """
        return self._name

    def set_enable_low_frequency(self, enable_low_frequency: bool):
        """
        Set whether the channel skip (True) or not (False) a given number of stimulation.

        Parameters
        ----------
        enable_low_frequency: bool
            Specifies if the channel skip (True) or not (False) a given number of stimulation.

        """
        self._enable_low_frequency = enable_low_frequency

    def get_enable_low_frequency(self) -> bool:
        """
        Get whether the channel skip (True) or not (False) a given number of stimulation.

        Returns
        -------
        bool
            True if the channel skip a given number of stimulation, False otherwise.
        """
        return self._enable_low_frequency

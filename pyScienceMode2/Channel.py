"""
Class used to construct a channel for each different electrode.
"""


class Channel:
    """
    Class representing a channel.

    Class Attributes
    ----------------
    MODE: dict
        Contain the different names of the different modes
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
        device_type="rehastim2",
    ):
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
            Current to send in the channel. [0,130] milli amp
        pulse_width: int
            Width of the stimulation. [0,500] μs (current version of rehastim [20, 500] μs, if (pw < 20) then pw = 20)
        enable_low_frequency: bool
            Choose if the channel skip (True) or not (False) a given number of stimulation.
        name: str
            Name of the muscle corresponding to the channel.
        """
        self.device_type = device_type
        self._mode = self.MODE[mode]
        self._no_channel = no_channel
        self._amplitude = amplitude
        self._pulse_width = pulse_width
        self._enable_low_frequency = enable_low_frequency
        self._name = name if name else f"muscle_{self._no_channel}"
        self._number_of_points = 0

        self.check_value_param()

    def __str__(self) -> str:
        """
        Used for printing an object Channel.

        Returns
        -------
        A string representing all parameters of Class Channel._
        """
        return (
            f"Channel {self._no_channel} {self._name}: {self._mode=}, {self._amplitude=}, {self._pulse_width=}, "
            f"{self._enable_low_frequency=}"
        )

    def check_device_type(self) :
        """
        Check if the device type is correct.
        """
        if self.device_type != "rehastim2" and self.device_type != "rehastim4":
            raise ValueError("Error : Device type must be rehastim2 or rehastim4. Device type given : %s" % self.device_type)
        return self.device_type

    def check_value_param(self):
        """
        Checks if the values given correspond are in limits.
        """
        if self.device_type == "rehastim2":
            if self._amplitude < 0 or self._amplitude > 130:
                raise ValueError("Error : Amplitude min = 0, max = 130. Amplitude given : %s" % self._amplitude)
            if self._no_channel < 1 or self._no_channel > 8:
                raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
            if self._pulse_width < 0 or self._pulse_width > 500:
                raise ValueError("Error : Impulsion time [0,500], given : %s" % self._pulse_width)

        """New parameters for rehastim4"""

        if self.device_type == "rehastim4":
            if self._amplitude < 0 or self._amplitude > 130:
                raise ValueError("Error : Amplitude min = 0, max = 130. Amplitude given : %s" % self._amplitude)
            if self._no_channel < 1 or self._no_channel > 8:
                raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
            if self._pulse_width < 10 or self._pulse_width > 65520:
                raise ValueError("Error : Impulsion time [0,500], given : %s" % self._pulse_width)
            if self._number_of_points < 0 or self._number_of_points > 15:
                raise ValueError("Error : Number of points [0,15], given : %s" % self._number_of_points)

    def set_mode(self, mode: MODE):
        """
        Set mode.
        """
        self._mode = mode

    def get_mode(self) -> MODE:
        """
        Returns mode.
        """
        return self._mode

    def set_amplitude(self, amp: int):
        """
        Set amplitude.
        """
        self.check_device_type() #Check the device used
        if self.device_type == "rehastim2":
            self._amplitude = amp
            self.check_value_param()
        if self.device_type == "rehastim4":
            self._amplitude = amp
            self.check_value_param()


    def get_amplitude(self) -> int:
        """
        Returns amplitude.
        """
        return self._amplitude

    def set_no_channel(self, no_channel: int):
        """
        Set no_channel.
        """
        self._no_channel = no_channel
        self.check_value_param()

    def get_no_channel(self) -> int:
        """
        Returns no_channel.
        """
        return self._no_channel

    def set_pulse_width(self, pulse_width: int):
        """
        Set pulse_width.
        """
        self._pulse_width = pulse_width
        self.check_value_param()

    def get_pulse_width(self) -> int:
        """
        Returns pulse_width.
        """
        return self._pulse_width

    def set_name(self, name: str):
        """
        Set name.
        """
        self._name = name

    def get_name(self) -> str:
        """
        Returns name.
        """
        return self._name

    def set_enable_low_frequency(self, enable_low_frequency: bool):
        """
        Set enable_low_frequency.
        """
        self._enable_low_frequency = enable_low_frequency

    def get_enable_low_frequency(self) -> bool:
        """
        Returns enable_low_frequency.
        """
        return self._enable_low_frequency

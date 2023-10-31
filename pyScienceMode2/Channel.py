"""
Class used to construct a channel for each different electrode.
"""
from sciencemode import sciencemode


class Channel:
    """
    Class representing a channel.

    Class Attributes
    ----------------
    MODE: dict
        Contain the different names of the different modes
    """

    MODE = {"Single": 0, "Doublet": 1, "Triplet": 2}
    MAX_POINTS = 16
    CHANNEL_MAPPING = {
        1: 'Smpt_Channel_Red',
        2: 'Smpt_Channel_Blue',
        3: 'Smpt_Channel_Black',
        4: 'Smpt_Channel_White'
    }

    def __init__(
        self,
        mode: str = "Single",
        no_channel: int = 1,
        amplitude: int = 0,
        pulse_width: int = 0,
        enable_low_frequency: bool = False,
        name: str = None,
        device_type="Rehastim2",
        frequency: float = 50.0,
        ramp: int = 0
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
        device_type: str
            Type of the device used. Rehastim2 or RehastimP24
        frequency: float
            Frequency of the channel. [0.5, 1000] Hz
        """
        self.device_type = device_type  # NEW : Check if the device is rehastim2 or rehastimP24
        self._mode = self.MODE[mode]
        self._no_channel = no_channel
        self._amplitude = amplitude
        self._pulse_width = pulse_width
        self._enable_low_frequency = enable_low_frequency
        self._name = name if name else f"muscle_{self._no_channel}"
        self._period = 1000.0 / frequency  # frequency (Hz) of the channel
        self.list_point = []  # list of points for the channel
        self._ramp = ramp
        self.check_value_param()

        if self.device_type == "Rehastim2" and ramp:
            raise RuntimeError("Ramp is not supported for Rehastim2")
        if self.device_type == "Rehastim2" and frequency != 50.0:
            raise RuntimeError("Frequency is not supported for Rehastim2")

        if self.device_type == "RehastimP24":
            smpt_channel_constant = self.CHANNEL_MAPPING.get(no_channel, 'Smpt_Channel_Undefined')
            self._smpt_channel = getattr(sciencemode, smpt_channel_constant, sciencemode.Smpt_Channel_Undefined)

            if mode == "Single" and self._amplitude and self._pulse_width:
                self.create_biphasic_pulse(self._amplitude, self._pulse_width) # Create a biphasic pulse for the channel
            if mode == "Doublet" and self._amplitude and self._pulse_width:  # Create a doublet pulse for the channel
                self.create_doublet(self._amplitude, self._pulse_width)
            elif mode == "Triplet" and self._amplitude and self._pulse_width:  # Create a triplet pulse for the channel
                self.create_triplet(self._amplitude, self._pulse_width)

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

    def create_biphasic_pulse(self, amplitude: int, pulse_width: int):
        """
        Create a biphasic pulse for the channel.

        Parameters
        ----------
        amplitude: int
            Current to send in the channel. [0,150] milli amp
        pulse_width: int
            Width of the stimulation. [0,4093] μs

        """

        positive_pulse = Point(pulse_width=pulse_width, amplitude=amplitude)
        negative_pulse = Point(pulse_width=pulse_width, amplitude=-amplitude)

        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)

    def create_doublet(self, amplitude: int, pulse_width: int):
        """
        Create a doublet pulse for the channel.

        Parameters
        ----------
        amplitude: int
            Current to send in the channel. [0,150] milli amp
        pulse_width: int
            Width of the stimulation. [0,4093] μs
        """

        # First biphasic pulse
        self.create_biphasic_pulse(amplitude, pulse_width)

        # Inter-pulse interval (IPI) = 5 ms. Can be adjusted if needed.
        self.list_point.append(Point(0, 0))
        self.list_point.append(Point(4000, 0))
        self.list_point.append(Point(1000, 0))

        # Second biphasic pulse
        self.create_biphasic_pulse(amplitude, pulse_width)

    def create_triplet(self, amplitude, pulse_width):
        """
        Create a triplet pulse for the channel.

        Parameters
        ----------
        amplitude: int
            Current to send in the channel. [0,150] milli amp
        pulse_width: int
            Width of the stimulation. [0,4093] μs
        """
        # First doublet pulse
        self.create_doublet(amplitude, pulse_width)
        # Inter-pulse interval (IPI) = 5 ms
        self.list_point.append(Point(0, 0))
        self.list_point.append(Point(4000, 0))
        self.list_point.append(Point(1000, 0))
        self.create_biphasic_pulse(amplitude, pulse_width)

    def check_device_type(self):
        """
        Check if the device type is correct. Raise an error otherwise.
        """
        if self.device_type != "Rehastim2" and self.device_type != "RehastimP24":
            raise ValueError("Error : Device type must be Rehastim2 or RehastimP24. Device type given : %s" % self.device_type)
        return self.device_type

    def check_value_param(self):
        """
        Checks if the values given correspond are in limits.
        """
        if self.device_type == "Rehastim2":
            if self._amplitude < 0 or self._amplitude > 130:
                raise ValueError("Error : Amplitude min = 0, max = 130. Amplitude given : %s" % self._amplitude)
            if self._no_channel < 1 or self._no_channel > 8:
                raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
            if self._pulse_width < 0 or self._pulse_width > 500:
                raise ValueError("Error : Impulsion time [0,500], given : %s" % self._pulse_width)

        if self.device_type == "RehastimP24":
            if self._period < 0.5 or self._period > 16383:
                raise ValueError("Error : Period min = 0.5, max = 16383. Period given : %s" % self._period)
            if self._no_channel < 1 or self._no_channel > 8:
                raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
            if self._amplitude < 0 or self._amplitude > 150:
                raise ValueError("Error : Amplitude min = 0, max = 150. Amplitude given : %s" % self._amplitude)
            if self._pulse_width < 0 or self._pulse_width > 4095:
                raise ValueError("Error : Impulsion time [0,500], given : %s" % self._pulse_width)
            if self._ramp < 0 or self._ramp > 16:
                raise ValueError("Error : Ramp min = 0, max = 16. Ramp given : %s" % self._ramp)

    def set_mode(self, mode: MODE):
        """
        Set mode.

        Parameters
        ----------
        mode: MODE
            Tell which mode is used.
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

        Parameters
        ----------
        amp: int
            Current to send in the channel.
        """
        self._amplitude = amp
        self.check_value_param()
        if self.check_device_type() == "RehastimP24" and self._pulse_width:
            self.create_biphasic_pulse(self._amplitude, self._pulse_width)

    def get_amplitude(self) -> int:
        """
        Returns amplitude.
        """
        return self._amplitude

    def set_no_channel(self, no_channel: int):
        """
        Set no_channel.

        Parameters
        ----------
        no_channel: int
            Number of the channel.
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

        Parameters
        ----------
        pulse_width: int
            Width of the stimulation.
        """
        self._pulse_width = pulse_width
        self.check_value_param()
        if self.device_type == "RehastimP24" and self._amplitude:  # Maybe remove this condition.
            self.create_biphasic_pulse(self._amplitude, self._pulse_width)

    def get_pulse_width(self) -> int:
        """
        Returns pulse_width.
        """
        return self._pulse_width

    def set_name(self, name: str):
        """
        Set name.

        Parameters
        ----------
        name: str
            Name of the muscle corresponding to the channel.
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

        Parameters
        ----------
        enable_low_frequency: bool
            Choose if the channel skip (True) or not (False) a given number of stimulation.
        """
        self._enable_low_frequency = enable_low_frequency

    def get_enable_low_frequency(self) -> bool:
        """
        Returns enable_low_frequency.
        """
        return self._enable_low_frequency

    def set_frequency(self, frequency: float):
        """
        Set the frequency for a channel

        Parameters
        ----------
        frequency: float
            Frequency of the channel (Hz)
        """
        if frequency <= 0:
            raise ValueError("frequency must be positive.")
        self._period = 1000.0 / frequency

    def get_frequency(self) -> float:
        """
        Returns the frequency of a channel
        """
        return 1000.0/self._period

    def get_ramp(self):
        """
        Returns the ramp of a channel
        """
        return self._ramp

    def set_ramp(self, ramp: int):
        """
        Set the ramp for a channel

        Parameters
        ----------
        ramp: int
            Ramp of the channel (pulses)
        """
        self._ramp = ramp
        self.check_value_param()

    def add_point(self, pulse_width: float, amplitude: float):
        """
        Add a point to the list of points for a channel. One channel can pilot 16 points.

        Parameters
        ----------
        pulse_width: float
            Width of the stimulation. [0,4093] μs
        amplitude: float
            Current to send in the channel. [-150,150] milli amp

        Returns
        -------
        point: Point
        """
        if len(self.list_point) < Channel.MAX_POINTS:
            point = Point(pulse_width, amplitude)
            self.list_point.append(point)
        else:
            raise ValueError(f"Cannot add more than {Channel.MAX_POINTS} points to a channel")
        return point


class Point:
    """
    Class to pilot a point for a channel.
    """
    def __init__(self, pulse_width: float, amplitude: float):
        self.pulse_width = pulse_width
        self.amplitude = amplitude
        self.check_parameters_point()

    def check_parameters_point(self):
        """
        Check if the values given correspond are in limits.
        """

        if not (0 <= self.pulse_width <= 4095):
            raise ValueError("Time must be between 0 and 4065.")
        if not (-150 <= self.amplitude <= 150):
            raise ValueError("Amplitude must be between -150 and 150.")

    def set_amplitude(self, amplitude: float):
        """
        Set current  for a point.

        Parameters
        ----------
        amplitude: float.
        """

        self.amplitude = amplitude
        self.check_parameters_point()

    def set_pulse_width(self, pulse_width: float):
        """
        Set time for a point.

        Parameters
        ----------
        pulse_width: float.
        """

        self.pulse_width = pulse_width
        self.check_parameters_point()




"""
Class used to construct a channel for each different electrode.
"""
from sciencemode_p24 import sciencemode


class Channel:
    """
    Class representing a channel.

    Class Attributes
    ----------------
    MODE: dict
        Contain the different names of the different modes
    """

    MODE = {"Single": 0, "Doublet": 1, "Triplet": 2, None: 3}
    MAX_POINTS = 16
    CHANNEL_MAPPING = {1: "Smpt_Channel_Red", 2: "Smpt_Channel_Blue", 3: "Smpt_Channel_Black", 4: "Smpt_Channel_White"}

    def __init__(
        self,
        mode: str = None,
        no_channel: int = 1,
        amplitude: int | float = 0,
        pulse_width: int = 0,
        enable_low_frequency: bool = False,
        name: str = None,
        device_type: str = None,
        frequency: float = 50.0,
        ramp: int = 0,
    ):
        """
        Create an object Channel.
        Check if the values given are in limits.

        Parameters
        ----------
        mode: MODE
            Indicate which mode is used. Single, Doublet, Triplet or None.
                If single, the channel will send a single biphasic pulse.
                If doublet, the channel will send a doublet biphasic pulse.
                If triplet, the channel will send a triplet biphasic pulse.
                If None, the channel will send the customed pulse.
        no_channel: int
            Channel number [1,8].
        amplitude: int | float
            Channel current. [0,130] mA for Rehastim2, [0,150] mA for RehastimP24
        pulse_width: int
            Stimulation width. [0,500] μs (current version of rehastim2 [20, 500] μs, if (pw < 20) then pw = 20)
            [0,4095] μs for RehastimP24
        enable_low_frequency: bool
            Choose if the channel skip (True) or not (False) a given number of stimulation.
        name: str
            Muscle name corresponding to the channel.
        device_type: str
            Device type used. Either Rehastim2 or RehastimP24
        frequency: float
            Channel frequency. [0.5, 1000] Hz
        """
        self.device_type = device_type  # Check if the device is Rehastim2 or RehastimP24
        self._mode = self.MODE[mode]
        self._no_channel = no_channel
        self._amplitude = amplitude
        self._pulse_width = pulse_width
        self._enable_low_frequency = enable_low_frequency
        self._name = name if name else f"muscle_{self._no_channel}"
        self._period = 1000.0 / frequency  # Frequency (Hz) of the channel
        self.list_point = []  # List of points for the channel
        self._ramp = ramp
        self.check_device_type()
        self.check_value_param()

        if self.device_type == "Rehastim2" and ramp:
            raise RuntimeError("Ramp is not supported for Rehastim2")
        if self.device_type == "Rehastim2" and frequency != 50.0:
            # If the user enters a frequency for a Rehastim2 channel, raise an error.
            # the frequency must still have a default value (50 in this case), otherwise division by 0.
            raise RuntimeError("Frequency can not be set for individual channel for the Rehastim2")

        if self.device_type == "RehastimP24":
            smpt_channel_constant = self.CHANNEL_MAPPING.get(no_channel, "Smpt_Channel_Undefined")
            self._smpt_channel = getattr(sciencemode, smpt_channel_constant, sciencemode.lib.Smpt_Channel_Undefined)

            self.generate_pulse()

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

    def is_pulse_symmetric(self):
        """
        Checks if the pulse is symmetric by ensuring the positive area is equal to the negative area.

        Parameters
        ----------
        safety: bool
            Whether to perform the symmetry check or not.

        Returns
        -------
        bool:
            True if the pulse is symmetric or if the safety check is disabled, otherwise False.
        """

        positive_area = 0
        negative_area = 0

        for point in self.list_point:
            if point.amplitude > 0:
                positive_area += point.amplitude * point.pulse_width
            else:
                negative_area -= point.amplitude * point.pulse_width

        return abs(positive_area - negative_area) < 1e-6

    def create_biphasic_pulse(self, amplitude: int | float, pulse_width: int):
        """
        Create a single biphasic pulse for the channel.

        Parameters
        ----------
        amplitude: int | float
            Current to send to the channel. [0,150] mA
        pulse_width: int
            Stimulation width. [0,4093] μs

        """
        self.list_point.clear()
        positive_pulse = Point(pulse_width=pulse_width, amplitude=amplitude)
        negative_pulse = Point(pulse_width=pulse_width, amplitude=-amplitude)

        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)

    def create_doublet(self, amplitude: int | float, pulse_width: int):
        """
        Create a doublet biphasic pulse for the channel.

        Parameters
        ----------
        amplitude: int | float
            Current to send in the channel. [0,150] mA
        pulse_width: int
            Stimulation width. [0,4093] μs
        """
        self.list_point.clear()

        # First biphasic pulse
        positive_pulse = Point(pulse_width=pulse_width, amplitude=amplitude)
        negative_pulse = Point(pulse_width=pulse_width, amplitude=-amplitude)

        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)

        # Inter-pulse interval (IPI) = 5 ms. Can be adjusted if needed.
        self.list_point.append(Point(0, 0))
        self.list_point.append(Point(4000, 0))
        self.list_point.append(Point(1000, 0))

        # Second biphasic pulse
        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)

    def create_triplet(self, amplitude: int | float, pulse_width: int):
        """
        Create a triplet biphasic pulse for the channel.

        Parameters
        ----------
        amplitude: int | float
            Current to send in the channel. [0,150] mA
        pulse_width: int
            Stimulation width. [0,4093] μs
        """
        # First doublet pulse
        self.list_point.clear()
        positive_pulse = Point(pulse_width=pulse_width, amplitude=amplitude)
        negative_pulse = Point(pulse_width=pulse_width, amplitude=-amplitude)

        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)
        # Inter-pulse interval (IPI) = 5 ms. Can be adjusted if needed.
        self.list_point.append(Point(0, 0))
        self.list_point.append(Point(4000, 0))
        self.list_point.append(Point(1000, 0))

        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)

        # Inter-pulse interval (IPI) = 5 ms
        self.list_point.append(Point(0, 0))
        self.list_point.append(Point(4000, 0))
        self.list_point.append(Point(1000, 0))

        # biphasic pulse
        self.list_point.append(positive_pulse)
        self.list_point.append(negative_pulse)

    def check_device_type(self):
        """
        Check if  device type is correct. Raise an error otherwise.
        """
        if self.device_type != "Rehastim2" and self.device_type != "RehastimP24":
            raise ValueError(
                "Error : Device type must be either Rehastim2 or RehastimP24. Device type given : %s" % self.device_type
            )
        return self.device_type

    def check_value_param(self):
        """
        Checks if the values given are in limits.
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
                raise ValueError("Error : Pulse Width [0,4095], given : %s" % self._pulse_width)
            if self._ramp < 0 or self._ramp > 16:
                raise ValueError("Error : Ramp min = 0, max = 16. Ramp given : %s" % self._ramp)

    def set_mode(self, mode: MODE):
        """
        Set mode.

        Parameters
        ----------
        mode: MODE
            Indicate which mode is used.
        """
        self._mode = mode

    def get_mode(self) -> MODE:
        """
        Returns mode.
        """
        return self._mode

    def set_amplitude(self, amplitude: int | float):
        """
        Set amplitude.

        Parameters
        ----------
        amplitude: int | float
            Current to send to the channel.
        """
        self._amplitude = amplitude
        self.check_value_param()
        self.generate_pulse()

    def get_amplitude(self) -> int | float:
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
            Channel number [1,8].
        """
        self._no_channel = no_channel
        self.check_value_param()
        self.generate_pulse()

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
            Stimulation Width [0,4095] μs
        """
        self._pulse_width = pulse_width
        self.check_value_param()
        self.generate_pulse()

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
            Muscle name corresponding to the channel.
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

    def set_frequency(self, frequency: int | float):
        """
        Set the frequency for a channel

        Parameters
        ----------
        frequency: int | float
            Channel frequency [0.5, 1000] Hz
        """
        if frequency <= 0:
            raise ValueError("frequency must be positive.")
        self._period = 1000.0 / frequency

        self.generate_pulse()

    def get_frequency(self) -> int | float:
        """
        Returns the frequency of a channel
        """
        return 1000.0 / self._period

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
            Channel ramp [0,16] pulses.
        """
        self._ramp = ramp
        self.check_value_param()
        self.generate_pulse()

    def set_device_type(self, device_type: str):
        """
        Set the device (Rehastim2 or RehastimP24) for a channel

        Parameters
        ----------
        device_type : str
            Device type used for the stimulation

        """
        self.device_type = device_type
        self.check_device_type()

    def get_device_type(self):
        """
        Get the actual device_type
        """
        return self.device_type

    def add_point(self, pulse_width: int, amplitude: int | float):
        """
        Add a point to the list of points for a channel. One channel can pilot 16 points.

        Parameters
        ----------
        pulse_width: int
            Width of the stimulation. [0,4093] μs
        amplitude: int | float
            Current to send in the channel. [-150,150] mA

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

    def generate_pulse(self):
        """
        Generate a pulse for a channel. The pulse is generated according to the mode and the parameters given.
        """
        if self.device_type == "RehastimP24":
            if self._mode == Channel.MODE["Single"]:  # Create a biphasic pulse for the channel
                self.create_biphasic_pulse(self._amplitude, self._pulse_width)
            elif self._mode == Channel.MODE["Doublet"]:  # Create a biphasic doublet pulse for the channel
                self.create_doublet(self._amplitude, self._pulse_width)
            elif self._mode == Channel.MODE["Triplet"]:  # Create a biphasic triplet pulse for the channel
                self.create_triplet(self._amplitude, self._pulse_width)


class Point:
    """
    Class to pilot a point for a channel.
    """

    def __init__(self, pulse_width: int, amplitude: int | float):
        self.pulse_width = pulse_width
        self.amplitude = amplitude
        self.check_parameters_point()

    def check_parameters_point(self):
        """
        Check if the values given are in limits.
        """

        if not (0 <= self.pulse_width <= 4095):
            raise ValueError("Pulse width must be between 0 and 4065.")
        if not (-150 <= self.amplitude <= 150):
            raise ValueError("Amplitude must be between -150 and 150.")

    def set_amplitude(self, amplitude: int | float):
        """
        Set current  for a point.

        Parameters
        ----------
        amplitude: int | float.
            Current for a stimulation point. [-150,150] mA
        """

        self.amplitude = amplitude
        self.check_parameters_point()

    def set_pulse_width(self, pulse_width: float):
        """
        Set time for a point.

        Parameters
        ----------
        pulse_width: int.
            Stimulation width. [0,4095] μs
        """

        self.pulse_width = pulse_width
        self.check_parameters_point()

"""
Class used to construct a channel for each different electrode.
"""
from .enums import Device, Modes


class Channel:
    """
    Class representing a channel.
    """

    MAX_POINTS = 16

    def __init__(
            self,
            mode: str | Modes = None,
            no_channel: int = 1,
            amplitude: int | float = 0,
            pulse_width: int = 0,
            enable_low_frequency: bool = False,
            name: str = None,
            device_type: str | Device = None,
            frequency: float = 50.0,
            ramp: int = 0,
    ):
        """
        Create an object Channel.
        Check if the values given are in limits.

        Parameters
        ----------
        mode: str | Modes
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
        device_type: str | Device
            Device type used. Either Rehastim2 or RehastimP24
        frequency: float
            Channel frequency. [0.5, 2000] Hz
        """
        self._no_channel = no_channel
        self._amplitude = amplitude
        self._pulse_width = pulse_width
        self._enable_low_frequency = enable_low_frequency
        self._name = name if name else f"muscle_{self._no_channel}"
        self._period = 1000.0 / frequency  # Frequency (Hz) of the channel
        self.list_point = []  # List of points for the channel

        if isinstance(device_type, str):
            device_type = device_type.lower().capitalize()
            try:
                self.device_type = Device[device_type].value
            except KeyError:
                valid_devices = ", ".join([d.name for d in Device])
                raise ValueError(f"device_type must be one of the following: {valid_devices}")
        elif isinstance(device_type, Device):
            self.device_type = device_type.value
        else:
            raise TypeError("device_type must be a string or a Device enum instance")

        if mode is not None:
            if isinstance(mode, str):
                try:
                    self._mode = Modes[mode.upper()].value
                except KeyError:
                    valid_modes = ", ".join([m.name for m in Modes])
                    raise ValueError(f"Choose a correct mode among {valid_modes.lower()}")
            elif isinstance(mode, Modes):
                self._mode = mode.value
            else:
                raise TypeError("mode must be a string or a Modes enum instance")
        else:
            self._mode = Modes.NONE.value

        if mode is not None and pulse_width is None:
            raise ValueError("pulse_width must be provided if mode is not None")
        if mode is not None and amplitude is None:
            raise ValueError("amplitude must be provided if mode is not None")

        self._ramp = ramp
        self.check_value_param()

        if self.device_type == Device.Rehastim2.value and ramp:
            raise RuntimeError("Ramp is not supported for Rehastim2")
        if self.device_type == Device.Rehastim2.value and frequency != 50.0:
            # If the user enters a frequency for a Rehastim2 channel, raise an error.
            # the frequency must still have a default value (50 in this case), otherwise division by 0.
            raise RuntimeError("Frequency can not be set for individual channel for the Rehastim2")

        if self.device_type == Device.Rehastimp24.value:
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

    def is_pulse_symmetric(self) -> bool:
        """
        Checks if the pulse is symmetric by ensuring the positive area is equal to the negative area.

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

    def create_single_biphasic_pulse(self, amplitude: int | float, pulse_width: int):
        """
        Create a single biphasic pulse for the channel.

        Parameters
        ----------
        amplitude: int | float
            Current to send to the channel. [0,150] mA
        pulse_width: int
            Stimulation width. [0,4095] μs

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
            Stimulation width. [0,4095] μs
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
            Stimulation width. [0,4095] μs
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

    def check_value_param(self):
        """
        Checks if the values given are in limits.
        """
        if self.device_type == Device.Rehastim2.value:
            if self._amplitude < 0 or self._amplitude > 130:
                raise ValueError("Error : Amplitude min = 0, max = 130. Amplitude given : %s" % self._amplitude)
            if self._no_channel < 1 or self._no_channel > 8:
                raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
            if self._pulse_width < 0 or self._pulse_width > 500:
                raise ValueError("Error : Impulsion time [0,500], given : %s" % self._pulse_width)

        if self.device_type == Device.Rehastimp24.value:
            if self._period < 0.5 or self._period > 16383:
                raise ValueError(
                    "Error : Frequency min = 0.5, max = 2000. Frequency given : %s Hz" % (1000 / self._period)
                )
            if self._no_channel < 1 or self._no_channel > 8:
                raise ValueError("Error : 8 channel possible. Channel given : %s" % self._no_channel)
            if self._amplitude < 0 or self._amplitude > 130:
                raise ValueError("Error : Amplitude min = 0, max = 130. Amplitude given : %s" % self._amplitude)
            if self._pulse_width < 0 or self._pulse_width > 4095:
                raise ValueError("Error : Pulse Width [0,4095], given : %s" % self._pulse_width)
            if self._ramp < 0 or self._ramp > 16:
                raise ValueError("Error : Ramp min = 0, max = 16. Ramp given : %s" % self._ramp)

    def set_mode(self, mode: str | Modes):
        """
        Set mode.

        Parameters
        ----------
        mode: str | Modes
            Indicate which mode is used.
        """

        if isinstance(mode, str):
            try:
                self._mode = Modes[mode.upper()].value
            except KeyError:
                raise ValueError(f"{mode} is not a valid mode")
        elif isinstance(mode, Modes):
            self._mode = mode.value
        else:
            raise ValueError("mode must be a string or a Modes enum instance")

        self.generate_pulse()

    def get_mode(self):
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
        self.generate_pulse()

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
        if self.device_type == Device.Rehastimp24.value:
            if frequency <= 0:
                raise ValueError("frequency must be positive.")
            self._period = 1000.0 / frequency
            self.generate_pulse()
        else:
            raise ValueError("Frequency can not be set for individual channel for the Rehastim2")

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
        if self.device_type == Device.Rehastimp24.value:
            self._ramp = ramp
            self.check_value_param()
            self.generate_pulse()
        else:
            raise ValueError("Ramp is not supported for Rehastim2")

    def set_device_type(self, device_type: str | Device):
        """
        Set the device (Rehastim2 or RehastimP24) for a channel

        Parameters
        ----------
        device_type : str | Device
            Device type used for the stimulation

        """
        if isinstance(device_type, str):
            try:
                normalized_device_type = device_type.lower().capitalize()
                self.device_type = Device[normalized_device_type].value
            except KeyError:
                valid_devices = ", ".join([d.value for d in Device])
                raise ValueError(f"device_type must be one of the following: {valid_devices}")
        elif isinstance(device_type, Device):
            self.device_type = device_type.value
        else:
            raise TypeError("device_type must be a int or Device type ")

    def get_device_type(self):
        """
        Get the actual device_type
        """
        return self.device_type

    def add_point(self, pulse_width: int, amplitude: int | float):
        """
        Add a point to the list of points for a channel. One channel can pilot 16 points.
        Used for the RehastimP24

        Parameters
        ----------
        pulse_width: int
            Width of the stimulation. [0,4095] μs
        amplitude: int | float
            Current to send in the channel. [-150,150] mA

        Returns
        -------
        point: Point
        """
        if self.device_type == Device.Rehastimp24.value:
            if len(self.list_point) < Channel.MAX_POINTS:
                point = Point(pulse_width, amplitude)
                self.list_point.append(point)
            else:
                raise ValueError(f"Cannot add more than {Channel.MAX_POINTS} points to a channel")
            return point
        else:
            raise ValueError("Point control not available on Rehastim2")

    def generate_pulse(self):
        """
        Generate a pulse for a channel. The pulse is generated according to the mode and the parameters given.
        """
        if self.device_type == Device.Rehastimp24.value:
            if self._mode == Modes.SINGLE.value:
                self.create_single_biphasic_pulse(self._amplitude, self._pulse_width)
            if self._mode == Modes.DOUBLET.value:
                self.create_doublet(self._amplitude, self._pulse_width)
            if self._mode == Modes.TRIPLET.value:
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
        if not (-130 <= self.amplitude <= 130):
            raise ValueError("Amplitude must be between -130 and 130.")

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

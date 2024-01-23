import logging

from pyScienceMode import Channel, Point, Device, Modes
from pyScienceMode import RehastimP24 as St
from pyScienceMode import Rehastim2 as St2
import random
from time import sleep
from sciencemode import sciencemode
from biosiglive import ViconClient, DeviceType
import numpy as np

logger = logging.getLogger("pyScienceMode")

"""
This file is used to test the performance of both devices (RehastimP24 and Rehastim2).
The tests are done with Vicon Nexus and the biosiglive library.
Some tests can be used for both devices, some others are specific to one device. You can
choose the device you want by putting the right device enum in the function.
"""


def get_trigger():
    """
    This function is used to get the trigger from Vicon.
    """
    interface = init_trigger()
    interface.get_frame()
    interface.add_device(
        nb_channels=2,
        device_type=DeviceType.Generic,
        name="stim",
        rate=10000,
    )
    stimulatorp24 = St(port="COM4", show_log=True)
    while True:
        trigger_data = interface.get_device_data(device_name="stim")[1:, :]
        idx = np.argwhere(trigger_data > 1.5)
        if len(idx) > 0:
            stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=0.1)


def init_trigger():
    """
    Initialize the trigger.
    """
    interface = ViconClient(ip="192.168.1.211", system_rate=100, init_now=True)
    return interface


def custom_shape_pulse():
    """
    Test of the new feature of the RehastimP24 : custom shape pulse
    """
    stimulatorp24 = St(port="COM4", show_log=True)
    channel_1 = Channel(no_channel=1, name="Biceps", amplitude=30, frequency=20, device_type=Device.Rehastimp24)

    list_channels.append(channel_1)

    stimulatorp24.init_stimulation(list_channels=list_channels)

    # Test pulse with only one point
    point1 = channel_1.add_point(300, 20)
    stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=False)

    # Test biphasic pulse
    point2 = channel_1.add_point(300, -20)
    stimulatorp24.update_stimulation(upd_list_channels=list_channels)

    # Test random shape pulse with 6 points
    point3 = channel_1.add_point(300, 10)
    point4 = channel_1.add_point(300, -10)
    point5 = channel_1.add_point(300, 5)
    point6 = channel_1.add_point(300, -5)
    stimulatorp24.update_stimulation(upd_list_channels=list_channels)

    # Test random shape pulse with 16 points
    channel_1.list_point.clear()  # Clear the list of points to create a new one
    for _ in range(16):
        amplitude = random.randint(-130, 130)
        duration = random.randint(0, 4095)
        channel_1.add_point(duration, amplitude)

    stimulatorp24.update_stimulation(upd_list_channels=list_channels)
    stimulatorp24.end_stimulation()
    list_channels.clear()
    channel_1.list_point.clear()


def single_doublet_triplet(device: Device):
    """
    Mode test (single, doublet, triplet) for both devices. It uses 3 channels at the same time.
    """
    if device == Device.Rehastimp24:
        stimulatorp24 = St(port="COM4", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE,
            no_channel=1,
            name="Biceps",
            amplitude=30,
            pulse_width=350,
            frequency=20,
            device_type=Device.Rehastimp24,
        )
        channel_2 = Channel(
            mode=Modes.DOUBLET,
            no_channel=2,
            name="Biceps",
            amplitude=30,
            frequency=20,
            pulse_width=350,
            device_type=Device.Rehastimp24,
        )
        channel_3 = Channel(
            mode=Modes.TRIPLET,
            no_channel=3,
            name="Biceps",
            amplitude=30,
            frequency=20,
            pulse_width=350,
            device_type=Device.Rehastimp24,
        )

        list_channels.append(channel_1)
        list_channels.append(channel_2)
        list_channels.append(channel_3)

        stimulatorp24.init_stimulation(list_channels=list_channels)
        stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=True)

        channel_1.set_mode(Modes.DOUBLET)
        channel_2.set_mode(Modes.TRIPLET)
        channel_3.set_mode(Modes.SINGLE)

        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        channel_1.set_mode(Modes.TRIPLET)
        channel_2.set_mode(Modes.SINGLE)
        channel_3.set_mode(Modes.DOUBLET)

        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        stimulatorp24.end_stimulation()
        list_channels.clear()
        channel_1.list_point.clear()
        channel_2.list_point.clear()
        channel_3.list_point.clear()

    if device == Device.Rehastim2:
        stimulator2 = St2(port="COM3", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE, no_channel=2, name="Biceps", amplitude=30, pulse_width=350, device_type=Device.Rehastim2
        )
        channel_2 = Channel(
            mode=Modes.DOUBLET, no_channel=3, name="Biceps", amplitude=30, pulse_width=350, device_type=Device.Rehastim2
        )
        channel_3 = Channel(
            mode=Modes.TRIPLET, no_channel=4, name="Biceps", amplitude=30, pulse_width=350, device_type=Device.Rehastim2
        )

        list_channels.append(channel_1)
        list_channels.append(channel_2)
        list_channels.append(channel_3)

        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=50)
        stimulator2.start_stimulation(stimulation_duration=2)

        channel_1.set_mode(Modes.DOUBLET)
        channel_2.set_mode(Modes.TRIPLET)
        channel_3.set_mode(Modes.SINGLE)

        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)

        channel_1.set_mode(Modes.TRIPLET)
        channel_2.set_mode(Modes.SINGLE)
        channel_3.set_mode(Modes.DOUBLET)

        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        stimulator2.end_stimulation()
        list_channels.clear()


def frequency_test(device: Device):
    """
    Test of the frequency for both devices,  we compare with the real frequency measured with Vicon and pyomeca.
    """
    # Test with 10Hz
    if device == Device.Rehastimp24:
        stimulatorp24 = St(port="COM4", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE,
            no_channel=1,
            name="Biceps",
            amplitude=30,
            pulse_width=350,
            frequency=10,
            device_type=Device.Rehastimp24,
        )
        list_channels.append(channel_1)

        stimulatorp24.init_stimulation(list_channels=list_channels)
        stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=True)

        # Test with 50Hz
        channel_1.set_frequency(50)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)

        # Test with 100Hz
        channel_1.set_frequency(100)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        stimulatorp24.end_stimulation()

        list_channels.clear()
        channel_1.list_point.clear()

    else:
        stimulator2 = St2(port="COM3", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE, no_channel=2, name="Biceps", amplitude=30, pulse_width=350, device_type=Device.Rehastim2
        )
        list_channels.append(channel_1)

        # Test with 10Hz
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=100)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)

        # Test with 50Hz
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=20)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)

        # Test with 100Hz
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=10)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        stimulator2.end_stimulation()
        list_channels.clear()


def force_rehastim2():
    """
    Same pattern as the force_rehastimp24 to compare the output force of the ergometer handle of the two devices
    """
    stimulator2 = St2(port="COM3", show_log=True)
    channel_1 = Channel(
        mode=Modes.SINGLE, no_channel=1, name="Biceps", amplitude=30, pulse_width=300, device_type=Device.Rehastim2
    )

    list_channels.append(channel_1)
    for _ in range(10):
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=33)
        stimulator2.start_stimulation(stimulation_duration=1)
        sleep(1)
    stimulator2.end_stimulation()
    stimulator2.disconnect()
    list_channels.clear()


def force_rehastimp24():
    """
    This function is used to compare the force output of the two devices.
    """
    stimulatorp24 = St(port="COM4", show_log=True)
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=1,
        name="Biceps",
        amplitude=10,
        pulse_width=300,
        frequency=100,
        device_type=Device.Rehastimp24,
    )
    list_channels.append(channel_1)
    stimulatorp24.init_stimulation(list_channels=list_channels)
    for _ in range(10):
        stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=1, safety=True)
        sleep(1)

    stimulatorp24.end_stimulation()
    list_channels.clear()
    channel_1.list_point.clear()


def more_than_16_points():
    """
    Test to stimulate with more than 16 points. (only for RehastimP24)
    """
    stimulatorp24 = St(port="COM4", show_log=True)
    channel_1 = Channel(no_channel=1, name="Biceps", frequency=20, device_type=Device.Rehastimp24)

    # Need to remove the max_point condition in channel.py (add_point function)
    list_channels.append(channel_1)
    stimulatorp24.init_stimulation(list_channels=list_channels)
    for _ in range(8):
        channel_1.add_point(300, 20)
        channel_1.add_point(300, -20)
    channel_1.add_point(300, 20)  # Add the 17th point
    stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=False)
    stimulatorp24.end_stimulation()
    list_channels.clear()
    channel_1.list_point.clear()

    # Same thing but with the low level mode
    for point in channel_1.list_point:
        list_points.append(point)

    stimulatorp24.start_stim_one_channel_stimulation(
        no_channel=1, points=list_points, stim_sequence=100, pulse_interval=33, safety=False
    )
    stimulatorp24.end_stim_one_channel()

    list_channels.clear()
    list_points.clear()
    channel_1.list_point.clear()


def update_parameters(device: Device):
    """
    Test to update the parameters of the stimulation (amplitude, pulse width, frequency, mode, no_channel)
    for both devices. It uses 2 channels.
    """
    if device == Device.Rehastimp24:
        stimulatorp24 = St(port="COM4", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE,
            no_channel=1,
            name="Biceps",
            amplitude=20,
            pulse_width=350,
            frequency=50,
            device_type=Device.Rehastimp24,
        )
        list_channels.append(channel_1)
        stimulatorp24.init_stimulation(list_channels=list_channels)
        stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=True)
        channel_1.set_frequency(10)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        channel_1.set_amplitude(10)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        channel_1.set_pulse_width(500)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        channel_1.set_mode(Modes.TRIPLET)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        channel_1.set_frequency(20)
        channel_1.set_amplitude(20)
        channel_1.set_pulse_width(350)
        channel_1.set_mode(Modes.SINGLE)
        channel_1.set_no_channel(2)
        stimulatorp24.init_stimulation(list_channels=list_channels)
        sleep(2)
        stimulatorp24.update_stimulation(upd_list_channels=list_channels)
        stimulatorp24.end_stimulation()

        list_channels.clear()
        channel_1.list_point.clear()
    else:
        stimulator2 = St2(port="COM3", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE, no_channel=2, name="Biceps", amplitude=20, pulse_width=350, device_type=Device.Rehastim2
        )
        list_channels.append(channel_1)
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=20)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=100)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        channel_1.set_amplitude(10)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        channel_1.set_pulse_width(500)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        channel_1.set_mode(Modes.TRIPLET)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)

        channel_1.set_amplitude(20)
        channel_1.set_pulse_width(350)
        channel_1.set_mode(Modes.SINGLE)
        channel_1.set_no_channel(3)
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=50)
        sleep(1)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)
        stimulator2.end_stimulation()
        stimulator2.disconnect()
        list_channels.clear()


def diff_frequency_ll_ml(frequency):
    """
    Test if they are differences between the low level mode and the medium level mode for the frequency for
    a custom shape pulse.
    """
    stimulatorp24 = St(port="COM4", show_log=True)
    channel_1 = Channel(
        no_channel=1, name="Biceps", amplitude=20, pulse_width=350, frequency=frequency, device_type=Device.Rehastimp24
    )
    list_channels.append(channel_1)
    stimulatorp24.init_stimulation(list_channels=list_channels)

    channel_1.add_point(300, 20)
    channel_1.add_point(300, -20)
    channel_1.add_point(300, 20)
    channel_1.add_point(300, -20)
    channel_1.add_point(300, 10)
    channel_1.add_point(300, -10)

    stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=True)
    stimulatorp24.end_stimulation()

    for point in channel_1.list_point:
        list_points.append(point)
        logger.info(point.pulse_width, point.amplitude)
    sleep(2)
    stimulatorp24.start_stim_one_channel_stimulation(
        no_channel=1, points=list_points, stim_sequence=100, pulse_interval=1000 / frequency
    )
    stimulatorp24.end_stim_one_channel()
    list_channels.clear()
    channel_1.list_point.clear()
    list_points.clear()


def communication_speed_P24():
    """
    Test to see the communication speed between the computer and the RehastimP24
    """
    stimulatorp24 = St(port="COM4", show_log=True)
    stimulatorp24.ll_init()
    point1 = Point(100, 20)
    point2 = Point(100, -20)
    list_points.append(point1)
    list_points.append(point2)

    waiting_time = 1
    ll_config = sciencemode.ffi.new("Smpt_ll_channel_config*")
    ll_config.enable_stimulation = True
    ll_config.channel = sciencemode.lib.Smpt_Channel_Red
    ll_config.connector = sciencemode.lib.Smpt_Connector_Yellow
    ll_config.number_of_points = len(list_points)
    ll_config.points[0].time = list_points[0].pulse_width
    ll_config.points[0].current = list_points[0].amplitude
    ll_config.points[1].time = list_points[1].pulse_width
    ll_config.points[1].current = list_points[1].amplitude
    while True:
        ll_config.packet_number = sciencemode.lib.smpt_packet_number_generator_next(stimulatorp24.device)
        sciencemode.lib.smpt_send_ll_channel_config(stimulatorp24.device, ll_config)
        sleep(waiting_time)
        waiting_time *= 0.9
        logger.info(waiting_time)


def limit_parameters(device: Device):
    """
    Test to see the limit of the parameters for both devices
    """
    if device == Device.Rehastimp24:
        stimulatorp24 = St(port="COM4", show_log=True)
        channel_1 = Channel(no_channel=1, name="Biceps", frequency=15, device_type=Device.Rehastimp24)
        list_channels.append(channel_1)
        for _ in range(8):
            channel_1.add_point(4095, 130)
            channel_1.add_point(4095, -130)
        stimulatorp24.init_stimulation(list_channels=list_channels)
        stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=True)
        stimulatorp24.end_stimulation()
        list_channels.clear()
        channel_1.list_point.clear()
    else:
        list_channels.clear()
        stimulator2 = St2(port="COM3", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE, no_channel=1, pulse_width=500, amplitude=130, name="Biceps", device_type=Device.Rehastim2
        )
        list_channels.append(channel_1)
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=8)
        stimulator2.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)


def communication_speed_r2():
    """
    Test to see the communication speed between the computer and the Rehastim2.
    """
    stimulator2 = St2(port="COM3", show_log=True)
    channel_1 = Channel(mode=Modes.SINGLE, no_channel=2, amplitude=10, pulse_width=100, device_type=Device.Rehastim2)

    list_channels.append(channel_1)
    stimulator2.init_channel(stimulation_interval=8, list_channels=list_channels)
    amplitude = 10
    waiting_time = 1
    while True:
        stimulator2.start_stimulation(stimulation_duration=0.35)
        amplitude *= 1.01
        channel_1.set_amplitude(amplitude)
        sleep(waiting_time)
        waiting_time *= 0.9
        logger.info(waiting_time)


def decalage(freq1, freq2, freq3, device: Device):
    """
    Test to see if there is a delay between the stimulation of the 3 channels for both devices.
    """
    if device == Device.Rehastimp24:
        stimulatorp24 = St(port="COM4", show_log=True)
        channel_1 = Channel(
            mode=Modes.SINGLE,
            no_channel=1,
            name="Biceps",
            amplitude=20,
            pulse_width=350,
            frequency=freq1,
            device_type=Device.Rehastimp24,
        )
        channel_2 = Channel(
            mode=Modes.TRIPLET,
            no_channel=2,
            name="Biceps",
            amplitude=20,
            pulse_width=350,
            frequency=freq2,
            device_type=Device.Rehastimp24,
        )
        channel_3 = Channel(
            mode=Modes.TRIPLET,
            no_channel=3,
            name="Biceps",
            amplitude=20,
            pulse_width=350,
            frequency=freq3,
            device_type=Device.Rehastimp24,
        )
        list_channels.append(channel_1)
        list_channels.append(channel_2)
        list_channels.append(channel_3)
        stimulatorp24.init_stimulation(list_channels=list_channels)
        stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=3, safety=True)
        stimulatorp24.end_stimulation()

        list_channels.clear()
        channel_1.list_point.clear()
        channel_2.list_point.clear()
        channel_3.list_point.clear()

    if device == Device.Rehastim2:
        stimulator2 = St2(port="COM3", show_log=True)
        list_channels.clear()
        channel_1 = Channel(
            mode=Modes.TRIPLET, no_channel=2, name="Biceps", amplitude=20, pulse_width=350, device_type=Device.Rehastim2
        )
        channel_2 = Channel(
            mode=Modes.TRIPLET, no_channel=3, name="Biceps", amplitude=20, pulse_width=350, device_type=Device.Rehastim2
        )
        channel_3 = Channel(
            mode=Modes.TRIPLET, no_channel=4, name="Biceps", amplitude=20, pulse_width=350, device_type=Device.Rehastim2
        )
        list_channels.append(channel_1)
        list_channels.append(channel_2)
        list_channels.append(channel_3)
        stimulator2.init_channel(list_channels=list_channels, stimulation_interval=8)
        stimulator2.start_stimulation(stimulation_duration=3)
        stimulator2.end_stimulation()
        stimulator2.disconnect()


def exe():
    """
    Test to see if the python program do the same thing as the .exe program.
    """
    stimulatorp24 = St(port="COM4", show_log=True)
    channel_1 = Channel(no_channel=1, amplitude=20, pulse_width=350, frequency=50, device_type=Device.Rehastimp24)
    list_channels.append(channel_1)
    stimulatorp24.init_stimulation(list_channels=list_channels)
    channel_1.add_point(350, 20)
    channel_1.add_point(350, -20)
    channel_1.add_point(350, 10)
    channel_1.add_point(350, -10)

    stimulatorp24.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2, safety=True)
    stimulatorp24.end_stimulation()
    list_channels.clear()
    channel_1.list_point.clear()


if __name__ == "__main__":
    list_points = []
    list_channels = []
    # Use the fonction you want to test here

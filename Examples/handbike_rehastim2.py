import time

import nidaqmx

from pysciencemode import Rehastim2 as St
from pysciencemode import Channel as Ch
from pysciencemode import Device, Modes

"""
This example shows how to use the P24 device for a hand cycling purpose.
Because the P24 device is not compatible with the MotoMed, this example will showcase the use of an encoder.
Therefore the nidaqmx library will be used to recover the pedal angle of the bike.
"""


class HandCycling2:
    def __init__(self):
        super(HandCycling2, self).__init__()
        channel_muscle_name = [
            "Triceps_r",
            "Biceps_r",
            "Delt_ant_r",
            "Delt_post_r",
            "Triceps_l",
            "Biceps_l",
            "Delt_ant_l",
            "Delt_post_l",
        ]
        self.list_channels = [
            Ch(
                mode=Modes.SINGLE,
                no_channel=i,
                amplitude=0,
                pulse_width=350,
                name=channel_muscle_name[i - 1],
                device_type=Device.Rehastim2,
            )
            for i in range(1, 9)
        ]

        # Set the intensity for each muscles
        self.intensity = {
            "biceps_r": 10,
            "triceps_r": 10,
            "delt_ant_r": 5,
            "delt_post_r": 5,
            "biceps_l": 10,
            "triceps_l": 10,
            "delt_ant_l": 5,
            "delt_post_l": 5,
        }

        self.channel_number = {
            "biceps_r": 2,
            "triceps_r": 1,
            "delt_ant_r": 3,
            "delt_post_r": 4,
            "biceps_l": 6,
            "triceps_l": 5,
            "delt_ant_l": 7,
            "delt_post_l": 8,
        }

        self.stimulation_state = {
            "triceps_r": False,
            "biceps_r": False,
            "delt_ant_r": False,
            "delt_post_r": False,
            "triceps_l": False,
            "biceps_l": False,
            "delt_ant_l": False,
            "delt_post_l": False,
        }

        # Create our object Stimulator
        self.stimulator = St(port="COM7", show_log=False)
        self.stimulator.init_channel(
            stimulation_interval=22,
            list_channels=self.list_channels,
            low_frequency_factor=0,
        )
        self.angle = 0

        self.stimulation_range = {
            "biceps_r": [220, 10],
            "triceps_r": [20, 180],
            "delt_ant_r": [20, 180],
            "delt_post_r": [220, 10],
            "biceps_l": [40, 190],
            "triceps_l": [200, 360],
            "delt_ant_l": [200, 360],
            "delt_post_l": [40, 190],
        }

        self.stim_condition = {}
        for key in self.stimulation_range.keys():
            self.stim_condition[key] = (
                1
                if self.stimulation_range[key][0] < self.stimulation_range[key][1]
                else 0
            )

        # This is to initialize the encoder for the pedal angle
        local_system = nidaqmx.system.System.local()
        driver_version = local_system.driver_version
        print(
            "DAQmx {0}.{1}.{2}".format(
                driver_version.major_version,
                driver_version.minor_version,
                driver_version.update_version,
            )
        )
        for device in local_system.devices:
            print(
                "Device Name: {0}, Product Category: {1}, Product Type: {2}".format(
                    device.name, device.product_category, device.product_type
                )
            )
            device_mane = device.name
            self.task = nidaqmx.Task()
            self.task.ai_channels.add_ai_voltage_chan(device_mane + "/ai14")
            self.task.start()

            self.min_voltage = 1.33
            max_voltage = 5
            self.origin = self.task.read() - self.min_voltage
            self.angle_coeff = 360 / (max_voltage - self.min_voltage)
            self.actual_voltage = None

    def get_angle(self):
        voltage = self.task.read() - self.min_voltage
        self.actual_voltage = voltage - self.origin
        self.angle = (
            360 - (self.actual_voltage * self.angle_coeff)
            if 0 < self.actual_voltage <= 5 - self.origin
            else abs(self.actual_voltage) * self.angle_coeff
        )

    def stimulate(self):
        self.stimulator.start_stimulation(upd_list_channels=self.list_channels)

        while 1:
            self.get_angle()
            intensity_to_update = False
            for key in self.stimulation_range.keys():
                if self.stim_condition[key] == 0:
                    if (
                        self.stimulation_range[key][0] <= self.angle <= 360
                        or 0 <= self.angle <= self.stimulation_range[key][1]
                    ) and self.stimulation_state[key] is False:
                        self.stimulation_state[key] = True
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(
                            self.intensity[key]
                        )
                        intensity_to_update = True
                    elif (
                        self.stimulation_range[key][1]
                        < self.angle
                        < self.stimulation_range[key][0]
                        and self.stimulation_state[key] is True
                    ):
                        self.stimulation_state[key] = False
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(
                            0
                        )
                        intensity_to_update = True
                else:
                    if (
                        self.stimulation_range[key][0]
                        <= self.angle
                        <= self.stimulation_range[key][1]
                        and self.stimulation_state[key] is False
                    ):
                        self.stimulation_state[key] = True
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(
                            self.intensity[key]
                        )
                        intensity_to_update = True
                    elif (
                        self.stimulation_range[key][0] > self.angle
                        or self.angle > self.stimulation_range[key][1]
                    ) and self.stimulation_state[key] is True:
                        self.stimulation_state[key] = False
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(
                            0
                        )
                        intensity_to_update = True
            if intensity_to_update:
                self.stimulator.start_stimulation(upd_list_channels=self.list_channels)

            time.sleep(0.001)


if __name__ == "__main__":
    HandCycling2().stimulate()

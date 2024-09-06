import time

import nidaqmx

from pyScienceMode import Rehastim2 as St
from pyScienceMode import Channel as Ch
from pyScienceMode import Device, Modes

"""
This example shows how to use the RehastimP24 device for a hand cycling purpose.
Because the RehastimP24 device is not compatible with the MotoMed, this example will showcase the use of an encoder.
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
        self.intensity = {"biceps_r": 28,
                          "triceps_r": 26,
                          "delt_ant_r": 25,
                          "delt_post_r": 30,
                          "biceps_l": 26,
                          "triceps_l": 28,
                          "delt_ant_l": 34,
                          "delt_post_l": 36}

        self.channel_number = {"biceps_r": 2,
                               "triceps_r": 1,
                               "delt_ant_r": 3,
                               "delt_post_r": 4,
                               "biceps_l": 6,
                               "triceps_l": 5,
                               "delt_ant_l": 7,
                               "delt_post_l": 8}

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
        self.stimulator = St(port="COM7", show_log=True)
        self.stimulator.init_channel(
            stimulation_interval=22, list_channels=self.list_channels, low_frequency_factor=0
        )

        self.angle = 0

        self.stimulation_range = {"biceps_r": [220, 10],
                                  "triceps_r": [20, 180],
                                  "delt_ant_r": [20, 180],
                                  "delt_post_r": [220, 10],
                                  "biceps_l": [40, 190],
                                  "triceps_l": [200, 360],
                                  "delt_ant_l": [200, 360],
                                  "delt_post_l": [40, 190]}

        self.stim_condition = {}
        for key in self.stimulation_range.keys():
            self.stim_condition[key] = 1 if self.stimulation_range[key][0] < self.stimulation_range[key][1] else 0

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
            self.stimulation_state = None

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
            print(self.angle)

            for key in self.stimulation_range.keys():
                if self.stim_condition[key] == 0:
                    if self.stimulation_range[key][0] <= self.angle < self.stimulation_range[key][1] and self.stimulation_state[key] == 0:
                        self.stimulation_state[key] = 1
                        self.list_channels[self.channel_number[key]-1].set_amplitude(self.intensity[key])
                    elif self.stimulation_range[key][0] > self.angle or self.angle > self.stimulation_range[key][1] and self.stimulation_state[key] == 1:
                        self.stimulation_state[key] = 0
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(0)
                else:
                    if self.stimulation_range[key][0] < self.angle or self.angle < self.stimulation_range[key][1] and self.stimulation_state[key] == 0:
                        self.stimulation_state[key] = 1
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(self.intensity[key])
                    elif self.stimulation_range[key][0] > self.angle or self.angle > self.stimulation_range[key][1] and self.stimulation_state[key] == 1:
                        self.stimulation_state[key] = 0
                        self.list_channels[self.channel_number[key] - 1].set_amplitude(self.intensity[key])

            # # Phase 1 / From 0° to 10°
            # # right biceps and deltoid posterior activated
            # if 0 <= self.angle < 10 and self.stimulation_state["Biceps_r"] + self.stimulation_state["Delt_post_r"] \
            #         + self.stimulation_state["Triceps_l"] + self.stimulation_state["Delt_ant_l"] != 2:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.list_channels[1].set_amplitude(self.biceps_r_intensity)
            #     self.list_channels[3].set_amplitude(self.delt_post_r_intensity)
            #
            #     self.stimulator.start_stimulation(
            #         upd_list_channels=self.list_channels
            #     )
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #     self.stimulation_state["Biceps_r"] = True
            #     self.stimulation_state["Delt_post_r"] = True
            #
            # # Phase 2 / From 10° to 20°
            # # no muscle activated
            # elif 10 <= self.angle < 20 and all(a == 0 for a in self.stimulation_state.values()) is False:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #
            # # Phase 3 / From 20° to 40°
            # # right triceps and deltoid anterior activated
            # elif 30 <= self.angle < 40 and self.stimulation_state["Triceps_r"] + self.stimulation_state[
            #     "Delt_ant_r"] != 2:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.list_channels[0].set_amplitude(self.triceps_r_intensity)
            #     self.list_channels[2].set_amplitude(self.delt_ant_r_intensity)
            #
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #     self.stimulation_state["Triceps_r"] = True
            #     self.stimulation_state["Delt_ant_r"] = True
            #
            # # Phase 4 / From 40° to 180°
            # # right triceps, right deltoid anterior, left biceps and left deltoid posterior activated
            # elif 40 <= self.angle < 200 and self.stimulation_state["Triceps_r"] + self.stimulation_state[
            #     "Delt_ant_r"] \
            #         + self.stimulation_state["Biceps_l"] + self.stimulation_state["Delt_post_l"] != 4:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.list_channels[0].set_amplitude(self.triceps_r_intensity)
            #     self.list_channels[2].set_amplitude(self.delt_ant_r_intensity)
            #     self.list_channels[5].set_amplitude(self.biceps_l_intensity)
            #     self.list_channels[7].set_amplitude(self.delt_post_l_intensity)
            #
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #     self.stimulation_state["Triceps_r"] = True
            #     self.stimulation_state["Delt_ant_r"] = True
            #     self.stimulation_state["Biceps_l"] = True
            #     self.stimulation_state["Delt_post_l"] = True
            #
            # # Phase 5 / From 180° to 190°
            # # left biceps and left deltoid posterior activated
            # elif 180 <= self.angle < 190 and self.stimulation_state["Triceps_r"] + self.stimulation_state[
            #     "Delt_ant_r"] \
            #         + self.stimulation_state["Biceps_l"] + self.stimulation_state["Delt_post_l"] != 2:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.list_channels[5].set_amplitude(self.biceps_l_intensity)
            #     self.list_channels[7].set_amplitude(self.delt_post_l_intensity)
            #
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #     self.stimulation_state["Biceps_l"] = True
            #     self.stimulation_state["Delt_post_l"] = True
            #
            # # Phase 6 / From 190° to 200°
            # # no muscle activated
            # elif 190 <= self.angle < 200 and all(a == 0 for a in self.stimulation_state.values()) is False:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #
            # # Phase 7 / From 200° to 220°
            # # left triceps and left deltoid anterior activated
            # elif 210 <= self.angle < 240 and self.stimulation_state["Triceps_l"] + self.stimulation_state[
            #     "Delt_ant_l"] != 2:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.list_channels[4].set_amplitude(self.triceps_l_intensity)
            #     self.list_channels[6].set_amplitude(self.delt_ant_l_intensity)
            #
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #     self.stimulation_state["Triceps_l"] = True
            #     self.stimulation_state["Delt_ant_l"] = True
            #
            # # Phase 8 / From 220° to 360°
            # # right biceps, right deltoid posterior, left triceps and left deltoid anterior activated
            # elif 220 <= self.angle < 350 and self.stimulation_state["Biceps_r"] + self.stimulation_state[
            #     "Delt_post_r"] \
            #         + self.stimulation_state["Triceps_l"] + self.stimulation_state["Delt_ant_l"] != 4:
            #     for list_chan in self.list_channels:
            #         list_chan.set_amplitude(0)
            #     self.list_channels[1].set_amplitude(self.biceps_r_intensity)
            #     self.list_channels[3].set_amplitude(self.delt_post_r_intensity)
            #     self.list_channels[4].set_amplitude(self.triceps_l_intensity)
            #     self.list_channels[6].set_amplitude(self.delt_ant_l_intensity)
            #
            #     self.stimulator.start_stimulation(upd_list_channels=self.list_channels)
            #     for stim_state in self.stimulation_state:
            #         self.stimulation_state[stim_state] = False
            #     self.stimulation_state["Biceps_r"] = True
            #     self.stimulation_state["Delt_post_r"] = True
            #     self.stimulation_state["Triceps_l"] = True
            #     self.stimulation_state["Delt_ant_l"] = True

            time.sleep(0.001)


if __name__ == "__main__":
    HandCycling2().stimulate()

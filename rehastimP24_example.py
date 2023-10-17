from time import sleep,time
from pyScienceMode2 import Channel as Ch
from sciencemode import sciencemode
from pyScienceMode2.rehastimp24_interface import StimulatorP24 as St

# list which contains the channels you want to use
list_channels = []

# Create an object channel

channel_1 = Ch.Channel(mode="Single", no_channel=1, amplitude=20, pulse_width=100, name="Biceps", device_type="RehastimP24")

list_channels.append(channel_1)

stimulator = St(port="COM4", show_log=True, device_type="RehastimP24")

# next_packet = stimulator.get_next_packet_number()
# print("next packetz number: {}", next_packet)

# stimulator.ll_init()

#
# ret = False
#
# while not sciencemode.smpt_new_packet_received(device):
#     time.sleep(1)
#
# sciencemode.smpt_last_ack(device, ack);
# print("last ack: {}",ack)
# print(f"command number {ack.command_number}, packet_number {ack.packet_number}")
#
# ret = sciencemode.smpt_get_get_extended_version_ack(device, extended_version_ack)
# print("smpt_get_get_extended_version_ack: {}", ret)
# print("fw_hash {} ", extended_version_ack.fw_hash)


# ll_init = sciencemode.ffi.new("Smpt_ll_init*")
# ll_init.high_voltage_level = sciencemode.Smpt_High_Voltage_Default
# ll_init.packet_number = sciencemode.smpt_packet_number_generator_next(device)
# ret = sciencemode.smpt_send_ll_init(device, ll_init)
# print("smpt_send_ll_init: {}", ret)
sleep(1)

# packet_number = sciencemode.smpt_packet_number_generator_next(device)
# print("next packet_number {}", packet_number)
#
# ll_config = sciencemode.ffi.new("Smpt_ll_channel_config*")
#
# ll_config.enable_stimulation = True
# ll_config.channel = sciencemode.Smpt_Channel_Blue
# ll_config.connector = sciencemode.Smpt_Connector_Yellow
# ll_config.number_of_points = 3
# ll_config.points[0].time = 100
# ll_config.points[0].current = 20
# ll_config.points[1].time = 100
# ll_config.points[1].current = 20
# ll_config.points[2].time = 100
# ll_config.points[2].current = -20
#
# for i in range(3):
#     ll_config.packet_number = sciencemode.smpt_packet_number_generator_next(device)
#     ret = sciencemode.smpt_send_ll_channel_config(device, ll_config)
#     print("smpt_send_ll_channel_config: {}", ret)
#     time.sleep(1)
#
# packet_number = sciencemode.smpt_packet_number_generator_next(device)
# ret = sciencemode.smpt_send_ll_stop(device, packet_number)
# print("smpt_send_ll_stop: {}", ret)
# Init the stimulation. Use it before starting the stimulation or after stopping it.

stimulator.init_stimulation(list_channels=list_channels, stimulation_interval=600)

# Add points with the configuration you want to create your shape pulse

stimulator.add_point_configuration(time=100, current=10)
stimulator.add_point_configuration(time=100, current=-10)

stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=100)

sleep(4)
stimulator.stop_stimulation()


# ml_init = sciencemode.ffi.new("Smpt_ml_init*")
# ml_init.packet_number = sciencemode.smpt_packet_number_generator_next(device)
# ret = sciencemode.smpt_send_ml_init(device, ml_init)
# print("smpt_send_ml_init: {}", ret)
# time.sleep(1)

# ml_update = sciencemode.ffi.new("Smpt_ml_update*")
# ml_update.packet_number = sciencemode.smpt_packet_number_generator_next(device)
# for i in range(8):
#     ml_update.enable_channel[i] = True
#     ml_update.channel_config[i].period = 20
#     ml_update.channel_config[i].number_of_points = 3
#     ml_update.channel_config[i].points[0].time = 100
#     ml_update.channel_config[i].points[0].current = 20
#     ml_update.channel_config[i].points[1].time = 100
#     ml_update.channel_config[i].points[1].current = 20
#     ml_update.channel_config[i].points[2].time = 100
#     ml_update.channel_config[i].points[2].current = -20
#
# ret = sciencemode.smpt_send_ml_update(device, ml_update)
# print("smpt_send_ml_update: {}", ret)
#
# ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")
#
# for i in range(10):
#     ml_get_current_data.data_selection = sciencemode.Smpt_Ml_Data_Channels
#     ml_get_current_data.packet_number = sciencemode.smpt_packet_number_generator_next(device)
#     ret = sciencemode.smpt_send_ml_get_current_data(device, ml_get_current_data)
#     print("smpt_send_ml_get_current_data: {}", ret)
#     time.sleep(1)
#
# packet_number = sciencemode.smpt_packet_number_generator_next(device)
# ret = sciencemode.smpt_send_ml_stop(device, packet_number)
# print("smpt_send_ml_stop: {}", ret)
#
# ret = sciencemode.smpt_close_serial_port(device)
# print("smpt_close_serial_port: {}", ret)
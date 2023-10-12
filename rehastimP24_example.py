import time
from pyScienceMode2 import Channel as Ch
from sciencemode import sciencemode
from pyScienceMode2.rehastimp24_interface import StimulatorP24 as St






ack = sciencemode.ffi.new("Smpt_ack*")
device = sciencemode.ffi.new("Smpt_device*")
extended_version_ack = sciencemode.ffi.new("Smpt_get_extended_version_ack*")
#
# def check_serial_port(port):
#     """
#     Vérifie si le port série est accessible et fonctionnel.
#
#     Args:
#     port (str): Le nom du port série à vérifier, par exemple "COM4".
#
#     Returns:
#     bool: True si le port série est accessible, False sinon.
#     """
#     # Convertit la chaîne en bytes pour la compatibilité avec la bibliothèque sciencemode
#     com = sciencemode.ffi.new("char[]", port.encode())
#     ret = sciencemode.smpt_check_serial_port(com)
#     if ret:
#         print(f"Le port {port} est accessible.")
#     else:
#         raise RuntimeError(f"Échec de l'accès au port {port}.")
#
#     return ret
#
# # Exemple d'utilisation
# if __name__ == "__main__":
#     # Remplacez "COM4" par le port série que vous souhaitez vérifier
#     port = "COM4"
#     is_port_accessible = check_serial_port(port)
#
#     if is_port_accessible:
#         print("Le port série est prêt à être utilisé.")
#     else:
#         print("Le port série n'est pas accessible. Veuillez vérifier votre connexion et réessayer.")

com = sciencemode.ffi.new("char[]", b"COM4")



ret = sciencemode.smpt_check_serial_port(com)
print("Port check is {}", ret)

ret = sciencemode.smpt_open_serial_port(device, com)
print("smpt_open_serial_port: {}", ret)

packet_number = sciencemode.smpt_packet_number_generator_next(device)
print("next packet_number {}", packet_number)

ret = sciencemode.smpt_send_get_extended_version(device, packet_number)
print("smpt_send_get_extended_version: {}", ret)

ret = False

while not sciencemode.smpt_new_packet_received(device):
    time.sleep(1)

sciencemode.smpt_last_ack(device, ack);
print(f"command number {ack.command_number}, packet_number {ack.packet_number}")

ret = sciencemode.smpt_get_get_extended_version_ack(device, extended_version_ack)
print("smpt_get_get_extended_version_ack: {}", ret)
print("fw_hash {} ", extended_version_ack.fw_hash)

ll_init = sciencemode.ffi.new("Smpt_ll_init*")
ll_init.high_voltage_level = sciencemode.Smpt_High_Voltage_Default
ll_init.packet_number = sciencemode.smpt_packet_number_generator_next(device)
ret = sciencemode.smpt_send_ll_init(device, ll_init)
print("smpt_send_ll_init: {}", ret)
time.sleep(1)

packet_number = sciencemode.smpt_packet_number_generator_next(device)
print("next packet_number {}", packet_number)

ll_config = sciencemode.ffi.new("Smpt_ll_channel_config*")

ll_config.enable_stimulation = True
ll_config.channel = sciencemode.Smpt_Channel_Blue
ll_config.connector = sciencemode.Smpt_Connector_Yellow
ll_config.number_of_points = 3
ll_config.points[0].time = 100
ll_config.points[0].current = 20
ll_config.points[1].time = 100
ll_config.points[1].current = 20
ll_config.points[2].time = 100
ll_config.points[2].current = -20

for i in range(3):
    ll_config.packet_number = sciencemode.smpt_packet_number_generator_next(device)
    ret = sciencemode.smpt_send_ll_channel_config(device, ll_config)
    print("smpt_send_ll_channel_config: {}", ret)
    time.sleep(1)

packet_number = sciencemode.smpt_packet_number_generator_next(device)
ret = sciencemode.smpt_send_ll_stop(device, packet_number)
print("smpt_send_ll_stop: {}", ret)

ml_init = sciencemode.ffi.new("Smpt_ml_init*")
ml_init.packet_number = sciencemode.smpt_packet_number_generator_next(device)
ret = sciencemode.smpt_send_ml_init(device, ml_init)
print("smpt_send_ml_init: {}", ret)
time.sleep(1)

ml_update = sciencemode.ffi.new("Smpt_ml_update*")
ml_update.packet_number = sciencemode.smpt_packet_number_generator_next(device)
for i in range(8):
    ml_update.enable_channel[i] = True
    ml_update.channel_config[i].period = 20
    ml_update.channel_config[i].number_of_points = 3
    ml_update.channel_config[i].points[0].time = 100
    ml_update.channel_config[i].points[0].current = 20
    ml_update.channel_config[i].points[1].time = 100
    ml_update.channel_config[i].points[1].current = 20
    ml_update.channel_config[i].points[2].time = 100
    ml_update.channel_config[i].points[2].current = -20

ret = sciencemode.smpt_send_ml_update(device, ml_update)
print("smpt_send_ml_update: {}", ret)

ml_get_current_data = sciencemode.ffi.new("Smpt_ml_get_current_data*")

for i in range(10):
    ml_get_current_data.data_selection = sciencemode.Smpt_Ml_Data_Channels
    ml_get_current_data.packet_number = sciencemode.smpt_packet_number_generator_next(device)
    ret = sciencemode.smpt_send_ml_get_current_data(device, ml_get_current_data)
    print("smpt_send_ml_get_current_data: {}", ret)
    time.sleep(1)

packet_number = sciencemode.smpt_packet_number_generator_next(device)
ret = sciencemode.smpt_send_ml_stop(device, packet_number)
print("smpt_send_ml_stop: {}", ret)

ret = sciencemode.smpt_close_serial_port(device)
print("smpt_close_serial_port: {}", ret)
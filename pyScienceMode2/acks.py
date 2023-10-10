from pyScienceMode2.utils import signed_int

# Errors messages


def motomed_error_values(error_code: int):
    if error_code == -1:
        return "Transfer error"
    elif error_code == -2:
        return "Parameter error"
    elif error_code == -3:
        return "Wrong mode error"
    elif error_code == -4:
        return "Motomed connection error"
    elif error_code == -7:
        return "Motomed busy error"
    elif error_code == -8:
        return "Busy error"
    else:
        return f"Unknown error. Error code : {str(error_code)}"


def rehastim_error(error_code: int) -> str:
    """
    Returns the string corresponding to the information contain in the 'StimulationError' packet.
    """
    if error_code == -1:
        return "Emergency switch activated/not connected"
    elif error_code == -2:
        return "Electrode error"
    elif error_code == -3:
        return "Stimulation module error"


def stimulation_error(error_code: int) -> str:
    """
    Returns the string corresponding to the information contain in the 'StimulationError' packet.
    """
    if error_code == -1:
        return "Transfer error"
    elif error_code == -2:
        return "Parameter error"
    elif error_code == -3:
        return "Wrong mode error"
    elif error_code == -8:
        return " Busy error"


# Acks Motomed


def get_motomed_mode_ack(packet: (list, str)) -> str:
    """
    Returns the string corresponding to the information contain in the 'InitPhaseTrainingAck' packet.
    """
    if packet[7] == 0:
        if packet[8] == 0:
            return "Start mode"
        elif packet[8] == 1:
            return "Phase training initialized"
        elif packet[8] == 2:
            return "Phase training started"
        elif packet[8] == 3:
            return "Phase training break"
        elif packet[8] == 4:
            return "Basic training started"
        elif packet[8] == 5:
            return "Basic training pause"
        elif packet[8] == 6:
            return "Motomed busy"
        elif signed_int(packet[8:9]) == -1:
            return "Motomed connection error"
    elif signed_int(packet[7:8]) == -1:
        return "Transfer error"
    elif signed_int(packet[7:8]) == -8:
        return "Busy error"


def init_phase_training_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'InitPhaseTrainingAck' packet.
    """
    if str(packet[7]) == "0":
        return "Phase training initialized"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def start_phase_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Start phase training / change phase sent to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def pause_phase_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Start pause sent to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def stop_phase_training_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Stop phase training sent to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def set_rotation_direction_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Sent rotation direction to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def set_speed_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Sent speed to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def set_gear_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Set Gear to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def start_basic_training_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Sent start basic training to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def pause_basic_training_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Sent basic pause to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def continue_basic_training_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Sent continue basic training to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def stop_basic_training_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartPhaseAck' packet.
    """
    if str(packet[7]) == "0":
        return "Sent stop basic training to MOTOmed"
    else:
        return motomed_error_values(signed_int(packet[7:8]))


def motomed_error_ack(packet):
    if packet == -4:
        return "Motomed connection error"
    elif packet == -6:
        return "Invalid Motomed trainer"


# Acks Stimulators
def get_mode_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'getModeAck' packet.
    """
    if packet[7] == 0:
        if packet[8] == 0:
            return "Start Mode"
        elif packet[8] == 1:
            return "Stimulation initialized"
        elif packet[8] == 2:
            return "Stimulation started"
    else:
        return stimulation_error(signed_int(packet[7:8]))


def init_stimulation_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'InitChannelListModeAck' packet.
    """
    if packet[7] == 0:
        return "Stimulation initialized"
    else:
        return stimulation_error(signed_int(packet[7:8]))


def start_stimulation_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StartChannelListModeAck' packet.
    """
    if packet[7] == 0:
        return "Stimulation started"
    else:
        return stimulation_error(signed_int(packet[7:8]))


def stop_stimulation_ack(packet: bytes) -> str:
    """
    Returns the string corresponding to the information contain in the 'StopChannelListModeAck' packet.
    """
    if packet[7] == 0:
        return "Stimulation stopped"
    else:
        return stimulation_error(signed_int(packet[7:8]))



def signed_int(packet: bytes):
    return int.from_bytes(packet, "big", signed=True)


def check_stimulation_interval(stimulation_interval):
    """
    Checks if the stimulation interval is within limits.
    """
    if stimulation_interval < 8 or stimulation_interval > 1025:
        raise ValueError("Error : Stimulation interval [8,1025]. Stimulation given : %s"
                         % stimulation_interval)


def check_inter_pulse_interval(inter_pulse_interval):
    """
    Checks if the "inter pulse interval" is within limits.
    """
    if inter_pulse_interval < 2 or inter_pulse_interval > 129:
        raise ValueError("Error : Inter pulse interval [2,129], given : %s" % inter_pulse_interval)


def check_low_frequency_factor(low_frequency_factor ):
    """
    Checks if the low frequency factor is within limits.
    """
    if low_frequency_factor < 0 or low_frequency_factor > 7:
        raise ValueError("Error : Low frequency factor [0,7], given : %s" % low_frequency_factor)


def check_unique_channel(list_channels: list) -> bool:
    """
    Checks if there is not 2 times the same channel in the ist given.

    Parameters
    ----------
    list_channels: list[Channel]
        Contains a list of channel.

    Returns
    -------
    True if all channels are unique, False and print a warning if not.
    """
    active_channel = []
    for i in range(len(list_channels)):
        if list_channels[i].get_no_channel() in active_channel:
            print("Warning : 2 channel no%s" % list_channels[i].get_no_channel() +
                  " in list_channels given. The first one given will be used.")
            list_channels.pop(i)
            return False
        else:
            active_channel.append(list_channels[i].get_no_channel())
    return True


def check_list_channel_order(list_channels):
    """
    Checks if the channels in the list_channels given are ordered.
    """
    number_previous_channel = 0
    for i in range(len(list_channels)):
        if list_channels[i].get_no_channel() < number_previous_channel:
            raise RuntimeError("Error: channels in list_channels given are not in order.")
        number_previous_channel = list_channels[i].get_no_channel()


def calc_electrode_number(list_channels: list, enable_low_frequency: bool = False) -> int:
    """
    When enable_low_frequency = False :
    Calculates the number corresponding to which electrode is activated.
    During the initialisation, the computer needs to tell the Rehastim which channel needs to be activated. It is
    done through the addition of 2 pow the number of the channel.
    For example if the channel 1 and 4 needs to be activated, electrode_number = 2**1 + 2**4

    When enable_low_frequency = True :
    Calculates the number corresponding to which electrode has the low_frequency_factor enabled.

    Parameters
    ----------
    list_channels: list[Channel]
        Contains the channels that will be activated.
    enable_low_frequency: bool
        Choose whether the number correspond to active channel (False) or correspond to channel with low frequency
        factor enabled (True).

    Returns
    -------
    electrode_number: int
        Electrode number calculated.
    """
    electrode_number = 0
    for i in range(len(list_channels)):
        if enable_low_frequency:
            if list_channels[i].get_enable_low_frequency():
                electrode_number += 2 ** (list_channels[i].get_no_channel() - 1)
        if not enable_low_frequency:
            electrode_number += 2 ** (list_channels[i].get_no_channel() - 1)
    return electrode_number
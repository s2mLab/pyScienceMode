from enum import Enum


class Rehastim2Commands(Enum):
    Init = 1
    InitAck = 2
    UnknownCommand = 3
    Watchdog = 4
    GetStimulationMode = 10
    GetStimulationModeAck = 11
    InitChannelListMode = 30
    InitChannelListModeAck = 31
    StartChannelListMode = 32
    StartChannelListModeAck = 33
    StopChannelListMode = 34
    StopChannelListModeAck = 35
    SinglePulse = 36
    SinglePulseAck = 37
    StimulationError = 38
    MotomedError = 90
    InitPhaseTraining = 50
    InitPhaseTrainingAck = 51
    StartPhase = 52
    StartPhaseAck = 53
    PausePhase = 54
    PausePhaseAck = 55
    StopPhaseTraining = 56
    StopPhaseTrainingAck = 57
    PhaseResult = 58
    ActualValues = 60
    SetRotationDirection = 70
    SetRotationDirectionAck = 71
    SetSpeed = 72
    SetSpeedAck = 73
    SetGear = 74
    SetGearAck = 75
    SetKeyboardLock = 76
    SetKeyboardLockAck = 77
    StartBasicTraining = 80
    StartBasicTrainingAck = 81
    PauseBasicTraining = 82
    PauseBasicTrainingAck = 83
    ContinueBasicTraining = 84
    ContinueBasicTrainingAck = 85
    StopBasicTraining = 86
    StopBasicTrainingAck = 87
    MotomedCommandDone = 89
    GetMotomedModeAck = 13
    GetMotomedMode = 12


class P24Commands(Enum):
    Smpt_Cmd_Ll_Init = 0
    Smpt_Cmd_Ll_Init_Ack = 1
    Smpt_Cmd_Ll_Channel_Config = 2
    Smpt_Cmd_Ll_Channel_Config_Ack = 3
    Smpt_Cmd_Ll_Stop = 4
    Smpt_Cmd_Ll_Stop_Ack = 5
    Smpt_Cmd_Ll_Emg_Switches = 18
    Smpt_Cmd_Ll_Emg_Switches_Ack = 19
    Smpt_Cmd_Ml_Init = 30
    Smpt_Cmd_Ml_Init_Ack = 31
    Smpt_Cmd_Ml_Update = 32
    Smpt_Cmd_Ml_Update_Ack = 33
    Smpt_Cmd_Ml_Stop = 34
    Smpt_Cmd_Ml_Stop_Ack = 35
    Smpt_Cmd_Ml_Get_Current_Data = 36
    Smpt_Cmd_Ml_Get_Current_Data_Ack = 37
    Smpt_Cmd_Get_Version_Main = 50
    Smpt_Cmd_Get_Version_Main_Ack = 51
    Smpt_Cmd_Get_Device_Id = 52
    Smpt_Cmd_Get_Device_Id_Ack = 53
    Smpt_Cmd_Get_Battery_Status = 54
    Smpt_Cmd_Get_Battery_Status_Ack = 55
    Smpt_Cmd_Set_Power = 56
    Smpt_Cmd_Set_Power_Ack = 57
    Smpt_Cmd_Reset = 58
    Smpt_Cmd_Reset_Ack = 59
    Smpt_Cmd_Get_Version_Stim = 60
    Smpt_Cmd_Get_Version_Stim_Ack = 61
    Smpt_Cmd_Get_Stim_Status = 62
    Smpt_Cmd_Get_Stim_Status_Ack = 63
    Smpt_Cmd_Get_Main_Status = 64
    Smpt_Cmd_Get_Main_Status_Ack = 65
    Smpt_Cmd_General_Error = 66
    Smpt_Cmd_Unknown_Cmd = 67
    Smpt_Cmd_Get_Extended_Version = 68
    Smpt_Cmd_Get_Extended_Version_Ack = 69
    Smpt_Cmd_Dl_Init = 100
    Smpt_Cmd_Dl_Init_Ack = 101
    Smpt_Cmd_Dl_Start = 102
    Smpt_Cmd_Dl_Start_Ack = 103
    Smpt_Cmd_Dl_Stop = 104
    Smpt_Cmd_Dl_Stop_Ack = 105
    Smpt_Cmd_Dl_Send_Live_Data = 106
    Smpt_Cmd_Dl_Send_File = 107
    Smpt_Cmd_Dl_Send_MMI = 108
    Smpt_Cmd_Dl_Get = 109
    Smpt_Cmd_Dl_Get_Ack = 110
    Smpt_Cmd_Dl_Power_Module = 111
    Smpt_Cmd_Dl_Power_Module_Ack = 112
    Smpt_Cmd_Dl_Send_File_Ack = 113
    Smpt_Cmd_Dl_Sys = 114
    Smpt_Cmd_Dl_Sys_Ack = 115
    Smpt_Cmd_Bl_Init = (120,)
    Smpt_Cmd_Bl_Init_Ack = (121,)
    Smpt_Cmd_Bl_Update_Init = (122,)
    Smpt_Cmd_Bl_Update_Init_Ack = (123,)
    Smpt_Cmd_Bl_Update_Block = (124,)
    Smpt_Cmd_Bl_Update_Block_Ack = (125,)
    Smpt_Cmd_Bl_Update_Stop = (126,)
    Smpt_Cmd_Bl_Update_Stop_Ack = (127,)
    Smpt_Cmd_Sl_Test_Memory_Card = (160,)
    Smpt_Cmd_Sl_Test_Memory_Card_Ack = (161,)
    Smpt_Cmd_Sl_Set_Debug = (162,)
    Smpt_Cmd_Sl_Set_Debug_Ack = (163,)
    Smpt_Cmd_Sl_Debug_Message = (164,)
    Smpt_Cmd_Sl_Set_Fuel_Gauge = (166,)
    Smpt_Cmd_Sl_Set_Fuel_Gauge_Ack = (167,)
    Smpt_Cmd_Sl_Set_Bluetooth = (168,)
    Smpt_Cmd_Sl_Set_Bluetooth_Ack = (169,)
    Smpt_Cmd_Sl_Set_Device_Id = (170,)
    Smpt_Cmd_Sl_Set_Device_Id_Ack = (171,)


class Modes(Enum):
    SINGLE = 0
    DOUBLET = 1
    TRIPLET = 2
    NONE = 3


class HighVoltage(Enum):
    Voltage_Default = 0
    Voltage_Off = 1
    High_Voltage_30V = 2
    High_Voltage_60V = 3
    High_Voltage_90V = 4
    High_Voltage_120V = 5
    High_Voltage_150V = 6


class ErrorCode(Enum):
    NoError = (0, None)
    TransferError = (1, "Transfer error.")
    ParameterError = (2, "Parameter error.")
    ProtocolError = (3, "Protocol error.")
    TimeoutError = (5, "Timeout error.")
    CurrentLevelNotInitialized = (
        7,
        "Current level not initialized. Close the current level or initialize it.\n"
        "Can be solved by disconnecting and reconnecting the device.",
    )
    ElectrodeError = (10, "Electrode error.")
    InvalidCommandError = (11, "Invalid command error.")

    def __new__(cls, value, message):
        member = object.__new__(cls)
        member._value_ = value
        member.message = message
        return member


class StimStatus(Enum):
    Uninitialized = 0
    Low_Level_Initialized = 1
    Mid_Level_Initialized = 2
    Mid_Level_Running = 3


class Device(Enum):
    Rehastim2 = "Rehastim2"
    P24 = "P24"

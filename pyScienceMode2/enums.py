from enum import Enum


class Type(Enum):
    """
    Enumeration representing message types and commands.

    This enumeration defines constants for various message types and commands used in communication.

    """
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

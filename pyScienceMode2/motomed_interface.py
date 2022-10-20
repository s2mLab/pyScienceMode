"""
Motomed Interface class used to control and get data from Motomed while connected to the rehamove2.
See ScienceMode2 - Description and protocol for more information.
"""

from pyScienceMode2.acks import *
from pyScienceMode2.utils import *
from pyScienceMode2.sciencemode import RehastimGeneric
import numpy as np


class Motomed(RehastimGeneric):
    """
    Class to control the motomed
    """

    def __init__(self, port: str, show_log: bool = False):
        """
        Parameters
        ----------
        port: str
            Port to which the motomed is connected.
        show_log: bool
            If True, print the log of the communication.
        """
        self.port = port
        self.speed = 0
        self.gear = 0
        self.body_training = 1
        self.direction = 0
        self.active = 0
        self.passive_speed = 0  # tr/min
        self.is_phase_initialize = False
        self.training_side = 0
        self.crank_orientation = 0
        self.fly_wheel = 0
        self.phase_variant = 0
        self.spasm_detection = 0
        self.last_phase_result = 0
        self.is_phase_training = False

        super().__init__(port, show_log, True)
        # Connect to rehastim
        packet = None
        while packet is None:
            packet = self._get_last_ack(init=True)
        self._send_generic_packet("InitAck", packet=self._init_ack(packet[5]), packet_number=packet[5])

    def _send_packet(self, cmd: str) -> (None, str):
        """
        Calls the methode that construct the packet according to the command.

        Parameters
        ----------
        cmd: str
            Command that will be sent.

        Returns
        -------
            In the case of an InitAck, return the string 'InitAck'. None otherwise.
        """
        self.event.wait()  # If the event is set, motomed last command is done next command can be sent
        if cmd == "InitPhaseTraining":
            packet = self._packet_construction(self.packet_count, "InitPhaseTraining", [self.body_training])
        elif cmd == "StartPhase":
            data_command = [
                self.phase_variant,
                self.passive_speed,
                self.gear,
                self.direction,
                self.fly_wheel,
                self.spasm_detection,
                self.training_side,
                self.crank_orientation,
            ]
            packet = self._packet_construction(self.packet_count, "StartPhase", data_command)
        elif cmd == "SetRotationDirection":
            packet = self._packet_construction(self.packet_count, "SetRotationDirection", [self.direction])
        elif cmd == "SetSpeed":
            packet = self._packet_construction(self.packet_count, "SetSpeed", [self.passive_speed])
        elif cmd == "SetGear":
            packet = self._packet_construction(self.packet_count, "SetGear", [self.gear])
        elif cmd == "StartBasicTraining":
            packet = self._packet_construction(self.packet_count, "StartBasicTraining", [self.body_training])
        else:
            packet = self._packet_construction(self.packet_count, cmd)
        init_ack = self._send_generic_packet(cmd, packet)
        if init_ack:
            return init_ack

    def get_motomed_mode(self) -> str:
        """
        Get the mode of the motomed.

        Returns
        -------
        mode: str
        """
        self._send_packet("GetMotomedMode")
        get_mot_mode_ack = self._calling_ack(self._get_last_ack())
        if get_mot_mode_ack in ["Transfer error", "Busy error", "Motomed busy", "Motomed connection error"]:
            raise RuntimeError("Error getting motomed mode : " + str(get_mot_mode_ack))
        else:
            return get_mot_mode_ack

    def init_phase_training(self, arm_training: bool = True):
        """
        Initialize the phase training.

        Parameters
        ----------
        arm_training: bool
            If True, the training is for the arm. If False, the training is for the leg.
        """
        self.body_training = 1 if arm_training else 0
        self._send_packet("InitPhaseTraining")
        init_phase_ack = self._calling_ack(self._get_last_ack())
        if init_phase_ack != "Phase training initialized":
            raise RuntimeError("Error initializing phase : " + str(init_phase_ack))
        self.is_phase_initialize = True

    def start_phase(
        self,
        go_forward: bool = True,
        active: bool = False,
        symmetry_training: bool = False,
        motomedmax_game: bool = False,
        gear: int = 0,
        speed: int = 0,
        fly_wheel: int = 0,
        spasm_detection: bool = False,
        direction_restoration: bool = False,
        training_side: str = "both",
        crank_symetric: bool = False,
    ):
        """
        Start the phase training.

        Parameters
        ----------
        go_forward: bool
            If True, the phase will be done in the forward direction.
             If False, the phase will be done in the backward direction.
        active: bool
            If True, the phase will be done in active mode.
        symmetry_training: bool
            If True, the phase will be done in symmetry training mode.
        motomedmax_game: bool
            If True, the phase will be done in motomedmax game mode.
        gear: int
            Gear of the motomed.
        speed: int
            Speed of the motomed.
        fly_wheel: int
            Fly wheel of the motomed.
        spasm_detection: bool
            If True, the phase will be done with spasm detection.
        direction_restoration: bool
            If True, the phase will be done with direction restoration after spasm.
        training_side: str
            Side of the training. Can be "left", "right" or "both".
        crank_symetric: bool
            If True, the phase will be done with a symetric crank.
        """
        if active + symmetry_training + motomedmax_game != 1:
            raise RuntimeError("Please chose one option between 'active' 'symmetry_training' and 'Motomedmax_game'.")
        if active:
            self.phase_variant = 0
        elif not active and not symmetry_training and not motomedmax_game:
            self.phase_variant = 1
        elif symmetry_training:
            self.phase_variant = 2
        elif motomedmax_game:
            self.phase_variant = 3

        if not self.is_phase_initialize:
            raise RuntimeError("Phase not initialized.")

        self.direction = 1 if go_forward else 0
        if gear > 20 or gear < 0:
            raise RuntimeError("Gear must be in [0, 20].")
        else:
            self.gear = gear

        if speed > 90 or speed < 0:
            raise RuntimeError("Speed must be in [0, 90].")
        else:
            self.passive_speed = speed

        if fly_wheel > 100 or fly_wheel < 0:
            raise RuntimeError("fly_wheel must be in [0, 100].")
        else:
            self.fly_wheel = fly_wheel
        if not spasm_detection:
            self.spasm_detection = 0
            if direction_restoration:
                raise RuntimeError("You can use direction restoration only if spasm detection is active.")
        else:
            if direction_restoration:
                self.spasm_detection = 2
            else:
                self.spasm_detection = 1
        if training_side == "both":
            self.training_side = 0
        elif training_side == "left":
            self.training_side = 1
        elif training_side == "right":
            self.training_side = 2
        else:
            raise RuntimeError("Training side must be 'both', 'right' or 'left'." f"You have : {training_side}.")
        self.crank_orientation = 1 if crank_symetric else 0
        self._send_packet("StartPhase")
        start_phase_train_ack = self._calling_ack(self._get_last_ack())
        if start_phase_train_ack != "Start phase training / change phase sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_phase_train_ack))

    def _pause_phase_training(self):
        """
        Pause the phase training.
        """
        self._send_packet("PausePhase")
        ack = self._calling_ack(self._get_last_ack())
        if ack != "Start pause sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(ack))

    def _stop_phase_training(self):
        """
        Stop the phase training.
        """
        self._send_packet("StopPhaseTraining")
        stop_phase_ack = self._calling_ack(self._get_last_ack())
        if stop_phase_ack == "PhaseResult":
            print("Result of the phase available.")
        elif stop_phase_ack != "Stop phase training sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(stop_phase_ack))

    def _continue_phase_training(self):
        """
        Continue the phase training.
        """
        self._send_packet("ContinuePhaseTraining")
        continue_phase_ack = self._calling_ack(self._get_last_ack())
        if continue_phase_ack != "Stop phase training sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(continue_phase_ack))

    def stop_training(self):
        """
        Stop the training.
        """
        self._stop_phase_training() if self.is_phase_training else self._stop_basic_training()

    def pause_training(self):
        """
        Pause the training.
        """
        self._pause_phase_training() if self.is_phase_training else self._pause_basic_training()

    def continue_training(self):
        """
        Continue the training.
        """
        self._continue_phase_training() if self.is_phase_training else self._continue_basic_training()

    def start_basic_training(self, arm_training: bool = True):
        """
        Start the basic training.

        Parameters
        ----------
        arm_training: bool
            If True, the training will be done with the arm.
        """
        self.body_training = 1 if arm_training else 0
        self._send_packet("StartBasicTraining")
        start_basic_ack = self._calling_ack(self._get_last_ack())
        if start_basic_ack != "Sent start basic training to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_basic_ack))

    def _stop_basic_training(self):
        """
        Stop the basic training.
        """
        self._send_packet("StopBasicTraining")
        stop_basic_ack = self._calling_ack(self._get_last_ack())
        if stop_basic_ack != "Sent stop basic training to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(stop_basic_ack))

    def _pause_basic_training(self):
        """
        Pause the basic training.
        """
        self._send_packet("PauseBasicTraining")
        pause_basic_ack = self._calling_ack(self._get_last_ack())
        if pause_basic_ack != "Sent basic pause to MOTOmed":
            raise RuntimeError("Error pause phase : " + str(pause_basic_ack))

    def _continue_basic_training(self):
        """
        Continue the basic training.
        """
        self._send_packet("ContinueBasicTraining")
        start_basic_ack = self._calling_ack(self._get_last_ack())
        if start_basic_ack != "Sent continue basic training to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_basic_ack))

    def set_direction(self, go_forward: bool = True):
        """
        Set the direction of the training.
        """
        self.direction = 1 if go_forward else 0
        self._send_packet("SetRotationDirection")
        rotation_ack = self._calling_ack(self._get_last_ack())
        if rotation_ack != "Sent rotation direction to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(rotation_ack))

    def set_speed(self, passive_speed: int):
        """
        Set the speed of the training.
        """
        self.passive_speed = passive_speed
        self._send_packet("SetSpeed")
        speed_ack = self._calling_ack(self._get_last_ack())
        if speed_ack != "Sent speed to MOTOmed":
            raise RuntimeError("Error sending speed : " + str(speed_ack))

    def set_gear(self, gear: int):
        """
        Set the gear of the training.
        """
        self.gear = gear
        self._send_packet("SetGear")
        gear_ack = self._calling_ack(self._get_last_ack())
        if gear_ack != "Set Gear to MOTOmed":
            raise RuntimeError("Error sending gear : " + str(gear_ack))

    def _calling_ack(self, packet: bytes) -> str:
        """
        Check for motomed response and return it.

        Parameters
        ----------
        packet: bytes
            Packet which needs to be processed.

        Returns
        -------
            A string which is the message corresponding to the processing of the packet.
        """
        self.event_ack.wait()
        if packet == "InitAck" or packet[6] == 1:
            return "InitAck"
        elif packet[6] == self.Type["GetMotomedModeAck"].value:
            return get_motomed_mode_ack(packet)
        elif packet[6] == self.Type["InitPhaseTrainingAck"].value:
            return init_phase_training_ack(packet)
        elif packet[6] == self.Type["StartPhaseAck"].value:
            return start_phase_ack(packet)
        elif packet[6] == self.Type["PausePhaseAck"].value:
            return pause_phase_ack(packet)
        elif packet[6] == self.Type["StopPhaseTrainingAck"].value:
            return stop_phase_training_ack(packet)
        elif packet[6] == self.Type["SetRotationDirectionAck"].value:
            return set_rotation_direction_ack(packet)
        elif packet[6] == self.Type["SetSpeedAck"].value:
            return set_speed_ack(packet)
        elif packet[6] == self.Type["SetGearAck"].value:
            return set_gear_ack(packet)
        elif packet[6] == self.Type["StartBasicTrainingAck"].value:
            return start_basic_training_ack(packet)
        elif packet[6] == self.Type["PauseBasicTrainingAck"].value:
            return pause_basic_training_ack(packet)
        elif packet[6] == self.Type["ContinueBasicTrainingAck"].value:
            return continue_basic_training_ack(packet)
        elif packet[6] == self.Type["StopBasicTrainingAck"].value:
            return stop_basic_training_ack(packet)
        elif packet[6] == self.Type["PhaseResult"].value:
            return self._phase_result_ack(packet)
        elif packet[6] == self.Type["MotomedCommandDone"].value:
            return stop_basic_training_ack(packet)
        elif packet[6] == self.Type["MotomedError"].value:
            return motomed_error_values(signed_int(packet[7:8]))
        else:
            raise RuntimeError("Error packet : not understood")

    def _phase_result_ack(self, packet: bytes) -> str:
        """
        Process the phase result packet.

        Parameters
        ----------
        packet: bytes
            Packet which needs to be processed.

        Returns
        -------
            A string which is the message corresponding to the processing of the packet.
        """
        msb_passive_distance = int(packet[8])
        lsb_passive_distance = int(packet[9])
        msb_active_distance = int(packet[10])
        lsb_active_distance = int(packet[11])
        average_power = int(packet[12])
        maximum_power = int(packet[13])
        msb_phase_duration = int(packet[14])
        lsb_phase_duration = int(packet[15])
        msb_active_phase_duration = int(packet[16])
        lsb_active_phase_duration = int(packet[17])
        msb_phase_work = int(packet[18])
        lsb_phase_work = int(packet[19])
        success_value = int(packet[20])
        symmetry = int(packet[21])
        average_muscle_tone = int(packet[22])

        passive_distance = msb_passive_distance * 255 + lsb_passive_distance
        active_distance = None
        phase_duration = None
        active_phase_duration = None
        phase_work = None
        last_phase_result = np.array(
            [
                passive_distance,
                active_distance,
                average_power,
                maximum_power,
                phase_duration,
                active_phase_duration,
                phase_work,
                success_value,
                symmetry,
                average_muscle_tone,
            ]
        )[:, np.newaxis]

        if self.last_phase_result is None:
            self.last_phase_result = last_phase_result
        elif self.last_phase_result.shape[1] < self.max_phase_result:
            self.last_phase_result = np.append(self.last_phase_result, last_phase_result, axis=1)
        else:
            self.last_phase_result = np.append(self.last_phase_result[:, 1:], last_phase_result, axis=1)
        return "PhaseResult"

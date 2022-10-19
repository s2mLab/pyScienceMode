# Stimulator class
import time
from pyScienceMode2.acks import *
from pyScienceMode2.utils import *
from pyScienceMode2.sciencemode import RehastimGeneric

# Notes :
# This code needs to be used in parallel with the "ScienceMode2 - Description and protocol" document


class Motomed(RehastimGeneric):
    def __init__(self, port):
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

        super().__init__(port, True)
        # Connect to rehastim
        packet = None
        while packet is None:
            packet = self.last_init_ack
        self._send_generic_packet("InitAck", packet=[], packet_number=packet[5])

    def _send_packet(self, cmd: str) -> str:
        """
        Calls the methode that construct the packet according to the command.

        Parameters
        ----------
        cmd: str
            Command that will be sent.
        packet_number: int
            Correspond to self.packet_count.

        Returns
        -------
        In the case of an InitAck, return the string 'InitAck'.
        """
        # while not self._motomed_command_done:
        #     pass
        if self.event:
            packet = [-1]
            if cmd == "GetMotomedMode":
                packet = self._packet_get_motomed_mode()
            elif cmd == "InitPhaseTraining":
                packet = self._packet_init_phase_training()
            elif cmd == "StartPhase":
                packet = self._packet_start_phase()
            elif cmd == "PausePhase":
                packet = self._packet_pause_phase()
            elif cmd == "StopPhaseTraining":
                packet = self._packet_stop_phase_training()
            elif cmd == "SetRotationDirection":
                packet = self._packet_set_rotation_direction()
            elif cmd == "SetSpeed":
                packet = self._packet_set_speed()
            elif cmd == "SetGear":
                packet = self._packet_set_gear()
            elif cmd == "StartBasicTraining":
                packet = self._packet_start_basic_training()
            elif cmd == "StopBasicTraining":
                packet = self._packet_stop_basic_training()
            elif cmd == "PauseBasicTraining":
                packet = self._packet_pause_basic_training()
            elif cmd == "ContinueBasicTraining":
                packet = self._packet_continue_basic_training()
            init_ack = self._send_generic_packet(cmd, packet)
            if init_ack:
                return init_ack

    def _packet_get_motomed_mode(self):
        packet = self._packet_construction(self.packet_count, "GetMotomedMode")
        return packet

    def _packet_init_phase_training(self):
        packet = self._packet_construction(self.packet_count, "InitPhaseTraining", [self.body_training])
        return packet

    def _packet_start_phase(self):
        packet = self._packet_construction(
            self.packet_count,
            "StartPhase",
            [
                self.phase_variant,
                self.passive_speed,
                self.gear,
                self.direction,
                self.fly_wheel,
                self.spasm_detection,
                self.training_side,
                self.crank_orientation,
            ],
        )
        return packet

    def _packet_pause_phase(self):
        packet = self._packet_construction(self.packet_count, "PausePhase")
        return packet

    def _packet_stop_phase_training(self):
        packet = self._packet_construction(self.packet_count, "StopPhaseTraining")
        return packet

    def _packet_set_rotation_direction(self):
        packet = self._packet_construction(self.packet_count, "SetRotationDirection", [self.direction])
        return packet

    def _packet_set_speed(self):
        packet = self._packet_construction(self.packet_count, "SetSpeed", [self.passive_speed])
        return packet

    def _packet_set_gear(self):
        packet = self._packet_construction(self.packet_count, "SetGear", [self.gear])
        return packet

    def _packet_start_basic_training(self):
        packet = self._packet_construction(self.packet_count, "StartBasicTraining", [self.body_training])
        return packet

    def _packet_stop_basic_training(self):
        packet = self._packet_construction(self.packet_count, "StopBasicTraining")
        return packet

    def _packet_continue_basic_training(self):
        packet = self._packet_construction(self.packet_count, "ContinueBasicTraining")
        return packet

    def _packet_pause_basic_training(self):
        packet = self._packet_construction(self.packet_count, "PauseBasicTraining")
        return packet

    def get_motomed_mode(self):
        self._send_packet("GetMotomedMode")
        get_motomed_mode_ack = self._calling_ack(self._get_last_ack())
        if get_motomed_mode_ack in ["Transfer error", "Busy error", "Motomed busy", "Motomed connection error"]:
            raise RuntimeError("Error getting motomed mode : " + str(get_motomed_mode_ack))
        else:
            return get_motomed_mode_ack

    def init_phase_training(self, arm_training: bool = True):
        self.body_training = 1 if arm_training else 0
        self._send_packet("InitPhaseTraining")
        init_phase_training_ack = self._calling_ack(self._get_last_ack())
        if init_phase_training_ack != "Phase training initialized":
            raise RuntimeError("Error initializing phase : " + str(init_phase_training_ack))
        self.is_phase_initialize = True

    def start_phase(
        self,
        arm_training: bool = True,
        go_forward: bool = True,
        active: bool = False,
        passive: bool = False,
        symmetry_training: bool = False,
        motomedmax_game: bool = False,
        gear: int = 0,
        speed: int = 0,
        fly_wheel: int = 0,
        spasm_detection: bool = False,
        direction_restoration: bool = False,
        training_side: str = "both",
        crank_equal_orientation: bool = True,
    ):

        if active + symmetry_training + motomedmax_game + passive != 1:
            raise RuntimeError(
                "Please chose one option between 'active', 'passive'," " 'symmetry_training' and 'Motomedmax_game'."
            )
        if active:
            self.phase_variant = 0
        elif passive:
            self.phase_variant = 1
        elif symmetry_training:
            self.phase_variant = 2
        elif motomedmax_game:
            self.phase_variant = 3

        if not self.is_phase_initialize:
            raise RuntimeError("Phase not initialized.")
        self.body_training = 1 if arm_training else 0

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
        self.crank_orientation = 1 if crank_equal_orientation else 0
        self._send_packet("StartPhase")
        start_phase_ack = self._calling_ack(self._get_last_ack())
        # if start_phase_ack != 'Start phase training / change phase sent to MOTOmed':
        #     raise RuntimeError("Error starting phase : " + str(start_phase_ack))

    def _pause_phase_training(self):
        self._send_packet("PausePhase")
        pause_phase_ack = self._calling_ack(self._get_last_ack())
        if pause_phase_ack != "Start pause sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(pause_phase_ack))

    def _stop_phase_training(self):
        self._send_packet("StopPhaseTraining")
        start_phase_ack = self._calling_ack(self._get_last_ack())
        if start_phase_ack != "Stop phase training sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_phase_ack))

    def _continue_phase_training(self):
        self._send_packet("ContinuePhaseTraining")
        start_phase_ack = self._calling_ack(self._get_last_ack())
        if start_phase_ack != "Stop phase training sent to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_phase_ack))

    def stop_training(self):
        if self.is_phase_training:
            self._stop_phase_training()
            # self.phase_result = self._get_phase_result()
        else:
            self._stop_basic_training()

    def pause_training(self):
        if self.is_phase_training:
            self._pause_phase_training()
        else:
            self._pause_basic_training()

    def continue_training(self):
        if self.is_phase_training:
            self._continue_phase_training()
        else:
            self._continue_basic_training()

    def start_basic_training(self, arm_training: bool = True):
        self.body_training = 1 if arm_training else 0
        self._send_packet("StartBasicTraining")
        start_basic_training_ack = self._calling_ack(self._get_last_ack())
        if start_basic_training_ack != "Sent start basic training to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_basic_training_ack))

    def _stop_basic_training(self):
        self._send_packet("StopBasicTraining")
        stop_basic_training_ack = self._calling_ack(self._get_last_ack())
        if stop_basic_training_ack != "Sent stop basic training to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(stop_basic_training_ack))

    def _pause_basic_training(self):
        self._send_packet("PauseBasicTraining")
        pause_basic_training_ack = self._calling_ack(self._get_last_ack())
        if pause_basic_training_ack != "Sent basic pause to MOTOmed":
            raise RuntimeError("Error pause phase : " + str(pause_basic_training_ack))

    def _continue_basic_training(self):
        self._send_packet("ContinueBasicTraining")
        start_basic_training_ack = self._calling_ack(self._get_last_ack())
        if start_basic_training_ack != "Sent continue basic training to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(start_basic_training_ack))

    def set_direction(self, go_forward: bool = True):
        self.direction = 1 if go_forward else 0
        self._send_packet("SetRotationDirection")
        rotation_ack = self._calling_ack(self._get_last_ack())
        if rotation_ack != "Sent rotation direction to MOTOmed":
            raise RuntimeError("Error starting phase : " + str(rotation_ack))

    def set_speed(self, passive_speed: int):
        self.passive_speed = passive_speed
        self._send_packet("SetSpeed")
        speed_ack = self._calling_ack(self._get_last_ack())
        if speed_ack != "Sent speed to MOTOmed":
            raise RuntimeError("Error sending speed : " + str(speed_ack))

    def set_gear(self, gear: int):
        self.gear = gear
        self._send_packet("SetGear")
        gear_ack = self._calling_ack(self._get_last_ack())
        if gear_ack != "Set Gear to MOTOmed":
            raise RuntimeError("Error sending gear : " + str(gear_ack))

    def _calling_ack(self, packet: list):
        """
        Collects the packet waiting in the port if no packet is given.
        Processes the packet given or collected.

        _check_multiple_packet_rec() must be called after the call of _calling_ack.
        After calling _calling_ack() must print(Fore.WHITE) because some error messages are written in red and the print
        function needs to be reset to WHITE after a print in another coloured occurred.

        Parameters
        ----------
        packet: list[int]
            Packet which needs to be processed.

        Returns
        -------
        A string which is the message corresponding to the processing of the packet.
        """
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
        elif packet[6] == self.Type["MotomedCommandDone"].value:
            return stop_basic_training_ack(packet)
        elif packet[6] == self.Type["MotomedError"].value:
            return motomed_error_values(signed_int(packet[7:8]))
        else:
            raise RuntimeError("Error packet : not understood")

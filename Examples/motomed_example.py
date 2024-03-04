import time
import logging
import logging.config

from pyScienceMode.devices.rehastim2 import Rehastim2


def setup_logger():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "output": {"format": "%(asctime)s - %(name)s.%(levelname)s:\t%(message)s"},
        },
        "datefmt": "%Y-%m-%d %H:%M:%S",
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "output", "stream": "ext://sys.stdout"}
        },
        "loggers": {
            "pyScienceMode": {"handlers": ["console"], "level": logging.DEBUG},
        },
    }
    logging.config.dictConfig(logging_config)


setup_logger()
logger = logging.getLogger("pyScienceMode")


port = "/dev/ttyUSB0"  # Enter the port on which the stimulator is connected

motomed = Rehastim2(port, show_log=True, with_motomed=True).motomed
motomed.init_phase_training(arm_training=True)
logger.info(motomed.get_motomed_mode())
motomed.start_phase(speed=50, gear=5, active=False, go_forward=False, spasm_detection=True)
time.sleep(2)
motomed.set_gear(10)
time.sleep(200)
motomed.stop_training()
logger.info(motomed.get_phase_result())

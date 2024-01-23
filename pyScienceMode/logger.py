import logging
import logging.config

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "output": {"format": "%(asctime)s - %(name)s.%(levelname)s:\t%(message)s"},
    },
    "datefmt": "%Y-%m-%d %H:%M:%S",
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "output", "stream": "ext://sys.stdout"}},
    "loggers": {
        "pyScienceMode": {"handlers": ["console"], "level": logging.DEBUG},
    },
}
logging.config.dictConfig(logging_config)

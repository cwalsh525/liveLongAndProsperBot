import logging

import config.default as default

# class Logging:

def create_logger(log_name, logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(default.base_path + '/log/{log_name}.log'.format(log_name=log_name))
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    if not logger.hasHandlers():
        logger.addHandler(fh)
    return logger

# utility function to use to avoid writing out two lines
def log_it_info(logger, msg):
    logger.info(msg)
    print(msg)

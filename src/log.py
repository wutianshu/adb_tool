#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import re
import config
import logging
from src.utils import Utils
from logging.handlers import RotatingFileHandler


class StdoutDirector:

    @staticmethod
    def write(msg):
        if config.log_text is not None:
            config.log_text.insert('end', msg)

    def flush(self):
        pass


logger = logging.getLogger('AdbTool')
logger.setLevel(logging.DEBUG)
FORMAT = '[%(asctime)s] %(levelname)s %(module)s:%(message)s'
formatter = logging.Formatter(FORMAT)
# 控制台日志输出
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)
# 本地日志存储
dire = os.path.join(config.root_path, 'logs')
Utils.creat_folder(dire)
log_file = os.path.join(dire, "AdbTool.log")
log_file_handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=10, encoding='utf8')
log_file_handler.suffix = "%Y-%m-%d_%H-%M-%S.log"
log_file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.log$")
log_file_handler.setFormatter(formatter)
log_file_handler.setLevel(logging.DEBUG)
# GUI日志输出
FORMAT = '[%(asctime)s] %(message)s'
gui_formatter = logging.Formatter(FORMAT)
sys.stdout = StdoutDirector()
gui_logger = logging.getLogger()
gui_handler = logging.StreamHandler(stream=sys.stdout)
gui_handler.setFormatter(gui_formatter)
gui_handler.setLevel(logging.INFO)

logger.addHandler(stream_handler)
logger.addHandler(log_file_handler)

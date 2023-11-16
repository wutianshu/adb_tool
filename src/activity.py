#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import csv
import time
import config
import random
import threading
import traceback
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class DeviceMonitor:
    def __init__(self, device, package, temp_data, interval=5.0, timeout=60):
        self.device = AdbUtils(device)
        self.package = package
        self.temp_data = temp_data
        self.interval = interval
        self.timeout = timeout
        self.main_activity = config.main_activity
        self.activity_list = config.activity_list
        self.black_activity_list = config.black_activity_list
        self.key = config.black_list_key
        self.stop_event = threading.Event()
        self.current_activity = None
        self.activity_monitor_thread = None

    def _activity_monitor(self):
        """
        activity测试方法，统计启动activity的各项时间
        检测到非测试activity时自动启动测试activity进行测试
        检测到activity黑名单后自动跳出
        :return:
        """
        e_time = time.time() + self.timeout
        activity_title = ("datetime", "current_activity", "this_time", "total_time", "wait_time")
        self.activity_file = os.path.join(self.temp_data.result_path, 'activity.csv')
        try:
            with open(self.activity_file, 'a+') as af:
                csv.writer(af, lineterminator='\n').writerow(activity_title)
        except Exception as e:
            logger.error("file not found: " + str(self.activity_file) + str(e))

        while not self.stop_event.is_set() and time.time() < e_time:
            try:
                before = time.time()
                self.current_activity = self.device.adb.get_top_activity()
                if self.current_activity:
                    activity_tuple = (Utils.get_current_time(), self.current_activity, 0, 0, 0)
                    try:
                        with open(self.activity_file, 'a+', encoding="utf-8") as writer:
                            writer_p = csv.writer(writer, lineterminator='\n')
                            writer_p.writerow(activity_tuple)
                    except RuntimeError as e:
                        logger.error(e)
                    logger.debug("current activity: " + self.current_activity)
                    if self.main_activity and self.activity_list:
                        if self.current_activity not in self.activity_list:
                            main_activity = self.main_activity[random.randint(0, len(self.main_activity) - 1)]

                            ret_dict = self.device.adb.start_command_activity(main_activity)
                            # 多数页面不支持，后续使用打洞命令来启动
                            # start_activity = self.package + "/" + main_activity
                            # logger.debug("start_activity:" + start_activity)
                            # ret_dict = self.device.adb.start_activity(start_activity)

                            this_time = ret_dict.get('ThisTime', 0)
                            total_time = ret_dict.get('TotalTime', 0)
                            wait_time = ret_dict.get('WaitTime', 0)
                            activity_tuple = (
                                Utils.get_current_time(), main_activity, this_time, total_time, wait_time)
                            try:
                                with open(self.activity_file, 'a+', encoding="utf-8") as writer:
                                    writer_p = csv.writer(writer, lineterminator='\n')
                                    writer_p.writerow(activity_tuple)
                            except RuntimeError as e:
                                logger.error(e)
                    if self.current_activity in self.black_activity_list:
                        self.device.adb.run_adb_shell_cmd('input keyevent %s' % self.key)

                time_consume = time.time() - before
                delta_inter = self.interval - time_consume
                logger.debug("get app activity time consumed: " + str(time_consume))
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                s = traceback.format_exc()
                logger.debug(e)
                logger.debug(s)

    def _activity_jump_monitor(self):
        activity_title = ("datetime", "current_activity", "this_time", "total_time", "wait_time")
        self.activity_file = os.path.join(self.temp_data.result_path, 'activity.csv')
        try:
            with open(self.activity_file, 'a+') as af:
                csv.writer(af, lineterminator='\n').writerow(activity_title)
        except Exception as e:
            logger.error("file not found: " + str(self.activity_file) + str(e))

        while not self.stop_event.is_set():
            current_activity = None
            this_time = total_time = wait_time = 0
            try:
                before = time.time()
                if self.activity_list:
                    command = self.activity_list[random.randint(0, len(self.activity_list) - 1)]
                    ret_dict = self.device.adb.start_command_activity(command)
                    current_activity = ret_dict.get('Activity')
                    this_time = ret_dict.get('ThisTime', 0)
                    total_time = ret_dict.get('TotalTime', 0)
                    wait_time = ret_dict.get('WaitTime', 0)
                if current_activity:
                    activity_tuple = (Utils.get_current_time(), current_activity, this_time, total_time, wait_time)
                    try:
                        with open(self.activity_file, 'a+', encoding="utf-8") as writer:
                            writer_p = csv.writer(writer, lineterminator='\n')
                            writer_p.writerow(activity_tuple)
                    except RuntimeError as e:
                        logger.error(e)
                    time_consume = time.time() - before
                    delta_inter = self.interval - time_consume
                    logger.debug("get app activity time consumed: " + str(time_consume))
                    if delta_inter > 0:
                        time.sleep(delta_inter)
                else:
                    logger.error('activity open error')
            except Exception as e:
                s = traceback.format_exc()
                logger.debug(e)
                logger.debug(s)

    def start(self):
        """
        启动activity监控
        :return:
        """
        self.activity_monitor_thread = threading.Thread(target=self._activity_monitor)
        # self.activity_monitor_thread = threading.Thread(target=self._activity_jump_monitor)
        self.activity_monitor_thread.start()
        logger.debug("DeviceMonitor activity monitor has started...")

    def stop(self):
        """
        停止activity监控
        :return:
        """
        if self.activity_monitor_thread.isAlive():
            self.stop_event.set()
            self.activity_monitor_thread.join(timeout=1)
            self.activity_monitor_thread = None
        logger.debug("DeviceMonitor stopped!")

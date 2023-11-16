#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import csv
import time
import threading
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class CpuCollector:
    def __init__(self, device, package, temp_data, interval=5, timeout=60):
        self.device = AdbUtils(device)
        self.package = package
        self.temp_data = temp_data
        self._interval = interval
        self._timeout = timeout
        self._stop_event = threading.Event()
        self.collect_cpu_thread = None
        self.sdk_version = self.device.adb.get_sdk_version()
        self._top_cmd = self._get_top_cmd()

    def _get_top_cmd(self):
        top_cmd = 'top -b -n 1 -d %d' % self._interval
        ret = self.device.adb.run_adb_shell_cmd(top_cmd)
        if ret and 'invalid argument "-b"' in ret.lower():
            logger.debug("top -b not support")
            top_cmd = 'top -n 1 -d %d' % self._interval
        return top_cmd

    @staticmethod
    def get_col_index(top_info, names):
        """
        根据列名获取列的序号
        :param top_info:
        :param names:
        :return:
        """
        line_list = top_info.split("\n")
        for line in line_list:
            line = line.strip()
            for col_name in names:
                if col_name in line:
                    key_list = re.split(r"\[%|\s+", line)
                    for num, item in enumerate(key_list):
                        if item == col_name:
                            return num

    def _parse_package(self, package, top_info):
        """
        通过top命令获取测试包的cpu信息
        :return:
        """
        datetime = Utils.get_current_time()
        package_dict = {'datetime': datetime, 'package': package, 'pid': '', 'pid_cpu': ''}
        line_list = top_info.split('\n')
        for line in line_list:
            if package in line:
                key_list = line.split()
                pid = key_list[0]
                package_name = key_list[-1]

                logger.debug("parse package: %s, pid: %s" % (package_name, pid))
                if package == package_name:
                    cpu_index = self.get_col_index(top_info, ["CPU]", "CPU%"])
                    if cpu_index is not None and len(key_list) > cpu_index:
                        pkg_cpu_rate = key_list[cpu_index]
                        pkg_cpu_rate = pkg_cpu_rate.replace('%', '')
                        package_dict['pid'] = pid
                        package_dict['pkg_cpu_rate'] = pkg_cpu_rate
                        break
        return package_dict

    def _parse_device(self, top_info):
        """
        通过top命令获取测试设备的cpu信息
        :return:
        """
        user_rate = ''
        sys_rate = ''
        idle_rate = ''
        total_rate = ''
        if self.sdk_version < 26:
            match = re.compile(r'User (\d+)%, System (\d+)%, IOW (\d+)%, IRQ (\d+)%').search(top_info)
            if match:
                user_rate = match.group(1)
                sys_rate = match.group(2)
                total_rate = int(user_rate) + int(sys_rate)
                logger.debug("user cpu: %s, sys cpu: %s, total cpu: %s" % (user_rate, sys_rate, str(total_rate)))
        else:
            match = re.compile(r'(\d+)%cpu\s+(\d+)%user\s+(\d+)%nice\s+(\d+)%sys\s+(\d+)%idle\s+(\d+)%iow\s+(\d+)%irq'
                               r'\s+(\d+)%sirq\s+(\d+)%host').search(top_info)
            if match:
                user_rate = match.group(2)
                sys_rate = match.group(4)
                idle_rate = match.group(5)
                total_rate = int(user_rate) + int(sys_rate)
                logger.debug("user cpu: %s, sys cpu: %s, idle cpu: %s, total cpu: %s" % (user_rate, sys_rate, idle_rate,
                                                                                         str(total_rate)))
        return dict(user_rate=user_rate, sys_rate=sys_rate, idle_rate=idle_rate, total_rate=total_rate)

    def _get_cpu_info(self):
        """
        获取设备、包cpu信息
        :return:
        """
        top_process = self.device.adb.run_adb_shell_cmd(self._top_cmd, sync=False)
        top_info = top_process.stdout.read()
        error = top_process.stderr.read()
        if error:
            logger.error("get cpu info error : " + str(error))
            return
        top_info = str(top_info, "utf-8")
        top_info.replace('\r', '')
        top_file = os.path.join(self.temp_data.result_path, 'cpu.log')
        with open(top_file, "a+", encoding="utf-8") as writer:
            writer.write(Utils.get_current_time() + " top info:\n")
            writer.write(top_info + "\n\n")
        if Utils.get_file_size(top_file) > 100:
            os.rename(top_file, top_file + '_' + Utils.get_current_time())
        package_cpu = self._parse_package(self.package, top_info)
        device_cpu = self._parse_device(top_info)
        package_cpu.update(device_cpu)
        return package_cpu

    def _cpu_collect(self):
        """
        cpu信息收集方法
        :return:
        """
        end_time = time.time() + self._timeout
        cpu_title = ["datetime", "total%", "user%", "system%", "idle%", "package", "package%"]
        cpu_file = os.path.join(self.temp_data.result_path, 'cpu.csv')
        try:
            with open(cpu_file, 'a+') as f:
                csv.writer(f, lineterminator='\n').writerow(cpu_title)
        except RuntimeError as e:
            logger.error(e)
        while not self._stop_event.is_set() and time.time() < end_time:
            try:
                cpu_list = []
                s_time = time.time()
                cpu_dict = self._get_cpu_info()
                execution_time = time.time() - s_time
                logger.debug("cpu collect time: " + str(execution_time))
                total_rate = cpu_dict.get('total_rate')
                user_rate = cpu_dict.get('user_rate')
                sys_rate = cpu_dict.get('sys_rate')
                idle_rate = cpu_dict.get('idle_rate')
                package = cpu_dict.get('package')
                pkg_cpu_rate = cpu_dict.get('pkg_cpu_rate')
                if pkg_cpu_rate is None:
                    logger.debug("package cpu get error")
                    continue
                cpu_list.extend(
                    [Utils.get_current_time(), total_rate, user_rate, sys_rate, idle_rate, package, pkg_cpu_rate])

                logger.info('total_cpu_rate:%s%%, user:%s%%, system:%s%%, idle:%s%%, package_cpu:%s%%' % (
                    total_rate, user_rate, sys_rate, idle_rate, pkg_cpu_rate))
                try:
                    with open(cpu_file, 'a+', encoding="utf-8") as f:
                        csv.writer(f, lineterminator='\n').writerow(cpu_list)
                except RuntimeError as e:
                    logger.error(e)

                sleep_time = self._interval - execution_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                logger.error('_cpu_collect error' + str(e))
        logger.debug("stop event is set or timeout")

    def start(self):
        """
        cpu收集启动方法
        :return:
        """
        logger.debug("CpuCollector start")
        self.collect_cpu_thread = threading.Thread(target=self._cpu_collect)
        self.collect_cpu_thread.start()

    def stop(self):
        """
        cpu收集停止方法
        :return:
        """
        logger.debug("CpuCollector stop")
        if self.collect_cpu_thread.isAlive():
            self._stop_event.set()
            self.collect_cpu_thread.join(timeout=2)
            self.collect_cpu_thread = None

        if hasattr(self, "_top_pipe"):
            if self._top_pipe.poll() is None:
                self._top_pipe.terminate()


if __name__ == '__main__':
    from src.perf_test import TempData

    TempData.result_path = r'D:\pythoncode\AdbTool\result'
    cpu_monitor = CpuCollector('172.31.120.178:5555', 'com.mgtv.tv', TempData)
    cpu_monitor.start()
    time.sleep(20)
    cpu_monitor.stop()

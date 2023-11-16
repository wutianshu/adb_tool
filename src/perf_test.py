#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import time
import config
import threading
from src.log import logger
from src.utils import Utils
from src.report import Report
from src.monkey import Monkey
from src.logcat import Logcat
from src.fps import FPSMonitor
from src.fd import FdCollector
from src.cpu import CpuCollector
from src.mail import send_mail
from src.adbutils import AdbUtils
from src.memory import MemCollector
from src.activity import DeviceMonitor
from src.threads import ThreadCollector
from src.adbmonkey import AdbMonkey


class TempData:
    old_pid = []
    package = None
    result_path = None
    start_time = None
    fd_num = 0
    terminate_signal = threading.Event()


class StartUp(object):
    def __init__(self, device_id):
        self.temp_data = TempData()
        self.device_id = device_id
        self.package = config.package
        self.frequency = config.frequency
        self.timeout = config.timeout * 3600
        self.exception_log_list = config.error_log
        self.mail = config.mail
        self.device = AdbUtils(self.device_id)
        self.temp_data.package = self.package
        self.collectors = []
        self.logcat_collector = None

    def add_collector(self, collector):
        self.collectors.append(collector)

    def run(self):
        report_path = config.report_path
        if report_path:
            Report(report_path, self.package)
            return
        self.clear_dump_heap()
        model = self.device.adb.get_devices_model()
        if model not in config.root_disable:
            self.device.adb.run_adb_cmd('root')
            time.sleep(3)
        is_device_connect = False
        for i in range(5):
            if self.device.adb.is_device_connected(self.device_id):
                is_device_connect = True
                break
            else:
                logger.error("device not found:" + self.device_id)
                time.sleep(10)
        if not is_device_connect:
            logger.error("50 second wait,device not found:" + self.device_id)
            return
        if not self.device.adb.is_app_installed(self.package):
            logger.error("test app not installed:" + self.package)
            # return
        try:
            args = (self.device_id, self.package, self.temp_data, self.frequency, self.timeout)
            if config.cpu_var:
                self.add_collector(CpuCollector(*args))
            if config.mem_var:
                self.add_collector(MemCollector(*args))
            if config.fps_var:
                self.add_collector(FPSMonitor(*args))
            if config.fd_var:
                self.add_collector(FdCollector(*args))
            if config.thr_var:
                self.add_collector(ThreadCollector(*args))
            if config.monkey == "monkey":
                self.add_collector(Monkey(*args))
            if config.monkey == "adb":
                self.add_collector(AdbMonkey(*args))
            if (config.main_activity and config.activity_list) or config.black_activity_list:
                self.add_collector(DeviceMonitor(*args))

            if len(self.collectors):
                start_time = Utils.get_current_underline_time()
                self.temp_data.start_time = start_time

                # 测试需求增加version code
                code, _ = self.device.adb.get_package_version(self.package)
                if code:
                    start_time += f'_{code}'
                if config.save_path:
                    self.temp_data.result_path = os.path.join(config.save_path, self.package, start_time)
                else:
                    self.temp_data.result_path = os.path.join(config.root_path, 'results', self.package, start_time)
                Utils.creat_folder(self.temp_data.result_path)
                self.save_device_info()
                for monitor in self.collectors:
                    try:
                        monitor.start()
                    except Exception as e:
                        logger.error(e)
                try:
                    self.logcat_collector = Logcat(self.device_id, self.package, self.temp_data)
                    if self.exception_log_list:
                        self.logcat_collector.set_exception_list(self.exception_log_list)
                        self.logcat_collector.add_log_handle(self.logcat_collector.handle_exception)
                        self.logcat_collector.add_log_handle(self.logcat_collector.handle_ueec_report)
                        self.logcat_collector.add_log_handle(self.logcat_collector.handle_step_report)
                        self.logcat_collector.add_log_handle(self.logcat_collector.handle_page_measure)
                    time.sleep(1)
                    self.logcat_collector.start()
                except Exception as e:
                    logger.error(e)

                end_time = time.time() + self.timeout
                while time.time() < end_time:
                    if self.check_task_stop():
                        logger.error("test app " + self.package + " exit signal, quit!")
                        break
                    time.sleep(self.frequency)
                logger.debug("test time is up,test finish")
                self.stop()
        except KeyboardInterrupt:
            logger.debug("catch KeyboardInterrupt, test finish")
            self.stop()
        except Exception as e:
            logger.error(e)

    def clear_dump_heap(self):
        file_list = self.device.adb.get_dir_file("/data/local/tmp")
        if file_list:
            for file in file_list:
                if self.package in file:
                    self.device.adb.remove_file("/data/local/tmp/%s" % file)

    def stop(self):
        for monitor in self.collectors:
            try:
                monitor.stop()
            except Exception as e:
                logger.error(e)

        try:
            if self.logcat_collector:
                self.logcat_collector.stop()
        except Exception as e:
            logger.error("stop exception for logcat monitor")
            logger.error(e)
        cost_time = round(float(
            time.time() - Utils.get_time_stamp(self.temp_data.start_time, "%Y_%m_%d_%H_%M_%S")) / 3600,
                          2)
        self.add_device_info("test cost time:", str(cost_time) + "h")
        report = Report(self.temp_data.result_path, self.package)
        report_path = report.book_name
        error_path = os.path.join(self.temp_data.result_path, 'error.log')
        files_path = [i for i in [report_path, error_path] if os.path.isfile(i)]
        send_mail(self.mail, self.device_id, self.device.adb.get_devices_model(), self.device.adb.get_system_version(),
                  files_path)
        logger.info('dumpheap takes a few minutes')
        self.pull_log_files()
        self.pull_heapdump()
        self.device.adb.package_dumpheap(self.package, self.temp_data.result_path)
        self.device.adb.remove_file('/data/local/tmp/*.hprof')

    def pull_heapdump(self):
        file_list = self.device.adb.get_dir_file("/data/local/tmp")
        if file_list:
            for file in file_list:
                if self.package in file:
                    self.device.adb.pull_file("/data/local/tmp/%s" % file, self.temp_data.result_path)

    def pull_log_files(self):
        if config.devices_log_path:
            for src_path in config.devices_log_path:
                self.device.adb.pull_file(src_path, self.temp_data.result_path)

    def save_device_info(self):
        file_path = os.path.join(self.temp_data.result_path, "device.txt")
        with open(file_path, "w+", encoding="utf-8") as writer:
            writer.write("device_id:" + self.device_id + "\n")
            writer.write(
                "device:" + self.device.adb.get_devices_brand() + " " + self.device.adb.get_devices_model() + "\n")
            writer.write("package name:" + self.package + "\n")
            writer.write(("package version code:%s\n" + "package version name:%s\n") %
                         self.device.adb.get_package_version(self.package))
            writer.write("system version:" + self.device.adb.get_system_version() + "\n")

    def add_device_info(self, key, value):
        device_file = os.path.join(self.temp_data.result_path, "device_test_info.txt")
        with open(device_file, "a+", encoding="utf-8") as writer:
            writer.write(key + ":" + value + "\n")

    @staticmethod
    def check_task_stop():
        if config.task_stop is True:
            return True
        else:
            return False


def main():
    device = config.devices
    timeout = config.timeout
    report_path = config.report_path
    if device or report_path:
        start = StartUp(device)
        start.run()
    else:
        adb = AdbUtils()
        device_list = adb.list_local_devices()
        perf_thread_list = []
        for device in device_list:
            start = StartUp(device)
            perf_thread = threading.Thread(target=start.run)
            perf_thread_list.append(perf_thread)
            perf_thread.start()
            time.sleep(5)
        end_time = time.time() + timeout
        while time.time() < end_time or len(perf_thread_list) == 0:
            time.sleep(5)
            for perf_thread in perf_thread_list:
                if not perf_thread.is_alive():
                    perf_thread_list.remove(perf_thread)
        logger.debug('all perf test finish')
    logger.info('perf test is finish')


if __name__ == "__main__":
    main()

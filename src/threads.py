#!/usr/bin/env python
# -*- coding: utf-8 -*-
import csv
import os
import time
import threading
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class ThreadCollector:
    def __init__(self, device, package, temp_data, interval=5, timeout=60):
        self.device = AdbUtils(device)
        self.package = package
        self.temp_data = temp_data
        self._interval = interval
        self._timeout = timeout
        self._stop_event = threading.Event()
        self.collect_threads_thread = None
        self.sdk_version = self.device.adb.get_sdk_version()

    def _get_package_thread(self):
        """
        获取包线程信息
        :return:
        """
        pid = self.device.adb.get_pid_from_package(self.package)
        if pid not in self.temp_data.old_pid:
            self.temp_data.old_pid.append(pid)
        if not pid:
            return []
        if self.sdk_version < 26:
            result = self.device.adb.run_adb_shell_cmd('ps -t %s' % pid)
        elif self.sdk_version == 27:
            result = self.device.adb.run_adb_shell_cmd('busybox ps -T|grep  %s' % self.package)
        else:
            result = self.device.adb.run_adb_shell_cmd('ps -T %s' % pid)
        thread_file = os.path.join(self.temp_data.result_path, 'thread.log')
        with open(thread_file, "a+", encoding="utf-8") as writer:
            writer.write(Utils.get_current_time() + " thread:\n")
            writer.write(result + "\n\n")
        if Utils.get_file_size(thread_file) > 100:
            os.rename(thread_file, thread_file + '_' + Utils.get_current_time())
        collection_time = time.time()
        if result:
            thread_num = len(result.split("\n"))
            return [collection_time, self.package, pid, thread_num]
        else:
            return []

    def _thread_collect(self):
        """
        线程信息收集方法
        :return:
        """
        e_time = time.time() + self._timeout
        thread_title = ("datetime", "package", "pid", "num")
        thread_file = os.path.join(self.temp_data.result_path, 'thread.csv')
        try:
            with open(thread_file, 'a+') as df:
                csv.writer(df, lineterminator='\n').writerow(thread_title)
        except RuntimeError as e:
            logger.error(e)

        while not self._stop_event.is_set() and time.time() < e_time:
            try:
                s_time = time.time()
                thread_info = self._get_package_thread()
                current_time = Utils.get_current_time()
                if not thread_info:
                    continue
                else:
                    logger.info('thread num:%s' % thread_info[3])
                try:
                    with open(thread_file, 'a+', encoding="utf-8") as thread_writer:
                        writer_p = csv.writer(thread_writer, lineterminator='\n')
                        thread_info[0] = current_time
                        writer_p.writerow(thread_info)
                except RuntimeError as e:
                    logger.error(e)

                execution_time = time.time() - s_time
                sleep_time = self._interval - execution_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                logger.error("_thread_collect error" + str(e))

    def start(self):
        """
        线程收集启动方法
        :return:
        """
        logger.debug("ThreadCollector start")
        self.collect_threads_thread = threading.Thread(target=self._thread_collect)
        self.collect_threads_thread.start()

    def stop(self):
        """
        线程收集停止方法
        :return:
        """
        logger.debug("ThreadCollector stop")
        if self.collect_threads_thread.isAlive():
            self._stop_event.set()
            self.collect_threads_thread.join(timeout=1)
            self.collect_threads_thread = None


if __name__ == "__main__":
    from src.perf_test import TempData

    TempData.result_path = r'D:\pythoncode\PerfTest\results\com.hunantv.operator\2021_09_18_10_18_17'
    monitor = ThreadCollector("", "com.hunantv.operator", TempData)
    monitor.start()
    time.sleep(60)
    monitor.stop()

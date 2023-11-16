#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import csv
import time
import config
import threading
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class MemCollector:
    def __init__(self, device, package, temp_data, interval=5, timeout=60):
        self.device = AdbUtils(device)
        self.package = package
        self.temp_data = temp_data
        self._interval = interval
        self._timeout = timeout
        self._stop_event = threading.Event()
        self.collect_mem_thread = None

    @staticmethod
    def mem_parse(result):
        re_process = re.compile(r'\*\* MEMINFO in pid (\d+) \[(\S+)] \*\*')
        re_total_pss = re.compile(r'TOTAL\s+(\d+)')
        re_java_heap = re.compile(r"Java Heap:\s+(\d+)")
        re_native_heap = re.compile(r"Native Heap:\s+(\d+)")
        re_system = re.compile(r'System:\s+(\d+)')
        re_views = re.compile(r'Views:\s+(\d+)')
        re_activities = re.compile(r'Activities:\s+(\d+)')

        match = re_process.search(result)
        if match:
            pid = match.group(1)
            process_name = match.group(2)
        else:
            pid = process_name = ''
        match = re_total_pss.search(result)
        if match:
            total_pss = round(float(match.group(1)) / 1024, 2)
        else:
            total_pss = 0
        match = re_java_heap.search(result)
        if match:
            java_heap = round(float(match.group(1)) / 1024, 2)
        else:
            java_heap = 0
        match = re_native_heap.search(result)
        if match:
            native_heap = round(float(match.group(1)) / 1024, 2)
        else:
            native_heap = 0
        match = re_system.search(result)
        if match:
            system = round(float(match.group(1)) / 1024, 2)
        else:
            system = 0
        match = re_views.search(result)
        if match:
            views = match.group(1)
        else:
            views = 0
        match = re_activities.search(result)
        if match:
            activities = match.group(1)
        else:
            activities = 0
        return dict(pid=pid, process_name=process_name, total_pss=total_pss, java_heap=java_heap,
                    native_heap=native_heap, system=system, views=views, activities=activities)

    def _dumpsys_mem_parse_(self, package):
        result = self.device.adb.run_adb_shell_cmd('dumpsys meminfo %s' % package)
        mem_file = os.path.join(self.temp_data.result_path, 'memory.log')
        with open(mem_file, "a+", encoding="utf-8") as writer:
            writer.write(Utils.get_current_time() + " dumpsys mem package info:\n")
            if result:
                writer.write(result + "\n\n")
        return self.mem_parse(result)

    def _memory_collect(self):
        """
        内存收集方法
        :return:
        """
        end_time = time.time() + self._timeout
        pid_title = ["datetime", "package", "pid"]
        pss_title = ["datetime", "package", "pid", "pss", "java_heap", "native_heap", "system", 'views', 'activities']
        pid_file = os.path.join(self.temp_data.result_path, 'pid.csv')
        pss_file = os.path.join(self.temp_data.result_path, 'pss.csv')
        try:
            with open(pss_file, 'a+', encoding="utf-8") as f:
                csv.writer(f, lineterminator='\n').writerow(pss_title)
            with open(pid_file, 'a+', encoding="utf-8") as f:
                csv.writer(f, lineterminator='\n').writerow(pid_title)
        except RuntimeError as e:
            logger.error(e)
        s_time = time.time()
        old_pid = None
        dumpsys_mem_times = 0
        hprof_path = "/data/local/tmp"
        self.device.adb.mkdir(hprof_path)
        is_first = True
        while not self._stop_event.is_set() and time.time() < end_time:
            try:
                start = time.time()
                collection_time = time.time()
                mem_info_dict = self._dumpsys_mem_parse_(self.package)
                pss_file = os.path.join(self.temp_data.result_path, 'pss.csv')
                current_pid = mem_info_dict.get('pid')
                total_pss = mem_info_dict.get('total_pss')
                java_heap = mem_info_dict.get('java_heap')
                native_heap = mem_info_dict.get('native_heap')
                system = mem_info_dict.get('system')
                views = mem_info_dict.get('views')
                activities = mem_info_dict.get('activities')
                if total_pss is None or total_pss == 0:
                    logger.debug("package memory get error")
                    continue
                logger.info("package total mem:%sMB,java_heap:%sMB,native_heap:%sMB,system:%sMB" % (
                    total_pss, java_heap, native_heap, system))
                pss_list = [Utils.get_format_time(collection_time), self.package, current_pid, total_pss, java_heap,
                            native_heap, system, views, activities]
                with open(pss_file, 'a+', encoding="utf-8") as pss_writer:
                    writer_p = csv.writer(pss_writer, lineterminator='\n')
                    writer_p.writerow(pss_list)

                if is_first or (start - s_time) > config.dumpheap_freq * 3600:
                    is_first = False
                    file_list = self.device.adb.get_dir_file(hprof_path)
                    if file_list:
                        for file in file_list:
                            if self.package in file:
                                self.device.adb.remove_file(hprof_path + "/" + file)
                    self.device.adb.package_dumpheap(self.package, self.temp_data.result_path)
                    s_time = start
                dumpsys_mem_times += 1

                pid_list = [Utils.get_format_time(collection_time)]
                pid_change = False

                if old_pid is None:
                    old_pid = current_pid
                    pid_change = True
                else:
                    if current_pid and current_pid != old_pid:
                        pid_change = True
                if pid_change:
                    old_pid = current_pid
                    pid_list.extend([self.package, current_pid])
                    try:
                        with open(pid_file, 'a+', encoding="utf-8") as pid_writer:
                            writer_p = csv.writer(pid_writer, lineterminator='\n')
                            writer_p.writerow(pid_list)
                            logger.debug("write to file:" + pid_file)
                    except RuntimeError as e:
                        logger.error(e)
                end = time.time()
                execution_time = end - start
                sleep_time = self._interval - execution_time
                logger.debug("memory cycle once: " + str(execution_time))
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                logger.error('_memory_collect error' + str(e))
        logger.debug("stop event is set or timeout")

    def start(self):
        """
        内存收集启动方法
        :return:
        """
        logger.debug("MemCollector start")
        self.collect_mem_thread = threading.Thread(target=self._memory_collect)
        self.collect_mem_thread.start()

    def stop(self):
        """
        内存收集停止方法
        :return:
        """
        logger.debug("MemCollector stop")
        if self.collect_mem_thread.isAlive():
            self._stop_event.set()
            self.collect_mem_thread.join(timeout=1)
            self.collect_mem_thread = None


if __name__ == "__main__":
    from src.perf_test import TempData

    TempData.result_path = r'D:\pythoncode\AdbTool\results'
    TempData.config_dic = dict(dumpheap_freq=3600)
    monitor = MemCollector('MAX0019071000091', 'com.mgtv.tv', TempData)
    monitor.start()
    time.sleep(180)
    monitor.stop()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
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
from src.memory import MemCollector


class AdbMonkey:
    def __init__(self, device, package, temp_data, interval=5, timeout=9999999):
        self.device = AdbUtils(device)
        self.package = package
        self._interval = 1
        self._timeout = timeout
        self._stop_event = threading.Event()
        self.collect_thread_num_thread = None
        self.monkey_cmd = config.monkey_cmd
        self.temp_data = temp_data
        self.main_activity = self.device.adb.get_main_activity(package)
        self.key_map = {
            '4': {'name': 'back', 'weight': 5},
            '19': {'name': 'up', 'weight': 20},
            '20': {'name': 'down', 'weight': 20},
            '21': {'name': 'left', 'weight': 20},
            '22': {'name': 'right', 'weight': 20},
            '23': {'name': 'OK', 'weight': 20},
            '82': {'name': 'menu', 'weight': 5},
            '3': {'name': 'home', 'weight': 1}
            # '84': {'name': 'search', 'weight': 1},
        }

    @property
    def random_key(self):
        """
        根据配置权重随机挑选按键
        :return: 按键key
        """
        total = sum([value.get('weight') for value in self.key_map.values()])
        ra = random.uniform(0, total)
        curr_sum = 0
        keys = self.key_map.keys()
        ret = list(keys)[random.randint(0, len(keys) - 1)]
        for k in keys:
            curr_sum += self.key_map[k]['weight']
            if ra <= curr_sum:
                ret = k
                break
        return ret

    def get_main_activity_windows(self, dumpsys):
        """
        获取应用首页窗口数量
        :param dumpsys:dumpsys window返回信息
        :return:窗口数量
        """
        activity = self.main_activity
        activity = activity.split('/')[-1]
        re_window = re.compile(r'Window #\d Window\{.+?%s\}' % activity)
        match = re_window.findall(dumpsys)
        match = [i for i in match if i.find('SurfaceView') == -1]
        return len(match)

    def _adb_monkey(self):
        """
        adb monkey执行方法
        :return:
        """
        end_time = time.time() + self._timeout
        if self.monkey_cmd is not None and self.monkey_cmd in self.key_map.keys():
            self.key_map.pop(self.monkey_cmd)
        self.start_app()
        is_start = 0

        adb_monkey_file = os.path.join(self.temp_data.result_path, 'monkey.csv')
        monkey_list_title = ("datetime", "activity", "key", 'views', 'activities')
        try:
            with open(adb_monkey_file, 'a+') as df:
                csv.writer(df, lineterminator='\n').writerow(monkey_list_title)
        except RuntimeError as e:
            logger.error(e)

        while not self._stop_event.is_set() and time.time() < end_time:
            try:
                if self.temp_data.fd_num > 700:
                    logger.error('fd num > 700, adb monkey stop')
                    break
                before = time.time()
                view = activity = 0
                logger.debug("-----------into _adb_monkey loop, thread is : " + str(
                    threading.current_thread().name))

                current_activity, dumpsys_result = self.device.adb.get_focus_window_activity(False)

                if not current_activity:
                    continue
                else:
                    win_num = self.get_main_activity_windows(dumpsys_result)
                    if self.main_activity in current_activity and win_num > 1:
                        self.device.adb.run_adb_shell_cmd('input keyevent 4')
                        logger.debug('adb monkey detect retain page, input key :4')

                    current_time = Utils.get_current_time()

                    if current_activity.find(self.package) == -1:
                        is_start += 1
                        if is_start > 4:
                            out = self.device.adb.run_adb_shell_cmd('dumpsys meminfo %s' % self.package)
                            try:
                                pkg_mem_info = MemCollector.mem_parse(out)
                                pid = view, activity = pkg_mem_info.pid, pkg_mem_info.view, pkg_mem_info.activity
                                logger.info('pid:%s, vies:%s, activity:%s' % (pid, view, activity))
                            except Exception as e:
                                logger.debug(e)
                            self.start_app()
                            is_start = 0

                        else:
                            time.sleep(2)
                            continue
                    key_code = self.random_key
                    if key_code == '4' and self.main_activity in current_activity:
                        continue
                    self.device.adb.run_adb_shell_cmd('input keyevent %s' % key_code)
                    key_code_name = self.key_map.get(key_code).get('name')
                    logger.debug('press key %s' % key_code_name)
                    try:
                        with open(adb_monkey_file, 'a+', encoding="utf-8") as monkey_writer:
                            writer_p = csv.writer(monkey_writer, lineterminator='\n')
                            writer_p.writerow([current_time, current_activity, key_code_name, view, activity])
                    except RuntimeError as e:
                        logger.error(e)
                after = time.time()
                time_consume = after - before
                delta_inter = self._interval - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logger.error("an exception happened in adb monkey, reason unknown!")
                logger.debug(e)
                s = traceback.format_exc()
                logger.debug(s)

    def start_app(self):
        """
        应用启动方法
        :return:
        """
        self.device.adb.start_activity(f'{self.package}/{self.main_activity}')
        logger.debug('start app %s' % self.main_activity)

    def start(self):
        """
        adb monkey启动方法
        :return:
        """
        logger.debug("AdbMonkey start")
        self.collect_thread_num_thread = threading.Thread(target=self._adb_monkey)
        self.collect_thread_num_thread.start()

    def stop(self):
        """
        adb monkey停止方法
        :return:
        """
        logger.debug("AdbMonkey stop")
        if self.collect_thread_num_thread.isAlive():
            self._stop_event.set()
            self.collect_thread_num_thread.join(timeout=1)
            self.collect_thread_num_thread = None


if __name__ == "__main__":
    from src.perf_test import TempData

    TempData.result_path = r'D:\pythoncode\AdbTool\results'
    monitor = AdbMonkey('172.31.120.177:5555', "com.gitvdemo.video", TempData)
    monitor.start()
    time.sleep(1200000)
    monitor.stop()

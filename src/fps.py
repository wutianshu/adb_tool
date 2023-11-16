#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import csv
import time
import copy
import queue
import datetime
import threading
import traceback
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class SurfaceStatsCollector(object):
    def __init__(self, device, frequency, package_name, temp_data, jank_threshold, use_legacy=False):
        self.device = device
        self.frequency = frequency
        self.package_name = package_name
        self.temp_data = temp_data
        self.jank_threshold = jank_threshold / 1000.0
        self.use_legacy_method = use_legacy
        self.surface_before = 0
        self.last_timestamp = 0
        self.data_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.focus_window = None
        self.collector_thread = None
        self.calculator_thread = None
        self.sdk_version = self.device.adb.get_sdk_version()

    def start(self):
        """
        打开SurfaceStatsCollector
        :return:
        """
        if not self.use_legacy_method and self._clear_surface_flinger_latency_data():
            try:
                self.focus_window = self.get_focus_activity()
                # 如果self.focus_window里包含字符'$'，必须将其转义
                if self.focus_window.find('$') != -1:
                    self.focus_window = self.focus_window.replace('$', r'\$')
            except Exception as e:
                logger.warn(u'无法动态获取当前Activity名称，使用page_flip统计全屏帧率！')
                logger.debug(e)
                self.use_legacy_method = True
                self.surface_before = self._get_surface_stats_legacy()
        else:
            logger.debug("dumpsys SurfaceFlinger --latency-clear is none")
            self.use_legacy_method = True
            self.surface_before = self._get_surface_stats_legacy()
        self.collector_thread = threading.Thread(target=self._collector_thread)
        self.collector_thread.start()
        self.calculator_thread = threading.Thread(target=self._calculator_thread)
        self.calculator_thread.start()

    def stop(self):
        """
        停止SurfaceStatsCollector
        :return:
        """
        if self.collector_thread:
            self.stop_event.set()
            self.collector_thread.join()
            self.collector_thread = None

    def get_focus_activity(self):
        return self.device.adb.get_focus_window_activity()

    def _calculate_results(self, timestamps):
        frame_count = len(timestamps)
        if frame_count == 0:
            fps = 0
            jank = 0
        elif frame_count == 1:
            fps = 1
            jank = 0
        else:
            seconds = timestamps[-1][1] - timestamps[0][1]
            if seconds > 0:
                fps = int(round((frame_count - 1) / seconds))
                jank = self._calculate_jank(timestamps)
            else:
                fps = 1
                jank = 0
        return fps, jank

    def _calculate_results_new(self, timestamps):
        frame_count = len(timestamps)
        if frame_count == 0:
            fps = 0
            jank = 0
        elif frame_count == 1:
            fps = 1
            jank = 0
        elif frame_count == 2 or frame_count == 3 or frame_count == 4:
            seconds = timestamps[-1][1] - timestamps[0][1]
            if seconds > 0:
                fps = int(round((frame_count - 1) / seconds))
                jank = self._calculate_jank(timestamps)
            else:
                fps = 1
                jank = 0
        else:
            seconds = timestamps[-1][1] - timestamps[0][1]
            if seconds > 0:
                fps = int(round((frame_count - 1) / seconds))
                jank = self._calculate_jank_new(timestamps)
            else:
                fps = 1
                jank = 0
        if fps > 60:
            fps = 60
        return fps, jank

    def _calculate_jank_new(self, timestamps):
        """同时满足两个条件计算为一次卡顿：
        ①Display FrameTime>前三帧平均耗时2倍。
        ②Display FrameTime>两帧电影帧耗时 (1000ms/24*2≈83.33ms)。
        """

        two_frame_stamp = 83.3 / 1000.0
        temp_frame_stamp = 0
        # 统计丢帧卡顿
        jank = 0
        for index, timestamp in enumerate(timestamps):
            # 前面四帧按超过166ms计算为卡顿
            if (index == 0) or (index == 1) or (index == 2) or (index == 3):
                if temp_frame_stamp == 0:
                    temp_frame_stamp = timestamp[1]
                    continue
                # 绘制帧耗时
                cost_time = timestamp[1] - temp_frame_stamp
                # 耗时大于阈值10个时钟周期,用户能感受到卡顿感
                if cost_time > self.jank_threshold:
                    jank = jank + 1
                temp_frame_stamp = timestamp[1]
            elif index > 3:
                current_stamp = timestamps[index][1]
                last_one_stamp = timestamps[index - 1][1]
                last_two_stamp = timestamps[index - 2][1]
                last_three_stamp = timestamps[index - 3][1]
                last_four_stamp = timestamps[index - 4][1]
                temp_frame_time = ((last_three_stamp - last_four_stamp) + (last_two_stamp - last_three_stamp) + (
                        last_one_stamp - last_two_stamp)) / 3 * 2
                current_frame_time = current_stamp - last_one_stamp
                if (current_frame_time > temp_frame_time) and (current_frame_time > two_frame_stamp):
                    jank = jank + 1
        return jank

    def _calculate_jank(self, timestamps):
        temp_stamp = 0
        # 统计丢帧卡顿
        jank = 0
        for timestamp in timestamps:
            if temp_stamp == 0:
                temp_stamp = timestamp[1]
                continue
            # 绘制帧耗时
            cost_time = timestamp[1] - temp_stamp
            # 耗时大于阈值10个时钟周期,用户能感受到卡顿感
            if cost_time > self.jank_threshold:
                jank = jank + 1
            temp_stamp = timestamp[1]
        return jank

    def _calculator_thread(self):
        """
        处理surface flinger数据
        :return:
        """
        fps_file = os.path.join(self.temp_data.result_path, 'fps.csv')
        if self.use_legacy_method:
            fps_title = ['datetime', 'fps']
        else:
            fps_title = ['datetime', "activity window", 'fps', 'jank']
        try:
            with open(fps_file, 'a+') as df:
                csv.writer(df, lineterminator='\n').writerow(fps_title)
        except RuntimeError as e:
            logger.exception(e)

        while True:
            try:
                data = self.data_queue.get()
                if isinstance(data, str) and data == 'Stop':
                    break
                before = time.time()
                if self.use_legacy_method:
                    td = data['timestamp'] - self.surface_before['timestamp']
                    seconds = td.seconds + td.microseconds / 1e6
                    frame_count = (data['page_flip_count'] -
                                   self.surface_before['page_flip_count'])
                    fps = int(round(frame_count / seconds))
                    if fps > 60:
                        fps = 60
                    self.surface_before = data
                    logger.debug('FPS:%2s' % fps)
                    tmp_list = [Utils.get_current_underline_time(), fps]
                    try:
                        with open(fps_file, 'a+', encoding="utf-8") as f:
                            csv.writer(f, lineterminator='\n').writerow(tmp_list)
                    except RuntimeError as e:
                        logger.exception(e)
                else:
                    timestamps = data[1]
                    collect_time = data[2]
                    fps, jank = self._calculate_results_new(timestamps)
                    if not fps or not self.focus_window:
                        continue
                    logger.info('fps:%s jank:%s' % (fps, jank))
                    fps_list = [collect_time, self.focus_window, fps, jank]
                    try:
                        with open(fps_file, 'a+', encoding="utf-8") as f:
                            tmp_list = copy.deepcopy(fps_list)
                            tmp_list[0] = Utils.get_format_time(tmp_list[0])
                            csv.writer(f, lineterminator='\n').writerow(tmp_list)
                    except RuntimeError as e:
                        logger.exception(e)
                time_consume = time.time() - before
                delta_inter = self.frequency - time_consume
                if delta_inter > 0:
                    time.sleep(delta_inter)
            except Exception as e:
                logger.error("an exception happened in fps _calculator_thread ,reason unknown!")
                logger.debug(e)
                s = traceback.format_exc()
                logger.debug(s)

    def _collector_thread(self):
        is_first = True
        while not self.stop_event.is_set():
            try:
                before = time.time()
                if self.use_legacy_method:
                    surface_state = self._get_surface_stats_legacy()
                    if surface_state:
                        self.data_queue.put(surface_state)
                else:
                    timestamps = []
                    refresh_period, new_timestamps = self._get_surface_flinger_frame_data()
                    if refresh_period is None or new_timestamps is None:
                        # activity发生变化，旧的activity不存时，取的时间戳为空，
                        self.focus_window = self.get_focus_activity()
                        logger.debug("refresh_period is None or timestamps is None")
                        continue
                    # 计算不重复的帧
                    timestamps += [timestamp for timestamp in new_timestamps if timestamp[1] > self.last_timestamp]
                    if len(timestamps):
                        first_timestamp = [[0, self.last_timestamp, 0]]
                        if not is_first:
                            timestamps = first_timestamp + timestamps
                        self.last_timestamp = timestamps[-1][1]
                        is_first = False
                    else:
                        # 两种情况：1）activity发生变化，但旧的activity仍然存时，取的时间戳不为空，但时间全部小于等于last_timestamp
                        #        2）activity没有发生变化，也没有任何刷新
                        is_first = True
                        cur_focus_window = self.get_focus_activity()
                        if self.focus_window != cur_focus_window:
                            self.focus_window = cur_focus_window
                            continue
                    logger.debug(timestamps)
                    self.data_queue.put((refresh_period, timestamps, time.time()))
                    time_consume = time.time() - before
                    delta_inter = self.frequency - time_consume
                    if delta_inter > 0:
                        time.sleep(delta_inter)
            except Exception as e:
                logger.error("an exception happened in fps _collector_thread , reason unknown!")
                logger.debug(e)
                s = traceback.format_exc()
                logger.debug(s)
        self.data_queue.put(u'Stop')

    def _clear_surface_flinger_latency_data(self):
        """
        :return:
        """
        if self.focus_window is None:
            results = self.device.adb.run_adb_shell_cmd(
                'dumpsys SurfaceFlinger --latency-clear')
        else:
            results = self.device.adb.run_adb_shell_cmd(
                'dumpsys SurfaceFlinger --latency-clear %s' % self.focus_window)
        return not len(results)

    def _get_surface_flinger_frame_data(self):
        timestamps = []
        nanoseconds_per_second = 1e9
        pending_fence_timestamp = (1 << 63) - 1
        if self.sdk_version >= 26:
            results = self.device.adb.run_adb_shell_cmd('dumpsys SurfaceFlinger --latency %s' % self.focus_window)
            results = results.replace("\r\n", "\n").splitlines()
            refresh_period = int(results[0]) / nanoseconds_per_second
            results = self.device.adb.run_adb_shell_cmd('dumpsys gfxinfo %s framestats' % self.package_name)
            results = results.replace("\r\n", "\n").splitlines()
            if not len(results):
                return None, None
            is_have_found_window = False
            profile_data_line = 0
            for line in results:
                if not is_have_found_window:
                    if "Window" in line and self.focus_window in line:
                        is_have_found_window = True
                if not is_have_found_window:
                    continue
                if "PROFILEDATA" in line:
                    profile_data_line += 1
                fields = line.split(",")
                if fields and '0' == fields[0]:
                    # 获取INTENDED_VSYNC VSYNC FRAME_COMPLETED时间 利用VSYNC计算fps jank
                    timestamp = [int(fields[1]), int(fields[2]), int(fields[13])]
                    if timestamp[1] == pending_fence_timestamp:
                        continue
                    timestamp = [_timestamp / nanoseconds_per_second for _timestamp in timestamp]
                    timestamps.append(timestamp)
                if 2 == profile_data_line:
                    break
        else:
            results = self.device.adb.run_adb_shell_cmd('dumpsys SurfaceFlinger --latency %s' % self.focus_window)
            results = results.replace("\r\n", "\n").splitlines()
            logger.debug("dumpsys SurfaceFlinger --latency result:")
            logger.debug(results)
            if not len(results):
                return None, None
            if not results[0].isdigit():
                return None, None
            try:
                refresh_period = int(results[0]) / nanoseconds_per_second
            except Exception as e:
                logger.exception(e)
                return None, None

            for line in results[1:]:
                fields = line.split()
                if len(fields) != 3:
                    continue
                timestamp = [int(fields[0]), int(fields[1]), int(fields[2])]
                if timestamp[1] == pending_fence_timestamp:
                    continue
                timestamp = [_timestamp / nanoseconds_per_second for _timestamp in timestamp]
                timestamps.append(timestamp)
        return refresh_period, timestamps

    def _get_surface_stats_legacy(self):
        timestamp = datetime.datetime.now()
        # 命令需要root
        ret = self.device.adb.run_adb_shell_cmd("service call SurfaceFlinger 1013")
        if not ret:
            return None
        match = re.search('^Result: Parcel\((\w+)', ret)
        if match:
            cur_surface = int(match.group(1), 16)
            return {'page_flip_count': cur_surface, 'timestamp': timestamp}
        return None


class FPSMonitor:

    def __init__(self, device_id, package, temp_data, frequency=5.0, timeout=24 * 60 * 60, jank_threshold=166,
                 use_legacy=False):
        self.use_legacy = use_legacy
        self.frequency = frequency  # 取样频率
        self.jank_threshold = jank_threshold
        self.device = AdbUtils(device_id)
        self.timeout = timeout
        if not package:
            package = self.device.adb.get_current_package()
        self.package = package
        self.temp_data = temp_data
        self.fps_collector = SurfaceStatsCollector(self.device, self.frequency, package, temp_data,
                                                   self.jank_threshold, self.use_legacy)

    def start(self):
        """
        启动FPSMonitor日志监控器
        :return:
        """
        self.fps_collector.start()
        logger.debug('FPS monitor has start!')

    def stop(self):
        """
        结束FPSMonitor日志监控器
        :return:
        """
        self.fps_collector.stop()
        logger.debug('FPS monitor has stop!')


if __name__ == '__main__':
    from src.perf_test import TempData

    TempData.result_path = r'D:\pythoncode\AdbTool\results'
    monitor = FPSMonitor('', "", TempData)
    monitor.start()
    time.sleep(6000)
    monitor.stop()

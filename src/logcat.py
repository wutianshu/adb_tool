#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import csv
import time
import threading
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class Logcat:
    def __init__(self, device_id, package, temp_data, activity_time=True):
        self.package = package
        self.temp_data = temp_data
        self.device = AdbUtils(device_id)
        self.running = False
        if activity_time:
            self.activity_time = ActivityTime(temp_data)
        self.exception_log_list = []
        self.start_time = None
        self.temp_log_num = 0
        self.save_log_num = 0
        self.create_time = None
        self.logcat_method = []
        self.logcat_start = False
        self.log_buffer = None
        self._logcat_thread = None
        self.model = self.device.adb.get_devices_model()
        self.sver = self.device.adb.get_system_version()
        self.mac = self.device.adb.get_device_mac(symbol=False)
        self.v_code, self.ver = self.device.adb.get_package_version(package)

    def logcat(self, save_dir):
        """
        记录logcat日志
        :param save_dir:
        :param params:
        :return:
        """
        if not save_dir:
            save_dir = self.temp_data.result_path
        self.temp_log_num = 0
        self.save_log_num = 0
        self.create_time = None
        if not self.create_time:
            self.create_time = Utils.get_current_underline_time()
        logcat_file = os.path.join(save_dir, 'logcat_%s.log' % self.create_time)
        log_list = []
        no_log_num = 0
        while self.logcat_start:
            try:
                log = self.log_buffer.stdout.readline().strip()
                try:
                    log = log.decode('utf8', 'ignore')
                except Exception as e:
                    logger.debug('logcat error' + str(e))
                if log:
                    no_log_num = 0
                    log_list.append(log)
                    for method in self.logcat_method:
                        try:
                            method(log)
                        except Exception as e:
                            logger.error("logcat method error:" + str(e))

                    self.temp_log_num += 1
                    self.save_log_num += 1
                    if self.temp_log_num > 100:
                        self.temp_log_num = 0
                        self.save_log(logcat_file, log_list)
                        log_list = []
                    if self.save_log_num > 500000:
                        self.save_log_num = 0
                        self.create_time = Utils.get_current_underline_time()
                        logcat_file = os.path.join(save_dir, 'logcat_%s.log' % self.create_time)
                        self.save_log(logcat_file, log_list)
                        log_list = []
                else:
                    # 这里需要加入多设备时获取日志错误的判断
                    no_log_num += 1
                    if no_log_num > 100:
                        logger.info("logcat is none,restart logcat")
                        self.log_buffer = self.device.adb.run_adb_shell_cmd('logcat -v threadtime', sync=False)
            except Exception as e:
                logger.error("logcat stdout read error:" + str(e))
        if log_list:
            self.save_log(logcat_file, log_list)

    @staticmethod
    def save_log(logcat_file, log_list):
        with open(logcat_file, 'a+', encoding="utf-8") as f:
            for log in log_list:
                f.write(log + "\n")

    def start_logcat(self, save_path=None):
        """
        开始运行logcat
        :param save_path:
        :return:
        """
        if hasattr(self, 'logcat_start') and self.logcat_start is True:
            logger.warning('logcat process have started,not need start')
            return
        try:
            self.device.adb.run_adb_shell_cmd('logcat -c ')
        except RuntimeError as e:
            logger.debug(e)
        self.logcat_start = True
        self.log_buffer = self.device.adb.run_adb_shell_cmd('logcat -v threadtime', sync=False)
        self._logcat_thread = threading.Thread(target=self.logcat, args=(save_path,))
        self._logcat_thread.setDaemon(True)
        self._logcat_thread.start()

    def stop_logcat(self):
        """
        停止logcat
        :return:
        """
        self.logcat_start = False
        logger.debug("stop logcat")
        if self.log_buffer is not None:
            if self.log_buffer.poll() is None:
                self.log_buffer.terminate()

    def start(self):
        """
        启动logcat日志监控器
        :return:
        """
        self.add_log_handle(self.activity_time.handle_activity_time)
        logger.debug("logcat monitor start...")
        if not self.running:
            self.start_logcat()
            time.sleep(1)
            self.running = True

    def stop(self):
        """
        结束logcat日志监控器
        :return:
        """
        logger.debug("logcat monitor: stop...")
        self.remove_log_handle(self.activity_time.handle_activity_time)
        logger.debug("logcat monitor: stopped")
        if self.exception_log_list:
            self.remove_log_handle(self.handle_exception)
        self.stop_logcat()
        self.running = False

    def set_exception_list(self, exception_log_list):
        self.exception_log_list = exception_log_list

    def add_log_handle(self, handle):
        """
        添加实时日志处理器，每产生一条日志，就调用一次handle
        :param handle:
        :return:
        """
        self.logcat_method.append(handle)

    def remove_log_handle(self, handle):
        """
        删除实时日志处理器
        :param handle:
        :return:
        """
        self.logcat_method.remove(handle)

    def handle_exception(self, log_line):
        """
        有log时回调
        :param log_line:
        :return:
        """
        tmp_file = os.path.join(self.temp_data.result_path, 'error.log')
        try:
            _, _, pid, _, level = log_line.split()[:5]
            for tag in self.exception_log_list:
                if tag and tag in log_line:
                    if 'NullPointerException' in tag:
                        # pid无法使用
                        log_list = log_line.split()
                        log_level = log_list[4]
                        if log_level != 'E':
                            continue
                    logger.debug("exception Info: " + log_line)
                    with open(tmp_file, 'a+', encoding="utf-8") as f:
                        f.write(log_line + '\n')
                    if tag.lower().find('anr') != -1:
                        traces_name = 'traces_%s.txt' % Utils.get_current_underline_time()
                        save_path = os.path.join(self.temp_data.result_path, traces_name)
                        self.device.adb.pull_file('/data/anr/traces.txt', save_path)
        except ValueError:
            logger.debug('log pid level get error:%s' % log_line)

    def handle_ueec_report(self, log_line):
        collection_time = time.time()
        ueec_file = os.path.join(self.temp_data.result_path, 'ueec.csv')
        if not os.path.exists(ueec_file):
            try:
                ueec_title = (
                    "datetime", "ueecCode", "pageName", "endType", "waitDuration", "duration", "average", "needReport")
                with open(ueec_file, 'a+') as ueec:
                    csv.writer(ueec, lineterminator='\n').writerow(ueec_title)
            except RuntimeError as e:
                logger.error(f'handle ueec report file open error:{e}')

        try:
            if log_line.find('UeecReporterImpl') == -1:
                return
            # no need Report:500301,pageName:IX, endType:3,diffTime:3, waitDur:5
            re_com = re.compile(r'(\d+),\s?pageName:(\w*?),\s?endType:(\d+),\s?diffTime:(\d+),\s?waitDur:(\d+)')
            match = re_com.search(log_line)
            if match:
                ueec_code = match.group(1)
                page_name = match.group(2)
                end_type = match.group(3)
                duration = match.group(4)
                wait_duration = match.group(5)
                need_report = 0
                average = '=ROUND(SUBTOTAL(1, F2:F99999),0)'
                if log_line.find('no need Report') == -1:
                    need_report = 1
                current_time = Utils.get_format_time(collection_time)
                ueec_list = [current_time, ueec_code, page_name, end_type, wait_duration,
                             duration, average, need_report]
                query = "INSERT INTO ueec (model,sver,mac,ver,v_code,package,code,page,duration,report,datetime) " \
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                data = self.model, self.sver, self.mac, self.ver, self.v_code, self.package, ueec_code, page_name, \
                    duration, need_report, current_time
                Utils.insert_data(query, data)
                with open(ueec_file, 'a+', encoding="utf-8") as ueec_writer:
                    writer_p = csv.writer(ueec_writer, lineterminator='\n')
                    writer_p.writerow(ueec_list)
        except ValueError:
            logger.debug('ueec report log error:%s' % log_line)

    def handle_step_report(self, log_line):
        collection_time = time.time()
        step_file = os.path.join(self.temp_data.result_path, 'step.csv')
        if not os.path.exists(step_file):
            try:
                step_title = "datetime", "step0", "step1", "step2", "step3", "step4", "step5", "step6", "step7"
                with open(step_file, 'a+') as step:
                    csv.writer(step, lineterminator='\n').writerow(step_title)
            except RuntimeError as e:
                logger.error(f'handle ueec report file open error:{e}')

        try:
            if log_line.find('allStep') == -1:
                return
            # allStep:step=0-0-3001,1-0-644,2-0-340,3-0-331,6-0-1,7-0-1663,time1:3001,time2:0
            step_list = re.findall(r'(\d)-\d-(\d+)', log_line)

            if len(step_list) == 0:
                return

            value_list = [''] * 8
            for num, value in step_list:
                value_list[int(num)] = int(value)

            current_time = Utils.get_format_time(collection_time)
            data = [self.model, self.sver, self.mac, self.ver, self.v_code, self.package, current_time] + value_list
            query = f"INSERT INTO step (model,sver,mac,ver,v_code, package,datetime,step0,step1,step2,step3,step4," \
                    f"step5,step6,step7) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            Utils.insert_data(query, data)
            with open(step_file, 'a+', encoding="utf-8") as step_writer:
                writer_p = csv.writer(step_writer, lineterminator='\n')
                writer_p.writerow([current_time] + value_list)
        except ValueError:
            logger.debug('step report log error:%s' % log_line)

    def handle_page_measure(self, log_line):
        page_file = os.path.join(self.temp_data.result_path, 'page.csv')
        if not os.path.exists(page_file):
            try:
                page_title = "datetime", "name", "jump", "first", "final", "total"
                with open(page_file, 'a+') as step:
                    csv.writer(step, lineterminator='\n').writerow(page_title)
            except RuntimeError as e:
                logger.error(f'handle page measure file open error:{e}')

        try:
            if log_line.find('PageMeasure') == -1:
                return
            # PageMeasure: OttPersonalAgreementAggregateActivity jump:50ms draw first:245ms draw final:245ms total:295ms
            re_com = re.compile(r': (\w+) jump:(\d+)ms draw first:(\d+)ms draw final:(\d+)ms total:(\d+)')
            search = re_com.search(log_line)
            if not search:
                return

            name, jump, first, final, total = search.groups()

            current_time = Utils.get_format_time(time.time())
            data = [self.model, self.sver, self.mac, self.ver, self.v_code, self.package, current_time, name, jump,
                    first, final, total]
            query = f"INSERT INTO page (model,sver,mac,ver,v_code, package,datetime,name,jump,first,final,total) " \
                    f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            Utils.insert_data(query, data)
            with open(page_file, 'a+', encoding="utf-8") as step_writer:
                writer_p = csv.writer(step_writer, lineterminator='\n')
                writer_p.writerow([current_time, name, jump, first, final, total])
        except ValueError:
            logger.debug('page measure log error:%s' % log_line)


class ActivityTime:
    def __init__(self, temp_data):
        self.temp_data = temp_data
        self.method_list = ['onCreate', 'onResume', 'onStart', 'onPause', 'onStop', 'onDestroy']
        self.data_list = []
        self.start()

    def handle_activity_time(self, log_line):
        re_compile = re.compile(r'(\w+) (\w+) time = (\d+)').search(log_line)
        if re_compile:
            timestamp = Utils.get_format_time(time.time())
            activity = re_compile.group(1)
            method = re_compile.group(2)
            time_num = re_compile.group(3)
            if method in self.method_list:
                self.data_list.append(dict(activity=activity, method=method, time_num=time_num, timestamp=timestamp))

    def _update_activity_list(self):
        file_path = os.path.join(self.temp_data.result_path, 'lifetime.csv')
        activity_time_title = ["datetime", "activity", "method", "time", 'time_interval']
        with open(file_path, 'a+', encoding="utf-8") as df:
            csv.writer(df, lineterminator='\n').writerow(activity_time_title)

        last_activity = last_method = last_time = None
        while True:
            during = None
            line_write_list = []
            if len(self.data_list) == 0:
                time.sleep(0.5)
                continue
            activity_info = self.data_list.pop(0)
            activity = activity_info.get('activity')
            current_time = activity_info.get('time_num')
            method = activity_info.get('method')
            if last_time is not None and activity == last_activity:
                if last_method == 'onCreate' and method == 'onStart':
                    during = int(current_time) - int(last_time)
                elif last_method == 'onStart' and method == 'onResume':
                    during = int(current_time) - int(last_time)
            last_activity = activity
            last_method = method
            last_time = current_time
            line_write_list.append(activity_info.get('timestamp'))
            line_write_list.append(activity_info.get('activity'))
            line_write_list.append(method)
            line_write_list.append(current_time)
            line_write_list.append(during)
            with open(file_path, "a+", encoding="utf-8") as f:
                csv_writer = csv.writer(f, lineterminator='\n')
                csv_writer.writerow(line_write_list)

    def start(self):
        activity_time_thread = threading.Thread(target=self._update_activity_list, daemon=True)
        activity_time_thread.start()


if __name__ == '__main__':
    l = Logcat('MAX0019111000244', 'com.mgtv.tv', '1')
    l.handle_page_measure(
        '10-26 11:24:45.880 16354 16354 I PageMeasure: VideoWebActivity jump:0ms draw first:466ms draw final:466ms total:466ms')

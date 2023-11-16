#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time
import config
import threading
from src.log import logger
from src.utils import Utils
from src.adbutils import AdbUtils


class Monkey:
    def __init__(self, device_id, package, temp_data, interval=5, timeout=888888888):
        self.package = package
        self.temp_data = temp_data
        self.interval = interval
        self.pct_per = config.monkey_cmd
        self.device = AdbUtils(device_id)
        self.running = False
        self.timeout = timeout
        self._stop_event = threading.Event()
        self._monkey_thread = None
        self.monkey_cmd = None
        self._log_process = None

    def start_monkey_thread(self, package, pct_per):
        """
        monkey启动线程，启动前先关闭运行的monkey进程
        :param package:包名
        :param pct_per: monkey执行命令
        :return:
        """
        if self.running is True and self.device.adb.is_process_running("com.android.commands.monkey") is True:
            logger.debug(u'monkey process have started,kill monkey')
            self.device.adb.kill_process("com.android.commands.monkey")
        self.monkey_cmd = 'monkey -p %s -v -v -v --ignore-crashes --ignore-timeouts ' \
                          '--ignore-security-exceptions --kill-process-after-error %s  99999999' % (
                              package, pct_per)
        self._monkey_thread = threading.Thread(target=self._monkey_check,
                                               args=[self.temp_data.result_path])
        self._monkey_thread.setDaemon(True)
        self._monkey_thread.start()

    def stop_monkey(self):
        """
        停止monkey方法
        :return:
        """
        self.running = False
        logger.debug("stop monkey")
        self.device.adb.kill_process("com.android.commands.monkey")
        if self._log_process is not None:
            if self._log_process.poll() is None:
                self._log_process.terminate()

    def _monkey_log(self, save_dir):
        """
        monkey日志获取方法
        :param save_dir:日志保存路径
        :return:
        """
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
        self.cache_log_num = 0
        self.file_log_num = 0
        self.start_time = None
        no_log_times = 0
        logs = []
        while self.running:
            try:
                try:
                    log = self._log_process.stdout.readline().strip()
                except Exception as e:
                    logger.warning('monkey thread error:%s' % e)
                    log = ''

                if not isinstance(log, str):
                    try:
                        log = str(log, "utf8")
                    except Exception as e:
                        logger.error('monkey log encode error: ' + log)
                        logger.error('_monkey_log error: ' + str(e))
                if log:
                    time_stamp = Utils.get_current_ms_time()
                    logs.append(time_stamp + '\t' + log)
                    self.cache_log_num = self.cache_log_num + 1
                    self.file_log_num = self.file_log_num + 1
                    if self.cache_log_num > 100:
                        if not self.start_time:
                            self.start_time = Utils.get_current_underline_time()
                        log_file = os.path.join(save_dir,
                                                'monkey_%s.log' % self.start_time)
                        self.cache_log_num = 0
                        self.device.adb.run_adb_shell_cmd("input keyevent 25")
                        self.save(log_file, logs)
                        logs = []
                    if self.file_log_num > 600000:
                        self.file_log_num = 0
                        self.start_time = Utils.get_current_underline_time()
                        log_file = os.path.join(save_dir, 'monkey_%s.log' % self.start_time)
                        self.save(log_file, logs)
                        logs = []
                else:
                    no_log_times = no_log_times + 1
                    if no_log_times % 1000 == 0:
                        logger.warning("monkey log is none,restart monkey,device:%s" % self.device.adb.device_id)
                        if not self.device.adb.is_process_running("com.android.commands.monkey") and self.running:
                            self.device.adb.kill_process("com.android.commands.monkey")
                            self._log_process = self.device.adb.run_adb_shell_cmd(self.monkey_cmd, sync=False)
            except Exception as e:
                logger.error("_monkey_log error" + str(e))

    def _monkey_check(self, save_dir):
        """
        monkey运行检测方法，
        _monkey_log运行时stdout.readline会出现阻塞，导致monkey关闭后无法自动启动
        :param save_dir:日志保存路径
        :return:
        """
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
        self.start_time = None
        no_run_times = 0
        log_size = 0
        self.start_time = Utils.get_current_underline_time()
        log_file = os.path.join(save_dir, 'monkey_%s.log' % self.start_time)
        while self.running:
            try:
                if self.temp_data.fd_num > 700:
                    logger.error('fd num > 700, kill process com.android.commands.monkey')
                    self.device.adb.kill_process("com.android.commands.monkey")
                    break
                ret = self.device.adb.is_process_running("com.android.commands.monkey")
                time.sleep(1)
                if ret and no_run_times < 6:
                    time.sleep(30)
                    file_size = Utils.get_file_size(log_file, False)
                    # monkey进程一直存在，但不执行测试动作，通过日志判断是否需要重启
                    if file_size == log_size:
                        logger.info(f'The file size has not changed,file size:{file_size},file:{log_file}')
                        no_run_times = no_run_times + 1
                    log_size = file_size

                    if file_size > 80 * 1024 * 1024:
                        self.start_time = Utils.get_current_underline_time()
                        log_file = os.path.join(save_dir, 'monkey_%s.log' % self.start_time)
                        self.device.adb.kill_process("com.android.commands.monkey")
                else:
                    no_run_times += 1
                    if no_run_times > 5:
                        logger.warning("monkey is not running,restart monkey,device:%s" % self.device.adb.device_id)
                        if self.running:
                            self.start_time = Utils.get_current_underline_time()
                            log_file = os.path.join(save_dir, 'monkey_%s.log' % self.start_time)
                            cmd = self.monkey_cmd + ' > ' + log_file
                            self.device.adb.kill_process("com.android.commands.monkey")
                            self._log_process = self.device.adb.run_adb_shell_cmd(cmd, sync=False)
                            time.sleep(30)
                            if os.path.exists(log_file) and Utils.get_file_size(log_file) == 0:
                                os.remove(log_file)
                            no_run_times = 0
                    time.sleep(5)
            except Exception as e:
                logger.error("_monkey_log error" + str(e))

    @staticmethod
    def save(save_file_path, log_list):
        """
        日志保存方法，批量保存缓存的日志
        :param save_file_path: 日志文件保存路径
        :param log_list: 缓存日志列表
        :return:
        """
        monkey_file = os.path.join(save_file_path)
        with open(monkey_file, 'a+', encoding="utf-8") as f:
            for log in log_list:
                f.write(log + "\n")

    def start(self):
        """
        monkey启动方法
        :return:
        """
        if not self.running:
            self.running = True
            self.start_monkey_thread(self.package, self.pct_per)
        logger.debug("Monkey has started...")

    def stop(self):
        """
        monkey停止方法
        :return:
        """
        self.stop_monkey()
        logger.debug("Monkey has stopped...")


if __name__ == "__main__":
    from src.perf_test import TempData

    config.monkey_cmd = '--pct-majornav 45 --pct-nav 35 --pct-syskeys 5 --pct-motion 5 --pct-appswitch 10 --throttle 2000 -s 1000'
    TempData.result_path = r'D:\pythoncode\AdbTool\results'
    monkey = Monkey('MAX0019071000091', "com.mgtv.tv", TempData)
    monkey.start()
    time.sleep(12000)
    monkey.stop()

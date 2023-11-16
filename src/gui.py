#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import re
import shutil
import subprocess
import threading
import tkinter.filedialog
import tkinter.font
import tkinter.simpledialog
from tkinter import *
from tkinter import ttk
from tkinter.messagebox import askokcancel
from tkinter.scrolledtext import ScrolledText
from tkinter.simpledialog import askstring

import psutil
import requests
import time

import config
from src.adbopen import AdbOpen
from src.adbutils import AdbUtils
from src.log import gui_logger, gui_handler
from src.log import logger
from src.logcat import Logcat
from src.mini_cap import MiniCap, KeyMap
from src.perf_test import main, TempData
from src.proxy import HttpProxy
from src.utils import Utils


class Gui:
    def __init__(self):
        self.android = AdbUtils()
        self.adb_open = AdbOpen()
        self.minicap = MiniCap(self.android)
        self.save_path = self.save_result_path()
        self.root = Tk()
        self.root.title("adb tool")
        # self.root.geometry('572x580')
        self.text = Text(self.root)
        self.title_label = None
        self.device_list = None
        self.record_process = None
        self.logcat = Logcat(None, None, None, None)
        self.logcat_process = self.dump_process = None
        self.os_platform = Utils.get_os_platform()
        self.root.iconbitmap(self.icon_path)
        self.restart_font = tkinter.font.Font(family="Times", size=20, weight="bold", slant="roman", underline=0)
        self.common_font = tkinter.font.Font(family="Times", size=10, weight="normal", slant="roman", underline=0)
        self.monkey_var = StringVar()
        self.cpu_var = IntVar()
        self.mem_var = IntVar()
        self.thr_var = IntVar()
        self.fd_var = IntVar()
        self.fps_var = IntVar()
        self._perf_thread = None

    @staticmethod
    def save_result_path():
        """
        文件保存方法
        :return:
        """
        result_path = os.path.join(config.root_path, 'results')
        if not os.path.isdir(result_path):
            os.mkdir(result_path)
        return result_path

    @property
    def icon_path(self):
        if self.os_platform == 'Windows':
            path = os.path.join(config.root_path, 'tools', 'favicon.ico')
        else:
            path = os.path.join(config.root_path, 'tools', 'favicon.icns')
        return path

    def creat_menu(self):
        """
        adb测试工具菜单栏生成方法
        :return:
        """
        menubar = Menu(self.root, tearoff=False)
        perf_menu = Menu(menubar, tearoff=False)
        perf_menu.add_command(label='指定设备', command=lambda: self.perf_start(True))
        perf_menu.add_command(label='全部设备', command=self.perf_start)
        perf_menu.add_command(label='查看日志', command=self.log_display)
        perf_menu.add_command(label='生成报告', command=self.remake_report)
        perf_menu.add_command(label='停止测试', command=self.perf_stop)
        menubar.add_cascade(label='性能测试', menu=perf_menu)

        key_menu = Menu(menubar, tearoff=False)
        key_menu.add_command(label='首页', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 3'))
        key_menu.add_command(label='菜单', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 82'))
        key_menu.add_command(label='设置', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 176'))
        key_menu.add_command(label='向上', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 19'))
        key_menu.add_command(label='向下', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 20'))
        key_menu.add_command(label='向左', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 21'))
        key_menu.add_command(label='向右', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 22'))
        key_menu.add_command(label='确认', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 23'))
        key_menu.add_command(label='返回', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 4'))
        key_menu.add_command(label='暂停', command=lambda: self.android.adb.run_adb_shell_cmd('input keyevent 85'))
        key_menu.add_command(label='其它', command=self.key_event)
        menubar.add_cascade(label='常用按键', menu=key_menu)

        device_menu = Menu(menubar, tearoff=False)
        device_menu.add_command(label='系统版本', command=self.build_release)
        device_menu.add_command(label='系统SDK', command=self.build_sdk)
        device_menu.add_command(label='设备MAC', command=self.device_mac)
        device_menu.add_command(label='设备厂家', command=self.device_product)
        device_menu.add_command(label='设备型号', command=self.device_model)
        device_menu.add_command(label='设备序列', command=self.serial_no)
        menubar.add_cascade(label='设备信息', menu=device_menu)

        operation_menu = Menu(menubar, tearoff=False)
        operation_menu.add_command(label='输入文字', command=self.input_text)
        operation_menu.add_command(label='执行命令', command=self.run_cmd)
        operation_menu.add_command(label='拉取文件', command=self.file_pull)
        operation_menu.add_command(label='推送文件', command=self.file_push)
        operation_menu.add_command(label='ping测试', command=self.ping_test)
        operation_menu.add_command(label='添加host', command=self.add_host)
        operation_menu.add_command(label='查看TOP', command=self.top_cpu)
        menubar.add_cascade(label='设备操作', menu=operation_menu)

        apk_menu = Menu(menubar, tearoff=False)
        apk_menu.add_command(label='查包信息', command=self.package_info)
        apk_menu.add_command(label='查包路径', command=self.package_path)
        apk_menu.add_command(label='查包日期', command=self.package_version_code)
        apk_menu.add_command(label='查包内存', command=self.dump_meminfo)
        apk_menu.add_command(label='查包进程', command=self.process_info)
        apk_menu.add_command(label='查包线程', command=self.process_task)
        apk_menu.add_command(label='文件描述', command=self.file_describe)
        apk_menu.add_command(label='导出内存', command=self.dump_heap)
        menubar.add_cascade(label='APK操作', menu=apk_menu)

        batch_menu = Menu(menubar, tearoff=False)
        batch_menu.add_command(label='批量安装', command=self.batch_install)
        batch_menu.add_command(label='批量卸载', command=self.batch_uninstall)
        batch_menu.add_command(label='批量重启', command=self.batch_reboot)
        batch_menu.add_command(label='批量按键', command=self.batch_kev_event)
        menubar.add_cascade(label='批量操作', menu=batch_menu)

        apk_menu = Menu(menubar, tearoff=False)

        apk_menu_1 = tkinter.Menu(menubar, tearoff=False)
        apk_menu_1.add_command(label='发布版本', command=lambda: self.apk_switch('dx'))
        apk_menu_1.add_command(label='预发布版本', command=lambda: self.apk_switch('dx', 'pre_release'))
        apk_menu.add_cascade(label='电信', menu=apk_menu_1)

        apk_menu_1 = tkinter.Menu(menubar, tearoff=False)
        apk_menu_1.add_command(label='发布版本', command=lambda: self.apk_switch('yd_iptv'))
        apk_menu_1.add_command(label='预发布版本', command=lambda: self.apk_switch('yd_iptv', 'pre_release'))
        apk_menu.add_cascade(label='移动IPTV', menu=apk_menu_1)

        apk_menu_1 = tkinter.Menu(menubar, tearoff=False)
        apk_menu_1.add_command(label='发布版本', command=lambda: self.apk_switch('yd_ott'))
        apk_menu_1.add_command(label='预发布版本', command=lambda: self.apk_switch('yd_ott', 'pre_release'))
        apk_menu.add_cascade(label='移动OTT', menu=apk_menu_1)

        apk_menu_1 = tkinter.Menu(menubar, tearoff=False)
        apk_menu_1.add_command(label='发布版本', command=lambda: self.apk_switch('lt'))
        apk_menu_1.add_command(label='预发布版本', command=lambda: self.apk_switch('lt', 'pre_release'))
        apk_menu.add_cascade(label='联通', menu=apk_menu_1)

        menubar.add_cascade(label='版本切换', menu=apk_menu)

        self.root.config(menu=menubar)

    @staticmethod
    def thread_run(func, *args):
        t = threading.Thread(target=func, args=args)
        t.setDaemon(True)
        t.start()

    def perf_start(self, single=False):
        """
        性能测试方法，指定设备或全部设备执行性能测试
        :param single: bool指定设备或全部设备通过此参数控制
        :return:
        """
        TempData.terminate_signal.clear()
        top_level = Toplevel()
        top_level.title("配置参数")
        top_level.iconbitmap(self.icon_path)

        device_id_var = tkinter.StringVar()
        device_list = self.android.adb.get_online_device()
        if single is True:
            Label(top_level, text="选择设备", font=self.common_font, width=12).grid(row=0, column=0, pady=6, sticky=W)
            ttk.Combobox(top_level, textvariable=device_id_var, value=device_list, width=48).grid(row=0, column=1,
                                                                                                  columnspan=2, pady=6,
                                                                                                  sticky=W)
        else:
            device_id_var.set('')

        Label(top_level, text="测试包名", font=self.common_font, width=12).grid(row=1, column=0, pady=6, sticky=W)
        package_var = StringVar()
        package = self.android.adb.get_current_package()
        package_var.set(package)
        Entry(top_level, textvariable=package_var, width=48).grid(row=1, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="测试方法", font=self.common_font, width=12).grid(row=2, column=0, pady=6, sticky=W)
        frame = Frame(top_level, width=48)
        frame.grid(row=2, column=1, sticky=W)
        self.monkey_var.set(config.monkey)
        Radiobutton(frame, variable=self.monkey_var, text='adb', value='adb', width=7). \
            grid(row=0, column=0, pady=6, sticky=W)
        Radiobutton(frame, variable=self.monkey_var, text='monkey', value='monkey', width=7). \
            grid(row=0, column=1, pady=6, sticky=W)
        Radiobutton(frame, variable=self.monkey_var, text='无', value='None', width=7). \
            grid(row=0, column=2, pady=6, sticky=W)

        Label(top_level, text="测试参数", font=self.common_font, width=12).grid(row=3, column=0, pady=6, sticky=W)
        monkey_cmd_var = StringVar()
        monkey_cmd_var.set(config.monkey_cmd)
        combobox = ttk.Combobox(top_level, textvariable=monkey_cmd_var, width=48)
        cmd_list = ['3',
                    '--pct-majornav 45 --pct-nav 35 --pct-syskeys 5 --pct-motion 5 --pct-appswitch 10 --throttle 2000 -s 1000',
                    '--pct-touch 90 --pct-appswitch 10 --throttle 2000 -s 1000', ]
        combobox['value'] = cmd_list
        combobox.grid(row=3, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="执行时间/时", font=self.common_font, width=12).grid(row=4, column=0, pady=6, sticky=W)
        timeout_var = IntVar()
        timeout_var.set(config.timeout)
        Entry(top_level, textvariable=timeout_var, width=48).grid(row=4, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="采集频率/秒", font=self.common_font, width=12).grid(row=5, column=0, pady=6, sticky=W)
        frequency_var = IntVar()
        frequency_var.set(config.frequency)
        Entry(top_level, textvariable=frequency_var, width=48).grid(row=5, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="错误日志", font=self.common_font, width=12).grid(row=6, column=0, pady=6, sticky=W)
        error_log_var = StringVar()
        error_log_var.set(','.join(config.error_log))
        Entry(top_level, textvariable=error_log_var, width=48).grid(row=6, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="导出文件", font=self.common_font, width=12).grid(row=7, column=0, pady=6, sticky=W)
        log_path_var = StringVar()
        log_path_var.set(','.join(config.devices_log_path))
        Entry(top_level, textvariable=log_path_var, width=48).grid(row=7, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="打洞命令", font=self.common_font, width=12).grid(row=8, column=0, pady=6, sticky=W)
        main_activity_var = StringVar()
        main_activity_var.set(','.join(config.main_activity))
        Entry(top_level, textvariable=main_activity_var, width=48).grid(row=8, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="测试activity", font=self.common_font, width=12).grid(row=9, column=0, pady=6, sticky=W)
        activity_list_var = StringVar()
        activity_list_var.set(','.join(config.activity_list))
        Entry(top_level, textvariable=activity_list_var, width=48).grid(row=9, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="黑名单activity", font=self.common_font, width=12).grid(row=10, column=0, pady=6, sticky=W)
        black_list_var = StringVar()
        black_list_var.set(','.join(config.black_activity_list))
        Entry(top_level, textvariable=black_list_var, width=48).grid(row=10, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="黑名单退出键", font=self.common_font, width=12).grid(row=11, column=0, pady=6, sticky=W)
        black_key_var = IntVar()
        black_key_var.set(config.black_list_key)
        Entry(top_level, textvariable=black_key_var, width=48).grid(row=11, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="内存下载/时", font=self.common_font, width=12).grid(row=12, column=0, pady=6, sticky=W)
        dumpheap_var = IntVar()
        dumpheap_var.set(config.dumpheap_freq)
        Entry(top_level, textvariable=dumpheap_var, width=48).grid(row=12, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="收件人", font=self.common_font, width=12).grid(row=13, column=0, pady=6, sticky=W)
        mail_var = StringVar()
        mail_var.set(','.join(config.mail))
        Entry(top_level, textvariable=mail_var, width=48).grid(row=13, column=1, columnspan=2, pady=6, sticky=W)

        Label(top_level, text="采集内容", font=self.common_font, width=11).grid(row=14, column=0, pady=6, sticky=W)
        frame = Frame(top_level, width=40)
        frame.grid(row=14, column=1, sticky=W)

        self.cpu_var.set(config.cpu_var)
        self.mem_var.set(config.mem_var)
        self.thr_var.set(config.thr_var)
        self.fd_var.set(config.fd_var)
        self.fps_var.set(config.fps_var)
        Checkbutton(frame, text='CPU', variable=self.cpu_var).grid(row=14, column=1, pady=6, sticky=W)
        Checkbutton(frame, text='MEM', variable=self.mem_var).grid(row=14, column=2, pady=6, sticky=W)
        Checkbutton(frame, text='THR', variable=self.thr_var).grid(row=14, column=3, pady=6, sticky=W)
        Checkbutton(frame, text='FD', variable=self.fd_var).grid(row=14, column=4, pady=6, sticky=W)
        Checkbutton(frame, text='FPS', variable=self.fps_var).grid(row=14, column=5, pady=6, sticky=W)

        def ok_button():
            """
            确定按钮，检查参数是否合法，合法后开始进行性能测试
            :return:
            """
            if self._perf_thread is None:
                try:
                    config.task_stop = False
                    config.devices = device_id_var.get()
                    if single is True and not config.devices:
                        err_msg.config(text='请选择想要测试的设备')
                        return
                    config.package = package_var.get()
                    config.monkey = self.monkey_var.get()
                    config.monkey_cmd = monkey_cmd_var.get()
                    config.timeout = timeout_var.get()
                    config.frequency = frequency_var.get()
                    error_log = error_log_var.get()
                    config.error_log = error_log.split(',') if error_log else []
                    if config.monkey == 'monkey' and (
                            config.monkey_cmd == '' or cmd_list.index(config.monkey_cmd) == 0):
                        err_msg.config(text='monkey参数配置错误')
                        return
                    log_path = log_path_var.get()
                    config.devices_log_path = log_path.split(',') if log_path else []
                    main_activity = main_activity_var.get()
                    config.main_activity = main_activity.split(',') if main_activity else []
                    activity_list = activity_list_var.get()
                    config.activity_list = activity_list.split(',') if activity_list else []
                    black_list = black_list_var.get()
                    config.black_activity_list = black_list.split(',') if black_list else []
                    config.black_list_key = black_key_var.get()
                    config.dumpheap_freq = dumpheap_var.get()
                    config.mail = mail_var.get().split(',')
                    config.cpu_var = self.cpu_var.get()
                    config.mem_var = self.mem_var.get()
                    config.thr_var = self.thr_var.get()
                    config.fd_var = self.fd_var.get()
                    config.fps_var = self.fps_var.get()
                    self._perf_thread = threading.Thread(target=main, daemon=True)
                    self._perf_thread.start()
                    top_level.destroy()
                except Exception as e:
                    err_msg.config(text=str(e))
            elif self._perf_thread.is_alive() is True:
                err_msg.config(text='已有执行中的任务')
            else:
                self._perf_thread = None
                ok_button()

        err_msg = Label(top_level, text='', pady=6, fg='red', width=48, height=1)
        err_msg.grid(row=15, column=0, columnspan=2, sticky=W)

        frame = Frame(top_level, width=12)
        frame.grid(row=15, column=2, sticky=E)
        Button(frame, text="确定", command=ok_button).grid(row=15, column=0, pady=6)
        Button(frame, text="取消", command=top_level.destroy).grid(row=15, column=1, pady=6, sticky=E)

    def perf_stop(self):
        """
        性能测试停止方法，用于手动停止性能测试
        :return:
        """
        config.task_stop = True
        self._perf_thread = None

    def remake_report(self):
        """
        重新生成测试报告方法，用于测试程序异常中止未生成报告场景
        :return:
        """
        string = askstring(title='获取信息', prompt='请输入需要生成报告的路径：')
        if string is None:
            return
        elif string == '':
            self.text.insert('insert', '本地路径未输入，请重新输入\n')
        else:
            string = string.replace('"', '')
            if not os.path.exists(string):
                self.text.insert('insert', '本地路径错误\n')
                return
            try:
                config.report_path = string
                main()
                self.text.insert('insert', '测试报告已生成，报告路径： %s\n' % config.report_path)
            except Exception as e:
                self.text.insert('insert', '测试报告生成失败，原因： %s\n' % str(e))
            finally:
                config.report_path = None

    def log_display(self):
        """
        性能测试执行过程中查看性能参数日志输出
        :return:
        """

        def close_window():
            gui_logger.removeHandler(gui_handler)
            config.log_text = None
            top_level.destroy()

        gui_logger.addHandler(gui_handler)
        top_level = Toplevel()
        top_level.iconbitmap(self.icon_path)
        top_level.bind('Esc', lambda e: top_level.destroy())
        top_level.protocol('WM_DELETE_WINDOW', close_window)
        top_level.title("日志输出")
        text = ScrolledText(top_level, height=50, width=100)
        text.grid(row=1, column=1)
        config.log_text = text

    def key_event(self):
        """
        按键模拟方法，input keyevent xx模拟遥控器按键
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', '使用场景：遥控器按键缺失或远程执行操作等场景\n')
        string = '\n遥控器按键编码：\nHome键：3\t\t菜单键：82\t\t设置键：176\t\t确认键：23\t\t返回键：4\n' \
                 '删除键：112\t\t向上：19\t\t向下：20\t\t向左：21\t\t向右：22\n' \
                 '音量+：24\t\t音量-：25\t\t静音：164\t\t频道+：166\t\t频道-：167\n' \
                 '数字0：7\t\t数字1：8\t\t数字2：9\t\t数字3：10\t\t数字4：11\n' \
                 '数字5：12\t\t数字6：13\t\t数字7：14\t\t数字8：15\t\t数字9：16\n' \
                 '红键：183\t\t绿键：184\t\t黄键：185\t\t蓝键：186\t\t快进：90\n' \
                 '快退：89\t\t暂停键：85\t\t搜索键：84\t\t角色键：142\n'
        self.text.insert('insert', string)
        string = askstring(title='获取信息', prompt='请输入遥控器编码：', initialvalue="按键对应数字编码见下方")
        if string is None:
            return
        elif string == '':
            self.text.insert('insert', '遥控器编码未输入，请输入\n')
        else:
            re_compile = re.compile(r'\d+$').match(string)
            if re_compile:
                num = re_compile.group(0)
                self.text.insert('insert', 'adb shell input keyevent %s\n' % num)
                self.android.adb.run_adb_shell_cmd('input keyevent %s' % num)
            else:
                self.text.insert('insert', '遥控器编码输入错误，请输入整数编码\n')

    def build_release(self):
        """
        获取android版本
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell getprop ro.build.version.release\n')
        version = self.android.adb.get_system_version()
        self.text.insert('insert', version)

    def build_sdk(self):
        """
        获取android sdk版本
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell getprop ro.build.version.sdk\n')
        version = self.android.adb.get_sdk_version()
        self.text.insert('insert', version)

    def device_mac(self):
        """
        获取android设备的mac地址
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell cat /sys/class/net/eth0/address\n')
        mac = self.android.adb.get_device_mac()
        self.text.insert('insert', mac)

    def device_product(self):
        """
        获取android设备的厂家信息
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell getprop ro.product.manufacturer\n')
        product = self.android.adb.get_devices_product()
        self.text.insert('insert', product)

    def device_model(self):
        """
        获取android设备的型号
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell getprop ro.product.model\n')
        model = self.android.adb.get_devices_model()
        self.text.insert('insert', model)

    def serial_no(self):
        """
        获取android设备的串号
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell getprop ro.serialno\n')
        version = self.android.adb.get_device_serialno()
        self.text.insert('insert', version)

    def input_text(self):
        """
        文字输入方法，如IP地址，用户账号密码，提高输入速度
        :return:
        """
        self.text.delete('1.0', 'end')
        self.text.insert('insert', '使用场景：如配置静态IP、输入账号密码等\n')
        string = askstring(title='获取信息', prompt='请输入文字：')
        if string is None:
            return
        elif string == '':
            self.text.insert('insert', '文字未输入，请输入\n')
        else:
            self.text.insert('insert', 'adb shell input text %s\n' % string)
            self.android.adb.input_text(string)

    def run_cmd(self):
        """
        执行adb命令
        :return:
        """

        def run_cmd_thread(cmd):
            ret = self.android.adb.run_adb_cmd(cmd)
            self.text.insert('insert', str(ret) + '\n')

        self.text.delete('1.0', 'end')
        string = askstring(title='获取信息', prompt='请输入adb命令：')
        if string is None:
            return
        elif string == '':
            self.text.insert('insert', '命令未输入，请重新输入\n')
        else:
            string = string.replace('adb', '')
            self.text.insert('insert', 'adb %s\n' % string)
            self.thread_run(run_cmd_thread, string)

    def file_pull(self):
        """
        下载android设备上的文件
        :return:
        """

        def file_pull_thread(src_path):
            ret = self.android.adb.pull_file(src_path, self.save_path)
            self.text.insert('insert', '\n' + str(ret) + '\n')

        self.text.delete('1.0', 'end')
        string = askstring(title='获取信息', prompt='请输入需要Pull的设备文件路径：',
                           initialvalue='示例：/system/build.prop')
        if string is None:
            return
        elif string == '':
            self.text.insert('insert', '文件路径未输入，请重新输入\n')
        else:
            self.text.insert('insert', 'adb pull %s %s\n' % (string, self.save_path))
            self.thread_run(file_pull_thread, string)

    def file_push(self):
        """
        将文件推送到android设备
        :return:
        """

        def file_push_thread(src, dst):
            try:
                ret = self.android.adb.push_file(src, dst)
                self.text.insert('insert', '\n' + str(ret) + '\n')
            except Exception as e:
                self.text.insert('insert', '\n' + str(e) + '\n')

        self.text.delete('1.0', 'end')
        src_path = tkinter.filedialog.askopenfilename()
        if not src_path:
            return
        string = askstring(title='获取信息', prompt='请输入Android设备的文件路径：',
                           initialvalue="示例：/data/local/tmp")
        if string is None:
            return
        elif string == '':
            self.text.insert('insert', '文件路径未输入，请重新输入\n')
        else:
            dst_path = string.strip()
            self.text.insert('insert', 'adb push %s %s\n' % (src_path, dst_path))
            self.thread_run(file_push_thread, *(src_path, dst_path))

    def add_host(self):
        self.text.delete('1.0', 'end')
        ret = self.android.adb.remount_dire()
        if ret is True:
            host = askstring(title='配置hosts', prompt='请输入需要添加的hosts，为空时清除全部hosts', initialvalue='')
            if not host:
                return
            cmd = f'"echo {host} > /etc/hosts"'
            self.android.adb.run_adb_shell_cmd(cmd)
            self.text.insert('insert', f'adb shell {cmd}')
        else:
            self.text.insert('insert', 'system目录挂载失败，无法添加host')

    def package_info(self):
        """
        获取apk信息方法
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            self.text.insert('insert', 'adb shell dumpsys package %s\n' % package)
            ret = self.android.adb.run_adb_shell_cmd('dumpsys package %s' % package)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def package_path(self):
        """
        获取apk安装路径方法
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            self.text.insert('insert', 'adb shell pm list package -f %s\n' % package)
            ret = self.android.adb.run_adb_shell_cmd('pm list package -f %s ' % package)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def package_version_code(self):
        """
        获取apk发布日期
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            cmd = f'dumpsys package {package}|grep version'
            self.text.insert('insert', f'{cmd}\n')
            ret = self.android.adb.run_adb_shell_cmd(cmd)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def dump_meminfo(self):
        """
        获取apk内存信息
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            self.text.insert('insert', 'adb shell dumpsys meminfo %s\n' % package)
            ret = self.android.adb.run_adb_shell_cmd('dumpsys meminfo %s' % package)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def process_info(self):
        """
        获取apk进程信息
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            self.text.insert('insert', 'adb shell ps|grep %s\n' % package)
            ret = self.android.adb.run_adb_shell_cmd('ps|grep %s' % package)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def process_task(self):
        """
        获取apk线程信息
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            pid = self.android.adb.get_pid_from_package(package)
            sdk = self.android.adb.get_sdk_version()
            if sdk > 27:
                cmd = f'ps -T {pid}'
            elif sdk == 27:
                cmd = f'busybox ps -T|grep {package}'
            else:
                cmd = f'ps -t {pid}'
            self.text.insert('insert', f'{cmd}\n')
            ret = self.android.adb.run_adb_shell_cmd(cmd)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def file_describe(self):
        """
        获取apk文件描述信息
        :return:
        """
        self.text.delete('1.0', 'end')
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        if package is None:
            return
        elif package == '':
            self.text.insert('insert', '包名未输入，请输入APK包名\n')
        elif self.is_app_package(package):
            pid = self.android.adb.get_pid_from_package(package)
            self.text.insert('insert', 'adb shell ls -l /proc/%s/fd\n' % pid)
            ret = self.android.adb.run_adb_shell_cmd('ls -l /proc/%s/fd' % pid)
            self.text.insert('insert', '%s\n' % ret)
        else:
            self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

    def title_info(self):
        """
        android设备device id显示方法
        :return:
        """
        device_list = self.android.list_local_devices()
        if device_list != self.device_list:
            if self.title_label:
                self.title_label.destroy()

            self.device_list = device_list
            radio_list = []
            for key, value in self.root.children.items():
                if isinstance(value, Radiobutton):
                    radio_list.append(value)
            [radio.destroy() for radio in radio_list]

            if len(self.device_list) > 0:
                self.android.adb.device_id = self.device_list[0]
                self.logcat.device.adb.device_id = self.device_list[0]
                product = self.android.adb.get_devices_product()
                model = self.android.adb.get_devices_model()
                if model not in config.root_disable:
                    self.android.adb.run_adb_cmd('root')
                label_text = '设备厂家：%s，设备型号：%s' % (product, model)
            else:
                label_text = '\n设备未连接或已下线\n'

            def call_radio_button():
                radio_no = int(v.get())
                self.android.adb.device_id = self.device_list[radio_no]
                self.logcat.device.adb.device_id = self.device_list[radio_no]
                new_product = self.android.adb.get_devices_product()
                new_model = self.android.adb.get_devices_model()
                if model not in config.root_disable:
                    self.android.adb.run_adb_cmd('root')
                self.title_label.config(text='设备厂家：%s，设备型号：%s' % (new_product, new_model))

            v = IntVar()
            v.set(0)
            i = 0
            for device in self.device_list:
                device_ip = device[:16] + '..'
                radio = Radiobutton(self.root, variable=v, text=device_ip, value=i, command=call_radio_button)
                radio.grid(row=0, column=i * 2, columnspan=2, sticky=W)
                i += 1
            self.title_label = Label(self.root, text=label_text, pady=6, font=self.common_font)
            self.title_label.grid(row=1, columnspan=8)
        self.root.after(5000, self.title_info)

    @staticmethod
    def is_app_package(package):
        """
        判断android设备是否安装apk
        :param package: 包名
        :return:
        """
        re_compile = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)+([.][a-zA-Z_][a-zA-Z0-9_]*)+$').match(package)
        if re_compile:
            return True
        return False

    def batch_install(self):
        def thread_install(string):
            if string is None:
                return
            elif string == '':
                self.text.insert('insert', 'APK包的本地路径或URL链接未输入，请重新输入\n')
            else:
                string = string.strip().replace('"', '')
                if not os.path.isfile(string):
                    if not re.match(r'^https?:/{2}\w.+$', string):
                        self.text.insert('insert', '输入的APK包的本地路径或URL链接错误\n')
                        return
                    string = self.download_pkg(string)
                    if not string:
                        return
                for device in self.device_list:
                    ret = AdbUtils(device).adb.install_apk(string)
                    if ret:
                        self.text.insert('insert', f'设备：{device} APK安装成功\n')
                    else:
                        self.text.insert('insert', f'设备：{device} APK安装失败装\n')

        self.text.delete('1.0', 'end')
        info = askstring(title='获取信息', prompt='请输入APK包的本地路径或URL链接：')
        self.thread_run(thread_install, info)

    def batch_uninstall(self):
        def app_uninstall_button(package):
            if package is None:
                return
            elif package == '':
                self.text.insert('insert', '包名未输入，请输入APK包名\n')
                return
            for device in self.device_list:
                ret = AdbUtils(device).adb.uninstall_apk(package)
                if ret:
                    self.text.insert('insert', f'设备：{device} APK卸载成功\n')
                else:
                    self.text.insert('insert', f'设备：{device} APK卸载失败\n')

        pkg = self.android.adb.get_current_package()
        pkg = askstring(title='获取信息', prompt='请输入需要卸载的APK包名：', initialvalue=pkg)
        self.thread_run(app_uninstall_button, pkg)

    def batch_reboot(self):
        def reboot_device_button(ret):
            if ret:
                for device in self.device_list:
                    AdbUtils(device).adb.reboot()
                    self.text.insert('insert', f'设备：{device} 已重启\n')

        result = askokcancel('提示', '确定要执行重启操作吗？')
        self.thread_run(reboot_device_button, result)

    def batch_kev_event(self):
        def key_event(string):
            if string is None:
                return
            elif string == '':
                self.text.insert('insert', '遥控器编码未输入，请输入\n')
            else:
                re_compile = re.compile(r'\d+$').match(string)
                if re_compile:
                    num = re_compile.group(0)
                    for device in self.device_list:
                        AdbUtils(device).adb.run_adb_shell_cmd('input keyevent %s' % num)
                        self.text.insert('insert', f'设备：{device} 已发送按键\n')
                else:
                    self.text.insert('insert', '遥控器编码输入错误，请输入整数编码\n')
        key = askstring(title='获取信息', prompt='请输入遥控器编码：', initialvalue="24")
        self.thread_run(key_event, key)

    def apk_switch(self, project, release='release'):
        apk_info_url = f'{config.apk_domain}/apk/apk_info.json'
        req = requests.get(apk_info_url)
        if req.status_code != 200:
            self.text.insert('insert', '版本切换服务异常\n')
            return
        top_level = Toplevel()
        top_level.title("版本切换")
        apk_info = json.loads(req.text)
        apk_list = apk_info.get(project).get(release)
        top_level.iconbitmap(self.icon_path)
        text = apk_info.get(project).get('name') + ('发布版本' if release == 'release' else '预发布版本')
        Label(top_level, text=text, font=self.common_font, width=60).grid(row=0, pady=6)
        listbox = Listbox(top_level, width=60)
        listbox.grid(row=1)
        for apk in apk_list:
            listbox.insert(END, apk)

        def url_apk_switch(package):
            self.text.delete('1.0', 'end')
            apk_url = f'{config.apk_domain}/apk/{project}/{release}/{package}'
            button.config(text='安装中', state=DISABLED)
            string = self.download_pkg(apk_url)
            if not string:
                if button.winfo_exists():
                    button.config(text='安装应用', state=NORMAL)
                return
            self.text.insert('insert', 'adb install %s\n' % string)
            ret = self.android.adb.install_apk(string)
            if ret:
                self.text.insert('insert', 'APK安装成功\n')
            else:
                self.text.insert('insert', 'APK安装失败\n')
            if button.winfo_exists():
                button.config(text='安装应用', state=NORMAL)

        button = Button(top_level, text="安装应用",
                        command=lambda: self.thread_run(url_apk_switch, listbox.get(listbox.curselection())),
                        font=self.common_font, width=8, height=1)
        button.grid(row=2, pady=6)

    def reset_app(self):
        """
        android设备apk缓存清除方法
        :return:
        """

        def reset_app_button(package):
            if package is None:
                return
            elif package == '':
                self.text.insert('insert', '包名未输入，请输入APK包名\n')
            elif self.is_app_package(package):
                button.config(text='清除中', state=DISABLED)
                self.text.insert('insert', 'adb shell pm clear %s\n' % package)
                ret = self.android.adb.pm_clear_package(package)
                self.text.insert('insert', str(ret) + '\n')
                button.config(text='清除缓存', state=NORMAL)
            else:
                self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

        def reset_app_thread():
            self.text.delete('1.0', 'end')
            package = self.android.adb.get_current_package()
            package = askstring(title='获取信息', prompt='请输入需要清除缓存的APK包名：', initialvalue=package)
            self.thread_run(reset_app_button, package)

        button = Button(self.root, text="清除缓存", command=reset_app_thread, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=0, pady=6, sticky=W)

    def start_app(self):
        """
        app启动方法，自动获取main activity并启动app
        :return:
        """

        def start_app_button(package):
            if package is None:
                return
            elif package == '':
                self.text.insert('insert', '包名未输入，请输入APK包名\n')
            elif self.is_app_package(package):
                if not self.android.adb.is_app_installed(package):
                    self.text.insert('insert', 'APK未安装\n')
                    return
                button.config(text='启动中', state=DISABLED)
                activity = self.android.adb.get_main_activity(package)
                self.text.insert('insert', 'adb shell am start -W %s/%s\n' % (package, activity))
                ret = self.android.adb.start_activity(f'{package}/{activity}')
                self.text.insert('insert', str(ret) + '\n')
                button.config(text='启动应用', state=NORMAL)
            else:
                self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

        def start_app_thread():
            self.text.delete('1.0', 'end')
            package = askstring(title='获取信息', prompt='请输入需要启动的APK包名：')
            self.thread_run(start_app_button, package)

        button = Button(self.root, text="启动应用", command=start_app_thread, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=1, pady=6, sticky=W)

    def stop_app(self):
        """
        app停止方法
        :return:
        """

        def stop_app_button(package):

            if package is None:
                return
            elif package == '':
                self.text.insert('insert', '包名未输入，请输入APK包名\n')
            elif self.is_app_package(package):
                button.config(text='停止中', state=DISABLED)
                self.text.insert('insert', 'adb shell am force-stop %s\n' % package)
                self.android.adb.force_stop_package(package)
                button.config(text='停止应用', state=NORMAL)
            else:
                self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

        def stop_app_thread():
            self.text.delete('1.0', 'end')
            package = self.android.adb.get_current_package()
            package = askstring(title='获取信息', prompt='请输入需要关闭的APK包名：', initialvalue=package)
            self.thread_run(stop_app_button, package)

        button = Button(self.root, text="停止应用", command=stop_app_thread, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=2, pady=6, sticky=W)

    def app_install(self):
        """
        app安装方法，自动判断是本地路径还是网络链接
        网络连接则下载后再进行安装
        :return:
        """

        def thread_install(string):
            if string is None:
                return
            elif string == '':
                self.text.insert('insert', 'APK包的本地路径或URL链接未输入，请重新输入\n')
            else:
                string = string.strip().replace('"', '')
                button.config(text='安装中', state=DISABLED)
                if not os.path.isfile(string):
                    if not re.match(r'^https?:/{2}\w.+$', string):
                        self.text.insert('insert', '输入的APK包的本地路径或URL链接错误\n')
                        button.config(text='软件安装', state=NORMAL)
                        return
                    string = self.download_pkg(string)
                    if not string:
                        button.config(text='软件安装', state=NORMAL)
                        return
                self.text.insert('insert', 'adb install -r -d %s\n' % string)
                ret = self.android.adb.install_apk(string)
                if ret:
                    self.text.insert('insert', 'APK安装成功\n')
                else:
                    self.text.insert('insert', 'APK安装失败，请尝试使用“软件卸载”执行卸载后再次安装\n')
                button.config(text='软件安装', state=NORMAL)

        def app_install_button():
            self.text.delete('1.0', 'end')
            string = askstring(title='获取信息', prompt='请输入APK包的本地路径或URL链接：')
            self.thread_run(thread_install, string)

        button = Button(self.root, text="软件安装", command=app_install_button, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=3, pady=6, sticky=W)

    def app_uninstall(self):
        """
        app卸载方法
        :return:
        """

        def app_uninstall_button(package):
            if package is None:
                return
            elif package == '':
                self.text.insert('insert', '包名未输入，请输入APK包名\n')
            elif self.is_app_package(package):
                button.config(text='卸载中', state=DISABLED)
                self.text.insert('insert', 'adb uninstall %s\n' % package)
                ret = self.android.adb.uninstall_apk(package)
                if ret:
                    self.text.insert('insert', 'APK卸载成功\n')
                else:
                    ret = self.android.adb.run_adb_shell_cmd('pm list package -f %s ' % package)
                    re_com = re.search(r'package:(.+?)=', ret)
                    if re_com:
                        ret = self.android.adb.remount_dire()
                        if ret:
                            self.android.adb.run_adb_shell_cmd(f'mv {re_com.group(1)} {re_com.group(1)}.bak')
                            self.text.insert('insert', 'APK卸载成功,请重启机顶盒\n')
                            button.config(text='软件卸载', state=NORMAL)
                            return
                    self.text.insert('insert', 'APK卸载失败\n')
                button.config(text='软件卸载', state=NORMAL)
            else:
                self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

        def app_uninstall():
            self.text.delete('1.0', 'end')
            package = self.android.adb.get_current_package()
            package = askstring(title='获取信息', prompt='请输入需要卸载的APK包名：', initialvalue=package)
            self.thread_run(app_uninstall_button, package)

        button = Button(self.root, text="软件卸载", command=app_uninstall, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=4, pady=6, sticky=W)

    def set_proxy(self):
        """
        设置代理方法，指定代理服务器和端口
        android 4.2及以下版本不支持
        :return:
        """
        data = {'ip_port': '192.168.43.56:8888'}

        def set_proxy_button(string):
            if string is None:
                return
            elif string == '':
                self.text.insert('insert', 'Ip:Port未输入，请重新输入\n')
            else:
                button.config(text='配置中', state=DISABLED)
                cmd = 'settings put global http_proxy %s' % string
                self.text.insert('insert', 'adb shell %s\n' % cmd)
                self.android.adb.run_adb_shell_cmd(cmd)
                ret = self.android.adb.run_adb_shell_cmd('settings get global http_proxy')
                if ret == string:
                    self.text.insert('insert', '\n代理设置成功\n')
                    data['ip_port'] = string
                else:
                    self.text.insert('insert', '\n代理设置不成功\n')
                button.config(text='配置代理', state=NORMAL)

        def set_proxy_thread():
            self.text.delete('1.0', 'end')
            string = askstring(title='获取信息', prompt='请输入代理Ip:Port',
                               initialvalue=data['ip_port'])
            self.thread_run(set_proxy_button, string)

        button = Button(self.root, text="配置代理", command=set_proxy_thread, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=5, pady=6, sticky=W)

    def delete_proxy(self):
        """
        删除代理方法，先判断settings delete命令是否支持
        不支持时使用sqlite3修改数据库进行删除操作
        未root设备无法使用sqlite3修改数据库操作
        :return:
        """

        def delete_proxy_button():
            button.config(text='删除中', state=DISABLED)
            self.text.delete('1.0', 'end')
            self.text.insert('insert', 'adb shell settings delete global http_proxy\n')
            ret = self.android.adb.run_adb_shell_cmd('settings delete global http_proxy')
            if 'Deleted' in ret:
                self.text.insert('insert', '%s\n' % ret)
                self.text.insert('insert', 'adb shell settings delete global global_http_proxy_host\n')
                ret = self.android.adb.run_adb_shell_cmd('settings delete global global_http_proxy_host')
                self.text.insert('insert', '%s\n' % ret)
                self.text.insert('insert', 'adb shell settings delete global global_http_proxy_port\n')
                ret = self.android.adb.run_adb_shell_cmd('settings delete global global_http_proxy_port')
                self.text.insert('insert', '%s\n' % ret)
            else:
                ret = self.sqlite3_install()
                if ret is True:
                    sqlite_path = 'sqlite3'
                else:
                    sqlite_path = ret
                self.text.insert('insert', 'delete from global where name ="http_proxy"\n')

                self.android.adb.run_adb_shell_cmd(
                    r"%s /data/data/com.android.providers.settings/databases/settings.db "
                    r"\"delete from global where name ='http_proxy'\"" % sqlite_path)
                self.text.insert('insert', 'delete from global where name ="global_http_proxy_host"\n')
                self.android.adb.run_adb_shell_cmd(
                    r"%s /data/data/com.android.providers.settings/databases/settings.db "
                    r"\"delete from global where name ='global_http_proxy_host'\"" % sqlite_path)
                self.text.insert('insert', 'delete from global where name ="global_http_proxy_port"\n')
                self.android.adb.run_adb_shell_cmd(
                    r"%s /data/data/com.android.providers.settings/databases/settings.db "
                    r"\"delete from global where name ='global_http_proxy_port'\"" % sqlite_path)

            ret1 = self.android.adb.run_adb_shell_cmd('settings get global http_proxy')
            if ret1 == 'null':
                self.text.insert('insert', '代理删除成功')
            else:
                self.text.insert('insert', '代理删除失败')
            button.config(text='删除代理', state=NORMAL)

        button = Button(self.root, text="删除代理", command=lambda: self.thread_run(delete_proxy_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=2, column=6, pady=6, sticky=W)

    def reboot_device(self):
        """
        设备重启方法，二次确认重启
        :return:
        """

        def reboot_device_button(ret):
            if ret:
                self.text.delete('1.0', 'end')
                self.text.insert('insert', 'adb reboot\n')
                button.config(text='重启中', state=DISABLED)
                self.android.adb.reboot()
                button.config(text='重启设备', state=NORMAL)

        def reboot_device_thread():
            ret = askokcancel('提示', '确定要执行重启操作吗？')
            self.thread_run(reboot_device_button, ret)

        button = Button(self.root, text="重启设备", command=reboot_device_thread, font=self.common_font, width=8, height=1)
        button.grid(row=2, column=7, pady=6, sticky=W)

    def download_pkg(self, url):
        """
        文件下载方法，用于软件安装时使用
        :param url:
        :return:
        """
        pkg_name = os.path.basename(url)
        dir_file = os.listdir(self.save_path)
        file_path = os.path.join(self.save_path, pkg_name)
        if pkg_name in dir_file:
            os.remove(file_path)
        res = requests.get(url)
        if res.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in res.iter_content(100000):
                    f.write(chunk)
            self.text.insert('insert', f'{url} 下载成功\n')
            return file_path
        self.text.insert('insert', f'{url} 下载失败\n')

    def sqlite3_install(self):
        ret = self.android.adb.run_adb_shell_cmd(
            r"sqlite3 /data/data/com.android.providers.settings/databases/settings.db "
            r"\"select * from global where name ='http_proxy'\"")
        if ret.find('not found') == -1 and ret.find('Permission denied') == -1:
            return True
        else:
            ret = self.android.adb.remount_dire()
            if ret is True:
                src_path = os.path.join(config.root_path, 'tools', 'sqlite3')
                dst_path = '/system/xbin'
                self.android.adb.push_file(src_path, dst_path)
                self.android.adb.run_adb_shell_cmd('chmod 777 /system/xbin/sqlite3')
                return True
            else:
                src_path = os.path.join(config.root_path, 'tools', 'sqlite3')
                dst_path = '/data/local/tmp'
                self.android.adb.push_file(src_path, dst_path)
                self.android.adb.run_adb_shell_cmd('chmod 777 /data/local/tmp/sqlite3')
                return dst_path

    def screen_shot(self):
        """
        截取android设备当前屏幕画面
        部分4.4版本的设备未连接显示器时，截图画面尺寸可能不正确
        :return:
        """

        def screen_shot_button():
            self.text.delete('1.0', 'end')
            self.text.insert('insert', 'adb shell screen_cap -p /data/local/tmp/screenshot.png\n')
            self.text.insert('insert', 'adb pull /data/local/tmp/screenshot.png %s\n' % self.save_path)
            button.config(text='截图中', state=DISABLED)
            self.android.adb.run_adb_shell_cmd('rm /data/local/tmp/screenshot*.png')
            self.android.adb.screen_cap(self.save_path)
            button.config(text='屏幕截图', state=NORMAL)

        button = Button(self.root, text="屏幕截图", command=lambda: self.thread_run(screen_shot_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=3, column=0, pady=6, sticky=W)

    def screen_record(self):
        """
        android设备当前设备录屏，最多支持180秒
        4.4设备播放页显示为黑屏
        :return:
        """
        data = {'tmp_path': ''}

        def screen_record_button():
            if not self.record_process:
                tmp_path = f'/data/local/tmp/screenrecord_{Utils.get_current_underline_time()}.mp4'
                data['tmp_path'] = tmp_path
                self.text.delete('1.0', 'end')
                self.text.insert('insert', '屏幕录制时间最多支持180秒，依次点击屏幕录制、停止录制完成屏幕录制\n')
                button.config(text='停止录制', state=DISABLED)
                self.android.adb.run_adb_shell_cmd('rm /data/local/tmp/screenrecord*.mp4')
                self.text.insert('insert', f'adb shell screenrecord {tmp_path}\n')
                self.record_process = self.android.adb.run_adb_shell_cmd(
                    f'screenrecord {tmp_path}', timeout=180, sync=False)
                t = threading.Thread(target=self.record_process.communicate)
                t.start()
                button.config(text='停止录制', state=NORMAL)
            else:
                tmp_path = data.get('tmp_path')
                button.config(text='屏幕录制', state=DISABLED)
                try:
                    far_proc = psutil.Process(self.record_process.pid)
                    for chi_proc in far_proc.children(recursive=True):
                        chi_proc.kill()
                    far_proc.kill()
                except psutil.NoSuchProcess:
                    logger.debug('NoSuchProcess no process found')
                time.sleep(1)
                file_path = os.path.join(self.save_path, 'screenrecord.mp4')
                if os.path.isfile(file_path):
                    os.remove(file_path)
                self.text.insert('insert', f'adb pull {tmp_path} {self.save_path}\n')
                ret = self.android.adb.pull_file(tmp_path, self.save_path)
                self.text.insert('insert', '\n' + str(ret) + '\n')
                button.config(text='屏幕录制', state=NORMAL)
                self.record_process = None

        button = Button(self.root, text="屏幕录制", command=lambda: self.thread_run(screen_record_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=3, column=1, pady=6, sticky=W)

    def tcp_dump(self):
        """
        :return:
        """
        data = {'tmp_path': '', 'dump_process': 0, 'mold': StringVar(), 'inf': StringVar(), 'root': StringVar(),
                'tcp': StringVar(), 'wire': StringVar(), 'ok': IntVar}

        def tcp_dump_button():

            def control_set(*args):
                value = combobox.get()
                if value == '实时查看':
                    label.grid(row=4, column=0, pady=6, sticky=W)
                    entry.grid(row=4, column=1, pady=6, sticky=W)
                else:
                    label.grid_forget()
                    entry.grid_forget()

            def ok_button():
                value = combobox.get()
                top_level.destroy()
                if value == '本地存储':
                    if is_root and dump:
                        start_tcp_dump_local()
                    else:
                        data['dump_process'] = 0
                else:
                    wire_dir = data['wire'].get().replace('"', '')
                    exe_path = wire_dir if 'Wireshark.exe' in wire_dir else os.path.join(wire_dir, 'Wireshark.exe')
                    if os.path.exists(exe_path) and is_root and dump:
                        data['wire'].set(exe_path)
                        start_tcp_dump_real()
                    else:
                        data['dump_process'] = 0

            if data.get('dump_process') == 0:
                top_level = Toplevel()
                top_level.title("开启抓包")
                top_level.iconbitmap(self.icon_path)

                type_list = ['本地存储', '实时查看']
                mold = data.get('mold')
                mold.set('本地存储')
                Label(top_level, text="抓包方式", font=self.common_font, width=12).grid(row=0, column=0, pady=6, sticky=W)
                combobox = ttk.Combobox(top_level, textvariable=mold, value=type_list, width=20)
                combobox.grid(row=0, column=1)
                combobox.bind("<<ComboboxSelected>>", control_set)

                int_list = self.android.adb.list_net_interface()
                inf = data.get('inf')
                if len(int_list) > 0:
                    inf.set(int_list[0])
                Label(top_level, text="选择接口", font=self.common_font, width=12).grid(row=1, column=0, pady=6, sticky=W)
                ttk.Combobox(top_level, textvariable=inf, value=int_list, width=20).grid(row=1, column=1)

                Label(top_level, text="root状态", font=self.common_font, width=12).grid(row=2, column=0, pady=6, sticky=W)
                root = data.get('root')
                is_root = self.android.adb.is_device_root()
                if is_root:
                    data['ok'] = 1
                    root.set('设备已root')
                else:
                    data['ok'] = 0
                    root.set('设备未root')
                Entry(top_level, textvariable=root, width=20, state=DISABLED).grid(row=2, column=1, pady=6, sticky=W)

                Label(top_level, text="tcpdump", font=self.common_font, width=12).grid(row=3, column=0, pady=6,
                                                                                       sticky=W)
                tcp = data.get('tcp')
                dump = self.android.adb.is_tool_install('tcpdump')
                if dump:
                    tcp.set(dump)
                else:
                    tcp.set('tcpdump未安装或无权限')
                Entry(top_level, textvariable=tcp, width=20, state=DISABLED).grid(row=3, column=1, pady=6, sticky=W)

                label = Label(top_level, text="wireshark", font=self.common_font, width=12)
                wire = data.get('wire')
                wire.set(r'输入wireshark路径')
                entry = Entry(top_level, textvariable=wire, width=20)

                err_msg = Label(top_level, text='', fg='red')
                err_msg.grid(row=5, column=0, sticky=W)
                frame = Frame(top_level)
                frame.grid(row=5, column=1, pady=6, sticky=E)
                Button(frame, text="确定", command=ok_button).grid()
            else:
                if data.get('mold').get() == '本地存储':
                    stop_tcp_dump_local()
                else:
                    stop_tcp_dump_real()

        def start_tcp_dump_local():
            tmp_path = f'/data/local/tmp/tcp_dump_{Utils.get_current_underline_time()}.pcap'
            data['tmp_path'] = tmp_path
            self.text.delete('1.0', 'end')
            self.text.insert('insert', '通过tcpdump命令抓包，依次点击开启抓包、停止抓包完成抓包操作，存在多个网卡时默认监视第一个网络接口\n')
            button.config(text='停止抓包', state=DISABLED)
            self.android.adb.run_adb_shell_cmd(r'rm /data/local/tmp/tcp_dump*.pcap')
            cmd = f"tcpdump -i {data['inf'].get()} -s 0 -w {tmp_path}"
            self.text.insert('insert', f'adb shell {cmd}\n')
            self.dump_process = self.android.adb.run_adb_shell_cmd(cmd, sync=False)
            thread = threading.Thread(target=self.dump_process.communicate)
            thread.start()
            button.config(text='停止抓包', state=NORMAL)
            data['dump_process'] = 1

        def stop_tcp_dump_local():
            tmp_path = data.get('tmp_path')
            button.config(text='导出中', state=DISABLED)
            try:
                far_proc = psutil.Process(self.dump_process.pid)
                for chi_proc in far_proc.children(recursive=True):
                    chi_proc.kill()
                far_proc.kill()
            except psutil.NoSuchProcess:
                logger.debug('NoSuchProcess no process found')
            time.sleep(1)

            self.text.insert('insert', f'adb pull {tmp_path} {self.save_path}\n')
            ret = self.android.adb.pull_file(tmp_path, self.save_path)
            self.text.insert('insert', '\n' + str(ret) + '\n')
            button.config(text='开启抓包', state=NORMAL)
            data['dump_process'] = 0

        def start_tcp_dump_real():
            self.android.adb.run_adb_cmd('forward tcp:2015 tcp:2015')
            wire_dir = data['wire'].get()
            cmd = f"\"tcpdump -i {data['inf'].get()} -s 0 -w - | busybox nc -l -p 2015\""
            self.dump_process = self.android.adb.run_adb_shell_cmd(cmd, sync=False)
            thread = threading.Thread(target=self.dump_process.communicate)
            thread.start()
            button.config(text='停止抓包', state=NORMAL)
            nc_path = os.path.join(config.root_path, 'tools', 'nc.exe')
            if os.path.exists(nc_path):
                self.text.delete('1.0', 'end')
                self.text.insert('insert', '请在命令行命令启动wireshark开始抓包\n')
                self.text.insert('insert', f'"{nc_path}" 127.0.0.1 2015| "{wire_dir}" -k -S -i -')
                subprocess.Popen(r"C:\Users\Dell\Desktop\test.bat", shell=True, stdout=subprocess.PIPE)
            else:
                self.text.insert('insert', f'{nc_path} 不存在')
            data['dump_process'] = 1

        def stop_tcp_dump_real():
            try:
                far_proc = psutil.Process(self.dump_process.pid)
                for chi_proc in far_proc.children(recursive=True):
                    chi_proc.kill()
                far_proc.kill()
            except psutil.NoSuchProcess:
                logger.debug('NoSuchProcess no process found')
            time.sleep(1)

            button.config(text='开启抓包', state=NORMAL)
            data['dump_process'] = 0

        button = Button(self.root, text="开启抓包", command=lambda: self.thread_run(tcp_dump_button), font=self.common_font,
                        width=8, height=1)
        button.grid(row=3, column=5, pady=6, sticky=W)

    def screen_display(self):
        """
        android设备屏幕实时画面显示
        基于minicap实现
        画面显示窗口支持按键操控
        :return:
        """

        def screen_display_button():
            ret = self.minicap.start_mini_server()
            if not ret:
                self.text.delete('1.0', 'end')
                self.text.insert('insert', '设备图像无法查看\n')
                return

            def key_press(event):
                key = event.keysym
                if KeyMap.key_map.get(key):
                    cmd = f'input keyevent {KeyMap.key_map.get(key)}'
                else:
                    cmd = f'input text {key}'
                t = threading.Thread(target=self.android.adb.run_adb_shell_cmd, args=(cmd,))
                t.start()

            def close_window():
                self.minicap.stop_screenrecord()
                canvas.destroy()
                top_level.destroy()
                button.config(text='查看屏幕', state=NORMAL)

            button.config(text='查看中', state=DISABLED)
            top_level = Toplevel()
            top_level.title("设备屏幕")
            top_level.iconbitmap(self.icon_path)
            top_level.protocol('WM_DELETE_WINDOW', close_window)
            top_level.bind('<Key>', key_press)

            canvas = Canvas(top_level)
            canvas.grid(row=1, column=1)
            self.minicap.canvas_display(canvas)

            # self.minicap.image_display()

        button = Button(self.root, text="查看屏幕", command=lambda: self.thread_run(screen_display_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=3, column=2, pady=6, sticky=W)

    def start_logcat(self):
        """
        日志采集方法，开启日志开始抓取日志，停止日志关闭日志抓取
        日志抓取时间过短会出现日志文件未保存现象
        :return:
        """

        def start_logcat_button():
            if not self.logcat_process:
                self.logcat.start_logcat(self.save_path)
                self.text.delete('1.0', 'end')
                self.text.insert('insert', '开始记录日志，日志保存路径：%s\n' % self.save_path)
                button.config(text='停止日志')
                self.logcat_process = True
            else:
                self.logcat.stop_logcat()
                self.text.insert('insert', '日志已停止记录\n')
                button.config(text='开启日志')
                self.logcat_process = None

        button = Button(self.root, text="开启日志", command=start_logcat_button, font=self.common_font, width=8, height=1)
        button.grid(row=3, column=3, pady=6, sticky=W)

    def dump_heap(self):
        """
        apk heap内存dump方法，内存文件正常dump需要满足以下两个条件中的一个：
        1、apk debuggable开启
        2、调协debuggable开启
        集成mprop工具，在已root设备上修改内存debuggable属性实现dump内存
        :return:
        """

        def thread_dump(package):
            if package is None:
                return
            elif package == '':
                self.text.insert('insert', '包名未输入，请输入APK包名\n')
            elif self.is_app_package(package):
                self.text.insert('insert', '开始执行导出操作\n')
                ret = self.android.adb.package_dumpheap(package, self.save_path)
                if ret:
                    self.text.insert('insert', '内存导出失败：\n%s\n' % ret)
                else:
                    self.text.insert('insert', '内存导出成功，文件路径：%s\n' % self.save_path)
            else:
                self.text.insert('insert', '请检查包名是否正确：%s\n' % package)

        status = self.android.adb.run_adb_shell_cmd('getprop ro.debuggable')
        if status == '0':
            ret = self.android.adb.run_adb_shell_cmd('ls /data/local/tmp')
            if 'mprop' not in ret:
                src_path = os.path.join(config.root_path, 'tools', 'mprop')
                dst_path = '/data/local/tmp'
                self.android.adb.push_file(src_path, dst_path)
                self.android.adb.run_adb_shell_cmd('chmod 777 /data/local/tmp/mprop')
            process = self.android.adb.run_adb_shell_cmd('./data/local/tmp/mprop ro.debuggable 1', sync=False)
            process.communicate()
        package = self.android.adb.get_current_package()
        package = askstring(title='获取信息', prompt='请输入需要查看的APK包名：', initialvalue=package)
        self.thread_run(thread_dump, package)

    def data_report(self):
        data = {'ip_port': '172.31.36.141:8888', 'proxy': False}

        def report_button():
            ip_port = askstring(title='数据上报测试', prompt='请输入代理IP和端口', initialvalue=data['ip_port'])
            if ip_port is None:
                return
            elif ip_port == '':
                self.text.insert('insert', 'IP地址和端口未输入，请重新输入\n')
            elif len(ip_port.split(':')) == 2:
                data['ip_port'] = ip_port
                ip, port = ip_port.split(':')
                if port.isdigit():
                    if not data['proxy']:
                        HttpProxy(int(port))
                        data['proxy'] = True
                    cmd = f'settings put global http_proxy {ip}:6666'
                    self.android.adb.run_adb_shell_cmd(cmd)
                    ret = self.android.adb.run_adb_shell_cmd('settings get global http_proxy')
                    if ret == f'{ip}:6666':
                        self.text.insert('insert', '数据测试开启成功\n')
                    else:
                        self.text.insert('insert', 'HTTP代理设置失败\n')
                else:
                    self.text.insert('insert', f'端口不是数字：{port}\n')
            else:
                self.text.insert('insert', f'请检查IP和端口配置是否正确：{ip_port}\n')

        button = Button(self.root, text="数据上报", command=report_button, font=self.common_font, width=8, height=1)
        button.grid(row=3, column=4, pady=6, sticky=W)

    def adb_connect(self):
        """
        adb连接方法
        :return:
        """

        def thread_connect(string):
            if string is None:
                return
            elif string == '':
                self.text.insert('insert', 'Ip地址未输入，请输入Ip地址\n')
            else:
                self.text.insert('insert', 'adb connect %s\n' % string)
                button.config(text='连接中', state=DISABLED)
                ret = self.android.adb.run_adb_cmd('connect %s' % string, timeout=30)
                button.config(text='Adb连接', state=NORMAL)
                self.text.insert('insert', '%s\n' % ret)

        def adb_connect_button():
            self.text.delete('1.0', 'end')
            string = askstring(title='获取信息', prompt='请输入需要连接设备的Ip地址：')
            self.thread_run(thread_connect, string)

        button = Button(self.root, text="Adb连接", command=adb_connect_button, font=self.common_font, width=8, height=1)
        button.grid(row=4, column=0, pady=6, sticky=W)

    def adb_disconnect(self):
        """
        adb连接断开方法，二次确认断开
        :return:
        """

        def adb_disconnect_button():
            ret = askokcancel('提示', '确定要断开ADB连接吗？')
            if ret:
                self.text.delete('1.0', 'end')
                self.text.insert('insert', 'adb disconnect %s\n' % self.android.adb.device_id)
                ret = self.android.adb.run_adb_cmd('disconnect ' + self.android.adb.device_id)
                self.text.insert('insert', str(ret) + '\n')

        button = Button(self.root, text="Adb断开", command=adb_disconnect_button, font=self.common_font, width=8,
                        height=1)
        button.grid(row=4, column=1, pady=6, sticky=W)

    def adb_enable(self):
        """
        adb永久开启方法，通过修改build.prop文件实现
        未root设备不支持此方法
        部分root设备可能也不支持
        :return:
        """

        def adb_enable_button():
            ret = self.android.adb.run_adb_shell_cmd('cat /system/build.prop')
            if ret != '':
                self.android.adb.remount_dire()
                if 'persist.service.adb.enable=0' in ret:
                    self.android.adb.run_adb_shell_cmd(
                        r"sed -i 's/persist.service.adb.enable=0/persist.service.adb.enable=1/g' /system/build.prop")
                    self.text.delete('1.0', 'end')
                    self.text.insert('insert', '永久开启adb已配置，请重启设备后查看adb是否可连接,如无法连接则该设备不支持该方法')
                elif 'persist.service.adb.enable=1' in ret:
                    self.text.delete('1.0', 'end')
                    self.text.insert('insert', '已完成配置，无需重复配置')
                else:
                    self.android.adb.run_adb_shell_cmd("echo \"'persist.service.adb.enable=1' >> /system/build.prop\"")
                    self.text.delete('1.0', 'end')
                    self.text.insert('insert', '永久开启adb已配置，请重启设备后查看adb是否可连接,如无法连接则该设备不支持该方法')
            else:
                self.text.delete('1.0', 'end')
                self.text.insert('insert', 'adb配置信息获取失败')

        button = Button(self.root, text="AdbEnable", command=adb_enable_button, font=self.common_font, width=8,
                        height=1)
        button.grid(row=4, column=2, pady=6, sticky=W)

    def activity_top(self):
        """
        获取当前页面activity信息
        :return:
        """

        def activity_top_button():
            self.text.delete('1.0', 'end')
            button.config(text='查看中', state=DISABLED)
            activity = self.android.adb.get_top_activity()
            button.config(text='查Activity', state=NORMAL)
            if not activity:
                self.text.insert('insert', 'activity获取失败\n')
                return
            self.text.insert('insert', activity)

        button = Button(self.root, text="查Activity", command=lambda: self.thread_run(activity_top_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=3, column=7, pady=6, sticky=W)

    def top_cpu(self):

        self.text.delete('1.0', 'end')
        self.text.insert('insert', 'adb shell top -n 1\n')
        ret = self.android.adb.run_adb_shell_cmd('top -n 1')
        self.text.insert('insert', ret)

    def remount_device(self):
        """
        挂载系统目录
        :return:
        """

        def remount_device_button():
            self.text.delete('1.0', 'end')
            self.text.insert('insert', 'adb shell mount -o remount /system\n')
            button.config(text='挂载中', state=DISABLED)
            ret = self.android.adb.remount_dire()
            button.config(text='挂载System', state=NORMAL)
            if ret is True:
                self.text.insert('insert', 'system目录挂载成功')
            else:
                self.text.insert('insert', 'system目录挂载失败:%s' % ret)

        button = Button(self.root, text="挂载System", command=lambda: self.thread_run(remount_device_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=3, column=6, pady=6, sticky=W)

    def ping_test(self):
        """
        android设备执行ping测试
        :return:
        """

        def thread_ping(string):
            if string is None:
                return
            elif string == '':
                self.text.insert('insert', 'Ip地址未输入，请输入Ip地址\n')
            else:
                self.text.insert('insert', 'adb shell ping -c 4 %s\n' % string)
                ret = self.android.adb.ping_test(string, 4)
                self.text.insert('insert', '%s\n' % ret)

        self.text.delete('1.0', 'end')
        string = askstring(title='获取信息', prompt='请输入需要Ping测试的Ip地址：')
        self.thread_run(thread_ping, string)

    def start_garden(self):
        """
        开启和关闭后花园
        :return:
        """
        data = {'var': 0}

        def start_garden_button():
            package = self.android.adb.get_current_package()
            ret = self.android.adb.run_adb_shell_cmd('getevent -p')
            ret_list = ret.split('add device')
            for ret in ret_list:
                re_regx = re.search(r'(/dev/input/event\d).+?0001  0002', ret, re.S)
                if re_regx:
                    event = re_regx.group(1)
                    cmd = f'adb -s {self.android.adb.device_id} shell sendevent {event} '
                    button.config(text='开启中', state=DISABLED)
                    ret = self.android.adb.run_adb_shell_cmd('dumpsys package %s' % package)
                    back = f'{cmd}1 158 1&{cmd} 0 0 0&{cmd}1 158 0&{cmd} 0 0 0'
                    menu = f'{cmd}1 139 1&{cmd} 0 0 0&{cmd}1 139 0&{cmd} 0 0 0'
                    up = f'{cmd}1 103 1&{cmd} 0 0 0&{cmd}1 103 0&{cmd} 0 0 0'
                    down = f'{cmd}1 108 1&{cmd} 0 0 0&{cmd}1 108 0&{cmd} 0 0 0'
                    left = f'{cmd}1 105 1&{cmd} 0 0 0&{cmd}1 105 0&{cmd} 0 0 0'
                    right = f'{cmd}1 106 1&{cmd} 0 0 0&{cmd}1 106 0&{cmd} 0 0 0'
                    ok = f'{cmd}1 28 1&{cmd} 0 0 0&{cmd}1 28 0&{cmd} 0 0 0'
                    if ret.find('com.hunantv.operator') != -1:
                        subprocess.Popen('&'.join([back, menu, up, up, down, up, up, up, down, down]), shell=True)
                    elif ret.find('com.mgtv.tv') != -1:
                        ret = self.android.adb.start_activity(f'{package}/com.mgtv.tv.channel.activity.AboutActivity')
                        if ret != 'Permission Denial':
                            subprocess.Popen('&'.join([left, left, right, left, ok]), shell=True)
                        else:
                            self.text.insert('insert', '设备未root，无法进入后花园\n')
                    else:
                        self.text.insert('insert', 'apk未兼容\n')
                    button.config(text='进后花园', state=NORMAL)

        button = Button(self.root, text="进后花园", command=lambda: self.thread_run(start_garden_button),
                        font=self.common_font, width=8, height=1)
        button.grid(row=4, column=3, pady=6, sticky=W)

    def text_delete(self):
        """
        清除工具文本输出框的全部内容
        :return:
        """

        def text_delete_button():
            self.text.delete('1.0', 'end')

        button = Button(self.root, text="清空文本", command=text_delete_button, font=self.common_font, width=8, height=1)
        button.grid(row=5, column=3, pady=6, sticky=W)

    def open_debug_log(self):
        def open_debug_button():
            log_path = os.path.join(config.root_path, 'logs')
            os.startfile(log_path)

        button = Button(self.root, text="Debug日志", command=open_debug_button, font=self.common_font, width=8, height=1)
        button.grid(row=5, column=3, pady=6, sticky=W)

    def open_dir(self):
        """
        打开测试结果目录
        :return:
        """

        def open_dir_button():

            if self.os_platform == 'Windows':
                os.startfile(self.save_path)
            else:
                subprocess.call(['open', self.save_path])

        if self.os_platform == 'Windows':
            width = 18
        else:
            width = 22
        button = Button(self.root, text="查看结果目录", command=open_dir_button, font=self.common_font, width=width, height=1)
        button.grid(row=4, column=4, columnspan=2, pady=6, sticky=W)

    def remove_dir(self):
        """
        清除测试结果目录，二次确认清除
        :return:
        """

        def remove_dir_button():
            ret = askokcancel('提示', '确定要清空结果目录吗？')
            if ret:
                del_list = os.listdir(self.save_path)
                for f in del_list:
                    file_path = os.path.join(self.save_path, f)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)

        if self.os_platform == 'Windows':
            width = 18
        else:
            width = 22
        button = Button(self.root, text="清空结果目录", command=remove_dir_button, font=self.common_font, width=width,
                        height=1)
        button.grid(row=4, column=6, columnspan=2, pady=6, sticky=W)

    def open_adb_method(self):
        """
        常用机顶盒设置adb开启方法查询
        :return:
        """
        factory_list = self.adb_open.get_all_factory()

        def get_model(*args):
            factory = combobox.get()
            model_list = self.adb_open.get_factory_model(factory)
            combobox1.set('')
            combobox1['value'] = model_list
            return model_list

        label = Label(self.root, text="开adb方法", font=self.common_font, width=8, height=1)
        label.grid(row=7, column=0, pady=6, sticky=W)

        number = tkinter.StringVar()
        combobox = ttk.Combobox(self.root, textvariable=number)
        combobox['value'] = factory_list
        combobox.grid(row=7, column=1, columnspan=6, pady=6, sticky=W)
        combobox.bind("<<ComboboxSelected>>", get_model)

        combobox1 = ttk.Combobox(self.root)
        combobox1.grid(row=7, column=4, columnspan=6, pady=6, sticky=W)

        def open_adb_method_button():
            factory = combobox.get()
            model = combobox1.get()
            if model == '':
                self.text.delete('1.0', 'end')
                self.text.insert('insert', '请选择设备的厂家或型号')
            else:
                method = self.adb_open.get_adb_open_method(factory, model)
                self.text.delete('1.0', 'end')
                self.text.insert('insert', method)

        button = Button(self.root, text="查询", command=open_adb_method_button, font=self.common_font, width=8, height=1)
        button.grid(row=7, column=7, pady=6, sticky=W)

    def text_display(self):
        """
        文本输出框
        :return:
        """
        text = self.text
        text.grid(row=10, columnspan=8)

    def contact(self):
        """
        联系人版本信息
        :return:
        """
        label = Label(self.root, text='版本v2.2.9.15\t联系人:chengyuan@mgtv.com', pady=6, font=self.common_font)
        label.grid(row=11, columnspan=8)

    def start(self):
        """
        进入消息循环方法
        :return:
        """
        self.creat_menu()
        self.title_info()

        self.reset_app()
        self.start_app()
        self.stop_app()
        self.app_install()
        self.app_uninstall()
        self.set_proxy()
        self.delete_proxy()
        self.reboot_device()

        self.screen_shot()
        self.screen_record()
        self.screen_display()
        self.start_logcat()
        self.data_report()
        self.tcp_dump()
        self.remount_device()
        self.activity_top()

        self.adb_connect()
        self.adb_disconnect()
        self.adb_enable()
        self.start_garden()
        self.open_dir()
        self.remove_dir()

        self.open_adb_method()

        self.text_display()
        self.contact()

        self.root.mainloop()


if __name__ == '__main__':
    g = Gui()
    g.start()

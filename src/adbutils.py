#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import time
import psutil
import threading
import subprocess
from src.log import logger
from src.utils import Utils


class ADB:
    def __init__(self, device_id=None):
        self.os_platform = Utils.get_os_platform()
        self.adb_path = self.get_adb_tool_path()
        self.device_id = device_id

    def get_adb_tool_path(self):
        """
        检测adb工具是否安装，否则使用tools目录下adb工具
        :return:
        """
        process = subprocess.Popen('adb version', stdout=subprocess.PIPE, shell=True, encoding='utf8')
        result = process.stdout.read()
        if 'Android Debug Bridge version' in result:
            adb_path = "adb"
            return adb_path
        logger.warning('adb not found,use tools adb')
        tools_path = os.path.join(Utils.get_root_dir(), 'tools')
        logger.debug("os platform :" + self.os_platform)
        if self.os_platform == "Windows":
            adb_path = os.path.join(tools_path, "windows", "adb.exe")
        elif self.os_platform == "Darwin":
            adb_path = os.path.join(tools_path, "darwin", "adb")
        else:
            adb_path = os.path.join(tools_path, "linux", "adb")
        return adb_path

    def get_online_device(self):
        """
        获取设备列表，且只获取正常连接设备
        :return:
        """
        result = self.run_adb_cmd('devices')
        result = result.replace('\r', '').splitlines()
        logger.debug("online device_id:")
        logger.debug(result)
        device_list = []
        for device in result[1:]:
            if len(device) <= 1 or '\t' not in device:
                continue
            if device.split('\t')[1] == 'device':
                device_list.append(device.split('\t')[0])
        if not result:
            device_list = self.get_online_device()
        return device_list

    def is_device_connected(self, device_id):
        """
        检查设备是否正常连接
        :param device_id:
        :return:bool
        """
        if device_id in self.get_online_device():
            return True
        else:
            return False

    def wait_device_connected(self, device_id, timeout=120):
        end_time = time.time() + timeout

        while True:
            ret = self.is_device_connected(device_id)
            if ret:
                break

            if time.time() > end_time:
                logger.error(f'{device_id} no connected')
                break
            time.sleep(1)

    @staticmethod
    def process_terminate(process, timeout):
        """
        超时后结束进程
        :param process:
        :param timeout:
        :return:
        """
        end_time = time.time() + timeout
        while process.poll() is None and time.time() < end_time:
            time.sleep(0.2)
        if process.poll() is None:
            logger.debug("process timeout,process terminate,args:%s" % process.args)
            process.terminate()

    @staticmethod
    def shell_process_terminate(process, timeout):
        """
        超时后结束进程
        :param process:
        :param timeout:
        :return:
        """
        end_time = time.time() + timeout
        while process.poll() is None and time.time() < end_time:
            time.sleep(0.2)
        if process.poll() is None:
            logger.debug("process timeout,process terminate,args:%s" % process.args)
            try:
                far_proc = psutil.Process(process.pid)
                for chi_proc in far_proc.children(recursive=True):
                    chi_proc.kill()
                far_proc.kill()
            except Exception as e:
                args = process.args
                logger.warning('process terminate error,args: ' + args)
                logger.debug(e)

    def run_adb_cmd(self, cmd, *args, **kw):
        """
        执行adb命令
        :param cmd:
        :param args:
        :param kw:
        :return:
        """
        if self.device_id:
            # adb 路径 device_id带路径时执行报，需加上“”
            cmd_list = [f'"{self.adb_path}"', '-s', f'"{self.device_id}"', cmd]
        else:
            cmd_list = [f'"{self.adb_path}"', cmd]
        for arg in args:
            cmd_list.append(arg)
        cmd_str = " ".join(cmd_list)
        if self.os_platform == 'Windows':
            cmd_str = cmd_str.replace('grep', 'findstr')
        logger.debug(cmd_str)
        process = subprocess.Popen(cmd_str, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=True)
        if "sync" in kw and kw['sync'] is False:
            return process
        if "timeout" in kw and kw['timeout'] is not None:
            timeout = kw['timeout']
        else:
            timeout = 10
        if timeout > 0:
            terminate_thread = threading.Thread(target=self.shell_process_terminate, args=(process, timeout))
            terminate_thread.start()
        (out, error) = process.communicate()
        if process.poll() != 0:
            if error:
                try:
                    error = error.decode('gbk')
                    logger.error(f'run adb cmd error: {error}')
                except Exception as e:
                    logger.debug(f'decode error: {error} \n {e}')
            else:
                logger.debug('cmd run timeout,process terminate')
        if str(out, "utf-8") == '':
            out = error
        if not isinstance(out, str):
            try:
                out = str(out, "utf8")
            except Exception as e:
                logger.debug(e)
                out = repr(out)
        return out.strip()

    def run_adb_shell_cmd(self, cmd, **kw):
        """
        执行adb shell命令
        :param cmd:
        :param kw:
        :return:
        """
        ret = self.run_adb_cmd('shell', '%s' % cmd, **kw)
        if ret is None:
            logger.error(u'adb cmd failed:%s ' % cmd)
        return ret

    def push_file(self, src_path, dst_path):
        """
        推送文件
        :param src_path: 本地路径
        :param dst_path: 设备路径
        :return:
        """
        file_size = os.path.getsize(src_path)
        if " " in src_path:
            src_path = '"' + src_path + '"'
        for i in range(3):
            result = self.run_adb_cmd('push', src_path, dst_path, timeout=180)
            if result.find('No such file or directory') != -1:
                logger.error('file:%s not exist' % src_path)
            if ('%d' % file_size) in result:
                return result
            logger.error(u'push file failed:%s' % result)

    def pull_file(self, src_path, dst_path):
        """
        拉取文件
        :param src_path:
        :param dst_path:
        :return:
        """
        result = self.run_adb_cmd('pull', src_path, dst_path, timeout=180)
        if result and 'failed to copy' in result:
            logger.error("failed to pull file:" + src_path)
        return result

    def screen_cap(self, save_path):
        """
        截取设备屏幕画面并下载到本地
        :param save_path:
        :return:
        """

        tmp_path = f'/data/local/tmp/screenshot_{Utils.get_current_underline_time()}.png'
        self.run_adb_shell_cmd(f'screencap -p %s' % tmp_path, timeout=20)
        self.pull_file(tmp_path, save_path)

    def remove_file(self, file_path):
        """
        删除设备的上文件
        :param file_path:文件路径
        :return:
        """
        self.run_adb_shell_cmd('rm ' + file_path)

    def is_exist(self, path):
        """
        检查文件是否存在
        :param path:路径
        :return:
        """
        result = self.run_adb_shell_cmd('ls -l %s' % path)
        if not result:
            return False
        if 'no such file or directory' in result.lower():
            return False
        return True

    def mkdir(self, dir_path):
        """
        判断设备上是否存在目录，不存在则创建目录
        :param dir_path:目录路径
        :return:
        """
        result = self.run_adb_shell_cmd('ls ' + dir_path)
        if 'no such file or directory' in result.lower():
            self.run_adb_shell_cmd('mkdir %s' % dir_path)

    def get_dir_file(self, dir_path):
        """
        根据目录名返回目录下的文件信息
        :param dir_path:目录路径
        :return:
        """
        result = self.run_adb_shell_cmd('ls -l %s' % dir_path)
        if not result:
            return ""
        result = result.replace('\r\r\n', '\n')
        if 'No such file or directory' in result:
            logger.error(result)
        file_list = []
        for line in result.split('\n'):
            items = line.split()
            if items[0] != "total" and len(items) != 2:
                file_list.append(items[-1])
        return file_list

    def start_activity(self, activity_name, action='', data_uri='', extra=None, wait=True):
        """
        启动指定activity
        :param activity_name:
        :param action:
        :param data_uri:
        :param extra:
        :param wait:
        :return:
        """
        if action != '':
            action = '-a %s ' % action
        if data_uri != '':
            data_uri = '-d %s ' % data_uri
        extra_str = ''
        if extra:
            for key in extra.keys():
                extra_str += '-e %s %s ' % (key, extra[key])
        w = ''
        if wait:
            w = '-W'

        result = self.run_adb_shell_cmd('am start %s -n %s %s %s %s' % (w, activity_name, action, data_uri, extra_str),
                                        timeout=30)
        if 'Permission Denial' in result:
            return 'Permission Denial'
        ret_dict = {}
        for line in result.splitlines():
            if ': ' in line:
                key, value = line.split(': ')
                ret_dict[key] = value
        return ret_dict

    def start_command_activity(self, command):
        result = self.run_adb_shell_cmd(f'am start -W -d "{command}"')
        ret_dict = {}
        if result:
            for line in result.splitlines():
                if ': ' in line:
                    key, value = line.split(': ')
                    ret_dict[key] = value
            return ret_dict

    def get_focus_window_activity(self, only=True):
        """
        通过dumpsys window获取activity
        :param only: 非True返回activity和dumpsys window结果
        :return:
        """
        activity_name = activity_line = ''
        dumpsys_result = self.run_adb_shell_cmd('dumpsys window')
        dumpsys_result_list = dumpsys_result.split('\n')
        for line in dumpsys_result_list:
            if line.find('mCurrentFocus=Window') != -1:
                activity_line = line.strip()
        if activity_line:
            activity_line_split = activity_line.split(' ')
        else:
            if only:
                return activity_name
            else:
                return activity_name, dumpsys_result
        if len(activity_line_split) > 1:
            if activity_line_split[1] == 'u0':
                activity_name = activity_line_split[2].rstrip('}')
            else:
                activity_name = activity_line_split[1]
        if only:
            return activity_name
        else:
            return activity_name, dumpsys_result

    def get_current_package(self):
        """
        当前activity包名
        :return:
        """
        focus_activity = self.get_focus_window_activity()
        if focus_activity:
            return focus_activity.split("/")[0]
        else:
            return ""

    def get_top_activity(self):
        """
        dumpsys activity top获取当前页面activity名
        :return:
        """
        top_activity = None
        ret = self.run_adb_shell_cmd("dumpsys activity top|grep ACTIVITY")
        if not ret:
            return None
        lines = ret.split("\n")
        lines.reverse()

        for line in lines:
            if "null" in line.lower():
                continue
            line = line.strip()
            logger.debug("dumpsys activity top info line :" + line)
            activity_info = line.split()[1]
            top_activity = activity_info.split("/")[1]
            logger.debug("dump activity top activity:" + top_activity)
            return top_activity
        return top_activity

    def get_main_activity(self, package):
        re_activity = re.compile(r'android.intent.action.MAIN:.+?(%s/.+?Activity)' % package, re.S)

        ret = self.is_app_installed(package)
        if ret:
            dumpsys = self.run_adb_shell_cmd('dumpsys package ' + package)
            match = re_activity.search(dumpsys)
            if match:
                main_activity = match.group(1)
                activity = main_activity.split('/')[-1]
                return activity
            logger.error('%s main activity not found' % package)
        logger.error('%s not installed' % package)

    def get_pid_from_package(self, package):
        """
        ps中通过包名获取pid
        :param package:
        :return:
        """
        pkg_list = self.get_pck_info_from_ps(package)
        if pkg_list:
            return pkg_list[0]["pid"]

    def get_pck_info_from_ps(self, package):
        """
        从ps中获取应用的信息
        :param package:
        :return:
        """
        ps_list = self.get_device_process()
        pck_list = []
        for item in ps_list:
            if item["proc_name"] == package:
                pck_list.append(item)
        return pck_list

    def package_dumpheap(self, package, save_path):
        """
        生成并下载heap dump文件
        :param package:
        :param save_path:
        :return:
        """
        self.try_enable_debuggable()
        heap_file = "/data/local/tmp/%s_dumpheap_%s.hprof" % (package, Utils.get_current_underline_time())
        ret = self.run_adb_shell_cmd("am dumpheap %s %s" % (package, heap_file))
        if 'Process not debuggable' in ret:
            logger.debug('Process not debuggable')
            return 'Process not debuggable'
        time.sleep(10)
        self.pull_file(heap_file, save_path)

    def try_enable_debuggable(self):
        status = self.run_adb_shell_cmd('getprop ro.debuggable')
        if status == '0':
            ret = self.run_adb_shell_cmd('ls /data/local/tmp')
            if 'mprop' not in ret:
                tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)).split('src')[0], 'tools')
                src_path = os.path.join(tools_path, 'mprop')
                dst_path = '/data/local/tmp'
                self.push_file(src_path, dst_path)
                self.run_adb_shell_cmd('chmod 777 /data/local/tmp/mprop')
            process = self.run_adb_shell_cmd('./data/local/tmp/mprop ro.debuggable 1', sync=False)
            process.communicate()

    def pm_clear_package(self, package):
        """
        根据包名清除应用缓存
        :param package:包名
        :return:
        """
        return self.run_adb_shell_cmd("pm clear %s" % package)

    def force_stop_package(self, package):
        """
        根据包名强制停止应用
        :param package:应用包名
        :return:
        """
        return self.run_adb_shell_cmd("am force-stop %s" % package)

    def input_text(self, string):
        """
        输入字符
        :param string:
        :return:
        """
        return self.run_adb_shell_cmd("input text %s" % string)

    def ping_test(self, address, count, timeout=10):
        """
        ping测试
        :param address:ip地址或域名
        :param count:ping包数据
        :param timeout:命令执行超时时间
        :return:
        """
        return self.run_adb_shell_cmd('ping -c %d %s' % (count, address), timeout=timeout)

    def get_system_version(self):
        """
        获取系统版本
        :return:
        """
        system_version = self.run_adb_shell_cmd("getprop ro.build.version.release")
        return system_version

    def get_device_mac(self, inter='eth0', symbol=True):
        """
        获取mac地址
        :return:
        """
        mac = self.run_adb_shell_cmd("cat /sys/class/net/%s/address" % inter)
        if not symbol:
            mac = mac.replace(':', '')
        if mac:
            return mac
        else:
            return ""

    def get_device_serialno(self):
        """
        获取设备序列号
        :return:
        """
        serialno = self.run_adb_shell_cmd("getprop ro.serialno")
        if serialno:
            return serialno
        else:
            return ""

    def get_sdk_version(self):
        """
        获取SDK版本
        :return:
        """
        ret = self.run_adb_shell_cmd('getprop ro.build.version.sdk')
        try:
            sdk_version = int(ret)
            return sdk_version
        except Exception as e:
            logger.debug(e)
            return 19

    def get_devices_product(self):
        """
        获取设备厂家
        :return:
        """
        device_product = self.run_adb_shell_cmd('getprop ro.product.manufacturer')
        return device_product

    def get_devices_brand(self):
        """
        获取设备品牌
        :return:
        """
        device_brand = self.run_adb_shell_cmd('getprop ro.product.brand')
        return device_brand

    def get_devices_model(self):
        """
        获取设备型号
        :return:
        """
        device_model = self.run_adb_shell_cmd('getprop ro.product.model')
        return device_model

    def get_package_version(self, package):
        """
        获取测试包的version信息
        :param package:
        :return:
        """
        code = name = ''
        info = self.run_adb_shell_cmd(f'dumpsys package {package}')
        code_rex = re.compile(r'versionCode=(\d+)').search(info)
        name_rex = re.compile(r'versionName=(.+)').search(info)
        if code_rex:
            code = code_rex.group(1)
        if name_rex:
            name = name_rex.group(1).strip()
        return code, name

    def get_wm_size(self):
        """
        获取屏幕分辨率
        :return:
        """
        string = self.run_adb_shell_cmd('wm size')
        match = re.compile(r'Physical size: (\d+)x(\d+)').match(string)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    def get_cpu_abi(self):
        """
        获取设备的CPU架构
        :return:
        """
        return self.run_adb_shell_cmd('getprop ro.product.cpu.abi')

    def get_process_pid(self, name):
        """
        通过进程名查找进程id
        :param name:进程名
        :return:
        """
        pid_list = []
        process_list = self.get_device_process()
        for process in process_list:
            if process['proc_name'] == name:
                pid_list.append(process['pid'])
        return pid_list

    def is_process_running(self, name):
        """
        判断进程是否存活
        :param name:进程名
        :return:
        """
        process_list = self.get_device_process()
        for process in process_list:
            if name in process['proc_name']:
                return True
        return False

    def get_device_process(self):
        """
        获取设备全部进程列表
        sdk < 26 使用ps 命令，否则使用ps -A 命令
        :return:
        """
        if self.get_sdk_version() < 26:
            result = self.run_adb_shell_cmd('ps')
        else:
            result = self.run_adb_shell_cmd('ps -A')
        result = result.replace('\r', '')
        lines = result.split('\n')
        busy_box = False
        if lines[0].startswith('PID'):
            busy_box = True

        result_list = []
        for i in range(1, len(lines)):
            items = lines[i].split()
            if not busy_box:
                if len(items) < 9:
                    err_msg = "ps命令返回错误：\n%s" % lines[i]
                    if len(items) == 8:
                        result_list.append({'uid': items[0], 'pid': int(items[1]), 'ppid': int(items[2]),
                                            'proc_name': items[7], 'status': items[-2]})
                    else:
                        logger.error(err_msg)
                else:
                    result_list.append({'uid': items[0], 'pid': int(items[1]), 'ppid': int(items[2]),
                                        'proc_name': items[8], 'status': items[-2]})
            else:
                idx = 4
                cmd = items[idx]
                if len(cmd) == 1:
                    idx += 1
                    cmd = items[idx]
                idx += 1
                if cmd[0] == '{' and cmd[-1] == '}':
                    cmd = items[idx]
                ppid = 0
                if items[1].isdigit():
                    ppid = int(items[1])
                result_list.append({'pid': int(items[0]), 'uid': items[1], 'ppid': ppid,
                                    'proc_name': cmd, 'status': items[-2]})
        return result_list

    def kill_process(self, name):
        """
        杀死指定包进程
        :param name:进程名称
        :return:
        """
        pid_list = self.get_process_pid(name)
        if pid_list:
            self.run_adb_shell_cmd('kill ' + ' '.join([str(pid) for pid in pid_list]))

    def is_app_installed(self, package):
        """
        判断app是否安装
        :param package:包名
        :return:bool
        """
        for local_package in self.list_installed_app():
            if package in local_package:
                return True
        return False

    def list_installed_app(self):
        """
        列举设备已安装的应用
        :return:
        """
        result = self.run_adb_shell_cmd('pm list packages')
        result = result.replace('\r', '').splitlines()
        logger.debug(result)
        installed_app_list = []
        for app in result:
            if 'package' not in app:
                continue
            if app.split(':')[0] == 'package':
                installed_app_list.append(app.split(':')[1])
        logger.debug(installed_app_list)
        return installed_app_list

    def _install_apk(self, apk_path, over_install=True, downgrade=False):
        """
        安装apk
        :param apk_path:待安装的apk路径
        :param over_install:强制安装
        :param downgrade:允许安装低版本
        :return:
        """
        timeout = 5 * 60
        tmp_path = '/data/local/tmp/install.apk'
        self.push_file(apk_path, tmp_path)
        cmdline = r'pm install %s %s %s' % ('-r -t' if over_install else '', "-d" if downgrade else "", tmp_path)
        ret = ''
        for i in range(1):
            try:
                ret = self.run_adb_shell_cmd(cmdline, timeout=timeout)
                logger.debug(ret)
                if i > 1 and 'INSTALL_FAILED_ALREADY_EXISTS' in ret:
                    ret = 'Success'
                    break

                if 'INSTALL_PARSE_FAILED_NO_CERTIFICATES' in ret or \
                        'INSTALL_FAILED_INSUFFICIENT_STORAGE' in ret:
                    raise RuntimeError('安装应用失败：%s' % ret)

                if 'INSTALL_FAILED_UID_CHANGED' in ret:
                    logger.error(ret)
                    continue
                if 'Success' in ret or 'INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES' in ret or \
                        'INSTALL_FAILED_ALREADY_EXISTS' in ret:
                    break
            except Exception as e:
                if i >= 2:
                    logger.debug(e)
                    logger.warning('install app failed')
                    ret = self.run_adb_shell_cmd(cmdline, timeout=timeout)
                    logger.debug(ret)
                    if ret and 'INSTALL_FAILED_ALREADY_EXISTS' in ret:
                        ret = 'Success'
        try:
            self.remove_file('/data/local/tmp/*.apk')
        except Exception as e:
            logger.debug(e)
        return ret

    def install_apk(self, apk_path, over_install=True, downgrade=False):
        """
        安装apk
        :param apk_path:待安装的apk路径
        :param over_install:强制安装
        :param downgrade:允许安装低版本
        :return:
        """
        result = self._install_apk(apk_path, over_install, downgrade)
        if 'INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES' in result:
            # 必须卸载安装
            return self.install_apk(apk_path, False, False)
        elif 'INSTALL_FAILED_ALREADY_EXISTS' in result:
            # 卸载成功依然有可能在安装时报这个错误
            return self.install_apk(apk_path, False, True)
        elif 'INSTALL_FAILED_VERSION_DOWNGRADE' in result:
            # 版本低于当前版本时报错
            return self.install_apk(apk_path, True, True)
        elif 'INSTALL_FAILED_UID_CHANGED' in result:
            # 卸载不干净时报错
            logger.debug('INSTALL_FAILED_UID_CHANGED,please ')
        if result.find('Success') >= 0:
            return True
        return False

    def uninstall_apk(self, pkg):
        """
        根据包名卸载apk
        :param pkg:apk包名
        :return:bool
        """
        result = self.run_adb_cmd('uninstall %s' % pkg, timeout=60)
        if result.find('Success') >= 0:
            return True
        return False

    def remount_dire(self, dire='/system'):
        """
        挂载目录
        优先使用remount命令，挂载失败后使用echo修改need_remount文件
        :param dire:目录路径
        :return:
        """
        ret = self.run_adb_cmd('remount')
        if ret == 'remount succeeded':
            return True
        else:
            self.run_adb_shell_cmd(r'"echo 1 > /sys/class/remount/need_remount"')
            ret = self.run_adb_shell_cmd('mount -o remount /system')
            if ret == '':
                return True
            return ret

    def reboot(self, timeout=5):
        """
        重启设备操作，部分设备重启后命令一直不退出
        增加超时参数
        :param timeout: 超时时间，默认5S
        :return:
        """
        self.run_adb_cmd('reboot', timeout=5)

    def list_net_interface(self):
        """
        列出设备可用接口
        :return:
        """
        ret = self.run_adb_shell_cmd('busybox ifconfig')
        if ret.find('not found') != -1:
            ret = self.run_adb_shell_cmd('ifconfig')
        ret_list = ret.split('\r\n')
        if_list = []
        for ret in ret_list:
            if ret.find('HWaddr') != -1:
                if_list.append(ret.split()[0])
        return if_list

    def is_device_root(self):
        """
        检查设备是否已root
        :return:
        """
        ret = self.run_adb_cmd('root')
        if ret.find('running as root') != -1:
            return True
        return False

    def is_tool_install(self, name):
        """
        检查设备下的工具是否安装并返回安装路径
        :return:
        """
        ret = self.run_adb_shell_cmd(f'busybox which {name}')
        if ret.find('not found') == -1:
            return ret

    def local_ip(self):
        output = self.run_adb_shell_cmd('busybox ifconfig')
        if output.find('not found') != -1:
            output = self.run_adb_shell_cmd('ifconfig')
        ip_pattern = r'inet addr:(\d+\.\d+\.\d+\.\d+)'
        for line in output.split('\n'):
            match = re.search(ip_pattern, line)
            if match:
                ip_address = match.group(1)
                if ip_address != '127.0.0.1':
                    return ip_address


class AdbUtils:
    def __init__(self, device_id=None):
        self.adb = None
        self.is_local = AdbUtils.is_local_device(device_id)
        if self.is_local:
            self.adb = ADB(device_id)

    @staticmethod
    def is_local_device(device_id):
        """
        通过device_id判断是否本地设备
        :param device_id:
        :return:
        """
        if not device_id:
            return True
        pattern = re.compile(r'([\w|.]+):(.+)')
        mat = pattern.match(device_id)
        if not mat or ((mat.group(2).isdigit()) and (int(mat.group(2)) > 1024) and (int(mat.group(2)) < 65536)):
            return True
        else:
            return False

    def list_local_devices(self):
        """
        获取设备列表
        :return:
        """
        return self.adb.get_online_device()


if __name__ == '__main__':
    dev = AdbUtils()
    dev.adb.wait_device_connected('MAX00191110002441')

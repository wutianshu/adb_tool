#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import os
import time
import socket
import struct
import threading
from src.log import logger
from config import root_path
from PIL import Image, ImageTk
from collections import OrderedDict


# https://github.com/openatx/stf-binaries/tree/0.3.0/node_modules/%40devicefarmer/minicap-prebuilt/prebuilt/armeabi-v7a/lib/android-30


class MNCInstaller(object):
    def __init__(self, android):
        self.android = android
        self.abi = self.android.adb.get_cpu_abi()
        self.sdk = self.android.adb.get_sdk_version()
        if self.is_mnc_installed():
            logger.info('minicap already existed')
        else:
            self.copy_mnc2device()
            self.copy_mnc_so2device()

    def copy_mnc2device(self):
        src_path = os.path.join(root_path, 'tools', 'minicap-prebuilt', 'prebuilt', self.abi, 'bin', 'minicap')
        dst_path = '/data/local/tmp/minicap'
        self.android.adb.push_file(src_path, dst_path)
        self.android.adb.run_adb_shell_cmd('chmod 777 ' + dst_path)
        logger.info('minicap installed in {}'.format(dst_path))

    def copy_mnc_so2device(self):
        src_path = os.path.join(root_path, 'tools', 'minicap-prebuilt', 'prebuilt', self.abi, 'lib',
                                'android-%s' % self.sdk, 'minicap.so')
        dst_path = '/data/local/tmp/minicap.so'
        self.android.adb.push_file(src_path, dst_path)
        self.android.adb.run_adb_shell_cmd('chmod 777 ' + dst_path)
        logger.info('minicap.so installed in {}'.format(dst_path))

    def is_installed(self, name):
        ret = self.android.adb.run_adb_shell_cmd('ls /data/local/tmp')
        if name in ret.split():
            return True
        return False

    def is_mnc_installed(self):
        ret = self.is_installed('minicap') and self.is_installed('minicap.so')
        return ret


class Banner:
    def __init__(self):
        self.__banner = OrderedDict(
            [('version', 0),
             ('length', 0),
             ('pid', 0),
             ('realWidth', 0),
             ('realHeight', 0),
             ('virtualWidth', 0),
             ('virtualHeight', 0),
             ('orientation', 0),
             ('quirks', 0)
             ])

    def __setitem__(self, key, value):
        self.__banner[key] = value

    def __getitem__(self, key):
        return self.__banner[key]

    def keys(self):
        return self.__banner.keys()

    def __str__(self):
        return str(self.__banner)


class KeyMap:
    key_map = {
        'Up': 19,
        'Down': 20,
        'Left': 21,
        'Right': 22,
        'Escape': 4,
        'Return': 23
    }


class MiniCap(object):
    def __init__(self, android):
        self.android = android
        self.mini_server = None
        self.buffer_size = 4096
        self.banner = Banner()
        self.__socket = None
        self.image_list = []
        self.stop_event = threading.Event()
        self.screenrecord = None
        self.width, self.height = 0, 0
        self.ratio = 0.5

    def get_size(self):
        width, height = self.android.adb.get_wm_size()
        if width and height:
            return int(width), int(height)
        raise ValueError('device wm size get error')

    def creat_minicap_server(self):
        MNCInstaller(self.android)
        screen_size = f'{self.width}x{self.height}@{int(self.width * self.ratio)}x{int(self.height * self.ratio)}/0'
        cmd = 'LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/minicap -P ' + screen_size
        logger.info('minicap server start: {}'.format(cmd))
        process = self.android.adb.run_adb_shell_cmd(cmd, sync=False)
        process.communicate()

    def start_mini_server(self):
        self.width, self.height = self.get_size()
        if self.android.adb.is_process_running('minicap'):
            return True
        self.mini_server = threading.Thread(target=self.creat_minicap_server, daemon=True)
        self.mini_server.start()
        for i in range(20):
            if self.android.adb.is_process_running('minicap'):
                return True
            time.sleep(1)
            logger.info('minicap not start,wait 1S')
        return False

    def stop_mini_server(self):
        self.mini_server.join(timeout=1)
        while True:
            self.android.adb.kill_process('/data/local/tmp/minicap')
            if not self.android.adb.is_process_running('/data/local/tmp/minicap'):
                break
            time.sleep(1)
            logger.info('minicap not start,wait 1S')
        self.mini_server = None

    def minicap_screen_shot(self):
        src_path = '/data/local/tmp/fastcap_temp.png'
        dst_path = os.path.join(root_path, 'result', 'fastcap_temp.png')
        self.android.adb.pull_file(src_path, dst_path)
        logger.info('export screen shot to {}'.format(dst_path))

    def socket_connect(self, host, port):
        try:
            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as e:
            logger.info(e)
        self.__socket.connect((host, port))

    # def image_display(self):
    #     import cv2, numpy as np
    #     self.start_screenrecord()
    #     cv2.namedWindow('screen', cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
    #     cv2.resizeWindow("screen", int(self.width * 0.43), int(self.height * 0.43))
    #     last_image = None
    #     while not self.stop_event.is_set():
    #         if len(self.image_list) == 0 and last_image is None:
    #             file_path = os.path.join(root_path, 'tools', 'screen_img.jpg')
    #             image = cv2.imread(file_path)
    #             last_image = image
    #         elif len(self.image_list) == 0 and last_image is not None:
    #             image = last_image
    #         else:
    #             image = self.image_list.pop(0)
    #             img_string = np.fromiter(image, np.uint8)
    #             image = cv2.imdecode(img_string, cv2.IMREAD_COLOR)
    #             last_image = image
    #         cv2.imshow('screen', image)
    #         ret = cv2.waitKeyEx(1)
    #         if ret != -1:
    #             if str(ret) in KeyMap.key_map.keys():
    #                 value = KeyMap.key_map.get(str(ret))
    #                 t = threading.Thread(target=self.android.adb.run_adb_shell_cmd, args=('input keyevent %s' % value,))
    #                 t.start()
    #         if cv2.getWindowProperty('screen', cv2.WND_PROP_VISIBLE) < 1:
    #             break
    #         if ret == cv2.EVENT_LBUTTONDOWN:
    #             break
    #     cv2.destroyAllWindows()
    #     self.stop_screenrecord()

    def canvas_display(self, canvas):
        self.start_screenrecord()
        last_image = None
        width, height = int(self.width * self.ratio), int(self.height * self.ratio)
        canvas.config(width=width, height=height)

        while not self.stop_event.is_set():
            if len(self.image_list) == 0 and last_image is None:
                file_path = os.path.join(root_path, 'tools', 'screen_img.jpg')
                image = Image.open(file_path)
                image = image.resize((width, height), Image.ANTIALIAS)
                last_image = image
            elif len(self.image_list) == 0 and last_image is not None:
                continue
            else:
                # data = self.image_list.pop(0)
                data = self.image_list[-1]  # 只取最新的一帧，部分盒子全部帧显示时太卡
                self.image_list = []

                im_io = io.BytesIO(data)
                image = Image.open(im_io)
                last_image = image

            image = ImageTk.PhotoImage(image)

            if canvas.winfo_exists():
                canvas.create_image(0, 0, anchor='nw', image=image)
            abc = None
            abc = image  # 解决摄像头图像闪烁的问题..
        self.stop_screenrecord()

    def _screenrecord_thread(self):
        self.android.adb.run_adb_cmd('forward tcp:1717 localabstract:minicap')
        self.socket_connect('localhost', 1717)
        read_banner_bytes = 0
        banner_length = 24
        read_frame_bytes = 0
        frame_body_length = 0
        data = []
        while not self.stop_event.is_set():
            try:
                chunk = self.__socket.recv(self.buffer_size)
            except socket.error as e:
                logger.info(e)
                chunk = ''
            cursor = 0
            buf_len = len(chunk)
            while cursor < buf_len:
                if read_banner_bytes < banner_length:
                    b_list = struct.unpack("<2b5i2b", chunk)
                    for k, v in zip(self.banner.keys(), b_list):
                        self.banner.__setitem__(k, v)
                    cursor = buf_len
                    read_banner_bytes = banner_length
                elif read_frame_bytes < 4:
                    frame_body_length += (chunk[cursor] << (read_frame_bytes * 8)) >> 0
                    cursor += 1
                    read_frame_bytes += 1
                else:
                    if buf_len - cursor >= frame_body_length:
                        data.extend(chunk[cursor:cursor + frame_body_length])

                        data = b''.join(map(lambda x: int.to_bytes(x, 1, 'big'), data))
                        self.image_list.append(data)
                        cursor += frame_body_length
                        frame_body_length = read_frame_bytes = 0
                        data = []
                    else:
                        data.extend(chunk[cursor:buf_len])
                        frame_body_length -= buf_len - cursor
                        read_frame_bytes += buf_len - cursor
                        cursor = buf_len
        logger.info("screenrecord thread stop")

    def start_screenrecord(self):
        logger.info("screenrecord thread start")
        if self.screenrecord is not None:
            self.stop_screenrecord()
        self.stop_event.clear()
        self.screenrecord = threading.Thread(target=self._screenrecord_thread)
        self.screenrecord.start()

    def stop_screenrecord(self):
        if self.screenrecord is not None:
            self.stop_event.set()
            try:
                self.__socket.shutdown(2)
                self.__socket.close()
            except Exception as e:
                logger.debug(e)
            self.screenrecord.join()
            self.screenrecord = None
            self.image_list = []
            time.sleep(1)

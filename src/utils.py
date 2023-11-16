#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time
import platform
import mysql.connector


class Utils:

    @staticmethod
    def get_current_underline_time():
        """
        文件存储时使用
        :return:
        """
        return time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime())

    @staticmethod
    def get_current_time():
        """
        数据采集时时间记录
        :return:
        """
        return time.strftime('%Y-%m-%d %H-%M-%S', time.localtime())

    @staticmethod
    def get_format_time(timestamp):
        """
        时间戳格式化
        :param timestamp:
        :return:
        """
        return time.strftime('%Y-%m-%d %H-%M-%S', time.localtime(timestamp))

    @staticmethod
    def get_current_ms_time():
        """
        monkey日志时间记录
        :return:
        """
        ct = time.time()
        ms = (ct - int(ct)) * 1000
        data_head = time.strftime('%m-%d %H:%M:%S', time.localtime())
        time_stamp = "%s.%03d" % (data_head, ms)
        return time_stamp

    @staticmethod
    def get_time_stamp(time_str, format_str):
        """
        字符转换成时间戳
        :param time_str:
        :param format_str:
        :return:
        """
        time_array = time.strptime(time_str, format_str)
        return time.mktime(time_array)

    @staticmethod
    def get_root_dir():
        """
        获取项目根路径
        :return:
        """
        src_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(src_dir)
        return root_dir

    @staticmethod
    def creat_folder(folder):
        """
        目录不存在时创建目录
        :param folder:
        :return:
        """
        if not os.path.exists(folder):
            os.makedirs(folder)

    @staticmethod
    def get_file_size(path, mb=True):
        size = os.path.getsize(path)
        if mb:
            size = size / float(1024 * 1024)
            return round(size, 2)
        else:
            return size

    @staticmethod
    def get_os_platform():
        """
        获取操作系统平台
        :return:
        """
        os_platform = platform.system()
        return os_platform

    @staticmethod
    def insert_data(query, data):
        # 数据库连接配置
        db_config = {
            'user': 'root',
            'password': '!@#123qwe',
            'host': '172.31.36.149',
            'database': 'devices',
        }
        conn = None
        cursor = None

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            # 插入数据
            #
            cursor.execute(query, data)
            conn.commit()

        except mysql.connector.Error as err:
            print(f"Error: {err}")

        finally:
            if conn is not None and conn.is_connected():
                cursor.close()
                conn.close()



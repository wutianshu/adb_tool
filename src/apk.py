#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import time
import json
import config
import requests
import subprocess
from src.log import logger
from src.monkey import Monkey
from src.adbutils import AdbUtils
from src.perf_test import TempData


class ApkUrl:
    def __init__(self, device_id=None):
        self.device_id = device_id
        self.result_path = None
        self.device = AdbUtils(device_id)

    @staticmethod
    def get_all_apk_id():
        app_list = []
        url = 'http://124.232.135.212:8082/AppStoreTV4/service/brilliantGathering.do'
        data = {'hierarchy': '3', 'userAccount': '6750041'}
        res = requests.post(url, json=data)
        if res.status_code != 200:
            return
        json_data = json.loads(res.text)
        data_list = json_data.get('data')
        for data in data_list:
            app_list.append(dict(name=data.get('name'), appId=data.get('data').get('appId')))
        logger.info(f'apk list:{app_list}')
        return app_list

    @staticmethod
    def get_apk_url(app_id):
        # 电信
        url = 'http://124.232.135.225:8082/AppStoreTV4/getAppInfo.do'
        data = dict(json='{"appId":"%s","userId":"12928483"}' % app_id)

        # 联通
        # url = 'http://iptvstore.hn165.com:8082/AppStoreTV4/getAppInfo.do'
        # data = dict(json='{"model": "HG680-L", "appId": "%s", "userId": "97002151"}' % app_id)

        res = requests.post(url, data=data)
        if res.status_code != 200:
            return
        json_data = json.loads(res.text)
        app_url = json_data.get('AppInfo').get('appUrl')
        logger.info(f'apk download url: {app_url}')
        return app_url

    def download_pkg(self, url):
        """
        文件下载方法，用于软件安装时使用
        :param url:
        :return:
        """
        save_path = os.path.join(config.root_path, 'results')
        self.result_path = save_path
        if not os.path.isdir(save_path):
            os.mkdir(save_path)
        pkg_name = os.path.basename(url)
        dir_file = os.listdir(save_path)
        file_path = os.path.join(save_path, pkg_name)
        if pkg_name in dir_file:
            os.remove(file_path)
        res = requests.get(url)
        if res.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in res.iter_content(100000):
                    f.write(chunk)
            return file_path
        logger.error('apk can not download: %s' % url)

    @staticmethod
    def get_apk_package(pkg_path):
        cmd = 'aapt dump badging %s' % pkg_path
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, encoding='utf8')
        info = process.stdout.read()
        match = re.compile("package: name='(\S+)' versionCode", re.S).search(info)
        if not match:
            raise Exception("get package info error")
        app_package = match.group(1)
        logger.info(f'apk package name: {app_package}')
        return app_package

    def tcp_dump(self, package, timeout=300):
        file_name = package + '.pcap'
        src_path = '/data/local/tmp/' + file_name
        dst_path = self.result_path
        cmd = 'tcpdump -i eth0 -s 0 -w %s' % src_path
        self.device.adb.run_adb_shell_cmd(cmd, timeout=timeout, sync=True)
        self.device.adb.pull_file(src_path, dst_path)
        self.device.adb.remove_file(src_path)

    def start_monkey(self, package):
        config.monkey_cmd = '--pct-majornav 45 --pct-nav 35 --pct-syskeys 5 --pct-motion 5 --pct-appswitch 10 --throttle 2000 -s 1000'
        TempData.result_path = self.result_path
        monkey = Monkey(self.device_id, package, TempData)
        monkey.start()
        self.tcp_dump(package, 300)
        monkey.stop()

    def main(self):
        # data_list = self.get_all_apk_id()
        data_list_yd = [
            [
                '鹅视界',
                'http://hnydiptvimg.yys.mgtv.com:6600/picture/zypt/apk/2022/04/08/20220408185806JH.1.2.1.Y3.6.HNYDIPTV.0.0_Release_2022040716_jiagu.apk'],
            [
                '奇视界',
                'http://hnydiptvimg.yys.mgtv.com:6600/picture/zypt/apk/2022/04/08/20220408185806JH.1.2.1.Y3.6.HNYDIPTV.0.0_Release_2022040716_jiagu.apk'],
            ['MG极速',
             'http://hnydiptvimg.yys.mgtv.com:6600/picture/zypt/apk/2021/08/17/202108171129096.9.0.0_0_5119_2021-08-05_40382442513_iptvHunanRelease.apk'],
            [
                '咪咕快游',
                'http://hnydiptvimg.yys.mgtv.com:6600/picture/zypt/apk/2021/08/17/202108171129096.9.0.0_0_5119_2021-08-05_40382442513_iptvHunanRelease.apk'],
            [
                '芒果教育',
                'http://hnydiptvimg.yys.mgtv.com:6600/picture/zypt/apk/2022/05/12/20220512095525ydiptv_classroom_vc12_vn1.5_com.hniptv.ydiptv.classroom_220421_1208_signed_Aligned.apk'],
            [
                '酷视界',
                'http://hnydiptvimg.yys.mgtv.com:6600/picture/zypt/apk/2022/05/13/20220513094959Wasu_Mgtv_hniptv_mobile_5.6.0.77_202205070938_protect.apk'],
            [
                '嘟嘟学堂',
                'http://10.1.204.6:1002/picture/zypt/apk/2021/12/30/20211230153640DuDuClassHost_V1.7_r_version_1.7.05-release.apk'],
            [
                '移动爱家教育',
                'http://10.1.204.6:1002/picture/zypt/apk/2022/05/25/20220525183426AJJYIPTV-1.1.3-hunan-MGFS.apk'],
            [
                '芒果音乐',
                'http://10.1.204.6:1002/picture/zypt/apk/2021/12/30/20211230152725TV_BASE_KALAOK2_mobile_hunan02_6.7.0_release_20210929_002_signed.apk'],
            [
                '快乐看',
                'http://10.1.204.6:1002/picture/zypt/apk/2022/07/04/20220704161802KLK.2.3.0.Y3.6.HNYDIPTV.0.0_Release_2022070409_jiagu.apk']

        ]
        data_list = [
            {'name': '天翼智家', 'appId': '20260656'},
            {'name': '随心看', 'appId': '27215364'},
            {'name': '家庭健康顾问', 'appId': '20171283'},
            {'name': '快乐看', 'appId': '93527731'},
            {'name': '欢喜首映', 'appId': '28290378'}
        ]
        for data in data_list:
            name = data.get('name')
            if name not in []:
                logger.info(f'start test apk:{name}')
                app_id = data.get('appId')
                apk_url = self.get_apk_url(app_id)
                apk_path = self.download_pkg(apk_url)
                apk_package = self.get_apk_package(apk_path)
                self.device.adb.install_apk(apk_path)
                self.start_monkey(apk_package)
                self.device.adb.uninstall_apk(apk_package)


if __name__ == '__main__':
    apk = ApkUrl('192.168.202.82:5555')
    apk.main()

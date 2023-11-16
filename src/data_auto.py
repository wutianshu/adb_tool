#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy
import json
import time
import queue
import socket
import requests
import threading
from urllib import parse
from src.log import logger
from src.adbutils import ADB
from datetime import datetime


class DataReport:
    def __init__(self, config, fields):
        self.config = config
        self.latest_fields = fields
        self.device_id = self.config.get('device').get('id')
        self.package = self.config.get('device').get('package')
        self.adb = ADB(self.device_id)
        self._stop_event = threading.Event()
        self.data_queue = queue.Queue()
        # self.start_http_server()
        self.report_list = []
        self.last_cntp = None
        self.last_cpid = None
        self.need_new_pv = True
        self.start()

    @staticmethod
    def http_server():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("", 1912))
        server_socket.listen(128)

        logger.debug("Proxy Server Listening on port 1912...")
        try:
            while True:
                client_socket, client_address = server_socket.accept()
                response = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
                client_socket.send(response.encode())
                client_socket.close()
        except Exception as exc:
            logger.error(exc)

    def start_http_server(self):
        t1 = threading.Thread(target=self.http_server, daemon=True)
        t1.start()

    def data_test(self):
        # url = 'http://127.0.0.1:1912/'
        url = 'http://172.31.36.147/'
        proxies = {'http': 'http://127.0.0.1:6666'}
        wait_pv_time = 0
        wait_stay_time = 0
        project = self.config.get('project')

        while not self._stop_event.is_set():
            size = self.data_queue.qsize()
            if size > 0:
                for i in range(size):
                    self.report_list.append(self.data_queue.get())

            if len(self.report_list) > 0:
                # 通过时间调整数据位置
                self.report_list = sorted(self.report_list, key=lambda a: a['current_time'])
                first_data = self.report_list[0]
                logtype = first_data.get('logtype')
                test_field = first_data.get('test_field')
                gain_field = first_data.get('gain_field')

                # 离开播放页时stop、hb事件晚于stay上报、show延时发送
                current_time = first_data.get('current_time')
                diff = current_time - int(time.time()*1000)
                if diff > 0:
                    time.sleep(diff/1000)
                    continue

                # 离开当前页面时会有pv优先于stay上报的现象
                if not self.need_new_pv and logtype == 'pv' and wait_stay_time < 1000:
                    logtype_list = [i['logtype'] for i in self.report_list]
                    if 'stay' in logtype_list:
                        index = logtype_list.index('stay')
                        self.report_list[index]['current_time'] = current_time-1
                    time.sleep(0.05)
                    wait_stay_time += 50
                    continue

                # stay后等待pv上报，iptv进入详情页时splay等上报会先于pv上报
                if wait_pv_time - time.time() > 0:
                    if self.need_new_pv and logtype != 'pv':
                        logtype_list = [i['logtype'] for i in self.report_list]
                        if 'pv' in logtype_list:
                            index = logtype_list.index('pv')
                            self.report_list[index]['current_time'] = current_time-1
                        continue
                elif wait_pv_time != 0:
                    # 特殊情况无PV或同时上报多个PV，OTT全屏切集
                    try:
                        requests.post(f'{url}need_pv', json={}, proxies=proxies, timeout=3)
                    except Exception as e:
                        logger.debug(e)
                    self.need_new_pv = False
                    wait_pv_time = 0
                self.report_list.pop(0)
                text = self.field_batch(test_field, gain_field)
                try:
                    requests.post(f'{url}{logtype}', json=text, proxies=proxies, timeout=3)
                except Exception as e:
                    logger.debug(e)

                if logtype == 'pv':
                    self.latest_fields['cntp'] = test_field.get('cntp', '')
                    self.latest_fields['cntpid'] = test_field.get('cntpid', '')
                    self.latest_fields['cpid'] = test_field.get('cpid', '')
                    if project == 'IPTV':
                        self.latest_fields['lastp'] = test_field.get('lastp', '')
                        self.latest_fields['lastpid'] = test_field.get('lastpid', '')
                    self.need_new_pv = False
                    wait_pv_time = 0
                elif logtype == 'stay':
                    if project == 'OTT':
                        self.latest_fields['lastp'] = test_field.get('cntp', '')
                        self.latest_fields['fpn'] = test_field.get('cntp')
                        self.latest_fields['fpid'] = test_field.get('cpid')
                    self.need_new_pv = True
                    wait_pv_time = time.time() + 10
                    wait_stay_time = 0

                # logger.info(f'{logtype},gain:{gain_field}')
                # logger.info(f'{logtype},latest:{self.latest_fields}')
            else:
                time.sleep(0.1)

    def start(self):
        logger.debug("data report test start")
        self.data_test_thread = threading.Thread(target=self.data_test)
        self.data_test_thread.setDaemon(True)
        self.data_test_thread.start()

    def stop(self):
        pass

    def field_batch(self, input_data, gain_field):
        out_data = dict(error={}, private={}, common={}, normal={}, ignore={})
        project = self.config.get('project')
        if self.config.get('not_int'):
            for k1, v1 in input_data.items():
                if isinstance(v1, int):
                    input_data[k1] = str(v1)
        common_keys = self.config.get(project).get('common')
        for key, value in input_data.items():
            if key in common_keys:
                self.field_check(out_data, input_data, gain_field, 'common', key, value)
            elif key in self.config.get(project).get('ignore'):
                out_data['ignore'][key] = value
            else:
                self.field_check(out_data, input_data, gain_field, 'private', key, value)
        if self.config.get('primitive'):
            out_data.update(dict(primitive=input_data))
        if self.config.get('lack'):
            for key in common_keys:
                if key not in input_data:
                    out_data['error'][key] = 'not exist'
        return out_data

    def field_check(self, out_data, input_data, gain_field, genre, key, value):
        project = self.config.get('project')
        field_value = self.config.get(project).get(genre).get(key)
        if field_value is None:
            out_data[genre][key] = value
            return

        func_name = str(field_value).split('-')[0]
        func = getattr(self, str(func_name), None)
        if func is not None:
            try:
                if key == 'lob':
                    self.lob_compare(out_data, input_data, gain_field, value)
                    return
                func(key, input_data, gain_field)
                out_data['normal'][key] = value
            except AssertionError as e:
                if str(e):
                    value = f'{value} ({str(e)})'
                    out_data['error'][key] = value
                else:
                    out_data[genre][key] = value
            except Exception as e:
                logger.error(f'{str(key)} compare error: {str(e)}')
        else:
            if field_value == value:
                out_data['normal'][key] = value
            else:
                out_data['error'][key] = f'{value} ({field_value} ?))'

    @staticmethod
    def keys2value(input_data, *args):
        for arg in args:
            value = input_data.get(arg)
            if value:
                return value

    @staticmethod
    def inter_compare(key, input_data, gain_field):
        text = input_data.get(key)
        if key not in gain_field:
            assert False
        value = gain_field.get(key)
        assert text == value, f'{value} ?'

    def inter_latest_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        if key not in self.latest_fields:
            assert False
        value = self.latest_fields.get(key)
        assert text == value, f'{value} ?'

    def time_compare(self, key, input_data, gain_field):
        project = self.config.get('project')
        field_value = self.config.get(project).get('common').get(key)
        if not field_value:
            field_value = self.config.get(project).get('private').get(key)
        num = field_value.split('-')[-1]
        if not num and not num.isdigit():
            logger.error('time compare no num')
            return

        text = input_data.get(key)
        if num == '14':
            dt = datetime.strptime(text, '%Y%m%d%H%M%S')
        else:
            dt = datetime.strptime(text, '%Y%m%d%H%M%S%f')
        assert isinstance(text, str), 'not str'
        assert len(text) == int(num), f'length is not {num}'
        current_time = datetime.now()
        time_diff = current_time - dt
        assert time_diff.total_seconds() <= 5, 'time diff <= 5'

    def ver_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('aver')
        if text != value or not value:
            _, value = self.adb.get_package_version(self.package)
            self.latest_fields['aver'] = value
        assert value in text, f'{value} ?'

    def bid_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        logtype = input_data.get('logtype')
        assert logtype, 'logtype not exist'

        project = self.config.get('project')
        log_cfg = self.config.get(project).get('fixed').get(logtype)
        assert log_cfg, 'fixed config not exist'

        value = log_cfg.get(key)
        assert value == text, f'{value} ?'

    def domain_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        logtype = input_data.get('logtype')
        assert logtype, 'logtype not exist'

        project = self.config.get('project')
        log_cfg = self.config.get(project).get('fixed').get(logtype)
        assert log_cfg, 'fixed config not exist'

        value = log_cfg.get(key)
        assert value, f'fixed config {key} not exist?'
        assert value in text, f'{value} ?'

    def method_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        logtype = input_data.get('logtype')
        assert logtype, 'logtype not exist'

        project = self.config.get('project')
        log_cfg = self.config.get(project).get('fixed').get(logtype)
        assert log_cfg, 'fixed config not exist'

        value = log_cfg.get(key)
        assert value, f'fixed config {key} not exist?'
        assert value == text, f'{value} ?'

        _json = input_data.get('_json')

        if text == 'POST':
            assert _json, f'json ?'

    def did_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('did')
        if text != value or not value:
            value = self.adb.get_device_mac(symbol=False).upper()
            self.latest_fields['did'] = value
        assert text == value, f'{value} ?'

    def serialno_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('did')
        if text != value or not value:
            value = self.adb.run_adb_shell_cmd("getprop ro.serialno")
            self.latest_fields['did'] = value
        assert text == value, f'{value} ?'

    def localip_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('localip')
        if text != value or not value:
            value = self.adb.local_ip()
            self.latest_fields['localip'] = value
        assert text == value, f'{value} ?'

    def mf_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('mf')
        if text != value or not value:
            value = self.adb.get_devices_product()
            self.latest_fields['mf'] = value
        assert text == value, f'{value} ?'

    def mod_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('mod')
        if text != value or not value:
            value = self.adb.get_devices_model()
            self.latest_fields['mod'] = value
        assert text == value, f'{value} ?'

    def sver_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = gain_field.get('sver')
        if text != value or not value:
            value = self.adb.get_system_version()
            self.latest_fields['sver'] = value
        assert text == value, f'{value} ?'

    def cpid_compare(self, key, input_data, gain_field):
        cntp = input_data.get('cntp')
        text = input_data.get(key)
        if cntp in ['I', 'IX']:
            value = gain_field.get('videoId', '')
            assert text == value, f'{value} ?'
            return
        elif cntp in ['theme_home', 'theme_splay']:
            value = gain_field.get('partId', '')
            assert text == value, f'{value} ?'
            return
        logtype = input_data.get('logtype')
        if logtype == 'pv':
            assert False

        value = self.latest_fields.get(key, '')
        assert text == value, f'{value} ?'

    def cntpid_compare(self, key, input_data, gain_field):
        cntp = input_data.get('cntp')
        text = input_data.get(key)
        if cntp in ['v_play', 'v_trylook']:
            value = gain_field.get('importId', '')
            assert text == value, f'{value} ?'
            return
        elif cntp in ['live_player']:
            value = self.latest_fields.get('channelId', '')
            assert text == value, f'{value} ?'
            return
        logtype = input_data.get('logtype')
        if logtype == 'pv':
            assert False

        value = self.latest_fields.get(key, '')
        assert text == value, f'{value} ?'

    @staticmethod
    def sct_compare(key, input_data, gain_field):
        cntp = input_data.get('cntp')
        text = input_data.get(key)
        if cntp in ['IX', 'theme_home', 'A']:
            assert text != 2, f'2 ?'
        else:
            assert text != 1, f'1 ?'

    def uvip_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        uuid = input_data.get('uuid')
        if key not in self.latest_fields:
            assert text == '0', '0 ?'
        elif uuid and uuid.startswith('mgtvmac'):
            assert text == '0', '0 ?'
        else:
            self.inter_compare(key, input_data, gain_field)

    def lob_compare(self, out_data, input_data, gain_field, value):
        if not value:
            return
        lob_dict = dict(error={}, private={}, normal={})
        value = parse.unquote(value)
        try:
            query_dict = json.loads(value)
        except json.JSONDecodeError:
            query_dict = dict(parse.parse_qsl(value))
        except Exception as e:
            logger.error(e)
            out_data['private']['lob'] = value
            return
        # 列表+字典暂不考虑兼容，例如：appls
        if isinstance(query_dict, list):
            out_data['private']['lob'] = value
            return

        input_data_copy = copy.deepcopy(input_data)
        input_data_copy.pop('lob', None)
        input_data_copy.update(query_dict)
        for k, v in query_dict.items():
            project = self.config.get('project')
            field_value = self.config.get(project).get('private').get(k)
            if field_value is None:
                lob_dict['private'][k] = v
                continue

            func = getattr(self, field_value, None)
            if func is not None:
                try:
                    # 将嵌套的lob移到原始数据中，可能全部func才能执行？
                    func(k, input_data_copy, gain_field)
                    lob_dict['normal'][k] = v
                except AssertionError as e:
                    if str(e):
                        v = f'{v} ({str(e)})'
                        lob_dict['error'][k] = v
                        logger.debug(k)
                        logger.debug(f'lob value: {value}')
                    else:
                        lob_dict['private'][k] = v
                except Exception as e:
                    logger.error(f'{str(k)} compare error: {str(e)}')
                    logger.debug(f'unknown error:lob value: {value}')

            else:
                if field_value == v:
                    lob_dict['normal'][k] = v
                else:
                    lob_dict['error'][k] = v
            # elif k not in self.fields:
            #     lob_dict['private'][k] = v
            # else:
            #     field_value = self.fields.get(k)
            #     if v == field_value:
            #         lob_dict['normal'][k] = v
            #     else:
            #         lob_dict['error'][k] = f'{v} ({field_value} ?)'

        for k, v in lob_dict.items():
            if v is not None and bool(v):
                v = dict(sorted(v.items()))
                out_data[k]['lob'] = v

    @staticmethod
    def empty_compare(key, input_data, gain_field):
        text = input_data.get(key, '')
        assert len(str(text)) > 0, '?'

    def cid_compare(self, key, input_data, gain_field):
        cntp = input_data.get('cntp')
        logtype = input_data.get('logtype')
        if cntp == 'A' and logtype == 'pv':
            assert False
        self.inter_compare(key, input_data, gain_field)

    @staticmethod
    def ignore_logtype_field(key, input_data, gain_field, logtype_list, valuable=True):
        text = input_data.get(key)
        if valuable:
            assert text, f'{key} not exist'

        if input_data.get('logtype') in logtype_list:
            assert False
        value = gain_field.get(key, '')
        assert text == value, f'{value} ?'

    def cntp_compare(self, key, input_data, gain_field):
        self.ignore_logtype_field(key, input_data, self.latest_fields, ['pv'])

    def lastp_compare(self, key, input_data, gain_field):
        project = self.config.get('project')
        if project == 'IPTV':
            self.ignore_logtype_field(key, input_data, self.latest_fields, ['pv'], False)

    def lastpid_compare(self, key, input_data, gain_field):
        self.ignore_logtype_field(key, input_data, self.latest_fields, ['pv'], False)

    def vloc_compare(self, key, input_data, gain_field):
        self.ignore_logtype_field(key, input_data, gain_field, ['click'], False)

    def vipdc_compare(self, key, input_data, gain_field):
        self.ignore_logtype_field(key, input_data, gain_field, ['click'], False)

    def suuid_compare(self, key, input_data, gain_field):
        self.ignore_logtype_field(key, input_data, gain_field, ['cp1'], True)

    def paid_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        value = self.latest_fields.get(key, '')

        if input_data.get('logtype') == 'pv':
            assert len(value) == 32, 'length is not 32'
        elif input_data.get('logtype') in ['stay', 'stop', 'hb']:
            value = gain_field.get(key, '')

        assert text == value, f'{value} ?'

    def len_compare(self, key, input_data, gain_field):
        project = self.config.get('project')
        field_value = self.config.get(project).get('common').get(key)
        if not field_value:
            field_value = self.config.get(project).get('private').get(key)
        num = field_value.split('-')[-1]
        if not num.isdigit():
            assert False, 'length not specified'

        text = input_data.get(key)
        assert len(text) == int(num), f'length is not {num}'

    @staticmethod
    def uvip_iptv_compare(key, input_data, gain_field):
        text = input_data.get(key)
        uvip = gain_field.get(key)
        if uvip:
            assert text == uvip, '1 ?'
        else:
            assert text == '0', '0 ?'

    def abt_compare(self, key, input_data, gain_field):
        self.ignore_logtype_field(key, input_data, gain_field, ['dhb'], False)

    def cf_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        project = self.config.get('project')
        if project == 'IPTV':
            if input_data.get('pt') in ['2', '5']:
                assert text == '0', '0 ?'
            else:
                self.inter_compare(key, input_data, gain_field)
        else:
            self.inter_compare(key, input_data, gain_field)

    def def_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        project = self.config.get('project')
        if project == 'IPTV':
            if input_data.get('pt') in ['2', '5']:
                assert text == '', ' ?'
            else:
                self.inter_compare(key, input_data, gain_field)
        else:
            self.inter_compare(key, input_data, gain_field)

    def isfree_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        project = self.config.get('project')
        if project == 'IPTV':
            if input_data.get('pt') in ['2', '5']:
                assert text == '0', '0 ?'
            else:
                value = gain_field.get('isFree')
                assert text == value, f'{value} ?'
        else:
            self.inter_compare(key, input_data, gain_field)

    def istry_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        project = self.config.get('project')
        if project == 'IPTV':
            if input_data.get('pt') in ['2', '5']:
                assert text == '0', '0 ?'
            else:
                is_preview = gain_field.get('isPreview')
                if text == '0':
                    assert is_preview == '0', '0 ?'
                else:
                    assert is_preview != '0', '1 ?'
        else:
            errno = gain_field.get('errno')
            preview = gain_field.get('preview')
            if text == '0':
                assert errno == '0', '1 ?'
            else:
                assert preview == '1' and errno != '0', '0 ?'

    def pay_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        project = self.config.get('project')
        if project == 'IPTV':
            if input_data.get('pt') in ['2', '5']:
                assert text == '0', '0 ?'
            else:
                is_free = gain_field.get('isFree')
                is_preview = gain_field.get('isPreview')
                if text == '0':
                    assert is_free == '0' or is_preview == '0', '1 ?'
                else:
                    assert is_free != '0', '0 ?'
        else:
            errno = gain_field.get('errno')
            preview = gain_field.get('preview')
            if text == '0':
                assert errno == '0', '0 ?'
            else:
                assert errno != '0' or preview == '1', '0 ?'

    def vid_compare(self, key, input_data, gain_field):
        text = input_data.get(key)
        project = self.config.get('project')
        if project == 'IPTV':
            if input_data.get('pt') in ['2', '5']:
                assert text == '', ' ?'
            else:
                value = gain_field.get('vid')
                assert text == value, f'{value} ?'


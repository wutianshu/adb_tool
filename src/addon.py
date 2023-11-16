#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import copy
import json
import time
import yaml
import requests
import threading
import urllib.parse
from os.path import join
from config import root_path
from src.log import logger
from mitmproxy.script import concurrent
from src.data_auto import DataReport


class MapObj:
    def __init__(self, local):
        try:
            self.scheme = local.get('from').get('scheme')
            self.host = local.get('from').get('host')
            self.port = local.get('from').get('port')
            self.path = local.get('from').get('path')
            qsl = urllib.parse.parse_qsl(local.get('from').get('query'), keep_blank_values=True)
            self.query = {}
            for key, value in qsl:
                self.query[key] = value
            self.method = 'GET'
            self.dest = local.get('to').get('dest')
            self.body = local.get('to').get('body')
            self.status = local.get('to').get('status')
        except AttributeError:
            logger.error('map init error')


class DpProxy:
    session = None
    ott_cfg = []
    proxy_cfg = {}
    res_handle = ['ott_start_handle']
    data_path = join(root_path, 'tools')
    param = None
    fields = {}
    config = {}

    def __init__(self):
        self.config.update(self.load_config())
        self.proxy_cfg.update(self.load_proxy_config())
        self.data_report = DataReport(self.config, self.fields)
        self.thread_update_config()

    def load_config(self):
        with open(join(self.data_path, 'config.yml'), encoding="utf-8") as file:
            try:
                return yaml.load(file, Loader=yaml.FullLoader)
            except Exception as e:
                logger.debug(e)

    def load_proxy_config(self):
        with open(join(self.data_path, 'proxy.json'), encoding="utf-8") as file:
            try:
                return json.loads(file.read(), encoding='utf8')
            except Exception as e:
                logger.debug(e)

    def update_config(self):
        while True:
            config = self.load_config()
            if config and config != self.config:
                self.config.update(config)
            proxy_cfg = self.load_proxy_config()
            if proxy_cfg and proxy_cfg != self.proxy_cfg:
                self.proxy_cfg.update(proxy_cfg)
            time.sleep(10)

    def thread_update_config(self):
        t = threading.Thread(target=self.update_config, daemon=True)
        t.start()

    @classmethod
    def get_cipher_config(cls, data, codec):
        e_pack = 'http://inottuni.ng.imgo.tv/v1/inside/encrypto'
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'}
        form = dict(mtype=2, codec=codec, pack=data)
        try:
            res = requests.post(e_pack, headers=headers, data=form)
            json_data = json.loads(res.text, encoding='utf8')
            if json_data.get('code') == 200:
                plaintext = json_data.get('data')
                return plaintext
            else:
                logger.error(res.text)
        except Exception as e:
            logger.error(f'get_test_cipher_config: {e}')

    @classmethod
    def ott_start_handle(cls, res, flow, _from):
        if 'getConfig' not in _from.path:
            return res
        if cls.ott_cfg:
            for cfg in cls.ott_cfg:
                res = json.dumps(json.loads(res, encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
                res = cls.sub_json(cfg[0], cfg[1], res)
        codec = flow.request.query.get('codec')
        if codec:
            for i in range(5):
                text = cls.get_cipher_config(res, codec)
                if text:
                    body = '{"data":"%s","errno":"0","msg":"success","serverTime":1610359693}' % text
                    return body
                logger.warning('cipher text return null')
                cls.session = None
            raise ValueError('ott start handle not effective')
        else:
            return '{"data":%s,"errno":"0","msg":"success","serverTime":1610359693}' % res

    @classmethod
    def get_proxy_value(cls, key):
        value = cls.proxy_cfg.get(key)
        return value

    @classmethod
    def set_map_switch(cls, map_type, status):
        if status == 'enable':
            cls.proxy_cfg[map_type] = 1
        else:
            cls.proxy_cfg[map_type] = 0

    @classmethod
    def set_ott_cfg(cls, *args):
        if len(args) > 0:
            if args not in cls.ott_cfg:
                cls.ott_cfg.append(args)
        else:
            cls.ott_cfg = []

    @staticmethod
    def sub_json(pattern, repl, string):
        # string = json.dumps(json.loads(string, encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
        string, count = re.subn(pattern, repl, string)
        if count == 0:
            logger.warning(f'配置文件中该配置不存在：{pattern}')
        elif count > 1:
            logger.warning(f'配置文件中该配置存在多个：{pattern}')
        return string

    @staticmethod
    def get_field_value(key: str, text: str):
        key_list = key.split('~')
        if len(key_list) > 1:
            key, num = key_list[0], int(key_list[1])
        else:
            key, num = key_list[0], 0
        pattern = r'"%s":\s?("[^"]+"|\d+)' % key
        # lob字段中存在转义符
        text = text.replace('\\', '')
        match = re.search(pattern, text)
        value = ''
        if match:
            value_list = match.groups()
            value = value_list[num]
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
                value = value.encode().decode('unicode_escape')
            # elif value.isdigit():
            #     value = int(value)
        return value

    def set_field_value(self, text, keys, not_null=True):
        self.clear_fields_value(keys)
        for key in keys:
            # 正则匹配时多个相同结果时使用~分隔指定位置
            key = key.split('~')[0]
            value = self.get_field_value(key, text)
            if not_null and value == '':
                continue
            self.fields[key] = value
            self.add_alias_field(key, value)

    def get_request_params(self, request, key):
        if request.method == 'GET':
            value = request.query.get(key, '')
        elif request.method == 'POST':
            content_type = request.headers.get('Content-Type')
            if 'x-www-form-urlencoded' in content_type:
                value = request.urlencoded_form.get(key, '')
            elif 'json' in content_type:
                text = request.text
                value = self.get_field_value(key, text)
            else:
                raise ValueError(f'request content type not support:{content_type}')
        elif request.method == 'OPTIONS':
            logger.debug('OPTIONS has no parameters')
            return
        else:
            logger.error(f'method not support:{request.url}, {request.method}')
            return
        return value

    def get_response_params(self, response, key):
        content_type = response.headers.get('Content-Type')
        if 'json' in content_type:
            text = response.text
            value = self.get_field_value(key, text)
            return value
        raise ValueError(f'response, content type not support:{content_type}')

    @classmethod
    def is_param_correct(cls, key):
        if cls.param is not None:
            if key in cls.param:
                return True
            logger.error(f'param incorrect {cls.param}')
            return False
        elif key == 'None':
            return True
        else:
            logger.error('param not exist')

    def get_logtype(self, request):
        logtype = self.get_request_params(request, 'logtype')
        if not logtype:
            logtype = self.get_request_params(request, 'act')
        return logtype

    @classmethod
    def reset_param(cls):
        cls.param = None

    def clear_fields_value(self, fields):
        for field in fields:
            project = self.config.get('project')
            alias = self.config.get(project).get('alias')
            alias_list = alias.get(field)
            if alias_list:
                for alias in alias_list:
                    self.fields[alias] = ''

    def add_alias_field(self, field_name, field_value):
        project = self.config.get('project')
        alias = self.config.get(project).get('alias')
        alias_list = alias.get(field_name)
        if alias_list:
            for alias in alias_list:
                self.fields[alias] = field_value

    def param2field(self, flow, value):
        content_type = flow.request.headers.get('Content-Type', '')
        if 'json' in content_type:
            text = flow.request.text
        elif 'x-www-form-urlencoded' in content_type:
            text = json.dumps(dict(flow.request.urlencoded_form))
        else:
            text = json.dumps(dict(flow.request.query))
        self.set_field_value(text, value)

    @staticmethod
    def sort_parameters(flow):
        if '127.0.0.1' in flow.request.url or '172.31.36.147' in flow.request.url:
            # 重复排序
            return
        sorted_params = []
        if flow.request.method == "GET":
            sorted_params = sorted(flow.request.query.items())
            flow.request.query = sorted_params
        elif flow.request.method == "POST":
            if flow.request.urlencoded_form:
                sorted_params = sorted(flow.request.urlencoded_form.items())
                flow.request.urlencoded_form = sorted_params
            else:
                try:
                    text = flow.request.text
                    if text:
                        json_obj = json.loads(text)
                        if isinstance(json_obj, dict):
                            sorted_params = sorted(json_obj.items())
                        elif isinstance(json_obj, list):
                            logger.debug('param not sort,cause param type is list')
                        else:
                            logger.error(f'param sort error,unknown param type:{flow.request.url}')
                        if sorted_params:
                            flow.request.text = json.dumps(dict(sorted_params))
                    else:
                        logger.debug(f'no text in param:{flow.request.url}')
                except json.JSONDecodeError:
                    logger.debug(f'param sort format error:{flow.request.url}')
                except Exception as e:
                    logger.error(f'param sort error:{flow.request.url}:{e}')
        elif flow.request.method == "OPTIONS":
            logger.debug(f'method options no param:{flow.request.url}')
        else:
            logger.error(f'method no param:{flow.request.url}')
        return sorted_params

    def is_flow_match(self, request, _from):
        if request.scheme != _from.scheme and _from.scheme:
            return False
        if request.host != _from.host and _from.host:
            return False
        if request.port != _from.port and _from.port:
            return False
        if not re.search(_from.path, request.path) and _from.path:
            return False

        for key, value in _from.query.items():
            params = self.get_request_params(request, key)
            if 'contain_' in value:
                if value.split('_')[-1] not in params:
                    return False
            elif 'not_' in value and 'not_' not in params:
                if value.split('_')[-1] in params:
                    return False
            else:
                if value != params:
                    return False
        return True

    @concurrent
    def request(self, flow):
        if not self.get_proxy_value('remote'):
            return
        if flow.request.method == 'OPTIONS':
            return
        remote_list = self.get_proxy_value('remote_list')
        request = flow.request
        sorted_params = None
        if self.config.get('sort'):
            sorted_params = self.sort_parameters(flow)
        for remote in remote_list:
            _from = remote.get('from')
            ret = self.is_flow_match(request, MapObj(remote))
            if ret:
                to = remote.get('to')
                for key, value in to.items():
                    if key and value:
                        if key == 'headers':
                            for k, v in value.items():
                                request.headers[k] = v
                        elif key == 'delay':
                            time.sleep(value)
                        elif key == 'param':
                            self.param2field(flow, value)
                        elif key == 'report':
                            current_time = int(time.time()*1000)
                            if sorted_params is None:
                                sorted_params = self.sort_parameters(flow)
                            if not sorted_params:
                                logger.error(f'sorted params is None:{str(remote)}')
                                return
                            domain = request.url
                            method = request.method
                            _json = False
                            logtype = self.get_logtype(request)
                            if logtype in ['cmc', 'stop', 'heartbeat', 'click', 'resume', 'pause', 'tvappclick']:
                                pass
                            else:
                                current_time += 1000
                            if method == 'POST':
                                content_type = request.headers.get('Content-Type')
                                if 'json' in content_type:
                                    _json = True
                                if logtype and self.config.get('display'):
                                    flow.request.url = domain + '.' + logtype
                            else:
                                if logtype and self.config.get('display'):
                                    flow.request.url = domain.replace('?', f'.{logtype}?')

                            field_dict = dict(sorted_params)
                            field_dict.update(dict(_domain=domain, _method=method, _json=_json))

                            if 'cpn' in field_dict and not field_dict.get('cntp'):
                                field_dict['cntp'] = field_dict['cpn']
                            if 'fpn' in field_dict and not field_dict.get('lastp'):
                                field_dict['lastp'] = field_dict['fpn']
                            if 'act' in field_dict and not field_dict.get('logtype'):
                                field_dict['logtype'] = field_dict['act']

                            self.data_report.data_queue.put({
                                'logtype': logtype,
                                'test_field': field_dict,
                                'gain_field': copy.deepcopy(self.fields),
                                'current_time': current_time

                            })

    @concurrent
    def response(self, flow):
        if not self.get_proxy_value('local'):
            return
        flow.response.headers['Access-Control-Allow-Origin'] = '*'
        if flow.request.method == 'OPTIONS':
            flow.response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            flow.response.status_code = 200
            return
        local_list = self.get_proxy_value('local_list')
        for local in local_list:
            ret = self.is_flow_match(flow.request, MapObj(local))
            if ret:
                for key, value in local.get('to').items():
                    flow.response.headers[key] = str(value).encode("unicode_escape")
                    if key == 'dest':
                        file_path = join(self.data_path, value)
                        with open(file_path, 'r', encoding='utf8') as f:
                            try:
                                res = f.read()
                                for handle in self.res_handle:
                                    res = getattr(self, handle)(res, flow, MapObj(local))
                                flow.response.set_text(res)
                            except Exception as e:
                                logger.error(f"local map error:{str(e)},dest:{value}")
                    elif key == 'param':
                        self.param2field(flow, value)
                    elif key == 'body':
                        text = flow.response.text
                        self.set_field_value(text, value)
                    elif key == 'status':
                        flow.response.status_code = int(value)
                    elif key == 'delay':
                        time.sleep(value)
                    else:
                        raise ValueError(f'map local not support:{key},{value}')
                return


addons = [DpProxy()]

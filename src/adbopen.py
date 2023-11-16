#!/usr/bin/env python
# -*- coding: utf-8 -*-


class AdbOpen:
    adb_info = [
        {'factory': '海信', 'list': [
            {'model': 'IP906H', 'method': '数字键1473692580'},
            {'model': 'IP116H', 'method': '数字键1473692580'},
            {'model': 'IP116H-F', 'method': '数字键1473692580'},
            {'model': '4KP60IP116H', 'method': '数字键1473692580'}
        ]},
        {'factory': '天邑', 'list': [
            {'model': 'TY1608', 'method': '设置页面-OK键+2323'},
            {'model': 'TY1612', 'method': '#123456#'},
            {'model': 'TY1208-Z', 'method': '设置页面-信息键+2323'}
        ]},
        {'factory': '杰赛', 'list': [
            {'model': 'S65', 'method': '1、电信数字键17935\n2、联通数字键19735'}
        ]},
        {'factory': '中兴', 'list': [
            {'model': '所有', 'method': '邮件发中兴刘实liu.shi@zte.com.cn授权开启ADB'},
        ]},
        {'factory': '华为', 'list': [
            {'model': '所有', 'method': '华为STB工具'},
        ]},
        {'factory': '长虹', 'list': [
            {'model': 'IHO-3300AD', 'method': '"*#06066#"打开adb'},
            {'model': 'IHO-3000', 'method': '设置 > 输入456555 > 点击确认按钮 > 打开ADB'},
            {'model': 'H-3300', 'method': '设置键输入456555'},
        ]},
        {'factory': '烽火', 'list': [
            {'model': 'HG680-KA', 'method': '设置键-软件版本信息-按5下确认键'},
            {'model': 'HG680-J', 'method': '设置键-软件版本信息-按5下确认键打开开发者模式，再进入高级设备ADB服务开启ADB'},
            {'model': 'HG680-L', 'method': '设置键-输入“#600498#”打开adb'},
            {'model': 'IP116H-F', 'method': '数字键1473692580'}
        ]},
        {'factory': '九洲', 'list': [
            {'model': '所有', 'method': '上下左右确定'},
        ]},
        {'factory': '新魔百和', 'list': [
            {'model': 'M301A', 'method': '黄蓝黄蓝'},

        ]},
        {'factory': '咪咕盒子', 'list': [
            {'model': 'MGV2000', 'method': '移动IPTV平台：上下左右确认菜单\n移动OTT平台：找张卓开ADB'},
            {'model': 'CM201-2', 'method': '上上下下左左右右okokokok'},
            {'model': 'UNT400B', 'method': '绿->黄->绿->黄'},

        ]},
        {'factory': '九联', 'list': [
            {'model': 'PTV-8508', 'method': 'adb connect xxx.xxx.xxx.xxx:8278'},
        ]},
        {'factory': '小米', 'list': [
            {'model': 'MiBOX4', 'method': '设置-账号与安全-ADB调试'},
        ]},
        {'factory': '迪优美特', 'list': [
            {'model': 'Android8.1.0tv53', 'method': '双头USB连接'},
        ]},
        {'factory': '浪潮', 'list': [
            {'model': 'IPBS9505', 'method': '遥控器连续按键值“上上下下左左右右”，端口号65432'},
        ]},
        {'factory': '创维', 'list': [
            {'model': 'E900V21C', 'method': '在设置-更多设置，进去里面，多按右键触发usb开关，然后点击开启usb调试'},
            {'model': 'E900V21E', 'method': '在设置-更多设置，进去里面，多按右键触发usb开关，然后点击开启usb调试'},
            {'model': 'E900V22D', 'method': 'adb connect 盒子ip地址:60001'},
            {'model': 'E900-S', 'method': '在设置-其它设置，多按右键触发usb开关，然后点击开启usb调试'},
        ]}
    ]

    def get_all_factory(self):
        factory_list = []
        for factory_info in self.adb_info:
            factory = factory_info.get('factory')
            factory_list.append(factory)
        return factory_list

    def get_factory_model(self, factory):
        model_list = []
        for info in self.adb_info:
            fac = info.get('factory')
            if fac == factory:
                model_info_list = info.get('list')
                for mode_info in model_info_list:
                    model = mode_info.get('model')
                    model_list.append(model)
                break
        return model_list

    def get_adb_open_method(self, factory, model):
        for factory_info in self.adb_info:
            cur_factory = factory_info.get('factory')
            if cur_factory == factory:
                model_list = factory_info.get('list')
                for model_info in model_list:
                    cur_model = model_info.get('model')
                    if cur_model == model:
                        method = model_info.get('method')
                        return method
        return '设备开ADB方法未知，如知道开启adb方法请邮件通知chengyuan@mgtv.com'

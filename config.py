#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

root_path = os.path.dirname(__file__)
root_disable = ['Android8.1.0.tv53']
package = 'com.mgtv.tv'
devices = ''
monkey = 'monkey'
monkey_cmd = ''
main_activity = []
activity_list = []
black_activity_list = []
black_list_key = 4
timeout = 24
frequency = 10
dumpheap_freq = 12
error_log = ['ANR in', 'MgtvCrash', 'onPlayerError']
devices_log_path = ['/data/anr']
save_path = None
report_path = None
mail = ['chengyuan@mgtv.com']
log_text = None
task_stop = False
cpu_var = mem_var = thr_var = fd_var = fps_var = 1
apk_domain = 'http://172.31.36.147'

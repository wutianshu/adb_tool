#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import asyncio
import threading
from src import addon
from mitmproxy import proxy, options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.tools.web.master import WebMaster


class HttpProxy:
    mit_master = None
    thread = None
    loop = None

    def __init__(self, listen_port):
        super(HttpProxy, self).__init__()
        self.init(int(listen_port))

    @classmethod
    def init(cls, listen_port):
        if cls.mit_master:
            return
        cls.start(listen_port)

    @staticmethod
    def loop_in_thread(loop, mit_master):
        asyncio.set_event_loop(loop)
        mit_master.run()

    @classmethod
    def start(cls, up_port, master='dump'):
        if not master:
            return
        opts = options.Options(listen_host='0.0.0.0', listen_port=6666, mode=f"upstream:http://127.0.0.1:{up_port}",
                               ssl_insecure=True)
        # opts = options.Options(listen_host='0.0.0.0', listen_port=up_port)
        p_config = proxy.config.ProxyConfig(opts)
        if master == 'dump':
            cls.mit_master = DumpMaster(opts, with_termlog=False, with_dumper=False, )
        else:
            cls.mit_master = WebMaster(opts, with_termlog=False)
        cls.mit_master.server = proxy.server.ProxyServer(p_config)
        cls.mit_master.addons.add(addon)
        cls.loop = asyncio.get_event_loop()
        cls.thread = threading.Thread(target=cls.loop_in_thread, args=(cls.loop, cls.mit_master), daemon=True)
        cls.thread.start()

    @classmethod
    def stop(cls):
        if getattr(cls, 'thread', None) and cls.thread.is_alive():
            # 停止 mitmproxy 的运行
            cls.mit_master.shutdown()

            # 等待线程结束
            cls.thread.join()

            # 清理相关资源
            cls.mit_master = None
            cls.thread = None

            # 关闭事件循环
            if cls.loop and not cls.loop.is_closed():
                cls.loop.stop()
                cls.loop.close()

    @classmethod
    def restart(cls, listen_port, master='dump'):
        # 先停止 MitmProxy
        cls.stop()

        # 等待 MitmProxy 停止完成
        while cls.is_running():
            time.sleep(0.1)

        # 再重新启动 MitmProxy
        cls.start(listen_port, master)

    @classmethod
    def is_running(cls):
        return getattr(cls, 'thread', None) and cls.thread.is_alive()


if __name__ == '__main__':
    mit = HttpProxy(9999)
    time.sleep(999999)

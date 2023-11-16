#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from src.log import logger
from src.excel import Excel
from src.utils import Utils


class Report(object):
    def __init__(self, csv_dir, package):
        self.summary_csf_file = {"cpu.csv": {"table_name": "cpu",
                                             "x_axis": "datetime",
                                             "y_axis": "%",
                                             "values": ["package%", "total%"]},
                                 "thread.csv": {"table_name": "thread_num",
                                                "x_axis": "datetime",
                                                "y_axis": "num",
                                                "values": ["num"]},
                                 "fd.csv": {"table_name": "fd_num",
                                            "x_axis": "datetime",
                                            "y_axis": "num",
                                            "values": ["num"]},
                                 "pid.csv": {"table_name": "pid",
                                             "x_axis": "datetime",
                                             "y_axis": "pid_num",
                                             "values": ["pid"]},
                                 "fps.csv": {"table_name": "fps",
                                             "x_axis": "datetime",
                                             "y_axis": "pid_num",
                                             "values": ["fps", "jank"]},
                                 "activity.csv": {"table_name": "activity_time",
                                                  "x_axis": "datetime",
                                                  "y_axis": "time(MS)",
                                                  "values": ["this_time", "wait_time"]},
                                 "monkey.csv": {"table_name": "activity_num",
                                                "x_axis": "datetime",
                                                "y_axis": "num",
                                                "values": ["activities"]},
                                 "lifetime.csv": {"table_name": "activity_lifetime",
                                                  "x_axis": "datetime",
                                                  "y_axis": "time(MS)",
                                                  "values": ['time_interval']},
                                 "pss.csv": {"table_name": "pss",
                                             "x_axis": "datetime",
                                             "y_axis": "mem(MB)",
                                             "values": ["pss", "java_heap", "native_heap", "system"]
                                             },
                                 "ueec.csv": {"table_name": "ueec",
                                              "x_axis": "datetime",
                                              "y_axis": "time(MS)",
                                              "values": ["duration", "average"]
                                              },
                                 "page.csv": {"table_name": "page",
                                              "x_axis": "datetime",
                                              "y_axis": "time(MS)",
                                              "values": ["total"]
                                              }
                                 }

        logger.debug(package)
        logger.debug(self.summary_csf_file)
        logger.info('create report for %s' % csv_dir)
        file_names = self.filter_file_names(csv_dir)
        logger.debug('%s' % file_names)
        if file_names:
            self.book_name = 'report_%s.xlsx' % Utils.get_current_underline_time()
            self.book_name = os.path.join(csv_dir, self.book_name)
            excel = Excel(self.book_name)
            for file_name in file_names:
                logger.debug('get csv %s to excel' % file_name)
                values = self.summary_csf_file[os.path.basename(file_name)]
                excel.csv_to_excel(file_name, values["table_name"], values["x_axis"], values["y_axis"],
                                   values["values"])
            logger.info('wait to save_log %s' % self.book_name)
            excel.save()

    def filter_file_names(self, csv_dir):
        csv_files = []
        logger.debug(csv_dir)
        for file_name in os.listdir(csv_dir):
            if os.path.isfile(os.path.join(csv_dir, file_name)) and os.path.basename(
                    file_name) in self.summary_csf_file.keys():
                file_path = os.path.join(csv_dir, file_name)
                logger.debug(file_path)
                csv_files.append(file_path)
        return csv_files


if __name__ == '__main__':
    result_dir = r'D:\pythoncode\AdbTool\results\com.mgtv.tv\2023_10_26_15_37_13_23102614'
    r = Report(result_dir, 'com.mgtv.tv')

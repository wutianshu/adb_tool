#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import csv
from src.log import logger
from src import xlsxwriter


class Excel(object):
    def __init__(self, excel_file):
        self.excel_file = excel_file
        self.workbook = xlsxwriter.Workbook(excel_file)
        self.color_list = ["blue", "green", "red", "yellow", "black", "purple"]

    def csv_to_excel(self, csv_file, sheet_name, x_axis, y_axis, y_fields):
        """
        把csv的数据存到excel中，并画曲线
        :param csv_file:
        :param sheet_name:
        :param x_axis:
        :param y_axis:
        :param y_fields:
        :return:
        """
        filename = os.path.splitext(os.path.basename(csv_file))[0]
        logger.debug("filename:"+filename)
        worksheet = self.workbook.add_worksheet(filename)
        with open(csv_file, 'r') as f:
            read = csv.reader(f)
            row = 0
            headings = []
            for line in read:
                col = 0
                for cell in line:
                    if self.is_number(cell):
                        worksheet.write(row, col, float(cell))
                    else:
                        worksheet.write(row, col, cell)
                    col = col + 1
                if row == 0:
                    headings = line
                row = row + 1
            columns = len(headings)
        y_fields_index = []
        package_index = []
        for column_name in y_fields:
            y_fields_index.extend([i for i, v in enumerate(headings) if v == column_name])
        package_index.extend([i for i, v in enumerate(headings) if v == "package"])
        logger.debug("series_index")
        logger.debug(package_index)
        if columns > 1 and row > 2:
            chart = self.workbook.add_chart({'type': 'line'})
            chart.show_blanks_as('span')
            i = 0
            for index in y_fields_index:
                chart.add_series({
                    'name': [filename, 0, index],
                    'categories': [filename, 1, 0, row - 1, 0],
                    'values': [filename, 1, index, row - 1, index],
                    'line': {'color': self.color_list[index % len(self.color_list)]}
                })
            chart.set_title({'name': sheet_name})
            chart.set_x_axis({'name': x_axis})
            chart.set_y_axis({'name': y_axis})
            worksheet.insert_chart('I3', chart, {'x_scale': 2, 'y_scale': 2})

    @staticmethod
    def is_number(s):
        try:
            float(s)
            return True
        except ValueError:
            pass
        try:
            import unicodedata
            unicodedata.numeric(s)
            return True
        except (TypeError, ValueError):
            pass
        return False

    def save(self):
        self.workbook.close()


if __name__ == '__main__':
    book_name = 'summary.xlsx'
    excel = Excel(book_name)
    # excel.csv_to_xlsx("mem_infos_10-42-38.csv","meminfo","datetime","mem(MB)",["pid_pss(MB)","pid_alloc_heap(MB)"])
    excel.csv_to_excel(r"D:\code\AdbTool\results\com.mgtv.tv\2021_11_17_15_04_20\cpu.csv",
                      "pss", "datetime", "%", ["total%", "package%"])
    excel.save()

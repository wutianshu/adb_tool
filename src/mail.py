#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time
import smtplib
from src.zipp import zipfile
from email.header import Header
from src.log import logger
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

MAIL_HOST = 'mx.mgpost.imgo.tv'
MAIL_USER = 'autotest@mgpost.imgo.tv'
MAIL_PASSWORD = '43zzERmMqk3LQvY'
SENDER = 'autotest@mgpost.imgo.tv'


def zip_files(files_path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as f:
        for file_path in files_path:
            basename = os.path.basename(file_path)
            f.write(file_path, basename)


def mail_text(device, mode, android_version, img=False, log=None):
    now_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    text = """
        <p>设备地址：%s</p>
        <p>设备型号：%s</p>
        <p>系统版本：%s</p>
        <p>当前时间：%s</p>
        """ % (device, mode, android_version, now_time)
    if img:
        text += """
        <p>错误日志：%s</p>
        <p>屏幕截图：</p>
        <p><img src="cid:image"></p>
        """ % log
    else:
        text += """测试报告详情见附件"""
    return text


def mail_message(receivers, text, files_path, img=False):
    message = MIMEMultipart()
    message['From'] = Header('PerfTest<%s>' % SENDER, 'utf-8')
    for receiver in receivers:
        message['To'] = Header(receiver, 'utf-8')
    subject = '性能自动化测试%s' % time.strftime('%Y-%m-%d', time.localtime())
    message['Subject'] = Header(subject, 'utf-8')
    message.attach(MIMEText(text, 'html', 'utf-8'))
    if img:
        for file_path in files_path:
            with open(file_path, 'rb') as f:
                att = MIMEImage(f.read())
            att.add_header('Content-ID', '<image>')
            message.attach(att)
    else:
        basedir = os.path.dirname(files_path[0])
        zip_path = os.path.join(basedir, 'report.zip')
        zip_files(files_path, zip_path)
        with open(zip_path, 'rb') as f:
            att = MIMEText(f.read(), 'base64', 'utf-8')
        att['Content-Type'] = 'application/octet-stream'
        att['Content-Disposition'] = 'attachment; filename="report.zip"'
        message.attach(att)
    return message


def send_mail(receivers, device, mode, android_version, files_path, img=False, log=None):
    text = mail_text(device, mode, android_version, img, log)
    message = mail_message(receivers, text, files_path, img)
    try:
        mail_obj = smtplib.SMTP(MAIL_HOST)
        mail_obj.login(MAIL_USER, MAIL_PASSWORD)
        mail_obj.sendmail(SENDER, receivers, message.as_string())
        logger.info('mail send success')
    except smtplib.SMTPAuthenticationError:
        logger.error("mail server username/password authentication error")
    except TimeoutError:
        logger.error('mail server connect timeout')


if __name__ == '__main__':
    send_mail(['chengyuan@mgtv.com'], '192.168.43.1:5555', 'B860AV', '4.4.2',
              [r'D:\pythoncode\PerfTest\results\com.mgtv.tv\2021_09_30_11_10_59\activity_lifetime.csv',
               r'D:\pythoncode\PerfTest\results\com.mgtv.tv\2021_09_30_11_10_59\adb_monkey.csv'], False, 'MgtvCrash')

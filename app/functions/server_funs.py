import os, smtplib
from django.contrib.sites import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from subprocess import Popen, PIPE



# отправка письма на указанный ящик без вложения. Вход: адрес, тема, текст
def send_mail(m, s, b):
    # отправим локальное письмо
    if os.name == 'nt':
        msg = MIMEMultipart()
        msg['From'] = 'manager@f-trade.ru'
        msg['To'] = m
        msg['Subject'] = s
        msg.attach(MIMEText(b, 'html'))
        text = msg.as_string()
        email_user = 'fishulika'
        try:
            server = smtplib.SMTP("smtp.f-trade.ru", 25)
            server.login(email_user, 'Ciffiav1')
            server.sendmail(email_user, m, text)
            server.quit()
        except BaseException as e:
            return str(e)
        else:
            return 'ok'
    # Отправим с сервера
    else:
        msg = MIMEMultipart()
        msg['From'] = 'manager@f-trade.ru'
        msg['To'] = m
        msg['Subject'] = s
        msg.attach(MIMEText(b, 'html'))

        # Отправка почты системным запросом
        p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
        p.communicate(msg.as_bytes())
        return 'ok'








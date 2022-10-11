from email.headerregistry import Address
from email.message import EmailMessage
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from datetime import datetime

from metrics.reporting_metrics.build_message import BuildMessage
from token_gen.token_generation import TokenGeneration
from accounts.accounts import Accounts
from metrics.reporting_metrics.daily_metric_scripts.create_daily_metrics_table import CreateDailyMetricsTable

import config.default as default
import utils.utils as utils

# TODO build class that creates an email with all the tracking metrics
# Gmail details
config = default.config
access_token = TokenGeneration(
    client_id=config['prosper']['client_id'],
    client_secret=config['prosper']['client_secret'],
    ps=config['prosper']['ps'],
    username=config['prosper']['username']
).execute()

header = utils.http_header_build(access_token)

today = datetime.today().strftime('%Y-%m-%d')


def create_email_message(from_address, to_address, subject, body, file_location_defaults):
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject
    msgtext = MIMEText(_text=body)
    msg.attach(msgtext)
    picText1 = MIMEText('<b>%s</b><br><img src="cid:%s"><br>' % ("", file_location_defaults), 'html')
    msg.attach(picText1)
    fp1 = open(file_location_defaults, 'rb')
    img1 = MIMEImage(fp1.read())
    fp1.close()
    img1.add_header('Content-ID', '<{}>'.format(file_location_defaults))
    msg.attach(img1)
    # add avg daily outstanding yield chart
    return msg

accounts = Accounts(header)

path_to_save_defaults = default.base_path + '/log/daily_defaults.png'
path_to_save_annualized_returns = default.base_path + '/log/daily_annualized_returns.png'
c = CreateDailyMetricsTable(start_date="2020-03-02", path_to_save_defaults=path_to_save_defaults)
c.create_default_tracking_line_graph_png()

msg = create_email_message(
    from_address=default.config['email']['send_from_email'],
    to_address=default.config['email']['send_to_email'],
    subject='Prosper default tracking for {date}'.format(date=today),
    body=BuildMessage(accounts).build_complete_message(),
    file_location_defaults=path_to_save_defaults
)

with smtplib.SMTP('smtp.gmail.com', port=587) as smtp_server:
    smtp_server.ehlo()
    smtp_server.starttls()
    smtp_server.login(default.config['email']['send_from_email'], default.config['email']['send_from_email_pass'])
    smtp_server.send_message(msg)

print('Email sent successfully')

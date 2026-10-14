# -*- coding: utf-8 -*-
"""邮件发送（SMTP + SSL/TLS）。"""
from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

log = logging.getLogger(__name__)


def send(
    subject: str,
    html_body: str,
    to: list[str],
    from_addr: str,
    smtp_host: str,
    smtp_port: int,
    user: str,
    password: str,
    use_ssl: bool = True,
) -> None:
    if not (smtp_host and user and password and to):
        raise RuntimeError("邮件配置不完整：需要 SMTP_HOST / SMTP_USER / SMTP_PASSWORD / MAIL_TO")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("英语每日精读", "utf-8")), from_addr or user))
    msg["To"] = ",".join(to)
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()
    try:
        server.login(user, password)
        server.sendmail(user, to, msg.as_string())
        log.info("邮件已发送至 %s", ", ".join(to))
    finally:
        server.quit()
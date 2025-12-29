# STL
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from typing import cast

# External
from celery import Task

# Custom
from background.celery_app import celery_worker
from configs import settings, get_logger

logger = get_logger()


@celery_worker.task()
def send_email(subject: str, to_email: str, body: str) -> None:
    # For development: just logger.info to console
    if settings.debug:
        logger.info(f"\n EMAIL TO: {to_email}")
        logger.info(f"SUBJECT: {subject}")
        logger.info(f"BODY:\n{body}\n")
        return

    # Production: use real SMTP (need an actual email)
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["To"] = to_email
    msg["From"] = settings.smtp_user
    msg.attach(payload=MIMEText(_text=body, _subtype="plain"))

    with smtplib.SMTP_SSL(
        host=settings.smtp_host, port=settings.smtp_port
    ) as server:
        server.login(user=settings.smtp_user, password=settings.smtp_password)
        server.send_message(msg=msg)


send_email_task: Task = cast(Task, send_email)

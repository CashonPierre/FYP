# STL
from typing import cast

# External
from celery import Task

# Custom
from background.celery_app import celery_worker
from configs import settings, get_logger

logger = get_logger()


def _send_via_resend(subject: str, to_email: str, body: str) -> None:
  import resend
  resend.api_key = settings.resend_api_key
  resend.Emails.send({
    "from": settings.resend_from_email,
    "to": [to_email],
    "subject": subject,
    "text": body,
  })


@celery_worker.task()
def send_email(subject: str, to_email: str, body: str) -> None:
  if settings.debug or not settings.resend_api_key:
    # Development / no key configured — log to console
    logger.info("\n EMAIL TO: %s", to_email)
    logger.info("SUBJECT: %s", subject)
    logger.info("BODY:\n%s\n", body)
    return

  _send_via_resend(subject=subject, to_email=to_email, body=body)


send_email_task: Task = cast(Task, send_email)

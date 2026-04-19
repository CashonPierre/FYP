# STL
from typing import cast

# External
from celery import Task

# Custom
from background.celery_app import celery_worker
from configs import settings, get_logger

logger = get_logger()


def _send_via_resend(
  subject: str, to_email: str, body: str, html: str | None = None
) -> None:
  import resend

  resend.api_key = settings.resend_api_key
  params: dict[str, object] = {
    "from": settings.resend_from_email,
    "to": [to_email],
    "subject": subject,
    "text": body,
  }
  if html is not None:
    params["html"] = html

  try:
    result = resend.Emails.send(params)
  except Exception:
    logger.exception(
      "Resend API error — email to %s not delivered. from=%s subject=%r",
      to_email,
      settings.resend_from_email,
      subject,
    )
    raise

  message_id = result.get("id") if isinstance(result, dict) else None
  logger.info(
    "Resend accepted email to %s (message_id=%s, from=%s, subject=%r)",
    to_email,
    message_id,
    settings.resend_from_email,
    subject,
  )


@celery_worker.task()
def send_email(
  subject: str, to_email: str, body: str, html: str | None = None
) -> None:
  if settings.debug or not settings.resend_api_key:
    # Development / no key configured — log to console
    logger.info("\n EMAIL TO: %s", to_email)
    logger.info("SUBJECT: %s", subject)
    logger.info("BODY:\n%s\n", body)
    return

  _send_via_resend(subject=subject, to_email=to_email, body=body, html=html)


send_email_task: Task = cast(Task, send_email)

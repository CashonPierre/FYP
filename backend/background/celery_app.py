from celery import Celery
from configs import settings

celery_worker: Celery = Celery(
    main="tasks",
    broker=settings.valkey_url,
    backend=settings.valkey_url,
)

celery_worker.autodiscover_tasks(["background.tasks"])

# to see the log in real-time:
# celery -A background.celery_app worker --loglevel=info

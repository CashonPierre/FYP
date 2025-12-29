from celery import Celery
from configs import settings

celery_worker: Celery = Celery(
    main="tasks",
    broker=f"{settings.valkey_scheme}{settings.valkey_host}:{settings.valkey_port}/{settings.valkey_db}",
    backend=f"{settings.valkey_scheme}{settings.valkey_host}:{settings.valkey_port}/{settings.valkey_db}",
)

celery_worker.autodiscover_tasks(["background.tasks"])

# to see the log in real-time:
# celery -A background.celery_app worker --loglevel=info

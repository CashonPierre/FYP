from celery import Celery
from celery.schedules import crontab

from configs import settings

celery_worker: Celery = Celery(
    main="tasks",
    broker=settings.valkey_url,
    backend=settings.valkey_url,
)

celery_worker.autodiscover_tasks(["background.tasks"])

# ---------------------------------------------------------------------------
# Celery Beat — periodic tasks
# Run the beat scheduler alongside a worker with:
#   celery -A background.celery_app beat --loglevel=info
# Or combined (dev only):
#   celery -A background.celery_app worker --beat --loglevel=info
# ---------------------------------------------------------------------------

celery_worker.conf.beat_schedule = {
    # Daily OHLC refresh: runs at 06:00 UTC every day.
    # Refreshes all symbols already in DB + all universe symbols.
    "daily-ohlc-refresh": {
        "task": "background.tasks.market_refresh.refresh_all_tracked_symbols",
        "schedule": crontab(hour=6, minute=0),
        "args": ("1D",),
    },
}

celery_worker.conf.timezone = "UTC"

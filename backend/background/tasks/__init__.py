from .email import send_email_task as send_email_task
from .backtest import run_backtest_task as run_backtest_task
from .backtest import run_backtest_batch_task as run_backtest_batch_task
from .cross_sectional import run_universe_backtest_task as run_universe_backtest_task
# Side-effect imports below register Celery tasks at worker startup so beat
# can enqueue them by string name (otherwise autodiscover_tasks won't find
# them because there's no `tasks.py` submodule in this package).
from . import market_refresh as market_refresh  # noqa: F401
from . import fundamentals_refresh as fundamentals_refresh  # noqa: F401

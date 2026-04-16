import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make sure backend/ is on the path so we can import our app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.make_db import Base
from configs import settings

# Import all models so Alembic can see them for autogenerate
import database.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
  fileConfig(config.config_file_name)

# Point Alembic at our models
target_metadata = Base.metadata

# Use DB URL from app settings
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
  url = config.get_main_option("sqlalchemy.url")
  context.configure(
    url=url,
    target_metadata=target_metadata,
    literal_binds=True,
    dialect_opts={"paramstyle": "named"},
  )
  with context.begin_transaction():
    context.run_migrations()


def run_migrations_online() -> None:
  connectable = engine_from_config(
    config.get_section(config.config_ini_section, {}),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
  )
  with connectable.connect() as connection:
    context.configure(
      connection=connection,
      target_metadata=target_metadata,
    )
    with context.begin_transaction():
      context.run_migrations()


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()

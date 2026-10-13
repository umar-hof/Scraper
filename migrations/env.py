from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.database import normalize_database_url
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
database_url = normalize_database_url(os.getenv("DATABASE_URL"), require_value=True)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL is required for migrations")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    # Validate before engine_from_config so Railway logs identify the missing
    # deployment variable instead of only showing SQLAlchemy's parse error.
    if not config.get_main_option("sqlalchemy.url"):
        raise RuntimeError("DATABASE_URL is required for migrations")
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

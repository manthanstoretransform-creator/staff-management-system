import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Deliberately NOT calling load_dotenv() here. app.core.database records which
# variables came from the real environment before it loads .env, and that
# distinction is what makes an explicitly exported DATABASE_URL authoritative.
# Populating os.environ from .env first would make every .env value look
# explicit and defeat it.
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Resolve the migration target using the SAME rules as the application.

    These two used to disagree: the app preferred DATABASE_URL (production)
    regardless of ENV, while this file ignored DATABASE_URL entirely unless
    ALEMBIC_TARGET=production and otherwise used DATABASE_URL_DEV. So
    `alembic upgrade head` and `uvicorn app.main:app` could -- and did -- point
    at different databases in the same shell. One resolver now serves both.

    ALEMBIC_TARGET=production is kept as an explicit opt-in for deploying
    migrations to production from a machine whose ENV says otherwise.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.core.database import describe_url, get_database_url

    if os.getenv("ALEMBIC_TARGET") == "production":
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ValueError(
                "ALEMBIC_TARGET=production but DATABASE_URL is not set."
            )
    else:
        url = get_database_url()

    # Migrations rewrite schemas. Always say out loud where they are going.
    print(f"alembic target: {describe_url(url)}", flush=True)
    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() will broadcast the
    SQL statements to the script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

import os

from alembic import context
from app.adapters import (
    daily,  # noqa: F401 -- register daily models in migration metadata
    family,  # noqa: F401 -- register family models in migration metadata
    recurrence,  # noqa: F401 -- register recurrence models in migration metadata
)
from app.adapters.database import Base
from sqlalchemy import create_engine, pool

engine = create_engine(os.environ["DATABASE_URL"], poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

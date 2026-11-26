"""baseline: empty schema

The first migration has no tables on purpose: the tables (4.4 view snapshots, the user's portfolio choice,
proposals) come with their decisions. Applying it only creates alembic_version, so every later migration has a
starting point and "alembic current" shows where a database is.

Revision ID: 0001
Revises:
Create Date: 2026-11-23
"""
from typing import Sequence, Union

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

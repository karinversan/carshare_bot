"""add note columns for closeups and final damage records

Revision ID: 0002_add_note_columns
Revises: 0001_initial
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_note_columns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inspection_images", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("manual_damages", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("inspection_damages_final", sa.Column("note", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("inspection_damages_final", "note")
    op.drop_column("manual_damages", "note")
    op.drop_column("inspection_images", "note")

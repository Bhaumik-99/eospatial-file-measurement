"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("crs", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PROCESSING", "COMPLETED", "FAILED", name="filestatus"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_files_status", "files", ["status"], unique=False)
    op.create_table(
        "feature_measurements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("feature_index", sa.Integer(), nullable=False),
        sa.Column("geometry_type", sa.String(length=64), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("crs", sa.String(length=512), nullable=True),
        sa.Column("measurement_crs", sa.String(length=1024), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column("length_m", sa.Float(), nullable=True),
        sa.Column("measurement_supported", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "feature_index", name="uq_file_feature_index"),
    )
    op.create_index(
        "ix_feature_measurements_file_id",
        "feature_measurements",
        ["file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_feature_measurements_file_id", table_name="feature_measurements")
    op.drop_table("feature_measurements")
    op.drop_index("ix_files_status", table_name="files")
    op.drop_table("files")

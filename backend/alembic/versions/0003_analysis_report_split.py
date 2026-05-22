"""analysis report split: nullable report_markdown, add report_generated_at

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("analysis_reports", "report_template", nullable=True)
    op.alter_column("analysis_reports", "independence", nullable=True)
    op.alter_column("analysis_reports", "report_markdown", nullable=True)
    op.add_column(
        "analysis_reports",
        sa.Column("report_generated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_reports", "report_generated_at")
    op.alter_column("analysis_reports", "report_markdown", nullable=False)
    op.alter_column("analysis_reports", "independence", nullable=False)
    op.alter_column("analysis_reports", "report_template", nullable=False)

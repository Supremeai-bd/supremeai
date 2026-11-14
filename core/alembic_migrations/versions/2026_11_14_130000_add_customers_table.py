"""Add customers table — Customer Directory and Admin Workspace Sync

বাংলা: SupremeAI Customer Directory-র পারসিস্টেন্ট ডেটাবেস টেবিল।
ফ্রন্টএন্ডের CustomerRecord এবং ব্যাকএন্ডের Customer ORM মডেলের সাথে সামঞ্জস্যপূর্ণ।

Revision ID: cust_dir_0001
Revises: slot_arch_0001
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cust_dir_0001"
down_revision: str | Sequence[str] | None = "slot_arch_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_tables_offline_safe(bind) -> set[str]:
    """Inspect tables safely in both online and offline migration modes."""
    try:
        inspector = sa.inspect(bind)
        return set(inspector.get_table_names())
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables_offline_safe(bind)

    if "customers" not in existing:
        op.create_table(
            "customers",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("tier", sa.String(length=50), nullable=False, server_default="Free"),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
            sa.Column("mrr", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("token_limit", sa.Integer(), nullable=False, server_default="100000"),
            sa.Column("connected_repos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("joined_date", sa.String(length=50), nullable=False),
            sa.Column("last_active", sa.String(length=100), nullable=False, server_default="Just now"),
            sa.Column("github_handle", sa.String(length=255), nullable=True),
            sa.Column("region", sa.String(length=100), nullable=True, server_default="Asia/Dhaka"),
            sa.Column("is_developer_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_customers_email", "customers", ["email"], unique=True)
        op.create_index("ix_customers_status", "customers", ["status"])
        op.create_index("ix_customers_tier", "customers", ["tier"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables_offline_safe(bind)
    if "customers" in existing:
        op.drop_index("ix_customers_tier", table_name="customers")
        op.drop_index("ix_customers_status", table_name="customers")
        op.drop_index("ix_customers_email", table_name="customers")
        op.drop_table("customers")

"""phase 1 reservation instrument semantics and fill identity checks

Revision ID: 6d4e9f0a12b3
Revises: 5c8e4a71b9d2
Create Date: 2026-09-16 00:16:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6d4e9f0a12b3"
down_revision: str | None = "5c8e4a71b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "risk_reservations",
        sa.Column("contract_multiplier", sa.Numeric(20, 8), nullable=False, server_default="1"),
    )
    op.add_column(
        "risk_reservations",
        sa.Column("contract_type", sa.String(length=16), nullable=False, server_default="LINEAR"),
    )
    op.add_column(
        "risk_reservations",
        sa.Column(
            "quantity_unit",
            sa.String(length=32),
            nullable=False,
            server_default="CONTRACTS",
        ),
    )
    op.create_check_constraint(
        "ck_risk_reservation_multiplier",
        "risk_reservations",
        "contract_multiplier > 0",
    )
    op.create_check_constraint(
        "ck_risk_reservation_contract_type",
        "risk_reservations",
        "contract_type IN ('LINEAR', 'INVERSE')",
    )
    op.create_check_constraint(
        "ck_execution_fill_fact_source_identity",
        "execution_fill_facts",
        "length(trim(source_fill_identity)) > 0",
    )
    op.alter_column("risk_reservations", "contract_multiplier", server_default=None)
    op.alter_column("risk_reservations", "contract_type", server_default=None)
    op.alter_column("risk_reservations", "quantity_unit", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_execution_fill_fact_source_identity",
        "execution_fill_facts",
        type_="check",
    )
    op.drop_constraint("ck_risk_reservation_contract_type", "risk_reservations", type_="check")
    op.drop_constraint("ck_risk_reservation_multiplier", "risk_reservations", type_="check")
    op.drop_column("risk_reservations", "quantity_unit")
    op.drop_column("risk_reservations", "contract_type")
    op.drop_column("risk_reservations", "contract_multiplier")

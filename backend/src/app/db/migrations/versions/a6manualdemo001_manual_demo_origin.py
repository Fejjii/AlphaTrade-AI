"""Explicit manual demo plan origin; existing immutable rows are unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "a6manualdemo001"
down_revision = "a5demolifecycle001"
branch_labels = None
depends_on = None

# Match ORM checks, preserving all canonical lineage requirements.
CHECKS = {
    "ck_plan_schema_v1": (
        "schema_version IN ('CanonicalTradePlanContentV1', 'ManualDemoTradePlanV1')"
    ),
    "ck_tpr_plan_authority": (
        "plan_authority IN ('paper_validation', 'canonical', 'manual_demo_test')"
    ),
    "ck_tpr_canonical_candidate_bind": (
        "(plan_authority IN ('paper_validation', 'manual_demo_test') AND "
        "canonical_candidate_id IS NULL) OR (plan_authority = 'canonical' AND "
        "canonical_candidate_id IS NOT NULL AND canonical_candidate_id = "
        "candidate_id)"
    ),
    "ck_tpr_compiled_setup_bind": (
        "(plan_authority IN ('paper_validation', 'manual_demo_test') AND "
        "compiled_setup_definition_id IS NULL) OR (plan_authority = 'canonical' AND "
        "compiled_setup_definition_id IS NOT NULL AND compiled_setup_definition_id ="
        " setup_definition_id)"
    ),
    "ck_tpr_manual_origin": (
        "(plan_authority = 'manual_demo_test' AND schema_version = "
        "'ManualDemoTradePlanV1' AND strategy_version_id IS NULL AND "
        "setup_definition_id IS NULL AND candidate_id IS NULL AND execution_venue = "
        "'BLOFIN_DEMO' AND execution_policy_version = 'manual-blofin-demo/v1') OR "
        "(plan_authority <> 'manual_demo_test' AND schema_version = "
        "'CanonicalTradePlanContentV1' AND strategy_version_id IS NOT NULL AND "
        "setup_definition_id IS NOT NULL AND candidate_id IS NOT NULL)"
    ),
}


def upgrade() -> None:
    op.drop_constraint("ck_trade_proposals_plan_root_kind", "trade_proposals", type_="check")
    op.create_check_constraint(
        "ck_trade_proposals_plan_root_kind",
        "trade_proposals",
        "plan_root_kind IN ('analysis_proposal', 'canonical_plan_root', 'manual_demo_test')",
    )
    op.alter_column("trade_proposals", "strategy_id", nullable=True)
    op.create_check_constraint(
        "ck_trade_proposals_manual_origin",
        "trade_proposals",
        "(plan_root_kind = 'manual_demo_test' AND strategy_id IS NULL "
        "AND signal_id IS NULL AND user_strategy_id IS NULL) OR "
        "(plan_root_kind <> 'manual_demo_test' AND strategy_id IS NOT NULL)",
    )
    for field in ("strategy_version_id", "setup_definition_id", "candidate_id"):
        op.alter_column("trade_plan_revisions", field, nullable=True)
    for name, expression in CHECKS.items():
        if name != "ck_tpr_manual_origin":
            op.drop_constraint(name, "trade_plan_revisions", type_="check")
        op.create_check_constraint(name, "trade_plan_revisions", expression)


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM trade_plan_revisions "
                "WHERE plan_authority = 'manual_demo_test' LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError(
            "Manual demo history exists; use forward recovery, never delete evidence."
        )
    for name in CHECKS:
        op.drop_constraint(name, "trade_plan_revisions", type_="check")
    op.create_check_constraint(
        "ck_plan_schema_v1",
        "trade_plan_revisions",
        "schema_version = 'CanonicalTradePlanContentV1'",
    )
    op.create_check_constraint(
        "ck_tpr_plan_authority",
        "trade_plan_revisions",
        "plan_authority IN ('paper_validation', 'canonical')",
    )
    for name in ("ck_tpr_canonical_candidate_bind", "ck_tpr_compiled_setup_bind"):
        op.create_check_constraint(
            name,
            "trade_plan_revisions",
            CHECKS[name].replace(
                "IN ('paper_validation', 'manual_demo_test')", "= 'paper_validation'"
            ),
        )
    for field in ("strategy_version_id", "setup_definition_id", "candidate_id"):
        op.alter_column("trade_plan_revisions", field, nullable=False)
    op.drop_constraint("ck_trade_proposals_manual_origin", "trade_proposals", type_="check")
    op.alter_column("trade_proposals", "strategy_id", nullable=False)
    op.drop_constraint("ck_trade_proposals_plan_root_kind", "trade_proposals", type_="check")
    op.create_check_constraint(
        "ck_trade_proposals_plan_root_kind",
        "trade_proposals",
        "plan_root_kind IN ('analysis_proposal', 'canonical_plan_root')",
    )

"""Safe dry-run-first setup/template migration (Phase 3)."""

from __future__ import annotations

import uuid
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    GlobalSetupTemplate,
    SetupDefinition,
    SetupMigrationRun,
    UserStrategy,
    UserStrategyVersion,
)
from app.schemas.common import SetupMigrationMode
from app.schemas.strategy_library import StrategyCard
from app.schemas.strategy_lifecycle import SetupMigrationReport, SetupMigrationRow
from app.schemas.structured_rules import StructuredRules
from app.services.setup_ast_compiler import compile_from_authored
from app.services.strategy_versioning import StrategyVersioningService


class SetupMigrationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._versions = StrategyVersioningService(session)

    def run(
        self,
        *,
        dry_run: bool,
        organization_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> SetupMigrationReport:
        mode = SetupMigrationMode.DRY_RUN if dry_run else SetupMigrationMode.APPLY
        rows: list[SetupMigrationRow] = []
        templates_created = 0
        templates_skipped = 0
        compiled_created = 0
        compiled_skipped = 0
        non_executable = 0
        collisions = 0

        setups = list(self._session.scalars(select(SetupDefinition)).all())
        seen_name_version: dict[tuple[str, int], uuid.UUID] = {}
        for setup in setups:
            key = (setup.name, setup.version)
            existing_alias = self._session.scalar(
                select(GlobalSetupTemplate).where(
                    GlobalSetupTemplate.setup_definition_id == setup.id
                )
            )
            if existing_alias is not None:
                templates_skipped += 1
                rows.append(
                    SetupMigrationRow(
                        kind="global_template",
                        source_id=setup.id,
                        target_id=existing_alias.id,
                        disposition="skipped_existing",
                    )
                )
                continue
            prior_id = seen_name_version.get(key)
            if prior_id is not None and prior_id != setup.id:
                collisions += 1
                rows.append(
                    SetupMigrationRow(
                        kind="global_template",
                        source_id=setup.id,
                        target_id=None,
                        disposition="collision_review_required",
                        detail="Name/version collision; left global.",
                    )
                )
                continue
            seen_name_version[key] = setup.id
            template_id = setup.id
            if not dry_run:
                template = GlobalSetupTemplate(
                    id=template_id,
                    setup_definition_id=setup.id,
                    name=setup.name,
                    version=setup.version,
                    strategy_id=setup.strategy_id,
                    is_global=True,
                    organization_id=None,
                )
                self._session.add(template)
                self._session.flush()
                template_id = template.id
            templates_created += 1
            rows.append(
                SetupMigrationRow(
                    kind="global_template",
                    source_id=setup.id,
                    target_id=template_id,
                    disposition="created",
                    detail="Global compatibility template; not tenant-owned.",
                )
            )

        strategy_stmt = select(UserStrategy)
        if organization_id is not None:
            strategy_stmt = strategy_stmt.where(UserStrategy.organization_id == organization_id)
        strategies = list(self._session.scalars(strategy_stmt).all())
        for strategy in strategies:
            versions = list(
                self._session.scalars(
                    select(UserStrategyVersion).where(
                        UserStrategyVersion.strategy_id == strategy.id
                    )
                ).all()
            )
            for version in versions:
                existing = self._versions.compiled_for_version(
                    version.id, organization_id=strategy.organization_id
                )
                if existing is not None:
                    compiled_skipped += 1
                    rows.append(
                        SetupMigrationRow(
                            kind="compiled_setup",
                            source_id=version.id,
                            target_id=existing.id,
                            disposition="skipped_existing",
                        )
                    )
                    continue
                card: StrategyCard | None = None
                rules: StructuredRules | None = None
                with suppress(Exception):
                    card = StrategyCard.model_validate(version.card)
                if version.structured_rules:
                    with suppress(Exception):
                        rules = StructuredRules.model_validate(version.structured_rules)
                if card is None:
                    non_executable += 1
                    rows.append(
                        SetupMigrationRow(
                            kind="compiled_setup",
                            source_id=version.id,
                            target_id=None,
                            disposition="non_executable",
                            detail="Authored card is not a deterministic compiler input.",
                        )
                    )
                    continue
                result = compile_from_authored(
                    card=card,
                    rules=rules,
                    pattern_spec=version.pattern_spec,
                    strategy_version_id=version.id,
                    organization_id=strategy.organization_id,
                )
                if result.document is None:
                    non_executable += 1
                    rows.append(
                        SetupMigrationRow(
                            kind="compiled_setup",
                            source_id=version.id,
                            target_id=None,
                            disposition="non_executable",
                            detail=result.failures[0].message if result.failures else None,
                        )
                    )
                    continue
                target_id = None
                if not dry_run:
                    compiled = self._versions.persist_compiled(
                        organization_id=strategy.organization_id,
                        user_id=strategy.user_id,
                        strategy_id=strategy.id,
                        strategy_version_id=version.id,
                        compiler_version=result.document.compiler_version,
                        grammar_version=result.document.grammar_version,
                        compiled_ast=result.document.pattern.model_dump(mode="json"),
                        content_hash=result.document.content_hash,
                    )
                    target_id = compiled.id
                compiled_created += 1
                rows.append(
                    SetupMigrationRow(
                        kind="compiled_setup",
                        source_id=version.id,
                        target_id=target_id,
                        disposition="created",
                    )
                )

        report = SetupMigrationReport(
            mode=mode,
            templates_created=templates_created,
            templates_skipped=templates_skipped,
            compiled_created=compiled_created,
            compiled_skipped=compiled_skipped,
            non_executable=non_executable,
            collisions=collisions,
            rows=rows,
        )
        run = SetupMigrationRun(
            organization_id=organization_id,
            mode=mode.value,
            report=report.model_dump(mode="json"),
            actor_user_id=actor_user_id,
        )
        self._session.add(run)
        self._session.flush()
        report = report.model_copy(update={"run_id": run.id})
        run.report = report.model_dump(mode="json")
        return report

    def rollback_run(self, run_id: uuid.UUID) -> int:
        """Record a compensating rollback. Compiled artifacts stay immutable.

        Physical schema downgrade is Alembic ``downgrade`` of revision ``8a9b0c1d2e3f``.
        """

        run = self._session.get(SetupMigrationRun, run_id)
        if run is None or run.mode != SetupMigrationMode.APPLY.value:
            return 0
        compensating = SetupMigrationRun(
            organization_id=run.organization_id,
            mode="rollback",
            report={
                "source_run_id": str(run.id),
                "compiled_rows_retained": True,
                "reason": "compiled_setup_definitions_are_immutable",
            },
            actor_user_id=run.actor_user_id,
        )
        self._session.add(compensating)
        self._session.flush()
        return 0

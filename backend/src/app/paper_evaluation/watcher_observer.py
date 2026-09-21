"""Watcher evaluation observer for paper measurement. Not a fusion authority."""

from __future__ import annotations

from uuid import UUID

from app.paper_evaluation.recorder import PaperEvaluationRecorder, observe_watcher_evaluation
from app.watcher.contracts import EvaluationCommand, EvaluationOutcome


class WatcherPaperEvaluationObserver:
    """Copies Watcher EvaluationOutcome into the measurement store.

    Exceptions are swallowed by WatcherFusionEvaluationService._observe so
    measurement cannot change setup truth or Candidate minting.
    """

    def __init__(
        self,
        recorder: PaperEvaluationRecorder,
        *,
        strategy_version_id: UUID | None = None,
        setup_definition_id: UUID | None = None,
        replayed: bool = False,
    ) -> None:
        self._recorder = recorder
        self._strategy_version_id = strategy_version_id
        self._setup_definition_id = setup_definition_id
        self._replayed = replayed

    def observe_evaluation(self, command: EvaluationCommand, outcome: EvaluationOutcome) -> None:
        observe_watcher_evaluation(
            self._recorder,
            command,
            outcome,
            strategy_version_id=self._strategy_version_id,
            setup_definition_id=self._setup_definition_id,
            replayed=self._replayed,
        )

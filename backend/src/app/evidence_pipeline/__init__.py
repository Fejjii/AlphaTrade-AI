"""Canonical live/read-only perpetual evidence pipeline.

Assembles existing Phase 5 USD-M contracts into CanonicalEvidenceWindowV1.
Does not enable Watcher, Telegram, execution, or live trading.
"""

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.canonical import (
    FIRST_SLICE_READ_SETUP_CONTENT_HASH,
    FIRST_SLICE_READ_SETUP_DEFINITION_ID,
    FIRST_SLICE_READ_STRATEGY_VERSION_ID,
    build_first_slice_assessment_command,
    first_slice_read_policy,
    is_first_slice_read_projection,
)
from app.evidence_pipeline.current_price import quote_current_price
from app.evidence_pipeline.service import CanonicalEvidenceService
from app.evidence_pipeline.types import (
    AssembledCanonicalEvidence,
    CompletenessReport,
    CurrentPricePresentation,
    CurrentPriceQuote,
)
from app.evidence_pipeline.watcher_port import AssemblingWatcherScanEvidence

__all__ = [
    "FIRST_SLICE_READ_SETUP_CONTENT_HASH",
    "FIRST_SLICE_READ_SETUP_DEFINITION_ID",
    "FIRST_SLICE_READ_STRATEGY_VERSION_ID",
    "AssembledCanonicalEvidence",
    "AssemblingWatcherScanEvidence",
    "CanonicalEvidenceService",
    "CompletenessReport",
    "CurrentPricePresentation",
    "CurrentPriceQuote",
    "FirstSliceEvidenceAssembler",
    "build_first_slice_assessment_command",
    "first_slice_read_policy",
    "is_first_slice_read_projection",
    "quote_current_price",
]

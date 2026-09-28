"""Interactive agent orchestration over existing AlphaTrade authorities.

Transcripts stay in the conversation store. Strategy previews stay in
strategy conversation proposals. Journal rows are written only by an explicit
confirm through JournalService. This package does not enable real trading.
"""

from app.interactive_agent.contracts import SCHEMA_VERSION
from app.interactive_agent.service import InteractiveAgentService

__all__ = ["SCHEMA_VERSION", "InteractiveAgentService"]

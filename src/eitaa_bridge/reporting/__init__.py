"""Local reporting core for the 1405 provincial cultural programs.

Level-3 component of the four-level operating model (ADR-51/ADR-53).
Owns programs, events, facts, questionnaire definitions, counting rules
and provincial aggregation. WordPress and Excel are projections only.
"""

from __future__ import annotations

from .model import (
    CEREMONIES_PROGRAM_ID,
    FACT_VALUE_KINDS,
    PROGRAM_CODES,
    Fact,
    FactValueKind,
    OccasionClass,
    Program,
    ProgramId,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from .rules import CountingRuleEngine, RULES_VERSION, classify_event_programs
from .aggregate import ProvincialAggregator, aggregate_program_report
from .bale_messaging import (
    BaleMessageRecord,
    BaleMessagingError,
    BaleMessagingFacade,
    BaleSendReport,
)
from .eitaa_extraction import EitaaCandidateExtractor, EventCandidate
from .excel_export import (
    ASHURA_ANNEX_SHEET_NAME,
    ReportingExportError,
    TemplateNotFoundError,
    UnresolvedStarCellsError,
    export_unified_report,
)
from .forms import (
    ALL_FORMS,
    FORMS_BY_PROGRAM,
    FilledForm,
    FormAnswer,
    QuestionnaireDefinition,
    prefill_form,
)
from .indexer import (
    DEFAULT_MONITOR_TARGETS,
    EitaaIntentIndexer,
    IndexDecision,
    MessageIntent,
)
from .monitor import DialogWatchConfig, EitaaReportMonitor, MonitorResult
from .service import ReportingService
from .store import ReportingStore
from .suggester import AgentSuggestion, ReportingSuggester

__all__ = [
    "AgentSuggestion",
    "ALL_FORMS",
    "ASHURA_ANNEX_SHEET_NAME",
    "CEREMONIES_PROGRAM_ID",
    "FACT_VALUE_KINDS",
    "FORMS_BY_PROGRAM",
    "PROGRAM_CODES",
    "BaleMessageRecord",
    "BaleMessagingError",
    "BaleMessagingFacade",
    "BaleSendReport",
    "CountingRuleEngine",
    "DEFAULT_MONITOR_TARGETS",
    "DialogWatchConfig",
    "EitaaCandidateExtractor",
    "EitaaIntentIndexer",
    "EitaaReportMonitor",
    "EventCandidate",
    "Fact",
    "FactValueKind",
    "FilledForm",
    "FormAnswer",
    "IndexDecision",
    "MessageIntent",
    "MonitorResult",
    "OccasionClass",
    "Program",
    "ProgramId",
    "ProgramKind",
    "ProvincialAggregator",
    "QuestionnaireDefinition",
    "ReportedEvent",
    "ReportingExportError",
    "ReportingService",
    "ReportingStore",
    "ReportingSuggester",
    "RULES_VERSION",
    "TemplateNotFoundError",
    "UnitScope",
    "UnresolvedStarCellsError",
    "ValueSource",
    "aggregate_program_report",
    "classify_event_programs",
    "export_unified_report",
    "prefill_form",
]

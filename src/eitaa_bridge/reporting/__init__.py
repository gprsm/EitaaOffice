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
from .assessment_import import (
    AssessmentImportResult,
    import_into_store,
    load_assessment_rows,
    parse_assessment_rows,
)
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
from .metrics import (
    ASSESSMENT_INSTRUMENT_1405,
    AssessmentInstrument,
    METRIC_DICTIONARY,
    MetricDefinition,
    MetricDictionary,
    normalize_coded_value,
)
from .plans import (
    PRAYER_MANDATE_1405,
    PRAYER_PLAN_1405,
    Mandate,
    PlanItem,
    realization_ratio,
    realization_report,
)
from .projections import build_prayer_dossier, build_visit_worksheet_prayer_row
from .registry import (
    EntityFact,
    ImamRecord,
    NomokalafRecord,
    UnitRecord,
    VenueRecord,
    nomokalaf_coverage,
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
    "ASSESSMENT_INSTRUMENT_1405",
    "AssessmentImportResult",
    "AssessmentInstrument",
    "CEREMONIES_PROGRAM_ID",
    "EntityFact",
    "FACT_VALUE_KINDS",
    "FORMS_BY_PROGRAM",
    "PROGRAM_CODES",
    "PRAYER_MANDATE_1405",
    "PRAYER_PLAN_1405",
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
    "ImamRecord",
    "IndexDecision",
    "METRIC_DICTIONARY",
    "Mandate",
    "MessageIntent",
    "MetricDefinition",
    "MetricDictionary",
    "MonitorResult",
    "NomokalafRecord",
    "OccasionClass",
    "PlanItem",
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
    "UnitRecord",
    "UnitScope",
    "UnresolvedStarCellsError",
    "ValueSource",
    "VenueRecord",
    "aggregate_program_report",
    "build_prayer_dossier",
    "build_visit_worksheet_prayer_row",
    "classify_event_programs",
    "export_unified_report",
    "import_into_store",
    "load_assessment_rows",
    "nomokalaf_coverage",
    "normalize_coded_value",
    "parse_assessment_rows",
    "prefill_form",
    "realization_ratio",
    "realization_report",
]

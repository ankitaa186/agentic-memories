from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
	role: Literal["user", "assistant", "system"]
	content: str


class TranscriptRequest(BaseModel):
	user_id: str
	history: List[Message]
	metadata: Optional[dict[str, Any]] = None



class OrchestratorMessageRequest(BaseModel):
	conversation_id: str
	role: Literal["user", "assistant", "system", "tool"]
	content: str
	message_id: Optional[str] = None
	timestamp: Optional[datetime] = None
	metadata: Dict[str, str] = Field(default_factory=dict)
	flush: bool = False


class MemoryInjectionPayload(BaseModel):
	memory_id: str
	content: str
	source: Literal["short_term", "long_term", "safety", "personalization", "system"]
	channel: Literal["inline", "tool", "side_channel"] = "inline"
	score: Optional[float] = None
	metadata: Dict[str, str] = Field(default_factory=dict)


class OrchestratorStreamResponse(BaseModel):
	injections: List[MemoryInjectionPayload] = Field(default_factory=list)


class OrchestratorTranscriptResponse(OrchestratorStreamResponse):
	pass


class OrchestratorRetrieveRequest(BaseModel):
	conversation_id: str
	query: str
	metadata: Dict[str, str] = Field(default_factory=dict)
	limit: int = Field(default=6, ge=1, le=50)
	offset: int = Field(default=0, ge=0)


class OrchestratorRetrieveResponse(OrchestratorStreamResponse):
	pass



class StoreMemoryItem(BaseModel):
	id: str
	content: str
	layer: Literal["short-term", "semantic", "long-term"]
	type: Literal["explicit", "implicit"]
	confidence: float
	ttl: Optional[int] = None
	timestamp: Optional[datetime] = None
	metadata: Optional[dict[str, Any]] = None


class StoreResponse(BaseModel):
	memories_created: int
	ids: List[str]
	summary: Optional[str] = None
	memories: Optional[List[StoreMemoryItem]] = None
	duplicates_avoided: int = 0
	updates_made: int = 0
	existing_memories_checked: int = 0


class RetrieveItem(BaseModel):
	id: str
	content: str
	layer: Literal["short-term", "semantic", "long-term"]
	type: Literal["explicit", "implicit"]
	score: float
	metadata: Optional[dict[str, Any]] = None
	importance: Optional[float] = None
	persona_tags: Optional[List[str]] = None
	emotional_signature: Optional[Dict[str, Any]] = None


class Pagination(BaseModel):
	limit: int = 10
	offset: int = 0
	total: int = 0


class RetrieveResponse(BaseModel):
	results: List[RetrieveItem]
	pagination: Pagination
	finance: Optional["FinanceAggregate"] = None

class PersonaContext(BaseModel):
	active_personas: List[str] = Field(default_factory=list)
	forced_persona: Optional[str] = None
	mood: Optional[str] = None


class PersonaRetrieveRequest(BaseModel):
	user_id: str
	query: Optional[str] = None
	limit: int = Field(default=10, ge=1, le=50)
	offset: int = Field(default=0, ge=0)
	persona_context: Optional[PersonaContext] = None
	granularity: Literal["raw", "episodic", "arc", "auto"] = "auto"
	include_narrative: bool = False
	explain: bool = False
	filters: Optional[dict[str, Any]] = None


class PersonaSelection(BaseModel):
	selected: Optional[str] = None
	confidence: float = 0.0
	state_snapshot_id: Optional[str] = None


class PersonaRetrieveResults(BaseModel):
	granularity: str
	memories: List[RetrieveItem] = Field(default_factory=list)
	summaries: List[Dict[str, Any]] = Field(default_factory=list)
	narrative: Optional[str] = None


class PersonaExplainability(BaseModel):
	weights: Dict[str, float] = Field(default_factory=dict)
	source_links: List[Dict[str, Any]] = Field(default_factory=list)


class PersonaRetrieveResponse(BaseModel):
	persona: PersonaSelection
	results: PersonaRetrieveResults
	explainability: Optional[PersonaExplainability] = None


class ForgetRequest(BaseModel):
	scopes: List[Literal["short-term", "semantic", "long-term"]] = Field(default_factory=list)
	dry_run: bool = False


class MaintenanceRequest(BaseModel):
	jobs: List[Literal["ttl_cleanup", "promotion", "compaction"]] = Field(default_factory=list)
	since_hours: Optional[int] = None


class MaintenanceResponse(BaseModel):
	jobs_started: List[str]
	status: Literal["running", "queued"] = "running"
	started_at: datetime = Field(default_factory=datetime.utcnow)


# Structured retrieval
class StructuredRetrieveRequest(BaseModel):
	user_id: str
	query: Optional[str] = None
	limit: int = Field(default=50, ge=1, le=100)


class StructuredRetrieveResponse(BaseModel):
	emotions: List[RetrieveItem] = Field(default_factory=list)
	behaviors: List[RetrieveItem] = Field(default_factory=list)
	personal: List[RetrieveItem] = Field(default_factory=list)
	professional: List[RetrieveItem] = Field(default_factory=list)
	habits: List[RetrieveItem] = Field(default_factory=list)
	skills_tools: List[RetrieveItem] = Field(default_factory=list)
	projects: List[RetrieveItem] = Field(default_factory=list)
	relationships: List[RetrieveItem] = Field(default_factory=list)
	learning_journal: List[RetrieveItem] = Field(default_factory=list)
	other: List[RetrieveItem] = Field(default_factory=list)
	finance: Optional["FinanceAggregate"] = None


# Portfolio summary (simplified schema - Story 3.3)
class PortfolioHolding(BaseModel):
	"""Simplified portfolio holding - public equities only"""
	ticker: str
	asset_name: Optional[str] = None
	shares: Optional[float] = None
	avg_price: Optional[float] = None
	first_acquired: Optional[datetime] = None
	last_updated: Optional[datetime] = None


class PortfolioSummaryResponse(BaseModel):
	"""Simplified portfolio summary response"""
	user_id: str
	holdings: List[PortfolioHolding] = Field(default_factory=list)
	total_holdings: int = 0


class FinanceGoal(BaseModel):
	"""Finance goal extracted from memory"""
	text: str
	tickers: List[str] = Field(default_factory=list)


class FinanceAggregate(BaseModel):
    portfolio: PortfolioSummaryResponse
    goals: List[FinanceGoal] = Field(default_factory=list)


# Forward refs resolution
RetrieveResponse.model_rebuild()
StructuredRetrieveResponse.model_rebuild()


# Narrative request/response
class NarrativeRequest(BaseModel):
    user_id: str
    query: Optional[str] = None
    start_time: Optional[str] = None  # ISO8601
    end_time: Optional[str] = None    # ISO8601
    limit: int = Field(default=25, ge=1, le=50)


class NarrativeResponse(BaseModel):
    user_id: str
    narrative: str
    summary: Optional[str] = None
    sources: List[dict] = Field(default_factory=list)


# =============================================================================
# Scheduled Intents API Models (Epic 5 + Epic 6 Extensions)
# =============================================================================
#
# Backward Compatibility Notes (Epic 6):
# - New fields have sensible defaults for existing triggers
# - trigger_timezone defaults to 'America/Los_Angeles' for existing triggers
# - cooldown_hours defaults to 24 (1 day)
# - fire_mode defaults to 'recurring' (no behavior change for existing triggers)
# - check_interval_minutes defaults to 5 (15 for portfolio triggers)
# - Existing triggers continue to work unchanged without modification
#

class TriggerSchedule(BaseModel):
    """Schedule configuration for time-based triggers (cron, interval, once).

    Used within ScheduledIntentCreate to define when a trigger should fire.
    Only one of cron, interval_minutes, or trigger_at should be set based on trigger_type.
    """
    cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    trigger_at: Optional[datetime] = None  # For 'once' trigger type
    check_interval_minutes: Optional[int] = Field(
        default=5,
        ge=5,
        description="Polling interval in minutes for condition-based triggers (min 5). "
                    "Default: 5 for most triggers, 15 for portfolio triggers."
    )
    timezone: str = Field(
        default="America/Los_Angeles",
        description="IANA timezone for scheduling (e.g., 'America/Los_Angeles', 'Europe/London', 'UTC')"
    )


class TriggerCondition(BaseModel):
    """Condition configuration for condition-based triggers (price, silence, portfolio).

    Used within ScheduledIntentCreate to define the conditions that must be met.
    Fields used depend on trigger_type:
    - price: ticker, operator, value OR expression (e.g., "NVDA < 130")
    - silence: threshold_hours OR expression (e.g., "inactive_hours > 48")
    - portfolio: expression (e.g., "any_holding_change > 5%")

    New expression field takes precedence over structured fields when both are provided.
    """
    # Legacy structured fields (backward compatible)
    ticker: Optional[str] = None
    operator: Optional[str] = None  # '<', '>', '<=', '>=', '=='
    value: Optional[float] = None
    threshold_hours: Optional[int] = None

    # New flexible expression fields (Story 6.2)
    condition_type: Optional[str] = Field(
        default=None,
        description="Condition category: 'price', 'portfolio', 'silence'"
    )
    expression: Optional[str] = Field(
        default=None,
        description="Human-readable condition expression (e.g., 'NVDA < 130', 'any_holding_change > 5%')"
    )

    # Cooldown configuration (Story 6.3)
    cooldown_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Minimum hours between condition-based trigger fires (1-168, default 24)"
    )

    # Fire mode configuration (Story 6.4)
    fire_mode: Literal["once", "recurring"] = Field(
        default="recurring",
        description="Fire mode: 'once' disables after first successful fire, 'recurring' (default) continues"
    )


class ScheduledIntentCreate(BaseModel):
    """Request model for creating a new scheduled intent.

    Defines a proactive trigger that can fire based on time (cron/interval/once)
    or conditions (price/silence/portfolio).
    """
    user_id: str
    intent_name: str
    description: Optional[str] = None
    trigger_type: Literal["cron", "interval", "once", "price", "silence", "portfolio"]
    trigger_schedule: Optional[TriggerSchedule] = None
    trigger_condition: Optional[TriggerCondition] = None
    action_type: Literal["notify", "check_in", "briefing", "analysis", "reminder"] = Field(
        default="notify",
        description="Type of action to perform when trigger fires"
    )
    action_context: str = Field(
        description="Context passed to the LLM when firing this intent. "
                    "Should include instructions for the AI assistant on how to respond "
                    "to the trigger condition. Example: 'Alert the user about the price change "
                    "and suggest reviewing their position.'"
    )
    action_priority: Literal["low", "normal", "high", "critical"] = Field(
        default="normal",
        description="Priority level affecting notification urgency and display"
    )
    expires_at: Optional[datetime] = None
    max_executions: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ScheduledIntentUpdate(BaseModel):
    """Request model for updating an existing scheduled intent (PATCH/PUT).

    All fields are optional to support partial updates.
    """
    intent_name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[Literal["cron", "interval", "once", "price", "silence", "portfolio"]] = None
    trigger_schedule: Optional[TriggerSchedule] = None
    trigger_condition: Optional[TriggerCondition] = None
    action_type: Optional[Literal["notify", "check_in", "briefing", "analysis", "reminder"]] = Field(
        default=None,
        description="Type of action to perform when trigger fires"
    )
    action_context: Optional[str] = Field(
        default=None,
        description="Context passed to the LLM when firing this intent"
    )
    action_priority: Optional[Literal["low", "normal", "high", "critical"]] = Field(
        default=None,
        description="Priority level affecting notification urgency and display"
    )
    enabled: Optional[bool] = None
    expires_at: Optional[datetime] = None
    max_executions: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ScheduledIntentResponse(BaseModel):
    """Response model for a scheduled intent with all database fields.

    Represents the complete state of a scheduled intent including
    scheduling state and execution results.
    """
    model_config = ConfigDict(from_attributes=True)

    # Identity
    id: UUID
    user_id: str
    intent_name: str
    description: Optional[str] = None

    # Trigger definition
    trigger_type: str
    trigger_schedule: Optional[Dict[str, Any]] = None
    trigger_condition: Optional[Dict[str, Any]] = None

    # Action configuration
    action_type: str
    action_context: str
    action_priority: str

    # Scheduling state
    next_check: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    last_executed: Optional[datetime] = None
    execution_count: int = 0

    # Execution results
    last_execution_status: Optional[str] = None
    last_execution_error: Optional[str] = None
    last_message_id: Optional[str] = None

    # Control
    enabled: bool = True
    expires_at: Optional[datetime] = None
    max_executions: Optional[int] = None

    # Audit
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IntentFireRequest(BaseModel):
    """Request model for reporting intent execution results.

    Sent by the proactive worker after attempting to fire an intent.
    Records the execution outcome and timing metrics.
    """
    status: Literal["success", "failed", "gate_blocked", "condition_not_met"]
    trigger_data: Optional[Dict[str, Any]] = None
    gate_result: Optional[Dict[str, Any]] = None
    message_id: Optional[str] = None
    message_preview: Optional[str] = None
    evaluation_ms: Optional[int] = None
    generation_ms: Optional[int] = None
    delivery_ms: Optional[int] = None
    error_message: Optional[str] = None


class IntentFireResponse(BaseModel):
    """Response model after firing an intent.

    Returns the updated intent state including next_check calculation.
    Includes cooldown status for condition-based triggers (Story 6.3).
    """
    intent_id: UUID
    status: str = Field(
        description="Execution result: 'success', 'failed', 'gate_blocked', 'condition_not_met', 'cooldown_active'"
    )
    next_check: Optional[datetime] = Field(
        default=None,
        description="Next scheduled time for this intent to be checked (UTC)"
    )
    enabled: bool = Field(
        description="Whether the intent is still active. May be set to false by fire_mode='once' or max_executions"
    )
    execution_count: int = Field(
        description="Total number of successful executions for this intent"
    )
    was_disabled_reason: Optional[str] = Field(
        default=None,
        description="Reason if intent was disabled by this fire. "
                    "Possible values: 'fire_mode_once' (condition trigger with fire_mode='once' succeeded), "
                    "'max_executions_reached', 'expired', 'manual'"
    )

    # Cooldown fields (Story 6.3)
    cooldown_active: bool = Field(
        default=False,
        description="True if intent is in cooldown period and fire was blocked"
    )
    cooldown_remaining_hours: Optional[float] = Field(
        default=None,
        description="Hours remaining until cooldown expires (only set if cooldown_active=True)"
    )
    last_condition_fire: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last successful condition-based trigger fire"
    )


class IntentClaimResponse(BaseModel):
    """Response model for claiming an intent for exclusive processing (Story 6.3).

    Returns the claimed intent data and claim timestamp.
    Used to prevent duplicate processing in multi-worker scenarios.
    """
    intent: ScheduledIntentResponse
    claimed_at: datetime = Field(
        description="Timestamp when the claim was made (expires after 5 minutes)"
    )


class IntentExecutionResponse(BaseModel):
    """Response model for an intent execution history record.

    Represents a single execution attempt with timing and result details.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    intent_id: UUID
    user_id: str
    executed_at: datetime
    trigger_type: str
    trigger_data: Optional[Dict[str, Any]] = None
    status: str
    gate_result: Optional[Dict[str, Any]] = None
    message_id: Optional[str] = None
    message_preview: Optional[str] = None
    evaluation_ms: Optional[int] = None
    generation_ms: Optional[int] = None
    delivery_ms: Optional[int] = None
    error_message: Optional[str] = None


# =============================================================================
# Direct Memory API Models (Epic 10)
# =============================================================================
#
# These schemas support direct memory storage operations, bypassing the normal
# LLM extraction pipeline. Used by Annie for explicit memory management.
#


class DirectMemoryRequest(BaseModel):
    """Request body for direct memory storage.

    Allows clients to store memories directly without LLM extraction.
    Supports general memory fields plus optional typed fields (episodic,
    emotional, procedural) that trigger routing to specialized storage tables.
    """

    # Required fields
    user_id: str = Field(
        ...,
        description="User identifier for memory ownership",
        example="user_12345",
    )
    content: str = Field(
        ...,
        max_length=5000,
        description="Memory content text (max 5000 characters)",
        example="User mentioned they prefer morning meetings and work best between 9am-12pm.",
    )

    # General memory fields
    layer: Literal["short-term", "semantic", "long-term"] = Field(
        default="semantic",
        description="Memory layer: 'short-term' (ephemeral), 'semantic' (facts), 'long-term' (persistent)",
        example="semantic",
    )
    type: Literal["explicit", "implicit"] = Field(
        default="explicit",
        description="Memory type: 'explicit' (stated directly) or 'implicit' (inferred)",
        example="explicit",
    )
    importance: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Importance score from 0.0 (trivial) to 1.0 (critical)",
        example=0.8,
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 (uncertain) to 1.0 (certain)",
        example=0.9,
    )
    persona_tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Persona tags for memory (max 10 tags)",
        example=["work", "preferences"],
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata key-value pairs",
        example={"source": "chat", "session_id": "abc123"},
    )

    # Optional episodic fields (triggers episodic_memories table storage)
    event_timestamp: Optional[datetime] = Field(
        default=None,
        description="When the event occurred (ISO8601 format). Setting this triggers storage to episodic_memories table.",
        example="2025-01-15T10:30:00Z",
    )
    location: Optional[str] = Field(
        default=None,
        description="Where the event occurred",
        example="Office conference room",
    )
    participants: Optional[List[str]] = Field(
        default=None,
        description="People involved in the event",
        example=["Alice", "Bob"],
    )
    event_type: Optional[str] = Field(
        default=None,
        description="Type of event (e.g., 'meeting', 'conversation', 'milestone')",
        example="meeting",
    )

    # Optional emotional fields (triggers emotional_memories table storage)
    emotional_state: Optional[str] = Field(
        default=None,
        description="Primary emotional state (e.g., 'happy', 'anxious', 'excited'). Setting this triggers storage to emotional_memories table.",
        example="excited",
    )
    valence: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Emotional valence from -1.0 (negative) to 1.0 (positive)",
        example=0.7,
    )
    arousal: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Emotional arousal from 0.0 (calm) to 1.0 (intense)",
        example=0.6,
    )
    trigger_event: Optional[str] = Field(
        default=None,
        description="Event that triggered the emotional state",
        example="Received promotion at work",
    )

    # Optional procedural fields (triggers procedural_memories table storage)
    skill_name: Optional[str] = Field(
        default=None,
        description="Name of the skill or procedure. Setting this triggers storage to procedural_memories table.",
        example="Python programming",
    )
    proficiency_level: Optional[str] = Field(
        default=None,
        description="Proficiency level (e.g., 'beginner', 'intermediate', 'expert')",
        example="intermediate",
    )


class DirectMemoryResponse(BaseModel):
    """Response body for direct memory storage operations.

    Returns the status of the storage operation, the assigned memory ID,
    and per-backend storage results.

    Error Codes:
    - VALIDATION_ERROR: Request validation failed (invalid fields, missing required data)
    - EMBEDDING_ERROR: Failed to generate embedding vector for the content
    - STORAGE_ERROR: Database storage operation failed (ChromaDB or TimescaleDB)
    - INTERNAL_ERROR: Unexpected server error during processing
    """

    status: Literal["success", "error"] = Field(
        ...,
        description="Operation status: 'success' or 'error'",
        example="success",
    )
    memory_id: Optional[str] = Field(
        default=None,
        description="UUID of the stored memory (present on success)",
        example="mem_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    )
    message: str = Field(
        ...,
        description="Human-readable status message",
        example="Memory stored successfully",
    )
    storage: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Storage status per backend. Keys: 'chromadb' (always), 'stored_in_episodic', 'stored_in_emotional', 'stored_in_procedural' (conditional based on request fields)",
        example={"chromadb": True, "stored_in_episodic": True},
    )
    error_code: Optional[
        Literal["VALIDATION_ERROR", "EMBEDDING_ERROR", "STORAGE_ERROR", "INTERNAL_ERROR"]
    ] = Field(
        default=None,
        description="Error code when status is 'error'. Values: VALIDATION_ERROR (invalid input), EMBEDDING_ERROR (vector generation failed), STORAGE_ERROR (database write failed), INTERNAL_ERROR (unexpected failure)",
        example=None,
    )


class DeleteMemoryResponse(BaseModel):
    """Response body for memory deletion operations.

    Returns the status of the deletion operation and per-backend results.
    Deletes from all storage backends where the memory exists: ChromaDB (always),
    and optionally episodic_memories, emotional_memories, procedural_memories tables.
    """

    status: Literal["success", "error"] = Field(
        ...,
        description="Operation status: 'success' or 'error'",
        example="success",
    )
    deleted: bool = Field(
        ...,
        description="True if memory was successfully deleted from at least one backend",
        example=True,
    )
    memory_id: str = Field(
        ...,
        description="The requested memory ID",
        example="mem_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    )
    storage: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Deletion status per backend. Keys: 'chromadb', 'episodic_memories', 'emotional_memories', 'procedural_memories'. Value is True if deleted, False if not found or failed.",
        example={"chromadb": True, "episodic_memories": True, "emotional_memories": False, "procedural_memories": False},
    )
    message: Optional[str] = Field(
        default=None,
        description="Status or error message providing details about the deletion operation",
        example="Memory deleted successfully from all backends",
    )


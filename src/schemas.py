from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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


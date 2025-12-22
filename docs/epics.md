# Agentic Memories v3.0 - Epic Breakdown

**Author:** Ankit
**Date:** 2025-11-16 (Revised)
**Project Level:** BMad Method (Brownfield Enhancement)
**Target Scale:** Platform Enhancement - User Profiles & MCP Developer Platform
**Scope:** API-First (No UI, No Auth for MVP)

---

## Overview

This document provides the complete epic and story breakdown for Agentic Memories v3.0, decomposing the requirements from the [PRD](./PRD.md) v2.0 into implementable backend API stories.

**Living Document Notice:** This is the revised version (v3.0) focused on **API-first** implementation. MCP developer tools, UI, and Authentication have been moved to post-MVP.

**Revision Summary (v3.0 - API-First):**
- **MVP Scope Reduced:** 21 stories → 9 stories (faster time to value)
- **Epic 1:** Profile Foundation (8 stories) - Database, extraction, CRUD APIs, caching
- **Epic 2:** Companion Integration (1 story) - Basic profile loading via API
- **Deferred to Post-MVP:** MCP Infrastructure (Epic 3), MCP Tools (Epic 4), Advanced Companion (Epic 5)
- **Focus:** Pure backend profile APIs - no MCP, no UI, no auth

---

## Functional Requirements Inventory

**Total: 86 Functional Requirements** (Reduced from 105 by removing UI and Auth)

### User Profile Management (FR1-FR24)

**Profile Creation & Population**
- FR1: System extracts profile-worthy information from conversations using LLM
- FR2: System assigns confidence scores (0-100%) to all profile fields
- FR3: Users can manually edit any profile field through API
- FR4: System tracks profile completeness score across all categories

**Profile Gap Detection & Questioning**
- FR5: Companion detects missing profile fields when loaded for conversation
- FR6: Companion asks targeted questions to fill profile gaps during natural conversation flow
- FR7: System prioritizes high-value profile gaps over low-priority gaps
- FR8: System avoids repetitive questioning (max 1 profile question per conversation, cooldown)

**Profile Updates & Confidence**
- FR9: System proposes profile updates when high-confidence new information detected (>80%)
- FR10: Users can approve or reject proposed profile updates via API
- FR11: System accumulates low-confidence profile candidates (<80%) until evidence strengthens
- FR12: Profile confidence scores update automatically as supporting evidence increases

**Profile Data Categories**
- FR13: Profile stores Core Identity data
- FR14: Profile stores Personality & Psychology data
- FR15: Profile stores Goals & Aspirations
- FR16: Profile stores Interests & Preferences
- FR17: Profile stores Relationships & Social Context

**Profile Access & Data Management**
- FR18: Users can export complete profile data in JSON format via API
- FR19: Users can import previously exported profile data via API
- FR20: Users can delete entire profile via API (right to be forgotten)
- FR21: System provides audit log API for profile access and changes
- FR22: System provides API to query profile completeness per category
- FR23: System provides API to view confidence scores for all profile fields
- FR24: System provides API to flag low-confidence fields (<50%)

### MCP Developer Platform - Core Tools (FR25-FR48)

**Financial Tool (FR25-FR30)**
- FR25-FR30: Portfolio, transactions, goals, spending patterns, discussions, aggregated response

**Skills Tool (FR31-FR36)**
- FR31-FR36: Procedural memories, progression, learning goals, activities, dependency graph, recommendations

**Social Tool (FR37-FR42)**
- FR37-FR42: Relationships, interactions, preferences, dynamics, events, aggregated context

**Content Tool (FR43-FR48)**
- FR43-FR48: Media consumed, preferences, learning resources, creators, discussions, patterns

### MCP Developer Platform - Growth Tools (FR49-FR63) [Post-MVP]

**Health/Fitness Tool (FR49-FR53)**
- FR49-FR53: Sleep, exercise, wellness goals, discussions, aggregated context

**Calendar/Schedule Tool (FR54-FR58)**
- FR54-FR58: Routines, events, time preferences, scheduling, aggregated context

**Location/Places Tool (FR59-FR63)**
- FR59-FR63: Favorite locations, memories, travel preferences, history, aggregated context

### MCP Platform Infrastructure (FR64-FR71)

**MCP Tool Discovery & Metadata (FR64-FR68)**
- FR64: Tools expose capability descriptions
- FR65: Tools follow MCP standard format
- FR66: Tools support version negotiation
- FR67: Developers can query available tools via discovery endpoint
- FR68: Each tool returns schema definition

**Performance & Caching (FR69-FR71)**
- FR69: System caches MCP tool responses in Redis
- FR70: Tool responses <100ms for pre-aggregated queries
- FR71: System logs all MCP tool requests for analytics

### Companion AI Integration (FR72-FR81)

**Profile-Augmented Conversations (FR72-FR76)**
- FR72: Companion loads user profile at conversation start
- FR73: Companion uses profile data to personalize communication style
- FR74: Companion references profile context without re-asking
- FR75: Companion surfaces relevant profile data during conversations
- FR76: Companion updates profile confidence scores based on conversation

**Memory Retrieval Enhancement (FR77-FR81)**
- FR77: `/v1/retrieve` can filter memories by profile attributes
- FR78: Hybrid retrieval prioritizes memories aligned with user profile
- FR79: Narrative construction uses profile baseline to enrich coherence
- FR80: Persona-aware retrieval considers profile data
- FR81: Memory search results include profile context summary

### System Administration (FR82-FR86)

**Profile Data Management (FR82-FR86)**
- FR82: View profile completeness statistics via API
- FR83: Monitor profile extraction accuracy via API
- FR84: Track profile confidence score distributions
- FR85: Configure profile extraction sensitivity via API
- FR86: Analytics API on profile gap patterns

---

## Epic Structure Summary

**2 MVP Epics (API-First)** covering 7 stories, delivering immediate value through backend APIs:

1. **Profile Foundation** - Database schema, extraction pipeline, CRUD APIs (6 stories, Stories 1.3 & 1.4 deferred)
2. **Companion Integration** - Profile-aware conversations via API (1 story)

**Post-MVP Epics (Deferred):**
- **MCP Infrastructure** - Protocol implementation, tool registry, caching (4 stories)
- **Core MCP Tools** - Financial, Skills, Social, Content developer tools (8 stories)
- **Advanced Companion Features** - Gap detection, confidence updates, retrieval enhancement (4 stories)
- **Growth MCP Tools** - Health, Calendar, Location tools (FR49-FR63)
- **Authentication & Authorization** - API keys, OAuth2, rate limiting
- **UI Components** - Dashboard, wizard, developer portal

**Sequencing Rationale:**
- **Epic 1** builds complete profile API system (immediate backend value)
- **Epic 2** integrates profiles into existing orchestrator (enhances conversations)
- **Post-MVP** MCP tools can be added later once API foundation is proven

---

## FR Coverage Map

**MVP Epics (API-First):**

**Epic 1 - Profile Foundation**
- Covers: FR1-FR8, FR13-FR24, FR82-FR86 (FR9-FR12 deferred with Stories 1.3 & 1.4)
- 6 MVP stories: Database, extraction, CRUD APIs, completeness, import/export, admin analytics
- Stories 1.3 (confidence aggregation) and 1.4 (proposal/approval) deferred to post-MVP
- Deliverable: Complete profile CRUD API system with direct-write extraction and LLM confidence

**Epic 2 - Companion Integration**
- Covers: FR72-FR76 (profile-aware conversations via API)
- 1 story: Load profile at conversation start, inject context
- Depends on: Epic 1
- Deliverable: Orchestrator uses profile API to enhance conversations

**Post-MVP Epics (Deferred):**

**Epic 3 - MCP Infrastructure** (Moved from MVP)
- Covers: FR64-FR71 (MCP protocol, tool registry, caching)
- 4 stories
- Depends on: Epic 1 (profile data exists)

**Epic 4 - Core MCP Tools** (Moved from MVP)
- Covers: FR25-FR48 (Financial, Skills, Social, Content tools)
- 8 stories
- Depends on: Epic 1 + Epic 3

**Epic 5 - Advanced Companion Features** (Expanded from old Epic 4)
- Covers: FR77-FR81 (retrieval enhancement, gap detection, confidence updates)
- 4 stories
- Depends on: Epic 1 + Epic 2

---

## Epic 1: Profile Foundation

**Goal:** Build foundational profile system with database schema, extraction pipeline, and core API capabilities.

**Dependencies:** None (first epic)

**Estimated Stories:** 6 MVP stories (Stories 1.3 and 1.4 deferred to post-MVP)

**FR Coverage:** FR1-FR8, FR12-FR24, FR82-FR86 (FR9-FR12 deferred with Stories 1.3 and 1.4)

---

### Story 1.1: User Profiles Database Schema & Migration

As a **backend developer**,
I want **a comprehensive user_profiles PostgreSQL table with all profile categories**,
So that **the system can store structured, queryable profile data separate from dynamic memories**.

**Acceptance Criteria:**

**Given** the existing database schema with identity_memories table
**When** the migration is executed
**Then** a new `user_profiles` table is created with columns for:
- Core Identity (name, age, gender, pronouns, location, timezone, occupation, education, birth_date)
- Personality (values JSONB, beliefs JSONB, communication_style VARCHAR, personality_traits JSONB, emotional_patterns JSONB)
- Goals & Aspirations (short_term_goals JSONB, long_term_goals JSONB, current_challenges JSONB, aspirations JSONB)
- Interests (hobbies JSONB, content_preferences JSONB, learning_interests JSONB, favorites JSONB)
- Relationships (important_people JSONB, social_preferences JSONB, relationship_dynamics JSONB)
- Metadata (user_id UUID PK, completeness_score NUMERIC, created_at, updated_at)

**And** each profile field has an associated confidence score column (e.g., name_confidence INTEGER 0-100)

**And** a profile_field_audit table is created to track field changes:
- audit_id, user_id, field_name, old_value, new_value, confidence_before, confidence_after, change_source, timestamp

**And** indexes are created for user_id lookups and confidence filtering

**Prerequisites:** None (foundational story)

**Technical Notes:**
- Use psycopg connection pool from existing timescale_client.py
- Follow migration naming convention: `migrations/postgres/009_user_profiles_table.up.sql`
- JSONB columns for flexibility with nested data structures
- Confidence scores as separate INT columns (e.g., name_confidence, age_confidence)
- Consider partial indexes for low-confidence fields (<50%) to optimize gap detection queries
- Total columns: ~35 fields (9 core + 5 personality + 4 goals + 4 interests + 3 relationships + metadata + ~25 confidence columns)

---

### Story 1.2: Profile Extraction LLM Pipeline

As a **backend developer**,
I want **an LLM-powered extraction pipeline that analyzes conversations and extracts profile-worthy information**,
So that **user profiles can be populated organically from natural conversation flow**.

**Acceptance Criteria:**

**Given** a conversation turn submitted via `/v1/store` endpoint
**When** the LangGraph extraction pipeline runs
**Then** the system invokes a new "profile extraction" node after existing memory extraction

**And** the profile extractor uses GPT-4 with structured output to identify:
- Which profile category the information belongs to (Core Identity, Personality, Goals, Interests, Relationships)
- Specific field name within that category
- Extracted value
- Confidence score (0-100) based on explicitness and context

**And** extraction results are stored in a `profile_extraction_candidates` table with:
- candidate_id, user_id, conversation_id, turn_id, category, field_name, extracted_value, confidence_score, extraction_timestamp, status (pending/approved/rejected)

**And** high-confidence extractions (>80%) trigger profile update proposals
**And** low-confidence extractions (<80%) are accumulated until evidence strengthens

**Prerequisites:**
- Story 1.1 (database schema)
- Existing LangGraph extraction pipeline (src/extraction/)

**Technical Notes:**
- Extend src/extraction/extraction_graph.py with new profile_extraction_node
- Use structured output with Pydantic models for type safety
- Implement initial confidence scoring in extraction:
  - Explicitness weight: 40% (direct statement vs. inferred)
  - Context clarity weight: 30% (unambiguous vs. ambiguous)
  - Source reliability weight: 30% (user vs. third-party mention)
- Batch multiple candidates before LLM call to reduce costs
- Add Langfuse tracing for extraction monitoring

---

### ~~Story 1.3: Profile Confidence Scoring Engine~~ [DEFERRED TO POST-MVP]

**Status:** Moved to Future Enhancements (2025-11-16)

**Reason:** With direct-write model, Story 1.2 uses simple replacement strategy (latest/highest confidence wins). Confidence aggregation from multiple extractions adds complexity without clear MVP value. Trust LLM extraction confidence scores. Profile_sources table maintains audit trail for future analysis if needed.

**See:** `docs/sprint-artifacts/scope-change-2025-11-16.md` for full decision record.

---

### ~~Original Story 1.3 Specification (Deferred)~~

<details>
<summary>Click to expand original story details</summary>

As a **backend developer**,
I want **an automated confidence scoring system that updates profile field confidence based on supporting evidence**,
So that **profile reliability improves as more conversational evidence accumulates**.

**Acceptance Criteria:**

**Given** multiple profile extraction candidates for the same field (e.g., 3 candidates for "occupation")
**When** the confidence scoring engine runs
**Then** the system calculates aggregate confidence using:
- Frequency (30%): Number of independent mentions
- Recency (25%): Time decay factor (recent mentions weighted higher)
- Explicitness (25%): Average explicitness scores from extractions
- Source diversity (20%): Different conversation contexts

**And** the aggregate confidence score (0-100) is stored in the user_profiles table confidence column

**And** when aggregate confidence crosses 80% threshold, the system:
- Moves candidate to "ready_for_approval" status
- Creates entry in profile_update_proposals table

**And** when aggregate confidence is below 80%, the system:
- Keeps candidate in "pending" status
- Continues accumulating evidence from future conversations

**Prerequisites:**
- Story 1.1 (database schema)
- Story 1.2 (extraction pipeline)

**Technical Notes:**
- Implement as src/services/profile_confidence.py
- Time decay function: confidence_multiplier = 1.0 / (1 + days_since_extraction / 30)
- Frequency scoring: base_score + (num_mentions - 1) * 10, capped at 100
- Run confidence re-calculation on:
  - New extraction candidate created
  - Daily batch job for all pending candidates
- Store calculation breakdown in JSONB for transparency

</details>

---

### ~~Story 1.4: Profile Update Proposal & Approval API~~ [DEFERRED TO POST-MVP]

**Status:** Moved to Future Enhancements (2025-11-16)

**Reason:** Story 1.2 implementation uses direct-write approach. Profile extractions write directly to `profile_fields` table with confidence tracking. Manual correction available via Story 1.5 CRUD APIs. This story requires additional infrastructure (proposals table, candidates table) not in current schema.

**See:** `docs/sprint-artifacts/scope-change-2025-11-16.md` for full decision record.

---

### ~~Original Story 1.4 Specification (Deferred)~~

<details>
<summary>Click to expand original story details</summary>

As a **backend developer**,
I want **API endpoints for proposing profile updates and handling user approval/rejection**,
So that **users maintain control over what gets added to their deterministic profile**.

**Acceptance Criteria:**

**Given** a high-confidence profile extraction (>80%) in "ready_for_approval" status
**When** the system checks for pending proposals
**Then** a profile update proposal is created in `profile_update_proposals` table with:
- proposal_id, user_id, field_name, current_value, proposed_value, confidence_score, supporting_evidence (array of conversation excerpts), created_at, status (pending/approved/rejected)

**And** a new API endpoint `GET /v1/profile/proposals` returns all pending proposals for a user

**And** a new API endpoint `POST /v1/profile/proposals/{proposal_id}/approve` updates:
- Sets proposal status to "approved"
- Updates user_profiles table with proposed_value and confidence_score
- Logs change in profile_field_audit table
- Returns updated profile

**And** a new API endpoint `POST /v1/profile/proposals/{proposal_id}/reject` updates:
- Sets proposal status to "rejected"
- Decreases confidence scores for associated candidates by 20%
- Returns rejection confirmation

**Prerequisites:**
- Story 1.1 (database schema)
- Story 1.3 (confidence scoring)

**Technical Notes:**
- Create src/routers/profile_proposals.py
- Include conversation excerpts (max 3) as supporting evidence in proposals
- Approval/rejection triggers audit log entry
- Consider rate limiting (max 1 proposal per conversation to avoid overwhelming users)
- Return proposals sorted by confidence score (highest first)
- No authentication enforcement for MVP

</details>

---

### Story 1.5: Profile CRUD API Endpoints

As a **backend developer**,
I want **complete CRUD API endpoints for user profiles**,
So that **users and the companion can read, create, update, and delete profile data programmatically**.

**Acceptance Criteria:**

**Given** a user request with user_id parameter
**When** calling `GET /v1/profile?user_id=...`
**Then** the system returns complete user profile with all categories and confidence scores

**And** when calling `GET /v1/profile/{category}?user_id=...` (e.g., /v1/profile/core-identity)
**Then** the system returns only that category's fields

**And** when calling `PUT /v1/profile/{category}/{field}` with `{"user_id": "...", "value": "...", "source": "manual"}`
**Then** the system updates the field, sets confidence to 100%, logs audit entry

**And** when calling `DELETE /v1/profile?user_id=...` with confirmation
**Then** the system deletes all profile data (right to be forgotten)

**And** when calling `GET /v1/profile/completeness?user_id=...`
**Then** the system returns completeness score (% of fields populated) per category

**Prerequisites:**
- Story 1.1 (database schema)
- Story 1.4 (approval workflow)

**Technical Notes:**
- Create src/routers/profile.py following FastAPI patterns
- Completeness calculation: (populated_fields / total_fields) * 100 per category
- Manual edits always set confidence to 100% (manual source is authoritative)
- DELETE requires confirmation parameter (simple string match, no token for MVP)
- Return formats:
  - Full profile: ~5KB JSON with all categories
  - Category: ~1KB JSON
  - Completeness: lightweight JSON with percentages
- No authentication for MVP - rely on user_id parameter

---

### Story 1.6: Profile Completeness Tracking

As a **system**,
I want **automatic tracking of profile completeness across all categories**,
So that **the system knows which profile gaps to prioritize for filling**.

**Acceptance Criteria:**

**Given** a user profile with some populated fields
**When** profile data changes (via approval, manual edit, or deletion)
**Then** the system recalculates completeness_score for each category:
- Core Identity: 9 total fields
- Personality: 5 total fields
- Goals: 4 total fields
- Interests: 4 total fields
- Relationships: 3 total fields

**And** the system calculates overall completeness = average of all category scores

**And** completeness scores are stored in user_profiles.completeness_score (overall) and category-specific columns

**And** the system identifies "high-value gaps" as:
- Core Identity fields (highest priority)
- Fields with zero confidence (never extracted)
- Fields relevant to user's goals (if goals are populated)

**And** gap prioritization list is cached in Redis for fast companion access

**Prerequisites:**
- Story 1.1 (database schema)
- Story 1.5 (CRUD API)

**Technical Notes:**
- Implement as src/services/profile_completeness.py
- Trigger recalculation on:
  - Profile field update
  - Proposal approval
  - Manual edit
- Store completeness breakdown in JSONB:
  ```json
  {
    "overall": 67,
    "categories": {
      "core_identity": 78,
      "personality": 60,
      "goals": 50,
      "interests": 75,
      "relationships": 33
    },
    "high_value_gaps": ["birth_date", "long_term_goals", "important_people"]
  }
  ```
- Cache in Redis with key: `profile_completeness:{user_id}`, TTL 1 hour

---

### Story 1.7: Profile Data Import/Export

As a **user**,
I want **to export my complete profile as JSON and import previously exported data via API**,
So that **I can back up my profile and migrate between systems if needed**.

**Acceptance Criteria:**

**Given** a user request with user_id
**When** calling `GET /v1/profile/export?user_id=...`
**Then** the system returns complete profile as JSON including:
- All profile fields with current values
- All confidence scores
- Completeness breakdown
- Export timestamp and version

**And** when calling `POST /v1/profile/import` with previously exported JSON + user_id
**Then** the system validates JSON schema and imports data:
- Overwrites existing profile fields with imported values
- Sets confidence scores from import (or defaults to 100% if not present)
- Logs import event in audit table
- Returns success confirmation

**And** import validation checks:
- JSON schema matches current profile structure
- All field types are valid
- Confidence scores are 0-100
- No malicious data (SQL injection, XSS)

**Prerequisites:**
- Story 1.1 (database schema)
- Story 1.5 (CRUD API)

**Technical Notes:**
- Export format versioning: include "schema_version": "1.0" for future compatibility
- Export file ~10-50KB depending on profile richness
- Import validation using Pydantic models
- Handle partial imports (if some fields fail validation, import valid ones)
- Log import source in audit: `change_source = "import"`
- No rate limiting for MVP

---

### Story 1.8: Profile Admin Analytics APIs

As a **system administrator**,
I want **API endpoints for profile extraction accuracy and completeness statistics across all users**,
So that **I can monitor system health and tune extraction sensitivity**.

**Acceptance Criteria:**

**Given** an admin request
**When** calling `GET /admin/profile/stats`
**Then** the system returns aggregate statistics:
- Total users with profiles
- Average profile completeness per category
- Distribution of confidence scores (0-50%, 50-80%, 80-100%)
- Extraction accuracy (% of proposals approved vs rejected)
- Most common profile gaps across users

**And** when calling `GET /admin/profile/config`
**Then** the system returns current extraction configuration:
- Confidence threshold for auto-approval (default 80%)
- Confidence scoring weights (frequency, recency, explicitness, diversity)
- Extraction sensitivity level

**And** when calling `PUT /admin/profile/config` with updated weights
**Then** the system updates configuration in database and applies to future extractions

**Prerequisites:**
- Story 1.2 (extraction pipeline)
- Story 1.3 (confidence scoring)
- Story 1.6 (completeness tracking)

**Technical Notes:**
- Create src/routers/admin_profile.py
- No authentication for MVP - trust admin endpoints not exposed publicly
- Stats calculation:
  - Run daily aggregation job, cache results in Redis
  - Real-time endpoint queries cached data (updated every 24h)
- Configuration stored in new table: `profile_extraction_config`
- Config changes logged in `system_config_audit` table

---

## Epic 2: Companion Integration

**Goal:** Integrate user profiles into existing orchestrator for profile-aware conversations.

**Dependencies:** Epic 1 (Profile Foundation)

**Estimated Stories:** 1

**FR Coverage:** FR72-FR76 (basic profile loading and context injection)

---

### Story 2.1: Profile-Aware Orchestrator Integration

As a **backend developer**,
I want **the orchestrator to automatically load and inject user profile at conversation start**,
So that **the companion AI can personalize responses and reference known information**.

**Acceptance Criteria:**

**Given** a conversation starts via `/v1/orchestrator/message` or `/v1/store`
**When** the orchestrator initializes for a user_id
**Then** the system calls `GET /v1/profile?user_id=...` to load complete profile

**And** profile data is injected into the orchestrator context as structured metadata
**And** profile summary (top 10 fields) is included in LLM system prompt:
```
User Profile Context:
- Name: [name] (if known)
- Communication Preference: [style]
- Top Goals: [1-3 goals]
- Key Interests: [1-3 interests]
```

**And** profile load is cached for the conversation duration (avoid re-querying each turn)
**And** if profile API returns empty/error, orchestrator continues normally (graceful degradation)

**Prerequisites:**
- Story 1.5 (Profile CRUD API)
- Existing `src/memory_orchestrator.py`

**Technical Notes:**
- Modify `AdaptiveMemoryOrchestrator.__init__()` or `stream_message()` to call profile API
- Use existing `ProfileAggregationService` internally (or call API endpoint)
- Cache profile in orchestrator session state: `self._profile_cache[user_id] = profile_data`
- TTL: session duration (cleared on orchestrator restart)
- Inject top fields only (avoid bloating system prompt >500 tokens)
- Profile load time target: <50ms (should be cached in Redis from Story 1.8)

---

## Post-MVP Epics

The following epics have been **moved to post-MVP** to focus on delivering immediate value through backend APIs. Developer tools (MCP) and advanced companion features will be added once the core profile system is stable.

---

## Epic 3: MCP Infrastructure [POST-MVP]

**Goal:** Build MCP platform infrastructure including protocol implementation, tool registry, caching, and logging.

**Dependencies:** Epic 1 (Profile Foundation) for user data

**Estimated Stories:** 4

**FR Coverage:** FR64-FR71

**Note:** Authentication stories (API keys, OAuth2, rate limiting) deferred to post-MVP

---

### Story 2.1: MCP Protocol Implementation & Tool Registry

As a **backend system**,
I want **to implement MCP protocol standards and a tool registry**,
So that **MCP tools follow consistent format and are discoverable by clients**.

**Acceptance Criteria:**

**Given** MCP tools need standardized interface
**When** implementing MCP endpoints
**Then** all tools follow MCP protocol structure:
- Request format: `{"tool": "financial", "params": {"user_id": "...", "context": "..."}, "version": "1.0"}`
- Response format: `{"tool": "financial", "result": {...}, "metadata": {"sources": [...], "confidence": 92, "cached": true}}`
- Error format: `{"error": {"code": "...", "message": "...", "details": {...}}}`

**And** a tool registry is created in `mcp_tool_registry` table:
- tool_id, tool_name, version, description, capabilities (JSONB), schema_definition (JSONB), status (active/deprecated)

**And** endpoint `GET /mcp/discovery` returns all active tools:
```json
{
  "tools": [
    {
      "name": "financial",
      "version": "1.0",
      "description": "Retrieve financial context combining portfolio, transactions, goals, and spending patterns",
      "capabilities": ["portfolio", "transactions", "goals", "spending"],
      "schema": {
        "params": {"user_id": "string", "context": "enum"},
        "response": {"portfolio": "object", "transactions": "array", ...}
      }
    }
  ]
}
```

**And** all MCP tools support version negotiation:
- Request header or param: `version: "1.0"`
- Response includes version: `"version": "1.0"`
- Reject unsupported versions with 400 Bad Request

**Prerequisites:** None (foundational MCP story)

**Technical Notes:**
- Create src/mcp/ directory with:
  - protocol.py (base classes, request/response models)
  - registry.py (tool registration and discovery)
  - tools/ (individual tool implementations)
- Use Pydantic for schema validation
- MCP version support: 1.0 initially
- Tool registry seeded via migration with 7 tools (financial, skills, social, content, health, calendar, location)
- Discovery endpoint cached in Redis, TTL 1 hour
- No authentication checks for MVP

---

### Story 2.2: MCP Tool Response Caching

As a **platform operator**,
I want **frequently requested MCP tool responses cached in Redis**,
So that **tool response times are <100ms and database load is minimized**.

**Acceptance Criteria:**

**Given** an MCP tool request for user profile or aggregated memories
**When** the same request was made recently (<5 minutes ago)
**Then** the system returns cached response from Redis instead of querying databases

**And** cache keys are structured as:
- `mcp_cache:{tool_name}:{user_id}:{params_hash}`
- TTL: 5 minutes (configurable per tool)

**And** cache invalidation occurs when:
- User profile updated → invalidate all `mcp_cache:*:{user_id}:*`
- New memory stored → invalidate memory-related caches
- Manual cache flush via admin endpoint

**And** cache hit/miss metrics are logged for monitoring:
- Cache hit rate per tool
- Average response time (cached vs uncached)

**And** response includes cache metadata:
- `"cached": true/false` in response metadata
- `"cache_age": 42` (seconds since cached)

**Prerequisites:**
- Story 2.1 (MCP protocol implementation)
- Redis infrastructure (existing)

**Technical Notes:**
- Implement caching decorator: `@mcp_cache(ttl=300)`
- Cache key includes MD5 hash of sorted params to ensure consistency
- Cached responses include metadata: cached_at, cache_ttl
- Invalidation patterns:
  - Profile update: Redis SCAN `mcp_cache:*:{user_id}:*` → DEL (safe for production)
  - Memory storage: invalidate specific tool caches
- Monitor cache size, implement LRU eviction if needed
- Cache warming for frequently accessed users (optional optimization)

---

### Story 2.3: MCP Request Logging & Analytics

As a **platform operator**,
I want **detailed logging of all MCP tool requests and responses**,
So that **I can monitor usage patterns, debug issues, and analyze tool adoption**.

**Acceptance Criteria:**

**Given** any MCP tool request
**When** the request is processed (success or error)
**Then** a log entry is created in `mcp_request_logs` table:
- log_id, user_id, tool_name, params (JSONB), response_status (success/error), response_time_ms, cache_hit (boolean), timestamp

**And** logs are also written to application logs with structured format:
```json
{
  "event": "mcp_request",
  "tool": "financial",
  "user_id": "...",
  "status": "success",
  "response_time_ms": 87,
  "cache_hit": true,
  "timestamp": "2025-11-16T10:30:00Z"
}
```

**And** an admin analytics endpoint `GET /admin/mcp/analytics` returns:
- Total requests per tool
- Average response time per tool
- Cache hit rate per tool
- Most active users
- Error rate per tool

**And** analytics can be filtered by:
- Date range
- Tool name
- User ID

**Prerequisites:**
- Story 2.1 (MCP protocol)
- Story 2.2 (Caching for cache_hit metric)

**Technical Notes:**
- Log to PostgreSQL for queryability, retain 90 days
- Async logging to avoid blocking requests (use FastAPI background tasks)
- Partition mcp_request_logs table by month for performance
- Analytics endpoint queries aggregated data (consider materialized view for performance)
- Include request_id for distributed tracing (UUID per request)
- Integrate with Langfuse for LLM observability (if tools use LLM)

---

### Story 2.4: MCP Error Handling & Standardization

As a **developer integrating MCP tools**,
I want **clear, actionable error messages when MCP requests fail**,
So that **I can quickly debug integration issues and fix my code**.

**Acceptance Criteria:**

**Given** an MCP tool request fails
**When** the error occurs
**Then** the response includes structured error with:
```json
{
  "error": {
    "code": "user_not_found",
    "message": "User ID '12345' does not exist in the system",
    "details": {
      "user_id": "12345",
      "action": "Verify the user_id parameter is correct"
    },
    "request_id": "req_abc123"
  }
}
```

**And** error codes are standardized:
- `user_not_found`: User ID doesn't exist (404)
- `tool_not_found`: Requested tool doesn't exist (404)
- `invalid_params`: Request params don't match schema (400)
- `invalid_version`: Unsupported MCP version (400)
- `internal_error`: Unexpected server error (500)
- `cache_error`: Redis cache unavailable (degraded, still returns data)

**And** all errors include:
- Human-readable message
- Actionable details/suggestions
- Request ID for support inquiries

**And** 5xx errors trigger logs for debugging

**Prerequisites:**
- Story 2.1 (MCP protocol)

**Technical Notes:**
- Create src/mcp/errors.py with custom exception classes
- Exception handler middleware catches and formats errors
- Request ID generated per request (UUID), included in logs and errors
- Graceful degradation: if cache unavailable, still query databases (log warning)
- Error responses follow same format as successful responses (consistent API)

---

## Epic 4: Core MCP Tools [POST-MVP]

**Goal:** Implement 4 core MCP tools (Financial, Skills, Social, Content) with smart aggregation from multiple data sources.

**Dependencies:**
- Epic 1 (Profile Foundation) for profile data
- Epic 3 (MCP Infrastructure) for protocol

**Estimated Stories:** 8 (2 per tool)

**FR Coverage:** FR25-FR48

**Status:** Deferred to post-MVP (API-first approach prioritized)

---

### Story 3.1: Financial Tool - Data Retrieval Logic

As a **third-party developer**,
I want **an MCP financial tool that aggregates portfolio holdings, transactions, goals, and spending patterns**,
So that **I can provide personalized financial advice in my application**.

**Acceptance Criteria:**

**Given** an MCP request to financial tool
**When** calling `POST /mcp/tools/financial` with params: `{"user_id": "...", "context": "portfolio"}`
**Then** the system retrieves and aggregates:
- Current portfolio holdings from PostgreSQL `portfolio_memories` table
- Recent transactions (last 30 days) from TimescaleDB `portfolio_memories` table
- Financial goals from user_profiles.goals (JSONB extraction)
- Spending patterns from episodic memories mentioning finances
- Recent financial discussions from episodic memories

**And** returns response:
```json
{
  "tool": "financial",
  "version": "1.0",
  "result": {
    "portfolio": {
      "total_value": 125000,
      "holdings": [...]
    },
    "recent_transactions": [...],
    "goals": {
      "short_term": "Save $10k for vacation",
      "long_term": "Retire by 55"
    },
    "spending_patterns": {
      "monthly_average": 3500,
      "categories": [...]
    },
    "recent_discussions": [...]
  },
  "metadata": {
    "sources": ["portfolio_memories", "user_profiles", "episodic_memories"],
    "confidence": 92,
    "last_updated": "2025-11-16T10:30:00Z",
    "cached": false
  }
}
```

**And** supports context filters:
- `context: "portfolio"` → only holdings
- `context: "transactions"` → only transactions
- `context: "goals"` → only goals
- `context: "full"` → everything (default)

**Prerequisites:**
- Story 2.1 (MCP protocol)
- Epic 1 (Profile foundation)
- Existing portfolio_memories table

**Technical Notes:**
- Implement in src/mcp/tools/financial_tool.py
- Use existing portfolio_memories table (structured and timescale)
- Query episodic memories with financial keywords: "money", "spent", "bought", "investment", "save"
- Aggregate confidence: average of source confidences
- Response cached for 5 minutes (Story 2.2)
- No authentication for MVP - rely on user_id parameter

---

### Story 3.2: Financial Tool - API Integration & Testing

As a **backend developer**,
I want **the financial tool fully integrated with MCP infrastructure and tested**,
So that **it's production-ready for developer integrations**.

**Acceptance Criteria:**

**Given** the financial tool implementation (Story 3.1)
**When** integrating with MCP infrastructure
**Then** the tool is registered in MCP tool registry with:
- tool_name: "financial"
- version: "1.0"
- schema definition for params and response
- capabilities: ["portfolio", "transactions", "goals", "spending", "discussions"]

**And** responses are cached with `mcp_cache:financial:{user_id}:{context}` key
**And** all requests logged to mcp_request_logs

**And** comprehensive tests exist:
- Unit tests for data retrieval logic (mock database responses)
- Integration tests with real database queries
- API endpoint tests (request/response validation)
- Error handling tests (invalid user, missing data, etc.)

**Prerequisites:**
- Story 3.1 (Financial tool implementation)
- Story 2.1, 2.2, 2.3 (MCP infrastructure)

**Technical Notes:**
- Add financial tool to registry via migration seed
- Tests in tests/mcp/test_financial_tool.py
- Test coverage >80% for tool code
- Mock database responses for faster unit tests
- E2E test with real profile + portfolio data
- Performance test: ensure <100ms for cached, <500ms for uncached

---

### Story 3.3: Skills Tool - Data Retrieval Logic

As a **third-party developer**,
I want **an MCP skills tool that provides procedural memories, skill progression, and learning recommendations**,
So that **I can build personalized learning experiences in my application**.

**Acceptance Criteria:**

**Given** an MCP request to skills tool
**When** calling `POST /mcp/tools/skills` with params: `{"user_id": "...", "skill_filter": "programming"}`
**Then** the system retrieves and aggregates:
- All procedural memories from PostgreSQL procedural_memories table
- Skill progression history with proficiency levels
- Learning goals from user_profiles.goals.learning
- Recent learning activities from episodic memories
- Skill dependencies from PostgreSQL (prerequisites, related skills)

**And** returns response:
```json
{
  "tool": "skills",
  "version": "1.0",
  "result": {
    "skills": [
      {
        "name": "Python",
        "proficiency": "Advanced",
        "progress": 85,
        "last_practiced": "2025-11-10"
      }
    ],
    "learning_goals": ["Master FastAPI", "Learn React"],
    "recent_activities": [...],
    "recommendations": [
      {
        "skill": "FastAPI",
        "reason": "Builds on Python expertise",
        "prerequisites_met": true
      }
    ],
    "skill_graph": {
      "nodes": [...],
      "edges": [...]
    }
  },
  "metadata": {
    "sources": ["procedural_memories", "user_profiles", "episodic_memories"],
    "confidence": 88,
    "cached": false
  }
}
```

**And** supports skill filtering by category (programming, languages, hobbies, etc.)

**Prerequisites:**
- Story 2.1 (MCP protocol)
- Epic 1 (Profile foundation)
- Existing procedural memory system

**Technical Notes:**
- Implement in src/mcp/tools/skills_tool.py
- Query PostgreSQL for skill dependencies using existing procedural_memory.py
- Procedural memories from PostgreSQL procedural_memories table
- Generate recommendations using algorithm:
  - Find skills with prerequisites met
  - Rank by relevance to user's learning goals
  - Return top 3-5
- Cache skill graph (changes infrequently), TTL 1 hour
- No authentication for MVP

---

### Story 3.4: Skills Tool - API Integration & Testing

As a **backend developer**,
I want **the skills tool fully integrated with MCP infrastructure and tested**,
So that **it's production-ready for developer integrations**.

**Acceptance Criteria:**

**Given** the skills tool implementation (Story 3.3)
**When** integrating with MCP infrastructure
**Then** the tool is registered in MCP tool registry
**And** caching and logging apply
**And** comprehensive tests exist covering:
- Skill retrieval from PostgreSQL
- Skill graph construction
- Recommendation generation
- API endpoint validation
- Error handling

**Prerequisites:**
- Story 3.3 (Skills tool implementation)
- Epic 2 infrastructure

**Technical Notes:**
- Similar integration pattern to Story 3.2
- Tests in tests/mcp/test_skills_tool.py
- Mock skill data for unit tests
- E2E test creates sample skill graph, validates retrieval
- Test coverage >80%

---

### Story 3.5: Social Tool - Data Retrieval Logic

As a **third-party developer**,
I want **an MCP social tool that provides relationship data, interaction patterns, and social preferences**,
So that **I can build socially-aware features in my application**.

**Acceptance Criteria:**

**Given** an MCP request to social tool
**When** calling `POST /mcp/tools/social` with params: `{"user_id": "...", "context": "relationships"}`
**Then** the system retrieves and aggregates:
- Important relationships from user_profiles.relationships.important_people (JSONB)
- Recent social interactions from episodic memories (mentions of people, events)
- Social preferences from user_profiles.relationships.social_preferences
- Relationship dynamics (frequency of mentions, recency)

**And** returns response:
```json
{
  "tool": "social",
  "version": "1.0",
  "result": {
    "relationships": [
      {
        "name": "Sarah",
        "relationship": "Best friend",
        "importance": "high",
        "last_interaction": "2025-11-14",
        "interaction_frequency": "weekly"
      }
    ],
    "recent_interactions": [...],
    "social_preferences": {
      "communication_style": "casual",
      "boundaries": ["No late-night calls"]
    },
    "upcoming_events": []
  },
  "metadata": {
    "sources": ["user_profiles", "episodic_memories"],
    "confidence": 85,
    "cached": false
  }
}
```

**And** supports context filters: relationships, interactions, preferences, full

**Prerequisites:**
- Story 2.1 (MCP protocol)
- Epic 1 (Profile with relationships data)

**Technical Notes:**
- Implement in src/mcp/tools/social_tool.py
- Query episodic memories for people mentions (ChromaDB + PostgreSQL)
- Extract interaction patterns:
  - Frequency: count mentions over time
  - Recency: last mention timestamp
  - Sentiment analysis: optional, post-MVP
- upcoming_events returns empty array initially (future: calendar integration)
- No authentication for MVP

---

### Story 3.6: Social Tool - API Integration & Testing

As a **backend developer**,
I want **the social tool fully integrated with MCP infrastructure and tested**,
So that **it's production-ready for developer integrations**.

**Acceptance Criteria:**

**Given** the social tool implementation (Story 3.5)
**When** integrating with MCP infrastructure
**Then** the tool is registered in registry
**And** caching, logging apply
**And** comprehensive tests exist

**Prerequisites:**
- Story 3.5 (Social tool implementation)
- Epic 2 infrastructure

**Technical Notes:**
- Similar integration pattern to Stories 3.2, 3.4
- Tests in tests/mcp/test_social_tool.py
- Test relationship extraction from episodic memories
- Test coverage >80%

---

### Story 3.7: Content Tool - Data Retrieval Logic

As a **third-party developer**,
I want **an MCP content tool that provides media consumption history, preferences, and learning resources**,
So that **I can recommend personalized content in my application**.

**Acceptance Criteria:**

**Given** an MCP request to content tool
**When** calling `POST /mcp/tools/content` with params: `{"user_id": "...", "content_type": "books"}`
**Then** the system retrieves and aggregates:
- Books, movies, media consumed from episodic memories
- Content preferences from user_profiles.interests.content_preferences
- Learning resources accessed (articles, courses, videos)
- Content creators followed (from profile or memories)
- Recent content discussions from episodic memories

**And** returns response:
```json
{
  "tool": "content",
  "version": "1.0",
  "result": {
    "consumed": {
      "books": ["Atomic Habits", "..."],
      "movies": ["Inception", "..."],
      "podcasts": ["Lex Fridman", "..."]
    },
    "preferences": {
      "genres": ["Sci-fi", "Self-improvement"],
      "formats": ["Books", "Podcasts"]
    },
    "learning_resources": [
      {
        "title": "FastAPI Tutorial",
        "type": "video",
        "accessed": "2025-11-12"
      }
    ],
    "creators_followed": ["Tim Ferriss", "..."],
    "recent_discussions": [...]
  },
  "metadata": {
    "sources": ["episodic_memories", "user_profiles"],
    "confidence": 80,
    "cached": false
  }
}
```

**And** supports content_type filters: books, movies, podcasts, articles, all

**Prerequisites:**
- Story 2.1 (MCP protocol)
- Epic 1 (Profile with content preferences)

**Technical Notes:**
- Implement in src/mcp/tools/content_tool.py
- Query episodic memories with content keywords: "read", "watched", "listened", "article", "book"
- Extract content items using keyword matching (LLM extraction optional post-MVP)
- Group by content_type for structured response
- creators_followed extracted from mentions in conversations
- No authentication for MVP

---

### Story 3.8: Content Tool - API Integration & Testing

As a **backend developer**,
I want **the content tool fully integrated with MCP infrastructure and tested**,
So that **it's production-ready for developer integrations**.

**Acceptance Criteria:**

**Given** the content tool implementation (Story 3.7)
**When** integrating with MCP infrastructure
**Then** the tool is registered in registry
**And** caching, logging apply
**And** comprehensive tests exist

**Prerequisites:**
- Story 3.7 (Content tool implementation)
- Epic 2 infrastructure

**Technical Notes:**
- Similar integration pattern to previous tool integrations
- Tests in tests/mcp/test_content_tool.py
- Test content extraction from episodic memories with various keywords
- Test coverage >80%

---

## Epic 5: Advanced Companion Features [POST-MVP]

**Goal:** Advanced profile features for companion AI including gap detection, confidence updates, and retrieval enhancement.

**Dependencies:** Epic 1 (Profile Foundation) + Epic 2 (Basic Companion Integration)

**Estimated Stories:** 4 (remaining from original Epic 4, excluding Story 4.1 which moved to MVP Epic 2)

**FR Coverage:** FR77-FR81 (retrieval enhancement, gap detection, confidence updates)

**Status:** Deferred to post-MVP (basic profile loading in Epic 2 is sufficient for MVP)

**Note:** Story 4.1 (Profile-Aware Conversation Initialization) has been moved to MVP as Epic 2, Story 2.1

---

### Story 4.1: Profile-Aware Conversation Initialization

As a **companion AI**,
I want **to automatically load user profile at conversation start**,
So that **I can personalize communication and reference known information without re-asking**.

**Acceptance Criteria:**

**Given** a conversation starts via `/v1/orchestrator/init` or `/v1/store` first turn
**When** the orchestrator initializes
**Then** the system loads complete user profile from cache or database

**And** profile is injected into system prompt or conversation context as structured data:
```
User Profile Summary:
- Name: [name] (Confidence: [score]%)
- Communication Style: [style]
- Key Goals: [top 3 goals]
- Important Relationships: [top 3 people]
- Interests: [top 5 interests]
```

**And** companion uses profile to:
- Address user by name if known
- Adapt communication style (formal/casual based on preference)
- Reference goals/interests in responses
- Avoid re-asking for known information

**Prerequisites:**
- Epic 1 (Profile foundation)
- Existing orchestrator (src/orchestrator/)

**Technical Notes:**
- Extend src/orchestrator/retrieval_orchestrator.py
- Load profile in initialization: `profile = profile_service.get_profile(user_id)`
- Inject profile summary into LLM system prompt
- Cache profile for session duration (avoid re-querying every turn)
- Graceful degradation: if profile empty, proceed normally
- Profile load time <10ms (cached)

---

### Story 4.2: Companion Profile Gap Detection

As a **companion AI**,
I want **to detect missing high-value profile fields when starting a conversation**,
So that **I can ask targeted questions to fill gaps during natural conversation flow**.

**Acceptance Criteria:**

**Given** a user starts a conversation with the companion
**When** the orchestrator initializes and loads profile
**Then** the system identifies high-value gaps from cached completeness data

**And** the system selects ONE gap to fill based on prioritization:
- Core Identity fields (highest priority: name, communication_style)
- Fields with zero confidence (never extracted)
- Fields relevant to conversation topic (if detectable)

**And** the system injects a profile gap question into the conversation:
- Natural phrasing based on conversation context
- Not in first turn (wait for 2-3 turns to establish flow)
- Max 1 profile question per conversation
- Cooldown: no questions if asked in last 24 hours

**And** when user responds, the response is analyzed by profile extraction pipeline (Story 1.2)

**Prerequisites:**
- Story 1.6 (Completeness tracking)
- Story 1.2 (Extraction pipeline)
- Story 4.1 (Profile loading)
- Existing orchestrator (src/orchestrator/)

**Technical Notes:**
- Load cached gap list from Redis: `profile_completeness:{user_id}`
- Implement gap_selection_strategy():
  - Check last_profile_question_time in session state or database
  - If cooldown active (< 24h), skip
  - Otherwise, select top gap from high_value_gaps list
- Inject question via system prompt or user message rewriting
- Track question_asked_at in session state
- Question templates: "I'd love to know more about [field] - what can you tell me?", "By the way, what's your [field]?"

---

### Story 4.3: Conversation-Based Confidence Updates

As a **companion AI**,
I want **to update profile confidence scores when conversations validate or contradict profile data**,
So that **profile accuracy improves over time based on user interactions**.

**Acceptance Criteria:**

**Given** a conversation where user explicitly confirms or corrects profile information
**When** the companion detects confirmation or correction
**Then** the system updates confidence scores:

**For Confirmations:**
- User says "Yes, that's right" or "Exactly" in response to profile reference
- Increase confidence by +5% (capped at 100%)
- Log confirmation in profile_field_audit

**For Corrections:**
- User says "Actually, it's..." or "No, I prefer..." correcting profile data
- Trigger profile extraction for corrected information
- Decrease old value confidence by -10%
- Create new extraction candidate with corrected value

**And** confidence updates are processed asynchronously (don't block conversation flow)

**Prerequisites:**
- Story 1.3 (Confidence scoring)
- Story 1.2 (Extraction pipeline)
- Story 4.1 (Profile loading)

**Technical Notes:**
- Implement confirmation/correction detection using LLM classification
- Simple patterns for MVP:
  - Confirmation: "yes", "correct", "exactly", "that's right"
  - Correction: "actually", "no", "it's", "prefer"
- Async processing using FastAPI background tasks
- Log all updates in profile_field_audit with source="conversation_validation"
- Update cached profile after confidence change

---

### Story 4.4: Profile-Filtered Memory Retrieval

As a **companion AI**,
I want **to filter retrieved memories by profile attributes**,
So that **memory search results are more relevant to user's interests and goals**.

**Acceptance Criteria:**

**Given** a memory retrieval query via `/v1/retrieve` or orchestrator
**When** user profile exists
**Then** the system can filter memories by profile attributes:
- Filter by interests: only memories mentioning user's hobbies/interests
- Filter by relationships: only memories involving specific people
- Filter by goals: only memories related to user's current goals

**And** existing `/v1/retrieve` endpoint accepts new optional parameters:
- `filter_by_interests: boolean` (default false)
- `filter_by_relationships: array<string>` (specific people)
- `filter_by_goals: boolean` (default false)

**And** hybrid retrieval prioritizes memories aligned with user profile:
- Memories mentioning user's interests get +10% relevance boost
- Memories involving important relationships get +15% boost
- Memories related to current goals get +20% boost

**Prerequisites:**
- Story 4.1 (Profile loading)
- Existing retrieval system (src/retrieval/)

**Technical Notes:**
- Extend src/retrieval/hybrid_retrieval.py
- Profile-based filtering happens after semantic/vector search
- Implement relevance boosting in ranking algorithm
- Use profile interests/relationships/goals from cached profile
- Graceful degradation: if profile empty, no filtering/boosting applied
- Performance: filtering should add <50ms to retrieval time

---

### Story 4.5: Profile-Enriched Memory Narratives

As a **companion AI**,
I want **to use profile baseline to enrich memory narratives with persistent context**,
So that **memory stories are more coherent and personalized**.

**Acceptance Criteria:**

**Given** a narrative construction request (existing `/v1/retrieve` with narrative mode)
**When** the system constructs a narrative from memories
**Then** the narrative includes profile context:
- Opens with brief user context: "As someone who values [values] and is working toward [goals]..."
- References user's perspective: "Given your interest in [interest]..."
- Connects memories to profile: "This relates to your goal of [goal]"

**And** memory search results include profile context summary:
```json
{
  "memories": [...],
  "narrative": "...",
  "profile_context": {
    "relevant_interests": ["coding", "learning"],
    "relevant_goals": ["Master FastAPI"],
    "relevant_relationships": ["Sarah (mentor)"]
  }
}
```

**And** profile enrichment is optional via parameter: `include_profile_context: boolean` (default true)

**Prerequisites:**
- Story 4.1 (Profile loading)
- Existing narrative construction (src/retrieval/)

**Technical Notes:**
- Extend src/retrieval/narrative_constructor.py
- Profile context injected into LLM prompt for narrative generation
- Extract relevant profile attributes based on memory content
- Template for profile context opening (customizable)
- Performance: narrative generation already uses LLM, minimal added latency

---

## Post-MVP Epics [High-Level]

### Epic 5: Growth MCP Tools

**Goal:** Expand MCP tool suite with Health/Fitness, Calendar/Schedule, and Location/Places tools.

**Dependencies:** Epic 3 (tool patterns established)

**Estimated Stories:** 6 (2 per tool)

**FR Coverage:** FR49-FR63

**Stories (High-Level):**

5.1 **Health/Fitness Tool - Data Retrieval** - Aggregate sleep patterns, exercise data, wellness goals, health discussions
5.2 **Health/Fitness Tool - Integration & Testing** - Full MCP integration

5.3 **Calendar/Schedule Tool - Data Retrieval** - Aggregate daily routines, upcoming events, time preferences, scheduling constraints
5.4 **Calendar/Schedule Tool - Integration & Testing** - Full MCP integration

5.5 **Location/Places Tool - Data Retrieval** - Aggregate favorite locations, location-based memories, travel preferences, location history
5.6 **Location/Places Tool - Integration & Testing** - Full MCP integration

**Implementation Notes:**
- Follow same patterns as Epic 3 core tools
- Data sources: episodic memories + profile fields
- Smart aggregation with confidence scores
- Full test coverage

---

### Epic 6: Authentication & Authorization

**Goal:** Add developer API key management, OAuth2 user authorization, and rate limiting.

**Dependencies:** Epic 2 (MCP Infrastructure), Epic 3 (Core Tools)

**Estimated Stories:** 7

**Deferred FRs:** Authentication requirements removed from MVP

**Stories (High-Level):**

6.1 **Developer API Key Registration & Management** - Registration, hashing, revocation
6.2 **OAuth2 User Authorization Flow** - Consent screen, token generation, scope validation
6.3 **Rate Limiting Per Developer API Key** - Redis-based rate limiting, tiered limits
6.4 **Scope-Based Permissions** - Tool-level access control
6.5 **User App Authorization Management** - View/revoke third-party access
6.6 **Security Audit Logging** - Track third-party access
6.7 **Rate Limit Error Handling** - Retry-after headers, clear error messages

---

### Epic 7: UI Components

**Goal:** Build web UI for profile management and developer portal.

**Dependencies:** Epic 1 (Profile APIs), Epic 6 (Auth for developer portal)

**Estimated Stories:** 8

**Deferred FRs:** All UI requirements removed from MVP

**Stories (High-Level):**

7.1 **Profile Dashboard** - View profile with confidence visualization
7.2 **Onboarding Wizard** - Initial profile setup flow
7.3 **Update Proposals UI** - Review and approve/reject proposals
7.4 **Profile Editing Interface** - Manual field editing
7.5 **Privacy Controls UI** - Visibility toggles, audit log viewer
7.6 **Developer Portal** - API key management dashboard
7.7 **OAuth Consent Screen** - Third-party app authorization UI
7.8 **Developer Documentation Site** - Interactive API docs, examples

---

### Epic 8: Developer Experience

**Goal:** Improve developer productivity with SDKs, examples, and debugging tools.

**Dependencies:** Epic 3 (Core Tools), Epic 6 (Auth)

**Estimated Stories:** 5

**Deferred FRs:** SDK and developer tooling requirements removed from MVP

**Stories (High-Level):**

8.1 **Python SDK** - Official library wrapping MCP tools
8.2 **JavaScript SDK** - NPM package for Node.js and browser
8.3 **Code Examples Repository** - GitHub repo with common use cases
8.4 **Webhooks for Data Changes** - Opt-in notifications
8.5 **Developer Debugging Tools** - Request replay, mock responses

---

## FR Coverage Matrix

This matrix validates that all 86 functional requirements are covered by at least one story.

| FR Range | Epic | Stories | Coverage |
|----------|------|---------|----------|
| FR1-FR4 | Epic 1 | 1.2, 1.5, 1.6 | ✅ Complete |
| FR5-FR8 | Epic 4 | 4.2 | ✅ Complete |
| FR9-FR12 | Epic 1 | 1.3, 1.4 | ✅ Complete |
| FR13-FR17 | Epic 1 | 1.1 (schema includes all categories) | ✅ Complete |
| FR18-FR24 | Epic 1 | 1.7 (import/export), 1.5 (APIs) | ✅ Complete |
| FR25-FR30 | Epic 3 | 3.1, 3.2 (Financial tool) | ✅ Complete |
| FR31-FR36 | Epic 3 | 3.3, 3.4 (Skills tool) | ✅ Complete |
| FR37-FR42 | Epic 3 | 3.5, 3.6 (Social tool) | ✅ Complete |
| FR43-FR48 | Epic 3 | 3.7, 3.8 (Content tool) | ✅ Complete |
| FR49-FR63 | Epic 5 | 5.1-5.6 (Growth tools) [Post-MVP] | ✅ Complete |
| FR64-FR68 | Epic 2 | 2.1 (MCP protocol & discovery) | ✅ Complete |
| FR69-FR71 | Epic 2 | 2.2, 2.3 (Caching, logging) | ✅ Complete |
| FR72-FR76 | Epic 4 | 4.1-4.3 (Profile-augmented conversations) | ✅ Complete |
| FR77-FR81 | Epic 4 | 4.4-4.5 (Enhanced retrieval) | ✅ Complete |
| FR82-FR86 | Epic 1 | 1.8 (Admin analytics) | ✅ Complete |

**Total Coverage: 86/86 FRs (100%)**

---

## Summary

**4 MVP Epics, 21 Stories:**
- **Epic 1: Profile Foundation** (8 stories) - Database, extraction, APIs
- **Epic 2: MCP Infrastructure** (4 stories) - Protocol, caching, logging
- **Epic 3: Core MCP Tools** (8 stories) - Financial, Skills, Social, Content
- **Epic 4: Companion Integration** (5 stories, can run parallel) - Profile-augmented AI

**4 Post-MVP Epics, ~26 Stories:**
- Epic 5: Growth MCP Tools (6 stories)
- Epic 6: Authentication & Authorization (7 stories)
- Epic 7: UI Components (8 stories)
- Epic 8: Developer Experience (5 stories)

**Epic Sequencing for Development:**

**Phase 1 - Profile Foundation (3-4 weeks)**
- Epic 1: Profile Foundation (8 stories)

**Phase 2 - MCP Platform (Parallel, 4-5 weeks)**
- Epic 2: MCP Infrastructure (4 stories) - 2 weeks
- Epic 3: Core MCP Tools (8 stories) - 3-4 weeks
- Epic 4: Companion Integration (5 stories) - 2 weeks (can overlap)

**Total Estimated MVP Timeline:** 7-9 weeks for Epics 1-4

**Post-MVP Timeline:** 8-12 weeks for Epics 5-8

**Technical Debt / Simplification:**
- Epic 9: Neo4j Removal (5 stories) - 3.5 days - See [epic-neo4j-removal.md](./epic-neo4j-removal.md)

**Next Steps:**
1. **Architecture Workflow** - Add technical implementation details (database schemas, API contracts, component designs)
2. **Solutioning Gate Check** - Validate PRD + Epics + Architecture alignment
3. **Sprint Planning** - Break stories into tasks, sequence sprints, begin implementation

---

**Living Document Notice:** This epic breakdown will be refined during Architecture workflow with specific technical implementation details, database migrations, API endpoint specifications, and integration patterns.

**Revision History:**
- v1.0 (2025-11-15): Initial with UI and Auth stories (105 FRs, 38 stories)
- v2.0 (2025-11-16): API-First revision, removed UI (Epic 2) and Auth (Epic 3 stories 3.1-3.4), simplified Epic 4 (86 FRs, 21 MVP stories)

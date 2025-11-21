# Agentic Memories v3.0 - User Profiles API

**Author:** Ankit
**Date:** 2025-11-16
**Version:** 3.0 (API-First MVP - MCP Deferred)

---

## Executive Summary

Agentic Memories v3.0 adds **Deterministic User Profiles** as a stable, API-accessible baseline of who the user is (demographics, personality, values, goals, preferences, relationships). This complements the existing dynamic memory system with a reliable identity layer.

**MVP Scope (API-First):**
- Complete profile CRUD APIs for structured user data
- LLM-powered profile extraction from conversations
- Confidence scoring and completeness tracking
- Profile-aware orchestrator for personalized conversations
- **Deferred to Post-MVP:** MCP developer tools, UI components, authentication

**Current State:**
Today, agentic-memories provides sophisticated memory storage and retrieval across 6 memory types (episodic, semantic, procedural, emotional, portfolio, identity) using polyglot persistence (5 databases). Memories are dynamically retrieved based on conversation context.

**Future State (MVP):**
With v3.0 MVP, companions will always know baseline user identity (deterministic profile) via REST APIs while continuing to use dynamic memories for context.

**Future State (Post-MVP):**
MCP developer tools will enable third-party apps (budgeting tools, fitness trackers, learning platforms) to integrate memory context via standardized protocol.

### What Makes This Special

**The Innovation:** Most memory systems are either fully deterministic (static user profiles) OR fully dynamic (conversational memory). Agentic Memories v3.0 uniquely combines both:

- **Deterministic Layer** (User Profile API) - Fast, stable baseline: "who you are"
- **Dynamic Layer** (Existing Memories) - Contextual, evolving: "what you're experiencing"
- **Future: Modular Access** (MCP Tools - Post-MVP) - Domain-specific retrieval for developers

This **hybrid architecture** gives companions the best of both worlds: instant access to stable identity while maintaining rich, contextual memory.

**The Compelling Moment:**
A companion can now say *"Based on your goal to save for a down payment (from profile) and your recent spending discussion last week (from episodic memory), let me help you adjust your budget."* - seamlessly blending stable profile data with dynamic conversational context.

---

## Project Classification

**Technical Type:** Platform Enhancement (Backend Profile APIs)
**Domain:** AI/ML - Memory & Context Systems
**Complexity:** Medium-High (Multi-database architecture, LLM integration)
**Field Type:** Brownfield (enhancing existing production system)
**MVP Scope:** API-First - Profile CRUD, Extraction, Orchestrator Integration
**Deferred:** MCP developer tools, UI components, authentication

**Context:**
This enhancement builds on an existing sophisticated system:
- Multi-part architecture (Python/FastAPI backend + React frontend)
- 6 memory types across 5 databases (ChromaDB, TimescaleDB, PostgreSQL, Neo4j, Redis)
- LangGraph extraction pipeline with persona-aware retrieval
- 15 REST API endpoints with hybrid multi-database queries
- Production deployment with Docker orchestration

**Enhancement Scope:**
Adding structured determinism (user profiles) and modular access (MCP tools) while preserving all existing flexibility and capabilities.

**MVP Constraints:**
- **No UI Components** - Pure API implementation, UI deferred to future phase
- **No Authentication** - Open API endpoints for testing, auth layer added post-MVP
- **Focus on Core Functionality** - Profile APIs + 4 Core MCP Tools working end-to-end

---

## Success Criteria

### Product Success

**For Companion Users:**
- Companion demonstrates knowledge of user's core identity within first 3 interactions (name, communication style, key preferences)
- Profile completeness reaches 70%+ within 2 weeks of regular use
- Profile extraction accuracy >85% (validated against manual corrections)

**For Developer Users:**
- Developer can integrate first MCP tool and get working memory context within 30 minutes
- MCP tools return rich, aggregated context combining profile + memories

### Technical Success

**Profile System:**
- Profile queries <10ms (deterministic data, no DB joins)
- Confidence scoring accuracy >85% (validated against user corrections)
- Profile updates trigger within 1 conversation turn when gaps detected

**MCP Tools:**
- Tool response time <100ms for pre-aggregated queries
- 99.5% uptime for MCP tool endpoints
- Zero breaking changes to existing REST API (backward compatibility)

---

## Product Scope

### MVP - Minimum Viable Product

**Phase 1: Profile Foundation**
- Database schema for user profiles (5 categories, confidence scores)
- LLM-powered profile extraction from conversations
- Profile CRUD APIs (create, read, update, delete)
- Profile completeness tracking
- Import/Export profile data

**Phase 2: MCP Infrastructure**
- MCP protocol implementation (request/response format)
- Tool registry and discovery endpoint
- Response caching in Redis
- Request logging for analytics

**Phase 3: Core MCP Tools**
- Financial Tool (portfolio, transactions, goals, spending)
- Skills Tool (procedural memories, progression, recommendations)
- Social Tool (relationships, interactions, preferences)
- Content Tool (media consumed, preferences, discussions)

**Phase 4: Companion Integration**
- Profile-augmented conversation initialization
- Gap detection and organic questioning
- Confidence updates from conversation validation
- Profile-filtered memory retrieval

### Post-MVP Features (Deferred)

**Authentication & Authorization:**
- Developer API key management
- OAuth2 user authorization flow
- Rate limiting per API key
- Scope-based permissions

**UI Components:**
- Profile dashboard with confidence visualization
- Onboarding wizard
- Update proposals review interface
- Developer portal and documentation

**Growth MCP Tools:**
- Health/Fitness Tool
- Calendar/Schedule Tool
- Location/Places Tool

**Developer Experience:**
- Python and JavaScript SDKs
- Interactive API documentation
- Code examples and tutorials
- Webhooks for data changes

---

## Domain Requirements

### User Profile System

**Purpose:** Create a deterministic, stable baseline of user identity that complements dynamic memories.

**Profile Categories:**

1. **Core Identity** (9 fields)
   - Name, age, gender, pronouns
   - Location, timezone
   - Occupation, education
   - Birth date

2. **Personality & Psychology** (5 fields)
   - Values (JSONB: integrity, creativity, family, etc.)
   - Beliefs (JSONB: political, spiritual, philosophical)
   - Communication style (formal, casual, direct, etc.)
   - Personality traits (JSONB: Big Five scores)
   - Emotional patterns (JSONB: triggers, coping mechanisms)

3. **Goals & Aspirations** (4 fields)
   - Short-term goals (JSONB array)
   - Long-term goals (JSONB array)
   - Current challenges (JSONB array)
   - Aspirations (JSONB array)

4. **Interests & Preferences** (4 fields)
   - Hobbies (JSONB array)
   - Content preferences (genres, formats, creators)
   - Learning interests (JSONB array)
   - Favorites (foods, activities, etc.)

5. **Relationships & Social Context** (3 fields)
   - Important people (JSONB: name, relationship, importance)
   - Social preferences (communication frequency, boundaries)
   - Relationship dynamics (interaction patterns)

**Confidence Scoring Algorithm:**

Each profile field has associated confidence score (0-100%):
- **Frequency (30%):** Number of independent mentions
- **Recency (25%):** Time decay (recent mentions weighted higher)
- **Explicitness (25%):** Direct statements vs. inferred
- **Source Diversity (20%):** Different conversation contexts

**Profile Population Strategies:**

1. **Organic Extraction** (Primary)
   - LLM analyzes every conversation for profile-worthy information
   - High-confidence extractions (>80%) → Propose update
   - Low-confidence extractions (<80%) → Accumulate until evidence strengthens

2. **Manual Entry** (Secondary)
   - API endpoints for direct profile updates
   - Manual edits always set confidence to 100%
   - Import/export for data portability

3. **Gap Detection** (Proactive)
   - Companion detects missing high-value fields
   - Asks targeted questions during conversation
   - Max 1 question per conversation, 24h cooldown

### MCP Tool Specifications

**Tool Architecture Pattern:**

Each MCP tool follows Smart Aggregation approach:
```
Tool Request
    ↓
Load user_profile (PostgreSQL/Redis) ← Deterministic baseline
    ↓
Load domain memories (ChromaDB, TimescaleDB, PostgreSQL) ← Dynamic context
    ↓
Load episodic context (Recent conversations mentioning domain)
    ↓
Combine & enrich
    ↓
Return aggregated JSON with metadata
```

**Core MCP Tools (MVP):**

1. **Financial Tool** (`/mcp/tools/financial`)
   - Current portfolio holdings
   - Recent transactions (30 days)
   - Financial goals from profile
   - Spending patterns
   - Recent financial discussions
   - Response time: <100ms (cached)

2. **Skills Tool** (`/mcp/tools/skills`)
   - All procedural memories
   - Skill progression history
   - Learning goals from profile
   - Recent practice sessions
   - Skill dependency graph (Neo4j)
   - Personalized recommendations

3. **Social Tool** (`/mcp/tools/social`)
   - Important relationships from profile
   - Recent social interactions
   - Social preferences and boundaries
   - Interaction patterns (frequency, sentiment)
   - Upcoming events (if available)

4. **Content Tool** (`/mcp/tools/content`)
   - Books, movies, media consumed
   - Content preferences from profile
   - Learning resources accessed
   - Content creators followed
   - Recent content discussions

**Growth Tools (Post-MVP):**

5. **Health/Fitness Tool** - Sleep, exercise, wellness
6. **Calendar/Schedule Tool** - Routines, events, time preferences
7. **Location/Places Tool** - Favorite places, travel preferences

---

## Technical Architecture

### Database Strategy

**User Profiles:**
- New `user_profiles` table in PostgreSQL (structured data)
- JSONB columns for flexible nested data (goals, interests, values)
- Separate confidence score columns (e.g., `name_confidence INT`)
- Redis caching layer for <10ms reads

**Profile Extraction:**
- `profile_extraction_candidates` table (pending updates)
- `profile_update_proposals` table (high-confidence candidates)
- `profile_field_audit` table (change history)

**MCP Infrastructure:**
- `mcp_tool_registry` table (tool metadata, schemas)
- `mcp_request_logs` table (analytics, debugging)
- Redis cache: `mcp_cache:{tool}:{user_id}:{params_hash}`

### Architecture Integration

**Extraction Pipeline Extension:**
```
Existing LangGraph Pipeline:
  Worthiness Check → Extract Memories → Classify Types
      ↓
  NEW: Profile Extraction Node
      ↓
  Identify profile-worthy info
  Calculate confidence
  Store as candidate or proposal
```

**API Coexistence:**
- Existing 15 REST endpoints unchanged (backward compatibility)
- New endpoints under `/v1/profile/` namespace
- New endpoints under `/v1/mcp/` namespace
- Existing `/v1/retrieve` extended with profile filters

**Data Flow:**

**Profile Population Flow:**
```
User Conversation
    ↓
LangGraph Extraction Pipeline
    ↓
Profile Extraction Node (NEW)
    ↓
Confidence Scorer
    ↓
[High Confidence >80%] → profile_update_proposals
[Low Confidence <80%] → profile_extraction_candidates (accumulate)
    ↓
Manual Approval API → user_profiles table
```

**MCP Tool Query Flow (No Auth):**
```
Developer App → MCP Tool Request
    ↓
Tool-Specific Aggregation Logic:
  - Load user_profile (PostgreSQL/Redis)
  - Load domain memories (ChromaDB, TimescaleDB, PostgreSQL)
  - Load episodic context
  - Combine and enrich
    ↓
Return aggregated JSON response
```

**Profile Gap Detection Flow:**
```
Companion Interaction Start
    ↓
Load user_profile from cache
    ↓
Check completeness score
    ↓
[Gap Detected] → Companion asks targeted question (max 1 per conversation)
[Complete >70%] → Proceed with conversation
```

---

## Functional Requirements

**COVERAGE NOTE:** These FRs capture core capabilities for MVP scope (API-First, No UI/Auth). Authentication, UI, and Growth Tools are deferred to post-MVP.

**Total: 86 Functional Requirements**

### User Profile Management (FR1-FR24)

**Profile Creation & Population**

- FR1: System extracts profile-worthy information from conversations using LLM (ongoing organic discovery)
- FR2: System assigns confidence scores (0-100%) to all profile fields based on evidence strength
- FR3: Users can manually edit any profile field through API
- FR4: System tracks profile completeness score across all categories (Core Identity, Personality, Goals, Interests, Relationships)

**Profile Gap Detection & Questioning**

- FR5: Companion detects missing profile fields when loaded for conversation
- FR6: Companion asks targeted questions to fill profile gaps during natural conversation flow
- FR7: System prioritizes high-value profile gaps (communication style, core values) over low-priority gaps
- FR8: System avoids repetitive questioning (max 1 profile question per conversation, 24h cooldown)

**Profile Updates & Confidence**

- FR9: System proposes profile updates when high-confidence new information is detected (>80% confidence threshold)
- FR10: Users can approve or reject proposed profile updates via API
- FR11: System accumulates low-confidence profile candidates (<80%) until evidence strengthens
- FR12: Profile confidence scores update automatically as supporting evidence increases

**Profile Data Categories**

- FR13: Profile stores Core Identity data (name, age, location, timezone, occupation, education, pronouns)
- FR14: Profile stores Personality & Psychology data (values, beliefs, communication style, personality traits, emotional patterns)
- FR15: Profile stores Goals & Aspirations (short-term goals, long-term goals, career ambitions, fears, dreams)
- FR16: Profile stores Interests & Preferences (entertainment, lifestyle habits, hobbies, food preferences, routines)
- FR17: Profile stores Relationships & Social Context (important people, pets, social preferences, celebration preferences)

**Profile Access & Data Management**

- FR18: Users can export complete profile data in JSON format via API
- FR19: Users can import previously exported profile data via API
- FR20: Users can delete entire profile via API (right to be forgotten)
- FR21: System provides audit log API for profile access and changes
- FR22: System provides API to query profile completeness per category
- FR23: System provides API to view confidence scores for all profile fields
- FR24: System provides API to flag low-confidence fields (<50%)

### MCP Developer Platform - Core Tools (FR25-FR48)

**Financial Tool**

- FR25: Financial Tool retrieves user's current portfolio holdings with aggregated data
- FR26: Financial Tool retrieves recent financial transactions (last 30 days default, configurable)
- FR27: Financial Tool retrieves user's financial goals and preferences from profile
- FR28: Financial Tool retrieves spending patterns and budget analysis
- FR29: Financial Tool retrieves recent financial discussions from episodic memories
- FR30: Financial Tool returns aggregated response combining all financial context sources

**Skills Tool**

- FR31: Skills Tool retrieves all procedural memories (skills user has or is learning)
- FR32: Skills Tool retrieves skill progression history with proficiency levels
- FR33: Skills Tool retrieves learning goals from user profile
- FR34: Skills Tool retrieves recent learning activities and practice sessions
- FR35: Skills Tool returns skill dependency graph (prerequisites, related skills)
- FR36: Skills Tool returns aggregated learning journey with recommendations

**Social Tool**

- FR37: Social Tool retrieves important relationships from user profile
- FR38: Social Tool retrieves recent social interactions from episodic memories
- FR39: Social Tool retrieves social preferences and boundaries from profile
- FR40: Social Tool retrieves relationship dynamics and interaction patterns
- FR41: Social Tool retrieves upcoming social events (if calendar integration exists)
- FR42: Social Tool returns aggregated social context

**Content Tool**

- FR43: Content Tool retrieves books, movies, media consumed (from episodic/semantic memories)
- FR44: Content Tool retrieves content preferences from user profile
- FR45: Content Tool retrieves learning resources and educational content accessed
- FR46: Content Tool retrieves content creators and influencers followed
- FR47: Content Tool retrieves recent content discussions from episodic memories
- FR48: Content Tool returns aggregated content consumption patterns

### MCP Developer Platform - Growth Tools (FR49-FR63) [Post-MVP]

**Health/Fitness Tool**

- FR49: Health Tool retrieves sleep patterns and quality metrics
- FR50: Health Tool retrieves exercise activities and fitness data
- FR51: Health Tool retrieves wellness goals from profile
- FR52: Health Tool retrieves health-related discussions and concerns
- FR53: Health Tool returns aggregated health and wellness context

**Calendar/Schedule Tool**

- FR54: Calendar Tool retrieves daily routines and habits from profile
- FR55: Calendar Tool retrieves upcoming events and commitments
- FR56: Calendar Tool retrieves time preferences (productive hours, downtime preferences)
- FR57: Calendar Tool retrieves scheduling constraints and availability patterns
- FR58: Calendar Tool returns aggregated schedule and time context

**Location/Places Tool**

- FR59: Location Tool retrieves favorite locations and frequent places
- FR60: Location Tool retrieves recent location-based episodic memories
- FR61: Location Tool retrieves travel preferences and dream destinations from profile
- FR62: Location Tool retrieves location history and movement patterns
- FR63: Location Tool returns aggregated location and place context

### MCP Platform Infrastructure (FR64-FR71)

**MCP Tool Discovery & Metadata**

- FR64: MCP tools expose capability descriptions (what data they return)
- FR65: MCP tools follow Model Context Protocol standard format
- FR66: MCP tools support version negotiation (clients specify tool version needed)
- FR67: Developers can query available MCP tools via discovery endpoint (`GET /mcp/discovery`)
- FR68: Each MCP tool returns schema definition (fields, data types, constraints)

**Performance & Caching**

- FR69: System caches MCP tool responses in Redis (5 min TTL for fresh data)
- FR70: MCP tool responses complete within 100ms for pre-aggregated queries
- FR71: System logs all MCP tool requests for analytics and debugging

### Companion AI Integration (FR72-FR81)

**Profile-Augmented Conversations**

- FR72: Companion always loads user profile at conversation start (deterministic baseline)
- FR73: Companion uses profile data to personalize communication style (formal/casual, verbose/concise)
- FR74: Companion references profile context without re-asking known information
- FR75: Companion surfaces relevant profile data during conversations (goals, preferences, relationships)
- FR76: Companion updates profile confidence scores based on conversation validation

**Memory Retrieval Enhancement**

- FR77: Existing `/v1/retrieve` endpoint can filter memories by profile attributes
- FR78: Hybrid retrieval prioritizes memories aligned with user profile (values, goals, interests)
- FR79: Narrative construction uses profile baseline to enrich story coherence
- FR80: Persona-aware retrieval considers profile data when selecting/weighting memories
- FR81: Memory search results include profile context summary alongside memories

### System Administration (FR82-FR86)

**Profile Data Management**

- FR82: Administrators can view profile completeness statistics across all users via API
- FR83: Administrators can monitor profile extraction accuracy (approved vs. rejected updates) via API
- FR84: System tracks profile confidence score distributions for calibration
- FR85: Administrators can configure profile extraction sensitivity (confidence thresholds) via API
- FR86: System provides analytics API on profile gap patterns (which fields most often missing)

---

## Non-Functional Requirements

### Performance

**Profile System:**
- Profile reads must complete in <10ms (cached in Redis, no complex queries)
- Profile updates must persist within 100ms
- Profile confidence calculations must complete within 50ms
- Profile gap detection must complete within 20ms (pre-calculated completeness scores)

**MCP Tools:**
- MCP tool responses must complete within 100ms for simple queries
- MCP tool responses must complete within 500ms for complex aggregations
- MCP tool cache hit rate >80% for frequently accessed profiles
- System must handle 1000 concurrent MCP tool requests without degradation

**Scalability:**
- Profile system must support 100,000 active user profiles
- MCP tools must support 10,000 API calls per minute at peak
- Profile extraction must scale with conversation volume (no backlog)

### Reliability

**Availability:**
- MCP tool endpoints must maintain 99.5% uptime
- Profile system must maintain 99.9% uptime (critical for all interactions)
- Graceful degradation if profile unavailable (use existing memory retrieval only)
- Zero downtime deployments for MCP tool updates

**Data Integrity:**
- Profile updates must be atomic (no partial updates)
- Profile-memory consistency enforced (no contradictory data)
- Confidence scores recalculated automatically when evidence changes
- Profile backups taken every 6 hours (point-in-time recovery)

### Maintainability

**Code Quality:**
- MCP tools follow consistent design patterns (easy to add new tools)
- Profile schema versioning for backward-compatible migrations
- Comprehensive unit tests (>80% coverage for profile and MCP code)
- Integration tests for all 4 core MCP tools

**Observability:**
- Structured logging for all profile operations (who, what, when, confidence)
- MCP tool latency metrics tracked
- Profile extraction accuracy tracked (approved/rejected ratio)
- Alerts for anomalies (sudden confidence drops, extraction failures)

### Integration

**API Compatibility:**
- Existing REST API endpoints remain unchanged (zero breaking changes)
- MCP tools use separate namespace (`/v1/mcp/`) to avoid conflicts
- Profile API follows RESTful conventions (GET, PUT, POST, DELETE)
- Error responses consistent with existing API format

---

## Implementation Planning

### Development Phases

**Phase 1: Profile Foundation (3-4 weeks)**
- Database schema and migrations
- Profile extraction LLM pipeline
- Confidence scoring engine
- Profile CRUD APIs
- Completeness tracking
- Import/Export APIs

**Phase 2: MCP Infrastructure (2-3 weeks)**
- MCP protocol implementation
- Tool registry and discovery
- Response caching layer
- Request logging
- Error handling

**Phase 3: Core MCP Tools (3-4 weeks)**
- Financial Tool implementation
- Skills Tool implementation
- Social Tool implementation
- Content Tool implementation
- Integration testing

**Phase 4: Companion Integration (2 weeks)**
- Profile-aware conversation initialization
- Gap detection logic
- Confidence update triggers
- Profile-filtered retrieval

**Total MVP Timeline: 10-13 weeks**

### Technical Dependencies

**External:**
- PostgreSQL (existing)
- Redis (existing)
- ChromaDB (existing)
- TimescaleDB (existing)
- Neo4j (existing)
- OpenAI GPT-4 or xAI Grok (existing)

**Internal:**
- Existing LangGraph extraction pipeline
- Existing retrieval orchestrator
- Existing database clients (psycopg, neo4j driver, redis-py)

### Risk Mitigation

**Technical Risks:**
- **Profile extraction accuracy low:** Start with high confidence threshold (>85%), tune based on rejection rates
- **MCP tool latency high:** Aggressive caching (Redis), pre-compute aggregations, optimize queries
- **Profile-memory conflicts:** Validation layer checks for contradictions, human review for conflicts

**Operational Risks:**
- **Backward compatibility breaks:** Comprehensive integration tests for existing API, feature flags for gradual rollout
- **Data migration issues:** Migrate existing identity_memories to profiles in background, dual-write period

---

## Post-MVP Roadmap

### Authentication & Authorization (Phase 5)
- Developer API key registration and management
- OAuth2 user authorization flow
- Rate limiting per API key
- Scope-based permissions (tool-level granularity)
- Audit logging for third-party access

### UI Components (Phase 6)
- Profile dashboard with confidence visualization
- Onboarding wizard for baseline profile setup
- Update proposals review interface
- Developer portal for API key management
- Interactive API documentation (Swagger UI)

### Growth MCP Tools (Phase 7)
- Health/Fitness Tool (sleep, exercise, wellness)
- Calendar/Schedule Tool (routines, events, time preferences)
- Location/Places Tool (favorite places, travel)

### Developer Experience (Phase 8)
- Python SDK for MCP tools
- JavaScript/TypeScript SDK for MCP tools
- Code examples repository (GitHub)
- Webhooks for profile/memory changes
- Developer debugging tools

---

## Appendices

### Glossary

**Deterministic Profile:** Stable user identity data (name, values, goals) distinct from dynamic conversational memories

**Confidence Score:** 0-100% measure of profile field reliability based on evidence strength

**MCP (Model Context Protocol):** Emerging standard for tool-based context access in AI applications

**Smart Aggregation:** MCP tool pattern combining profile + domain memories + episodic context

**Profile Completeness:** Percentage of profile fields populated across all categories

**Gap Detection:** Proactive identification of missing high-value profile fields

**Hybrid Architecture:** System combining deterministic (profiles) and dynamic (memories) layers

### API Endpoint Summary

**Profile APIs:**
- `GET /v1/profile` - Retrieve full profile
- `GET /v1/profile/{category}` - Retrieve category (core-identity, personality, etc.)
- `PUT /v1/profile/{category}/{field}` - Update field
- `DELETE /v1/profile` - Delete profile
- `GET /v1/profile/completeness` - Get completeness scores
- `POST /v1/profile/import` - Import profile data
- `GET /v1/profile/export` - Export profile data
- `GET /v1/profile/proposals` - Get pending update proposals
- `POST /v1/profile/proposals/{id}/approve` - Approve proposal
- `POST /v1/profile/proposals/{id}/reject` - Reject proposal
- `GET /v1/profile/audit` - Get audit log

**MCP Tool APIs:**
- `GET /mcp/discovery` - List available tools
- `POST /mcp/tools/financial` - Financial context
- `POST /mcp/tools/skills` - Skills and learning context
- `POST /mcp/tools/social` - Social and relationships context
- `POST /mcp/tools/content` - Content consumption context

**Admin APIs:**
- `GET /admin/profile/stats` - Profile system statistics
- `GET /admin/profile/config` - Get extraction config
- `PUT /admin/profile/config` - Update extraction config
- `GET /admin/mcp/analytics` - MCP tool usage analytics

### Database Schema Overview

**user_profiles:**
- Core Identity: name, age, gender, pronouns, location, timezone, occupation, education, birth_date
- Personality: values (JSONB), beliefs (JSONB), communication_style, personality_traits (JSONB), emotional_patterns (JSONB)
- Goals: short_term_goals (JSONB), long_term_goals (JSONB), current_challenges (JSONB), aspirations (JSONB)
- Interests: hobbies (JSONB), content_preferences (JSONB), learning_interests (JSONB), favorites (JSONB)
- Relationships: important_people (JSONB), social_preferences (JSONB), relationship_dynamics (JSONB)
- Metadata: user_id, completeness_score, created_at, updated_at
- Confidence scores: {field}_confidence for each field

**profile_extraction_candidates:**
- candidate_id, user_id, conversation_id, turn_id, category, field_name, extracted_value, confidence_score, status, extraction_timestamp

**profile_update_proposals:**
- proposal_id, user_id, field_name, current_value, proposed_value, confidence_score, supporting_evidence (JSONB), status, created_at

**profile_field_audit:**
- audit_id, user_id, field_name, old_value, new_value, confidence_before, confidence_after, change_source, timestamp

**mcp_tool_registry:**
- tool_id, tool_name, version, description, capabilities (JSONB), schema_definition (JSONB), status

**mcp_request_logs:**
- log_id, user_id, tool_name, params (JSONB), response_status, response_time_ms, cache_hit, timestamp

---

**Document Version History:**
- v1.0 (2025-11-15): Initial PRD with full UI and Auth scope
- v2.0 (2025-11-16): API-First revision, removed UI and Auth for MVP focus

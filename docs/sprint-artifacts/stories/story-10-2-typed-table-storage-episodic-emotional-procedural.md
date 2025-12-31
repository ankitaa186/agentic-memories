# Story 10.2: Typed Table Storage (Episodic, Emotional, Procedural)

**Epic:** 10 - Direct Memory API
**Story ID:** 10-2
**Status:** Review
**Dependencies:** Story 10.1 (Direct Store ChromaDB)
**Blocked By:** 10-1-direct-memory-store-endpoint-chromadb

---

## Goal

Add conditional routing to typed TimescaleDB tables based on optional fields. When a direct memory request includes type-specific fields (event_timestamp, emotional_state, or skill_name), the system should automatically route the memory to the appropriate typed table in addition to ChromaDB storage.

---

## Acceptance Criteria

### AC #1: Schema Extension

**Given** the DirectMemoryRequest schema exists from Story 10.1
**When** a user wants to store typed memories (episodic, emotional, or procedural)
**Then** the schema should support the following optional fields:

**Episodic Fields:**
- [x] `event_timestamp: Optional[datetime]` - When the event occurred (triggers episodic storage)
- [x] `location: Optional[str]` - Where the event occurred
- [x] `participants: Optional[List[str]]` - People involved in the event
- [x] `event_type: Optional[str]` - Category of event

**Emotional Fields:**
- [x] `emotional_state: Optional[str]` - Emotional state (triggers emotional storage)
- [x] `valence: Optional[float]` - Emotional valence (-1.0 negative to 1.0 positive), with `ge=-1.0, le=1.0`
- [x] `arousal: Optional[float]` - Emotional arousal (0.0 calm to 1.0 excited), with `ge=0.0, le=1.0`
- [x] `trigger_event: Optional[str]` - What triggered the emotional state

**Procedural Fields:**
- [x] `skill_name: Optional[str]` - Skill name (triggers procedural storage)
- [x] `proficiency_level: Optional[str]` - Skill level: beginner, intermediate, advanced, expert

---

### AC #2: Storage Routing

**Given** a direct memory request is received with optional typed fields
**When** the memory is being stored
**Then** routing should occur as follows:

- [x] If `event_timestamp` is provided, store in `episodic_memories` table (TimescaleDB)
- [x] If `emotional_state` is provided, store in `emotional_memories` table (TimescaleDB)
- [x] If `skill_name` is provided, store in `procedural_memories` table (PostgreSQL)
- [x] Multiple typed fields can be provided simultaneously (e.g., both episodic and emotional)
- [x] ChromaDB storage always occurs regardless of typed fields (per Story 10.1)

**Storage Helper Functions:**
- [x] `_store_episodic(memory_id, body)` - Insert into episodic_memories table
- [x] `_store_emotional(memory_id, body)` - Insert into emotional_memories table
- [x] `_store_procedural(memory_id, body)` - Insert into procedural_memories table with UPSERT logic

---

### AC #3: Metadata Tracking

**Given** a memory is stored in typed tables
**When** the storage operation completes
**Then** metadata flags should be stored in ChromaDB:

- [x] `stored_in_episodic: bool` - True if stored in episodic_memories table
- [x] `stored_in_emotional: bool` - True if stored in emotional_memories table
- [x] `stored_in_procedural: bool` - True if stored in procedural_memories table
- [x] `source: "direct_api"` - Indicates memory came from direct API (from Story 10.1)

**Purpose:** These flags enable efficient cross-storage deletion in Story 10.3 by allowing the delete endpoint to know which typed tables need cleanup.

---

### AC #4: Response

**Given** a direct memory storage request is processed
**When** the response is returned
**Then** the response should include storage status per backend:

- [x] `storage` field contains status for each backend attempted
- [x] ChromaDB success is **required** for overall success (source of truth)
- [x] Typed table storage is **best-effort** - failures are logged but don't fail the request
- [x] Response example for episodic memory:
  ```json
  {
    "status": "success",
    "memory_id": "mem_f7g8h9i0j1k2",
    "message": "Memory stored successfully",
    "storage": {
      "chromadb": true,
      "episodic": true
    }
  }
  ```
- [x] Response example for failed typed storage (ChromaDB succeeded):
  ```json
  {
    "status": "success",
    "memory_id": "mem_f7g8h9i0j1k2",
    "message": "Memory stored successfully",
    "storage": {
      "chromadb": true,
      "episodic": false
    }
  }
  ```

---

## Technical Notes

### Implementation Details

1. **Routing Logic Determination:**
   ```python
   store_episodic = body.event_timestamp is not None
   store_emotional = body.emotional_state is not None
   store_procedural = body.skill_name is not None
   ```

2. **Helper Function: `_store_episodic()`**
   - Insert into `episodic_memories` table
   - Fields: id, user_id, event_timestamp, event_type, content, location, participants, importance_score, tags, metadata
   - Use `get_timescale_conn()` and `release_timescale_conn()` pattern

3. **Helper Function: `_store_emotional()`**
   - Insert into `emotional_memories` table
   - Fields: id, user_id, timestamp, emotional_state, valence, arousal, context, trigger_event, metadata
   - Default valence to 0.0 if not provided
   - Default arousal to 0.5 if not provided

4. **Helper Function: `_store_procedural()`**
   - Insert/Update into `procedural_memories` table
   - Fields: id, user_id, skill_name, proficiency_level, context, metadata
   - Use `ON CONFLICT (id) DO UPDATE` for upsert behavior
   - Default proficiency_level to "beginner" if not provided

5. **Error Handling:**
   - Typed table failures should be caught, logged, and tracked in `storage_results`
   - ChromaDB must succeed for overall success
   - Use try/except blocks around each typed table insert

6. **Connection Management:**
   - Always use `try/finally` to ensure `release_timescale_conn()` is called
   - Each helper function manages its own connection lifecycle

### Database Schema References

**episodic_memories table:**
```sql
CREATE TABLE episodic_memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type TEXT,
    content TEXT,
    location TEXT,
    participants TEXT[],
    importance_score FLOAT,
    tags TEXT[],
    metadata JSONB
);
```

**emotional_memories table:**
```sql
CREATE TABLE emotional_memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    emotional_state TEXT NOT NULL,
    valence FLOAT,
    arousal FLOAT,
    context TEXT,
    trigger_event TEXT,
    metadata JSONB
);
```

**procedural_memories table:**
```sql
CREATE TABLE procedural_memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    proficiency_level TEXT,
    context TEXT,
    metadata JSONB
);
```

### Files to Modify

1. **`src/schemas.py`** - Add optional typed fields to DirectMemoryRequest (if not already done in 10.4)
2. **`src/routers/memories.py`** - Add routing logic and helper functions

---

## Tasks

- [x] Add optional episodic fields to DirectMemoryRequest schema (event_timestamp, location, participants, event_type)
- [x] Add optional emotional fields to DirectMemoryRequest schema (emotional_state, valence, arousal, trigger_event)
- [x] Add optional procedural fields to DirectMemoryRequest schema (skill_name, proficiency_level)
- [x] Implement `_store_episodic()` helper function with proper connection management
- [x] Implement `_store_emotional()` helper function with proper connection management
- [x] Implement `_store_procedural()` helper function with UPSERT logic
- [x] Add routing logic to determine which typed tables to store in
- [x] Add metadata flags (stored_in_episodic, stored_in_emotional, stored_in_procedural) to ChromaDB metadata
- [x] Update response to include storage status per backend
- [x] Add error handling for typed table storage failures (log and continue)
- [x] Write unit tests for each helper function
- [x] Write unit tests for routing logic
- [ ] Write integration tests for typed memory storage
- [ ] Verify memories stored in typed tables are retrievable via hybrid retrieval

---

## Definition of Done

- [x] All acceptance criteria met
- [x] Typed tables receive correct data based on optional field presence
- [x] Metadata flags (stored_in_episodic, stored_in_emotional, stored_in_procedural) stored in ChromaDB
- [x] Response includes storage status per backend
- [x] Typed table failures logged but don't fail overall request (ChromaDB required only)
- [x] No linting errors
- [x] Unit tests pass with >80% coverage for typed storage code
- [ ] Integration tests verify typed memories are retrievable via hybrid retrieval
- [ ] PR ready for review

---

## Example Requests/Responses

### Episodic Memory Example

**Request:**
```json
POST /v1/memories/direct
{
  "user_id": "0000000000",
  "content": "User attended daughter's graduation ceremony at Stanford",
  "layer": "long-term",
  "type": "explicit",
  "importance": 0.9,
  "event_timestamp": "2025-06-15T14:00:00Z",
  "location": "Stanford University, CA",
  "participants": ["daughter Sarah", "wife Maria"],
  "event_type": "family_milestone"
}
```

**Response:**
```json
{
  "status": "success",
  "memory_id": "mem_f7g8h9i0j1k2",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "episodic": true
  }
}
```

### Emotional Memory Example

**Request:**
```json
POST /v1/memories/direct
{
  "user_id": "0000000000",
  "content": "User expressed frustration about job search taking too long",
  "layer": "semantic",
  "type": "explicit",
  "emotional_state": "frustrated",
  "valence": -0.6,
  "arousal": 0.7,
  "trigger_event": "Another job rejection email"
}
```

**Response:**
```json
{
  "status": "success",
  "memory_id": "mem_l3m4n5o6p7q8",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "emotional": true
  }
}
```

### Procedural Memory Example

**Request:**
```json
POST /v1/memories/direct
{
  "user_id": "0000000000",
  "content": "User demonstrated advanced Python skills including async programming",
  "layer": "semantic",
  "type": "explicit",
  "skill_name": "python_programming",
  "proficiency_level": "advanced"
}
```

**Response:**
```json
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "procedural": true
  }
}
```

---

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/stories/10-2-typed-table-storage-episodic-emotional-procedural.context.xml`

### Debug Log

**2025-12-29:** Implementation Plan
- Analyzed existing patterns in episodic_memory.py, emotional_memory.py, procedural_memory.py
- Schema fields already complete from Story 10.4 (DirectMemoryRequest in src/schemas.py)
- Need to implement helper functions and routing logic in src/routers/memories.py
- Pattern: get_timescale_conn() / release_timescale_conn() with try/finally

### Completion Notes

**Implementation completed 2025-12-29**

1. **Helper Functions Added to `src/routers/memories.py`:**
   - `_store_episodic(memory_id, body)` - Inserts to episodic_memories table with proper connection management
   - `_store_emotional(memory_id, body)` - Inserts to emotional_memories table with default valence=0.0, arousal=0.5
   - `_store_procedural(memory_id, body)` - Inserts to procedural_memories table with UPSERT logic, default proficiency_level="beginner"

2. **Routing Logic:**
   - `store_episodic = body.event_timestamp is not None`
   - `store_emotional = body.emotional_state is not None`
   - `store_procedural = body.skill_name is not None`
   - Multiple types can be stored simultaneously

3. **Metadata Flags in ChromaDB:**
   - `stored_in_episodic`, `stored_in_emotional`, `stored_in_procedural` flags accurately track storage results
   - `source: "direct_api"` maintained from Story 10.1

4. **Response Format:**
   - `storage` dict only includes keys for backends that were attempted
   - ChromaDB is always `true` on success (required for overall success)
   - Typed tables show actual result (true/false based on success)

5. **Error Handling:**
   - Typed table failures are logged at WARNING level but don't fail the request
   - Connection rollback on errors, proper release in finally blocks
   - ChromaDB failures still result in overall request failure

6. **Unit Tests:**
   - 33 tests added in `tests/unit/test_memories_router.py`
   - Tests cover helper functions, routing logic, schema validation, error handling
   - All 388 unit tests pass (no regressions)

### File List

**New Files:**
- `tests/unit/test_memories_router.py` - 33 unit tests for memories router

**Modified Files:**
- `src/routers/memories.py` - Added helper functions and routing logic for typed table storage

---

## Estimated Effort

**4 hours** (as per Epic 10 breakdown)

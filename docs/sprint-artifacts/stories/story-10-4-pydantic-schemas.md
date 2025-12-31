# Story 10.4: Pydantic Schemas

**Epic:** 10 - Direct Memory API
**Story ID:** 10-4
**Status:** review
**Dependencies:** None (first story in implementation order)
**Blocked By:** None

---

## Goal

Add request/response schemas to `src/schemas.py` for direct memory operations.

## Acceptance Criteria

### AC #1: DirectMemoryRequest Schema

**Given** a developer needs to validate incoming direct memory storage requests
**When** they import `DirectMemoryRequest` from `src/schemas.py`
**Then** the schema should include:

- [x] **Required fields:** `user_id: str`, `content: str` (max_length=5000)
- [x] **General fields:** layer, type, importance (0.0-1.0), confidence (0.0-1.0), persona_tags (max 10), metadata
- [x] **Optional episodic fields:** event_timestamp, location, participants, event_type
- [x] **Optional emotional fields:** emotional_state, valence (-1.0 to 1.0), arousal (0.0 to 1.0), trigger_event
- [x] **Optional procedural fields:** skill_name, proficiency_level
- [x] All fields have clear `Field(description=...)` for OpenAPI generation

### AC #2: DirectMemoryResponse Schema

**Given** a direct memory storage operation completes
**When** the endpoint returns a response
**Then** the `DirectMemoryResponse` schema should include:

- [x] `status: Literal["success", "error"]`
- [x] `memory_id: Optional[str]` - UUID of stored memory
- [x] `message: str` - Status message
- [x] `storage: Optional[Dict[str, bool]]` - Status per backend
- [x] `error_code: Optional[Literal["VALIDATION_ERROR", "EMBEDDING_ERROR", "STORAGE_ERROR", "INTERNAL_ERROR"]]`

### AC #3: DeleteMemoryResponse Schema

**Given** a memory deletion operation completes
**When** the endpoint returns a response
**Then** the `DeleteMemoryResponse` schema should include:

- [x] `status: Literal["success", "error"]`
- [x] `deleted: bool` - True if memory was deleted
- [x] `memory_id: str` - Requested memory ID
- [x] `storage: Optional[Dict[str, bool]]` - Deletion status per backend
- [x] `message: Optional[str]` - Status or error message

### AC #4: Documentation

**Given** the schemas are added to `src/schemas.py`
**When** FastAPI generates OpenAPI documentation
**Then**:

- [x] All schemas appear in `/docs`
- [x] Field descriptions are visible
- [x] Validators (ge, le, max_length) are reflected

## Technical Notes

### File Location
- **Target file:** `src/schemas.py`
- Add schemas after existing `IntentExecutionResponse` class

### Code Pattern
```python
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class DirectMemoryRequest(BaseModel):
    """Request body for direct memory storage."""
    user_id: str = Field(..., description="User identifier")
    content: str = Field(..., max_length=5000, description="Memory content")
    # ... additional fields
```

## Tasks

- [x] Review existing `src/schemas.py` patterns
- [x] Add `DirectMemoryRequest` with all required and optional fields
- [x] Add `DirectMemoryResponse` with status, memory_id, storage, error_code
- [x] Add `DeleteMemoryResponse` with status, deleted, memory_id, storage, message
- [x] Add comprehensive Field() descriptions for OpenAPI
- [x] Verify no linting errors with `ruff check src/schemas.py`
- [x] Verify OpenAPI generation at `/docs`

## Definition of Done

- [x] All acceptance criteria met
- [x] Code follows existing patterns in schemas.py
- [x] No linting errors
- [x] All three schemas added and validated
- [x] OpenAPI documentation generates properly
- [x] PR ready for review

## Estimated Effort

1.5 hours

---

## Dev Agent Record

### Context Reference
- `docs/sprint-artifacts/stories/10-4-pydantic-schemas.context.xml`

### Debug Log
**Implementation Plan (2025-12-29):**
1. Reviewed existing `src/schemas.py` patterns - identified use of Field() with description, ge/le validators, Literal types
2. Added schemas after IntentExecutionResponse class (line 510)
3. Implemented DirectMemoryRequest with all required and optional fields grouped by type
4. Implemented DirectMemoryResponse and DeleteMemoryResponse with all specified fields
5. Verified Python syntax with py_compile
6. Ran schema validation tests to confirm Field validators work correctly
7. Verified OpenAPI schema generation produces descriptions for all fields

### Completion Notes
All three Pydantic schemas (DirectMemoryRequest, DirectMemoryResponse, DeleteMemoryResponse) have been added to `src/schemas.py`. Implementation follows existing patterns in the codebase with:
- Field() validators for numeric ranges (ge=, le=)
- Literal types for enumerated values
- Comprehensive descriptions for OpenAPI documentation
- Optional fields with default=None
- Default values matching existing Memory model patterns

Unit tests pass. Schema validation confirmed for all field constraints.

### File List
**Modified:**
- `src/schemas.py` - Added DirectMemoryRequest, DirectMemoryResponse, DeleteMemoryResponse schemas (lines 510-674)

### Change Log
- 2025-12-29: Added Epic 10 Direct Memory API schemas (Story 10.4)

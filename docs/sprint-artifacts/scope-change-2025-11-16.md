# Scope Change Decision Record

**Date:** 2025-11-16 (Updated)
**Project:** Agentic Memories v3.0 - User Profiles API
**Decision Makers:** Ankit (Product Owner), BMad Team (PM, Architect, SM, Dev)

---

## Decision

**Stories 1.3 (Profile Confidence Scoring Engine) and 1.4 (Profile Update Proposal & Approval API) have been moved from MVP scope to Future Enhancements.**

---

## Context

During sprint planning review, the team discovered a discrepancy between the original story specification and the actual implementation:

### Original Story 1.4 Specification
- High-confidence extractions (>80%) create proposals in `profile_update_proposals` table
- User can approve/reject proposed profile updates via API endpoints
- Provides proactive user control over automatically extracted profile data

### Actual Story 1.2 Implementation
- Profile extraction writes **directly** to `profile_fields` table
- All extractions are committed immediately with confidence scores tracked
- No `profile_extraction_candidates` or `profile_update_proposals` tables exist
- Direct-write approach already tested and deployed

---

## Analysis

**Team Discussion Points:**

**John (PM):** "Without approval, we're writing potentially incorrect assumptions directly into the deterministic profile. The approval workflow is proactive - it surfaces high-confidence extractions and asks 'Is this right?'"

**Winston (Architect):** "Story 1.4 as written assumes infrastructure that doesn't exist. The current implementation auto-commits all extractions directly to the profile. Are we comfortable writing unvalidated LLM extractions to the source of truth?"

**Bob (SM):** "Story 1.5's manual editing becomes the ONLY path to profile corrections if we skip 1.4. Is that the MVP experience we want?"

**Amelia (Dev):** "Story 1.2's implementation is solid and tested. Profile extraction writes directly, confidence scores are tracked, and everything's in production."

**Ankit (Decision):** "Let's go with simpler direct-write approach, and keep the approval as future enhancement."

---

## Rationale

1. **Speed to MVP:** Direct-write approach is already implemented and working
2. **Safety Net Exists:** Story 1.5 (CRUD APIs) provides manual correction capability
3. **Confidence Tracking:** Low-confidence fields are visible in the database for future smart prompts
4. **Reduced Complexity:** Eliminates need for additional tables and approval workflow logic
5. **User Trust Bet:** Accepting that users will either trust extractions or use manual editing

---

## Impact Assessment

### Scope Changes
- **MVP Stories:** 9 → 8 stories
- **Epic 1:** Now 7 stories (down from 8)
- **Total MVP:** 8 stories (Epic 1: 7 stories, Epic 2: 1 story)

### Deferred Features (FR9-FR11)
- FR9: System proposes profile updates when high-confidence new information detected
- FR10: Users can approve or reject proposed profile updates via API
- FR11: System accumulates low-confidence profile candidates until evidence strengthens

### Current Behavior
- All profile extractions write directly to `profile_fields` with confidence scores
- Confidence scoring (Story 1.3) will calculate and update scores for existing fields
- Users can manually review and edit via CRUD APIs (Story 1.5)
- Profile completeness tracking (Story 1.6) will identify low-confidence fields

### Future Enhancement Path
When Story 1.4 is revisited post-MVP, it would require:
- New tables: `profile_extraction_candidates`, `profile_update_proposals`
- New service layer for proposal management
- New API endpoints: `GET /v1/profile/proposals`, `POST /v1/profile/proposals/{id}/approve`
- Migration strategy for existing direct-write data

---

## Story 1.3 Deferral (Added Later Same Day)

### Context
After deferring Story 1.4, the team questioned whether Story 1.3 (confidence aggregation) was still needed with the direct-write model.

### Analysis
**Winston (Architect):** "Story 1.3's original purpose was to aggregate confidence from multiple extractions to determine when to create proposals (Story 1.4). Without proposals, the value proposition changes."

**Amelia (Dev):** "Current implementation (Story 1.2) already does simple replacement - latest extraction wins. Profile_sources table maintains audit trail. Story 1.3 would add aggregation complexity on top."

**Ankit's Question:** "Why keep duplicates? Shouldn't we just replace low confidence with higher confidence more recent value?"

**John (PM):** "Exactly. If we trust the LLM extraction confidence, we don't need manual aggregation. Simple replacement works for MVP."

### Decision Rationale
1. **Trust LLM Confidence:** Each extraction has confidence score from LLM
2. **Simple Replacement:** Latest/highest confidence extraction wins (already implemented)
3. **Audit Trail Preserved:** profile_sources table tracks all extractions for future analysis
4. **YAGNI Principle:** Don't build aggregation logic until we prove it's needed
5. **Faster MVP:** Removes implementation complexity

### Impact
- Story 1.3 moved to future enhancements along with Story 1.4
- Both are coupled to approval workflow concept
- Can revisit if real usage shows need for confidence aggregation

---

## Timeline Impact

**Positive:** Removes two stories from Epic 1, significantly accelerating MVP completion

**Before:** 9 MVP stories (2 done, 7 remaining)
**After Story 1.4 defer:** 8 MVP stories (2 done, 6 remaining)
**After Story 1.3 defer:** 7 MVP stories (2 done, 5 remaining)

**Epic 1:** 6 stories (down from 8)
**Epic 2:** 1 story (unchanged)

---

## Acceptance

✅ **Approved by:** Ankit (Product Owner)
✅ **Sprint Status Updated:** docs/sprint-artifacts/sprint-status.yaml
✅ **Decision Recorded:** This document
✅ **Epics Updated:** docs/epics.md

---

## Next Steps

1. ✅ Update sprint-status.yaml (completed)
2. ✅ Update epics.md to move Stories 1.3 and 1.4 to "Future Enhancements" section
3. ⏳ Continue with Story 1.5 (Profile CRUD API Endpoints)
4. 📝 Note in PRD that FR9-FR11 are deferred to post-MVP

---

**Document Owner:** BMad Master
**Last Updated:** 2025-11-16

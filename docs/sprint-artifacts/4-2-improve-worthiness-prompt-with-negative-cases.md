# Story 4.2: Improve Worthiness Prompt with Negative Cases

Status: drafted

## Story

As a **memory system**,
I want **the worthiness check to reject obvious/redundant content**,
so that **low-value content is filtered early (before LLM extraction)**.

## Acceptance Criteria

1. **AC1:** Add "NOT Worthy" section to WORTHINESS_PROMPT containing:
   - Generic desires everyone has ("wants to make money", "wants success")
   - Quantitative facts about holdings (portfolio tool tracks these)
   - Obvious implications of stated preferences
   - Restatements of previous memories
   - Meta-commentary about the conversation itself

2. **AC2:** Add "Ask Yourself" decision framework with 3 questions:
   - Would this help personalize responses for THIS user vs. any user?
   - Is this NOVEL information not already stored?
   - Is this INSIGHT (why) rather than STATE (what)?
   - Decision rule: If any answer is NO, mark as NOT worthy

3. **AC3:** Test negative case: "User wants to make money" → Returns `worthy: false`

4. **AC4:** Test positive case: "User prefers X because Y" → Returns `worthy: true`

5. **AC5:** Existing worthy content still passes (regression):
   - Profile info: "I'm John, 35 years old" → worthy
   - Finance with insight: "I'm bullish on AAPL because of services growth" → worthy
   - Projects: "I'm building a portfolio tracker" → worthy

## Tasks / Subtasks

- [ ] **Task 1: Add "NOT Worthy" Section** (AC: 1)
  - [ ] 1.1 Open `src/services/prompts.py`
  - [ ] 1.2 Locate `WORTHINESS_PROMPT` variable (lines 1-23)
  - [ ] 1.3 Add "## NOT Worthy (Even if it seems like a preference)" section
  - [ ] 1.4 Add bullet: Generic desires everyone has (with examples)
  - [ ] 1.5 Add bullet: Quantitative facts about holdings
  - [ ] 1.6 Add bullet: Obvious implications of stated preferences
  - [ ] 1.7 Add bullet: Restatements of previous memories
  - [ ] 1.8 Add bullet: Meta-commentary about conversation

- [ ] **Task 2: Add "Ask Yourself" Decision Framework** (AC: 2)
  - [ ] 2.1 Add "## Ask Yourself" section after NOT Worthy section
  - [ ] 2.2 Add question 1: "Would this help personalize for THIS user vs. any user?"
  - [ ] 2.3 Add question 2: "Is this NOVEL information not already stored?"
  - [ ] 2.4 Add question 3: "Is this INSIGHT (why) rather than STATE (what)?"
  - [ ] 2.5 Add decision rule: "If any answer is NO, mark as NOT worthy"

- [ ] **Task 3: Test Negative Cases** (AC: 3)
  - [ ] 3.1 Create test function for worthiness check
  - [ ] 3.2 Test input: "I want to make money investing" → verify `worthy: false`
  - [ ] 3.3 Test input: "I have a portfolio" → verify `worthy: false`
  - [ ] 3.4 Test input: "Tell me about the stock market" → verify `worthy: false`
  - [ ] 3.5 Document rejection reasons in test output

- [ ] **Task 4: Test Positive Cases** (AC: 4, 5)
  - [ ] 4.1 Test input: "I prefer value investing because it's lower risk" → verify `worthy: true`
  - [ ] 4.2 Test input: "I'm John, a 35-year-old engineer in NYC" → verify `worthy: true`
  - [ ] 4.3 Test input: "I'm bullish on AAPL due to services revenue growth" → verify `worthy: true`
  - [ ] 4.4 Test input: "I'm building a portfolio tracking app" → verify `worthy: true`
  - [ ] 4.5 Verify confidence scores are appropriate (>0.7 for explicit statements)

- [ ] **Task 5: Integration Test** (AC: 3, 4, 5)
  - [ ] 5.1 Run full extraction pipeline with mixed worthy/unworthy content
  - [ ] 5.2 Verify worthiness check filters before extraction LLM call
  - [ ] 5.3 Check logs show proper rejection reasons
  - [ ] 5.4 Verify no false negatives (valid content incorrectly rejected)

## Dev Notes

### Implementation Details

**File to modify:** `src/services/prompts.py`

**Current WORTHINESS_PROMPT structure (lines 1-23):**
```python
WORTHINESS_PROMPT = """
You extract whether a user's recent message is memory-worthy...
{schema}
Guidelines (recall-first):
- Worthy if: ...
- Not worthy alone: greetings, meta-chatter, filler
Edge cases: ...
FINANCE PRIORITY RULES: ...
""".strip()
```

**Proposed additions (insert before .strip()):**
```python
## NOT Worthy (Even if it seems like a preference)

- Generic desires everyone has ("wants to make money", "wants success")
- Quantitative facts about holdings (portfolio tool tracks these)
- Obvious implications of stated preferences
- Restatements of previous memories
- Meta-commentary about the conversation itself

## Ask Yourself

Before marking as worthy:
1. Would this help personalize responses for THIS user vs. any user?
2. Is this NOVEL information not already stored?
3. Is this INSIGHT (why) rather than STATE (what)?

If any answer is NO, mark as NOT worthy.
```

### Relationship to Story 4.1

- Story 4.1 adds anti-patterns to EXTRACTION_PROMPT (filters DURING extraction)
- Story 4.2 adds negative cases to WORTHINESS_PROMPT (filters BEFORE extraction)
- These are complementary: worthiness is the first gate, extraction is the second
- Both should align on what constitutes "truism" and "state data"

### Testing Strategy

Test using the worthiness check directly:
```bash
docker exec agentic-memories-api-1 python3 -c "
from src.services.llm_utils import call_llm
from src.services.prompts import WORTHINESS_PROMPT

# Test worthiness check
result = call_llm(WORTHINESS_PROMPT, 'I want to make money investing')
print(result)  # Should have worthy: false
"
```

### Project Structure Notes

- **File location:** `src/services/prompts.py` (existing file, line 1-23)
- **Related files:**
  - `src/services/graph_extraction.py` - calls worthiness check
  - `src/services/unified_ingestion_graph.py` - orchestrates worthiness node
- **No new files needed** - this is a prompt-only change

### Learnings from Previous Story

**From Story 4.1 (Status: drafted)**

Story 4.1 focuses on EXTRACTION_PROMPT anti-patterns. This story (4.2) focuses on WORTHINESS_PROMPT.
The two prompts should have consistent definitions of:
- Truisms
- State data
- Meta-chatter

Ensure alignment in terminology and examples.

[Source: docs/sprint-artifacts/4-1-add-negative-examples-to-extraction-prompt.md]

### References

- [Source: docs/epic-extraction-quality.md#Story-4.2]
- [Source: docs/epic-extraction-quality.md#Change-4]
- [Source: src/services/prompts.py#WORTHINESS_PROMPT]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-12-20 | BMad Master | Story drafted from Epic 4 requirements |

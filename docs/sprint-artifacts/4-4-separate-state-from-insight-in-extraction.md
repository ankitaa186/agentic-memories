# Story 4.4: Separate State from Insight in Extraction

Status: done

## Story

As a **memory system**,
I want **to distinguish between quantitative state and qualitative insight**,
so that **state data goes to structured tools, insights go to memories**.

## Acceptance Criteria

1. **AC1:** Add State vs. Insight classification guidance to EXTRACTION_PROMPT
   - Define STATE: quantitative, changes frequently, tracked by tools
   - Define INSIGHT: qualitative, stable, explains reasoning
   - Include decision rules for each type

2. **AC2:** Holdings quantities route to portfolio object ONLY, not memory content
   - "User owns 100 shares of AAPL" → `portfolio: {ticker: "AAPL", quantity: 100}`
   - NOT as memory content: "User owns 100 shares of AAPL"

3. **AC3:** Investment thesis/reasoning stored as memory content
   - "User bought AAPL for dividend income" → memory content with insight
   - Include `portfolio` object for ticker reference + memory for reasoning

4. **AC4:** Test pure state input: "I bought 100 AAPL"
   - Should produce: portfolio object with quantity
   - Should NOT produce: memory content about ownership

5. **AC5:** Test insight input: "I bought AAPL for dividend income"
   - Should produce: portfolio object (ticker reference)
   - Should produce: memory content explaining the WHY

## Tasks / Subtasks

- [ ] **Task 1: Add State vs. Insight Classification to EXTRACTION_PROMPT** (AC: 1)
  - [ ] 1.1 Open `src/services/prompts.py`
  - [ ] 1.2 Add new section "## Classify: State vs. Insight" after Core Extraction Rules
  - [ ] 1.3 Define STATE category with examples:
        - Holdings quantities: "User owns X shares of Y"
        - Portfolio values: "User's position is worth $X"
        - Price targets: "User's target for X is $Y"
  - [ ] 1.4 Define INSIGHT category with examples:
        - Investment thesis: "User bought X because of Y moat"
        - Risk tolerance: "User prefers defensive positions"
        - Strategy: "User follows Buffett's value investing"
  - [ ] 1.5 Add action rules:
        - STATE → Extract to `portfolio` object ONLY, not as memory content
        - INSIGHT → Extract as memory content with high confidence

- [ ] **Task 2: Update Finance Examples** (AC: 2, 3)
  - [ ] 2.1 Locate existing finance examples in EXTRACTION_PROMPT
  - [ ] 2.2 Update Example 1 (multi-faceted input) to show state vs insight routing
  - [ ] 2.3 Add new example showing pure state → portfolio only
  - [ ] 2.4 Add new example showing insight → memory + portfolio reference

- [ ] **Task 3: Test Pure State Routing** (AC: 4)
  - [ ] 3.1 Create test input: "I bought 100 shares of AAPL at $150"
  - [ ] 3.2 Run extraction pipeline
  - [ ] 3.3 Verify output has `portfolio` object: `{ticker: "AAPL", quantity: 100, price: 150}`
  - [ ] 3.4 Verify NO memory content like "User owns 100 shares of AAPL"
  - [ ] 3.5 Document extraction decision

- [ ] **Task 4: Test Insight Routing** (AC: 5)
  - [ ] 4.1 Create test input: "I bought AAPL because I believe in their services growth"
  - [ ] 4.2 Run extraction pipeline
  - [ ] 4.3 Verify output has memory content: "User bought AAPL because of belief in services growth"
  - [ ] 4.4 Verify output has `portfolio` object for ticker reference (optional)
  - [ ] 4.5 Document that insight was captured

- [ ] **Task 5: Test Mixed Input** (AC: 2, 3, 4, 5)
  - [ ] 5.1 Create test input: "I bought 100 AAPL at $150 for dividend income"
  - [ ] 5.2 Run extraction pipeline
  - [ ] 5.3 Verify `portfolio` object has quantity and price
  - [ ] 5.4 Verify memory content has insight: "User bought AAPL for dividend income"
  - [ ] 5.5 Verify NO redundant state memory created

## Dev Notes

### Implementation Details

**File to modify:** `src/services/prompts.py`

**New section to add (after Core Extraction Rules, before Domain-Specific Rules):**

```markdown
## Classify: State vs. Insight

For every potential memory involving quantitative data, classify:

**STATE** (quantitative, changes frequently, tracked by tools):
- Holdings quantities: "User owns X shares of Y"
- Portfolio values: "User's position is worth $X"
- Price targets: "User's target for X is $Y"
- Account balances: "User has $X in savings"

→ Action: Extract to `portfolio` object ONLY, not as memory content.
   The Portfolio tool tracks this state data.

**INSIGHT** (qualitative, stable, explains reasoning):
- Investment thesis: "User bought X because of Y moat"
- Risk tolerance: "User prefers defensive positions"
- Strategy: "User follows Buffett's value investing"
- Market view: "User is bearish on tech due to rate hikes"

→ Action: Extract as memory content with high confidence.
   Include `portfolio.ticker` for reference if applicable.

**Examples:**

Input: "I bought 100 shares of AAPL at $150"
Output:
- portfolio: {ticker: "AAPL", quantity: 100, price: 150}
- content: (NONE - pure state)

Input: "I bought AAPL because I love their ecosystem"
Output:
- portfolio: {ticker: "AAPL"}
- content: "User bought AAPL because of love for Apple ecosystem."

Input: "I own 2810 shares of RKLB because I believe in Neutron's reusability"
Output:
- portfolio: {ticker: "RKLB", quantity: 2810}
- content: "User holds RKLB because of belief in Neutron rocket reusability."
```

### Relationship to Previous Stories

| Story | Contribution |
|-------|--------------|
| 4.1 | Anti-patterns include "State Data" as what NOT to extract as memory |
| 4.2 | Worthiness prompt rejects pure state without insight |
| 4.3 | Entailment prevents duplicate state memories |
| 4.4 | **Explicit routing rules for state → portfolio, insight → memory** |

Story 4.4 makes the state/insight distinction actionable with clear routing rules.

### Testing Strategy

```bash
docker exec agentic-memories-api-1 python3 -c "
from src.services.extraction import extract_from_transcript
from src.schemas import StoreRequest

# Test pure state
req = StoreRequest(
    user_id='test-user-compaction-001',
    messages=[{'role': 'user', 'content': 'I bought 100 shares of AAPL at 150'}]
)
result = extract_from_transcript(req)
print('Memories:', [m.content for m in result.get('memories', [])])
print('Portfolio:', [m.portfolio for m in result.get('memories', []) if m.portfolio])
"
```

### Project Structure Notes

- **File to modify:** `src/services/prompts.py` - EXTRACTION_PROMPT
- **Related behavior:** Portfolio extraction in `src/services/portfolio_service.py`
- **No new files needed**

### References

- [Source: docs/epic-extraction-quality.md#Story-4.4]
- [Source: docs/epic-extraction-quality.md#Change-3]
- [Source: src/services/prompts.py#Finance-Stocks]

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
| 2025-12-20 | BMad Master | Story drafted from Epic 4 requirements (YOLO mode) |
| 2025-12-21 | Dev Agent | Implementation complete - Story marked DONE |

## Completion Notes

### Changes Made (2025-12-21)

**1. Added "Classify: State vs. Insight" section to EXTRACTION_PROMPT**
- Defines STATE: quantitative data tracked by tools (holdings, values, prices)
- Defines INSIGHT: qualitative reasoning (thesis, strategy, beliefs)
- Clear routing rules: STATE → portfolio object only, INSIGHT → memory content
- Three routing examples showing correct behavior

**2. Updated Example 1 in EXTRACTION_PROMPT**
- Changed to show `content: null` for pure state (finance quantity/price)
- Added Example 1b showing insight with memory content

### Test Results

| Test | Input | Result |
|------|-------|--------|
| Pure state | "I bought 100 shares of AAPL at $150" | ✅ `content: None` + portfolio object |
| Insight | "I bought AAPL because of services growth" | ✅ Memory content with reasoning |
| Mixed | "I bought 100 AAPL at $150 for dividend income" | ✅ 2 entries: state + insight |

### Files Modified
- `src/services/prompts.py` - Added State vs. Insight classification section, updated Example 1

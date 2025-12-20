# Epic 4: Memory Extraction Quality Improvements

**Epic ID:** 4
**Author:** Claude Code (Based on user feedback analysis 2025-12-20)
**Status:** Proposed
**Priority:** P0 (Quality & Cost Reduction)
**Dependencies:** None
**Target Timeline:** 1-2 weeks

---

## Executive Summary

Improve memory extraction quality to eliminate redundant, obvious, and semantically duplicate memories. The current system extracts "everything" including truisms, state data that belongs in structured tools, and multiple variations of the same fact. This wastes context window tokens and degrades retrieval quality.

**Key Benefits:**
- **Higher signal-to-noise ratio**: Only unique, valuable insights stored
- **Reduced token waste**: Fewer redundant memories in retrieval
- **Better retrieval relevance**: Unique facts instead of 5 variations of same thing
- **Cost reduction**: Fewer memories = less storage, less embedding compute

---

## Background & Motivation

### The Problem (Real User Feedback)

User feedback identified four categories of extraction waste:

#### 1. Echo Chamber Effect
Multiple memories storing semantically identical information:
```
- "User prefers value investing in the style of Warren Buffett." (Dec 15)
- "User prefers investment analysis in the style of Warren Buffett and Charlie Munger." (Dec 16)
- "User identifies as a value investor." (Dec 15)
- "User's learning is heavily influenced by Warren Buffett." (Dec 15)
- "User prefers investing advice from Warren Buffett..." (Dec 19)
```
**Impact:** 5 retrieval slots consumed for one fact.

#### 2. Captain Obvious (Truisms)
Storing generic statements that provide no personalization value:
```
- "User has an investment portfolio."
- "User owns stocks."
- "User wants to maximize gains."
```
**Impact:** Wastes storage on facts derivable from context or universally true.

#### 3. State vs. Insight Confusion
Storing state data that belongs in structured tools:
```
BAD:  "User owns 2810 shares of Rocket Lab."  (Portfolio tool manages this)
GOOD: "User holds Rocket Lab because they believe in the neutron rocket's reusability moat."
```
**Impact:** Duplicates data already in portfolio_holdings table.

#### 4. Lack of Semantic Consolidation
No mechanism to merge related memories into a "golden record":
```
CURRENT: 5 separate Buffett memories
IDEAL:   "User is a value investor (Buffett/Munger disciple) focused on mitigating Key Man risk."
```

### Root Cause Analysis

| Problem | Root Cause | Solution Area |
|---------|------------|---------------|
| Echo Chamber | Dedup threshold too strict (0.90) | Compaction + Extraction |
| Truisms | No negative examples in prompt | Extraction Prompt |
| State/Insight | No tool-awareness in extraction | Extraction Prompt |
| No Consolidation | No merge logic in compaction | Compaction |

---

## Goals & Success Criteria

### Primary Goals

1. **Reduce semantic duplicates** by 80%+ through improved extraction
2. **Eliminate truisms** via negative examples in prompts
3. **Separate state from insight** - don't store what tools track
4. **Enable consolidation** - merge related memories into dense records

### Success Criteria

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Duplicate Rate** | ~28% (101/355) | <5% | Dedup removal rate |
| **Truism Extraction** | Common | Zero | Manual audit |
| **State Duplication** | Frequent | Zero | Portfolio vs memory overlap |
| **Memory Density** | Low | High | Unique info per memory |

### Non-Goals

- Changing memory storage schema
- Modifying retrieval logic
- Rebuilding extraction from scratch
- Real-time consolidation (batch is fine)

---

## Proposed Solution: Prompt Improvements

### Change 1: Add Negative Examples (Anti-Patterns)

Add to `EXTRACTION_PROMPT`:

```markdown
## CRITICAL: What NOT to Extract

### Anti-Pattern 1: Truisms & Obvious Statements
DO NOT extract generic statements that are universally true or obvious:

❌ "User wants to make money."
❌ "User has an investment portfolio."
❌ "User owns stocks."
❌ "User likes good ideas."
❌ "User wants to be successful."
❌ "User is interested in investing."

These provide zero personalization value. Everyone wants these things.

### Anti-Pattern 2: State Data (Belongs in Structured Tools)
DO NOT extract quantitative holdings data - the Portfolio tool tracks this:

❌ "User owns 2810 shares of Rocket Lab."
❌ "User bought 100 shares of AAPL."
❌ "User's TSLA position is worth $50,000."

✅ DO extract the WHY behind holdings:
✅ "User holds Rocket Lab because of belief in neutron rocket reusability moat."
✅ "User bought AAPL as a defensive position during market uncertainty."
✅ "User is bullish on TSLA due to FSD progress."

### Anti-Pattern 3: Semantic Echoes
Before extracting, ask: "Does an existing memory already capture this?"

Existing: "User is a value investor following Buffett's principles."
Input: "I really admire Warren Buffett's approach."
Action: ❌ SKIP (already captured)

Existing: "User is a value investor following Buffett's principles."
Input: "I also like Munger's mental models approach."
Action: ✅ EXTRACT (adds new information about Munger)

### Anti-Pattern 4: Restatements of User Actions
DO NOT extract memories that simply restate what the user just did:

❌ "User asked about AAPL stock." (meta-chatter)
❌ "User is curious about the market." (vague)
❌ "User is researching investments." (obvious from context)
```

### Change 2: Add Semantic Entailment Check

Add to extraction workflow (before storage):

```markdown
## Pre-Storage Entailment Check

Before storing a new memory, verify it adds unique information:

1. Query existing memories for semantic similarity (threshold: 0.80)
2. For each similar existing memory, ask:
   - Does the existing memory ENTAIL (logically imply) the new one?
   - Does the new memory add NOVEL information?
3. Only store if: similarity < 0.80 OR novel information detected

Example:
- Existing: "User is a Buffett-style value investor."
- New: "User likes Warren Buffett."
- Entailment: YES (existing implies new)
- Action: DISCARD new memory
```

### Change 3: Add Insight Classification

Add to `EXTRACTION_PROMPT`:

```markdown
## Classify: State vs. Insight

For every potential memory, classify:

**STATE** (quantitative, changes frequently, tracked by tools):
- Holdings quantities: "User owns X shares of Y"
- Portfolio values: "User's position is worth $X"
- Price targets: "User's target for X is $Y"
→ Action: Extract to `portfolio` object ONLY, not as memory content

**INSIGHT** (qualitative, stable, explains reasoning):
- Investment thesis: "User bought X because of Y moat"
- Risk tolerance: "User prefers defensive positions"
- Strategy: "User follows Buffett's value investing"
→ Action: Extract as memory content with high confidence
```

### Change 4: Improve Worthiness Prompt

Add to `WORTHINESS_PROMPT`:

```markdown
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

---

## User Stories

### Story 4.1: Add Negative Examples to Extraction Prompt
**As a** memory system
**I want** explicit anti-patterns in the extraction prompt
**So that** the LLM avoids extracting truisms, state data, and echoes

**Acceptance Criteria:**
- [ ] Add "What NOT to Extract" section with 4 anti-patterns
- [ ] Add examples for each anti-pattern
- [ ] Run extraction on test conversations and verify no truisms extracted
- [ ] Measure: zero truisms in 10 test extractions

**Implementation:**
- Edit `src/services/prompts.py` EXTRACTION_PROMPT
- Add anti-pattern section after Core Extraction Rules

---

### Story 4.2: Improve Worthiness Prompt with Negative Cases
**As a** memory system
**I want** the worthiness check to reject obvious/redundant content
**So that** low-value content is filtered early (before LLM extraction)

**Acceptance Criteria:**
- [ ] Add "NOT Worthy" section to WORTHINESS_PROMPT
- [ ] Add "Ask Yourself" decision framework
- [ ] Test: "User wants to make money" → NOT worthy
- [ ] Test: "User prefers X because Y" → worthy

**Implementation:**
- Edit `src/services/prompts.py` WORTHINESS_PROMPT
- Add negative examples and decision framework

---

### Story 4.3: Add Semantic Entailment Check Before Storage
**As a** memory system
**I want** to check if new memories are semantically entailed by existing ones
**So that** redundant variations are not stored

**Acceptance Criteria:**
- [ ] Query existing memories before extraction (already done for context)
- [ ] Lower similarity threshold from 0.90 to 0.80
- [ ] Add entailment instruction to extraction prompt
- [ ] Measure: <5% duplicate rate post-implementation

**Implementation:**
- Edit `src/services/prompts.py` EXTRACTION_PROMPT deduplication section
- Edit `src/services/compaction_ops.py` similarity threshold
- Add explicit entailment reasoning to prompt

---

### Story 4.4: Separate State from Insight in Extraction
**As a** memory system
**I want** to distinguish between quantitative state and qualitative insight
**So that** state data goes to structured tools, insights go to memories

**Acceptance Criteria:**
- [ ] Add State vs. Insight classification guidance to prompt
- [ ] Holdings quantities route to portfolio object only
- [ ] Investment thesis/reasoning stored as memory content
- [ ] Test: "I bought 100 AAPL" → portfolio object, no content memory
- [ ] Test: "I bought AAPL for dividend income" → memory with insight

**Implementation:**
- Edit `src/services/prompts.py` EXTRACTION_PROMPT
- Add classification guidance
- Modify examples to show correct routing

---

### Story 4.5: Add Golden Record Consolidation to Compaction
**As a** memory system
**I want** compaction to merge semantically related memories into dense records
**So that** 5 Buffett memories become 1 high-quality memory

**Acceptance Criteria:**
- [ ] Add consolidation step after deduplication in compaction graph
- [ ] Cluster memories by topic/theme (embedding similarity)
- [ ] Use LLM to synthesize cluster into single golden record
- [ ] Preserve highest confidence, merge tags
- [ ] Test: 5 similar memories → 1 consolidated memory

**Implementation:**
- Edit `src/services/compaction_graph.py`
- Add `node_consolidate` after `node_dedup`
- Add consolidation prompt
- Add topic clustering logic

**Note:** This is the most complex story - consider P1 priority after other stories prove value.

---

## Implementation Plan

### Phase 1: Prompt Improvements (Stories 4.1-4.4)
**Effort:** 1-2 days
**Risk:** Low
**Impact:** High

1. Update WORTHINESS_PROMPT with negative cases
2. Update EXTRACTION_PROMPT with anti-patterns
3. Update EXTRACTION_PROMPT with entailment check
4. Update EXTRACTION_PROMPT with state/insight classification
5. Lower dedup threshold to 0.80
6. Test with sample conversations

### Phase 2: Golden Record Consolidation (Story 4.5)
**Effort:** 3-5 days
**Risk:** Medium
**Impact:** High

1. Add consolidation node to compaction graph
2. Implement topic clustering
3. Create consolidation prompt
4. Test with real user data
5. Add dry-run mode for safety

---

## Appendix: Proposed Prompt Diffs

### WORTHINESS_PROMPT Addition

```diff
+ ## NOT Worthy (Even if it seems like a preference)
+
+ - Generic desires everyone has ("wants to make money", "wants success")
+ - Quantitative facts about holdings (portfolio tool tracks these)
+ - Obvious implications of stated preferences
+ - Restatements of previous memories
+ - Meta-commentary about the conversation itself
+
+ ## Ask Yourself
+
+ Before marking as worthy:
+ 1. Would this help personalize responses for THIS user vs. any user?
+ 2. Is this NOVEL information not already stored?
+ 3. Is this INSIGHT (why) rather than STATE (what)?
+
+ If any answer is NO, mark as NOT worthy.
```

### EXTRACTION_PROMPT Addition

```diff
+ ## CRITICAL: What NOT to Extract
+
+ ### Anti-Pattern 1: Truisms & Obvious Statements
+ DO NOT extract generic statements that are universally true or obvious:
+ ❌ "User wants to make money."
+ ❌ "User has an investment portfolio."
+ ❌ "User owns stocks."
+
+ ### Anti-Pattern 2: State Data (Belongs in Structured Tools)
+ DO NOT extract quantitative holdings - the Portfolio tool tracks this:
+ ❌ "User owns 2810 shares of Rocket Lab."
+ ✅ "User holds Rocket Lab because of belief in neutron rocket reusability."
+
+ ### Anti-Pattern 3: Semantic Echoes
+ If existing memory captures the essence, SKIP the new one.
+
+ ### Anti-Pattern 4: Restatements of Actions
+ ❌ "User asked about AAPL stock." (meta-chatter)
```

---

## Testing Strategy

### Test Cases for Prompt Improvements

| Input | Expected Output | Anti-Pattern Tested |
|-------|-----------------|---------------------|
| "I want to make money investing" | Empty / NOT worthy | Truism |
| "I own 500 shares of AAPL" | Portfolio object only, no memory | State Data |
| "I bought AAPL for the dividend" | Memory: insight about dividend | State vs Insight |
| "I like Buffett" (existing: "User follows Buffett") | Empty / SKIP | Semantic Echo |
| "I also like Munger's approach" | Memory: Munger addition | Novel info |

### Regression Tests

- Ensure valid preferences still extracted ("User prefers dark mode")
- Ensure profile data still extracted ("User's name is X")
- Ensure project data still extracted ("User is working on X")
- Ensure relationship data still extracted ("User's wife is Emma")

---

## Open Questions

1. **Threshold tuning:** Is 0.80 the right similarity threshold? May need tuning.
2. **Consolidation frequency:** Run consolidation daily? Weekly? On-demand?
3. **Consolidation safety:** What if consolidation loses important nuance?
4. **Tool awareness:** How to dynamically know what tools exist?

---

## References

- User feedback (2025-12-20 chat session)
- Current prompts: `src/services/prompts.py`
- Compaction pipeline: `src/services/compaction_graph.py`
- Extraction pipeline: `src/services/graph_extraction.py`

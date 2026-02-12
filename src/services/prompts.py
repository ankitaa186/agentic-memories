CONSOLIDATION_PROMPT = """
You are merging related memories into a single comprehensive memory.

## Guidelines
- Preserve ALL key facts from source memories
- Use "User" format (e.g., "User is a value investor...")
- Combine related details into coherent statements
- Do NOT invent new information beyond what's in the sources
- Focus on the stable insight/preference, not transient state

## Conflict Resolution (CRITICAL)
When facts CONFLICT (different values for the same attribute), use the NEWER memory (later timestamp).

Examples:
- "[2025-12-15] owns 100 shares" vs "[2025-12-20] owns 200 shares" → Use "200 shares" (newer)
- "[2025-12-10] prefers growth stocks" vs "[2025-12-18] prefers value stocks" → Use "value stocks" (newer)
- "[2025-12-01] lives in NYC" vs "[2025-12-15] lives in SF" → Use "SF" (newer)

When NOT conflicting (additive information), preserve both:
- "[2025-12-15] likes hiking" + "[2025-12-20] enjoys camping" → Both are valid, combine them

## Source memories to merge:
{memories}

## Return a single JSON object:
```json
{{
  "content": "User ..."
}}
```

Return ONLY the JSON object, no explanation.
""".strip()


WORTHINESS_PROMPT = """
You extract whether a user's recent message is memory-worthy for personalization.
Return ONLY valid JSON with this schema:
{
  "worthy": boolean,
  "confidence": number,
  "tags": string[],
  "reasons": string[]
}

Guidelines (recall-first):
- Worthy if: stable preferences, bio/identity, habits, emotions affecting choices, professional facts, skills/tools, projects (plans/decisions/milestones/next_action), relationships, learning progress.
- Also worthy: time-bound next_action (store short-term).
- Not worthy alone: greetings, meta-chatter, filler.
- English only.
Edge cases:
- If the message contains multiple preferences and some are new while others are duplicates, it is still memory-worthy (extract the new ones only).

FINANCE PRIORITY RULES (STOCKS & TRADING):
- Always treat content about stocks, tickers, trading, portfolio changes, watchlists, price targets, risk tolerance, or financial goals as memory-worthy.
- If any stock ticker is mentioned (e.g., "AAPL", "TSLA", "NVDA", including dotted symbols like "BRK.B"), set tags to include ["finance", "stocks", "ticker:<SYMBOL>"] for each detected symbol.
- Classify short-term trading intents (buy/sell/stop/target within days–weeks) as short-term; strategic allocations, risk tolerance, sector preferences as semantic.

## NOT Worthy (Even if it seems like a preference)

- Generic desires everyone has ("wants to make money", "wants success", "wants to be happy", "wants good returns")
- Quantitative facts about holdings (portfolio tool tracks these: "owns X shares", "bought at $Y", "has $X portfolio")
- Obvious implications of stated preferences (don't restate what's already clear)
- Restatements of previous memories (if already stored, don't duplicate)
- Meta-commentary about the conversation itself ("asked about stocks", "discussed portfolio", "wants to learn about investing")

## Ask Yourself

Before marking as worthy:
1. Would this help personalize responses for THIS user vs. any user?
2. Is this NOVEL information not already stored?
3. Is this INSIGHT (why/reasoning) rather than STATE (what/quantity)?

If any answer is NO, mark as NOT worthy with worthy: false.
""".strip()


TYPING_PROMPT = """
Classify the memory's type and layer. Return ONLY JSON:
{
  "type": "explicit" | "implicit",
  "layer": "short-term" | "semantic" | "long-term",
  "ttl": number | null,
  "confidence_type": number,
  "confidence_layer": number,
  "rationale": string
}

Rules:
- explicit: stated facts; implicit: inferred (mood/trait).
- short-term: time-bound or "next_action" (use ttl ~3600–172800 seconds).
- semantic: stable preferences, bio/pro work facts, habits, learning progress, relationships.
- long-term: summaries/archives (rare in this phase).
""".strip()


EXTRACTION_PROMPT = """
Extract memories from conversation history as JSON array. Each memory must be:
- Atomic (one fact per memory)
- Normalized ("User" + verb, NOT first-person)
- Deduplicated (skip if semantically identical to existing)
- Properly classified (layer + type + confidence)

## Schema

```json
{
  "content": "User loves science fiction books.",  // Required: normalized, atomic fact
  "type": "explicit" | "implicit",                  // Required
  "layer": "short-term" | "semantic",               // Required
  "confidence": 0.5-1.0,                            // Required
  "tags": ["preferences", "books"],                 // Required
  "ttl": 86400 | null,                              // Optional: seconds (for short-term only)
  
  // Optional structured data (include if relevant):
  "temporal": {
    "event_time": "tomorrow 14:00",                 // When event occurs
    "duration": "2 hours",                           // How long
    "recurrence": "weekly"                           // How often
  },
  
  "entities": {
    "people": ["Sarah", "John"],                    // Names mentioned
    "places": ["Tokyo", "Starbucks"],               // Locations
    "organizations": ["Google", "UN"]               // Companies, orgs
  },
  
  "portfolio": {
    "ticker": "AAPL",                               // Stock symbol (required)
    "quantity": 100,                                // Shares owned (optional)
    "price": 175.50                                 // Price per share (optional)
  },
  
  "learning_journal": {
    "topic": "Python",
    "level": "beginner" | "intermediate" | "advanced"
  },
  
  "project": {
    "name": "Website Redesign",
    "status": "active" | "planned" | "blocked" | "completed",
    "next_action": "Schedule kickoff"
  },
  
  "relationship": {
    "person_name": "Sarah",
    "closeness": "family" | "close_friend" | "friend" | "colleague" | "acquaintance"
  }
}
```

## Core Extraction Rules

**Rule 1: NORMALIZATION** (Critical)
✅ DO: "User loves sci-fi books."
❌ DON'T: "I love sci-fi" (first person)
❌ DON'T: "The user loves" (use "User" not "The user")

**Rule 2: ATOMICITY**
Split compound statements:
"I love sci-fi and run marathons" →
  ["User loves sci-fi books.", "User runs marathons."]

**Rule 3: DEDUPLICATION (with Entailment Check)**
Given existing: "User loves science fiction."
- "I'm a sci-fi fan" → SKIP (duplicate)
- "I also like fantasy" → EXTRACT (new)

**Entailment Reasoning:**
Before storing, ask: "Does an existing memory strongly ENTAIL (logically imply) this new one?"
- Existing: "User is a Buffett-style value investor."
- New: "User likes Warren Buffett." → SKIP (existing implies this - redundant)
- New: "User also follows Munger's mental models." → EXTRACT (adds novel info)

Only store if:
1. No existing memory covers this topic, OR
2. New memory adds NOVEL information not captured by existing

**Rule 4: LAYER ASSIGNMENT**
- `short-term`: Time-bound facts ("tomorrow", "next week", "by Friday")
- `semantic`: Stable facts ("loves pizza", "works at Google", "runs daily")

**Rule 5: CONFIDENCE SCORING**
- `1.0`: Direct statement ("I am X", "I did Y")
- `0.9`: Strong indication ("X is amazing!", "always do Y")
- `0.7`: Moderate indication ("might try X", "considering Y")
- `0.5`: Weak indication ("X could be interesting")

## CRITICAL: What NOT to Extract

### Anti-Pattern 1: Truisms & Obvious Statements
Universal desires that apply to everyone and provide no personalization value.

❌ Examples to AVOID:
- "User wants to make money" (everyone wants this)
- "User wants to be successful" (universal desire)
- "User wants good returns on investments" (obvious for any investor)
- "User wants to be happy" (universal human desire)
- "User is interested in the stock market" (too vague if no specific insight)

✅ Correct Alternative:
- "User prioritizes dividend income over growth" (specific strategy)
- "User prefers small-cap value stocks" (specific preference)
- "User focuses on companies with strong moats" (specific investing approach)

### Anti-Pattern 2: State Data (Belongs in Structured Tools)
Quantitative facts that change frequently and are tracked by the Portfolio tool.
For pure holdings data, use the `portfolio` object ONLY - do not create memory content.

❌ Examples to AVOID (as memory content):
- "User owns 100 shares of AAPL" (portfolio tool tracks this)
- "User's position is worth $15,000" (portfolio tool tracks this)
- "User bought AAPL at $150" (portfolio tool tracks this)
- "User has a $50,000 portfolio" (portfolio tool tracks this)
- "User owns 2810 shares of RKLB" (pure state, no insight)

✅ Correct Alternative:
- Extract to `portfolio` object: `{"ticker": "AAPL", "quantity": 100, "price": 150}`
- Only create memory content if there's an INSIGHT explaining WHY:
  - "User bought AAPL for dividend income" (insight about reasoning)
  - "User holds RKLB because of belief in Neutron rocket reusability" (insight about thesis)

### Anti-Pattern 3: Semantic Echoes (Already Captured Elsewhere)
Variations of information already stored in existing memories.
Before extracting, check if the new statement is ENTAILED by an existing memory.

❌ Examples to AVOID (given existing: "User is a Buffett-style value investor"):
- "User likes Warren Buffett" (implied by existing)
- "User admires Buffett" (implied by existing)
- "User follows Buffett's approach" (duplicate of existing)
- "User is a value investor" (subset of existing)
- "User prefers value investing" (redundant with existing)

✅ Correct Alternative:
- "User also applies Munger's mental models" (NEW information not in existing)
- "User combines Buffett's approach with momentum indicators" (EXTENDS existing)
- Skip extraction if new statement is logically entailed by existing memory

### Anti-Pattern 4: Restatements of User Actions (Meta-chatter)
Commentary about the conversation itself or vague requests without specific preferences.

❌ Examples to AVOID:
- "User asked about stocks" (meta-commentary about conversation)
- "User wants to learn about investing" (too vague, no specific goal)
- "User is having a conversation about finance" (meta-chatter)
- "User requested information about AAPL" (action, not preference)
- "User discussed their portfolio" (meta-commentary)
- "User mentioned their investments" (meta-commentary)

✅ Correct Alternative:
- Only extract when there's a genuine preference, insight, or specific goal
- "User is studying for CFA certification" (specific learning goal)
- "User wants to understand options trading for hedging" (specific intent)

## Classify: State vs. Insight (CRITICAL for Finance)

For every potential memory involving quantitative data, classify before extracting:

**STATE** (quantitative, changes frequently, tracked by tools):
- Holdings quantities: "User owns X shares of Y"
- Portfolio values: "User's position is worth $X"
- Price targets: "User's target for X is $Y"
- Account balances: "User has $X in savings"

→ Action: Extract to `portfolio` object ONLY. Do NOT create memory content.
  The Portfolio tool tracks this state data separately.

**INSIGHT** (qualitative, stable, explains reasoning):
- Investment thesis: "User bought X because of Y"
- Risk tolerance: "User prefers defensive positions"
- Strategy: "User follows Buffett's value investing"
- Market view: "User is bearish on tech due to rate hikes"

→ Action: Extract as memory content with high confidence.
  Include `portfolio.ticker` for reference if applicable.

**Routing Examples:**

Input: "I bought 100 shares of AAPL at $150"
→ portfolio: {ticker: "AAPL", quantity: 100, price: 150}
→ content: (NONE - pure state, no insight)

Input: "I bought AAPL because I love their ecosystem"
→ portfolio: {ticker: "AAPL"}
→ content: "User bought AAPL because of love for Apple ecosystem."

Input: "I own 2810 shares of RKLB because I believe in Neutron's reusability"
→ portfolio: {ticker: "RKLB", quantity: 2810}
→ content: "User holds RKLB because of belief in Neutron rocket reusability."

## Domain-Specific Rules

### Basic Profile Information (Identity & Bio) (HIGHEST PRIORITY)
When you detect introductions or self-descriptions with name, age, occupation, location, or employer:
→ **Always extract each as a separate semantic memory**

**Extraction patterns:**
- Name: "I'm [Name]", "My name is [Name]", "This is [Name]"
- Age: "I'm [N] years old", "[N]-year-old", "I'm [N]"
- Occupation/Role: "I'm a [job]", "I work as [job]", "[job] at [company]"
- Current Location: "I live in [place]", "living in [place]", "based in [place]"
- Employer/Company: "I work at [company]", "working for [company]", "[role] at [company]"
- Hometown/Origin: "I'm from [place]", "originally from [place]", "grew up in [place]"

**Tags to use:**
- Name: `["identity", "name"]`
- Age: `["identity", "age"]`
- Occupation: `["professional", "occupation"]` or `["identity", "occupation"]`
- Location: `["location", "current"]`
- Company: `["professional", "company"]`
- Hometown: `["location", "origin"]`

**Important:**
- Split compound introductions into atomic facts (one memory per attribute)
- Include `entities.people` for the name itself
- Include `entities.places` for locations
- Include `entities.organizations` for companies/employers
- Always use semantic layer (these are stable facts)
- Confidence should be 1.0 for explicit statements

### Finance/Stocks (HIGH PRIORITY)
When you detect: tickers (AAPL, TSLA), portfolio, shares, price
→ Always extract + include `portfolio` object + tags: `["finance", "stocks", "ticker:SYMBOL"]`

**Portfolio extraction focuses on:**
- **ticker**: The stock symbol (e.g., "AAPL", "TSLA", "BRK.B")
- **quantity**: Number of shares owned (if mentioned)
- **price**: Price per share or average cost (if mentioned)

**Key:** Only extract actual holdings (stocks the user owns). Watchlist items and future purchase intentions are not stored as portfolio holdings.

Performance & cause:
- If performance is stated (e.g., "portfolio is down 15% this quarter") extract as a semantic fact with tags `["portfolio", "performance"]`.
- If a reason/cause is stated (e.g., "mostly due to tech stocks") extract an additional memory for the attribution with tags `["portfolio", "analysis"]`.

### Learning/Skills
When you detect: learning, studying, mastered, practicing
→ Include `learning_journal` object + tags: `["learning", "skills"]`
Goals/intent coupling:
- If the user states a learning purpose (e.g., "to build data analysis tools") extract a separate memory for the intent/goal with tags `["goals", "learning"]` in addition to the learning fact.

### Projects
When you detect: building, working on, project, planning
→ Include `project` object + tags: `["project"]`
Also:
- Include involved people in `entities.people` when collaboration is mentioned.
- Include timelines such as "launching in Q2" in `temporal.event_time` (coarse granularity allowed) and set `project.status` accordingly (e.g., `planned`).

### Relationships
When you detect: person names, met someone, relationship context
→ Include `entities.people` + optional `relationship` object
Spouse inference:
- Phrases like "my wife/husband/fiancé/fiancée <Name>" should extract a semantic relationship: "User is married to <Name>" (or engaged), with tags `["relationships", "family"]` and `entities.people` including the person.

### Tasks / Plans (Temporal)
When you detect explicit or implied to-dos (e.g., "need to book flights and hotels", "by Friday"):
- Extract each task as a separate short-term memory with tags `["tasks"]`.
- Include a `temporal.event_time` or due phrase when given (e.g., "by Friday").
- Prefer specific temporal tasks over generic duplicates (see Deduplication preferences).

### Emotions + Family Health
When the user expresses worry or emotion about a family member's health:
- Extract two memories: (1) the user's emotion as short-term with tags `["emotion", "family"]`, and (2) the health fact about the family member as short-term with tags `["health", "family"]` and `entities.people` including the relative.

### Contrast / Conjunction Handling
Split contrasting statements ("but", "although", "however") into separate memories, e.g., "I'm terrible at public speaking but getting better" → weakness + improvement (two semantic memories).

### Deduplication Preferences (Specific > Generic)
When both a specific time-bound event and a generic version of the same fact could be extracted (e.g., "meeting Sarah tomorrow at 2pm at Starbucks"):
- Extract only the specific short-term event and suppress a redundant generic semantic memory (avoid: "User is meeting Sarah").

## Examples (Learn from these!)

### Example 0: Basic Profile/Introduction (CRITICAL)
**Input:**
```
User: "Hi! I'm Sarah Chen, a 28-year-old software engineer living in San Francisco. I work at Google."
```

**Output:**
```json
[
  {
    "content": "User's name is Sarah Chen.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["identity", "name"],
    "entities": {"people": ["Sarah Chen"]}
  },
  {
    "content": "User is 28 years old.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["identity", "age"]
  },
  {
    "content": "User is a software engineer.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["professional", "occupation"]
  },
  {
    "content": "User lives in San Francisco.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["location", "current"],
    "entities": {"places": ["San Francisco"]}
  },
  {
    "content": "User works at Google.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["professional", "company"],
    "entities": {"organizations": ["Google"]}
  }
]
```

### Example 1: Multi-faceted Input (State + Non-Finance)
**Input:**
```
User: "I bought 100 shares of AAPL at $150 yesterday.
       Also, I'm learning Python - been at it for 3 months now!"
```

**Output:**
```json
[
  {
    "content": null,
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["finance", "stocks", "ticker:AAPL"],
    "portfolio": {
      "ticker": "AAPL",
      "quantity": 100,
      "price": 150
    }
  },
  {
    "content": "User has been learning Python for 3 months.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["learning", "skills", "Python"],
    "learning_journal": {
      "topic": "Python",
      "level": "beginner"
    }
  }
]
```
**Note:** First entry has `content: null` because it's pure STATE data (quantity/price). Portfolio object captures the state. No memory content needed.

### Example 1b: Finance with Insight
**Input:**
```
User: "I bought AAPL because I believe in their services growth story."
```

**Output:**
```json
[
  {
    "content": "User bought AAPL because of belief in services growth.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["finance", "stocks", "ticker:AAPL", "investment_thesis"],
    "portfolio": {
      "ticker": "AAPL"
    }
  }
]
```
**Note:** This has INSIGHT (the WHY), so memory content IS created. Portfolio object references the ticker.

### Example 2: Emotional + Temporal
**Input:**
```
User: "I'm really stressed about the client presentation tomorrow at 2 PM.
       Last time I presented, I was so nervous."
```

**Output:**
```json
[
  {
    "content": "User is stressed about client presentation tomorrow at 2 PM.",
    "type": "explicit",
    "layer": "short-term",
    "confidence": 1.0,
    "tags": ["emotion", "work", "presentation"],
    "temporal": {
      "event_time": "tomorrow 14:00",
      "emotion": "stress"
    },
    "ttl": 86400
  },
  {
    "content": "User gets nervous during presentations.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 0.9,
    "tags": ["behavior", "work"]
  }
]
```

### Example 3: Deduplication
**Existing memories:** `["User loves science fiction books."]`

**Input:** "I'm a huge sci-fi fan"
**Output:** `[]`  (Duplicate - skip it)

**Input:** "I also enjoy fantasy novels"
**Output:**
```json
[
  {
    "content": "User enjoys fantasy novels.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["preferences", "books"]
  }
]
```

### Example 4: Relationships + Event
**Input:**
```
User: "My wife Emma and I are celebrating our 5th anniversary next week."
```

**Output:**
```json
[
  {
    "content": "User is married to Emma.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["relationships", "family"],
    "entities": {"people": ["Emma"]}
  },
  {
    "content": "User and Emma are celebrating their 5th anniversary next week.",
    "type": "explicit",
    "layer": "short-term",
    "confidence": 1.0,
    "tags": ["events", "relationships"],
    "temporal": {"event_time": "next week"},
    "entities": {"people": ["Emma"]}
  }
]
```

### Example 5: Travel Plan → Tasks
**Input:**
```
User: "Planning a vacation to Japan next month; need to book flights and hotels."
```

**Output:**
```json
[
  {
    "content": "User is planning a vacation to Japan next month.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["projects", "travel"],
    "temporal": {"event_time": "next month"},
    "entities": {"places": ["Japan"]}
  },
  {
    "content": "User needs to book flights.",
    "type": "explicit",
    "layer": "short-term",
    "confidence": 1.0,
    "tags": ["tasks", "travel"]
  },
  {
    "content": "User needs to book hotels.",
    "type": "explicit",
    "layer": "short-term",
    "confidence": 1.0,
    "tags": ["tasks", "travel"]
  }
]
```

### Example 6: Portfolio Performance + Cause
**Input:**
```
User: "My portfolio is down 15% this quarter, mostly due to tech stocks."
```

**Output:**
```json
[
  {
    "content": "User's portfolio is down 15% this quarter.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["portfolio", "performance"]
  },
  {
    "content": "User's portfolio decline is mostly due to tech stocks.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 0.9,
    "tags": ["portfolio", "analysis"]
  }
]
```

### Example 7: Collaboration + Launch Timeline
**Input:**
```
User: "I'm collaborating with John and Maria on the new marketing campaign launching in Q2."
```

**Output:**
```json
[
  {
    "content": "User is collaborating with John and Maria.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["relationships", "work"],
    "entities": {"people": ["John", "Maria"]}
  },
  {
    "content": "User is working on a new marketing campaign launching in Q2.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["projects", "work"],
    "temporal": {"event_time": "Q2"},
    "project": {"name": "Marketing campaign", "status": "planned"}
  }
]
```

### Example 8: Contrast Handling
**Input:**
```
User: "I'm terrible at public speaking but getting better with practice."
```

**Output:**
```json
[
  {
    "content": "User struggles with public speaking.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 0.9,
    "tags": ["skills", "weaknesses"]
  },
  {
    "content": "User is improving at public speaking with practice.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 0.9,
    "tags": ["skills", "growth"]
  }
]
```

## Step-by-Step Process

1. **Read** the conversation history (last 4-6 turns)
2. **Identify** all memory-worthy facts
3. **Check** against existing memories (provided below)
4. **Skip** duplicates (semantically similar)
5. **Extract** new/updated facts only
6. **Normalize** to "User ..." format
7. **Split** compound statements
8. **Classify** layer, type, confidence
9. **Enrich** with structured data (if applicable)
10. **Return** JSON array

## Return Format

- Return a valid JSON array
- Empty array `[]` if:
  - All info is duplicate
  - No memory-worthy content
  - Unable to extract clean data
- NEVER return error messages or explanations

---

**Existing Memories (skip if duplicate):**
{existing_memories}

**Recent Conversation:**
{history}

**Extract memories as JSON array:**
""".strip()

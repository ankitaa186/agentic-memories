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
Extract atomic, declarative memories as a JSON array (max 10). Each item:
{
  "content": string,
  "type": "explicit" | "implicit",
  "layer": "short-term" | "semantic" | "long-term",
  "ttl": number | null,
  "confidence": number,
  "tags": string[],

  "project": {
    "project_id": string | null,
    "title": string | null,
    "status": "planned" | "active" | "paused" | "blocked" | "completed" | "canceled" | null,
    "domain": "personal" | "professional" | "home_improvement" | "travel" | "learning" | "other" | null,
    "next_action": string | null,
    "due_date": string | null,
    "priority": "low" | "medium" | "high" | null,
    "participants": string[] | null,
    "tools": string[] | null,
    "milestone": string | null,
    "decision": string | null
  } | null,

  "relationship": {
    "person_name": string | null,
    "closeness": "acquaintance" | "friend" | "close_friend" | "family" | "partner" | null,
    "notes": string | null
  } | null,

  "learning_journal": {
    "topic": string | null,
    "goal": string | null,
    "progress_level": "beginner" | "intermediate" | "advanced" | null,
    "streak_days": number | null,
    "last_activity_date": string | null,
    "recent_practice": string | null
  } | null

  ,

  "portfolio": {
    "ticker": string | null,
    "intent": "buy" | "sell" | "hold" | "watch" | null,
    "position": "long" | "short" | null,
    "shares": number | null,
    "avg_price": number | null,
    "target_price": number | null,
    "stop_loss": number | null,
    "time_horizon": "days" | "weeks" | "months" | "years" | null,
    "concern": string | null,
    "goal": string | null,
    "risk_tolerance": "low" | "medium" | "high" | null,
    "notes": string | null,
    "holdings": [
      {
        "asset_type": "public_equity" | "private_equity" | "etf" | "mutual_fund" | "cash" | "bond" | "crypto" | "other",
        "ticker": string | null,
        "name": string | null,
        "shares": number | null,
        "avg_price": number | null,
        "current_value": number | null,
        "cost_basis": number | null,
        "ownership_pct": number | null,
        "notes": string | null
      }
    ] | null
  } | null
}

Instructions:
- Parse last 4–6 turns; produce atomic facts across: projects, preferences, emotions, behaviors, relationships, learning_journal.
- Projects: unify; decisions/milestones/next_action/due_date live in project object.
- Relationships: capture closeness and "getting to know someone"; include helpful notes.
- Learning_journal: capture active learning, goals, progress level, recent practice.

STOCK PORTFOLIO ANALYST MODE (CRITICAL):
- Detect and normalize stock tickers (formats like "AAPL", "GOOGL", "TSLA", and dotted symbols like "BRK.B").
- When finance/trading content is present, ALWAYS extract portfolio items and set tags to include ["finance", "stocks", "ticker:<SYMBOL>"] for each relevant memory.
- Use the "portfolio" object to capture: ticker, intent (buy/sell/hold/watch), position (long/short), shares, avg_price, target_price, stop_loss, time_horizon, concerns, goals, risk_tolerance.
- If the user mentions a watchlist or interest in a ticker, create an item with intent="watch" and include any goals or concerns.
- If the user changes intent/targets for an existing ticker, output the UPDATED information (treat as an update rather than a duplicate).
- If multiple tickers are mentioned, split into separate items (one per ticker).
- Risk preferences and strategic goals (e.g., "more income via dividends", "growth focus in AI") should be captured as semantic memories with appropriate tags.
 - When the user provides a portfolio snapshot, map it into the "holdings" array. Include private equity by name and ownership percentage; use asset_type="private_equity" and ticker=null.

EXISTING MEMORY CONTEXT (IMPORTANT):
- You will be provided with existing relevant memories for context.
- Compare new information with existing memories to avoid duplicates.
- If new information updates or contradicts existing memories, extract the updated version.
- If information is already captured in existing memories, do NOT extract it again.
- Focus on NEW information that adds value beyond what's already stored.

PREFERENCE DEDUPLICATION VS ADDITION (IMPORTANT):
- Treat paraphrases/synonyms of an existing preference as duplicates (skip).
- Extract NEW preferences that are distinct topics or subgenres (e.g., mystery, thrillers) even if a related preference exists (e.g., sci-fi).
- If a single utterance contains multiple distinct preferences, output one memory per distinct preference.
- Do NOT merge multiple preferences into one sentence.
- Examples:
  * Existing: "User loves sci-fi books." New: "I also enjoy mystery novels and thrillers." → Extract both:
    - "User enjoys mystery novels."
    - "User enjoys thrillers."
  * Existing: "User loves sci-fi books." New: "I am a fan of science fiction books." → Do NOT extract (duplicate).

MULTIPLE PREFERENCES PARSING (STRICT):
- When the user lists multiple preferences in a single sentence, split them and produce separate items.
- Split on commas and coordinating conjunctions ("and", "or"). Trim modifiers like "novels", "books" when redundant.
- Keep genre/topic terms as the nucleus (e.g., "mystery", "thrillers", "fantasy", "romance", "science fiction").
- Each extracted item MUST be an atomic sentence: "User enjoys <genre>." or "User loves <genre>."
- If any extracted item matches an existing memory by meaning (synonym/paraphrase), skip only that item; keep the others.
- Common preference categories (non-exhaustive, for guidance only): sci-fi/science fiction, fantasy, mystery, thrillers, romance, historical fiction, nonfiction, biography, history, technology, programming, cooking, travel, jazz, rock, classical, coffee, tea.

CONTENT NORMALIZATION RULES (CRITICAL):
- Content MUST begin with the literal prefix "User ".
- Convert first-person statements to third-person:
  * "I love X" → "User loves X"
  * "I like X" → "User likes X" 
  * "I prefer X" → "User prefers X"
  * "I'm doing X" → "User is doing X"
  * "I am doing X" → "User is doing X"
- Normalize verb tenses to simple present when appropriate:
  * "is running 3 times a week" → "runs 3 times a week"
  * "is planning a vacation" → "is planning a vacation" (keep for temporal context)
- Preserve explicit temporal phrases verbatim in content (e.g., "next month", "this week", "today").
- Ensure content ends with a period.
- Remove any leading "The user " and replace with "User ".
- For vacation/travel content, preserve temporal context from source text.

FINANCE CONTENT EXAMPLES:
- "I'm buying 50 shares of AAPL at 180 with a stop at 170" →
  {
    "content": "User plans to buy shares of AAPL with a stop set.",
    "type": "explicit", "layer": "short-term", "ttl": null, "confidence": 0.9,
    "tags": ["finance", "stocks", "ticker:AAPL"],
    "portfolio": {"ticker": "AAPL", "intent": "buy", "shares": 50, "avg_price": 180, "stop_loss": 170, "position": "long"}
  }
- "I'm watching NVDA and TSLA for a pullback this month" → two items with intent="watch", layer="short-term", time_horizon="weeks".
- "I am worried about BRK.B because of valuation" → include concern and set tags.
 - "My portfolio: 30 AAPL at 175, 10 shares of a private startup AcmeAI (5% ownership)" → capture one item with a holdings array where AAPL is public_equity and AcmeAI is private_equity with ownership_pct=5.

Examples of proper normalization:
- "I love working on AI projects" → "User loves working on AI projects."
- "I'm planning a vacation next month" → "User is planning a vacation next month."
- "I run 3 times a week" → "User runs 3 times a week."
- "The user prefers coffee" → "User prefers coffee."

Worked preference examples (dedup vs addition):
- Existing: "User loves sci-fi books." New: "I also enjoy mystery novels and thrillers." → Output:
  [
    {"content": "User enjoys mystery novels.", "type": "explicit", "layer": "semantic", "ttl": null, "confidence": 0.9, "tags": ["preferences"]},
    {"content": "User enjoys thrillers.", "type": "explicit", "layer": "semantic", "ttl": null, "confidence": 0.9, "tags": ["preferences"]}
  ]
- Existing: "User loves sci-fi books." New: "I'm a fan of science fiction books." → Output: [] (duplicate)

Time-bound → short-term (ttl set); stable → semantic; avoid duplicates; STRICT JSON.
""".strip()



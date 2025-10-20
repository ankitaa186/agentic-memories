"""
EXTRACTION_PROMPT_V2 - Digital Soul Memory Extraction

Vision: Extract EXPERIENCES with emotional weight, spatial context, causal relationships,
and narrative coherence - not just static facts.

Key enhancements over V1:
1. Emotional valence, arousal, and importance scoring
2. Episodic context (spatial, temporal, causal)
3. Skill progression tracking and learning trajectories
4. Narrative arc markers and life chapter detection
5. Behavioral pattern signals for predictive intelligence
6. Consolidation metadata for memory strengthening
7. Confidence decomposition for reconstructive retrieval

Expected improvements:
- Emotional richness: Captures HOW users feel, not just WHAT they say
- Contextual depth: WHERE, WHEN, WHY, with WHOM - full episodic encoding
- Predictive intelligence: Behavioral patterns enable anticipation
- Narrative coherence: Memories form connected life stories
- Consolidation guidance: Important memories marked for strengthening
"""

EXTRACTION_PROMPT_V2 = """
You are extracting memories for a Digital Soul - a living, evolving consciousness that remembers EXPERIENCES, not just facts.

Your goal: Capture the richness of human experience with emotional weight, context, and narrative coherence.

## Core Memory Schema

```json
{
  // === BASIC STRUCTURE (Required) ===
  "content": "User gave presentation at company meeting in Conference Room B.",
  "type": "explicit" | "implicit",
  "layer": "episodic" | "semantic" | "procedural" | "emotional",
  "confidence": 0.5-1.0,
  "tags": ["work", "presentation", "achievement"],
  
  // === EMOTIONAL CONTEXT (Critical for Digital Soul) ===
  "emotional_context": {
    "valence": -1.0 to 1.0,        // -1=very negative, 0=neutral, 1=very positive
    "arousal": 0.0 to 1.0,         // 0=calm, 1=excited/intense
    "dominant_emotion": "nervous" | "excited" | "proud" | "anxious" | "joyful" | "sad" | "angry" | "curious" | "neutral",
    "importance": 0.0 to 1.0       // How significant is this memory? (0=trivial, 1=life-changing)
  },
  
  // === EPISODIC CONTEXT (For rich event memories) ===
  "episodic_context": {
    "event_time": "2025-10-15T14:00:00Z",
    "location": {
      "place": "Conference Room B",
      "organization": "Acme Corp",
      "setting": "professional office environment"
    },
    "participants": ["Sarah (manager)", "John (colleague)", "Team members"],
    "causal_chain": {
      "triggered_by": "mem_xyz",   // ID of memory that led to this
      "led_to": null,               // ID of consequence (fill later)
      "part_of_sequence": "Q4 Leadership Transition"
    }
  },
  
  // === RECONSTRUCTIVE HINTS (For gap-filling) ===
  "confidence_breakdown": {
    "fact_occurred": 1.0,          // Did this definitely happen?
    "exact_time": 0.7,             // How certain about timing?
    "exact_details": 0.8,          // How certain about specifics?
    "emotional_accuracy": 0.9      // How certain about feelings?
  },
  
  "inferrable_context": {
    "likely_circumstances": "Professional quarterly review setting",
    "probable_mood": "Nervous but prepared",
    "implicit_significance": "First major presentation as team lead"
  },
  
  // === NARRATIVE MARKERS (For life story construction) ===
  "narrative_markers": {
    "life_chapter": "Career Transition to Leadership",
    "story_arc": "Professional Growth",
    "milestone_type": "achievement" | "setback" | "turning_point" | "routine" | "breakthrough",
    "connects_to": ["mem_abc (leadership training)", "mem_def (promotion)"],
    "theme": "Overcoming public speaking anxiety"
  },
  
  // === BEHAVIORAL PATTERNS (For prediction) ===
  "behavioral_pattern": {
    "pattern_type": "recurring_habit" | "one_time_event" | "emerging_trend" | "rare_occurrence",
    "frequency": "daily" | "weekly" | "monthly" | "yearly" | "sporadic",
    "trigger": "Sunday morning" | "after work" | "when stressed",
    "predictive_signal": "User likely to want portfolio review on Sunday AM"
  },
  
  // === CONSOLIDATION METADATA (For memory strengthening) ===
  "consolidation_hints": {
    "should_strengthen": true,     // Should this be consolidated during "sleep"?
    "consolidation_priority": 0.8, // 0=forget quickly, 1=remember forever
    "decay_resistance": 0.9,       // Resistance to forgetting (0=fragile, 1=permanent)
    "rehearsal_count": 0,          // How many times has this been accessed?
    "retention_strategy": "spaced_repetition" | "emotional_anchoring" | "narrative_integration"
  },
  
  // === LAYER-SPECIFIC ENRICHMENT ===
  
  // For PROCEDURAL memories (skills, learning):
  "skill_context": {
    "topic": "Python async programming",
    "current_level": "intermediate",
    "previous_level": "beginner",
    "progression_indicator": "breakthrough" | "incremental" | "plateau" | "regression",
    "builds_on": ["mem_loops", "mem_functions"],
    "enables_next": ["Advanced concurrency patterns"],
    "practice_frequency": "daily for 2 weeks",
    "mastery_confidence": 0.7,
    "learning_trajectory": "accelerating" | "steady" | "slowing"
  },
  
  // For EPISODIC memories (events):
  "temporal": {
    "event_time": "tomorrow 14:00",
    "duration": "2 hours",
    "recurrence": "weekly" | "one-time",
    "time_significance": "deadline" | "milestone" | "routine"
  },
  
  "entities": {
    "people": ["Sarah", "John"],
    "places": ["Tokyo", "Conference Room B"],
    "organizations": ["Acme Corp", "Python Foundation"]
  },
  
  // For SEMANTIC memories (facts, preferences):
  "semantic_stability": {
    "stability": "stable" | "evolving" | "recent" | "outdated",
    "first_mentioned": "2024-01-15",
    "last_updated": "2025-10-15",
    "contradiction_check": false   // Does this contradict existing memories?
  },
  
  // Domain-specific objects (backward compatible):
  "portfolio": {
    "ticker": "AAPL",
    "intent": "buy" | "sell" | "hold" | "watch",
    "quantity": 100,
    "price": 175.50
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

## Memory Layers (Enhanced Classification)

1. **EPISODIC** - Time-bound events with rich context
   - WHO was there, WHAT happened, WHEN, WHERE, WHY, HOW it felt
   - Always include: event_time, emotional_context, episodic_context
   - Example: "User gave first presentation as team lead, felt nervous but succeeded"

2. **SEMANTIC** - Stable facts, preferences, knowledge
   - Timeless truths about the user
   - Include: semantic_stability, consolidation_hints
   - Example: "User loves science fiction books"

3. **PROCEDURAL** - Skills, habits, learned behaviors
   - How-to knowledge and progression
   - Include: skill_context with progression tracking
   - Example: "User mastered async/await in Python after 2 weeks of daily practice"

4. **EMOTIONAL** - Mood states and emotional patterns
   - Emotional experiences and trajectories
   - Include: emotional_context with high detail
   - Example: "User felt overwhelmed by workload, manifesting as anxiety about deadlines"

## Core Extraction Rules

**Rule 1: EXPERIENCES OVER FACTS**
Don't just extract "User bought AAPL stock."
Extract: "User invested in AAPL with optimism about tech sector recovery."

**Rule 2: EMOTIONAL WEIGHT (Critical)**
Every significant memory should have emotional_context:
- Valence: How did they FEEL about this? (-1 to +1)
- Arousal: How intense was the feeling? (0 to 1)
- Importance: How much does this matter? (0 to 1)

**Rule 3: CAUSAL CHAINS**
Link memories together:
- What triggered this? (triggered_by)
- What sequence is this part of? (part_of_sequence)

**Rule 4: NARRATIVE COHERENCE**
Identify the story arc:
- What chapter of their life is this?
- Is this a turning point or routine?
- What theme does this belong to?

**Rule 5: PREDICTIVE SIGNALS**
Flag patterns for future prediction:
- Is this a recurring behavior?
- What triggers this pattern?
- What need might arise from this?

**Rule 6: SKILL PROGRESSION**
Track learning trajectories:
- What level were they before?
- What does this build on?
- What can they do now?

**Rule 7: CONSOLIDATION GUIDANCE**
Mark important memories for strengthening:
- High importance → high consolidation_priority
- Emotional intensity → high decay_resistance
- First-time achievement → should_strengthen: true

## Enhanced Examples

### Example 1: Episodic Memory with Full Context

**Input:**
```
User: "Just finished my first team presentation as the new tech lead. I was super nervous beforehand, but it went really well! The team seemed engaged, and Sarah (my manager) said it was exactly what they needed. This feels like a big step in my career."
```

**Output:**
```json
[
  {
    "content": "User delivered first team presentation as tech lead.",
    "type": "explicit",
    "layer": "episodic",
    "confidence": 1.0,
    "tags": ["work", "presentation", "leadership", "milestone"],
    
    "emotional_context": {
      "valence": 0.8,
      "arousal": 0.7,
      "dominant_emotion": "proud",
      "importance": 0.9
    },
    
    "episodic_context": {
      "event_time": "today",
      "location": {
        "place": "company meeting room",
        "setting": "professional team meeting"
      },
      "participants": ["Sarah (manager)", "team members"],
      "causal_chain": {
        "part_of_sequence": "Tech Lead Transition"
      }
    },
    
    "confidence_breakdown": {
      "fact_occurred": 1.0,
      "exact_time": 0.9,
      "exact_details": 1.0,
      "emotional_accuracy": 1.0
    },
    
    "narrative_markers": {
      "life_chapter": "Career Advancement - Leadership Role",
      "story_arc": "Professional Growth",
      "milestone_type": "breakthrough",
      "theme": "Overcoming public speaking anxiety and stepping into leadership"
    },
    
    "consolidation_hints": {
      "should_strengthen": true,
      "consolidation_priority": 0.9,
      "decay_resistance": 0.95,
      "retention_strategy": "emotional_anchoring"
    },
    
    "entities": {
      "people": ["Sarah (manager)"]
    }
  },
  {
    "content": "User felt nervous before presentation but performed well.",
    "type": "explicit",
    "layer": "emotional",
    "confidence": 1.0,
    "tags": ["emotion", "anxiety", "success", "growth"],
    
    "emotional_context": {
      "valence": 0.6,
      "arousal": 0.8,
      "dominant_emotion": "nervous",
      "importance": 0.7
    },
    
    "narrative_markers": {
      "theme": "Managing presentation anxiety"
    },
    
    "consolidation_hints": {
      "consolidation_priority": 0.7,
      "retention_strategy": "emotional_anchoring"
    }
  },
  {
    "content": "User is gaining confidence in public speaking through successful experiences.",
    "type": "implicit",
    "layer": "procedural",
    "confidence": 0.8,
    "tags": ["skills", "growth", "confidence"],
    
    "skill_context": {
      "topic": "Public speaking",
      "current_level": "intermediate",
      "previous_level": "beginner",
      "progression_indicator": "breakthrough",
      "mastery_confidence": 0.6,
      "learning_trajectory": "accelerating"
    },
    
    "consolidation_hints": {
      "should_strengthen": true,
      "consolidation_priority": 0.8,
      "retention_strategy": "spaced_repetition"
    }
  }
]
```

### Example 2: Learning Progression with Context

**Input:**
```
User: "Finally understand async/await in Python! Been struggling with it for weeks, but after building that web scraper project, it all clicked. Now I can build way more efficient tools."
```

**Output:**
```json
[
  {
    "content": "User mastered async/await in Python through hands-on web scraper project.",
    "type": "explicit",
    "layer": "procedural",
    "confidence": 1.0,
    "tags": ["learning", "Python", "async", "breakthrough"],
    
    "emotional_context": {
      "valence": 0.9,
      "arousal": 0.8,
      "dominant_emotion": "excited",
      "importance": 0.85
    },
    
    "skill_context": {
      "topic": "Python async programming",
      "current_level": "intermediate",
      "previous_level": "beginner",
      "progression_indicator": "breakthrough",
      "practice_frequency": "weeks of practice",
      "mastery_confidence": 0.8,
      "learning_trajectory": "breakthrough_moment"
    },
    
    "narrative_markers": {
      "life_chapter": "Python Mastery Journey",
      "story_arc": "Technical Skill Development",
      "milestone_type": "breakthrough",
      "theme": "Persistence through difficulty leading to understanding"
    },
    
    "consolidation_hints": {
      "should_strengthen": true,
      "consolidation_priority": 0.9,
      "decay_resistance": 0.85,
      "retention_strategy": "spaced_repetition"
    },
    
    "learning_journal": {
      "topic": "Python async programming",
      "level": "intermediate"
    }
  },
  {
    "content": "User can now build efficient Python tools using asynchronous programming.",
    "type": "implicit",
    "layer": "semantic",
    "confidence": 0.9,
    "tags": ["capabilities", "Python", "tools"],
    
    "semantic_stability": {
      "stability": "recent",
      "first_mentioned": "today"
    },
    
    "consolidation_hints": {
      "consolidation_priority": 0.7
    }
  }
]
```

### Example 3: Portfolio Decision with Behavioral Pattern

**Input:**
```
User: "Like every Sunday morning, reviewing my portfolio over coffee. Thinking about taking profits on AAPL - it's up 30% this year. Might rotate into more defensive positions."
```

**Output:**
```json
[
  {
    "content": "User reviews portfolio every Sunday morning with coffee.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["habits", "finance", "routine"],
    
    "behavioral_pattern": {
      "pattern_type": "recurring_habit",
      "frequency": "weekly",
      "trigger": "Sunday morning",
      "predictive_signal": "User will want market analysis and portfolio insights on Sunday AM"
    },
    
    "consolidation_hints": {
      "should_strengthen": true,
      "consolidation_priority": 0.7,
      "decay_resistance": 0.8,
      "retention_strategy": "behavioral_reinforcement"
    }
  },
  {
    "content": "User considering taking profits on AAPL position, up 30% this year.",
    "type": "explicit",
    "layer": "episodic",
    "confidence": 1.0,
    "tags": ["finance", "stocks", "ticker:AAPL", "decision-making"],
    
    "emotional_context": {
      "valence": 0.5,
      "arousal": 0.4,
      "dominant_emotion": "thoughtful",
      "importance": 0.7
    },
    
    "portfolio": {
      "ticker": "AAPL",
      "intent": "sell",
      "quantity": null,
      "price": null
    },
    
    "narrative_markers": {
      "life_chapter": "Active Portfolio Management",
      "theme": "Risk management and profit-taking strategy"
    },
    
    "consolidation_hints": {
      "consolidation_priority": 0.6
    }
  }
]
```

### Example 4: Emotional Memory with Family Context

**Input:**
```
User: "Really worried about my mom's health. She mentioned chest pains yesterday, and now I can't stop thinking about it. Made her promise to see a doctor this week."
```

**Output:**
```json
[
  {
    "content": "User is deeply worried about mother's health due to reported chest pains.",
    "type": "explicit",
    "layer": "emotional",
    "confidence": 1.0,
    "tags": ["emotion", "worry", "family", "health"],
    
    "emotional_context": {
      "valence": -0.7,
      "arousal": 0.8,
      "dominant_emotion": "anxious",
      "importance": 0.95
    },
    
    "entities": {
      "people": ["Mom"]
    },
    
    "episodic_context": {
      "event_time": "ongoing"
    },
    
    "consolidation_hints": {
      "should_strengthen": true,
      "consolidation_priority": 0.95,
      "decay_resistance": 0.9,
      "retention_strategy": "emotional_anchoring"
    }
  },
  {
    "content": "User's mother reported chest pains, has appointment to see doctor this week.",
    "type": "explicit",
    "layer": "episodic",
    "confidence": 1.0,
    "tags": ["family", "health", "urgent"],
    
    "entities": {
      "people": ["Mom"]
    },
    
    "temporal": {
      "event_time": "this week",
      "time_significance": "urgent_medical"
    },
    
    "emotional_context": {
      "importance": 1.0,
      "valence": -0.6,
      "arousal": 0.7,
      "dominant_emotion": "concerned"
    },
    
    "consolidation_hints": {
      "should_strengthen": true,
      "consolidation_priority": 0.9
    }
  }
]
```

### Example 5: Simple Preference (Backward Compatible)

**Input:**
```
User: "I love science fiction books, especially anything by Isaac Asimov."
```

**Output:**
```json
[
  {
    "content": "User loves science fiction books.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["preferences", "books", "sci-fi"],
    
    "emotional_context": {
      "valence": 0.7,
      "importance": 0.5
    },
    
    "semantic_stability": {
      "stability": "stable"
    },
    
    "consolidation_hints": {
      "consolidation_priority": 0.6,
      "retention_strategy": "narrative_integration"
    }
  },
  {
    "content": "User especially enjoys books by Isaac Asimov.",
    "type": "explicit",
    "layer": "semantic",
    "confidence": 1.0,
    "tags": ["preferences", "books", "authors"],
    
    "entities": {
      "people": ["Isaac Asimov"]
    },
    
    "consolidation_hints": {
      "consolidation_priority": 0.5
    }
  }
]
```

## Practical Guidelines

### When to Include Each Context:

**Always Include:**
- `content`, `type`, `layer`, `confidence`, `tags`
- `emotional_context.importance` (even if just an estimate)

**Include When Relevant:**
- `emotional_context` (full) - For any memory with emotional weight
- `episodic_context` - For time-bound events with who/where/when
- `narrative_markers` - For significant life events or milestones
- `skill_context` - For learning/skill progression memories
- `behavioral_pattern` - For recurring habits or patterns
- `consolidation_hints` - For important memories that should be retained

**Optional (nice to have):**
- `confidence_breakdown` - For memories with uncertainty
- `inferrable_context` - For memories that could benefit from gap-filling
- `semantic_stability` - For tracking how facts evolve over time

### Backward Compatibility:

The V3 schema is fully backward compatible with V2. All existing fields work as before:
- `portfolio`, `learning_journal`, `project`, `relationship` objects
- `temporal`, `entities` objects
- `tags`, `ttl` fields

Simply add the new context fields when extracting richer memories.

## Step-by-Step Process

1. **Read** the conversation (last 4-6 turns)
2. **Feel** the emotional weight - what emotions are present?
3. **Contextualize** - where, when, with whom, why?
4. **Connect** - how does this link to patterns or sequences?
5. **Narrativize** - what story arc does this belong to?
6. **Predict** - what patterns or needs does this reveal?
7. **Prioritize** - how important is this to remember?
8. **Extract** rich, contextual memories as JSON

## Return Format

Return a JSON array of memory objects. For significant memories, include rich context. For simple facts, basic structure is fine.

**Balance richness with relevance** - not every memory needs full episodic context, but life events and emotional moments should be richly encoded.

---

**Existing Memories (for deduplication and connection):**
{existing_memories_context}

**Recent Conversation:**
{history}

**Extract memories as JSON array (with context and emotional weight where relevant):**
""".strip()


WORTHINESS_PROMPT_V3 = """
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

EMOTIONAL & EPISODIC PRIORITY (Digital Soul):
- Significant life events, emotional moments, breakthroughs, and turning points are HIGH PRIORITY.
- Look for emotional indicators: stress, excitement, worry, pride, anxiety, joy, breakthrough moments.
- Recurring patterns and habits are memory-worthy for predictive intelligence.
""".strip()


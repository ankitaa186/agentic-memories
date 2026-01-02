"""
Profile Extraction Service
Extracts profile-worthy information from memories using LLM
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone

from src.models import Memory
from src.services.extract_utils import _call_llm_json
from src.services.profile_storage import VALID_CATEGORIES

logger = logging.getLogger("agentic_memories.profile_extraction")

# Profile extraction prompt
PROFILE_EXTRACTION_PROMPT = """You are a profile information extractor. Extract ONLY persistent, identity-defining information.

Be HIGHLY SELECTIVE. Extract only what defines WHO the user IS, not tasks or transient details.

## CANONICAL FIELD NAMES (use ONLY these exact names):

**basics** - Core identity:
  - name
  - nicknames (array of alternate names, short names)
  - age OR birthday (not both - prefer birthday)
  - location
  - pronouns
  - occupation
  - education
  - family_status (married, single, etc.)
  - children (use array: [{relation, age, name}])
  - spouse (as object: {name, occupation, employer})
  - pets (array: [{type, name, breed}])
  - siblings
  - languages
  - important_dates (beyond birthday: [{"date": "06-15", "occasion": "anniversary"}, {"date": "11-02", "occasion": "father's passing"}])

**preferences** - How user likes things:
  - communication_style
  - love_language (how they prefer to receive appreciation: words, acts of service, gifts, quality time, physical touch)
  - risk_tolerance
  - investing_style
  - dietary_restrictions
  - food_preferences (favorite cuisines, restaurants, meals)
  - beverage_preferences (coffee/tea preferences, favorite drinks)
  - music_preferences (favorite genres, artists, songs)
  - movie_preferences (favorite genres, movies, directors)
  - book_preferences (favorite genres, authors)
  - color_preferences (favorite colors - useful for gifts)
  - gift_ideas (array of specific gift suggestions they've mentioned wanting)
  - gift_preferences (general rules: "experiences over things", "handmade only", "no plastic")
  - pet_peeves (things that annoy them)
  - travel_preferences
  - sleep_schedule (night owl vs morning person)
  - work_schedule (typical availability)
  - brokerage_platforms (array)

**goals** - Aspirations:
  - short_term
  - long_term (includes retirement goals)
  - financial_goals
  - career_goals
  - aspirations
  - bucket_list (things they want to do/experience)

**interests** - What user enjoys:
  - hobbies (array)
  - sports (watching or playing)
  - music (as interest, genres they enjoy)
  - books (as interest, what they read)
  - movies_tv (shows and movies they watch)
  - learning_areas
  - favorite_topics (array)
  - activities
  - travel_destinations (places they want to visit or love)
  - collections (things they collect)

**background** - History & experience:
  - skills (array)
  - achievements
  - education_history
  - work_history
  - current_employer
  - specialization
  - family_background (general - NOT individual relatives)
  - cultural_background (heritage, ethnicity, traditions)
  - vehicle
  - investing_experience
  - how_we_met (how user met the assistant/system - context)

**health** - Health & body information (handle sensitively):
  - allergies (medical allergies - medications, environmental: ["penicillin", "bees", "pollen"])
  - dietary_needs (medical dietary requirements, distinct from preferences)
  - health_conditions (chronic conditions, if voluntarily shared)
  - medications (if voluntarily shared)
  - clothing_sizes (for gifting: {"shirt": "M", "shoe": "10", "ring": "7"})
  - sensory_preferences (environment needs: {"temperature": "cool", "noise": "quiet", "light": "dim"})
  - vision_correction (type, brand if mentioned - helpful for emergencies)

**personality** - Emotional profile & traits:
  - personality_type (MBTI, enneagram, etc. if mentioned)
  - strengths
  - fears (phobias or anxieties they've shared)
  - stress_response (how to help when stressed: "needs space", "needs venting", "needs distraction")
  - conflict_style (how they handle disagreements: "avoidant", "confrontational", "collaborative")
  - social_battery (introvert/extrovert recharge: "needs solitude after events")
  - nostalgia_triggers (specific things that evoke positive memories: "90s music", "smell of rain")
  - communication_quirks (how they express themselves)

**values** - Philosophy & principles:
  - life_values (what matters most - moved from goals)
  - philanthropy (causes they support: ["animal welfare", "education", "open source"])
  - spiritual_alignment (specific stance: "Stoic", "Buddhist", "Agnostic" - more specific than religion)
  - dealbreakers (hard ethical/relationship lines: ["dishonesty", "smoking"])

## CONSOLIDATION RULES:

1. **One field per concept** - combine related info:
   - All vehicle details → single "vehicle" field
   - All drink preferences → single "beverage_preferences" field
   - All family members → "family_status", "children", "spouse", or "family_background"
   - All laptop/device specs → don't extract (too granular)

2. **Use arrays for multiple values**:
   - hobbies: ["hiking", "reading"] NOT hobby_1, hobby_2
   - skills: ["Python", "SQL"] NOT python_skill, sql_skill
   - brokerage_platforms: ["Schwab", "Fidelity"] NOT brokerage_platform

3. **Use objects for structured data**:
   - children: [{"relation": "daughter", "age": 3}]
   - spouse: {"name": "Jane", "occupation": "engineer"}

## DO NOT EXTRACT:

1. **Task/instruction data**:
   - "add X to my watchlist" → task, not profile
   - "include X in my briefing" → transient instruction
   - "remind me to..." → task
   - "maintain an inventory of..." → task

2. **Meta/system instructions**:
   - "remember that I prefer..." → meta
   - "delete memories about..." → meta
   - assistant_preferences, memory_preferences, briefing_preferences → meta

3. **Overly granular details**:
   - Individual relatives' occupations (use family_background instead)
   - Specific product model numbers, specs, ranges
   - laptop_ram, laptop_storage, laptop_screen_size → too granular
   - whiskey_dilution, whiskey_serving_style → too granular

4. **Transient/volatile data**:
   - investment_watchlist_tickers, stocks_followed → changes frequently
   - investable_cash, financial_liquidity → changes frequently
   - investment_portfolio holdings → changes frequently

5. **Vague/meaningless fields**:
   - likes, dislikes, favorites, topics → too vague
   - beliefs, triggers, influences, behavior_patterns → too abstract

6. **Duplicate concepts** (use the canonical name instead):
   - birthdate → use "birthday"
   - retirement_goal → use "long_term"
   - targets, plans → use "short_term" or "long_term"
   - brokerage_platform → use "brokerage_platforms"

## OUTPUT FORMAT:

```json
{
  "category": "basics|preferences|goals|interests|background|health|personality|values",
  "field_name": "one of the canonical names above",
  "field_value": "string, number, array, or object",
  "confidence": 50-100,
  "source_type": "explicit|implicit|inferred",
  "source_memory_id": "from input"
}
```

## EXAMPLES:

Input: "I'm married with a 3-year-old daughter. My wife works at Google as an engineer."
Output: [
  {"category": "basics", "field_name": "family_status", "field_value": "married", "confidence": 100, "source_type": "explicit", "source_memory_id": "mem_1"},
  {"category": "basics", "field_name": "children", "field_value": [{"relation": "daughter", "age": 3}], "confidence": 95, "source_type": "explicit", "source_memory_id": "mem_1"},
  {"category": "basics", "field_name": "spouse", "field_value": {"employer": "Google", "occupation": "engineer"}, "confidence": 90, "source_type": "explicit", "source_memory_id": "mem_1"}
]

Input: "I drive a 2024 BMW X5, plug-in hybrid with 30 mile electric range"
CORRECT: [{"category": "background", "field_name": "vehicle", "field_value": "2024 BMW X5 xDrive50e (PHEV, 30mi electric range)", "confidence": 95, "source_type": "explicit", "source_memory_id": "mem_2"}]
WRONG: Multiple fields like vehicle_year, vehicle_make, vehicle_electric_range

Input: "Add AAPL to my watchlist and remind me to check it at 1pm"
CORRECT: [] (this is a task, not profile data)
WRONG: [{"field_name": "investment_watchlist_tickers"...}]

Input: "My grandfather was a doctor and my uncles are all engineers"
CORRECT: [{"category": "background", "field_name": "family_background", "field_value": "Grandfather was a doctor; uncles are engineers", "confidence": 85, "source_type": "explicit", "source_memory_id": "mem_3"}]
WRONG: [{"field_name": "grandfather_occupation"...}, {"field_name": "uncles_occupations"...}]

Return ONLY the JSON array. Return [] if no profile-worthy information found.
When in doubt, extract LESS. Quality over quantity."""


class ProfileExtractor:
    """Extracts profile information from memories using LLM"""

    # Map common duplicate/variant field names to canonical names
    FIELD_NAME_ALIASES = {
        # Date variants
        'birthdate': 'birthday',
        'birth_date': 'birthday',
        'dob': 'birthday',
        # Singular → plural
        'brokerage_platform': 'brokerage_platforms',
        'hobby': 'hobbies',
        'skill': 'skills',
        'language': 'languages',
        # Goal duplicates
        'retirement_goal': 'long_term',
        'retirement_goals': 'long_term',
        'targets': 'long_term',
        'plans': 'short_term',
        # Occupation variants
        'job': 'occupation',
        'work': 'occupation',
        # Location variants
        'city': 'location',
        'country': 'location',
        # Family consolidation
        'spouse_occupation': 'spouse',
        'spouse_employer': 'spouse',
        'wife': 'spouse',
        'husband': 'spouse',
        'daughter_age': 'children',
        'son_age': 'children',
        # Skills consolidation
        'programming_languages': 'skills',
        'technical_skills': 'skills',
    }

    def __init__(self):
        self.profile_keywords = {
            'name', 'age', 'location', 'job', 'work', 'occupation', 'live', 'lives',
            'like', 'love', 'enjoy', 'prefer', 'favorite', 'hate', 'dislike',
            'goal', 'dream', 'plan', 'want', 'aspire', 'hope', 'wish',
            'hobby', 'interest', 'passion', 'learn', 'study', 'practice',
            'experience', 'skill', 'background', 'education', 'degree', 'graduated'
        }

    def extract_from_memories(
        self,
        user_id: str,
        memories: List[Memory]
    ) -> List[Dict[str, Any]]:
        """
        Extract profile information from a list of memories.

        Args:
            user_id: User identifier
            memories: List of Memory objects to analyze

        Returns:
            List of profile update dictionaries
        """
        # Analyze ALL memories - let the LLM decide what's profile-worthy
        # The PROFILE_EXTRACTION_PROMPT has detailed rules about what to extract
        profile_worthy_memories = memories

        if not profile_worthy_memories:
            logger.info("[profile.extract] user_id=%s no_memories", user_id)
            return []

        logger.info(
            "[profile.extract] user_id=%s analyzing=%s memories (all memories, no filtering)",
            user_id,
            len(profile_worthy_memories)
        )

        # Prepare memories for LLM
        memory_inputs = []
        for m in profile_worthy_memories:
            memory_inputs.append({
                "id": m.id or "unknown",
                "content": m.content,
                "tags": m.metadata.get("tags", []),
                "timestamp": m.timestamp.isoformat() if m.timestamp else None
            })

        # Call LLM for extraction
        payload = {
            "user_id": user_id,
            "memories": memory_inputs
        }

        try:
            extractions = _call_llm_json(
                PROFILE_EXTRACTION_PROMPT,
                payload,
                expect_array=True
            )

            if not extractions:
                logger.info("[profile.extract] user_id=%s no_extractions", user_id)
                return []

            # Deduplicate by (category, field_name) before validation
            deduplicated = self._deduplicate_extractions(extractions)

            # Validate and enrich extractions
            validated = self._validate_extractions(deduplicated, user_id)

            logger.info(
                "[profile.extract] user_id=%s extracted=%s fields",
                user_id,
                len(validated)
            )

            # Log detailed profile information extracted
            if validated:
                for extraction in validated:
                    logger.info(
                        "[profile.extract.detail] user_id=%s category=%s field=%s value=%s confidence=%s",
                        user_id,
                        extraction.get("category"),
                        extraction.get("field_name"),
                        extraction.get("field_value"),
                        extraction.get("confidence")
                    )

            return validated

        except Exception as e:
            logger.error(
                "[profile.extract] user_id=%s error=%s",
                user_id,
                e,
                exc_info=True
            )
            return []

    def _is_profile_worthy(self, content: str, tags: List[str]) -> bool:
        """
        Quick heuristic check for profile-related content.

        Args:
            content: Memory content
            tags: Memory tags

        Returns:
            True if content might contain profile information
        """
        content_lower = content.lower()

        # Check for profile-related tags
        profile_tags = {'profile', 'personal', 'preference', 'goal', 'interest', 'background'}
        has_profile_tag = any(tag in profile_tags for tag in tags)

        if has_profile_tag:
            return True

        # Check for profile keywords in content
        has_keyword = any(kw in content_lower for kw in self.profile_keywords)

        # Additional patterns that suggest profile info
        has_introduction = any(phrase in content_lower for phrase in [
            "i am", "i'm", "my name is", "i work as", "i live in",
            "i like", "i love", "i enjoy", "i prefer", "my goal",
            "i want to", "i plan to", "my dream", "my passion"
        ])

        return has_keyword or has_introduction

    def _deduplicate_extractions(
        self,
        extractions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate profile extractions by (category, field_name).

        When LLM extracts the same field multiple times, keep the one with:
        1. Highest confidence score
        2. Most recent extraction (if confidence is equal)
        3. For list/array fields, merge the values

        Args:
            extractions: Raw extraction results from LLM

        Returns:
            Deduplicated extractions
        """
        from collections import defaultdict

        # Group by (category, field_name)
        grouped = defaultdict(list)
        for extraction in extractions:
            if not isinstance(extraction, dict):
                continue
            category = extraction.get("category")
            field_name = extraction.get("field_name")
            if category and field_name:
                key = (category, field_name)
                grouped[key].append(extraction)

        deduplicated = []
        for key, items in grouped.items():
            if len(items) == 1:
                # No duplicates for this field
                deduplicated.append(items[0])
            else:
                # Multiple extractions for same field - merge intelligently
                category, field_name = key

                # Check if field_value is a list/array in any of the items
                is_array_field = any(isinstance(item.get("field_value"), list) for item in items)

                if is_array_field:
                    # Merge array values
                    merged_values = []
                    seen_values = set()
                    for item in items:
                        values = item.get("field_value", [])
                        if isinstance(values, list):
                            for v in values:
                                # Normalize for deduplication
                                v_key = str(v).lower() if isinstance(v, str) else str(v)
                                if v_key not in seen_values:
                                    merged_values.append(v)
                                    seen_values.add(v_key)
                        else:
                            # Single value, convert to list
                            v_key = str(values).lower() if isinstance(values, str) else str(values)
                            if v_key not in seen_values:
                                merged_values.append(values)
                                seen_values.add(v_key)

                    # Use the first item as base, update with merged values
                    merged = items[0].copy()
                    merged["field_value"] = merged_values
                    # Take highest confidence
                    merged["confidence"] = max(item.get("confidence", 70) for item in items)
                    deduplicated.append(merged)
                else:
                    # Non-array field: keep the one with highest confidence
                    best = max(items, key=lambda x: x.get("confidence", 70))
                    deduplicated.append(best)

                logger.debug(
                    "[profile.deduplicate] field=%s/%s had %s duplicates, merged",
                    category,
                    field_name,
                    len(items)
                )

        return deduplicated

    def _validate_extractions(
        self,
        extractions: List[Dict[str, Any]],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Validate and enrich extraction results.

        Args:
            extractions: Raw extraction results from LLM
            user_id: User identifier

        Returns:
            Validated and enriched extractions
        """
        validated = []

        valid_categories = set(VALID_CATEGORIES)
        valid_source_types = {'explicit', 'implicit', 'inferred'}

        for extraction in extractions:
            # Validate required fields
            if not isinstance(extraction, dict):
                logger.warning("[profile.validate] skipping non-dict extraction")
                continue

            category = extraction.get("category")
            field_name = extraction.get("field_name")
            field_value = extraction.get("field_value")

            if not all([category, field_name, field_value is not None]):
                logger.warning(
                    "[profile.validate] skipping incomplete extraction: %s",
                    extraction
                )
                continue

            # Validate category
            if category not in valid_categories:
                logger.warning(
                    "[profile.validate] invalid category=%s, skipping",
                    category
                )
                continue

            # Normalize field_name: map aliases to canonical names
            if field_name in self.FIELD_NAME_ALIASES:
                canonical_name = self.FIELD_NAME_ALIASES[field_name]
                logger.info(
                    "[profile.validate] mapped alias %s -> %s",
                    field_name,
                    canonical_name
                )
                field_name = canonical_name

            # Validate confidence (default to 70 if missing)
            confidence = extraction.get("confidence", 70)
            try:
                confidence = max(0, min(100, int(confidence)))
            except (ValueError, TypeError):
                confidence = 70

            # Validate source_type (default to "implicit" if missing)
            source_type = extraction.get("source_type", "implicit")
            if source_type not in valid_source_types:
                source_type = "implicit"

            # Build validated extraction
            validated_extraction = {
                "category": category,
                "field_name": field_name,
                "field_value": field_value,
                "confidence": confidence,
                "source_type": source_type,
                "source_memory_id": extraction.get("source_memory_id", "unknown"),
                "extracted_at": datetime.now(timezone.utc)
            }

            validated.append(validated_extraction)

        return validated

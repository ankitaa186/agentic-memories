"""
Profile Extraction Service
Extracts profile-worthy information from memories using LLM
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone

from src.models import Memory
from src.services.extract_utils import _call_llm_json

logger = logging.getLogger("agentic_memories.profile_extraction")

# Profile extraction prompt
PROFILE_EXTRACTION_PROMPT = """You are a profile information extractor for a personal memory system.

Analyze the provided memories and extract user profile information. Return a JSON array of profile updates.

**Profile Categories:**
- **basics**: name, age, location, occupation, education, family_status
- **preferences**: communication_style, likes, dislikes, favorites, work_style
- **goals**: short_term, long_term, aspirations, plans, targets
- **interests**: hobbies, topics, activities, passions, learning_areas
- **background**: history, experiences, skills, achievements, education_history

**Extraction Rules:**
1. Only extract if information is clearly stated or strongly implied
2. Assign confidence based on clarity:
   - explicit (user directly states): 90-100%
   - implicit (clearly implied from context): 70-89%
   - inferred (reasonable assumption): 50-69%
3. Do NOT extract:
   - Temporary states (e.g., "I'm tired today")
   - One-time events (use episodic memory instead)
   - Opinions about others (not about the user)
4. Mark source_type:
   - "explicit": User directly stated (e.g., "My name is Alice")
   - "implicit": Clear from context (e.g., "I work as an engineer" → occupation)
   - "inferred": Reasonable assumption (e.g., mentions Python often → interest in programming)
5. **Multi-value handling (IMPORTANT)**:
   - For fields that can have multiple values (languages, hobbies, degrees, skills):
     * Extract EACH instance as a SEPARATE profile update
     * Use the SAME field_name for related items (e.g., all languages use "languages")
     * Use arrays for field_value when there are multiple items
   - Examples:
     * "I speak English and Spanish" → languages: ["English", "Spanish"]
     * "I have a Master's from MIT and Bachelor's from Berkeley" → TWO education_history entries
     * "I enjoy hiking, reading, and cooking" → hobbies: ["hiking", "reading", "cooking"]

**Output Format:**
Return a JSON array of objects with this structure:
{
  "category": "basics" | "preferences" | "goals" | "interests" | "background",
  "field_name": "string (e.g., 'name', 'occupation', 'short_term_goals')",
  "field_value": "any (string, number, list, or object)",
  "confidence": 50-100,
  "source_type": "explicit" | "implicit" | "inferred",
  "source_memory_id": "string (memory ID from input)"
}

**Examples:**

Input: "Hi, I'm Alice and I work as a software engineer in San Francisco."
Output: [
  {
    "category": "basics",
    "field_name": "name",
    "field_value": "Alice",
    "confidence": 100,
    "source_type": "explicit",
    "source_memory_id": "mem_abc123"
  },
  {
    "category": "basics",
    "field_name": "occupation",
    "field_value": "software engineer",
    "confidence": 95,
    "source_type": "explicit",
    "source_memory_id": "mem_abc123"
  },
  {
    "category": "basics",
    "field_name": "location",
    "field_value": "San Francisco",
    "confidence": 90,
    "source_type": "explicit",
    "source_memory_id": "mem_abc123"
  }
]

Input: "I've been coding in Python for 5 years. I really enjoy it."
Output: [
  {
    "category": "interests",
    "field_name": "programming_languages",
    "field_value": ["Python"],
    "confidence": 85,
    "source_type": "implicit",
    "source_memory_id": "mem_def456"
  },
  {
    "category": "background",
    "field_name": "python_experience",
    "field_value": "5 years",
    "confidence": 90,
    "source_type": "explicit",
    "source_memory_id": "mem_def456"
  }
]

Return ONLY the JSON array, or an empty array [] if no profile information is found."""


class ProfileExtractor:
    """Extracts profile information from memories using LLM"""

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

        valid_categories = {'basics', 'preferences', 'goals', 'interests', 'background'}
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

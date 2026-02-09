from __future__ import annotations

from typing import Any, Dict


from langgraph.graph import END, StateGraph

from src.services.prompts_v3 import WORTHINESS_PROMPT_V3, EXTRACTION_PROMPT_V3
from src.schemas import TranscriptRequest
from src.services.extract_utils import _call_llm_json
from src.services.memory_context import (
    get_relevant_existing_memories,
    format_memories_for_llm_context,
)


def build_extraction_graph() -> StateGraph:
    graph = StateGraph(dict)

    def node_worthiness(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        _span = start_span(
            "worthiness_check", input={"history_count": len(state["history"])}
        )

        # Process all messages to capture initial profile information
        payload = {"history": state["history"]}
        resp = _call_llm_json(WORTHINESS_PROMPT_V3, payload)
        state["worthy"] = bool(resp and resp.get("worthy", False))
        state["worthy_raw"] = resp

        end_span(output={"worthy": state["worthy"]})
        return state

    def decide_next(state: Dict[str, Any]) -> str:
        return "extract" if state.get("worthy") else END

    def node_extract(state: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.tracing import start_span, end_span

        # Get existing memories for context
        existing_memories = state.get("existing_memories", [])

        _span = start_span(
            "memory_extraction",
            input={"existing_memories_count": len(existing_memories)},
        )

        existing_context = format_memories_for_llm_context(existing_memories)

        # Process all messages to capture initial profile information
        payload = {
            "history": state["history"],
            "existing_memories_context": existing_context,
        }

        # Enhanced V3 extraction prompt with context (includes emotional/narrative support)
        enhanced_prompt = f"{EXTRACTION_PROMPT_V3}\n\n{existing_context}\n\nBased on the existing memories above, extract only NEW information that adds value."

        items = _call_llm_json(enhanced_prompt, payload, expect_array=True) or []
        state["items"] = items

        end_span(output={"items_extracted": len(items)})
        return state

    graph.add_node("worth", node_worthiness)
    graph.add_node("extract", node_extract)
    graph.set_entry_point("worth")
    graph.add_conditional_edges("worth", decide_next, {"extract": "extract", END: END})
    graph.add_edge("extract", END)
    return graph


def run_extraction_graph(request: TranscriptRequest) -> Dict[str, Any]:
    graph = build_extraction_graph()

    # Get relevant existing memories for context
    existing_memories = get_relevant_existing_memories(request)

    # Initialize state with conversation history and existing memories
    state: Dict[str, Any] = {
        "history": [m.model_dump() for m in request.history],
        "existing_memories": existing_memories,
    }

    result = graph.compile().invoke(state)
    return result

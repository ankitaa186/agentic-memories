#!/usr/bin/env python3
"""
Direct prompt testing script.
Tests extraction prompts directly without running the full pipeline.

Usage:
    python tests/evals/test_prompts_direct.py
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables from .env file
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key not in os.environ:
                    os.environ[key] = value

# Set environment variables if not set
if not os.getenv("OPENAI_API_KEY"):
    print("Error: OPENAI_API_KEY environment variable not set")
    print("Please create a .env file with OPENAI_API_KEY=your_key")
    sys.exit(1)

from src.services.extract_utils import _call_llm_json
from src.services.memory_context import format_memories_for_llm_context
from tests.evals.metrics import score_predictions, format_metrics_report, evaluate_extraction_comprehensive, count_tokens

# Check if we should use V2 prompt (set by run_evals.sh)
if os.getenv("USE_PROMPT_V2"):
    from src.services.prompts_v2 import EXTRACTION_PROMPT_V2 as EXTRACTION_PROMPT
    print("ℹ️  Using EXTRACTION_PROMPT_V2")
else:
    from src.services.prompts import EXTRACTION_PROMPT
    print("ℹ️  Using EXTRACTION_PROMPT (baseline)")

FIXTURE = Path(__file__).parent / "fixtures" / "basic_extraction.jsonl"


def load_test_data():
    """Load test data from fixture file."""
    test_cases = []

    if not FIXTURE.exists():
        print(f"Error: Fixture file not found at {FIXTURE}")
        return []

    with FIXTURE.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                test_cases.append(data)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue

    return test_cases


def test_prompt_extraction(test_case):
    """Test extraction prompt directly on a single test case."""
    user_id = test_case["user_id"]
    history = test_case["history"]
    expected = test_case["gold"]

    # Convert history to dict format for the LLM call
    history_dicts = [{"role": m["role"], "content": m["content"]} for m in history]

    # Optional: existing memories context for dedup/update tests
    existing = test_case.get("existing", [])
    existing_context = "\n".join(existing) if isinstance(existing, list) else (existing or "")

    # Create payload (last 6 messages)
    payload = {
        "history": history_dicts[-6:],
        "existing_memories_context": existing_context
    }

    # Create the prompt that would be used
    prompt = f"{EXTRACTION_PROMPT}\n\nBased on the conversation history, extract memories."

    try:
        # Call LLM directly (this is what node_extract does internally)
        items = _call_llm_json(prompt, payload, expect_array=True) or []

        # Extract predicted memories
        predicted = []
        for item in items:
            if isinstance(item, dict) and "content" in item:
                predicted.append({
                    "content": item.get("content", ""),
                    "type": item.get("type", "explicit"),
                    "layer": item.get("layer", "semantic"),
                    "confidence": item.get("confidence", 0.7),
                    "tags": item.get("tags", [])
                })

        # Estimate token usage
        prompt_text = prompt + "\n\n" + json.dumps(payload)
        completion_text = json.dumps(items) if items else "[]"

        prompt_tokens = count_tokens(prompt_text)
        completion_tokens = count_tokens(completion_text)

        return {
            "user_id": user_id,
            "gold": expected,
            "predicted": predicted,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": "gpt-4"
        }

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {
            "user_id": user_id,
            "gold": expected,
            "predicted": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": "gpt-4",
            "error": str(e)
        }


def main():
    print("=" * 80)
    print("DIRECT PROMPT TESTING")
    print("=" * 80)
    print()

    # Load test data
    print("Loading test data...")
    test_cases = load_test_data()

    if not test_cases:
        print("Error: No test cases loaded. Exiting.")
        return 1

    print(f"✓ Loaded {len(test_cases)} test cases\n")

    # Test each case
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] Testing user_id={test_case['user_id']}...")

        result = test_prompt_extraction(test_case)
        results.append(result)

        if "error" not in result:
            print(f"  ✓ Extracted {len(result['predicted'])} memories (expected {len(test_case['gold'])})")

            # Show what was extracted
            for p in result['predicted'][:2]:  # Show first 2
                print(f"    - [{p['layer']}] {p['content'][:50]}...")
        else:
            print(f"  ✗ Error: {result['error']}")

    print()
    print("=" * 80)
    print("CALCULATING METRICS")
    print("=" * 80)
    print()

    # Calculate metrics
    metrics = evaluate_extraction_comprehensive(results)

    # Print report
    print(format_metrics_report(metrics, "PROMPT EVALUATION RESULTS"))

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    results_file = results_dir / "results_prompt_test.json"
    with results_file.open("w") as f:
        json.dump(results, f, indent=2, default=str)

    metrics_file = results_dir / "metrics_prompt_test.json"
    with metrics_file.open("w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n✓ Saved results to {results_file}")
    print(f"✓ Saved metrics to {metrics_file}")

    # Assessment
    print("\n" + "=" * 80)
    print("ASSESSMENT")
    print("=" * 80)

    if metrics.get("recall", 0) >= 0.6 and metrics.get("precision", 0) >= 0.5:
        print("✅ PASS: Quality metrics meet thresholds")
    else:
        print("⚠️  WARNING: Quality metrics below thresholds")
        if metrics.get("recall", 0) < 0.6:
            print(f"   - Recall: {metrics.get('recall', 0):.3f} (target: >= 0.6)")
        if metrics.get("precision", 0) < 0.5:
            print(f"   - Precision: {metrics.get('precision', 0):.3f} (target: >= 0.5)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

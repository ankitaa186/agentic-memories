#!/usr/bin/env python3
"""
Comprehensive Extraction Evaluation Suite

Tests extraction prompts across 3 test suites:
1. Basic (20 cases) - Original test set
2. Comprehensive (50 cases) - Real-world scenarios  
3. Edge Cases (40 cases) - Challenging/ambiguous inputs

Evaluates:
- Precision, Recall, F1 Score
- Layer and Type Accuracy
- Confidence Calibration
- Token Usage and Cost
- Category-specific Performance
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

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

# Check for required environment variables
if not os.getenv("OPENAI_API_KEY"):
    print("Error: OPENAI_API_KEY environment variable not set")
    print("Please create a .env file with OPENAI_API_KEY=your_key")
    sys.exit(1)

from src.services.extract_utils import _call_llm_json
from tests.evals.metrics import (
    evaluate_extraction_comprehensive,
    format_metrics_report,
    count_tokens
)

# Check if we should use V2 prompt (set by run_evals.sh)
if os.getenv("USE_PROMPT_V2"):
    from src.services.prompts_v2 import EXTRACTION_PROMPT_V2 as EXTRACTION_PROMPT
    print("ℹ️  Using EXTRACTION_PROMPT_V2")
else:
    from src.services.prompts import EXTRACTION_PROMPT
    print("ℹ️  Using EXTRACTION_PROMPT (baseline)")


def load_test_suite(fixture_file: str) -> List[Dict[str, Any]]:
    """Load a test suite from a JSONL fixture file"""
    fixture_path = Path(__file__).parent / "fixtures" / fixture_file
    
    if not fixture_path.exists():
        print(f"⚠️  Fixture not found: {fixture_file}")
        return []
    
    test_cases = []
    with open(fixture_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))
    
    return test_cases


def run_test_suite(
    suite_name: str,
    fixture_file: str,
    prompt: Any
) -> Dict[str, Any]:
    """Run evaluation on a single test suite"""
    
    print(f"\n{'='*80}")
    print(f"📋 Test Suite: {suite_name}")
    print(f"{'='*80}\n")
    
    # Load test cases
    test_cases = load_test_suite(fixture_file)
    
    if not test_cases:
        print(f"❌ No test cases found in {fixture_file}")
        return {"error": "No test cases"}
    
    print(f"✓ Loaded {len(test_cases)} test cases")
    
    # Track results by category if available
    category_results: Dict[str, List[Dict[str, Any]]] = {}
    all_results = []
    
    # Run each test case
    for i, test_case in enumerate(test_cases, 1):
        user_id = test_case.get("user_id", f"test_{i}")
        history = test_case["history"]
        gold_memories = test_case["gold"]
        category = test_case.get("category", "uncategorized")
        
        # Show progress
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(test_cases)} test cases...")
        
        try:
            # Convert history to dict format for the LLM call
            history_dicts = [{"role": m["role"], "content": m["content"]} for m in history]
            
            # Call LLM for extraction (include existing memories if provided)
            existing = test_case.get("existing", [])
            existing_context = "\n".join(existing) if isinstance(existing, list) else (existing or "")
            payload = {
                "history": history_dicts,
                "existing_memories_context": existing_context
            }
            
            items = _call_llm_json(prompt, payload, expect_array=True) or []
            
            # Extract predictions
            predicted = []
            for item in items:
                predicted.append({
                    "content": item.get("content", ""),
                    "type": item.get("type", "explicit"),
                    "layer": item.get("layer", "semantic"),
                    "confidence": item.get("confidence", 0.7),
                    "tags": item.get("tags", [])
                })
            
            # Calculate tokens (same method as test_prompts_direct.py)
            prompt_text = prompt + "\n\n" + json.dumps(payload)
            completion_text = json.dumps(items) if items else "[]"
            
            prompt_tokens = count_tokens(prompt_text)
            completion_tokens = count_tokens(completion_text)
            
            result = {
                "user_id": user_id,
                "category": category,
                "gold": gold_memories,
                "predicted": predicted,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            }
            
            all_results.append(result)
            
            # Track by category
            if category not in category_results:
                category_results[category] = []
            category_results[category].append(result)
            
        except Exception as e:
            print(f"\n❌ Error on test case {i} ({user_id}): {e}")
            # Add empty result to maintain count
            all_results.append({
                "user_id": user_id,
                "category": category,
                "gold": gold_memories,
                "predicted": [],
                "error": str(e),
                "prompt_tokens": 0,
                "completion_tokens": 0
            })
    
    print(f"✓ Completed {len(all_results)} test cases\n")
    
    # Calculate overall metrics
    print("📊 Calculating Metrics...\n")
    overall_metrics = evaluate_extraction_comprehensive(all_results, include_token_metrics=True)
    
    # Calculate category-specific metrics
    category_metrics = {}
    for category, results in category_results.items():
        if len(results) >= 2:  # Only calculate if enough samples
            category_metrics[category] = evaluate_extraction_comprehensive(
                results, 
                include_token_metrics=False
            )
    
    return {
        "suite_name": suite_name,
        "fixture_file": fixture_file,
        "test_count": len(test_cases),
        "overall_metrics": overall_metrics,
        "category_metrics": category_metrics,
        "all_results": all_results
    }


def print_suite_summary(suite_result: Dict[str, Any]) -> None:
    """Print a summary of suite results"""
    metrics = suite_result["overall_metrics"]
    
    print(f"\n{'='*80}")
    print(f"📊 {suite_result['suite_name']} - Results Summary")
    print(f"{'='*80}\n")
    
    print(format_metrics_report(metrics))
    
    # Show top/bottom categories if available
    category_metrics = suite_result.get("category_metrics", {})
    if category_metrics:
        print(f"\n📂 Category Performance (Top 5):\n")
        
        # Sort by F1 score
        sorted_categories = sorted(
            category_metrics.items(),
            key=lambda x: x[1]["quality"]["f1_score"],
            reverse=True
        )
        
        for category, cat_metrics in sorted_categories[:5]:
            f1 = cat_metrics["quality"]["f1_score"]
            precision = cat_metrics["quality"]["precision"]
            recall = cat_metrics["quality"]["recall"]
            print(f"  • {category:30s}  F1: {f1:.3f}  P: {precision:.3f}  R: {recall:.3f}")
        
        if len(sorted_categories) > 5:
            print(f"\n  ... and {len(sorted_categories) - 5} more categories\n")


def compare_suites(suite_results: List[Dict[str, Any]]) -> None:
    """Compare results across suites"""
    print(f"\n{'='*80}")
    print(f"📊 Cross-Suite Comparison")
    print(f"{'='*80}\n")
    
    print(f"{'Suite':<25} {'Tests':>8} {'F1':>8} {'Precision':>10} {'Recall':>8} {'Cost':>10}")
    print(f"{'-'*80}")
    
    for result in suite_results:
        if "error" in result:
            continue
            
        name = result["suite_name"]
        count = result["test_count"]
        metrics = result["overall_metrics"]
        
        f1 = metrics["quality"]["f1_score"]
        precision = metrics["quality"]["precision"]
        recall = metrics["quality"]["recall"]
        cost = metrics.get("tokens", {}).get("total_cost", 0)
        
        print(f"{name:<25} {count:>8} {f1:>8.3f} {precision:>10.3f} {recall:>8.3f} ${cost:>9.4f}")


def main():
    """Run comprehensive evaluation across all test suites"""
    
    print("\n" + "="*80)
    print("🧪 COMPREHENSIVE EXTRACTION EVALUATION")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Prompt: {EXTRACTION_PROMPT[:100]}...\n")
    
    # Define test suites
    suites = [
        {
            "name": "Basic",
            "fixture": "basic_extraction.jsonl",
            "description": "Original 20-case test set (enhanced)"
        },
        {
            "name": "Comprehensive", 
            "fixture": "comprehensive_extraction.jsonl",
            "description": "50 real-world scenarios"
        },
        {
            "name": "Edge Cases",
            "fixture": "edge_cases_extraction.jsonl", 
            "description": "40 challenging inputs"
        },
        {
            "name": "Dedup Existing",
            "fixture": "dedup_existing.jsonl",
            "description": "Existing memories dedup & update handling"
        },
        {
            "name": "Updates & State",
            "fixture": "updates_state.jsonl",
            "description": "Switches, flips, job changes, skill progression"
        },
        {
            "name": "Temporal & Recurring",
            "fixture": "temporal_recurring.jsonl",
            "description": "Recurring events, relative dates, time zones"
        }
    ]
    
    # Run all suites
    all_suite_results = []
    
    for suite in suites:
        print(f"\n{'='*80}")
        print(f"🚀 Starting: {suite['name']} - {suite['description']}")
        print(f"{'='*80}")
        
        try:
            result = run_test_suite(
                suite_name=suite["name"],
                fixture_file=suite["fixture"],
                prompt=EXTRACTION_PROMPT
            )
            
            all_suite_results.append(result)
            print_suite_summary(result)
            
        except Exception as e:
            print(f"\n❌ Suite '{suite['name']}' failed: {e}")
            all_suite_results.append({
                "suite_name": suite["name"],
                "error": str(e)
            })
    
    # Compare all suites
    if len(all_suite_results) > 1:
        compare_suites(all_suite_results)
    
    # Save detailed results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"comprehensive_results_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "prompt_preview": EXTRACTION_PROMPT[:200],
            "suites": all_suite_results
        }, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"💾 Results saved to: {output_file}")
    print(f"{'='*80}\n")
    
    # Final summary
    total_tests = sum(r.get("test_count", 0) for r in all_suite_results)
    avg_f1 = sum(
        r.get("overall_metrics", {}).get("quality", {}).get("f1_score", 0)
        for r in all_suite_results if "error" not in r
    ) / max(1, len([r for r in all_suite_results if "error" not in r]))
    
    print(f"✅ Evaluation Complete!")
    print(f"   • Total Tests: {total_tests}")
    print(f"   • Average F1: {avg_f1:.3f}")
    print(f"   • Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    main()


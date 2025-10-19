from __future__ import annotations

from typing import Dict, List, Tuple, Any

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


def canonicalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def score_predictions(gold_items: List[str], pred_items: List[str]) -> Dict[str, float]:
    """Calculate precision, recall, and F1 score."""
    gold = {canonicalize(x) for x in gold_items}
    pred = {canonicalize(x) for x in pred_items}
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken or fallback estimation."""
    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            pass
    
    # Fallback to rough estimate: ~4 chars per token
    return len(text) // 4


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str = "gpt-4") -> float:
    """Calculate cost in USD based on token usage."""
    # Pricing as of 2024 (adjust as needed)
    pricing = {
        "gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
        "gpt-4-turbo": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
        "gpt-3.5-turbo": {"prompt": 0.0005 / 1000, "completion": 0.0015 / 1000},
    }
    
    rates = pricing.get(model, pricing["gpt-4"])
    prompt_cost = prompt_tokens * rates["prompt"]
    completion_cost = completion_tokens * rates["completion"]
    
    return prompt_cost + completion_cost


def evaluate_extraction_comprehensive(
    results: List[Dict[str, Any]],
    include_token_metrics: bool = True
) -> Dict[str, Any]:
    """
    Comprehensive evaluation of extraction results.
    
    Args:
        results: List of extraction results with:
            - gold: List of expected memories
            - predicted: List of extracted memories
            - prompt_tokens: (optional) Token count for prompt
            - completion_tokens: (optional) Token count for completion
            - model: (optional) Model name
            
    Returns:
        Dict with comprehensive metrics including quality and cost
    """
    all_gold = []
    all_pred = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    
    # Quality metrics per category
    layer_correct = 0
    layer_total = 0
    type_correct = 0
    type_total = 0
    confidence_by_correctness = {"correct": [], "incorrect": []}
    
    for result in results:
        gold = result.get("gold", [])
        predicted = result.get("predicted", [])
        
        # Collect all items for overall metrics
        all_gold.extend([g["content"] for g in gold])
        all_pred.extend([p.get("content", p) if isinstance(p, dict) else p for p in predicted])
        
        # Token metrics
        if include_token_metrics:
            prompt_tokens = result.get("prompt_tokens", 0)
            completion_tokens = result.get("completion_tokens", 0)
            model = result.get("model", "gpt-4")
            
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            total_cost += calculate_cost(prompt_tokens, completion_tokens, model)
        
        # Detailed quality metrics (if structured data available)
        if gold and isinstance(gold[0], dict) and predicted and isinstance(predicted[0], dict):
            for g in gold:
                # Find matching prediction
                g_content = canonicalize(g["content"])
                for p in predicted:
                    if isinstance(p, dict) and canonicalize(p.get("content", "")) == g_content:
                        # Check layer accuracy
                        layer_total += 1
                        if p.get("layer") == g.get("layer"):
                            layer_correct += 1
                        
                        # Check type accuracy
                        type_total += 1
                        if p.get("type") == g.get("type"):
                            type_correct += 1
                        
                        # Confidence calibration
                        confidence = p.get("confidence", 0.0)
                        confidence_by_correctness["correct"].append(confidence)
                        break
            
            # Track incorrect predictions
            pred_contents = {canonicalize(p.get("content", "")) for p in predicted if isinstance(p, dict)}
            gold_contents = {canonicalize(g["content"]) for g in gold}
            for p in predicted:
                if isinstance(p, dict):
                    p_content = canonicalize(p.get("content", ""))
                    if p_content not in gold_contents:
                        confidence = p.get("confidence", 0.0)
                        confidence_by_correctness["incorrect"].append(confidence)
    
    # Calculate overall quality metrics
    quality_metrics = score_predictions(all_gold, all_pred)
    
    # Additional metrics
    metrics = {
        **quality_metrics,
        "total_gold": len(all_gold),
        "total_predicted": len(all_pred),
    }
    
    # Layer and type accuracy
    if layer_total > 0:
        metrics["layer_accuracy"] = layer_correct / layer_total
    if type_total > 0:
        metrics["type_accuracy"] = type_correct / type_total
    
    # Confidence calibration
    if confidence_by_correctness["correct"]:
        metrics["avg_confidence_correct"] = sum(confidence_by_correctness["correct"]) / len(confidence_by_correctness["correct"])
    if confidence_by_correctness["incorrect"]:
        metrics["avg_confidence_incorrect"] = sum(confidence_by_correctness["incorrect"]) / len(confidence_by_correctness["incorrect"])
    
    # Token and cost metrics
    if include_token_metrics:
        metrics["total_prompt_tokens"] = total_prompt_tokens
        metrics["total_completion_tokens"] = total_completion_tokens
        metrics["total_tokens"] = total_prompt_tokens + total_completion_tokens
        metrics["total_cost_usd"] = total_cost
        
        # Per-extraction averages
        num_extractions = len(results)
        if num_extractions > 0:
            metrics["avg_prompt_tokens"] = total_prompt_tokens / num_extractions
            metrics["avg_completion_tokens"] = total_completion_tokens / num_extractions
            metrics["avg_tokens_per_extraction"] = (total_prompt_tokens + total_completion_tokens) / num_extractions
            metrics["cost_per_extraction_usd"] = total_cost / num_extractions
        
        # Per-memory costs
        if len(all_pred) > 0:
            metrics["cost_per_memory_usd"] = total_cost / len(all_pred)
    
    return metrics


def format_metrics_report(metrics: Dict[str, Any], title: str = "Evaluation Metrics") -> str:
    """Format metrics as a readable report."""
    lines = [
        "=" * 80,
        f"{title:^80}",
        "=" * 80,
        "",
        "QUALITY METRICS:",
        f"  Precision:     {metrics.get('precision', 0):.3f}  (% of extracted memories that are correct)",
        f"  Recall:        {metrics.get('recall', 0):.3f}  (% of expected memories that were found)",
        f"  F1 Score:      {metrics.get('f1', 0):.3f}  (Harmonic mean of precision & recall)",
        f"  Total Gold:    {metrics.get('total_gold', 0)}",
        f"  Total Predicted: {metrics.get('total_predicted', 0)}",
        "",
    ]
    
    # Layer and type accuracy
    if "layer_accuracy" in metrics:
        lines.append(f"  Layer Accuracy: {metrics['layer_accuracy']:.3f}  (Correct memory layer classification)")
    if "type_accuracy" in metrics:
        lines.append(f"  Type Accuracy:  {metrics['type_accuracy']:.3f}  (Correct explicit/implicit classification)")
    
    # Confidence calibration
    if "avg_confidence_correct" in metrics:
        lines.append("")
        lines.append("CONFIDENCE CALIBRATION:")
        lines.append(f"  Avg confidence (correct):   {metrics['avg_confidence_correct']:.3f}")
        if "avg_confidence_incorrect" in metrics:
            lines.append(f"  Avg confidence (incorrect): {metrics['avg_confidence_incorrect']:.3f}")
            diff = metrics['avg_confidence_correct'] - metrics['avg_confidence_incorrect']
            lines.append(f"  Calibration gap:            {diff:.3f}  (Higher is better)")
    
    # Token and cost metrics
    if "total_tokens" in metrics:
        lines.append("")
        lines.append("TOKEN & COST METRICS:")
        lines.append(f"  Total Tokens:             {metrics['total_tokens']:,}")
        lines.append(f"    - Prompt tokens:        {metrics['total_prompt_tokens']:,}")
        lines.append(f"    - Completion tokens:    {metrics['total_completion_tokens']:,}")
        lines.append(f"  Avg Tokens per Extraction: {metrics.get('avg_tokens_per_extraction', 0):.0f}")
        lines.append(f"  Total Cost:               ${metrics['total_cost_usd']:.4f}")
        lines.append(f"  Cost per Extraction:      ${metrics.get('cost_per_extraction_usd', 0):.4f}")
        lines.append(f"  Cost per Memory:          ${metrics.get('cost_per_memory_usd', 0):.4f}")
    
    lines.append("")
    lines.append("=" * 80)
    
    return "\n".join(lines)



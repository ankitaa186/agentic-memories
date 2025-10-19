# 🧪 Extraction Prompt Evaluation

Direct testing of extraction prompts to measure quality, accuracy, and cost.

---

## Quick Start

```bash
# From project root
./run_evals.sh
```

The script will:
1. Set up Python environment
2. Ask which test suite you want (Basic or Comprehensive)
3. Ask which prompt to test (Current or V2)
4. Run evaluation and show results

**That's it!**

---

## Test Suites

We have **110 test cases** across **2 test suites**:

| Suite | Cases | Coverage | Runtime |
|-------|-------|----------|---------|
| **Basic** | 20 | Quick validation, common scenarios | ~2 min |
| **Comprehensive** | 110 | All suites: Basic (20) + Real-world (50) + Edge cases (40) | ~10 min |

### Basic Suite (20 cases)
- Simple preferences and habits
- Emotional states and relationships
- Tasks, events, and activities
- Portfolio transactions
- Multi-turn conversations

### Comprehensive Suite (110 cases)
Includes Basic plus:

**Real-world Scenarios (50 cases)**:
- Health: allergies, diet, medical conditions
- Finance: transactions, goals, portfolio allocation
- Work: profession, leadership, projects
- Family: relationships, children, life events
- Skills: languages, technical, learning
- Goals: with progress tracking
- Personality: traits, social preferences
- Location: current, history, travel

**Edge Cases (40 cases)**:
- Empty/non-informative inputs
- Uncertain statements ("maybe", "might")
- Past vs. present distinctions
- Others' opinions vs. user's opinions
- Double negatives and linguistic complexity
- High information density
- Sensitive information (medical, mental health)
- Inference requirements

---

## Metrics

### Quality Metrics
| Metric | Description | Target | Current |
|--------|-------------|--------|---------|
| **Precision** | % of extracted memories that are correct | >0.70 | 0.68 |
| **Recall** | % of gold memories that were extracted | >0.60 | 0.44 ⚠️ |
| **F1 Score** | Harmonic mean of precision and recall | >0.65 | 0.54 |

### Classification Metrics
- **Layer Accuracy**: % correct semantic vs. short-term
- **Type Accuracy**: % correct explicit vs. implicit

### Cost Metrics
- **Cost per Extraction**: Average $ per API call
- **Cost per Memory**: Average $ per extracted memory
- **Tokens Used**: Average tokens per extraction

---

## Understanding Results

### Console Output

```
Quality Metrics:
  Precision: 0.682 (68.2%)
  Recall:    0.441 (44.1%) ⚠️
  F1 Score:  0.536

Classification:
  Layer Accuracy: 0.800 (80.0%)
  Type Accuracy:  0.867 (86.7%)

Cost Analysis:
  Tokens per extraction: 2,215
  Cost per extraction: $0.0686
  Cost per memory: $0.0624
```

### What to Look For

✅ **Good Signs**:
- F1 > 0.65
- Precision > 0.70
- Recall > 0.60
- Cost < $0.10 per extraction

⚠️ **Warning Signs**:
- F1 < 0.60
- Precision < 0.65
- Recall < 0.50
- Cost > $0.15 per extraction

❌ **Critical Issues**:
- F1 < 0.50
- Precision < 0.60
- Recall < 0.40
- Cost > $0.20 per extraction

### Current Issue

**Low Recall (44%)** - We're missing too many memories that should be extracted. The V2 prompt aims to improve this.

---

## Comparing Prompts

To compare two runs:

```bash
# 1. Run baseline
./run_evals.sh
# Select: Comprehensive + Current Prompt
# Note the results filename

# 2. Run improved
./run_evals.sh
# Select: Comprehensive + V2 Prompt
# Note the results filename

# 3. Compare
python tests/evals/compare_results.py \
    tests/evals/results/comprehensive_results_TIMESTAMP1.json \
    tests/evals/results/comprehensive_results_TIMESTAMP2.json
```

The comparison will show:
- Side-by-side metrics
- % changes for each metric
- Per-suite performance
- Overall verdict

---

## Files

```
tests/evals/
├── test_prompts_direct.py          # Basic suite runner
├── test_comprehensive.py           # Comprehensive suite runner
├── compare_results.py              # Compare two result files
├── metrics.py                      # Metric calculations
├── fixtures/
│   ├── sample_extraction.jsonl          # 20 basic test cases
│   ├── comprehensive_extraction.jsonl   # 50 real-world cases
│   └── edge_cases_extraction.jsonl      # 40 edge cases
└── results/                        # Generated results (JSON)
```

---

## Manual Usage

If you prefer to run Python directly:

```bash
# Setup (one-time)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run evaluations
source .venv/bin/activate
python tests/evals/test_prompts_direct.py      # Basic suite
python tests/evals/test_comprehensive.py        # All suites
```

---

## Adding Test Cases

To add new test cases, edit the JSONL files:

```json
{
  "user_id": "test_xxx",
  "history": [
    {"role": "user", "content": "I love Python programming."}
  ],
  "gold": [
    {
      "content": "User loves Python programming.",
      "type": "explicit",
      "layer": "semantic",
      "tags": ["preferences", "programming"]
    }
  ],
  "category": "simple_preference"
}
```

Each test case needs:
- `user_id`: Unique identifier
- `history`: Array of messages
- `gold`: Array of expected memories
- `category`: (optional) Category for grouping

---

## Troubleshooting

### "OPENAI_API_KEY not found"
```bash
# Create .env file in project root
echo "OPENAI_API_KEY=sk-..." > .env
```

### "Virtual environment not found"
```bash
# Recreate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### "Rate limit exceeded"
Wait a few minutes and retry, or run the smaller Basic suite.

---

## Expected Improvements with V2

The V2 prompt is designed to improve:

| Metric | Baseline | V2 Target | Change |
|--------|----------|-----------|--------|
| F1 Score | 0.54 | 0.70 | +30% |
| Recall | 0.44 | 0.65 | +47% ⭐ |
| Precision | 0.68 | 0.75 | +10% |
| Cost | $0.07 | $0.05 | -29% |

**Key improvements**:
- Shorter prompt (40% fewer tokens)
- Examples-first approach
- Clearer extraction criteria
- Better temporal/entity handling

---

## Next Steps

1. **Run baseline**: `./run_evals.sh` → Comprehensive → Current Prompt
2. **Run V2**: `./run_evals.sh` → Comprehensive → V2 Prompt
3. **Compare**: Use `compare_results.py` to see improvements
4. **Deploy**: If V2 shows improvement, update production prompt

---

**Questions?** Check the inline comments in the test scripts or run `./run_evals.sh --help`

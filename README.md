# Email Generation Assistant — AI Engineer Candidate Assessment

A complete evaluation pipeline for an LLM-powered professional email generation assistant.  
Built as part of the SG Services AI Engineer technical assessment.

---

## What This Project Does

This project builds and evaluates an AI assistant that generates professional emails from three inputs:
- **Intent** — the purpose of the email (e.g. "Follow up after interview")
- **Key Facts** — bullet points that must appear in the email
- **Tone** — the desired style (formal, casual, urgent, empathetic, confident)

It then compares **two prompting strategies** using **three custom evaluation metrics**, and produces a structured CSV report with all scores.

---

## Quick Start

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd email_eval
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your API key
```bash
cp .env.example .env
# Edit .env and paste your OpenAI API key
```
Get your key at: https://platform.openai.com/api-keys  
You need to add credit (minimum $5) — there is no free tier on the API.

### 4. Run the pipeline
```bash
python main.py
```

**Expected runtime:** ~3–5 minutes (20 generation calls + 10 judge calls)  
**Expected cost:** under $0.10 total

### 5. View results
```
reports/evaluation_results.csv   — all 20 scored emails with raw metrics
reports/summary.txt              — model comparison table
```

---

## Project Structure

```
email_eval/
├── main.py                  # Pipeline orchestrator (run this)
├── requirements.txt
├── .env.example
├── data/
│   └── scenarios.json       # 10 test cases with reference emails
├── app/
│   ├── prompts.py           # Model A and Model B prompt builders
│   ├── generator.py         # OpenAI API calls for email generation
│   └── evaluator.py         # All 3 custom metrics
└── reports/
    ├── evaluation_results.csv   # Generated after running main.py
    └── summary.txt              # Generated after running main.py
```

---

## Prompting Strategy

### Model A — Basic Prompt (Baseline)
A single user message with the three inputs and a one-line instruction.  
No system role. No examples. Represents the minimum viable prompt.

### Model B — Role + Few-Shot Prompt (Advanced)
- **System Role:** Establishes an expert persona — "senior professional communications specialist, 15 years experience."
- **Two Few-Shot Examples:** Show the model the exact expected output format, length, and tone vocabulary before the real task.
- **Why not Chain-of-Thought?** Email generation is a *structured output task*, not a *reasoning task*. CoT adds tokens and latency with no measurable quality gain. Few-shot examples directly anchor format and tone, which is what this task requires.

---

## Evaluation Metrics

### Metric 1 — Fact Recall Score (Automated)
**Definition:** Percentage of required facts that appear in the generated email.

**Logic:**
1. For each fact, attempt exact substring match (case-insensitive)
2. If no exact match, extract meaningful keywords from the fact and check if ≥50% appear in the email
3. Score = `facts_found / total_facts`

**Range:** 0.0 – 1.0  
**Why:** The most important job of an email assistant is to include what it was told to include. This metric is fast, deterministic, and fully reproducible with no API cost.

---

### Metric 2 — Tone Alignment Score (LLM-as-Judge)
**Definition:** How accurately the generated email matches the requested tone, scored by a stronger judge model.

**Logic:**
1. Send the generated email + requested tone to `gpt-4.1` (judge model)
2. Judge returns an integer score 1–10 against a structured rubric
3. Score normalised to 0.0–1.0 (divide by 10)
4. JSON mode enforced to prevent parsing failures

**Judge model:** `gpt-4.1` (stronger than the generation model `gpt-4.1-mini`, preventing self-serving bias)  
**Range:** 0.0 – 1.0 (raw: 1–10)  
**Why:** Tone is subjective and impossible to measure with regex. LLM-as-Judge achieves ~85% agreement with human raters — the current industry standard for scalable text evaluation.

---

### Metric 3 — Email Structure Score (Automated)
**Definition:** Whether the email contains all three required structural components.

**Components checked:**
- Subject line (line starting with "Subject:")
- Body (≥30 words after the subject line)
- Closing sign-off ("regards", "sincerely", "best", "cheers", etc. in last 5 lines)

**Score:** `components_present / 3`  
**Range:** 0.0 – 1.0  
**Why:** Professional emails have a mandatory structure. This catches the most common generation failure mode (missing subject lines or abrupt endings) cheaply and reliably.

---

### Composite Score
`(Metric 1 + Metric 2 + Metric 3) / 3` — equal weighting across all three metrics.

---

## Models Used

| Role | Model | Why |
|---|---|---|
| Email generation | `gpt-4.1-mini` | Current recommended budget model (April 2025). Replaced gpt-4o-mini. Strong instruction following, ~$0.40/1M input tokens. |
| LLM Judge | `gpt-4.1` | Stronger than the generation model — prevents self-serving bias. |

---

## Test Scenarios

10 scenarios designed to reflect SG Services' actual business domain (recruitment, B2B sales, business communications):

| # | Category | Tone |
|---|---|---|
| 1 | Post-interview follow-up | Professional |
| 2 | Cold B2B outreach | Confident |
| 3 | Candidate rejection | Empathetic |
| 4 | Interview scheduling | Formal |
| 5 | Sales proposal follow-up | Urgent |
| 6 | Job offer letter | Formal |
| 7 | Process delay apology | Empathetic |
| 8 | Reference request | Professional |
| 9 | Webinar invitation | Casual |
| 10 | Partnership meeting request | Confident |

All 5 tones are covered. Each scenario includes 5 required facts and a human-written reference email.

---

## Output Format

`evaluation_results.csv` columns:

| Column | Description |
|---|---|
| scenario_id | 1–10 |
| model_variant | A or B |
| tone | Requested tone |
| metric_1_fact_recall | 0.0–1.0 |
| metric_1_facts_found | Integer |
| metric_2_tone_alignment | 0.0–1.0 |
| metric_2_tone_raw | 1–10 (LLM judge raw score) |
| metric_2_tone_rationale | One-sentence judge explanation |
| metric_3_structure | 0.0–1.0 |
| composite_score | Average of all 3 metrics |
| generated_email | Full generated email text |
| reference_email | Human-written reference email |

---

## Comparative Analysis

See `reports/summary.txt` for the auto-generated comparison after running the pipeline.

The analysis answers:
- Which model/strategy performed better across all 3 metrics?
- What was the biggest failure mode of the lower-performing model?
- Which model is recommended for production and why?

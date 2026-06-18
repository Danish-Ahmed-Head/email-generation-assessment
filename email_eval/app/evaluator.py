"""
evaluator.py
------------
Implements 3 custom metrics for evaluating email quality.

METRIC 1 — Fact Recall Score (Automated)
  Definition: Percentage of required facts that appear in the generated email.
  Logic:
    - For each fact in the scenario, check if its key content appears in the email.
    - Uses two-pass approach:
        Pass 1: Exact substring match (case-insensitive)
        Pass 2: Keyword overlap — extract meaningful words from the fact,
                check if 50%+ of them appear in the email.
    - Score = facts_found / total_facts  →  range 0.0 to 1.0
  Why: The #1 job of an email assistant is to include what it was told to include.
       This is fully deterministic and reproducible with no API cost.

METRIC 2 — Tone Alignment Score (LLM-as-Judge)
  Definition: How accurately the generated email matches the requested tone.
  Logic:
    - Send the generated email + requested tone to gpt-4.1 (stronger judge model).
    - Judge returns a score from 1–10 with a one-sentence rationale.
    - Score is normalised to 0.0–1.0 (divide by 10).
    - Structured output enforced via JSON mode to prevent parsing failures.
  Why: Tone is subjective and cannot be measured by regex. LLM-as-Judge achieves
       ~85% agreement with human raters (Confident AI, 2026) — industry standard.
  Judge model: gpt-4.1 (stronger than the generation model gpt-4.1-mini,
               which is the correct setup to avoid self-serving bias).

METRIC 3 — Email Structure Score (Automated)
  Definition: Whether the email contains all three required structural components.
  Logic:
    - Component 1 (Subject line): email starts with or contains "Subject:"
    - Component 2 (Body): email body has at least 30 words after the subject line
    - Component 3 (Closing): email ends with a recognised sign-off phrase
      (regards, sincerely, best, cheers, kind regards, yours, warm regards, thanks)
    - Score = components_present / 3  →  range 0.0 to 1.0
  Why: Professional emails have a mandatory structure. This is cheap, fast,
       deterministic, and catches the most common generation failure mode
       (missing subject lines or abrupt endings).
"""

import re
import json
import time
from openai import OpenAI
import os

JUDGE_MODEL = "openai/gpt-4.1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Recognised closing phrases — lowercase
CLOSING_PHRASES = [
    "regards",
    "sincerely",
    "best,",
    "cheers",
    "kind regards",
    "yours sincerely",
    "warm regards",
    "thanks",
    "looking forward",
]

# Words to strip when doing keyword overlap matching
STOPWORDS = {
    "is", "a", "an", "the", "and", "or", "of", "to", "in", "for",
    "on", "at", "with", "by", "from", "that", "this", "was", "be",
    "are", "it", "as", "has", "have", "been", "will", "would", "their",
    "our", "we", "he", "she", "they", "his", "her",
}


# ---------------------------------------------------------------------------
# METRIC 1: Fact Recall Score
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> list[str]:
    """Strip stopwords and short tokens from a fact string."""
    words = re.findall(r"[a-z0-9$€£%]+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def score_fact_recall(generated_email: str, facts: list[str]) -> dict:
    """
    Score how many required facts appear in the generated email.

    Returns:
        {
            "score": float (0.0–1.0),
            "facts_found": int,
            "total_facts": int,
            "detail": list of {fact, found, method}
        }
    """
    email_lower = generated_email.lower()
    detail = []
    facts_found = 0

    for fact in facts:
        fact_lower = fact.lower()

        # Pass 1: exact substring match
        if fact_lower in email_lower:
            detail.append({"fact": fact, "found": True, "method": "exact"})
            facts_found += 1
            continue

        # Pass 2: keyword overlap — 50% threshold
        keywords = _extract_keywords(fact_lower)
        if not keywords:
            detail.append({"fact": fact, "found": False, "method": "no_keywords"})
            continue

        matched = sum(1 for kw in keywords if kw in email_lower)
        ratio = matched / len(keywords)

        if ratio >= 0.50:
            detail.append({"fact": fact, "found": True, "method": f"keyword_overlap_{ratio:.0%}"})
            facts_found += 1
        else:
            detail.append({"fact": fact, "found": False, "method": f"keyword_overlap_{ratio:.0%}"})

    score = facts_found / len(facts) if facts else 0.0
    return {
        "score": round(score, 4),
        "facts_found": facts_found,
        "total_facts": len(facts),
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# METRIC 2: Tone Alignment Score (LLM-as-Judge)
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """You are a strict, impartial evaluator of professional email quality.
Your only job is to score how well the tone of a generated email matches the requested tone.

Scoring rubric (1–10):
  10 — Perfect match. Every sentence reflects the requested tone without exception.
   8 — Strong match. Tone is consistent throughout with minor deviations.
   6 — Moderate match. Tone is mostly correct but some sentences feel off.
   4 — Weak match. Only parts of the email reflect the requested tone.
   2 — Poor match. The email largely ignores the requested tone.
   1 — No match. The email tone is the opposite of what was requested.

Tone definitions:
  formal     — structured sentences, no contractions, third-person sign-offs
  professional — polished and clear, slightly warmer than formal
  empathetic — warm, acknowledges feelings, uses phrases that show understanding
  urgent     — direct, time-pressure language, short sentences, clear call-to-action
  confident  — assertive, value-forward, no hedging language
  casual     — conversational, contractions allowed, warm opener

You MUST respond ONLY with a valid JSON object. No preamble. No explanation outside the JSON.
Format:
{"score": <integer 1-10>, "rationale": "<one sentence max 20 words>"}"""


def score_tone_alignment(
    client: OpenAI,
    generated_email: str,
    requested_tone: str,
    retry_attempts: int = 3,
) -> dict:
    """
    Use gpt-4.1 as a judge to score tone alignment.

    Returns:
        {
            "score": float (0.0–1.0),
            "raw_score": int (1–10),
            "rationale": str
        }
    """
    user_message = f"""Requested tone: {requested_tone}

Generated email:
{generated_email}

Score the tone alignment. Respond ONLY with JSON."""

    for attempt in range(retry_attempts):
        try:
            response = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,   # deterministic judge
                max_tokens=100,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            raw_score = int(parsed["score"])
            raw_score = max(1, min(10, raw_score))  # clamp 1–10

            return {
                "score": round(raw_score / 10, 4),
                "raw_score": raw_score,
                "rationale": parsed.get("rationale", ""),
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            if attempt < retry_attempts - 1:
                time.sleep(1)
            else:
                # Fallback: return neutral score rather than crash
                return {
                    "score": 0.5,
                    "raw_score": 5,
                    "rationale": f"Parse error after {retry_attempts} attempts: {e}",
                }
        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg and attempt < retry_attempts - 1:
                wait_time = 2 ** attempt
                print(f"  Judge rate limit, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                return {
                    "score": 0.5,
                    "raw_score": 5,
                    "rationale": f"API error: {e}",
                }


# ---------------------------------------------------------------------------
# METRIC 3: Email Structure Score
# ---------------------------------------------------------------------------

def score_email_structure(generated_email: str) -> dict:
    """
    Check for 3 structural components: subject line, body, closing.

    Returns:
        {
            "score": float (0.0–1.0),
            "components_found": int,
            "detail": {
                "has_subject": bool,
                "has_body": bool,
                "has_closing": bool
            }
        }
    """
    lines = generated_email.strip().splitlines()

    # Component 1: Subject line
    has_subject = any(line.lower().strip().startswith("subject:") for line in lines)

    # Component 2: Body — at least 30 words after the subject line
    body_text = generated_email
    for i, line in enumerate(lines):
        if line.lower().strip().startswith("subject:"):
            body_text = "\n".join(lines[i + 1:])
            break
    body_words = len(re.findall(r"\w+", body_text))
    has_body = body_words >= 30

    # Component 3: Closing sign-off in last 5 lines
    last_lines = "\n".join(lines[-5:]).lower()
    has_closing = any(phrase in last_lines for phrase in CLOSING_PHRASES)

    components_found = sum([has_subject, has_body, has_closing])
    score = components_found / 3

    return {
        "score": round(score, 4),
        "components_found": components_found,
        "detail": {
            "has_subject": has_subject,
            "has_body": has_body,
            "has_closing": has_closing,
        },
    }


# ---------------------------------------------------------------------------
# Run all metrics on a single result
# ---------------------------------------------------------------------------

def evaluate_result(client: OpenAI, result: dict) -> dict:
    """
    Run all 3 metrics on one generation result.
    Returns the result dict enriched with metric scores.
    """
    m1 = score_fact_recall(result["generated_email"], result["facts"])
    m2 = score_tone_alignment(client, result["generated_email"], result["tone"])
    m3 = score_email_structure(result["generated_email"])

    # Composite average
    composite = round((m1["score"] + m2["score"] + m3["score"]) / 3, 4)

    return {
        **result,
        "metric_1_fact_recall": m1["score"],
        "metric_1_facts_found": m1["facts_found"],
        "metric_1_total_facts": m1["total_facts"],
        "metric_2_tone_alignment": m2["score"],
        "metric_2_tone_raw": m2["raw_score"],
        "metric_2_tone_rationale": m2["rationale"],
        "metric_3_structure": m3["score"],
        "metric_3_has_subject": m3["detail"]["has_subject"],
        "metric_3_has_body": m3["detail"]["has_body"],
        "metric_3_has_closing": m3["detail"]["has_closing"],
        "composite_score": composite,
    }


def run_all_evaluations(client: OpenAI, results: list[dict]) -> list[dict]:
    """
    Evaluate all generation results.
    Returns enriched list with all metric scores.
    """
    evaluated = []
    total = len(results)

    for i, result in enumerate(results):
        print(
            f"  [{i+1}/{total}] Evaluating Scenario #{result['scenario_id']} "
            f"| Variant {result['model_variant']}"
        )
        evaluated.append(evaluate_result(client, result))
        time.sleep(0.3)  # small delay for judge API calls

    return evaluated

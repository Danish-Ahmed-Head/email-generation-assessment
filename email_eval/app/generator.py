"""
generator.py
------------
Sends prompts to OpenRouter API and returns generated emails.

Uses gpt-4.1-mini via OpenRouter for generation:
  - OpenRouter is OpenAI SDK-compatible (same Chat Completions interface)
  - Just swap base_url + API key; everything else stays identical
  - Set OPENROUTER_API_KEY in your environment

Temperature set to 0.7:
  - Low enough for consistent structure and fact inclusion
  - High enough to avoid robotic, repetitive phrasing across 10 scenarios
"""

import os
import time
from openai import OpenAI
from app.prompts import build_prompt_a, build_prompt_b

GENERATION_MODEL = "openai/gpt-4.1-mini"   # OpenRouter model slug
TEMPERATURE = 0.7
MAX_TOKENS = 600

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not found. "
            "Set it with: export OPENROUTER_API_KEY='your-key-here'"
        )
    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )


def generate_email(
    client: OpenAI,
    intent: str,
    facts: list[str],
    tone: str,
    model_variant: str,  # "A" or "B"
    retry_attempts: int = 3,
) -> str:
    """
    Generate an email using the specified prompt strategy.
    Retries on rate limit or transient errors.

    Args:
        client: OpenAI client instance (pointed at OpenRouter)
        intent: The purpose of the email
        facts: List of facts that must appear in the email
        tone: Desired tone (formal, casual, empathetic, urgent, confident)
        model_variant: "A" for basic prompt, "B" for role+few-shot
        retry_attempts: Number of retry attempts on failure

    Returns:
        Generated email text as a string
    """
    if model_variant == "A":
        messages = build_prompt_a(intent, facts, tone)
    elif model_variant == "B":
        messages = build_prompt_b(intent, facts, tone)
    else:
        raise ValueError(f"model_variant must be 'A' or 'B', got: {model_variant}")

    for attempt in range(retry_attempts):
        try:
            response = client.chat.completions.create(
                model=GENERATION_MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg and attempt < retry_attempts - 1:
                wait_time = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                print(f"  Rate limit hit, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(
                    f"Generation failed for variant={model_variant}, "
                    f"attempt={attempt + 1}: {e}"
                ) from e

    raise RuntimeError("All retry attempts exhausted")


def run_all_generations(scenarios: list[dict]) -> list[dict]:
    """
    Run both Model A and Model B on all 10 scenarios.
    Returns a flat list of result dicts, one per (scenario, variant) pair.

    Each result dict contains:
        scenario_id, intent, tone, facts, model_variant,
        generated_email, reference_email
    """
    client = get_client()
    results = []
    total = len(scenarios) * 2  # 10 scenarios x 2 variants = 20 calls
    count = 0

    for scenario in scenarios:
        for variant in ["A", "B"]:
            count += 1
            print(
                f"  [{count}/{total}] Scenario #{scenario['id']} "
                f"| Variant {variant} | Tone: {scenario['tone']}"
            )

            email = generate_email(
                client=client,
                intent=scenario["intent"],
                facts=scenario["facts"],
                tone=scenario["tone"],
                model_variant=variant,
            )

            results.append({
                "scenario_id": scenario["id"],
                "intent": scenario["intent"],
                "tone": scenario["tone"],
                "facts": scenario["facts"],
                "model_variant": variant,
                "generated_email": email,
                "reference_email": scenario["reference_email"],
            })

            # Small delay between calls to avoid rate limits
            time.sleep(0.5)

    return results
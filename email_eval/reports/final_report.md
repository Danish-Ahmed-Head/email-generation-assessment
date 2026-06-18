# Final Report — Email Generation Assistant
**Candidate Assessment | SG Services AI Engineer Role**  
*Prepared by: Danish Ahmed*

---

## Section 1 — Prompt Template

### Model A: Basic Prompt (Baseline)

**System message:** *(none)*

**User message:**
```
Write a professional email with the following details:

Intent: {intent}
Tone: {tone}
Key facts to include:
- {fact_1}
- {fact_2}
- {fact_3}
...

Write only the email. Include a subject line.
```

---

### Model B: Role + Few-Shot Prompt (Advanced)

**System message:**
```
You are a senior professional communications specialist with 15 years of experience
writing business emails for recruitment agencies and B2B sales organisations.
You write emails that are clear, concise, and precisely matched to the requested tone.
You always include a subject line. You never use filler phrases like "I hope this 
email finds you well." You include every key fact provided and weave them naturally 
into the email. Your emails have three parts: a clear opening, a focused body, and 
a polite closing with sign-off.
```

**Few-Shot Example 1 (User):**
```
Intent: Confirm a job offer has been accepted
Tone: formal
Key facts to include:
- Candidate name is Elena Vasquez
- Role is Lead Recruiter
- Start date is August 5th
- Salary agreed at $72,000
- Onboarding details will follow separately
```

**Few-Shot Example 1 (Assistant):**
```
Subject: Offer Acceptance Confirmed – Lead Recruiter | Elena Vasquez

Dear Elena,

We are delighted to confirm receipt of your signed offer acceptance for the Lead 
Recruiter position at SG Services Group.

Your agreed terms are as follows:
- Start Date: August 5th
- Annual Salary: $72,000

We will be in touch separately with your full onboarding details ahead of your start 
date. In the meantime, please do not hesitate to reach out if you have any questions.

We look forward to welcoming you to the team.

Yours sincerely,
SG Services Recruitment Team
```

**Few-Shot Example 2 (User):**
```
Intent: Reach out to a prospect who downloaded a whitepaper
Tone: casual
Key facts to include:
- Prospect downloaded the AI Recruiting Playbook
- Company is FreshHire Inc
- Offering a 15-minute intro call
- SG Services specialises in AI recruitment automation
- Can offer a free demo of the platform
```

**Few-Shot Example 2 (Assistant):**
```
Subject: Loved That You Grabbed the Playbook – Quick Chat?

Hi [First Name],

Glad you downloaded the AI Recruiting Playbook! It's one of our most popular 
resources, and it sounds like FreshHire Inc is thinking seriously about where AI 
fits in your hiring stack.

At SG Services, AI recruitment automation is what we do every day. I'd love to 
show you what it looks like in practice — we can do a free demo of the platform 
in just 15 minutes.

Would a quick intro call work for you this week?

Cheers,
SG Services Team
```

**Live task (User):**
```
Intent: {intent}
Tone: {tone}
Key facts to include:
- {fact_1}
...
```

**Why Role + Few-Shot over Chain-of-Thought:**  
Email generation is a structured output task, not a reasoning task. Chain-of-Thought 
prompting is most valuable when a model needs to reason through a problem step by step 
before arriving at an answer (e.g. maths, logic, multi-step planning). For email 
generation, the model already knows how to write emails — it needs to be shown the 
*exact format, length, and tone vocabulary* expected. Few-shot examples achieve this 
directly. Chain-of-Thought would add tokens and latency with no measurable quality 
gain on format-constrained tasks.

---

## Section 2 — Custom Metric Definitions

### Metric 1: Fact Recall Score

**What it measures:** The percentage of required facts that appear in the generated email.

**Logic:**
1. For each required fact (string), perform a case-insensitive substring search of the generated email.
2. If no exact match, extract meaningful keywords from the fact (removing stopwords and short tokens), then check whether ≥50% of those keywords appear in the email body.
3. Final score = `facts_found / total_facts`

**Score range:** 0.0 (no facts included) to 1.0 (all facts included)

**Why this metric:** An email assistant's primary obligation is to include the information it was given. Failure here is a critical failure regardless of how polished the writing sounds. This metric is deterministic, reproducible, and costs nothing to run at scale.

---

### Metric 2: Tone Alignment Score (LLM-as-Judge)

**What it measures:** How accurately the generated email matches the requested tone.

**Logic:**
1. Send the generated email and the requested tone label to `gpt-4.1` (judge model).
2. The judge evaluates against a structured rubric and returns an integer 1–10 plus a one-sentence rationale.
3. Score is normalised: `raw_score / 10`
4. JSON mode is enforced to ensure consistent, parseable output.

**Rubric anchors:**
- 10 = Perfect tone match throughout
- 8 = Strong match with minor deviations
- 6 = Mostly correct, some sentences feel off
- 4 = Weak match, only partial tone adherence
- 1 = Opposite of requested tone

**Score range:** 0.0–1.0 (raw: 1–10)

**Judge model:** `gpt-4.1` (stronger than the generation model to avoid self-serving bias)

**Why this metric:** Tone is a subjective, contextual quality that no regex or keyword list can capture. LLM-as-Judge is now the industry-standard approach for evaluating open-ended text quality, achieving approximately 85% agreement with human raters — higher than inter-human agreement on the same task (Confident AI, 2026).

---

### Metric 3: Email Structure Score

**What it measures:** Whether the email contains the three components required for a complete professional email.

**Components:**
| Component | Detection Logic |
|---|---|
| Subject line | Any line starting with "Subject:" |
| Body | ≥30 words of content after the subject line |
| Closing sign-off | Recognised phrase in last 5 lines ("regards", "sincerely", "best", "cheers", etc.) |

**Score:** `components_present / 3`  
**Score range:** 0.0, 0.33, 0.67, or 1.0

**Why this metric:** Professional email has a mandatory structure. The most common failure mode of prompted email generation is omitting the subject line (when the model "forgets" it's writing an email) or ending abruptly. This metric is cheap, fully automated, and directly actionable — a score of 0.67 tells you exactly which component is missing.

---

## Section 3 — Comparative Analysis

---

### Results Summary

| Metric | Model A (Basic) | Model B (Role+Few-Shot) | Winner |
|---|---|---|---|
| Fact Recall (M1) | 0.98 | 0.98 | Tie |
| Tone Alignment (M2, /10) | 9.20 | 8.60 | A |
| Email Structure (M3) | 0.97 | 1.00 | B |
| **Composite Average** | **0.9556** | **0.9466** | **A** |

*Full raw data: see evaluation_results.csv in the repository.*

---

### Which model/strategy performed better?

Model A (Basic Prompt) achieved a higher composite score (0.9556 vs 0.9466).
The biggest gap was Tone Alignment (9.20 vs 8.60 /10) where Model A won clearly.
Model B won only on Email Structure (1.00 vs 0.97) and tied on Fact Recall (0.98 each).

---

### Biggest failure mode of the lower-performing model (Model A)

**Tone collapse under extreme tone requests.**

Tone over-formality in Model B. The few-shot examples primed the model toward
a formal/professional register. This caused it to underperform on empathetic
and casual scenarios (3, 7, 9) where the judge scored it 8/10 vs Model A's 10/10.

---

### Production recommendation

Model A is recommended for production based on the metric data.

1. Tone Alignment (9.20 vs 8.60): A 0.60 point gap means Model A better matches
   the diverse tones SG Services needs across candidates, clients and prospects.

2. Fact Recall (0.98 vs 0.98): Both models are equal — no advantage either way.

3. Email Structure (0.97 vs 1.00): Model B has a marginal edge but 0.97 is
   production-ready. The one missing component was a closing sign-off in
   Scenario 2 Variant A only.

4. Cost: Identical — same model, different prompt only.

Note: The composite gap is small (0.009). If brand-voice consistency becomes
a priority, Model B's few-shot examples can be updated to cover all 5 tones,
which would likely close the gap and make B the better long-term choice.

---

*End of Report*

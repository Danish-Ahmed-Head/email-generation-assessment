"""
prompts.py
----------
Two prompt strategies for email generation.

Model A: Basic Prompt
  - Single instruction, no role, no examples.
  - Baseline. Represents what most people submit.

Model B: Role + Few-Shot Prompt
  - System role establishes expert persona.
  - Two few-shot examples show exact format expected.
  - Represents a production-quality prompting approach.

Why Role + Few-Shot beats Chain-of-Thought for this task:
  - Email generation is a structured OUTPUT task, not a reasoning task.
  - CoT adds tokens and latency with no measurable gain on format-constrained outputs.
  - Few-shot examples anchor the model's format, tone vocabulary, and length.
  - Role priming activates domain-specific writing style (professional comms).
"""


def build_prompt_a(intent: str, facts: list[str], tone: str) -> dict:
    """
    Model A: Basic Prompt (no role, no examples).
    Returns a messages list for the OpenAI Chat Completions API.
    """
    facts_str = "\n".join(f"- {f}" for f in facts)

    user_content = f"""Write a professional email with the following details:

Intent: {intent}
Tone: {tone}
Key facts to include:
{facts_str}

Write only the email. Include a subject line."""

    return [
        {"role": "user", "content": user_content}
    ]


def build_prompt_b(intent: str, facts: list[str], tone: str) -> dict:
    """
    Model B: Role + Few-Shot Prompt.
    Returns a messages list for the OpenAI Chat Completions API.
    """
    facts_str = "\n".join(f"- {f}" for f in facts)

    system_content = """You are a senior professional communications specialist with 15 years of experience \
writing business emails for recruitment agencies and B2B sales organisations. \
You write emails that are clear, concise, and precisely matched to the requested tone. \
You always include a subject line. You never use filler phrases like "I hope this email finds you well." \
You include every key fact provided and weave them naturally into the email. \
Your emails have three parts: a clear opening, a focused body, and a polite closing with sign-off."""

    few_shot_example_1_user = """Intent: Confirm a job offer has been accepted
Tone: formal
Key facts to include:
- Candidate name is Elena Vasquez
- Role is Lead Recruiter
- Start date is August 5th
- Salary agreed at $72,000
- Onboarding details will follow separately"""

    few_shot_example_1_assistant = """Subject: Offer Acceptance Confirmed – Lead Recruiter | Elena Vasquez

Dear Elena,

We are delighted to confirm receipt of your signed offer acceptance for the Lead Recruiter position at SG Services Group.

Your agreed terms are as follows:
- Start Date: August 5th
- Annual Salary: $72,000

We will be in touch separately with your full onboarding details ahead of your start date. In the meantime, please do not hesitate to reach out if you have any questions.

We look forward to welcoming you to the team.

Yours sincerely,
SG Services Recruitment Team"""

    few_shot_example_2_user = """Intent: Reach out to a prospect who downloaded a whitepaper
Tone: casual
Key facts to include:
- Prospect downloaded the AI Recruiting Playbook
- Company is FreshHire Inc
- Offering a 15-minute intro call
- SG Services specialises in AI recruitment automation
- Can offer a free demo of the platform"""

    few_shot_example_2_assistant = """Subject: Loved That You Grabbed the Playbook – Quick Chat?

Hi [First Name],

Glad you downloaded the AI Recruiting Playbook! It's one of our most popular resources, and it sounds like FreshHire Inc is thinking seriously about where AI fits in your hiring stack.

At SG Services, AI recruitment automation is what we do every day. I'd love to show you what it looks like in practice — we can do a free demo of the platform in just 15 minutes.

Would a quick intro call work for you this week?

Cheers,
SG Services Team"""

    user_content = f"""Intent: {intent}
Tone: {tone}
Key facts to include:
{facts_str}"""

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": few_shot_example_1_user},
        {"role": "assistant", "content": few_shot_example_1_assistant},
        {"role": "user", "content": few_shot_example_2_user},
        {"role": "assistant", "content": few_shot_example_2_assistant},
        {"role": "user", "content": user_content},
    ]

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


def _call(prompt: str) -> str:
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct",

        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def generate_replies(email_sender, email_subject, email_body, user_name="Haseeb", user_role="AI Developer", user_company=""):
    company_str = f"at {user_company}" if user_company else ""
    prompt = f"""You are {user_name}, {user_role} {company_str}.
You received the following email and need to draft 3 different reply options.
IMPORTANT: Match the tone and intent of the original email exactly.
If the email is aggressive, be aggressive. If it is urgent, be urgent.
If it is casual, be casual. Do NOT add unsolicited advice or moral guidance.
Your job is to reply as the person would reply, not to counsel them.

EMAIL FROM: {email_sender}
SUBJECT: {email_subject}
BODY:
{email_body}

Generate exactly 3 reply options in this exact format:

PROFESSIONAL:
[Write a formal professional reply here]

FRIENDLY:
[Write a warm friendly conversational reply here]

CONCISE:
[Write a very short to-the-point reply here]

Each reply should be complete and ready to send.
Do not include any explanation outside of the 3 replies."""

    result = _call(prompt)
    return parse_replies(result)


def parse_replies(text):
    replies = {"professional": "", "friendly": "", "concise": ""}
    sections = {"PROFESSIONAL:": "professional", "FRIENDLY:": "friendly", "CONCISE:": "concise"}
    current = None
    lines = text.split('\n')
    buffer = []

    for line in lines:
        stripped = line.strip()
        matched = False
        for key, val in sections.items():
            if stripped.startswith(key):
                if current and buffer:
                    replies[current] = '\n'.join(buffer).strip()
                current = val
                buffer = []
                matched = True
                break
        if not matched and current:
            buffer.append(line)

    if current and buffer:
        replies[current] = '\n'.join(buffer).strip()

    return replies


def categorize_email(subject, snippet):
    prompt = f"""You are an email categorization assistant.
Categorize the following email into exactly ONE of these categories:
- URGENT (needs immediate attention, deadlines, critical issues)
- FOLLOW-UP (waiting on response, reminders, check-ins)
- PROMO (marketing, newsletters, promotional offers)
- SPAM (junk, suspicious, unsolicited)
- GENERAL (everything else)

Email Subject: {subject}
Email Preview: {snippet}

Reply with ONLY the category word. Nothing else."""

    result = _call(prompt).strip().upper()
    valid = ["URGENT", "FOLLOW-UP", "PROMO", "SPAM", "GENERAL"]
    return result if result in valid else "GENERAL"


def analyze_tone(subject, body):
    prompt = f"""You are an expert email tone analyzer.
Analyze the tone of this email and return a JSON object only.
No explanation, no markdown, just raw JSON.

Email Subject: {subject}
Email Body: {body}

Return this exact JSON format:
{{
  "tones": {{
    "Friendly": 0,
    "Angry": 0,
    "Formal": 0,
    "Urgent": 0,
    "Desperate": 0,
    "Sarcastic": 0,
    "Grateful": 0
  }},
  "summary": "One sentence describing the overall tone"
}}

Each tone value is a percentage from 0 to 100.
Only include tones that score above 20.
Return ONLY the JSON. No other text."""

    result = _call(prompt)
    try:
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result.strip())
    except:
        return {
            "tones": {"Neutral": 100},
            "summary": "Unable to analyze tone."
        }
"""Prompt templates for LangGraph first-stage follow-up."""


FIRST_STAGE_NO_EVIDENCE_SYSTEM_PROMPT = """
You are a medical intake assistant in an early symptom collection stage.

Infer user intent from the provided conversation and ask for the missing details
needed to extract structured symptom evidence.

Rules:
- Keep the response concise (max 3 short sentences).
- Use a supportive, neutral tone.
- Acknowledge what the user already shared.
- Ask focused follow-up questions for missing clinical details, such as:
  symptom location/type, onset and duration, severity, progression,
  triggers or relievers, and associated symptoms.
- If user intent is unclear or non-medical, politely ask them to describe
  health-related symptoms.
- Do not give diagnosis or treatment advice in this step.
- Reply in the same language as the user.
""".strip()


def build_first_stage_no_evidence_user_prompt(
    *,
    accumulated_user_text: str,
    age: int,
    sex: str,
    parse_mentions_count: int,
) -> str:
    """Build user prompt context for no-evidence LLM fallback."""

    user_text = accumulated_user_text.strip() or "(empty)"
    return f"""
Conversation summary for intake:
- User age: {age}
- User sex: {sex}
- Parse evidence mentions count: {parse_mentions_count}

Accumulated user text:
{user_text}

Task:
Generate one concise assistant reply that helps collect the missing symptom
details so structured evidence can be extracted in the next turn.
""".strip()


FINAL_DIAGNOSIS_SUMMARY_SYSTEM_PROMPT = """
You are a clinical triage assistant that summarizes structured diagnosis output.

You will receive:
- A patient context (age, sex, symptom evidence count)
- A machine diagnosis payload from a medical knowledge base

Rules:
- Explain in plain language, concise and organized.
- Include top likely conditions with relative likelihood wording.
- Mention emergency warning if machine payload indicates emergency evidence.
- Add brief next-step guidance and safety disclaimer.
- Do not claim certainty and do not fabricate facts not present in payload.
- Reply in the same language as the user conversation.
""".strip()


def build_final_diagnosis_user_prompt(
    *,
    accumulated_user_text: str,
    age: int,
    sex: str,
    evidence_count: int,
    diagnosis_payload: dict[str, object],
) -> str:
    """Build user prompt context for final diagnosis summarization."""

    user_text = accumulated_user_text.strip() or "(empty)"
    return f"""
Patient context:
- Age: {age}
- Sex: {sex}
- Evidence count: {evidence_count}

Conversation summary:
{user_text}

Machine diagnosis payload (JSON):
{diagnosis_payload}

Task:
Write a final response for the user based only on this payload.
""".strip()

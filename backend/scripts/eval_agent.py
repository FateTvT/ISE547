"""Run evaluation cases with async concurrency."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "app" / "core" / "prompts"
DATA_PATH = Path("data/updated_result_with_BERT_eval_120_cleaned_cleaned.csv")
TARGET_COLUMN = "Diagnosis Category"
FEATURE_COLUMNS = [
    "age",
    "gender_numeric",
    "symptoms",
    "Patient History",
    "Remarks",
    "treatment",
    "timespan",
    "Diagnosis",
]

ALLOWED_CATEGORY_CHOICES = [
    "Bone-related disorders",
    "Hip-related disorders",
    "Musculoskeletal disorders",
    "Other",
    "Spinal disorders",
]

ALLOWED_DIAGNOSIS_CHOICES = [
    "Avascular Necrosis",
    "Clinical & Rehab Ops",
    "Fractures",
    "Inflammatory & Other Joint",
    "Osteoarthritis",
    "Osteoporosis",
    "Spinal Disorders",
    "Technical & Eng Tasks",
    "cervical spine injury prediction",
    "lumbar spine mri interpretation",
    "prolonged opioid prescription",
    "spine level identification using uss",
    "x-ray diagnosis",
]
LLM_PROMPT_TEMPLATE = """
{prompt_content}

Hard constraints:
- Category MUST be selected from this list only: {allowed_categories}
- Top-1/Top-2/Top-3 Diagnosis MUST each be selected from this list only: {allowed_diagnoses}
- Do not output values outside these two lists.

Auxiliary context from diagnosis interface:
Diagnosis Interface Result (JSON): {diagnosis_result}
""".strip()

PROMPT_FILE_MAP = {
    "p1": "P1_Direct.txt",
    "p2": "P2_Structured.txt",
    "p3": "P3_Conservative.txt",
    "p4": "P4_CategoryFirst.txt",
}


def load_prompt_content(prompt_key: str) -> str:
    prompt_filename = PROMPT_FILE_MAP[prompt_key]
    prompt_path = PROMPTS_DIR / prompt_filename
    return prompt_path.read_text(encoding="utf-8").strip()


def render_prompt_content(prompt_template: str, template_vars: dict[str, str]) -> str:
    rendered = prompt_template
    for key, value in template_vars.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _ensure_backend_on_path() -> Path:
    if (BACKEND_DIR / "app").exists():
        candidate_str = str(BACKEND_DIR)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
        return BACKEND_DIR
    raise ModuleNotFoundError("Cannot locate backend root containing app package.")


_ensure_backend_on_path()

from app.core.config import settings  # noqa: E402

INFERMEDICA_BASE_URL = settings.INFERMEDICA_BASE_URL
INFERMEDICA_APP_ID = settings.INFERMEDICA_APP_ID
INFERMEDICA_APP_KEY = settings.INFERMEDICA_APP_KEY
INFERMEDICA_LANGUAGE = settings.INFERMEDICA_LANGUAGE
PARSE_PATH = "/parse"
DIAGNOSIS_PATH = "/diagnosis"

OPENROUTER_BASE_URL = settings.OPENROUTER_BASE_URL
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
DEFAULT_CHAT_MODEL = settings.DEFAULT_CHAT_MODEL


def gender_numeric_to_sex(gender_numeric: int) -> str:
    if int(gender_numeric) == 0:
        return "male"
    if int(gender_numeric) == 1:
        return "female"
    return "other"


def build_parse_text(age: int, symptoms: str, patient_history: str) -> str:
    return (
        f"Patient age: {age}. "
        f"Symptoms: {symptoms}. "
        f"Patient history: {patient_history}."
    )


def infermedica_headers() -> dict[str, str]:
    return {
        "App-Id": INFERMEDICA_APP_ID,
        "App-Key": INFERMEDICA_APP_KEY,
        "Accept-Language": INFERMEDICA_LANGUAGE,
        "Content-Type": "application/json",
    }


async def call_parse(
    client: httpx.AsyncClient,
    *,
    text: str,
    age: int,
    sex: str,
) -> dict[str, Any]:
    payload = {
        "text": text,
        "age": {"value": int(age)},
        "sex": sex,
    }
    response = await client.post(
        f"{INFERMEDICA_BASE_URL.rstrip('/')}{PARSE_PATH}",
        headers=infermedica_headers(),
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def parse_mentions_to_evidence(parse_result: dict[str, Any]) -> list[dict[str, str]]:
    mentions = parse_result.get("mentions", []) or []
    evidence: list[dict[str, str]] = []
    for mention in mentions:
        mention_id = str(mention.get("id", "")).strip()
        choice_id = str(mention.get("choice_id", "")).strip()
        if mention_id and choice_id:
            evidence.append({"id": mention_id, "choice_id": choice_id})
    return evidence


async def call_diagnosis(
    client: httpx.AsyncClient,
    *,
    age: int,
    sex: str,
    evidence: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "sex": sex,
        "age": {"value": int(age)},
        "evidence": evidence,
    }
    response = await client.post(
        f"{INFERMEDICA_BASE_URL.rstrip('/')}{DIAGNOSIS_PATH}",
        headers=infermedica_headers(),
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def build_llm_user_prompt(
    *,
    prompt_content: str,
    age: int,
    gender: str,
    symptoms: str,
    patient_history: str,
    diagnosis_payload: dict[str, Any],
) -> str:
    template_vars = {
        "age": str(age),
        "gender": str(gender),
        "patient_history": str(patient_history),
        "symptoms": str(symptoms),
        "diagnosis_result": json.dumps(diagnosis_payload, ensure_ascii=False),
        "allowed_categories": "; ".join(ALLOWED_CATEGORY_CHOICES),
        "allowed_diagnoses": "; ".join(ALLOWED_DIAGNOSIS_CHOICES),
    }
    rendered_prompt_content = render_prompt_content(prompt_content, template_vars)

    return LLM_PROMPT_TEMPLATE.format(
        prompt_content=rendered_prompt_content,
        diagnosis_result=template_vars["diagnosis_result"],
        allowed_categories=template_vars["allowed_categories"],
        allowed_diagnoses=template_vars["allowed_diagnoses"],
    )


def create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=DEFAULT_CHAT_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0.2,
    )


def _extract_field(text: str, field_name: str) -> str:
    pattern = re.compile(rf"(?im)^\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$")
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def _first_two_sentences(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    sentence_pattern = re.compile(r"[^.!?]+[.!?]?")
    sentences = [s.strip() for s in sentence_pattern.findall(cleaned) if s.strip()]
    if not sentences:
        return cleaned
    return " ".join(sentences[:2]).strip()


def _extract_json_object_text(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""

    brace_count = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            brace_count += 1
            continue
        if char == "}":
            brace_count -= 1
            if brace_count == 0:
                return text[start : idx + 1]
    return ""


def _parse_llm_json(raw_output: str) -> dict[str, Any]:
    stripped = raw_output.strip()
    if stripped.startswith("```"):
        fence_match = re.search(
            r"(?is)^```(?:json)?\s*(.*?)\s*```$",
            stripped,
        )
        if fence_match:
            stripped = fence_match.group(1).strip()

    for candidate in (stripped, _extract_json_object_text(stripped)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {}


def _json_value_as_text(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _conditions_from_diagnosis(
    diagnosis_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    conditions = diagnosis_payload.get("conditions", [])
    if not isinstance(conditions, list):
        return []
    return [item for item in conditions if isinstance(item, dict)]


def _normalize_choice_text(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _pick_allowed_value(value: str, allowed_values: list[str]) -> str:
    normalized_to_original = {
        _normalize_choice_text(item): item for item in allowed_values
    }
    return normalized_to_original.get(_normalize_choice_text(value), "")


def format_triage_output(raw_output: str, diagnosis_payload: dict[str, Any]) -> str:
    conditions = _conditions_from_diagnosis(diagnosis_payload)
    parsed_json = _parse_llm_json(raw_output)

    if parsed_json:
        category = _json_value_as_text(parsed_json, ["category", "Category"])
        top1 = _json_value_as_text(
            parsed_json,
            ["diagnosis_top1", "top1", "Top-1 Diagnosis"],
        )
        top2 = _json_value_as_text(
            parsed_json,
            ["diagnosis_top2", "top2", "Top-2 Diagnosis"],
        )
        top3 = _json_value_as_text(
            parsed_json,
            ["diagnosis_top3", "top3", "Top-3 Diagnosis"],
        )
        brief_reason = _json_value_as_text(
            parsed_json,
            ["brief_reason", "Brief Reason"],
        )
    else:
        category = _extract_field(raw_output, "Category")
        top1 = _extract_field(raw_output, "Top-1 Diagnosis")
        top2 = _extract_field(raw_output, "Top-2 Diagnosis")
        top3 = _extract_field(raw_output, "Top-3 Diagnosis")
        brief_reason = _extract_field(raw_output, "Brief Reason")

    condition_names = [
        str(item.get("name", "")).strip()
        for item in conditions
        if str(item.get("name", "")).strip()
    ]
    allowed_condition_names = [
        mapped
        for mapped in (
            _pick_allowed_value(name, ALLOWED_DIAGNOSIS_CHOICES)
            for name in condition_names
        )
        if mapped
    ]
    top_fallbacks = (allowed_condition_names + condition_names + ["", "", ""])[:3]

    if not category:
        first_category = ""
        if conditions:
            category_info = conditions[0].get("category")
            if isinstance(category_info, dict):
                first_category = str(category_info.get("name", "")).strip()
        category = first_category

    mapped_category = _pick_allowed_value(category, ALLOWED_CATEGORY_CHOICES)
    category = mapped_category or category or "Unknown"

    top1 = (
        _pick_allowed_value(top1, ALLOWED_DIAGNOSIS_CHOICES) or top1 or top_fallbacks[0]
    )
    top2 = (
        _pick_allowed_value(top2, ALLOWED_DIAGNOSIS_CHOICES) or top2 or top_fallbacks[1]
    )
    top3 = (
        _pick_allowed_value(top3, ALLOWED_DIAGNOSIS_CHOICES) or top3 or top_fallbacks[2]
    )
    top1 = top1 or "Unknown"
    top2 = top2 or "Unknown"
    top3 = top3 or "Unknown"

    brief_reason = _first_two_sentences(brief_reason)
    if not brief_reason:
        brief_reason = (
            "Initial triage is inferred from the provided symptoms and history, "
            "with diagnostic interface output as supporting context."
        )

    return (
        f"Category: {category}\n"
        f"Top-1 Diagnosis: {top1}\n"
        f"Top-2 Diagnosis: {top2}\n"
        f"Top-3 Diagnosis: {top3}\n"
        f"Brief Reason: {brief_reason}"
    )


async def run_llm_diagnosis(
    llm: ChatOpenAI,
    *,
    prompt_content: str,
    age: int,
    gender: str,
    symptoms: str,
    patient_history: str,
    diagnosis_payload: dict[str, Any],
) -> str:
    user_prompt = build_llm_user_prompt(
        prompt_content=prompt_content,
        age=age,
        gender=gender,
        symptoms=symptoms,
        patient_history=patient_history,
        diagnosis_payload=diagnosis_payload,
    )
    messages = [
        SystemMessage(content="Follow the user prompt exactly."),
        HumanMessage(content=user_prompt),
    ]
    response = await llm.ainvoke(messages)
    return str(response.content).strip()


async def process_row(
    row_idx: int,
    row: pd.Series,
    *,
    client: httpx.AsyncClient,
    llm: ChatOpenAI,
    semaphore: asyncio.Semaphore,
    prompt_content: str,
    prompt_id: str,
    run_mode: str,
) -> dict[str, Any]:
    async with semaphore:
        age = int(row["age"])
        symptoms = str(row["symptoms"])
        patient_history = str(row["Patient History"])
        sex = gender_numeric_to_sex(int(row["gender_numeric"]))
        gold_category = str(row[TARGET_COLUMN])
        gold_diagnosis = str(row["Diagnosis"])

        try:
            input_text = build_parse_text(
                age=age,
                symptoms=symptoms,
                patient_history=patient_history,
            )

            parse_result = await call_parse(
                client,
                text=input_text,
                age=age,
                sex=sex,
            )
            evidence = parse_mentions_to_evidence(parse_result)

            diagnosis_result = await call_diagnosis(
                client,
                age=age,
                sex=sex,
                evidence=evidence,
            )

            llm_final_output = await run_llm_diagnosis(
                llm,
                prompt_content=prompt_content,
                age=age,
                gender=sex,
                symptoms=symptoms,
                patient_history=patient_history,
                diagnosis_payload=diagnosis_result,
            )
            llm_final_output = format_triage_output(llm_final_output, diagnosis_result)

            print(
                f"row={row_idx} done, mentions={len(evidence)}, "
                f"llm_len={len(llm_final_output)}"
            )
            error = ""
            raw_output = llm_final_output
        except Exception as exc:  # noqa: BLE001
            print(f"row={row_idx} failed: {exc}")
            error = str(exc)
            raw_output = ""

        return {
            "case_id": row_idx,
            "system_type": "llm_triage",
            "system_name": DEFAULT_CHAT_MODEL,
            "prompt_id": prompt_id,
            "run_mode": run_mode,
            "raw_output": raw_output,
            "gold_category": gold_category,
            "gold_diagnosis": gold_diagnosis,
            "age": age,
            "gender": sex,
            "patient_history": patient_history,
            "symptoms": symptoms,
            "error": error,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate diagnosis flow in batch.")
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="How many rows from the dataset to run.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max number of concurrent cases.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DATA_PATH,
        help="Input CSV path.",
    )
    parser.add_argument(
        "--p",
        type=str,
        choices=tuple(PROMPT_FILE_MAP.keys()),
        default="p2",
        help="Prompt profile: p1, p2, p3, or p4.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Default: data/eval_agent_{p}_top{top_n}_results.csv",
    )
    return parser.parse_args()


def _resolve_script_relative_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


async def run() -> None:
    args = parse_args()
    if args.top_n <= 0:
        raise ValueError("--top-n must be a positive integer.")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be a positive integer.")

    input_path = _resolve_script_relative_path(args.input)
    df = pd.read_csv(input_path)
    sample_df = df[FEATURE_COLUMNS + [TARGET_COLUMN]].head(args.top_n).copy()
    prompt_content = load_prompt_content(args.p)
    llm = create_llm()
    semaphore = asyncio.Semaphore(args.concurrency)
    prompt_id = f"medical_triage_{args.p}"
    run_mode = f"top_n={args.top_n};concurrency={args.concurrency};p={args.p}"

    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            process_row(
                int(row_idx),
                row,
                client=client,
                llm=llm,
                semaphore=semaphore,
                prompt_content=prompt_content,
                prompt_id=prompt_id,
                run_mode=run_mode,
            )
            for row_idx, row in sample_df.iterrows()
        ]
        rows = await asyncio.gather(*tasks)

    rows.sort(key=lambda item: int(item["case_id"]))
    results_df = pd.DataFrame(rows)
    results_df = results_df[
        [
            "case_id",
            "system_type",
            "system_name",
            "prompt_id",
            "run_mode",
            "raw_output",
            "gold_category",
            "gold_diagnosis",
            "age",
            "gender",
            "patient_history",
            "symptoms",
            "error",
        ]
    ]

    output_rel_path = args.output or Path(
        f"data/eval_agent_{args.p}_top{args.top_n}_results.csv"
    )
    output_path = _resolve_script_relative_path(output_rel_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved: {output_path.resolve()}")
    print(f"Rows: {len(results_df)}")


if __name__ == "__main__":
    asyncio.run(run())

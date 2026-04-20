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
DATA_PATH = Path("data/updated_result_with_BERT_eval_120.csv")
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

POSSIBLE_DIAGNOSIS = [
    "Avascular Necrosis of Bilateral Hips",
    "Avascular Necrosis of the Left Hip",
    "Avascular Necrosis of the Right Hip",
    "Bone Marrow Edema Syndrome of Bilateral Hips",
    "Bone Marrow Edema Syndrome of the Left Hip",
    "Bone Marrow Edema Syndrome of the right Hip",
    "acetabular fracture",
    "acetabular fracture / femur fracture",
    "acl rehab evaluation",
    "adverse events post spine surgery",
    "arthritic hip",
    "back pain diagnosis using decision support system",
    "back pain diagnosis using pain drawings",
    "back pain triage from pain drawing",
    "cobb angle estimation",
    "discharge destination",
    "discharge destination post surgery",
    "implant design optimisation",
    "intraoperative somatosensory evoked potential monitoring",
    "neck of femur fracture",
    "osteoarthritis",
    "osteoarthritis  rt.",
    "osteoarthritis diagnosis & severity",
    "osteoarthritis diagnosis with infrared",
    "osteolysis",
    "osteoporosis diagnosis from dexa",
    "osteoporotic fractures",
    "predicting cost of spinal fusion",
    "predicting osteoporosis from qct",
    "recovery post arthroplasty",
    "rheumatoid arthritis",
    "risk of hip fracture prediction",
    "rotator cuff strength",
    "scoliosis diagnosis by gait analysis",
    "spinal cord injury diagnosis from skin impedence",
    "spinal cord injury from diffusion tensor imaging",
    "spinal stenosis grading",
    "spinal tumors",
    "trochanter fracture",
]
LLM_PROMPT_TEMPLATE = """
You are a medical triage assistant for an academic evaluation project.

Your task is to read the user's symptom description and provide an initial triage-oriented response.
This is NOT a real medical diagnosis and you must not claim certainty.

Based only on the information provided, return:
1) the single most appropriate diagnosis category,
2) the three most likely candidate diagnoses ranked from most likely to less likely.

You must always provide an answer even if the information is incomplete.

Keep your answer concise and structured exactly in this format:

Category: <one diagnosis category>
Top-1 Diagnosis: <one diagnosis>
Top-2 Diagnosis: <one diagnosis>
Top-3 Diagnosis: <one diagnosis>
Brief Reason: <1-2 sentences>

Output rules:
- Return plain text only.
- Exactly 5 lines, in the exact order above.
- Do not add bullets, markdown, code blocks, or extra notes.
- Each line must start with the exact field name shown above.

User information:
Age: {age}
Gender: {gender}
Patient History: {patient_history}
Symptoms: {symptoms}
Diagnosis Interface Result (JSON): {diagnosis_result}
""".strip()


def _ensure_backend_on_path() -> Path:
    candidates = [
        BACKEND_DIR,
    ]
    for candidate in candidates:
        if (candidate / "app").exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return candidate
    raise ModuleNotFoundError("Cannot locate backend root containing app package.")


BACKEND_ROOT = _ensure_backend_on_path()

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
    age: int,
    gender: str,
    symptoms: str,
    patient_history: str,
    diagnosis_payload: dict[str, Any],
) -> str:
    return LLM_PROMPT_TEMPLATE.format(
        age=age,
        gender=gender,
        patient_history=patient_history,
        symptoms=symptoms,
        diagnosis_result=json.dumps(diagnosis_payload, ensure_ascii=False),
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


def _conditions_from_diagnosis(
    diagnosis_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    conditions = diagnosis_payload.get("conditions", [])
    if not isinstance(conditions, list):
        return []
    return [item for item in conditions if isinstance(item, dict)]


def format_triage_output(raw_output: str, diagnosis_payload: dict[str, Any]) -> str:
    conditions = _conditions_from_diagnosis(diagnosis_payload)

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
    top_fallbacks = (condition_names + ["Unknown", "Unknown", "Unknown"])[:3]

    if not category:
        first_category = ""
        if conditions:
            category_info = conditions[0].get("category")
            if isinstance(category_info, dict):
                first_category = str(category_info.get("name", "")).strip()
        category = first_category or "Unknown"

    top1 = top1 or top_fallbacks[0]
    top2 = top2 or top_fallbacks[1]
    top3 = top3 or top_fallbacks[2]

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
    age: int,
    gender: str,
    symptoms: str,
    patient_history: str,
    diagnosis_payload: dict[str, Any],
) -> str:
    user_prompt = build_llm_user_prompt(
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
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Default: data/eval_agent_top{top_n}_results.csv",
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
    llm = create_llm()
    semaphore = asyncio.Semaphore(args.concurrency)
    prompt_id = "medical_triage_v1"
    run_mode = f"top_n={args.top_n};concurrency={args.concurrency}"

    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            process_row(
                int(row_idx),
                row,
                client=client,
                llm=llm,
                semaphore=semaphore,
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
        f"data/eval_agent_top{args.top_n}_results.csv"
    )
    output_path = _resolve_script_relative_path(output_rel_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved: {output_path.resolve()}")
    print(f"Rows: {len(results_df)}")


if __name__ == "__main__":
    asyncio.run(run())

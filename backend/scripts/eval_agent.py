"""Run evaluation cases with async concurrency."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

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

LLM_SYSTEM_PROMPT = """
You are a clinical triage assistant.

You will receive:
1) Basic patient information (age)
2) Patient symptoms and medical history text (symptoms + Patient History)
3) Output from a structured diagnostic interface (/diagnosis output JSON)

Please output:
- A concise, structured diagnostic conclusion;
- 1-3 most likely disease directions, highlighting the supporting rationale for each;
- Clear risk warnings (e.g., emergency "red flag" signals);
- Recommended next steps;
- A mandatory disclaimer stating that this is not a final clinical diagnosis.

Constraints:
- Base your response strictly on the provided input; do not fabricate facts not present in the text;
- Output in English.
""".strip()


def _ensure_backend_on_path() -> Path:
    script_backend = Path(__file__).resolve().parents[1]
    candidates = [
        Path.cwd(),
        Path.cwd().parent,
        Path.cwd() / "backend",
        Path.cwd().parent / "backend",
        script_backend,
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
    symptoms: str,
    patient_history: str,
    diagnosis_payload: dict[str, Any],
) -> str:
    return f"""
Patient information:
- Age: {age}
- Symptoms: {symptoms}
- Patient History: {patient_history}

/diagnosis output (JSON):
{json.dumps(diagnosis_payload, ensure_ascii=False)}

Task:
Please provide a final diagnosis summary in English based on the information above.
""".strip()


def create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=DEFAULT_CHAT_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0.2,
    )


async def run_llm_diagnosis(
    llm: ChatOpenAI,
    *,
    age: int,
    symptoms: str,
    patient_history: str,
    diagnosis_payload: dict[str, Any],
) -> str:
    user_prompt = build_llm_user_prompt(
        age=age,
        symptoms=symptoms,
        patient_history=patient_history,
        diagnosis_payload=diagnosis_payload,
    )
    messages = [
        SystemMessage(content=LLM_SYSTEM_PROMPT),
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
) -> dict[str, Any]:
    async with semaphore:
        age = int(row["age"])
        symptoms = str(row["symptoms"])
        patient_history = str(row["Patient History"])
        sex = gender_numeric_to_sex(int(row["gender_numeric"]))

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
            symptoms=symptoms,
            patient_history=patient_history,
            diagnosis_payload=diagnosis_result,
        )

        print(
            f"row={row_idx} done, mentions={len(evidence)}, "
            f"llm_len={len(llm_final_output)}"
        )

        return {
            "row_index": row_idx,
            "age": age,
            "symptoms": symptoms,
            "patient_history": patient_history,
            "input_text": input_text,
            "target_y": row[TARGET_COLUMN],
            "ground_truth_diagnosis": row["Diagnosis"],
            "parse_mentions_count": len(parse_result.get("mentions", []) or []),
            "parse_output_json": json.dumps(parse_result, ensure_ascii=False),
            "diagnosis_output_json": json.dumps(diagnosis_result, ensure_ascii=False),
            "llm_final_output": llm_final_output,
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


async def run() -> None:
    args = parse_args()
    if args.top_n <= 0:
        raise ValueError("--top-n must be a positive integer.")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be a positive integer.")

    df = pd.read_csv(args.input)
    sample_df = df[FEATURE_COLUMNS + [TARGET_COLUMN]].head(args.top_n).copy()
    llm = create_llm()
    semaphore = asyncio.Semaphore(args.concurrency)

    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            process_row(
                int(row_idx),
                row,
                client=client,
                llm=llm,
                semaphore=semaphore,
            )
            for row_idx, row in sample_df.iterrows()
        ]
        rows = await asyncio.gather(*tasks)

    rows.sort(key=lambda item: int(item["row_index"]))
    results_df = pd.DataFrame(rows)

    output_path = args.output or Path(f"data/eval_agent_top{args.top_n}_results.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved: {output_path.resolve()}")
    print(f"Rows: {len(results_df)}")


if __name__ == "__main__":
    asyncio.run(run())

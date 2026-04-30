# ISE547
# AI Triage Agent for Structured Patient Intake and Guided Clinical Routing

This repository contains the final project for ISE 547. The project is a full-stack AI triage agent that converts free-text patient symptom descriptions into structured intake information, asks follow-up questions when the case is ambiguous, consults a diagnosis knowledge base, and produces interpretable care-routing recommendations.

The system is designed as an intake-and-routing assistant, not as a replacement for licensed medical diagnosis.

## Demo

- Project website: https://ise547.link/home
- Demo username: ISE547
- Demo password: zkj666

## Project Overview

Patients often describe symptoms in incomplete and unstructured language. However, real healthcare workflows require structured intake, clarification, and safe next-step guidance. This project addresses that gap by combining a multi-step AI interview workflow with external diagnosis support and a deployable web interface.

The final system includes:

- A React + TypeScript frontend for patient intake and chat interaction
- A FastAPI backend for API logic and workflow execution
- A LangGraph-based state machine for symptom parsing, follow-up questioning, and final summary generation
- OpenRouter-hosted language models for natural-language interaction
- Infermedica API support for symptom parsing and diagnosis guidance
- SQLite-based session and conversation history
- Docker Compose support for local deployment
- Batch evaluation scripts for comparing the interview agent with prompt-only LLM baselines

Evaluation Summary

The system was evaluated on a fixed 120-case closed-set benchmark sampled from a multilingual healthcare text dataset. The final interview agent was compared against four prompt-only LLM baselines:

GPT-4o-mini
Claude-3.5-haiku
Qwen-2.5-7B-Instruct
Llama-3.1-8B-Instruct

Safety Note

This project is an educational prototype. It is intended for structured patient intake and care-routing support only. It should not be used as a substitute for licensed medical diagnosis, emergency care, or professional clinical judgment.

## Repository Structure

```text
ISE547/
├── backend/        # FastAPI backend, LangGraph workflow, evaluation scripts, data processing
├── frontend/       # React + TypeScript frontend
├── ops/            # Deployment scripts and production operation files
├── docker-compose.yml
├── .env.example
└── README.md
Quick setup and architecture notes for the ISE547 project.

## Requirements

- Python 3.12+
- `uv`
- Bun
- Supervisor (for production deployment)

## Demo Website

Try the online demo here: [https://ise547.link/home](https://ise547.link/home).

## Graph Architecture

The backend diagnosis flow is implemented in `backend/app/core/langgraph/graph.py`.

```text
START
  -> parse_first_stage
       ├─ has evidence -> diagnosis_kb_step
       └─ no evidence  -> first_stage_need_more -> END

diagnosis_kb_step
  ├─ has follow-up question and user continues
  │    -> ask_human_for_kb_choice
  │    -> apply_user_choice_to_evidence
  │    -> diagnosis_kb_step (loop)
  └─ no follow-up question or user requests final result
       -> final_diagnosis_summary -> END
```

## Local Development

### Start Backend (port 8000)

```bash
cd backend
uv sync
make dev
```

### Start Frontend

```bash
cd frontend
bun install
bun run dev
```

## Regenerate Frontend API Client

```bash
cd backend
make gen-client
```

## Data Sampling Script

Use the sampling script to build a fixed 120-row evaluation set from the diagnosis dataset.

```bash
cd backend
uv run -m scripts.extract_sample
```

Data cleaning protocol (applied in this order):

1. Remove exact duplicates where all fields in `age + gender + Patient History + symptoms + Diagnosis` are identical.
2. Remove rows with empty `Diagnosis`, empty `Diagnosis Category`, or `Diagnosis Category = Unknown`.
3. Remove direct label-leakage rows where normalized `Diagnosis` is a substring of normalized `Patient History` (lowercased, punctuation removed, whitespace compressed).

Fixed stratified quotas (total = 120):

- `Hip-related disorders`: 50
- `Musculoskeletal disorders`: 25
- `Bone-related disorders`: 20
- `Other`: 15
- `Spinal disorders`: 10

By default, the script reads:

- `scripts/data/updated_result_with_BERT.csv`

and writes:

- `scripts/data/updated_result_with_BERT_eval_120.csv`

Optional arguments:

- `--input`: input CSV path
- `--output`: output CSV path
- `--seed`: random seed for reproducibility (default: 42)

## Production Deployment

Run from the repository root:

```bash
BACKEND_PORT=8000 bash ops/deploy.sh deploy
```

Common commands:

```bash
bash ops/deploy.sh status
bash ops/deploy.sh restart
bash ops/deploy.sh stop
```

## Logs

```bash
tail -f backend/logs/backend.stderr.log
```

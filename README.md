# ISE547

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

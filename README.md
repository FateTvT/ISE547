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

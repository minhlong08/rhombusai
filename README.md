# Rhombus AI: scheduled ETL (S3 -> GCS) resilience tests

Tests a Rhombus AI pipeline the way a customer would use it (S3 source, AI-built cleaning pipeline, GCS destination, schedule), then breaks the input with schema drift and semantic drift.

## 1. Setup and how to run

Prereqs: Python 3.10+, Node 18+, an S3 bucket, a GCS bucket, a Rhombus AI account.

```bash
# Datasets (deterministic, already committed)
python datasets/generate.py

# UI tests (Playwright)
cd ui-tests && npm install && npx playwright install chromium
cp .env.example .env   # fill in
npm test               # headed: npm run test:headed ; record real selectors: npm run codegen

# API tests (pytest)
cd api-tests && pip install -r requirements.txt
cp .env.example .env && set -a && . ./.env && set +a   # values from DevTools > Network
pytest -v

# Data validation
cd data-validation && pip install -r requirements.txt
gcloud auth application-default login
python fetch_gcs.py gs://<bucket>/<prefix>/ gcs_baseline.csv
python validate.py --label baseline --input ../datasets/baseline.csv --output gcs_baseline.csv --output2 gcs_baseline_run2.csv
python fetch_gcs.py gs://<bucket>/<prefix>/ gcs_<case>.csv
./run_case.sh <case> <dataset-file> 
```
Edit `data-validation/rules.json` so the cleaning rules match the prompt you gave the AI builder.

Drift procedure: run baseline, then for each case overwrite the S3 file with `datasets/<case>.csv`, wait for the **scheduled** run, download GCS output, validate, record in `observations/<case>.md`, restore baseline.

## 2. Observations summary

| Case | Change | Pipeline stopped? | Chatbot fix worked? | Details |
|---|---|---|---|---|
| Drop column | `country` removed | Yes | Yes | [file](observations/schema-drop-column.md) |
| Rename column | `email` -> `email_address` | Yes | Yes | [file](observations/schema-rename-column.md) |
| Change type | `quantity` int -> text | Yes | Yes | [file](observations/schema-change-type.md) |
| Add column | `loyalty_tier` added | Yes | Yes | [file](observations/schema-add-column.md) |
| All four together | combined | Yes | Yes | [file](observations/schema-all-combined.md) |
| Dollars to cents | `amount_usd` x100 | Yes | n/a | [file](observations/semantic-dollars-to-cents.md) |
| mm/dd to dd/mm | `signup_date` swap | Yes | n/a | [file](observations/semantic-date-mdy-to-dmy.md) |
| Status recoded | `shipped` -> `S` | No | n/a | [file](observations/semantic-status-recoded.md) |


## Design notes
- Semantic drift is only detectable against a reference. The validator compares cleaned output to the baseline output joined on `order_id`, plus input-scale checks.
- The baseline contains ambiguous dates (day <= 12) on purpose; otherwise day/month swaps are unambiguous and invisible.
- `datasets/` plus `simulate_platform.py` prove the validator catches drift offline; that simulator says nothing about Rhombus AI.

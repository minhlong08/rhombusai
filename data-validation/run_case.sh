#!/usr/bin/env bash
# ./run_case.sh <label> <dataset-file-name> [second-output.csv]
# Assumes you already downloaded gcs_<label>.csv (python fetch_gcs.py ...) and gcs_baseline.csv exists.
set -u; cd "$(dirname "$0")"; L=$1; F=$2
python validate.py --label "$L" --input "../datasets/$F" --output "gcs_$L.csv" \
  --baseline-input ../datasets/baseline.csv --baseline-output gcs_baseline.csv ${3:+--output2 "$3"} | tee "reports/$L.txt"

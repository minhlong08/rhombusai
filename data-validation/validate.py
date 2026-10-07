#!/usr/bin/env python3
"""Compare GCS output with S3 input.

Usage:
  python validate.py --label baseline --input ../datasets/baseline.csv --output gcs_baseline.csv
  python validate.py --label semantic-cents --input ../datasets/semantic-dollars-to-cents.csv \
      --output gcs_cents.csv --baseline-input ../datasets/baseline.csv --baseline-output gcs_baseline.csv
  python validate.py ... --output2 second_run_same_input.csv     # determinism between two runs

Exit code 0 = no FAIL, 1 = at least one FAIL. A JSON report is written to --report (default reports/<label>.json).
Checks are independent so one broken input never hides the others.
"""
import argparse, json, pathlib, re, sys, hashlib
import pandas as pd

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
results = []


def rec(check, status, detail=""):
    results.append({"check": check, "status": status, "detail": detail})
    print(f"[{status:4}] {check}" + (f" - {detail}" if detail else ""))


def load(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def blank(s):
    return s.str.strip().eq("")


def num(s):
    return pd.to_numeric(s.str.replace(r"[$,\s]", "", regex=True), errors="coerce")


# ---------- 1. schema ----------
def check_schema(inp, out, rules):
    exp_in, exp_out = rules["expected_input_columns"], rules["expected_output_columns"]
    miss_in, extra_in = [c for c in exp_in if c not in inp.columns], [c for c in inp.columns if c not in exp_in]
    if miss_in or extra_in:
        rec("schema.input_matches_expected", "WARN", f"input drifted: missing={miss_in} unexpected={extra_in}")
    else:
        rec("schema.input_matches_expected", "PASS")
    miss, extra = [c for c in exp_out if c not in out.columns], [c for c in out.columns if c not in exp_out]
    if miss or extra:
        rec("schema.output_matches_expected", "FAIL", f"output missing={miss} unexpected={extra}")
    elif list(out.columns) != exp_out:
        rec("schema.output_column_order", "WARN", f"order {list(out.columns)}")
    else:
        rec("schema.output_matches_expected", "PASS")
    # silent carry-on: input drifted but output looks clean/unchanged
    if (miss_in or extra_in) and not (miss or extra):
        rec("schema.silent_masking", "FAIL", "input schema drifted yet output has the baseline schema - check whether values are NULL-filled/stale")


# ---------- 2. row counts ----------
def check_rows(inp, out, rules):
    key = rules["key_column"]
    n_in, n_out = len(inp), len(out)
    uniq_in = inp.drop_duplicates().shape[0]
    rec("rows.output_not_empty", "PASS" if n_out else "FAIL", f"in={n_in} out={n_out}")
    rec("rows.output_le_unique_input", "PASS" if n_out <= uniq_in else "FAIL", f"unique_input={uniq_in} out={n_out}")
    if key in inp.columns:
        extra = set(out[key]) - set(inp[key])
        rec("rows.no_invented_keys", "PASS" if not extra else "FAIL", f"{len(extra)} keys in output not in input")
    rec("rows.dropped_reported", "INFO", f"{n_in - n_out} of {n_in} rows removed ({(n_in - n_out) / max(n_in, 1):.0%})")


# ---------- 3. cleaning rules ----------
def check_cleaning(out, rules):
    key = rules["key_column"]
    if rules.get("dedupe") and key in out.columns:
        d = int(out.duplicated().sum()), int(out[key].duplicated().sum())
        rec("clean.no_duplicate_rows", "PASS" if d[0] == 0 else "FAIL", f"{d[0]} full duplicates")
        rec("clean.unique_key", "PASS" if d[1] == 0 else "FAIL", f"{d[1]} repeated {key}")
    for c in rules.get("required_non_null", []):
        if c in out.columns:
            n = int(blank(out[c]).sum())
            rec(f"clean.non_null[{c}]", "PASS" if n == 0 else "FAIL", f"{n} blank")
    if rules.get("email_valid_lowercase_trimmed") and "email" in out.columns:
        bad = int((~out["email"].map(lambda e: bool(EMAIL_RE.match(e)))).sum())
        rec("clean.email_valid_lower_trimmed", "PASS" if bad == 0 else "FAIL", f"{bad} bad")
    if rules.get("name_trimmed") and "customer_name" in out.columns:
        bad = int((out["customer_name"] != out["customer_name"].str.strip()).sum())
        rec("clean.name_trimmed", "PASS" if bad == 0 else "FAIL", f"{bad} untrimmed")
    if rules.get("amount_numeric_non_negative") and "amount_usd" in out.columns:
        v = num(out["amount_usd"])
        bad = int(v.isna().sum() + (v < 0).sum())
        rec("clean.amount_numeric_non_negative", "PASS" if bad == 0 else "FAIL", f"{bad} bad")
    if rules.get("date_iso_format") and "signup_date" in out.columns:
        bad = int((~out["signup_date"].map(lambda s: bool(ISO_RE.match(s)))).sum())
        rec("clean.date_iso", "PASS" if bad == 0 else "FAIL", f"{bad} non-ISO")
    if rules.get("status_lowercase") and "status" in out.columns:
        bad = int((out["status"] != out["status"].str.lower()).sum())
        rec("clean.status_lowercase", "PASS" if bad == 0 else "FAIL", f"{bad} not lowercase")
    if rules.get("quantity_range") and "quantity" in out.columns:
        lo, hi = rules["quantity_range"]
        q = num(out["quantity"])
        bad = int((q.isna() | (q < lo) | (q > hi)).sum())
        rec("clean.quantity_in_range", "PASS" if bad == 0 else "FAIL", f"{bad} outside {lo}-{hi}")


# ---------- 4. determinism ----------
def digest(df):
    return hashlib.sha256(df.sort_values(list(df.columns)).to_csv(index=False).encode()).hexdigest()


def check_determinism(out, other, label):
    if other is None:
        rec("determinism", "SKIP", f"no second output given ({label})")
        return
    same = digest(out) == digest(other)
    rec("determinism.same_input_same_output", "PASS" if same else "FAIL",
        "" if same else f"rows {len(out)} vs {len(other)}; cols equal={list(out.columns) == list(other.columns)}")


# ---------- 5. semantic drift ----------
def check_semantic(inp, out, b_in, b_out, rules):
    s, key = rules["semantic"], rules["key_column"]
    nc, dc, cc = s["numeric_column"], s["date_column"], s["categorical_column"]
    tol = s["numeric_median_ratio_tolerance"]
    # (a) input-side: does the input itself look different from baseline input?
    if b_in is not None and nc in inp.columns and nc in b_in.columns:
        r = num(inp[nc]).median() / num(b_in[nc]).median()
        rec("semantic.input_numeric_scale", "PASS" if abs(r - 1) <= tol else "WARN",
            f"median {nc} ratio vs baseline input = {r:.2f}")
    # (b) output-side: compare against baseline output, joined on key
    if b_out is None:
        rec("semantic.output_vs_baseline", "SKIP", "no --baseline-output")
        return
    if nc in out.columns and nc in b_out.columns:
        r = num(out[nc]).median() / num(b_out[nc]).median()
        rec("semantic.output_numeric_scale", "PASS" if abs(r - 1) <= tol else "FAIL",
            f"median {nc} output/baseline_output = {r:.2f}")
    if dc in out.columns and dc in b_out.columns and key in out.columns:
        m = out[[key, dc]].merge(b_out[[key, dc]], on=key, suffixes=("_run", "_base"))
        diff = int((m[dc + "_run"] != m[dc + "_base"]).sum())
        rec("semantic.dates_match_baseline_for_same_key", "PASS" if diff == 0 else "FAIL",
            f"{diff}/{len(m)} shared keys have a different cleaned date" +
            (f"; e.g. {m[m[dc + '_run'] != m[dc + '_base']].head(2).values.tolist()}" if diff else ""))
        # dates that became invalid or NaT
        bad = int(pd.to_datetime(out[dc], errors="coerce").isna().sum())
        rec("semantic.dates_parseable", "PASS" if bad == 0 else "FAIL", f"{bad} unparseable")
    if cc in out.columns and cc in b_out.columns:
        new = sorted(set(out[cc]) - set(b_out[cc]))
        rec("semantic.categorical_vocabulary", "PASS" if not new else "FAIL", f"new values in {cc}: {new}")
    if key in out.columns:
        shared = out[key].isin(b_out[key]).mean()
        rec("semantic.same_rows_survive", "PASS" if shared > 0.95 else "WARN", f"{shared:.0%} of output keys also in baseline output")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--output2")
    ap.add_argument("--baseline-input")
    ap.add_argument("--baseline-output")
    ap.add_argument("--rules", default=str(pathlib.Path(__file__).parent / "rules.json"))
    ap.add_argument("--report")
    a = ap.parse_args()
    rules = json.load(open(a.rules))
    inp, out = load(a.input), load(a.output)
    o2 = load(a.output2) if a.output2 else None
    b_in = load(a.baseline_input) if a.baseline_input else None
    b_out = load(a.baseline_output) if a.baseline_output else None
    print(f"== {a.label} ==")
    for fn, args in [(check_schema, (inp, out, rules)), (check_rows, (inp, out, rules)), (check_cleaning, (out, rules)),
                     (check_determinism, (out, o2, a.label)), (check_semantic, (inp, out, b_in, b_out, rules))]:
        try:
            fn(*args)
        except Exception as e:  # a crashed check must be visible, not fatal to the rest
            rec(fn.__name__, "FAIL", f"validator error: {e!r}")
    rp = pathlib.Path(a.report or f"reports/{a.label}.json")
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps({"label": a.label, "results": results}, indent=2))
    fails = sum(r["status"] == "FAIL" for r in results)
    print(f"-- {fails} FAIL, {sum(r['status']=='WARN' for r in results)} WARN -> {rp}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

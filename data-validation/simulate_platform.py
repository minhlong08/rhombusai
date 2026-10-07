"""Stand-in for the Rhombus pipeline, ONLY to prove the validator works offline.
NOT evidence about Rhombus AI. Applies a naive cleaner to an input CSV."""
import sys, pandas as pd, re
from dateutil import parser as dp

def clean(src, dst):
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    for c in df.columns: df[c] = df[c].str.strip()
    df["customer_name"] = df["customer_name"].str.title()
    df["email"] = df["email"].str.lower()
    df["status"] = df["status"].str.lower()
    def d(s):
        try: return dp.parse(s, dayfirst=False).date().isoformat()
        except Exception: return ""
    df["signup_date"] = df["signup_date"].map(d)
    df = df[(df.customer_name != "") & df.email.str.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")]
    a = pd.to_numeric(df.amount_usd, errors="coerce"); df = df[a >= 0]
    q = pd.to_numeric(df.quantity, errors="coerce"); df = df[(q >= 1) & (q <= 100)]
    df = df[df.signup_date != ""].drop_duplicates()
    df.to_csv(dst, index=False)

if __name__ == "__main__": clean(sys.argv[1], sys.argv[2])

"""Generate the baseline messy CSV and every drifted variant (deterministic, seed=42)."""
import csv, random, pathlib
from datetime import date, timedelta

random.seed(42)
OUT = pathlib.Path(__file__).parent
BASE_COLS = ["order_id", "customer_name", "email", "signup_date", "country", "amount_usd", "status", "quantity"]
FIRST = ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi", "ivan", "judy"]
LAST = ["smith", "jones", "lee", "brown", "garcia", "khan", "nguyen", "wilson"]
COUNTRIES = ["Australia", "australia", "AU", "United States", "USA", "us", "Canada", "CA"]
STATUS = ["shipped", "Shipped", "PENDING", "pending", "cancelled", "Cancelled"]


def fmt_date(d, kind):
    return {"iso": d.isoformat(), "mdy": d.strftime("%m/%d/%Y"), "mon": d.strftime("%d %b %Y")}[kind]


def make_rows(n=150):
    rows = []
    for i in range(1, n + 1):
        f, l = random.choice(FIRST), random.choice(LAST)
        d = date(2023, 1, 1) + timedelta(days=random.randint(0, 700))
        # ~half of dates have day <= 12 so mm/dd vs dd/mm is genuinely ambiguous (needed for semantic drift)
        if d.day <= 12 and random.random() < 0.4:
            d = d.replace(day=random.randint(13, 28))
        name = random.choice([f"{f} {l}", f"  {f.upper()} {l.upper()} ", f"{f.title()} {l.title()}"])
        email = f"{f}.{l}{i}@example.com"
        rows.append({
            "order_id": 1000 + i, "customer_name": name,
            "email": random.choice([email, email.upper(), f" {email} "]),
            "signup_date": fmt_date(d, random.choice(["iso", "mdy", "mon"])),
            "country": random.choice(COUNTRIES),
            "amount_usd": f"{random.uniform(5, 500):.2f}",
            "status": random.choice(STATUS), "quantity": random.randint(1, 10),
        })
    for r in random.sample(rows, 8): r["email"] = ""
    for r in random.sample(rows, 6): r["amount_usd"] = ""
    for r in random.sample(rows, 5): r["customer_name"] = ""
    for r in random.sample(rows, 6): r["email"] = "not-an-email"
    for r in random.sample(rows, 5):
        if r["amount_usd"]: r["amount_usd"] = "-" + r["amount_usd"]
    for r in random.sample(rows, 4): r["amount_usd"] = "N/A"
    for r in random.sample(rows, 4): r["quantity"] = random.choice([0, -3, 999])
    rows += [dict(r) for r in random.sample(rows, 12)]  # exact duplicates
    random.shuffle(rows)
    return rows


def write(name, cols, rows):
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def isnum(s):
    try: float(s); return True
    except ValueError: return False


def main():
    base = make_rows()
    write("baseline.csv", BASE_COLS, base)

    # ---- schema drift: one change each ----
    write("schema-drop-column.csv", [c for c in BASE_COLS if c != "country"], base)
    write("schema-rename-column.csv",
          ["order_id", "customer_name", "email_address", "signup_date", "country", "amount_usd", "status", "quantity"],
          [{**r, "email_address": r["email"]} for r in base])
    typed = [{**r, "quantity": f"{r['quantity']} units"} for r in base]  # int -> text
    write("schema-change-type.csv", BASE_COLS, typed)
    write("schema-add-column.csv", BASE_COLS + ["loyalty_tier"],
          [{**r, "loyalty_tier": random.choice(["gold", "silver", "bronze"])} for r in base])
    write("schema-all-combined.csv",
          ["order_id", "customer_name", "email_address", "signup_date", "amount_usd", "status", "quantity", "loyalty_tier"],
          [{**r, "email_address": r["email"], "loyalty_tier": "gold"} for r in typed])

    # ---- semantic drift: identical structure to baseline ----
    write("semantic-dollars-to-cents.csv", BASE_COLS,
          [{**r, "amount_usd": str(round(float(r["amount_usd"]) * 100)) if isnum(r["amount_usd"]) else r["amount_usd"]} for r in base])

    def swap(s):
        if "/" in s:
            m, d, y = s.split("/"); return f"{d}/{m}/{y}"
        return s
    write("semantic-date-mdy-to-dmy.csv", BASE_COLS, [{**r, "signup_date": swap(r["signup_date"])} for r in base])

    recode = {"shipped": "S", "pending": "P", "cancelled": "C"}
    write("semantic-status-recoded.csv", BASE_COLS, [{**r, "status": recode[r["status"].lower()]} for r in base])


if __name__ == "__main__":
    main()
